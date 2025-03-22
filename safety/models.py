from idlelib.pyparse import trans
from typing import Optional

from django.db import models, transaction

from flitz.models import BaseModel
from safety.utils.phone_number import hash_phone_number, normalize_phone_number

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

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contact_triggers')

    # sha256sum(salt + phone_number)
    phone_number_hashed = models.CharField(max_length=64, null=False, blank=False)
    related_object = models.ForeignKey(UserBlock, on_delete=models.SET_NULL, null=True, blank=True)

    def set_phone_number(self, phone_number: str):
        normalized_phone_number = normalize_phone_number(phone_number)
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

            block = UserBlock.objects.create(user=user, blocked_by=self.user, reason=UserBlock.Reason.BY_TRIGGER)
            self.related_object = block
            self.save()




