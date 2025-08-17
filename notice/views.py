from django.db.models import Q
from rest_framework import viewsets
from rest_framework.filters import OrderingFilter

from notice.models import Notice
from notice.serializers import NoticeSerializer, NoticeListSerializer


class NoticeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    공지사항 ViewSet (읽기 전용)
    
    공지사항 목록 조회 및 상세 조회 기능을 제공합니다.
    인증 없이 모든 사용자가 접근 가능합니다.
    """

    # permission_classes = [AllowAny]
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        삭제되지 않은 공지사항만 반환
        """
        queryset = Notice.objects.filter(
            Q(deleted_at__isnull=True)
        )
        return queryset
    
    def get_serializer_class(self):
        """
        액션에 따라 다른 시리얼라이저 사용
        - list: 간략한 정보만 제공
        - retrieve: 상세 정보 제공
        """
        if self.action == 'list':
            return NoticeListSerializer
        return NoticeSerializer
