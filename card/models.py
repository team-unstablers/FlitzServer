from dacite import from_dict
from django.core.files.storage import default_storage, Storage
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone

from uuid_v7.base import uuid7

from card.objdef import CardObject
from flitz.models import BaseModel
from location.models import LocationDistanceMixin
from user.models import User

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

    def remove_orphaned_assets(self):
        card_obj = from_dict(data_class=CardObject, data=self.content)

        current_references = card_obj.extract_asset_references()
        current_references_ids = [ref.id for ref in current_references]

        references_in_db = self.asset_references.all()

        with transaction.atomic():
            for reference in references_in_db:
                if reference.id not in current_references_ids:
                    reference.delete_asset()

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
    class RevealPhase(models.IntegerChoices):
        # 카드가 아예 표시되지 않음
        HIDDEN = 0

        # 45분 경과 후 흐릿하게 표시됨
        BLURRY_STRONG = 1

        # 90분 경과 후 약간 덜 흐릿하게 표시됨
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

    def update_reveal_phase(self):
        """
        카드의 공개 단계를 업데이트합니다.
        """
        with transaction.atomic():
            if self.reveal_phase == CardDistribution.RevealPhase.FULLY_REVEALED:
                return

            if not self.is_okay_to_reveal_assertive:
                return

            if self.is_okay_to_reveal_soft or self.is_okay_to_reveal_hard:
                self.reveal_phase = CardDistribution.RevealPhase.FULLY_REVEALED
            else:
                """
                TODO: phased reveal을 도입할지 말지 고려해봐야 합니다.
                
                timediff = timezone.now() - self.created_at

                if self.reveal_phase == CardDistribution.RevealPhase.HIDDEN and \
                   timediff >= settings.CARD_REVEAL_TIME_BLURRY_STRONG:
                    self.reveal_phase = CardDistribution.RevealPhase.BLURRY_STRONG
                elif self.reveal_phase == CardDistribution.RevealPhase.BLURRY_STRONG and \
                   timediff >= settings.CARD_REVEAL_TIME_BLURRY_SOFT:
                    self.reveal_phase = CardDistribution.RevealPhase.BLURRY_SOFT
                """

                return
            self.save()


    @property
    def is_okay_to_reveal_assertive(self) -> bool:
        """
        (TODO: 조건 확실히 하세요)
        배포받은 카드가 사용자에게 공개될 수 있는지 확인합니다. (assertive)
        사용자의 안전을 최우선으로 하기 위해, 이 조건들을 선행으로 만족하지 않으면 soft / hard를 만족하더라도 카드를 공개하지 않습니다.

        - opponent가 여전히 가까이 있으면 카드 표시하지 않음
        - opponent가 **차단/제한 목록**에 등록되어 있으면 카드 표시하지 않음 (GC를 통해 삭제되어야 함)
        - opponent가 **shadowban** 처리되어 있으면 카드 표시하지 않음 (GC를 통해 삭제되어야 함)
        """

        # opponent가 너무 가까이 있으면 카드 표시하지 않음
        opponent_distance = self.distance_to(self.opponent.location)
        cond_distance = opponent_distance >= settings.CARD_REVEAL_DISTANCE_ASSERTIVE

        return cond_distance

    @property
    def is_okay_to_reveal_soft(self) -> bool:
        """
        배포받은 카드가 사용자에게 공개될 수 있는지 확인합니다. (soft)

        AND(
            - 카드 교환 지점으로부터 2km 이상 멀어져야 함
            - 카드 교환 시점으로부터 2시간 이상 경과해야 함
        )
        """

        distance = self.distance_to(self.user.location)
        cond_distance = distance >= settings.CARD_REVEAL_DISTANCE_SOFT

        utcnow = timezone.now()
        cond_time = utcnow - self.created_at >= settings.CARD_REVEAL_TIME_SOFT

        return cond_distance and cond_time

    @property
    def is_okay_to_reveal_hard(self) -> bool:
        """
        배포받은 카드가 사용자에게 공개될 수 있는지 확인합니다. (hard)

        OR(
            - 카드 교환 지점으로부터 15km 이상 멀어져야 함
            - 카드 교환 시점으로부터 24시간 이상 경과해야 함
        )
        """

        distance = self.distance_to(self.user.location)
        cond_distance = distance >= settings.CARD_REVEAL_DISTANCE_HARD

        utcnow = timezone.now()
        cond_time = utcnow - self.created_at >= settings.CARD_REVEAL_TIME_HARD

        return cond_distance or cond_time






class CardVote(BaseModel):
    class Meta:
        unique_together = ['card', 'user']

    class VoteType(models.IntegerChoices):
        UPVOTE = 1
        DOWNVOTE = 2

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voted_cards')

    vote_type = models.IntegerField(choices=VoteType.choices)

