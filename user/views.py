from django.core.files.storage import Storage, default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.shortcuts import render, get_object_or_404

from uuid_v7.base import uuid7

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from flitz.thumbgen import generate_thumbnail
from user.models import User
from user.serializers import PublicUserSerializer, PublicSelfUserSerializer

from flitz.exceptions import UnsupportedOperationException

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

    @action(detail=False, methods=['GET'], url_path='self')
    def get_self(self, request, *args, **kwargs):
        user = self.request.user
        serializer = PublicSelfUserSerializer(user)

        return Response(serializer.data)

    @action(detail=False, methods=['POST'], url_path='self/profile-image')
    def set_profile_image(self, request, *args, **kwargs):
        user = self.request.user

        file: UploadedFile = request.data['file']
        extension = file.name.split('.')[-1]

        if not file.content_type.startswith('image'):
            raise UnsupportedOperationException()

        with transaction.atomic():
            object_key = f'profile_images/{str(uuid7())}.jpg'

            storage: Storage = default_storage
            thumbnail = generate_thumbnail(file)

            storage.save(object_key, thumbnail)
            user.profile_image_key = object_key
            user.profile_image_url = storage.url(object_key).split('?')[0]

            user.save()

        serializer = PublicSelfUserSerializer(user)

        return Response(serializer.data)

    @action(detail=False, methods=['GET'], url_path=r'by-username/(?P<username>[a-zA-Z0-9_]+)')
    def get_by_username(self, request, username, *args, **kwargs):
        user = get_object_or_404(User, username=username)
        serializer = PublicUserSerializer(user)

        return Response(serializer.data)

    @action(detail=False, methods=['POST'], url_path='register')
    def register(self, request, *args, **kwargs):
        username = request.data.get('username')
        password = request.data.get('password')

        user = User.objects.create_user(
            username=username,
            email=None,
            password=password
        )

        user.is_active = True
        user.save()

        return Response({'is_success': True}, status=201)
