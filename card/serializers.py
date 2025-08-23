from rest_framework import serializers

from user.serializers import PublicSimpleUserSerializer

from card.models import Card, UserCardAsset, CardDistribution, CardFavoriteItem, CardFlag


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
        fields = ('id', 'card', 'user', 'reveal_phase')

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


class CardFlagSerializer(serializers.ModelSerializer):
    
    reason = serializers.JSONField(required=True)
    user_description = serializers.CharField(required=False, allow_blank=True)

    def validate_reason(self, value):
        """
        reason이 문자열 배열인지 검증
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("reason must be an array")
        
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("reason must be an array of strings")
        
        if len(value) == 0:
            raise serializers.ValidationError("reason array cannot be empty")
        
        return value
    
    def create(self, validated_data):
        # context에서 user와 card 자동 설정
        validated_data['user'] = self.context['request'].user
        validated_data['card'] = self.context['card']
        return super().create(validated_data)

    class Meta:
        model = CardFlag
        fields = ('reason', 'user_description')
