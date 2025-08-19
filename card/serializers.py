from rest_framework import serializers

from user.serializers import PublicSimpleUserSerializer

from card.models import Card, UserCardAsset, CardDistribution, CardFavoriteItem


class PublicSelfUserCardAssetSerializer(serializers.ModelSerializer):
    """
    카드 에셋 정보를 fetch할 때 사용되는 serializer
    """
    public_url = serializers.FileField(source='object', read_only=True)
    
    class Meta:
        model = UserCardAsset
        fields = ('id', 'type', 'public_url', 'mimetype', 'size', 'created_at', 'updated_at')

class PublicWriteOnlyCardSerializer(serializers.ModelSerializer):
    """
    카드 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = Card
        fields = ('id', 'user', 'title', 'content', 'created_at', 'updated_at')

    user = PublicSimpleUserSerializer()


class PublicCardSerializer(serializers.ModelSerializer):
    """
    카드 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = Card
        fields = ('id', 'user', 'title', 'content', 'created_at', 'updated_at')

    user = PublicSimpleUserSerializer()
    content = serializers.SerializerMethodField(method_name='get_content')

    def get_content(self, obj: Card):
        return obj.get_content_with_url()

class CardDistributionSerializer(serializers.ModelSerializer):
    """
    카드 배포 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = CardDistribution
        fields = ('id', 'card', 'user')

    card = PublicCardSerializer()
    user = PublicSimpleUserSerializer()

class CardFavoriteItemSerializer(serializers.ModelSerializer):
    """
    카드 즐겨찾기 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = CardFavoriteItem
        fields = ('id', 'card')

    card = PublicCardSerializer()
