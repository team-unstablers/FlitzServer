from datetime import datetime, timedelta

from django.db import transaction
from django.shortcuts import render
from django.utils import timezone
from timezonefinder import TimezoneFinder
import pytz

from rest_framework import permissions, viewsets, parsers, status
from rest_framework.decorators import action, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from card.models import CardDistribution
from flitz.exceptions import UnsupportedOperationException
from location.models import DiscoverySession, DiscoveryHistory, UserLocation
from location.serializers import DiscoveryReportSerializer


def get_timezone_from_coordinates(latitude, longitude):
    """위도/경도로부터 시간대를 결정합니다."""
    tf = TimezoneFinder()
    timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
    if timezone_str:
        return pytz.timezone(timezone_str)
    return pytz.UTC  # 기본값으로 UTC 반환


def get_today_start_in_timezone(tz):
    """특정 시간대의 '오늘' 시작 시간을 계산합니다."""
    now = timezone.now()
    local_time = now.astimezone(tz)
    today_start = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start


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

        # 사용자의 위치 정보로부터 시간대를 결정합니다
        user_timezone = get_timezone_from_coordinates(
            validated_data['latitude'], 
            validated_data['longitude']
        )
        
        # 해당 시간대의 '오늘' 시작 시간을 계산합니다
        today_start = get_today_start_in_timezone(user_timezone)
        
        # 오늘 하루동안 같은 사람을 발견한 기록이 있는지 확인합니다.
        prev_discover_history = DiscoveryHistory.objects.filter(
            session=session,
            discovered=discovered_session,
            created_at__gt=today_start
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

        # 30분 이내에 서로를 발견했는지 확인 (사용자의 현지 시간대 기준)
        time_threshold = timezone.now().astimezone(user_timezone) - timedelta(minutes=30)
        opposite_history = DiscoveryHistory.objects.filter(
            session=discovered_session,
            discovered=session,
            created_at__gt=time_threshold
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
