from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.core.files.uploadedfile import UploadedFile
from django.db import models, transaction
from uuid_v7.base import uuid7

from flitz.models import UUIDv7Field, BaseModel
from flitz.thumbgen import generate_thumbnail
from safety.utils.phone_number import hash_phone_number, normalize_phone_number


# Create your models here.

def profile_image_upload_to(instance, filename):
    """
    프로필 이미지의 저장 경로를 생성합니다.
    파일명은 UUID7을 사용하고, 항상 .jpg로 저장됩니다.
    디렉토리 샤딩을 적용하여 성능을 최적화합니다.
    """
    file_uuid = str(uuid7())
    # UUID의 첫 2글자로 디렉토리 샤딩 (256개 디렉토리로 분산)
    shard = file_uuid[:2]
    return f"profile_images/{shard}/{file_uuid}.jpg"

class User(AbstractUser):
    class Meta:
        indexes = [
            models.Index(fields=['username'])
        ]

    id = UUIDv7Field(primary_key=True, editable=False)

    username = models.CharField(max_length=24, unique=True)
    display_name = models.CharField(max_length=24)

    phone_number = models.CharField(max_length=32, null=True, blank=True)
    phone_number_hashed = models.CharField(max_length=64, null=True, blank=True)

    disabled_at = models.DateTimeField(null=True, blank=True)

    profile_image = models.ImageField(upload_to=profile_image_upload_to, null=True, blank=True)

    free_coins = models.IntegerField(default=0)
    paid_coins = models.IntegerField(default=0)

    fully_deleted_at = models.DateTimeField(null=True, blank=True)

    main_card = models.ForeignKey('card.Card', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    primary_session = models.ForeignKey('user_auth.UserSession', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def profile_image_url(self) -> Optional[str]:
        if not self.profile_image.name:
            return None

        return self.profile_image.url


    def set_phone_number(self, phone_number: str):
        normalized_phone_number = normalize_phone_number(phone_number)

        self.phone_number = normalized_phone_number
        self.phone_number_hashed = hash_phone_number(normalized_phone_number)

    def send_push_message(self, title: str, body: str, data: Optional[dict]=None, thread_id: Optional[str]=None, mutable_content: bool=False):
        """
        사용자에게 푸시 메시지를 보냅니다.

        :note: 이 메소드를 직접 호출하지 마십시오! 대신 `user.tasks.send_push_message`를 사용하십시오. (Celery task)
        """

        if not self.primary_session:
            return

        self.primary_session.send_push_message(title, body, data, thread_id=thread_id, mutable_content=mutable_content)

    def update_location(self, latitude: float, longitude: float, altitude: Optional[float]=None, accuracy: Optional[float]=None):
        from location.models import UserLocation

        with transaction.atomic():
            location, created = UserLocation.objects.get_or_create(
                defaults={
                    'latitude': 0.0,
                    'longitude': 0.0,
                    'altitude': 0.0,
                    'accuracy': 0.0,
                },
                user=self
            )

            location.latitude = latitude
            location.longitude = longitude
            location.altitude = altitude
            location.accuracy = accuracy

            location.update_timezone()
            location.save()

        return location

    def set_profile_image(self, image_file: UploadedFile):
        if not image_file.content_type.startswith('image/'):
            raise ValueError("Uploaded file is not an image.")

        # 기존 이미지가 있으면 삭제
        if self.profile_image:
            self.profile_image.delete(save=False)

        # 썸네일 생성 후 저장
        (thumbnail, size) = generate_thumbnail(image_file)
        # 파일명은 upload_to 함수가 자동으로 처리
        self.profile_image.save('thumbnail.jpg', thumbnail, save=True)




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
        conversation = DirectMessageConversation.create_conversation(user_a, user_b)

        import user.tasks as user_tasks

        # TODO: i18n
        user_tasks.send_push_message.delay_on_commit(
            user_a.id,
            '매칭 성공!',
            f'{user_b.display_name}님과 매칭되었습니다! 지금 바로 대화를 시작해보세요!',
            {
                'type': 'match',
                'user_id': str(user_b.id),
                'user_profile_image_url': user_b.profile_image_url,
                'conversation_id': conversation.id
            },
            mutable_content=True
        )

        user_tasks.send_push_message.delay_on_commit(
            user_b.id,
            '매칭 성공!',
            f'{user_a.display_name}님과 매칭되었습니다! 지금 바로 대화를 시작해보세요!',
            {
                'type': 'match',
                'user_id': str(user_a.id),
                'user_profile_image_url': user_a.profile_image_url,
                'conversation_id': conversation.id
            },
            mutable_content=True
        )

class Notification(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=64, null=False, blank=False)
    content = models.JSONField(null=False, default=dict)

    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
