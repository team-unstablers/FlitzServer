from django.db import models

from flitz.models import UUIDv7Field, BaseModel

from user.models import User

# Create your models here.

class UserLocation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, primary_key=True, related_name='location')

    latitude = models.FloatField(null=False, blank=False)
    longitude = models.FloatField(null=False, blank=False)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DiscoverySession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discovery_session')
    is_active = models.BooleanField(default=False)

class DiscoveryHistory(BaseModel):
    session = models.ForeignKey(DiscoverySession, on_delete=models.CASCADE, related_name='discovered')
    discovered = models.ForeignKey(DiscoverySession, on_delete=models.CASCADE, related_name='discovered_by')




