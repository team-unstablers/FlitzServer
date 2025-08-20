import uuid

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from twisted.words.im.basechat import Conversation

from card.models import CardDistribution, CardFavoriteItem
from flitz.thumbgen import generate_thumbnail
from messaging.models import DirectMessageConversation
from safety.models import UserWaveSafetyZone, UserBlock
from safety.serializers import UserWaveSafetyZoneSerializer
from user.models import User, UserIdentity, UserMatch, UserSettings
from user.serializers import PublicUserSerializer, PublicSelfUserSerializer, SelfUserIdentitySerializer, \
    UserRegistrationSerializer, UserSettingsSerializer

from flitz.exceptions import UnsupportedOperationException
from user_auth.models import UserSession

# Create your views here.

class PublicUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicUserSerializer

    def get_permissions(self):
        if self.action == 'register':
            return [permissions.AllowAny()]

        return [permissions.IsAuthenticated()]

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
            return Response({'is_success': False, 'message': 'Identity not found'}, status=404)

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
            return Response({'is_success': False, 'message': 'Wave safety zone settings not available'}, status=404)

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




    @action(detail=False, methods=['POST'], url_path='register')
    def register(self, request, *args, **kwargs):
        # TODO: rate limiting by IP address?
        # TODO: recaptcha validation

        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({}, status=400)

        validated_data = serializer.validated_data

        with transaction.atomic():

            user = User.objects.create_user(
                username=validated_data['username'],
                email=None,
                password=validated_data['password'],
            )

            user.display_name = validated_data['display_name']
            user.title = validated_data['title']
            user.bio = validated_data['bio']
            user.hashtags = validated_data['hashtags']

            # TODO: NICE 인증 이후 휴대폰 번호 설정하도록 해야 함

            user.is_active = True
            user.save()

        return Response({'is_success': True}, status=201)