from django.db import models

from flitz.models import BaseModel
from safety.utils.phonehash import hash_phone_number

from user.models import User

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

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # sha256sum(salt + phone_number)
    phone_number_hashed = models.CharField(max_length=64, null=False, blank=False)

    def set_phone_number(self, phone_number: str):
        self.phone_number_hashed = hash_phone_number(phone_number)
