from datetime import datetime
from idlelib.pyparse import trans

from dacite import from_dict
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.shortcuts import render, get_object_or_404

from rest_framework import permissions, viewsets, parsers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from card.objdef import CardObject, CardSchemaVersion, AssetReference
from card.serializers import PublicCardSerializer, PublicSelfUserCardAssetSerializer, \
    CardDistributionSerializer, PublicWriteOnlyCardSerializer, CardFavoriteItemSerializer
from card.models import Card, UserCardAsset, CardDistribution, CardVote, CardFavoriteItem
from flitz.pagination import CursorPagination
from user.models import User, UserLike

from flitz.exceptions import UnsupportedOperationException

# Create your views here.

class CardDistributionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CardDistributionSerializer

    def get_queryset(self):
        return CardDistribution.objects.filter(
            user=self.request.user,
            dismissed_at=None,
            deleted_at=None
        )

    def create(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def destroy(self, request, *args, **kwargs):
        distribution: CardDistribution = self.get_object()
        distribution.deleted_at = datetime.now()

        distribution.save()

        return Response({'is_success': True}, status=200)

    @action(detail=True, methods=['PUT'], url_path='like')
    def like(self, request, pk, *args, **kwargs):
        distribution: CardDistribution = self.get_object()

        with transaction.atomic():
            CardVote.objects.create(
                card=distribution.card,
                user=request.user,

                vote_type=CardVote.VoteType.UPVOTE
            )

            distribution.dismissed_at = datetime.now()
            distribution.save()

            _, created = UserLike.objects.get_or_create(
                user=distribution.card.user,
                liked_by=request.user
            )

            if created:
                UserLike.try_match_user(distribution.card.user, request.user)

        return Response({'is_success': True}, status=200)

    @action(detail=True, methods=['PUT'], url_path='dislike')
    def dislike(self, request, pk, *args, **kwargs):
        distribution: CardDistribution = self.get_object()

        with transaction.atomic():
            CardVote.objects.create(
                card=distribution.card,
                user=request.user,

                vote_type=CardVote.VoteType.DOWNVOTE
            )

            distribution.dismissed_at = datetime.now()
            distribution.save()

        return Response({'is_success': True}, status=200)

class PublicCardViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return PublicCardSerializer

        if self.action == 'update':
            return PublicWriteOnlyCardSerializer

        return PublicCardSerializer

    def get_queryset(self):
        queryset = Card.objects.filter(deleted_at=None) \
            .select_related('user') \
            .prefetch_related('asset_references')

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
        card: Card = self.get_object()
        if card.user != request.user:
            raise UnsupportedOperationException()

        data = request.data
        card_dict = data['content']

        if card_dict is None:
            raise UnsupportedOperationException()

        card_obj = from_dict(data_class=CardObject, data=data['content'])

        if not card_obj.sanity_check():
            raise UnsupportedOperationException()

        # super().update(request, *args, **kwargs)
        card.content = card_obj.as_dict()
        card.save()

        serializer = PublicCardSerializer(self.get_object())
        return Response(serializer.data)

    @action(detail=True, methods=['PUT'], url_path='set-as-main')
    def set_card_as_main(self, request: Request, pk, *args, **kwargs):
        card = get_object_or_404(Card, pk=pk)

        if card.user != request.user:
            raise UnsupportedOperationException()

        request.user.main_card = card
        request.user.save()

        return Response({'is_success': True}, status=200)


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
                object=file,  # FileField에 직접 파일 할당
                mimetype=file.content_type,
                size=file.size
            )


        serializer = PublicSelfUserCardAssetSerializer(asset)
        return Response(serializer.data)

    @action(detail=True, methods=['PUT'], url_path='asset-references/gc')
    def garbage_collect_asset_references(self, request: Request, pk, *args, **kwargs):
        card = get_object_or_404(Card, pk=pk)

        if card.user != request.user:
            raise UnsupportedOperationException()

        card.remove_orphaned_assets()

        return Response()


class CardFavoriteViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CardFavoriteItemSerializer

    def get_queryset(self):
        return CardFavoriteItem.objects.filter(
            user=self.request.user,
            deleted_at=None
        ).select_related('card', 'card__user')

    def create(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def destroy(self, request, *args, **kwargs):
        item: CardFavoriteItem = self.get_object()

        if item.user != request.user:
            raise UnsupportedOperationException()

        item.deleted_at = datetime.now()
        item.save()

        return Response({'is_success': True}, status=200)

    def update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()
