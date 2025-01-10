from django.db import models

from flitz.models import BaseModel
from user.models import User

# Create your models here.
class UserSession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.CharField(max_length=64)

    initiated_from = models.CharField(max_length=128, null=False, blank=False)
    
    apns_token = models.CharField(max_length=256, null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
