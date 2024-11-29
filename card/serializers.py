from rest_framework import serializers

from user.serializers import PublicSimpleUserSerializer

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
        fields = ('id', 'user', 'title', 'content', 'created_at', 'updated_at')

    user = PublicSimpleUserSerializer()


class PublicCardListSerializer(serializers.ModelSerializer):
    """
    자신의 카드 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = Card
        fields = ('id', 'user', 'title', 'created_at', 'updated_at')

    user = PublicSimpleUserSerializer()


