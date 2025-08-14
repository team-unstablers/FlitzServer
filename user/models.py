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

class UserGenderBit(models.IntegerChoices):
    UNSET = 0
    MAN = 1
    WOMAN = 2
    NON_BINARY = 4

    @staticmethod
    def ALL():
        return UserGenderBit.MAN | UserGenderBit.WOMAN | UserGenderBit.NON_BINARY

class User(AbstractUser):
    class Meta:
        indexes = [
            models.Index(fields=['username'])
        ]

    id = UUIDv7Field(primary_key=True, editable=False)

    username = models.CharField(max_length=24, unique=True)
    display_name = models.CharField(max_length=24)

    country = models.CharField(max_length=2, null=True, blank=True)

    phone_number = models.CharField(max_length=32, null=True, blank=True)
    phone_number_hashed = models.CharField(max_length=64, null=True, blank=True)

    disabled_at = models.DateTimeField(null=True, blank=True)

    profile_image = models.ImageField(upload_to=profile_image_upload_to, null=True, blank=True)

    title = models.CharField(max_length=20, null=False, blank=True, default='')

    bio = models.CharField(max_length=600, null=False, blank=True, default='')
    hashtags = models.JSONField(default=list, blank=True, null=False)

    birth_date = models.DateField(null=True, blank=True)

    free_coins = models.IntegerField(default=0)
    paid_coins = models.IntegerField(default=0)

    contacts_blocker_enabled = models.BooleanField(default=False, null=False, blank=False)

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
        normalized_phone_number = normalize_phone_number(phone_number, self.country)

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

class UserIdentity(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='identity', db_index=True)

    # 성별 필드
    gender = models.IntegerField(choices=UserGenderBit.choices, default=UserGenderBit.UNSET)
    # 트랜스젠더 여부
    is_trans = models.BooleanField(default=False)
    # 트랜스젠더 여부를 다른 사용자에게 표시할 것인가
    display_trans_to_others = models.BooleanField(default=False)

    # 선호하는 성별 (비트 마스크)
    preferred_genders = models.IntegerField(default=0)
    # 비-트랜스젠더인 경우, 트랜스젠더를 환영할 것인지 여부,
    # 구현 시 배제 옵션이 아니라, 환영 옵션임을 인지해야 합니다: 이 설정을 False로 한다고 해도 트랜스젠더 분들과는 매칭될 수 있어야 합니다.
    welcomes_trans = models.BooleanField(default=False)
    # 트랜스젠더인 경우, 안전한 매칭을 선호할 것인지 여부 (트랜스젠더 당사자나, welcomes_trans=True인 사용자와만 매칭됨)
    trans_prefers_safe_match = models.BooleanField(default=False)

    def is_acceptable(self, other: 'UserIdentity') -> bool:
        """
        다른 사용자의 아이덴티티가 현재 사용자의 선호에 맞는지 확인합니다.
        """

        is_preferred = (self.preferred_genders & other.gender) != 0

        if not is_preferred:
            # 선호하는 성별이 아니면 매칭 불가
            return False

        if self.is_trans and self.trans_prefers_safe_match:
            # GUARD: 안전한 매칭을 선호하는 트랜스젠더인 경우 상대가 트랜스젠더 당사자인거나, 트랜스젠더에 대해 우호적이어야 한다
            return other.is_trans or other.welcomes_trans

        return True

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
