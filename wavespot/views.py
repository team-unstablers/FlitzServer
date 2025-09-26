from django.core.cache import cache
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import Http404
from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from card.models import CardDistribution
from safety.models import UserBlock
from user.models import User
from user_auth.authentication import UserSessionAuthentication
from wavespot.authentication import WaveSpotAppClipAuthentication
from wavespot.models import WaveSpot, WaveSpotAppClipSession, WaveSpotCardDistribution, WaveSpotPost
from wavespot.serializers import (WaveSpotAuthorizationSerializer, WaveSpotAppClipAuthorizationSerializer,
    WaveSpotSerializer, WaveSpotCardDistributionCreateSerializer, WaveSpotCardDistributionSerializer,
    WaveSpotPostSerializer, WaveSpotPostCreateSerializer)


# Create your views here.

class WaveSpotViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WaveSpotSerializer

    def get_authenticators(self):
        is_wavespot_authorize_app_clip = self.request.META['PATH_INFO'].startswith('/wavespot/authorize/app-clip')

        if is_wavespot_authorize_app_clip:
            return []

        return [
            WaveSpotAppClipAuthentication(),
            UserSessionAuthentication(),
        ]

    def get_queryset(self):
        user = self.request.user

        if isinstance(user, User):
            wavespot_id = cache.get(f'user:{user.id}:wavespot:current', None)

            if wavespot_id is None:
                raise Exception("No current wavespot for user")

            return WaveSpot.objects.filter(
                id=wavespot_id,
                disabled_at__isnull=True,
            )
        elif isinstance(user, WaveSpotAppClipSession):
            return WaveSpot.objects.filter(
                id=user.wavespot_id,
                disabled_at__isnull=True,
            )
        else:
            return WaveSpot.objects.none()

    def list(self, request, *args, **kwargs):
        raise NotImplementedError("Listing all wavespots is not supported.")

    @action(methods=['GET'], detail=False, url_path='current', url_name='current')
    def current(self, request):
        queryset = self.get_queryset()
        if not queryset.exists():
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.no_current'
            }, status=404)

        serializer = WaveSpotSerializer(queryset.first())
        return Response(serializer.data, status=200)

    @action(methods=['POST'], detail=None, url_path='authorize', url_name='authorize_user')
    def authorize_user(self, request):
        serializer = WaveSpotAuthorizationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.auth_failed'
            }, status=400)

        validated_data = serializer.validated_data

        wavespot = WaveSpot.objects.filter(
            major=validated_data['major'],
            minor=validated_data['minor'],
            disabled_at__isnull=True,
        ).first()

        if wavespot is None:
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.auth_failed'
            }, status=400)

        if not wavespot.authorize(validated_data['latitude'], validated_data['longitude']):
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.auth_failed'
            }, status=400)

        cache.set(f'user:{request.user.id}:wavespot:current', wavespot.id, timeout=60 * 60 * 3) # 3 hours

        return Response({
            'is_success': True,
        }, status=200)

    @action(methods=['POST'], detail=None, url_path='authorize/app-clip', url_name='authorize_app_clip')
    def authorize_app_clip(self, request):
        serializer = WaveSpotAppClipAuthorizationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.auth_failed'
            }, status=400)

        validated_data = serializer.validated_data

        wavespot = WaveSpot.objects.filter(
            major=validated_data['major'],
            minor=validated_data['minor'],
            disabled_at__isnull=True,
        ).first()

        if wavespot is None:
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.auth_failed'
            }, status=400)

        if not wavespot.authorize(validated_data['latitude'], validated_data['longitude']):
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.auth_failed'
            }, status=400)

        app_clip_session = WaveSpotAppClipSession.objects.create(
            wavespot=wavespot,
            user_agent=validated_data['user_agent'],
            nickname=validated_data['nickname'],
            initiated_from=request.META.get('REMOTE_ADDR'),
        )

        token = app_clip_session.create_token()
        app_clip_session.save()

        return Response({
            'token': token,
        }, status=200)

