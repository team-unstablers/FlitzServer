from django.db.models import Q
from django.utils import timezone

from django.db import models
from django.contrib.postgres.indexes import GinIndex
from uuid_v7.base import uuid7

from flitz.models import BaseModel
from messaging.objdef import load_direct_message_content
from user.models import User

from user import tasks as user_tasks

# Create your models here.

def attachment_upload_to(instance, filename):
    """
    DM 첨부파일의 저장 경로를 생성합니다.
    파일명은 UUID7을 사용하고, 확장자는 원본 파일에서 가져옵니다.
    디렉토리 샤딩을 적용하여 성능을 최적화합니다.
    """
    ext = filename.split('.')[-1] if '.' in filename else ''
    file_uuid = str(uuid7())
    filename = f"{file_uuid}.{ext}" if ext else file_uuid

    # UUID의 첫 2글자로 디렉토리 샤딩 (256개 디렉토리로 분산)
    shard = file_uuid[:2]
    return f"dm_attachments/{shard}/{filename}"


def attachment_thumbnail_upload_to(instance, filename):
    """
    DM 첨부파일 썸네일의 저장 경로를 생성합니다.
    파일명은 UUID7을 사용하고, 확장자는 원본 파일에서 가져옵니다.
    디렉토리 샤딩을 적용하여 성능을 최적화합니다.
    """
    ext = filename.split('.')[-1] if '.' in filename else ''
    file_uuid = str(uuid7())
    filename = f"{file_uuid}.{ext}" if ext else file_uuid

    # UUID의 첫 2글자로 디렉토리 샤딩 (256개 디렉토리로 분산)
    shard = file_uuid[:2]
    return f"dm_attachment_thumbnails/{shard}/{filename}"


class DirectMessageConversation(BaseModel):
    class Meta:
        indexes = [
            models.Index(fields=['deleted_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    latest_message = models.ForeignKey('DirectMessage', on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def create_conversation(cls, user_a: User, user_b: User):
        conversation = cls.objects.create()

        DirectMessageParticipant.objects.create(conversation=conversation, user=user_a)
        DirectMessageParticipant.objects.create(conversation=conversation, user=user_b)

        return conversation

class DirectMessageParticipant(BaseModel):
    class Meta:
        unique_together = ('conversation', 'user')
        indexes = [
            models.Index(fields=['deleted_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    conversation = models.ForeignKey(DirectMessageConversation, on_delete=models.CASCADE, related_name='participants', db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)

    read_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

class DirectMessage(BaseModel):
    class Meta:
        indexes = [
            GinIndex(fields=['content']),

            models.Index(fields=['deleted_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    conversation = models.ForeignKey(DirectMessageConversation, on_delete=models.CASCADE, related_name='messages', db_index=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)

    content = models.JSONField(null=False, blank=False)

    deleted_at = models.DateTimeField(null=True, blank=True)

    def send_push_notification(self):
        content = self.content
        content_type = content.get('type')

        notification_title = f'{self.sender.display_name} 님의 새 메시지'

        if content_type == 'text':
            notification_body = content.get('text')

            if len(notification_body) > 240:
                notification_body = notification_body[:240] + '…'

        elif content_type == 'attachment':
            attachment_type = content.get('attachment_type')
            if attachment_type == 'image':
                notification_body = f'{self.sender.display_name} 님이 이미지를 보냈습니다.'
            elif attachment_type == 'video':
                notification_body = f'{self.sender.display_name} 님이 동영상을 보냈습니다.'
            elif attachment_type == 'audio':
                notification_body = f'{self.sender.display_name} 님이 음성 메시지를 보냈습니다.'
            else:
                notification_body = f'{self.sender.display_name} 님이 새 메시지를 보냈습니다.'
        else:
            notification_body = f'{self.sender.display_name} 님이 새 메시지를 보냈습니다.'

        participants = self.conversation.participants.filter(
            ~Q(user=self.sender)
        ).values_list('user_id', flat=True)

        for participant_id in participants:
            user_tasks.send_push_message.delay_on_commit(
                participant_id,
                notification_title,
                notification_body,
                {
                    'type': 'message',
                    'user_id': str(self.sender.id),
                    'user_display_name': self.sender.display_name,
                    'user_profile_image_url': self.sender.profile_image_url,
                    'message_content': notification_body,
                    'conversation_id': str(self.conversation.id)
                },
                thread_id=str(self.conversation.id),
                mutable_content=True
            )

    def get_content_with_url(self) -> dict:
        if self.content.get('type') != 'attachment' or not hasattr(self, 'attachment'):
            return self.content

        content = load_direct_message_content(self.content)

        attachment = self.attachment

        if attachment.object.name:
            content.public_url = attachment.object.url
        else:
            content.public_url = None

        if attachment.thumbnail.name:
            content.thumbnail_url = attachment.thumbnail.url
        else:
            content.thumbnail_url = None

        return content.as_dict()


class DirectMessageAttachment(BaseModel):
    class Meta:
        indexes = [
            models.Index(fields=['deleted_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    class AttachmentType(models.TextChoices):
        IMAGE = 'image'
        VIDEO = 'video'
        AUDIO = 'audio'
        OTHER = 'other'

    conversation = models.ForeignKey(DirectMessageConversation, on_delete=models.CASCADE, related_name='attachments', db_index=True)
    message = models.OneToOneField(DirectMessage, on_delete=models.CASCADE, related_name='attachment', null=True, blank=True)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)

    type = models.CharField(max_length=32, choices=AttachmentType.choices)

    object = models.FileField(upload_to=attachment_upload_to, null=True)
    thumbnail = models.ImageField(upload_to=attachment_thumbnail_upload_to, null=True, blank=True)

    mimetype = models.CharField(max_length=128)
    size = models.IntegerField()

    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

    def delete_attachment(self):
        try:
            if self.object and self.object.name:
                self.object.delete(save=False)

            if self.thumbnail and self.thumbnail.name:
                self.thumbnail.delete(save=False)

        except Exception as e:
            print(e)

        self.deleted_at = timezone.now()
        self.save()

class DirectMessageFlag(BaseModel):
    class FlagReason(models.TextChoices):
        INAPPROPRIATE = 'INAPPROPRIATE', 'Inappropriate'
        SPAM = 'SPAM', 'Spam'
        HARASSMENT = 'HARASSMENT', 'Harassment'
        OTHER = 'OTHER', 'Other'

    conversation = models.ForeignKey(DirectMessageConversation, on_delete=models.CASCADE)
    message = models.ForeignKey(DirectMessage, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    reason = models.CharField(max_length=32, choices=FlagReason.choices, null=False, blank=False)
    user_description = models.TextField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)