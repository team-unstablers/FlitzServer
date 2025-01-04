from rest_framework import serializers

from user.models import User

class PublicUserSerializer(serializers.ModelSerializer):
    """
    타 사용자를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'profile_image_url')

class PublicSimpleUserSerializer(serializers.ModelSerializer):
    """
    타 사용자를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'profile_image_url')

class PublicSelfUserSerializer(serializers.ModelSerializer):
    """
    자신의 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'profile_image_url', 'free_coins', 'paid_coins')


