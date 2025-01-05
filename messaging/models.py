from datetime import datetime
from django.core.files.storage import default_storage, Storage

from django.db import models
from django.contrib.postgres.indexes import GinIndex

from flitz.models import BaseModel
from user.models import User

# Create your models here.


class DirectMessageConversation(BaseModel):
    latest_message = models.ForeignKey('DirectMessage', on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def create_conversation(cls, user_a: User, user_b: User):
        conversation = cls.objects.create()

        DirectMessageParticipant.objects.create(conversation=conversation, user=user_a)
        DirectMessageParticipant.objects.create(conversation=conversation, user=user_b)

        return conversation

class DirectMessageParticipant(BaseModel):
    conversation = models.ForeignKey(DirectMessageConversation, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    read_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

class DirectMessage(BaseModel):
    class Meta:
        indexes = [
            GinIndex(fields=['content'])
        ]

    conversation = models.ForeignKey(DirectMessageConversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)

    content = models.JSONField(null=False, blank=False)

    deleted_at = models.DateTimeField(null=True, blank=True)

class DirectMessageAttachment(BaseModel):
    class AttachmentType(models.TextChoices):
        IMAGE = 'image'
        VIDEO = 'video'
        AUDIO = 'audio'
        OTHER = 'other'

    conversation = models.ForeignKey(DirectMessageConversation, on_delete=models.CASCADE, related_name='attachments')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)

    type = models.CharField(max_length=32, choices=AttachmentType.choices)

    object_key = models.CharField(max_length=2048)
    public_url = models.CharField(max_length=2048)

    thumbnail_key = models.CharField(max_length=2048, null=True, blank=True)
    thumbnail_url = models.CharField(max_length=2048, null=True, blank=True)

    mimetype = models.CharField(max_length=128)
    size = models.IntegerField()
    deleted_at = models.DateTimeField(null=True, blank=True)

    def delete_attachment(self):
        try:
            storage: Storage = default_storage
            storage.delete(self.object_key)

            if self.thumbnail_key:
                storage.delete(self.thumbnail_key)
        except Exception as e:
            print(e)
            
        self.deleted_at = datetime.now()
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