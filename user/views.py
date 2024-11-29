from django.shortcuts import render, get_object_or_404

from rest_framework import permissions, viewsets

from user.models import User
from user.serializers import PublicUserSerializer, PublicSelfUserSerializer

from flitz.exceptions import UnsupportedOperationException

# Create your views here.

class PublicUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicUserSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return User.objects.filter(disabled_at=None, fully_deleted_at=None)

    def list(self, request, *args, **kwargs):
        # 사용자 리스트는 보여져선 안됨
        raise UnsupportedOperationException()
