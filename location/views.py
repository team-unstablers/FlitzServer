from django.db import transaction

from rest_framework import permissions, viewsets, parsers, status
from rest_framework.decorators import action, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from flitz.exceptions import UnsupportedOperationException
from location.match import UserMatcher
from location.models import DiscoverySession, DiscoveryHistory, UserLocation
from location.serializers import DiscoveryReportSerializer, UpdateLocationSerializer


# Create your views here.

class FlitzWaveViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='discovery/start')
    def start_discovery(self, request: Request):
        """
        사용자들이 서로를 발견하고 카드를 교환하는 기능인 FlitzWave (디스커버리 세션)을 시작합니다.
        """
        # 디스커버리 세션을 시작합니다.

        # 기존 디스커버리 세션을 전부 비활성화합니다.
        DiscoverySession.objects.filter(
            user=request.user,
            is_active=True
        ).update(
            is_active=False
        )

        # 새로운 디스커버리 세션을 생성합니다.
        discovery_session = DiscoverySession.objects.create(
            user=request.user,
            is_active=True
        )

        return Response({
            'session_id': discovery_session.pk
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='discovery/stop')
    def stop_discovery(self, request: Request):
        """
        FlitzWave (디스커버리 세션)을 중지합니다.
        """
        DiscoverySession.objects.filter(
            user=request.user,
            is_active=True
        ).update(
            is_active=False
        )

        return Response({
            'is_success': True
        })
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='discovery/update')
    def update_location(self, request: Request):
        """
        사용자의 위치 정보를 업데이트합니다.
        """
        serializer = UpdateLocationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data

        with transaction.atomic():
            request.user.update_location(
                latitude=validated_data['latitude'],
                longitude=validated_data['longitude'],
                altitude=validated_data.get('altitude'),
                accuracy=validated_data.get('accuracy')
            )

        return Response({
            'is_success': True
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='discovery/report')
    def report_discovery(self, request: Request):
        """
        다른 사용자를 발견했음을 서버에 보고합니다.
        """
        serializer = DiscoveryReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data

        with transaction.atomic():
            request.user.update_location(
                latitude=validated_data['latitude'],
                longitude=validated_data['longitude'],
                altitude=validated_data.get('altitude'),
                accuracy=validated_data.get('accuracy')
            )

            session = DiscoverySession.objects.filter(
                id=validated_data['session_id'],
                user=request.user,
                is_active=True
            ).first()

            discovered_session = DiscoverySession.objects.filter(
                id=validated_data['discovered_session_id'],
                is_active=True
            ).exclude(
                user=request.user
            ).first()

            if not session or not discovered_session:
                return Response({ 'is_success': True })

            matcher = UserMatcher(session, discovered_session)

            if not matcher.sanity_check():
                # TODO: Sentry.capture_message('FlitzWave: sanity check failed')
                return Response({ 'is_success': True })

            if not matcher.prerequisite_check():
                # TODO: Sentry.capture_message('FlitzWave: prerequisite check failed')
                return Response({ 'is_success': True })

            # TODO: MatcherHistory 모델 생성, 왜 실패했는지 등등을 분석할 수 있으면 좋을 것 같아
            matched = matcher.try_match()

            return Response({
                'is_success': True
            })
