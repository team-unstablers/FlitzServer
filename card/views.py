from dacite import from_dict
from django.core.files.uploadedfile import UploadedFile
from django.core.files.storage import default_storage, Storage
from django.db import transaction
from django.shortcuts import render, get_object_or_404

from rest_framework import permissions, viewsets, parsers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from card.objdef import CardObject, CardSchemaVersion, AssetReference
from card.serializers import PublicCardSerializer, PublicCardListSerializer, PublicSelfUserCardAssetSerializer
from card.models import Card, UserCardAsset
from flitz.pagination import CursorPagination
from user.models import User

from flitz.exceptions import UnsupportedOperationException

# Create your views here.

class PublicCardViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return PublicCardListSerializer

        return PublicCardSerializer

    def get_queryset(self):
        queryset = Card.objects.filter(deleted_at=None).select_related('user')

        if self.action == 'list':
            queryset = queryset.filter(user=self.request.user).defer('content')

        return queryset

    def create(self, request: Request, *args, **kwargs):
        card_obj = CardObject.create_empty(version=CardSchemaVersion.V1)

        card = Card.objects.create(
            user=self.request.user,
            title='',
            content=card_obj.as_dict()
        )

        serializer = PublicCardSerializer(card)

        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        if self.get_object().user != request.user:
            raise UnsupportedOperationException()

        data = request.data
        card_dict = data['content']

        if card_dict is None:
            raise UnsupportedOperationException()

        card_obj = from_dict(data_class=CardObject, data=data['content'])

        if not card_obj.sanity_check():
            raise UnsupportedOperationException()

        data['content'] = card_obj.as_dict()

        return super().update(request, *args, **kwargs)


    @action(detail=True, methods=['GET', 'POST'], url_path='asset-references')
    def asset_references(self, request: Request, pk, *args, **kwargs):
        if request.method == 'GET':
            return self.get_asset_references(request, pk, *args, **kwargs)
        elif request.method == 'POST':
            return self.create_asset_reference(request, pk, *args, **kwargs)

    def get_asset_references(self, request: Request, pk, *args, **kwargs):
        queryset = UserCardAsset.objects.filter(card_id=pk, deleted_at=None)
        serializer = PublicSelfUserCardAssetSerializer(queryset, many=True)

        return Response(serializer.data)

    @action(detail=True, methods=['POST'], url_path='asset-references', url_name='create_asset_reference')
    def create_asset_reference(self, request: Request, pk, *args, **kwargs):
        card = get_object_or_404(Card, pk=pk)

        if card.user != request.user:
            raise UnsupportedOperationException()

        file: UploadedFile = request.data['file']
        extension = file.name.split('.')[-1]

        if extension is None:
            raise UnsupportedOperationException()

        if file.content_type.startswith('image'):
            type = UserCardAsset.AssetType.IMAGE
        elif file.content_type.startswith('video'):
            type = UserCardAsset.AssetType.VIDEO
        elif file.content_type.startswith('audio'):
            type = UserCardAsset.AssetType.AUDIO
        else:
            type = UserCardAsset.AssetType.OTHER


        with transaction.atomic():
            asset = UserCardAsset.objects.create(
                user=request.user,
                card=card,
                type=type,
                object_key='',
                public_url='',
                mimetype=file.content_type,
                size=file.size
            )

            asset.object_key = f'card_assets/{asset.id}.{extension}'

            storage: Storage = default_storage
            storage.save(asset.object_key, file)

            asset.public_url = storage.url(asset.object_key).split('?')[0]
            asset.save()


        serializer = PublicSelfUserCardAssetSerializer(asset)
        return Response(serializer.data)

    @action(detail=True, methods=['PUT'], url_path='asset-references/gc')
    def garbage_collect_asset_references(self, request: Request, pk, *args, **kwargs):
        card = get_object_or_404(Card, pk=pk)

        if card.user != request.user:
            raise UnsupportedOperationException()

        card.remove_orphaned_assets()

        return Response()

    @action(detail=False, methods=['GET'], url_path='retrieved')
    def get_retrieved(self, request: Request, *args, **kwargs):
        pass