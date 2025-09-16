import datetime
from typing import Optional, Literal, List

import pytz
from django.contrib.auth.models import AbstractUser
from django.core.files.uploadedfile import UploadedFile
from django.core.cache import cache
from django.db import models, transaction
from django.utils import timezone
from django.contrib.postgres.indexes import GinIndex
from uuid_v7.base import uuid7

from flitz.apns import APSPayload
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

def deleted_user_archive_upload_to(instance, filename):
    """
    사용자 삭제 아카이브의 저장 경로를 생성합니다.
    파일명은 UUID7을 사용하고, 항상 .enc로 저장됩니다.
    디렉토리 샤딩을 적용하여 성능을 최적화합니다.
    """
    file_uuid = str(uuid7())
    # UUID의 첫 2글자로 디렉토리 샤딩 (256개 디렉토리로 분산)
    shard = file_uuid[:2]
    return f"user_delarch/{shard}/{file_uuid}.enc"


class UserGenderBit(models.IntegerChoices):
    UNSET = 0
    MAN = 1
    WOMAN = 2
    NON_BINARY = 4

    @staticmethod
    def ALL():
        return UserGenderBit.MAN | UserGenderBit.WOMAN | UserGenderBit.NON_BINARY

class UserDeletionPhase(models.IntegerChoices):
    INITIATED = 0, '삭제 시작됨'
    SENSITIVE_DATA_DELETED = 1, '민감 정보 삭제됨'
    CONTENT_DELETED = 2, '컨텐츠 삭제됨'
    MESSAGE_DELETED = 3, '메시지 삭제됨'
    FULLY_DELETED = 4, '전체 삭제됨'


class UserDeletionReviewRequestReason(models.IntegerChoices):
    HAS_FLAGGED_CONTENT = 1
    HAS_FLAGGED_MESSAGE = 2
    HAS_FLAGGED_PROFILE = 4
    OTHER = 8


# 푸시 알림 유형
PushNotificationType = Literal['message', 'match', 'notice', 'marketing']

OnlineStatus  = Literal['online', 'recently', 'offline']

# FIXME: 그런데 이거 나라마다 멀다고 느끼는 기준이 다를 수 있지 않을까?
FuzzyDistance = Literal['nearest', 'near', 'medium', 'far', 'farthest']

