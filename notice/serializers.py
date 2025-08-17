from rest_framework import serializers

from notice.models import Notice


class NoticeSerializer(serializers.ModelSerializer):
    """
    공지사항 시리얼라이저
    """
    
    class Meta:
        model = Notice
        fields = [
            'id',
            'title', 
            'content',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]


class NoticeListSerializer(serializers.ModelSerializer):
    """
    공지사항 목록 시리얼라이저 (간략한 정보만 제공)
    """

    class Meta:
        model = Notice
        fields = [
            'id',
            'title',
            'created_at',
        ]
        read_only_fields = fields
