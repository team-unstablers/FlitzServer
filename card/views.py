from django.shortcuts import render, get_object_or_404

from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from card.objdef import CardObject, CardSchemaVersion
from card.serializers import PublicCardSerializer, PublicSelfCardSerializer
from card.models import Card
from flitz.pagination import CursorPagination
from user.models import User

from flitz.exceptions import UnsupportedOperationException

# Create your views here.

class PublicCardViewSet(viewsets.ModelViewSet):
    serializer_class = PublicCardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Card.objects.filter(deleted_at=None)

        if self.action == 'list':
            queryset = queryset.filter(user=self.request.user)

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


    @action(detail=False, methods=['GET'], url_path='retrieved')
    def get_retrieved(self, request: Request, *args, **kwargs):
        pass