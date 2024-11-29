from django.db import models
from django.contrib.postgres.indexes import GinIndex

from flitz.models import BaseModel
from user.models import User

# Create your models here.


class DirectMessageConversation(BaseModel):
    latest_message = models.ForeignKey('DirectMessage', on_delete=models.SET_NULL, null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

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