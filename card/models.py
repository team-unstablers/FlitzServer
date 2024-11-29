from django.db import models

from flitz.models import BaseModel
from user.models import User

# Create your models here.

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
    object_key = models.CharField(max_length=2048, null=False, blank=False)
    public_url = models.CharField(max_length=2048, null=False, blank=False)

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
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    title = models.CharField(max_length=32, null=False, blank=False)
    content = models.JSONField(null=False, blank=False)

    deleted_at = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

class UserCardAsset(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='asset_references')

    type = models.CharField(max_length=32, null=False, blank=False)
    object_key = models.CharField(max_length=2048, null=False, blank=False)
    public_url = models.CharField(max_length=2048, null=False, blank=False)

    mimetype = models.CharField(max_length=128, null=False, blank=False)
    size = models.IntegerField(null=False, blank=False)

    deleted_at = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

class CardFlag(BaseModel):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='flags')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flagged_cards')

    reason = models.CharField(max_length=128, null=False, blank=False)
    user_description = models.TextField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)

class CardDistribution(BaseModel):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='distributions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_cards')

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

class CardVote(BaseModel):
    class VoteType(models.IntegerChoices):
        UPVOTE = 1
        DOWNVOTE = 2

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voted_cards')

    vote_type = models.IntegerField(choices=VoteType.choices)

