import pytz
import pygeohash as pgh

from django.db import models

from flitz.models import BaseModel

from user.models import User

from location.utils.timezone import get_timezone_from_coordinates
from location.utils.distance import measure_distance

"""
| 자릿수 (Precision) | 격자 크기 (오차 범위) | 일반적인 적용 예시 |
| :--- | :--- | :--- |
| 1 | ≤ 5,000km × 5,000km | 대륙 |
| 2 | ≤ 1,250km × 625km | 국가 |
| 3 | ≤ 156km × 156km | 주 또는 큰 도시 |
| 4 | ≤ 39.1km × 19.5km | 도시 |
| 5 | ≤ 4.89km × 4.89km | 동네, 마을 |
| 6 | ≤ 1.22km × 0.61km | 큰 길, 캠퍼스 |
| 7 | ≤ 153m × 153m | 축구장, 블록 |
| 8 | ≤ 38.2m × 19.1m | 건물, 큰 집 |
| 9 | ≤ 4.77m × 4.77m | 방, 현관 |
| 10 | ≤ 1.19m × 0.6m | 작은 문 |
| 11 | ≤ 14.9cm × 14.9cm | 손바닥 |
| 12 | ≤ 3.7cm × 1.9cm | 동전 |
"""
GEOHASH_PRECISION = 6


class LocationDistanceMixin:
    def distance_to(self, other) -> float:
        """
        두 위치 정보 사이의 거리를 계산합니다. 킬로미터 단위입니다.
        """
        loc1 = (self.latitude, self.longitude)
        loc2 = (other.latitude, other.longitude)

        return measure_distance(loc1, loc2)

# Create your models here.

class UserLocation(models.Model, LocationDistanceMixin):
    class Meta:
        get_latest_by = 'created_at'

        indexes = [
            models.Index(fields=['user']),

            models.Index(fields=['geohash']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True, related_name='location')

    latitude = models.FloatField(null=False, blank=False)
    longitude = models.FloatField(null=False, blank=False)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    timezone = models.CharField(max_length=64, null=False, blank=False, default='UTC')

    geohash = models.CharField(max_length=10, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def update_geohash(self):
        self.geohash = pgh.encode(self.latitude, self.longitude, precision=GEOHASH_PRECISION)


    def update_timezone(self):
        timezone_obj = get_timezone_from_coordinates(self.latitude, self.longitude)
        self.timezone = str(timezone_obj)

    @property
    def timezone_obj(self) -> pytz.timezone:
        return pytz.timezone(self.timezone)

class UserLocationHistory(BaseModel, LocationDistanceMixin):
    class Meta:
        get_latest_by = 'created_at'

        indexes = [
            models.Index(fields=['user']),

            models.Index(fields=['geohash']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='location_history')

    latitude = models.FloatField(null=False, blank=False)
    longitude = models.FloatField(null=False, blank=False)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    timezone = models.CharField(max_length=64, null=False, blank=False, default='UTC')

    geohash = models.CharField(max_length=10, null=True, blank=True)
    is_in_safety_zone = models.BooleanField(default=False)

    def update_geohash(self):
        self.geohash = pgh.encode(self.latitude, self.longitude, precision=GEOHASH_PRECISION)

    def update_timezone(self):
        timezone_obj = get_timezone_from_coordinates(self.latitude, self.longitude)
        self.timezone = str(timezone_obj)

    @property
    def timezone_obj(self) -> pytz.timezone:
        return pytz.timezone(self.timezone)



class DiscoverySession(BaseModel):
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
        ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discovery_session')
    is_active = models.BooleanField(default=False)

class DiscoveryHistory(BaseModel, LocationDistanceMixin):
    class Meta:
        indexes = [
            models.Index(fields=['session', 'discovered']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    session = models.ForeignKey(DiscoverySession, on_delete=models.CASCADE, related_name='discovered')
    discovered = models.ForeignKey(DiscoverySession, on_delete=models.CASCADE, related_name='discovered_by')

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

