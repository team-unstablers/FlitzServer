import pytz
from django.db import models

from flitz.models import UUIDv7Field, BaseModel

from user.models import User

from location.utils import get_timezone_from_coordinates, get_today_start_in_timezone

# Create your models here.

class UserLocation(models.Model):
    class Meta:
        get_latest_by = 'created_at'

    user = models.ForeignKey(User, on_delete=models.CASCADE, primary_key=True, related_name='location')

    latitude = models.FloatField(null=False, blank=False)
    longitude = models.FloatField(null=False, blank=False)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    timezone = models.CharField(max_length=64, null=False, blank=False, default='UTC')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def update_timezone(self):
        self.timezone = get_timezone_from_coordinates(self.latitude, self.longitude)

    @property
    def timezone_obj(self) -> pytz.timezone:
        return pytz.timezone(self.timezone)


class DiscoverySession(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discovery_session')
    is_active = models.BooleanField(default=False)

class DiscoveryHistory(BaseModel):
    session = models.ForeignKey(DiscoverySession, on_delete=models.CASCADE, related_name='discovered')
    discovered = models.ForeignKey(DiscoverySession, on_delete=models.CASCADE, related_name='discovered_by')

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)




