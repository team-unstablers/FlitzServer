from datetime import datetime, timedelta

from django.db import transaction
from django.shortcuts import render

from rest_framework import permissions, viewsets, parsers
from rest_framework.decorators import action, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from card.models import CardDistribution
from flitz.exceptions import UnsupportedOperationException
from location.models import DiscoverySession, DiscoveryHistory


# Create your views here.

class LocationViewSet(viewsets.ViewSet):

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_name='discovery/start')
    def start_discovery(self, request: Request):
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

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_name='discovery/stop')
    def stop_discovery(self, request: Request):
        DiscoverySession.objects.filter(
            user=request.user,
            is_active=True
        ).update(
            is_active=False
        )

        return Response({
            'is_success': True
        })

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated], url_name='discovery/report')
    def report_discovery(self, request: Request):
        session_id = request.data['session_id']
        discovered_session_id = request.data['discovered_session_id']

        session = DiscoverySession.objects.filter(
            id=session_id,
            user=request.user,
            is_active=True
        ).first()

        discovered_session = DiscoverySession.objects.filter(
            id=discovered_session_id,
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
            discovered_session=discovered_session,

            created_at__gt=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )

        if prev_discover_history.exists():
            # 무시합니다.
            raise UnsupportedOperationException()

        # 서로 발견한 사용자를 기록합니다.
        history = DiscoveryHistory.objects.create(
            session=session,
            discovered_session=discovered_session
        )

        opposite_history = DiscoveryHistory.objects.filter(
            session=discovered_session,
            discovered_session=session,
            created_at__gt=datetime.now() - timedelta(minutes=30) # 30분 이내에 서로를 발견해야 합니다
        )

        if opposite_history.exists():
            with transaction.atomic():
                # 서로를 발견하였으므로, 카드를 교환합니다.
                distrib_a = CardDistribution.objects.create(
                    card=session.user.cards[0],
                    user=discovered_session.user,

                    latitude=0,
                    longitude=0,
                    altitude=0,
                    accuracy=0,
                )

                distrib_b = CardDistribution.objects.create(
                    card=discovered_session.user.cards[0],
                    user=session.user,

                    latitude=0,
                    longitude=0,
                    altitude=0,
                    accuracy=0,
                )


        return Response({
            'is_success': True
        })