from datetime import timedelta

import jwt
from django.conf import settings
from django.db import models, transaction
from django.contrib.postgres.indexes import GinIndex
from django.utils import timezone
from uuid_v7.base import uuid7

from flitz.models import BaseModel

from user.models import User
from card.models import Card, CardDistribution

from location.utils.distance import measure_distance

def wavespot_post_image_upload_to(instance, filename):
    """
    카드 에셋 파일의 저장 경로를 생성합니다.
    파일명은 UUID7을 사용하고, 확장자는 원본 파일에서 가져옵니다.
    디렉토리 샤딩을 적용하여 성능을 최적화합니다.
    """
    ext = filename.split('.')[-1] if '.' in filename else ''
    file_uuid = str(uuid7())
    filename = f"{file_uuid}.{ext}" if ext else file_uuid

    # UUID의 첫 2글자로 디렉토리 샤딩 (256개 디렉토리로 분산)
    shard = file_uuid[:2]
    return f"wavespot_post_images/{shard}/{filename}"


class WaveSpot(BaseModel):
    """
    WaveSpot 제휴 업체 모델
    """

    class Meta:
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['major', 'minor']),
            models.Index(fields=['latitude', 'longitude']),

            models.Index(fields=['disabled_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

        constraints = [
            models.UniqueConstraint(fields=['major', 'minor'], name='unique_major_minor')
        ]

    # identifier
    name = models.CharField(max_length=32, unique=True)

    # 사용자에게 실제 표시하기 위한 이름
    display_name = models.CharField(max_length=32)

    # BLE iBeacon의 major, minor
    major = models.PositiveIntegerField(null=False)
    minor = models.PositiveIntegerField(null=False)

    # WaveSpot의 위치 정보
    latitude = models.FloatField(null=False)
    longitude = models.FloatField(null=False)

    # in meters
    radius = models.FloatField(null=False)

    disabled_at = models.DateTimeField(null=True, default=None)

    def authorize(self, latitude: float, longitude: float) -> bool:
        distance_kilo = measure_distance((self.latitude, self.longitude), (latitude, longitude))
        distance_meter = distance_kilo * 1000

        return distance_meter <= self.radius

class WaveSpotAppClipSession(BaseModel):
    """
    iOS App Clip 세션 모델
    """

    wavespot = models.ForeignKey(WaveSpot, on_delete=models.CASCADE, related_name='+')

    user_agent = models.CharField(max_length=256, null=True, blank=True)

    # 방문자 닉네임 (16자 이내)
    nickname = models.CharField(max_length=16, null=False, blank=False)

    # IP Address
    initiated_from = models.CharField(max_length=128, null=False, blank=False)

    expires_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)

    def create_token(self) -> str:
        now = timezone.now()

        token = jwt.encode({
            'sub': str(self.id),
            'iat': now,
            # 만료 시간은 6시간으로 지정한다. 실질 6시간 이상 체류하는 경우는 거의 없을 것으로 예상됨.
            'exp': now + timedelta(hours=6),
            'x-flitz-options': '--with-love --wavespot-session',
        }, key=settings.SECRET_KEY, algorithm='HS256')

        return token

    @property
    def is_authenticated(self) -> bool:
        """
        DRF 호환용
        """
        return True

class WaveSpotPost(BaseModel):
    """
    WaveSpot에 게시되는 방문자 포스트 모델
    """

    class AuthorType(models.TextChoices):
        USER = 'user', 'User'
        APP_CLIP = 'app_clip', 'App Clip Session'

    class Meta:
        indexes = [
            models.Index(fields=['wavespot']),
            models.Index(fields=['author_type']),
            models.Index(fields=['author_user']),
            models.Index(fields=['author_app_clip']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),

            models.Index(fields=['deleted_at']),
        ]

        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(author_type='user', author_user__isnull=False, author_app_clip__isnull=True) |
                    models.Q(author_type='app_clip', author_user__isnull=True, author_app_clip__isnull=False)
                ),
                name='wavespot_post_author_integrity'
            )
        ]

    wavespot = models.ForeignKey(WaveSpot, on_delete=models.CASCADE, related_name='posts')

    # 작성자 - 둘 중 하나만 설정됨
    author_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='wavespot_posts',
                                   null=True, blank=True)
    author_app_clip = models.ForeignKey(WaveSpotAppClipSession,
                                       on_delete=models.CASCADE,
                                       related_name='posts',
                                       null=True, blank=True)
    author_type = models.CharField(max_length=10, choices=AuthorType.choices, db_index=True)

    content = models.TextField(max_length=512)

    deleted_at = models.DateTimeField(null=True, default=None)

    @property
    def author(self):
        """작성자 객체를 반환"""
        if self.author_type == self.AuthorType.USER:
            return self.author_user
        return self.author_app_clip

    def save(self, *args, **kwargs):
        # author_type 자동 설정
        if self.author_user:
            self.author_type = self.AuthorType.USER
        elif self.author_app_clip:
            self.author_type = self.AuthorType.APP_CLIP
        super().save(*args, **kwargs)

