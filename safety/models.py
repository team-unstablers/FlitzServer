from typing import Optional

from django.db import models, transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from flitz.models import BaseModel
from location.utils.distance import measure_distance
from safety.utils.phone_number import hash_phone_number, normalize_phone_number

from user.models import User

class UserWaveSafetyZone(BaseModel):
    """
    "자동으로 Wave 끄기" 기능에 대한 설정 정보를 저장합니다.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wave_safety_zone', db_index=True)

    latitude = models.FloatField(null=True, blank=False)
    longitude = models.FloatField(null=True, blank=False)

    # TODO: validate: accept only (300m, 500m, 1000m)
    # radius (in meters)
    radius = models.FloatField(null=False, blank=False)

    is_enabled = models.BooleanField(default=False, null=False, blank=False)
    enable_wave_after_exit = models.BooleanField(default=True, null=False, blank=False)

    def evaluate(self, latitude: float, longitude: float) -> bool:
        """
        주어진 위도와 경도가 설정된 안전 구역 내에 있는지 평가합니다.
        """

        if not self.is_enabled:
            return False

        distance = measure_distance(
            (self.latitude, self.longitude),
            (latitude, longitude),
        )

        radius_in_kilo = self.radius / 1000.0  # Convert radius from meters to kilometers

        return distance <= radius_in_kilo


class UserBlock(BaseModel):
    """
    사용자 차단 정보를 저장합니다.
    """

    class Type(models.IntegerChoices):
        """
        차단 유형
        """
        BLOCK = (1, '차단')
        LIMIT = (2, '제한')

    class Reason(models.IntegerChoices):
        """
        차단 사유를 정의합니다.
        """
        BY_USER = (1, '사용자 동작에 의한 차단')
        BY_TRIGGER = (2, '연락처 트리거에 의한 차단')
        pass


    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blocked_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_users')

    type = models.IntegerField(choices=Type.choices, default=Type.BLOCK, null=False, blank=False)
    reason = models.IntegerField(choices=Reason.choices, default=Reason.BY_USER, null=False, blank=False)

class UserContactsTrigger(BaseModel):
    """
    연락처에 따른 사용자 차단 트리거 정보를 저장합니다.
    """

    class Meta:
        unique_together = (('user', 'phone_number_hashed'),)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contact_triggers')

    # sha256sum(salt + phone_number)
    phone_number_hashed = models.CharField(max_length=64, null=False, blank=False)
    related_object = models.ForeignKey(UserBlock, on_delete=models.SET_NULL, null=True, blank=True)

    def set_phone_number(self, phone_number: str):
        normalized_phone_number = normalize_phone_number(phone_number, self.user.country)
        self.phone_number_hashed = hash_phone_number(normalized_phone_number)

    def evaluate(self) -> Optional[User]:
        """
        트리거를 평가합니다.
        """

        user = User.objects.filter(phone_number_hashed=self.phone_number_hashed)
        return user.first()

    def perform_block(self):
        """
        트리거에 의해 사용자를 차단합니다.
        """

        with transaction.atomic():
            user = self.evaluate()

            if user is None:
                return

            if user == self.user:
                # 자기 자신은 차단할 수 없음
                return

            block = UserBlock.objects.create(user=user, blocked_by=self.user, reason=UserBlock.Reason.BY_TRIGGER)
            self.related_object = block
            self.save()


@receiver(pre_delete, sender=UserContactsTrigger)
def delete_related_userblock(sender, instance, **kwargs):
    """
    UserContactsTrigger가 삭제될 때 연결된 UserBlock 객체도 함께 삭제합니다.
    반대의 경우(UserBlock이 삭제될 때 UserContactsTrigger가 삭제되는 것)는 발생하지 않습니다.
    """
    if instance.related_object:
        # SET_NULL 동작을 막기 위해 참조를 제거
        related_object = instance.related_object
        instance.related_object = None
        instance.save(update_fields=['related_object'])
        # 연결된 UserBlock 삭제
        related_object.delete()