class User(AbstractUser):
    class Meta:
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['country']),
            models.Index(fields=['phone_number_hashed']),

            models.Index(fields=['nice_di']),

            models.Index(fields=['disabled_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    id = UUIDv7Field(primary_key=True, editable=False)

    username = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=24)

    country = models.CharField(max_length=2, null=True, blank=True)
    nice_di = models.CharField(max_length=64, null=True, blank=True)

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

    # 현재 삭제 페이즈
    deletion_phase = models.IntegerField(choices=UserDeletionPhase.choices, null=True, blank=True)
    # 다음 페이즈로 이동하기 위한 예약 시간
    deletion_phase_scheduled_at = models.DateTimeField(null=True, blank=True)

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

    @property
    def last_seen(self) -> datetime:
        timestamp = cache.get(f'user:last_seen:{self.id}')

        if timestamp is None:
            return None

        return timezone.datetime.fromtimestamp(timestamp, tz=pytz.UTC)

    @property
    def online_status(self) -> OnlineStatus:
        last_seen = self.last_seen
        if not last_seen:
            return 'offline'

        diff = timezone.now() - last_seen

        if diff.seconds < (60 * 5):
            return 'online'
        elif diff.seconds < (60 * 60 * 6):
            return 'recently'
        else:
            return 'offline'

    def update_last_seen(self):
        TIMEOUT = 86400 * 7

        cache.set(f'user:last_seen:{self.id}', timezone.now().timestamp(), timeout=TIMEOUT)


    def set_phone_number(self, phone_number: str):
        normalized_phone_number = normalize_phone_number(phone_number, self.country)

        self.phone_number = normalized_phone_number
        self.phone_number_hashed = hash_phone_number(normalized_phone_number)

    def send_push_message(self,
                          type: PushNotificationType,
                          title: str,
                          body: str,
                          data: Optional[dict]=None,
                          thread_id: Optional[str]=None,
                          mutable_content: bool=False,
                          sound: Optional[str]=None):
        """
        사용자에게 푸시 메시지를 보냅니다.

        :note: 이 메소드를 직접 호출하지 마십시오! 대신 `user.tasks.send_push_message`를 사용하십시오. (Celery task)
        """

        if not self.primary_session:
            return

        if not self.settings.allows_push(type):
            return

        self.primary_session.send_push_message(title, body, data, thread_id=thread_id, mutable_content=mutable_content, sound=sound)


    def send_push_message_ex(self,
                             type: PushNotificationType,
                             aps: APSPayload,
                             user_info: Optional[dict] = None):
        """
        사용자에게 푸시 메시지를 보냅니다.

        :note: 이 메소드를 직접 호출하지 마십시오! 대신 `user.tasks.send_push_message_ex`를 사용하십시오. (Celery task)
        """

        if not self.primary_session:
            return

        if not self.settings.allows_push(type):
            return

        self.primary_session.send_push_message_ex(aps, user_info=user_info)

    def update_location(self, latitude: float, longitude: float, altitude: Optional[float]=None, accuracy: Optional[float]=None, force_timezone_update: bool=False):
        from location.models import UserLocation
        from location.utils.distance import measure_distance

        with transaction.atomic():
            location, created = UserLocation.objects.get_or_create(
                defaults={
                    'latitude': latitude,
                    'longitude': longitude,
                    'altitude': altitude or 0.0,
                    'accuracy': accuracy or 0.0,
                },
                user=self
            )

            if not created:
                # 기존 위치와의 거리 계산 (시간대 변경 여부 판단용)
                old_location = (location.latitude, location.longitude)
                new_location = (latitude, longitude)
                distance = measure_distance(old_location, new_location)
                
                location.latitude = latitude
                location.longitude = longitude
                location.altitude = altitude
                location.accuracy = accuracy

                # 10km 이상 이동했거나 강제 업데이트 플래그가 설정된 경우에만 시간대 업데이트
                if distance > 10.0 or force_timezone_update:
                    location.update_timezone()
            else:
                # 새로 생성된 경우에는 시간대 업데이트
                location.update_timezone()

            # update geohash
            location.update_geohash()
            location.save()

        return location

    def distance_to(self, other: 'User') -> Optional[float]:
        if self.id == other.id:
            return 0.0

        if not hasattr(other, 'location') or not hasattr(self, 'location'):
            return None

        return self.location.distance_to(other.location)

    def fuzzy_distance_to(self, other: 'User') -> FuzzyDistance:
        if self.id == other.id:
            return 'nearest'

        distance = self.distance_to(other)

        if distance is None:
            return 'farthest'

        # FIXME: 이거 수정 필요

        if distance <= 0.3: # 300m 이내
            return 'nearest'
        elif distance <= 1.000: # 1km 이내
            return 'near'
        elif distance <= 5.0: # 5km 이내
            return 'medium'
        elif distance <= 30.0: # 30km 이내
            return 'far'
        else: # 20km 이상
            return 'farthest'


    def set_profile_image(self, image_file: UploadedFile):
        if not image_file.content_type.startswith('image/'):
            raise ValueError("Uploaded file is not an image.")

        # 기존 이미지가 있으면 삭제
        if self.profile_image.name:
            self.profile_image.delete(save=False)

        # 썸네일 생성 후 저장
        (thumbnail, size) = generate_thumbnail(image_file)
        # 파일명은 upload_to 함수가 자동으로 처리
        self.profile_image.save('thumbnail.jpg', thumbnail, save=True)

    def is_blocked_by(self, other: 'User') -> bool:
        """
        다른 사용자가 현재 사용자를 차단했는지 확인합니다.
        """

        return other.blocked_users.only('id').filter(user=self).exists()

class UserSettings(BaseModel):
    class Meta:
        indexes = [
            models.Index(fields=['user']),
        ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')

    messaging_notifications_enabled = models.BooleanField(default=True)
    match_notifications_enabled = models.BooleanField(default=True)
    notice_notifications_enabled = models.BooleanField(default=True)
    marketing_notifications_enabled = models.BooleanField(default=False)
    # 대한민국 정보통신망법 제 50조 8항 / 시행령 제62조의3에 의해 마케팅 푸시의 경우 수신 동의 확인이 의무화 되어 있습니다
    # 수신 동의를 받은 날부터 2년마다 아래 내용을 반드시 표시해야 합니다
    # 1. 전송자의 명칭 (회사명 / 서비스명)
    # 2. 수신 동의 날짜 (YYYY-MM-DD)
    # 3. 수신동의를 한 사실
    # 4. 수신동의를 철회할 수 있는 방법
    # 안 지키면 3000만원 이하의 과태료에 처해질 수 있습니다
    marketing_notifications_enabled_at = models.DateTimeField(null=True, blank=True)

    def allows_push(self, type: PushNotificationType) -> bool:
        """
        사용자가 특정 유형의 푸시 알림을 허용하는지 확인합니다.
        """
        if type == 'message':
            return self.messaging_notifications_enabled
        elif type == 'match':
            return self.match_notifications_enabled
        elif type == 'notice':
            return self.notice_notifications_enabled
        elif type == 'marketing':
            return self.marketing_notifications_enabled
        else:
            return True

class UserIdentity(BaseModel):
    class Meta:
        indexes = [
            models.Index(fields=['user']),

            models.Index(fields=['gender']),
            models.Index(fields=['is_trans', 'trans_prefers_safe_match']),
            models.Index(fields=['welcomes_trans']),
        ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='identity')

    # 성별 필드
    gender = models.PositiveIntegerField(choices=UserGenderBit.choices, default=UserGenderBit.UNSET)
    # 트랜스젠더 여부
    is_trans = models.BooleanField(default=False)
    # 트랜스젠더 여부를 다른 사용자에게 표시할 것인가
    display_trans_to_others = models.BooleanField(default=False)

    # 선호하는 성별 (비트 마스크)
    preferred_genders = models.PositiveIntegerField(default=0)
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

        match_exists = UserMatch.match_exists(user_a, user_b)

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
    def match_exists(cls, user_a: User, user_b: User) -> bool:
        """
        두 사용자 간의 매칭이 존재하는지 확인합니다.
        """
        user_a, user_b = sorted([user_a, user_b], key=lambda x: x.id)
        return cls.objects.filter(user_a=user_a, user_b=user_b).exists()

    @classmethod
    def create_match(cls, user_a: User, user_b: User):
        user_a, user_b = sorted([user_a, user_b], key=lambda x: x.id)

        if user_a.is_blocked_by(user_b) or user_b.is_blocked_by(user_a):
            # 차단된 사용자 간의 매칭은 불가능
            return

        cls.objects.create(user_a=user_a, user_b=user_b)

        from messaging.models import DirectMessageConversation
        conversation = DirectMessageConversation.create_conversation(user_a, user_b)

        import user.tasks as user_tasks

        user_tasks.send_push_message_ex.delay_on_commit(
            user_a.id,
            'match',
            aps={
                'alert': {
                    'title': '매칭 성공!',
                    'body': f'{user_b.display_name}님과 매칭되었습니다! 지금 바로 대화를 시작해보세요!',
                    'title-loc-key': 'fz.notification.match.title',
                    'loc-key': 'fz.notification.match.body',
                    'loc-args': [user_b.display_name],
                },
                'mutable-content': 1,
                'sound': 'wave.aif',
            },
            user_info={
                'type': 'match',
                'user_id': str(user_b.id),
                'user_profile_image_url': user_b.profile_image_url,
                'conversation_id': str(conversation.id)
            },
        )

        user_tasks.send_push_message_ex.delay_on_commit(
            user_b.id,
            'match',
            aps={
                'alert': {
                    'title': '매칭 성공!',
                    'body': f'{user_a.display_name}님과 매칭되었습니다! 지금 바로 대화를 시작해보세요!',
                    'title-loc-key': 'fz.notification.match.title',
                    'loc-key': 'fz.notification.match.body',
                    'loc-args': [user_a.display_name],
                },
                'mutable-content': 1,
                'sound': 'wave.aif',
            },
            user_info={
                'type': 'match',
                'user_id': str(user_a.id),
                'user_profile_image_url': user_a.profile_image_url,
                'conversation_id': str(conversation.id)
            },
        )

    @classmethod
    def delete_match(cls, user_a: User, user_b: User):
        user_a, user_b = sorted([user_a, user_b], key=lambda x: x.id)

        cls.objects.filter(user_a=user_a, user_b=user_b).delete()

class Notification(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=64, null=False, blank=False)
    content = models.JSONField(null=False, default=dict)

    read_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

class UserDeletionReviewRequest(BaseModel):
    """
    사용자가 플래그된 경우, 추가적인 리뷰 후 삭제를 진행하기 위한 모델입니다.
    """
    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='deletion_review_request')

    reason = models.IntegerField(null=False, blank=False, default=0)
    reason_text = models.CharField(max_length=256, null=False, blank=False)

    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

class DeletedUserArchive(BaseModel):
    """
    삭제된 사용자의 기본 정보를 일정 기간동안 보관합니다.
    """

    original_user_id = UUIDv7Field(null=True)
    archived_data = models.FileField(upload_to=deleted_user_archive_upload_to, null=True, blank=True)

    delete_scheduled_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

class UserDeletionFeedback(BaseModel):
    """
    사용자가 삭제 후 남긴 피드백을 저장합니다.
    """

    feedback_text = models.TextField(null=False, blank=False)


class UserFlag(BaseModel):
    """
    사용자 프로필 신고 기록을 저장합니다.
    """
    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['flagged_by']),

            GinIndex(fields=['reason']),

            models.Index(fields=['resolved_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flags')
    flagged_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flagged_users')

    reason = models.JSONField(default=list)
    user_description = models.TextField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)