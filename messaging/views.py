from django.http import Http404
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from flitz.exceptions import UnsupportedOperationException
from messaging.models import DirectMessageConversation, DirectMessage
from messaging.serializers import DMConversationSerializer, DMMessageSerializer


class DMConversationViewSet(viewsets.ModelViewSet):

    serializer_class = DMConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DirectMessageConversation.objects \
            .filter(deleted_at__isnull=None, participants__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        initial_participants = serializer.validated_data['initial_participants']
        conflicts = DirectMessageConversation.objects \
            .filter(participants__user=initial_participants[0]) \
            .filter(participants__user=initial_participants[1]) \
            .exists()

        if conflicts:
            raise ValidationError(code=status.HTTP_409_CONFLICT)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def destroy(self, request, *args, **kwargs):
        instance: DirectMessageConversation = self.get_object()
        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DMMessageViewSet(viewsets.ModelViewSet):

    serializer_class = DMMessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_conversation_id(self):
        return self.kwargs['conversation_id']

    def get_conversation(self):
        try:
            return DirectMessageConversation.objects.get(id__exact=self.get_conversation_id())
        except:
            raise Http404()

    def get_queryset(self):
        if not self.get_conversation().participants.filter(user=self.request.user).exists():
            raise Http404()

        return DirectMessage.objects \
            .filter(conversation_id__exact=self.get_conversation_id(), deleted_at__isnull=True)

    def create(self, request, *args, **kwargs):
        request.data['sent_by'] = self.request.user.id
        request.data['parent_conversation'] = self.get_conversation_id()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created_instance: DirectMessage = serializer.save()

        conversation = self.get_conversation()
        conversation.latest_message_id = created_instance.id
        conversation.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def destroy(self, request, *args, **kwargs):
        instance: DirectMessage = self.get_object()

        if instance.sender_id is not self.request.user.id:
            raise Http404()

        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
