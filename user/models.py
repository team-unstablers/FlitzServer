from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.db import models

from flitz.models import UUIDv7Field, BaseModel
from flitz.apns import APNS


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

    profile_image_key = models.CharField(max_length=2048, null=True, blank=True)
    profile_image_url = models.CharField(max_length=2048, null=True, blank=True)

    free_coins = models.IntegerField(default=0)
    paid_coins = models.IntegerField(default=0)

    fully_deleted_at = models.DateTimeField(null=True, blank=True)

    main_card = models.ForeignKey('card.Card', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def send_push_message(self, title: str, body: str, data: Optional[dict]=None):
        """
        사용자에게 푸시 메시지를 보냅니다.
        """

        # 원래대로라면 유효한 세션은 하나여야 하지만, 추후 여러 기기에서 로그인할 수 있도록 수정될 수 있으므로
        valid_sessions = self.sessions.filter(invalited_at=None)
        apns_tokens = valid_sessions.values('apns_token')

        apns = APNS.default()
        apns.send_notification(title, body, apns_tokens, data)



class UserBlock(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blocked_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blocked_users')

class UserLike(BaseModel):
    class Meta:
        unique_together = ['user', 'liked_by']

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    liked_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='liked_users')

    @classmethod
    def try_match_user(cls, user_a: User, user_b: User):
        user_a, user_b = sorted([user_a, user_b], key=lambda x: x.id)

        match_exists = UserMatch.objects.filter(user_a=user_a, user_b=user_b).exists()

        if match_exists:
            # assertion failed: match_exists == False
            return

        like_a_exists = cls.objects.filter(user=user_a, liked_by=user_b).exists()
        like_b_exists = cls.objects.filter(user=user_b, liked_by=user_a).exists()

        if like_a_exists and like_b_exists:
            UserMatch.create_match(user_a, user_b)


class UserMatch(BaseModel):
    class Meta:
        unique_together = ['user_a', 'user_b']

    user_a = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    user_b = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')

    @classmethod
    def create_match(cls, user_a: User, user_b: User):
        user_a, user_b = sorted([user_a, user_b], key=lambda x: x.id)

        cls.objects.create(user_a=user_a, user_b=user_b)

        from messaging.models import DirectMessageConversation
        DirectMessageConversation.create_conversation(user_a, user_b)

        # TODO: i18n
        user_a.send_push_message(
            '매칭 성공!',
            f'{user_b.display_name}님과 매칭되었습니다! 지금 바로 대화를 시작해보세요!',
            {
                'type': 'match',
                'user': user_b.id
            }
        )

        user_b.send_push_message(
            '매칭 성공!',
            f'{user_a.display_name}님과 매칭되었습니다! 지금 바로 대화를 시작해보세요!',
            {
                'type': 'match',
                'user': user_a.id
            }
        )

class Notification(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=64, null=False, blank=False)
    content = models.JSONField(null=False),

    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)