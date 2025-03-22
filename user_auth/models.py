from datetime import timedelta

import jwt

from django.db import models
from django.conf import settings
from django.utils import timezone

from flitz.models import BaseModel
from flitz.apns import APNS

from user.models import User

# Create your models here.
class UserSession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    description = models.CharField(max_length=64)

    initiated_from = models.CharField(max_length=128, null=False, blank=False)
    
    apns_token = models.CharField(max_length=256, null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

    def send_push_message(self, title: str, body: str, data: dict):
        """
        사용자에게 푸시 메시지를 보냅니다.
        """

        apns = APNS.default()
        apns.send_notification(title, body, [self.apns_token], data)

    def create_token(self) -> str:
        token = jwt.encode({
            'sub': str(self.id),
            'iat': timezone.now(),
            'exp': timezone.now() + timedelta(days=30),
            'x-flitz-options': '--with-love',
        }, key=settings.SECRET_KEY, algorithm='HS256')

        return token
