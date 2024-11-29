from rest_framework import serializers

from card.models import Card, UserCardAsset

class PublicSelfUserCardAssetSerializer(serializers.ModelSerializer):
    """
    카드 에셋 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = UserCardAsset
        fields = ('id', 'type', 'public_url', 'mimetype', 'size', 'created_at', 'updated_at')

class PublicCardSerializer(serializers.ModelSerializer):
    """
    카드 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = Card
        fields = ('id', 'title', 'content', 'created_at', 'updated_at')


class PublicSelfCardSerializer(serializers.ModelSerializer):
    """
    자신의 카드 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = Card
        fields = ('id', 'title', 'content', 'asset_references', 'created_at', 'updated_at')

    asset_references = PublicSelfUserCardAssetSerializer(many=True, read_only=True)