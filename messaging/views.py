from dataclasses import asdict

from django.core.files.storage import default_storage, Storage
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import viewsets, permissions, status, parsers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from flitz.exceptions import UnsupportedOperationException

from messaging.models import DirectMessageConversation, DirectMessage, DirectMessageAttachment
from messaging.objdef import DirectMessageAttachmentContent
from messaging.serializers import DirectMessageConversationSerializer, DirectMessageSerializer, DirectMessageAttachmentSerializer
from messaging.thumbgen import generate_thumbnail


class DirectMessageConversationViewSet(viewsets.ModelViewSet):

    serializer_class = DirectMessageConversationSerializer
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
            raise ValidationError(detail="CONFLICT", code=status.HTTP_409_CONFLICT)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def partial_update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def destroy(self, request, *args, **kwargs):
        instance: DirectMessageConversation = self.get_object()
        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DirectMessageViewSet(viewsets.ModelViewSet):

    serializer_class = DirectMessageSerializer
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

    def partial_update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def destroy(self, request, *args, **kwargs):
        instance: DirectMessage = self.get_object()

        if instance.sender_id is not self.request.user.id:
            raise Http404()

        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class DirectMessageAttachmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_conversation_id(self):
        return self.kwargs['conversation_id']

    def get_conversation(self):
        try:
            return DirectMessageConversation.objects.get(
                id__exact=self.get_conversation_id(),
                participants__user=self.request.user
            )
        except:
            raise Http404()

    def get_queryset(self):
        return DirectMessageAttachment.objects.filter(
            sender=self.request.user,
            conversation__id=self.get_conversation_id(),

            deleted_at=None
        )

    def create(self, request, *args, **kwargs):
        conversation = self.get_conversation()
        file: UploadedFile = request.data['file']
        extension = file.name.split('.')[-1]

        # Determine attachment type
        if file.content_type.startswith('image'):
            attachment_type = DirectMessageAttachment.AttachmentType.IMAGE
        elif file.content_type.startswith('video'):
            attachment_type = DirectMessageAttachment.AttachmentType.VIDEO
        elif file.content_type.startswith('audio'):
            attachment_type = DirectMessageAttachment.AttachmentType.AUDIO
        else:
            attachment_type = DirectMessageAttachment.AttachmentType.OTHER

        if attachment_type != DirectMessageAttachment.AttachmentType.IMAGE:
            # not supported yet
            raise UnsupportedOperationException()

        with transaction.atomic():
            attachment = DirectMessageAttachment.objects.create(
                conversation=conversation,
                type=attachment_type,
                object_key='',
                public_url='',
                mimetype=file.content_type,
                size=file.size
            )

            attachment.object_key = f'dm_attachments/{attachment.id}.orig'
            attachment.thumbnail_key = f'dm_attachments/{attachment.id}.jpg'

            storage: Storage = default_storage
            storage.save(attachment.object_key, file)

            thumbnail_file = generate_thumbnail(file)
            storage.save(attachment.thumbnail_key, thumbnail_file)

            attachment.public_url = storage.url(attachment.object_key).split('?')[0]
            attachment.thumbnail_url = storage.url(attachment.thumbnail_key).split('?')[0]

            attachment.save()

            content = DirectMessageAttachmentContent(
                type='attachment',

                attachment_type='image',
                attachment_id=attachment.id,

                # 굳이 원본을 보여줄 필요는 없음
                public_url=attachment.thumbnail_url,
                thumbnail_url=attachment.thumbnail_url
            )

            # Optionally create a direct message referencing the new attachment
            message = DirectMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                content=asdict(content)
            )


        conversation.latest_message = message
        conversation.save()

        # 이게 과연 맞는지?
        serializer = DirectMessageSerializer(message)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