class WaveSpotPostFlag(BaseModel):
    """
    WaveSpot 포스트 신고 기록을 저장합니다.
    """

    class Meta:
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['flagged_by']),

            GinIndex(fields=['reason']),

            models.Index(fields=['resolved_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    post = models.ForeignKey(WaveSpotPost, on_delete=models.CASCADE, related_name='flags')
    flagged_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+', null=True)

    reason = models.JSONField(default=list)
    user_description = models.TextField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)


class WaveSpotPostImage(BaseModel):
    """
    WaveSpotPost에 첨부되는 이미지 모델
    """

    class Meta:
        indexes = [
            models.Index(fields=['post']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    post = models.ForeignKey(WaveSpotPost, on_delete=models.CASCADE, related_name='images')

    image = models.FileField(upload_to=wavespot_post_image_upload_to, null=True)
    deleted_at = models.DateTimeField(null=True, default=None)

class WaveSpotCardDistribution(BaseModel):
    """
    WaveSpot에서 배포되는 카드 모델
    """

    class Meta:
        indexes = [
            models.Index(fields=['wavespot']),
            models.Index(fields=['card']),

            models.Index(fields=['deleted_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    wavespot = models.ForeignKey(WaveSpot, on_delete=models.CASCADE, related_name='card_distributions')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='wavespot_distributions')

    quantity = models.PositiveIntegerField(null=False, default=3)
    distributed_count = models.PositiveIntegerField(null=False, default=0)

    deleted_at = models.DateTimeField(null=True, default=None)

    def can_distribute(self, user: User) -> bool:
        """
        이 카드를 사용자가 가져갈 수 있는지 여부를 반환합니다.
        """

        if self.deleted_at is not None:
            # ASSERTION: 이미 삭제된 카드는 가져갈 수 없습니다.
            return False

        if user.is_blocked_by(self.card.user) or self.card.user.is_blocked_by(user):
            # ASSERTION: 차단 상태인 경우 카드를 가져갈 수 없습니다.
            return False

        return self.distributed_count < self.quantity

    @transaction.atomic
    def distribute(self, user: User) -> bool:
        """
        사용자가 이 카드를 가져가도록 시도합니다.
        :return: 카드를 성공적으로 가져갔으면 True, 이미 가져갔거나 배포할 수 없으면 False
        """

        if not self.can_distribute(user):
            return False

        already_distributed = CardDistribution.objects.filter(user=user, card=self.card).exists()

        if already_distributed:
            return False

        distribution = CardDistribution.objects.create(
            user=user,
            card=self.card,

            distribution_method=CardDistribution.DistributionMethod.WAVESPOT,
            reveal_phase=CardDistribution.RevealPhase.FULLY_REVEALED
        )

        self.distributed_count += 1

        return True

