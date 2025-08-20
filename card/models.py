from datetime import timedelta
from typing import Optional

from dacite import from_dict
from django.core.files.storage import default_storage, Storage
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone

from uuid_v7.base import uuid7

from card.objdef import CardObject, AssetReference, ImageElement
from flitz.models import BaseModel
from location.models import LocationDistanceMixin
from user.models import User, UserMatch


# Create your models here.

def official_card_asset_upload_to(instance, filename):
    """
    공식 카드 에셋 파일의 저장 경로를 생성합니다.
    파일명은 UUID7을 사용하고, 확장자는 원본 파일에서 가져옵니다.
    디렉토리 샤딩을 적용하여 성능을 최적화합니다.
    """
    ext = filename.split('.')[-1] if '.' in filename else ''
    file_uuid = str(uuid7())
    filename = f"{file_uuid}.{ext}" if ext else file_uuid
    
    # UUID의 첫 2글자로 디렉토리 샤딩 (256개 디렉토리로 분산)
    shard = file_uuid[:2]
    return f"official_card_assets/{shard}/{filename}"


def card_asset_upload_to(instance, filename):
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
    return f"card_assets/{shard}/{filename}"



class OfficialCardAssetAuthor(BaseModel):
    name = models.CharField(max_length=64, null=False, blank=False)
    description = models.CharField(max_length=128, null=False, blank=False)

class OfficialCardAssetGroup(BaseModel):
    title = models.CharField(max_length=32, null=False, blank=False)
    description = models.CharField(max_length=128, null=False, blank=False)

    author = models.ForeignKey(OfficialCardAssetAuthor, on_delete=models.CASCADE, related_name='asset_groups')

    price = models.IntegerField(default=0)
    free = models.BooleanField(default=False)

    deleted_at = models.DateTimeField(null=True, blank=True)

class OfficialCardAsset(BaseModel):
    group = models.ForeignKey(OfficialCardAssetGroup, on_delete=models.CASCADE, related_name='assets')

    index = models.IntegerField(null=False, blank=False, default=0)

    title = models.CharField(max_length=32, null=True, blank=True)
    description = models.CharField(max_length=128, null=True, blank=True)

    type = models.CharField(max_length=32, null=False, blank=False)
    object = models.FileField(upload_to=official_card_asset_upload_to, null=True)

    mimetype = models.CharField(max_length=128, null=False, blank=False)
    size = models.IntegerField(null=False, blank=False)

    deleted_at = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

class OfficialCardAssetPurchase(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(OfficialCardAssetGroup, on_delete=models.CASCADE)

    refunded_at = models.DateTimeField(null=True, blank=True)

    refund_reason = models.CharField(max_length=128, null=True, blank=True)

class Card(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cards')

    title = models.CharField(max_length=32, null=False, blank=False)
    content = models.JSONField(null=False, blank=False)

    deleted_at = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

    # 최종으로 GC가 실행된 시간
    gc_ran_at = models.DateTimeField(null=True, blank=True)

    def remove_orphaned_assets(self):
        card_obj = from_dict(data_class=CardObject, data=self.content)

        current_references = card_obj.extract_asset_references()
        current_references_ids = [ref.id for ref in current_references]

        # 삭제되지 않은 애셋 레퍼런스만 필터링
        references_in_db = self.asset_references.filter(deleted_at__isnull=True)

        with transaction.atomic():
            for reference in references_in_db:
                if str(reference.id) not in current_references_ids:
                    reference.delete_asset()

    def get_content_with_url(self) -> dict:
        asset_references_queryset = self.asset_references.filter(deleted_at__isnull=True)
        card_obj = from_dict(data_class=CardObject, data=self.content)

        def resolve_asset_url(asset: Optional[AssetReference]) -> Optional[str]:
            if asset is None:
                return None

            asset_reference = asset_references_queryset.filter(id=asset.id).first()
            if asset_reference is None or (not asset_reference.object.name):
                return None

            return asset_reference.object.url

        if card_obj.background:
            card_obj.background.public_url = resolve_asset_url(card_obj.background)

        for element in card_obj.elements:
            if isinstance(element, ImageElement):
                element.source.public_url = resolve_asset_url(element.source)

        return card_obj.as_dict()

class UserCardAsset(BaseModel):
    class AssetType(models.TextChoices):
        IMAGE = 'image'
        VIDEO = 'video'
        AUDIO = 'audio'
        OTHER = 'other'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='asset_references')

    type = models.CharField(max_length=32, null=False, blank=False, choices=AssetType.choices)

    object = models.FileField(upload_to=card_asset_upload_to, null=True)

    mimetype = models.CharField(max_length=128, null=False, blank=False)
    size = models.IntegerField(null=False, blank=False)

    deleted_at = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

    def delete_asset(self):
        # FileField가 실제 파일을 가지고 있는지 확인
        if self.object and self.object.name:
            self.object.delete(save=False)  # save=False로 DB 중복 저장 방지

        self.deleted_at = timezone.now()
        self.save()

class CardFlag(BaseModel):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='flags')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flagged_cards')

    reason = models.CharField(max_length=128, null=False, blank=False)
    user_description = models.TextField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)

