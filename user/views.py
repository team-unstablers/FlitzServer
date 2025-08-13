from django.core.files.uploadedfile import UploadedFile
from django.shortcuts import render, get_object_or_404

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from flitz.thumbgen import generate_thumbnail
from user.models import User, UserIdentity
from user.serializers import PublicUserSerializer, PublicSelfUserSerializer, SelfUserIdentitySerializer

from flitz.exceptions import UnsupportedOperationException
from user_auth.models import UserSession

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

    @action(detail=False, methods=['GET', 'PATCH'], url_path='self')
    def dispatch_self(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.get_self(request, *args, **kwargs)
        elif request.method == 'PATCH':
            return self.patch_self(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def get_self(self, request, *args, **kwargs):
        user = self.request.user
        serializer = PublicSelfUserSerializer(user)

        return Response(serializer.data)

    def patch_self(self, request, *args, **kwargs):
        user = self.request.user
        serializer = PublicSelfUserSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)

    @action(detail=False, methods=['GET', 'PATCH'], url_path='self/identity')
    def dispatch_self_identity(self, request, *args, **kwargs):
        if request.method == 'GET':
            return self.get_self_identity(request, *args, **kwargs)
        elif request.method == 'PATCH':
            return self.patch_self_identity(request, *args, **kwargs)
        else:
            raise UnsupportedOperationException()

    def get_self_identity(self, request, *args, **kwargs):
        user: User = self.request.user

        if not hasattr(user, 'identity'):
            return Response({'is_success': False, 'message': 'Identity not found'}, status=404)

        identity = user.identity
        serializer = SelfUserIdentitySerializer(identity)
        return Response(serializer.data)

    def patch_self_identity(self, request, *args, **kwargs):
        user: User = self.request.user

        identity, created = UserIdentity.objects.get_or_create(
            user=user
        )

        serializer = SelfUserIdentitySerializer(identity, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)


    @action(detail=False, methods=['PUT'], url_path='self/apns-token')
    def set_apns_token(self, request, *args, **kwargs):
        session: UserSession = self.request.auth
        apns_token = request.data.get('apns_token')

        if apns_token is None or len(apns_token) == 0:
            return Response({'is_success': False})
        
        if session.apns_token == apns_token:
            return Response({'is_success': False})

        session.apns_token = apns_token
        session.save()

        return Response({'is_success': True})

    @action(detail=False, methods=['POST'], url_path='self/profile-image')
    def set_profile_image(self, request, *args, **kwargs):
        user: User = self.request.user

        file: UploadedFile = request.data['file']
        user.set_profile_image(file)

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
