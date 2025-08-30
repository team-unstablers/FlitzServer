import secrets
from datetime import timedelta

import jwt
from django.conf import settings
from django.core.cache import cache
from uuid_v7.base import uuid7

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as t

from rest_framework import permissions, viewsets, serializers, status
from rest_framework.decorators import action, throttle_classes
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from card.models import CardDistribution, CardFavoriteItem
from flitz.thumbgen import generate_thumbnail
from flitz.turnstile import validate_turnstile
from messaging.models import DirectMessageConversation
from safety.models import UserWaveSafetyZone, UserBlock
from safety.serializers import UserWaveSafetyZoneSerializer
from user.models import User, UserIdentity, UserMatch, UserSettings, UserDeletionPhase, UserDeletionFeedback, UserFlag
from user.registration import UserRegistrationContext
from user.serializers import PublicUserSerializer, PublicSelfUserSerializer, SelfUserIdentitySerializer, \
    UserRegistrationSerializer, UserSettingsSerializer, UserPasswdSerializer, UserDeactivationSerializer, \
    UserFlagSerializer, UserRegistrationSessionStartSerializer, UserRegistrationStartPhoneVerificationSerializer, \
    UserRegistrationCompletePhoneVerificationSerializer, UserSetEmailSerializer, UserVerifyEmailSerializer, \
    UserStartPhoneVerificationSerializer, UserCompletePhoneVerificationSerializer, UsernameAvailabilitySerializer

from flitz.exceptions import UnsupportedOperationException
from flitz.tasks import post_slack_message
from user.tasks import execute_deletion_phase, send_templated_email
from user.throttling import UserEmailRateThrottle
from user.verification.errors import AdultVerificationError
from user.verification.logics import CompletePhoneVerificationArgs
from user_auth.authentication import UserRegistrationSessionAuthentication
from user_auth.models import UserSession

# Create your views here.

class PublicUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicUserSerializer

    def get_permissions(self):
        if self.action == 'start_registration':
            return [permissions.AllowAny()]

        return [permissions.IsAuthenticated()]

    def get_authenticators(self):
        is_registration_endpoint = self.request.META['PATH_INFO'].startswith('/users/register/')

        if is_registration_endpoint:
            return [UserRegistrationSessionAuthentication()]

        return super().get_authenticators()

    def get_queryset(self):
        return User.objects.filter(disabled_at=None, fully_deleted_at=None)

    def list(self, request, *args, **kwargs):
        # 사용자 리스트는 보여져선 안됨
        raise UnsupportedOperationException()

    @action(detail=False, methods=['GET', 'PATCH'], url_path='self')
    def dispatch_self(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.get_self(request, *args, **kwargs)
        elif request.method == 'PATCH':
            return self.patch_self(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def get_self(self, request, *args, **kwargs):
        user = self.request.user
        serializer = PublicSelfUserSerializer(user)

        return Response(serializer.data)

    def patch_self(self, request, *args, **kwargs):
        user = self.request.user
        serializer = PublicSelfUserSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)

    @action(detail=False, methods=['POST'], url_path='self/passwd')
    def change_password(self, request, *args, **kwargs):
        serializer = UserPasswdSerializer(data=request.data, context={'request': request})

        try:
            serializer.is_valid(raise_exception=True)
            validated_data = serializer.validated_data

            user: User = self.request.user
            user.set_password(validated_data['new_password'])

            user.save()
        except serializers.ValidationError as e:
            return Response({
                'is_success': False,
                'reason': "fz.user.passwd.invalid_password",
            }, status=400)

        return Response({'is_success': True}, status=200)

    @action(detail=False, methods=['GET', 'PATCH'], url_path='self/identity')
    def dispatch_self_identity(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.get_self_identity(request, *args, **kwargs)
        elif request.method == 'PATCH':
            return self.patch_self_identity(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def get_self_identity(self, request, *args, **kwargs):
        user: User = self.request.user

        if not hasattr(user, 'identity'):
            return Response({'is_success': False, 'reason': 'Identity not found'}, status=404)

        identity = user.identity
        serializer = SelfUserIdentitySerializer(identity)
        return Response(serializer.data)

    def patch_self_identity(self, request, *args, **kwargs):
        user: User = self.request.user

        identity, created = UserIdentity.objects.get_or_create(
            user=user
        )

        serializer = SelfUserIdentitySerializer(identity, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)

    @action(detail=False, methods=['GET', 'PATCH'], url_path='self/settings')
    def dispatch_self_settings(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.get_self_settings(request, *args, **kwargs)
        elif request.method == 'PATCH':
            return self.patch_self_settings(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def get_self_settings(self, request, *args, **kwargs):
        user: User = self.request.user

        settings, created = UserSettings.objects.get_or_create(
            user=user
        )

        serializer = UserSettingsSerializer(settings)

        return Response(serializer.data)

    def patch_self_settings(self, request, *args, **kwargs):
        user: User = self.request.user

        settings, created = UserSettings.objects.get_or_create(
            user=user
        )

        serializer = UserSettingsSerializer(settings, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)



    @action(detail=False, methods=['GET', 'PATCH'], url_path='self/wave-safety-zone')
    def dispatch_self_wave_safety_zone(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.get_self_wave_safety_zone(request, *args, **kwargs)
        elif request.method == 'PATCH':
            return self.patch_self_wave_safety_zone(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def get_self_wave_safety_zone(self, request, *args, **kwargs):
        user: User = self.request.user

        if not hasattr(user, 'wave_safety_zone'):
            return Response({'is_success': False, 'reason': 'Wave safety zone settings not available'}, status=404)

        safety_zone = user.wave_safety_zone
        serializer = UserWaveSafetyZoneSerializer(safety_zone)
        return Response(serializer.data)

    def patch_self_wave_safety_zone(self, request, *args, **kwargs):
        user: User = self.request.user

        identity, created = UserWaveSafetyZone.objects.get_or_create(
            user=user,
            defaults={
                'radius': 300,
                'is_enabled': False,
                'enable_wave_after_exit': True,
            }
        )

        serializer = UserWaveSafetyZoneSerializer(identity, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)


    @action(detail=False, methods=['PUT'], url_path='self/apns-token')
    def set_apns_token(self, request, *args, **kwargs):
        session: UserSession = self.request.auth
        apns_token = request.data.get('apns_token')

        if apns_token is None or len(apns_token) == 0:
            return Response({'is_success': False})
        
        if session.apns_token == apns_token:
            return Response({'is_success': False})

        session.apns_token = apns_token
        session.save()

        return Response({'is_success': True})

    @action(detail=False, methods=['POST'], url_path='self/profile-image')
    def set_profile_image(self, request, *args, **kwargs):
        user: User = self.request.user

        file: UploadedFile = request.data['file']
        user.set_profile_image(file)

        serializer = PublicSelfUserSerializer(user)
        return Response(serializer.data)

    @action(detail=False, methods=['POST'], url_path='self/set-email', throttle_classes=[UserEmailRateThrottle])
    def set_email(self, request, *args, **kwargs):
        user: User = self.request.user

        if f'fz:user_email_change:{user.id}' in cache:
            return Response({
                'is_success': False,
                'reason': 'fz.user.email_change_pending'
            }, status=400)

        serializer = UserSetEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.user.invalid_email'
            }, status=400)

        validated_data = serializer.validated_data
        email = validated_data['email']

        if user.email == email:
            return Response({
                'is_success': False,
                'reason': 'fz.user.email_unchanged'
            }, status=400)

        if User.objects.filter(~Q(id=user.id), email=email).exists():
            return Response({
                'is_success': False,
                'reason': 'fz.user.email_in_use'
            }, status=400)

        verification_code = ''.join(secrets.choice('0123456789') for _ in range(6))

        context = {
            'email': email,
            'verification_code': verification_code
        }

        cache.set(f'fz:user_email_change:{user.id}', context, timeout=(10 * 60)) # 10분 유효

        send_templated_email.delay(
            to=email,
            subject=t("email.verify_request.title"),
            template_name='verify_request',
            ctx={
                'username': user.display_name,
                'verification_code': verification_code,
            }
        )

        return Response({'is_success': True}, status=200)

    @action(detail=False, methods=['POST'], url_path='self/set-email/verify')
    def verify_email(self, request, *args, **kwargs):
        user: User = self.request.user

        serializer = UserVerifyEmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.user.invalid_verification_code'
            }, status=400)

        validated_data = serializer.validated_data
        verification_code = validated_data['verification_code']

        cached = cache.get(f'fz:user_email_change:{user.id}', None)
        if cached is None or cached.get('verification_code', '') != verification_code:
            return Response({
                'is_success': False,
                'reason': 'fz.user.invalid_verification_code'
            }, status=400)

        email = cached.get('email')
        if email is None:
            return Response({
                'is_success': False,
                'reason': 'fz.user.invalid_verification_code'
            }, status=400)

        if User.objects.filter(~Q(id=user.id), email=email).exists():
            return Response({
                'is_success': False,
                'reason': 'fz.user.email_in_use'
            }, status=400)

        user.email = email
        user.save()

        cache.delete(f'fz:user_email_change:{user.id}')

        return Response({'is_success': True}, status=200)

    @action(detail=False, methods=['POST'], url_path='phone-verification/start', url_name='start_phone_verification')
    def start_phone_verification(self, request, *args, **kwargs):
        user: User = request.user

        serializer = UserStartPhoneVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.auth.invalid_request'
            }, status=400)

        payload = serializer.validated_data

        from user.verification.logics import start_phone_verification

        response, private_data = start_phone_verification({
            'country_code': payload['country_code'],
            'phone_number': payload.get('phone_number', None)
        })

        # set private data and update context

        context = {
            'country_code': payload['country_code'],
            'phone_number': payload.get('phone_number', None),

            'private_data': private_data,
        }

        cache.set(f'fz:phone_verification:{user.id}', context, timeout=(15 * 60))

        return Response({
            'is_success': True,
            'additional_data': response.get('additional_data', {}),
        }, status=200)

    @action(detail=False, methods=['POST'], url_path='phone-verification/complete', url_name='complete_phone_verification')
    def complete_phone_verification(self, request, *args, **kwargs):
        user: User = request.user

        serializer = UserCompletePhoneVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.auth.invalid_request'
            }, status=400)

        payload = serializer.validated_data

        context = cache.get(f'fz:phone_verification:{user.id}', None)
        if context is None:
            return Response({
                'is_success': False,
                'reason': 'fz.auth.session_expired'
            }, status=400)

        args: CompletePhoneVerificationArgs = {
            'country_code': context['country_code'],

            **payload
        }

        from user.verification.logics import complete_phone_verification
        private_data = context.get('private_data', None)

        try:
            response = complete_phone_verification(args, private_data)
        except AdultVerificationError:
            # 성인 인증 실패

            # TODO: 사용자를 정지 처리하거나 추가 조치를 취해야 함

            return Response({
                'is_success': False,
                'reason': 'fz.auth.adult_verification_failed'
            }, status=400)
        except Exception as e:
            # TODO: report to Sentry

            return Response({
                'is_success': False,
                'reason': f'fz.server_error'
            }, status=400)

        with transaction.atomic():
            # 휴대폰 번호 중복 확인
            if User.objects.filter(
                phone_number=response['phone_number']
            ).exists():
                # 헉, 이미 사용 중인 번호네?

                User.objects.filter(
                    phone_number=response['phone_number']
                ).update(phone_number=None)

            user.country = context['country_code']
            user.phone_number = response['phone_number']
            user.save()

        cache.delete(f'fz:user_phone_verification:{user.id}')

        return Response({
            'is_success': True,
        }, status=200)

    @action(detail=False, methods=['GET'], url_path=r'by-username/(?P<username>[a-zA-Z0-9_]+)')
    def get_by_username(self, request, username, *args, **kwargs):
        user = get_object_or_404(User, username=username)
        serializer = PublicUserSerializer(user)

        return Response(serializer.data)

    @action(detail=True, methods=['PUT', 'DELETE'], url_path='block')
    def dispatch_block_user(self, request, *args, **kwargs):
        if request.method == 'PUT':
            return self.block_user(request, *args, **kwargs)
        elif request.method == 'DELETE':
            return self.unblock_user(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def block_user(self, request, *args, **kwargs):
        user = self.request.user
        target_user = self.get_object()

        if user.id == target_user.id:
            raise UnsupportedOperationException()

        with transaction.atomic():
            _, created = UserBlock.objects.get_or_create(
                user=target_user,
                blocked_by=user,

                defaults={
                    'reason': UserBlock.Reason.BY_USER
                }
            )

            now = timezone.now()

            UserMatch.delete_match(user, target_user)

            DirectMessageConversation.objects.filter(
                participants__user=user
            ).filter(
                participants__user=target_user
            ).distinct().update(
                deleted_at=now,
            )

            CardDistribution.objects.filter(card__user=target_user, user=user).update(
                deleted_at=now,
            )

            CardFavoriteItem.objects.filter(card__user=target_user, user=user).update(
                deleted_at=now,
            )

        return Response({'is_success': True}, status=201)

    def unblock_user(self, request, *args, **kwargs):
        user = self.request.user
        target_user = self.get_object()

        if user.id == target_user.id:
            raise UnsupportedOperationException()

        with transaction.atomic():
            UserBlock.objects.filter(
                user=target_user,
                blocked_by=user
            ).delete()

        return Response({'is_success': True}, status=204)

    @action(detail=True, methods=['POST'], url_path='flag')
    def flag_user(self, request, *args, **kwargs):
        """
        사용자를 신고하는 API 엔드포인트
        """
        target_user = self.get_object()
        
        if request.user.id == target_user.id:
            return Response({
                'is_success': False,
                'reason': 'Cannot flag yourself'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = UserFlagSerializer(
            data=request.data,
            context={
                'request': request,
                'user': target_user
            }
        )

        try:
            serializer.is_valid(raise_exception=True)
            flag: UserFlag = serializer.save()

            post_slack_message.delay(
                "*새로운 사용자 신고*\n"
                f"> *신고자*: {request.user.display_name} ({request.user.username}; `{request.user.id}`)\n"
                f"> *신고 대상*: {target_user.display_name} ({target_user.username}; `{target_user.id}`)\n"
                f"> *신고 유형*: `{str(flag.reason)}`\n"
                f"> *추가 정보*: {str(flag.user_description)}"
            )

            return Response({
                'is_success': True,
            }, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({
                'is_success': False,
                'reason': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['POST'], url_path='self/deactivate')
    def deactivate_self(self, request, *args, **kwargs):
        user: User = self.request.user

        serializer = UserDeactivationSerializer(data=request.data, context={'request': request})
        try:
            serializer.is_valid(raise_exception=True)

            try:
                feedback_text = serializer.validated_data.get('feedback', '').strip()

                if feedback_text:
                    UserDeletionFeedback.objects.create(
                        feedback_text=serializer.data['feedback'],
                    )
            except Exception as e:
                print(f"Failed to save deletion feedback: {e}")

            with transaction.atomic():
                user.disabled_at = timezone.now()
                user.deletion_phase = UserDeletionPhase.INITIATED
                user.deletion_phase_scheduled_at = timezone.now()
                user.save()

            execute_deletion_phase.delay(user.id)

        except serializers.ValidationError as e:
            return Response({
                'is_success': False,
                'reason': 'fz.auth.invalid_password',
            }, status=400)

        return Response({'is_success': True}, status=200)


    @action(detail=False, methods=['POST'], url_path='register/start', url_name='start_registration')
    def start_registration(self, request, *args, **kwargs):
        """
        회원가입 세션을 시작합니다.
        """

        serializer = UserRegistrationSessionStartSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.auth.invalid_request',
            }, status=400)

        data = serializer.validated_data

        turnstile_token = serializer.validated_data['turnstile_token']

        remote_addr = request.META.get('REMOTE_ADDR')
        turnstile_response = validate_turnstile(turnstile_token, remote_addr)

        if not turnstile_response['success'] or turnstile_response['action'] != 'register':
            return Response({
                'is_success': False,
                'reason': 'fz.auth.turnstile_failed'
            }, status=401)

        # 새 세션을 생성한다
        now = timezone.now()
        session_id = str(uuid7())

        context = UserRegistrationContext(
            session_id=session_id,

            device_info=data['device_info'],
            apns_token=data['apns_token'],

            country_code=data['country_code'].upper(),
            agree_marketing_notifications=data['agree_marketing_notifications'],

            phone_verification_state=None,
            phone_number=None,

            phone_number_duplicated=False,
        )

        context.save()

        token = jwt.encode({
            'sub': session_id,
            'iat': now,
            'exp': now + timedelta(minutes=30), # 30분 이내에 회원가입을 완료해야 한다
            'x-flitz-options': '--with-love --registration',
        }, key=settings.SECRET_KEY, algorithm='HS256')

        return Response({
            'token': token,
        }, status=201)

    @action(detail=False, methods=['POST'], url_path='register/phone-verification/start', url_name='registration_start_phone_verification')
    def registration_start_phone_verification(self, request, *args, **kwargs):
        context: UserRegistrationContext = request.user

        serializer = UserRegistrationStartPhoneVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.auth.invalid_request'
            }, status=400)

        payload = serializer.validated_data

        from user.verification.logics import start_phone_verification

        response, private_data = start_phone_verification({
            'country_code': context.country_code.upper(),
            'phone_number': payload.get('phone_number', None)
        })

        # set private data and update context
        context.phone_verification_state = private_data
        context.save()

        return Response({
            'is_success': True,
            'additional_data': response.get('additional_data', {}),
        }, status=200)

    @action(detail=False, methods=['POST'], url_path='register/phone-verification/complete', url_name='registration_complete_phone_verification')
    def registration_complete_phone_verification(self, request, *args, **kwargs):
        context: UserRegistrationContext = request.user

        serializer = UserRegistrationCompletePhoneVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.auth.invalid_request'
            }, status=400)

        payload = serializer.validated_data

        args: CompletePhoneVerificationArgs = {
            'country_code': context.country_code.upper(),

            **payload
        }

        from user.verification.logics import complete_phone_verification
        private_data = context.phone_verification_state

        try:
            response = complete_phone_verification(args, private_data)
        except AdultVerificationError:
            # 성인 인증 실패 - 회원가입을 중단하고 세션을 삭제한다

            cache.delete(f'fz:user_registration:{context.session_id}')

            return Response({
                'is_success': False,
                'reason': 'fz.auth.adult_verification_failed'
            }, status=400)
        except Exception as e:
            # TODO: report to Sentry

            return Response({
                'is_success': False,
                'reason': f'fz.server_error'
            }, status=400)

        phone_number_duplicated = False

        # 휴대폰 번호 중복 확인
        if User.objects.filter(
            phone_number=response['phone_number']
        ).exists():
            # 헉, 이미 사용 중인 번호네?
            phone_number_duplicated = True

        context.phone_number = response['phone_number']
        context.phone_verification_additional_data = response.get('additional_data', {})

        context.phone_verification_state = None
        context.phone_number_duplicated = phone_number_duplicated

        context.save()

        if phone_number_duplicated:
            # 일단은 성공으로 응답하되, 추가 메시지를 보낸다
            # 클라이언트에서 이 번호를 사용해서 새로 가입할지 선택시킨다. (기존 계정은 휴대폰 번호 필드를 지우고, 새로 휴대폰 인증을 받도록 강제)
            return Response({
                'is_success': True,
                'additional_message': 'fz.auth.phone_number_duplicated'
            }, status=200)

        return Response({
            'is_success': True,
        }, status=200)


    @action(detail=False, methods=['POST'], url_path='register/username-availability')
    def registration_check_username_availability(self, request, *args, **kwargs):
        serializer = UsernameAvailabilitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.auth.username_not_available'
            }, status=400)

        existence = User.objects.filter(
            username=serializer.validated_data['username']
        ).only('id').exists()

        if existence:
            return Response({
                'is_success': False,
                'reason': 'fz.auth.username_not_available'
            }, status=400)

        return Response({
            'is_success': True,
        }, status=200)


    @action(detail=False, methods=['POST'], url_path='register/complete', url_name='complete_registration')
    def complete_registration(self, request, *args, **kwargs):
        context: UserRegistrationContext = request.user

        if context.phone_number is None:
            return Response({
                'is_success': False,
                'reason': 'fz.auth.phone_not_verified'
            }, status=400)


        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.auth.validation_failed',
                'errors': serializer.errors,
            }, status=400)

        validated_data = serializer.validated_data

        with transaction.atomic():
            if context.phone_number_duplicated:
                if validated_data['force_use_phone_number']:
                    # 휴대폰 번호가 충돌 났음에도 불구하고 신규 사용자가 가입을 원하므로,
                    # 기존 사용자의 휴대폰 번호를 지운다

                    # TODO: 이 부분은 추후에 휴대폰 번호 변경 기능이 생기면, 변경 기능에도 동일하게 적용해야 함
                    # TODO: 기존 사용자에겐 휴대폰 번호를 다시 인증 받기 전까진 앱을 사용할 수 없도록 해야 함
                    User.objects.filter(
                        phone_number=context.phone_number
                    ).update(
                        phone_number=None
                    )
                else:
                    return Response({
                        'is_success': False,
                        'reason': 'fz.auth.phone_number_duplicated'
                    }, status=400)

            user = User.objects.create_user(
                username=validated_data['username'],
                email=None,
                password=validated_data['password'],
            )

            user.display_name = validated_data['display_name']
            user.title = validated_data['title']
            user.bio = validated_data['bio']
            user.hashtags = validated_data['hashtags']

            if context.phone_verification_additional_data:
                additional_data = context.phone_verification_additional_data
                if 'birth_date' in additional_data:
                    user.birth_date = additional_data['birth_date']
                if 'di' in additional_data:
                    user.nice_di = additional_data['di']

            user.country = context.country_code
            user.set_phone_number(context.phone_number)

            user.is_active = True
            user.save()

            # create initial settings
            UserSettings.objects.update_or_create(
                user=user,
                defaults={
                    'marketing_notifications_enabled': context.agree_marketing_notifications,
                    'marketing_notifications_enabled_at': timezone.now() if context.agree_marketing_notifications else None,
                }
            )

            # create session
            session = UserSession.objects.create(
                user=user,
                description=context.device_info,
                initiated_from=request.META.get('REMOTE_ADDR'),
                apns_token=context.apns_token if context.apns_token else None,
            )

            user.primary_session = session
            user.save()

            # create token
            token = session.create_token()
            refresh_token = session.update_refresh_token()

            # clear registration session
            cache.delete(f'fz:user_registration:{context.session_id}')

        return Response({
            'token': token,
            'refresh_token': refresh_token
        }, status=201)