class CardDistribution(BaseModel, LocationDistanceMixin):
    class Meta:
        # XXX: 개발 단계에서 같은 카드를 여러번 distribute하는건 사실 편하기 때문에 이걸 막아야 하는지는 잘 모르겠음
        # unique_together = (('card', 'user'),)

        indexes = [
            models.Index(fields=['card']),
            models.Index(fields=['user']),

            models.Index(fields=['reveal_phase']),

            models.Index(fields=['dismissed_at']),
            models.Index(fields=['deleted_at']),

            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]

    class RevealPhase(models.IntegerChoices):
        # 카드가 아예 표시되지 않음
        HIDDEN = 0

        # 흐릿하게 표시됨
        BLURRY_STRONG = 1

        # 덜 흐릿하게 표시됨 (maybe unused)
        BLURRY_SOFT = 2

        # 완전히 표시됨
        FULLY_REVEALED = 3

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='distributions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_cards')

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    reveal_phase = models.IntegerField(default=0, choices=RevealPhase.choices)

    dismissed_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    @property
    def opponent(self) -> User:
        """
        상대방 사용자를 가져옵니다.
        """

        return self.card.user

    @transaction.atomic
    def update_reveal_phase(self):
        """
        카드의 공개 단계를 업데이트합니다.
        """
        if self.reveal_phase == CardDistribution.RevealPhase.FULLY_REVEALED:
            return

        if not self.is_okay_to_reveal_assertive:
            self.reveal_phase = CardDistribution.RevealPhase.HIDDEN
            self.deleted_at = timezone.now()
            return

        if self.is_okay_to_reveal_immediately or self.is_okay_to_reveal_hard:
            self.reveal_phase = CardDistribution.RevealPhase.FULLY_REVEALED
            return
        elif self.is_okay_to_reveal_soft:
            if self.reveal_phase == CardDistribution.RevealPhase.HIDDEN:
                self.reveal_phase = CardDistribution.RevealPhase.BLURRY_STRONG
                return


    @property
    def is_okay_to_reveal_assertive(self) -> bool:
        """
        배포받은 카드가 사용자에게 공개될 수 있는지 확인합니다. (assertive)
        사용자의 안전을 최우선으로 하기 위해, 이 조건들을 선행으로 만족하지 않으면 soft / hard를 만족하더라도 카드를 공개하지 않습니다.

        - opponent가 **shadowban** 처리되어 있으면 카드 표시하지 않음 (GC를 통해 삭제되어야 함)
        - opponent가 **차단/제한 목록**에 등록되어 있으면 카드 표시하지 않음 (GC를 통해 삭제되어야 함)

        NOTE: 이 조건 테스트에 실패한 경우 이 distribution은 즉시 삭제되어야 합니다.
        """

        # 1. opponent가 shadowban 상태이면 카드를 표시하지 않는다
        is_shadowbanned = False  # FIXME: shadowban 개념이 아직 없음

        if is_shadowbanned:
            return False

        # 2. opponent가 차단되어 있으면 카드를 표시하지 않는다
        is_blocked = self.opponent.is_blocked_by(self.user)

        if is_blocked:
            return False


        return True

    @property
    def is_okay_to_reveal_immediately(self) -> bool:
        """
        배포받은 카드가 사용자에게 즉시 공개될 수 있는지 확인합니다. (immediate)
        """

        # TODO: 1. 공식 카드 여부
        is_official_card = False

        # 2. 기존에 매칭된 적이 있는지
        match_exists = UserMatch.match_exists(
            user_a=self.user,
            user_b=self.opponent
        )

        return is_official_card or match_exists

    @property
    def is_okay_to_reveal_soft(self) -> bool:
        """
        배포받은 카드가 사용자에게 공개될 수 있는지 확인합니다. (soft)

        AND(
            - 카드 교환 지점으로부터 300m 이상 멀어져야 함
            - 카드 교환 시점으로부터 30분 이상 경과해야 함
        )
        """

        if settings.DEVELOPMENT_MODE:
            # 개발 환경에서는 soft reveal 조건을 무시합니다.
            return True

        REVEAL_DISTANCE_SOFT  = 300 # meters
        REVEAL_TIMEDELTA_SOFT = timedelta(minutes=30)

        distance = self.distance_to(self.user.location)
        cond_distance = distance >= REVEAL_DISTANCE_SOFT

        utcnow = timezone.now()
        cond_time = (utcnow - self.created_at) >= REVEAL_TIMEDELTA_SOFT

        return cond_distance and cond_time

    @property
    def is_okay_to_reveal_hard(self) -> bool:
        """
        배포받은 카드가 사용자에게 공개될 수 있는지 확인합니다. (hard)

        AND(
            - 사용자의 마지막 위치로부터 500m 이상 멀어져야 함
            OR(
                - 카드 교환 지점으로부터 3km 이상 멀어져야 함
                - 카드 교환 시점으로부터 3시간 이상 경과해야 함
            )
        )
        """

        REVEAL_USER_DISTANCE_HARD = 500 # meters

        REVEAL_DISTANCE_HARD = 3000 # meters
        REVEAL_TIMEDELTA_HARD = timedelta(hours=3)

        user_distance = self.opponent.location.distance_to(self.user.location)
        cond_user_distance = user_distance >= REVEAL_USER_DISTANCE_HARD

        distance = self.distance_to(self.user.location)
        cond_distance = distance >= REVEAL_DISTANCE_HARD

        utcnow = timezone.now()
        cond_time = (utcnow - self.created_at) >= REVEAL_TIMEDELTA_HARD

        return cond_user_distance and (cond_distance or cond_time)

class CardVote(BaseModel):
    class Meta:
        unique_together = ['card', 'user']

    class VoteType(models.IntegerChoices):
        UPVOTE = 1
        DOWNVOTE = 2

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voted_cards')

    vote_type = models.IntegerField(choices=VoteType.choices)

class CardFavoriteItem(BaseModel):
    """
    사용자가 '좋아요'한 카드 아이템을 저장합니다.
    """

    class Meta:
        unique_together = (('user', 'card'),)
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['card']),

            models.Index(fields=['deleted_at']),
        ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='card_collection_items')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='collection_items')

    deleted_at = models.DateTimeField(null=True, blank=True)