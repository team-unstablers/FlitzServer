from django.shortcuts import render, get_object_or_404

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from user.models import User
from user.serializers import PublicUserSerializer, PublicSelfUserSerializer

from flitz.exceptions import UnsupportedOperationException

# Create your views here.

class PublicUserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicUserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(disabled_at=None, fully_deleted_at=None)

    def list(self, request, *args, **kwargs):
        # 사용자 리스트는 보여져선 안됨
        raise UnsupportedOperationException()

    @action(detail=False, methods=['GET'], url_path='self')
    def get_self(self, request, *args, **kwargs):
        user = self.request.user
        serializer = PublicSelfUserSerializer(user)

        return Response(serializer.data)

    @action(detail=False, methods=['GET'], url_path=r'by-username/(?P<username>[a-zA-Z0-9_]+)')
    def get_by_username(self, request, username, *args, **kwargs):
        user = get_object_or_404(User, username=username)
        serializer = PublicUserSerializer(user)

        return Response(serializer.data)