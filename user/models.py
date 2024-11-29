from django.contrib.auth.models import AbstractUser

from django.db import models

from flitz.models import UUIDv7Field, BaseModel

# Create your models here.

class User(AbstractUser):
    class Meta:
        indexes = [
            models.Index(fields=['username'])
        ]

    id = UUIDv7Field(primary_key=True, editable=False)

    username = models.CharField(max_length=24, unique=True)
    display_name = models.CharField(max_length=24)

    disabled_at = models.DateTimeField(null=True, blank=True)

    free_coins = models.IntegerField(default=0)
    paid_coins = models.IntegerField(default=0)

    fully_deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class UserBlock(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blocked_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_users')

class UserSession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.CharField(max_length=64)

    initiated_from = models.CharField(max_length=128, null=False, blank=False)

    expires_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

class Notification(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=64, null=False, blank=False)
    content = models.JSONField(null=False),

    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)