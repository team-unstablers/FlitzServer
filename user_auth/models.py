from datetime import timedelta
from typing import Optional, List

import jwt

from django.db import models, transaction
from django.conf import settings
from django.utils import timezone

from flitz.models import BaseModel
from flitz.apns import APNS, APSPayload

from user.models import User

# Create your models here.
class UserSession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    description = models.CharField(max_length=64)

    initiated_from = models.CharField(max_length=128, null=False, blank=False)
    
    apns_token = models.CharField(max_length=256, null=True, blank=True)
    refresh_token = models.CharField(max_length=512, null=True, blank=True, unique=True)
    token_refreshed_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

    def send_push_message(self,
                          title: str,
                          body: str,
                          data: dict,
                          thread_id: Optional[str] = None,
                          mutable_content: bool = False,
                          sound: Optional[str] = None):
        """
        사용자에게 푸시 메시지를 보냅니다.
        """

        apns = APNS.default()
        apns.send_notification(title, body, [self.apns_token], data, thread_id=thread_id, mutable_content=mutable_content, sound=sound)

    def send_push_message_ex(self,
                             aps: APSPayload,
                             user_info: dict = None):
        """
        사용자에게 푸시 메시지를 보냅니다.
        """

        apns = APNS.default()
        apns.send_notification_ex(
            aps,
            [self.apns_token],
            user_info=user_info
        )


    def create_token(self) -> str:
        now = timezone.now()

        token = jwt.encode({
            'sub': str(self.id),
            'iat': now,
            'exp': now + timedelta(days=3),
            'x-flitz-options': '--with-love',
        }, key=settings.SECRET_KEY, algorithm='HS256')

        return token

    @transaction.atomic
    def update_refresh_token(self) -> str:
        now = timezone.now()

        self.refresh_token = jwt.encode({
            'sub': str(self.id),
            'iat': now,
            'exp': now + timedelta(days=30),
            'x-flitz-options': '--with-love --refresh',
        }, key=settings.SECRET_KEY, algorithm='HS256')

        self.token_refreshed_at = now

        self.save(update_fields=['refresh_token', 'token_refreshed_at', 'updated_at'])

        return self.refresh_token


