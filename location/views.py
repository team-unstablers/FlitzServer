from datetime import datetime, timedelta

from django.db import transaction
from django.shortcuts import render

from rest_framework import permissions, viewsets, parsers, status
from rest_framework.decorators import action, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from card.models import CardDistribution
from flitz.exceptions import UnsupportedOperationException
from location.models import DiscoverySession, DiscoveryHistory
from location.serializers import DiscoveryReportSerializer


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

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_path='discovery/report')
    def report_discovery(self, request: Request):
        """
        다른 사용자를 발견했음을 서버에 보고합니다.
        """
        serializer = DiscoveryReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        
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
            # FIXME
            raise UnsupportedOperationException()

        # 오늘 하루동안 같은 사람을 발견한 기록이 있는지 확인합니다.
        prev_discover_history = DiscoveryHistory.objects.filter(
            session=session,
            discovered=discovered_session,

            created_at__gt=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )

        if prev_discover_history.exists():
            # 무시합니다.
            raise UnsupportedOperationException()

        # 서로 발견한 사용자를 기록합니다.
        history = DiscoveryHistory.objects.create(
            session=session,
            discovered=discovered_session,

            latitude=validated_data['latitude'],
            longitude=validated_data['longitude'],
            altitude=validated_data['altitude'],

            accuracy=validated_data['accuracy']
        )

        opposite_history = DiscoveryHistory.objects.filter(
            session=discovered_session,
            discovered=session,
            created_at__gt=datetime.now() - timedelta(minutes=30) # 30분 이내에 서로를 발견해야 합니다
        )

        if opposite_history.exists():
            opposite_history = opposite_history.first()

            # 서로를 발견하였으므로, 카드를 교환합니다.
            if not CardDistribution.objects.filter(
                card=session.user.main_card,
                user=discovered_session.user
            ).exists():
                distrib_a = CardDistribution.objects.create(
                    card=session.user.main_card,
                    user=discovered_session.user,

                    latitude=history.latitude,
                    longitude=history.longitude,
                    altitude=history.altitude,
                    accuracy=history.accuracy
                )

            if not CardDistribution.objects.filter(
                card=discovered_session.user.main_card,
                user=session.user
            ).exists():
                distrib_b = CardDistribution.objects.create(
                    card=discovered_session.user.main_card,
                    user=session.user,

                    latitude=opposite_history.latitude,
                    longitude=opposite_history.longitude,
                    altitude=opposite_history.altitude,
                    accuracy=opposite_history.accuracy
                )


        return Response({
            'is_success': True
        })
