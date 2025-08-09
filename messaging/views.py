from dataclasses import asdict

from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.decorators import action
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from flitz.exceptions import UnsupportedOperationException

from messaging.models import DirectMessageConversation, DirectMessage, DirectMessageAttachment, DirectMessageParticipant
from messaging.objdef import DirectMessageAttachmentContent
from messaging.serializers import DirectMessageConversationSerializer, DirectMessageSerializer, \
    DirectMessageReadOnlySerializer, DirectMessageAttachmentSerializer
from flitz.thumbgen import generate_thumbnail


class DirectMessageConversationViewSet(viewsets.ModelViewSet):

    serializer_class = DirectMessageConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DirectMessageConversation.objects \
            .filter(deleted_at__isnull=True, participants__user=self.request.user) \
            .prefetch_related('participants') \
            .select_related('latest_message', 'latest_message__sender', 'latest_message__attachment')

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

    permission_classes = [permissions.IsAuthenticated]

    def get_conversation_id(self):
        return self.kwargs['conversation_id']

    def get_conversation(self):
        try:
            return DirectMessageConversation.objects.get(id__exact=self.get_conversation_id())
        except:
            raise Http404()

    def get_serializer_class(self):
        if self.action == 'create':
            return DirectMessageSerializer
        return DirectMessageReadOnlySerializer

    def get_queryset(self):
        if not self.get_conversation().participants.filter(user=self.request.user).exists():
            raise Http404()

        return DirectMessage.objects \
            .filter(conversation_id__exact=self.get_conversation_id(), deleted_at__isnull=True) \
            .select_related('sender', 'attachment')

    def create(self, request, *args, **kwargs):
        request.data['sent_by'] = self.request.user.id
        request.data['parent_conversation'] = self.get_conversation_id()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created_instance: DirectMessage = serializer.save()

        conversation = self.get_conversation()
        conversation.latest_message_id = created_instance.id
        conversation.save()
        
        # 실시간 메시지 이벤트 발송
        channel_layer = get_channel_layer()
        group_name = f'direct_message_{created_instance.conversation_id}'

        message_data = DirectMessageReadOnlySerializer(instance=created_instance).data

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'dm_message',
                'message': message_data
            }
        )

        created_instance.send_push_notification()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    @action(detail=False, methods=['post'])
    def mark_as_read(self, request, conversation_id=None):
        """메시지를 읽음 상태로 표시하는 API 엔드포인트"""
        conversation = self.get_conversation()
        
        # 참여자의 읽음 상태 업데이트
        try:
            participant = DirectMessageParticipant.objects.get(
                conversation=conversation,
                user=request.user
            )
            participant.read_at = timezone.now()
            participant.save()
            
            # 읽음 상태 이벤트 발송
            channel_layer = get_channel_layer()
            group_name = f'direct_message_{conversation.id}'
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'dm_read_event',
                    'user_id': str(request.user.id),
                    'read_at': participant.read_at.isoformat()
                }
            )
            
            return Response({'status': 'success'}, status=status.HTTP_200_OK)
        except DirectMessageParticipant.DoesNotExist:
            raise Http404("You are not a participant in this conversation")

    def retrieve(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def partial_update(self, request, *args, **kwargs):
        raise UnsupportedOperationException()

    def destroy(self, request, *args, **kwargs):
        instance: DirectMessage = self.get_object()

        if instance.sender_id != self.request.user.id:
            raise Http404()

        instance.deleted_at = timezone.now()
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

class DirectMessageAttachmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DirectMessageAttachmentSerializer

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
            conversation__id=self.get_conversation_id(),
            conversation__participants__user=self.request.user,

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
            # TODO: resize image and remove EXIF data
            sanitized_file = file
            (thumbnail, size) = generate_thumbnail(file, 1280)

            attachment = DirectMessageAttachment.objects.create(
                sender=self.request.user,
                conversation=conversation,
                type=attachment_type,
                object=thumbnail,
                thumbnail=thumbnail,
                mimetype=file.content_type,
                size=thumbnail.size,

                width=size[0],
                height=size[1]
            )

            content = DirectMessageAttachmentContent(
                type='attachment',

                attachment_type='image',
                attachment_id=str(attachment.id),  # UUID를 문자열로 변환

                width=size[0],
                height=size[1],

                # 굳이 원본을 보여줄 필요는 없음
                public_url=attachment.thumbnail.url,
                thumbnail_url=attachment.thumbnail.url
            )

            # Optionally create a direct message referencing the new attachment
            message = DirectMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                content=asdict(content)
            )

            attachment.message = message
            attachment.save()

        conversation.latest_message = message
        conversation.save()
        
        # 첨부파일 메시지에 대한 실시간 이벤트 발송
        channel_layer = get_channel_layer()
        group_name = f'direct_message_{conversation.id}'

        message_data = DirectMessageReadOnlySerializer(instance=message).data

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'dm_message',
                'message': message_data
            }
        )

        message.send_push_notification()

        return Response(message_data, status=status.HTTP_201_CREATED)