class WaveSpotPostViewSet(viewsets.ModelViewSet):
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_authenticators(self):
        return [
            WaveSpotAppClipAuthentication(),
            UserSessionAuthentication(),
        ]

    def get_serializer_class(self):
        if self.action == 'create':
            return WaveSpotPostCreateSerializer
        return WaveSpotPostSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        try:
            context['wavespot'] = WaveSpot.objects.get(
                id=self.get_wavespot_id(),
                disabled_at__isnull=True
            )
        except WaveSpot.DoesNotExist:
            pass
        return context

    def get_wavespot_id(self):
        return self.kwargs['wavespot_id']

    def get_queryset(self):
        user = self.request.user
        wavespot_id = self.get_wavespot_id()

        if isinstance(user, User):
            current_id = cache.get(f'user:{user.id}:wavespot:current', None)

            if wavespot_id != current_id:
                raise Http404()

            return WaveSpotPost.objects.filter(
                wavespot_id=wavespot_id,
                deleted_at__isnull=True,
            ).exclude(
                Exists(
                    UserBlock.objects.filter(
                        user=user,
                        blocked_by=OuterRef('author_user')
                    )
                )
            ).exclude(
                Exists(
                    UserBlock.objects.filter(
                        user=OuterRef('author_user'),
                        blocked_by=user
                    )
                )
            ).select_related('author_user', 'author_app_clip').prefetch_related('images')
        elif isinstance(user, WaveSpotAppClipSession):
            if wavespot_id != user.wavespot_id:
                raise Http404()

            return WaveSpotPost.objects.filter(
                wavespot_id=wavespot_id,
                deleted_at__isnull=True,
            ).select_related('author_user', 'author_app_clip').prefetch_related('images')
        else:
            return WaveSpotPost.objects.none()

    def create(self, request, *args, **kwargs):
        """포스트 생성 (이미지 포함)"""
        user = request.user
        wavespot_id = self.get_wavespot_id()

        # 권한 검증
        if isinstance(user, User):
            current_id = cache.get(f'user:{user.id}:wavespot:current', None)
            if wavespot_id != current_id:
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.not_in_range'
                }, status=403)
        elif isinstance(user, WaveSpotAppClipSession):
            if wavespot_id != user.wavespot_id:
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.not_authorized'
                }, status=403)
        else:
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.permission_denied'
            }, status=403)

        # Serializer를 사용해 생성
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        # 생성된 포스트를 다시 조회용 Serializer로 반환
        post = serializer.instance
        response_serializer = WaveSpotPostSerializer(post, context=self.get_serializer_context())
        return Response(response_serializer.data, status=201, headers=headers)

    def update(self, request, *args, **kwargs):
        """포스트 수정 - 작성자만 가능"""
        instance = self.get_object()
        user = request.user

        # 작성자 확인
        if isinstance(user, User):
            if instance.author_user != user:
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.permission_denied'
                }, status=403)
        elif isinstance(user, WaveSpotAppClipSession):
            if instance.author_app_clip != user:
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.permission_denied'
                }, status=403)
        else:
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.permission_denied'
            }, status=403)

        # content만 수정 가능 (이미지는 수정 불가)
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """포스트 삭제 - 작성자만 가능"""
        instance = self.get_object()
        user = request.user

        # 작성자 확인
        if isinstance(user, User):
            if instance.author_user != user:
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.permission_denied'
                }, status=403)
        elif isinstance(user, WaveSpotAppClipSession):
            if instance.author_app_clip != user:
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.permission_denied'
                }, status=403)
        else:
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.permission_denied'
            }, status=403)

        # Soft delete
        from django.utils import timezone
        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=204)


class WaveSpotCardDistributionViewSet(viewsets.ModelViewSet):
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    serializer_class = WaveSpotCardDistributionSerializer

    def get_wavespot_id(self):
        return self.kwargs['wavespot_id']

    def get_queryset(self):
        user = self.request.user
        wavespot_id = self.get_wavespot_id()

        if isinstance(user, User):
            current_id = cache.get(f'user:{user.id}:wavespot:current', None)

            if wavespot_id != current_id:
                raise Http404()

            return WaveSpotCardDistribution.objects.filter(
                wavespot_id=wavespot_id,
                deleted_at__isnull=True,
            ).exclude(
                Exists(
                    UserBlock.objects.filter(
                        user=user,
                        blocked_by=OuterRef('card__user')
                    )
                )
            ).exclude(
                Exists(
                    UserBlock.objects.filter(
                        user=OuterRef('card__user'),
                        blocked_by=user
                    )
                )
            ).select_related('card', 'card__user')
        elif isinstance(user, WaveSpotAppClipSession):
            if wavespot_id != user.wavespot_id:
                raise Http404()

            return WaveSpotCardDistribution.objects.filter(
                wavespot_id=wavespot_id,
                deleted_at__isnull=True,
            ).select_related('card', 'card__user')
        else:
            return WaveSpotCardDistribution.objects.none()

    def create(self, request, *args, **kwargs):
        raise NotImplementedError("Creation is not supported.")

    def partial_update(self, request, *args, **kwargs):
        raise NotImplementedError("Partial update is not supported.")

    def update(self, request, *args, **kwargs):
        raise NotImplementedError("Update is not supported.")

    def destroy(self, request, *args, **kwargs):
        if not isinstance(request.user, User):
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.permission_denied'
            }, status=403)

        instance: WaveSpotCardDistribution = self.get_object()

        if instance.card.user != request.user:
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.permission_denied'
            }, status=403)

        # Soft delete
        from django.utils import timezone
        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=204)

    @action(methods=['POST'], detail=False, url_path='create', url_name='create_distribution')
    def create_distribution(self, request, *args, **kwargs):
        if not isinstance(request.user, User):
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.permission_denied'
            }, status=403)

        serializer = WaveSpotCardDistributionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.invalid_data',
            }, status=400)

        with transaction.atomic():
            validated_data = serializer.validated_data

            if WaveSpotCardDistribution.objects.filter(
                wavespot_id=self.get_wavespot_id(),
                card_id=validated_data['card_id'],
                deleted_at__isnull=False,
            ).exists():
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.already_distributed'
                }, status=400)

            WaveSpotCardDistribution.objects.create(
                wavespot_id=self.get_wavespot_id(),
                card_id=validated_data['card_id']
            )

        return Response({
            'is_success': True,
        }, status=201)

    @action(methods=['POST'], detail=True, url_path='distribute', url_name='distribute')
    def distribute(self, request, *args, **kwargs):
        instance: WaveSpotCardDistribution = self.get_object()
        user = request.user

        if not isinstance(user, User):
            return Response({
                'is_success': False,
                'reason': 'fz.wavespot.permission_denied'
            }, status=403)

        with transaction.atomic():
            if not instance.can_distribute(user):
                return Response({
                    'is_success': False,
                    'reason': 'fz.wavespot.cannot_distribute'
                }, status=400)

            instance.distribute(user)

        return Response({
            'is_success': True,
        }, status=200)
