from rest_framework import serializers

from user.models import User, UserIdentity


class PublicUserSerializer(serializers.ModelSerializer):
    """
    타 사용자를 fetch할 때 사용되는 serializer
    """

    profile_image_url = serializers.ImageField(source='profile_image', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'title', 'bio', 'hashtags', 'profile_image_url')

class PublicSimpleUserSerializer(serializers.ModelSerializer):

    profile_image_url = serializers.ImageField(source='profile_image', read_only=True)

    """
    타 사용자를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = User
        # FIXME: 이거 앱 호환성때문에 부수 fields가 추가됨... ㅠㅠㅠㅠ
        #        앱 내에서 SimpleUser와 User를 구분하십시오!!
        fields = ('id', 'username', 'display_name', 'title', 'bio', 'hashtags', 'profile_image_url')

class HashtagListField(serializers.JSONField):
    """
    해시태그 필드를 위한 커스텀 JSONField
    """

    def to_representation(self, value):
        # FIXME
        if isinstance(value, list):
            return [tag.strip() for tag in value if isinstance(tag, str)]

        return []

    def to_internal_value(self, data):
        # FIXME
        if isinstance(data, list):
            return [tag.strip() for tag in data if isinstance(tag, str)]

        raise ValueError("Expected a list of strings for hashtags.")

class PublicSelfUserSerializer(serializers.ModelSerializer):
    """
    자신의 정보를 fetch할 때 사용되는 serializer
    """

    profile_image_url = serializers.ImageField(source='profile_image', read_only=True)

    title = serializers.CharField(allow_blank=True, max_length=20)
    bio = serializers.CharField(allow_blank=True, max_length=600)


    hashtags = HashtagListField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'display_name', 'title', 'bio', 'hashtags', 'birth_date', 'phone_number', 'profile_image_url', 'free_coins', 'paid_coins')
        read_only_fields = ('id', 'email', 'username', 'birth_date', 'phone_number', 'profile_image_url', 'free_coins', 'paid_coins')


class SelfUserIdentitySerializer(serializers.ModelSerializer):
    """
    자신의 정체성 / 선호 정보를 fetch하거나 수정할 때 사용되는 serializer
    """

    class Meta:
        model = UserIdentity
        fields = ('gender', 'is_trans', 'display_trans_to_others', 'preferred_genders', 'welcomes_trans', 'trans_prefers_safe_match')
