from rest_framework import serializers
from user.serializers import PublicSimpleUserSerializer
from safety.models import UserBlock, UserWaveSafetyZone, UserContactsTrigger


class UserWaveSafetyZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWaveSafetyZone
        fields = ('latitude', 'longitude', 'radius', 'is_enabled', 'enable_wave_after_exit')

class UserBlockSerializer(serializers.ModelSerializer):
    blocked_user = PublicSimpleUserSerializer(source='user', read_only=True)
    
    class Meta:
        model = UserBlock
        fields = ('id', 'blocked_user', 'created_at')  # 'reason' 필드 제외
        read_only_fields = ('id', 'blocked_user', 'created_at')

class UserContactsTriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserContactsTrigger
        fields = ('id', 'phone_number_hashed')
        read_only_fields = ('id', 'phone_number_hashed')

class UserContactsTriggerBulkCreateSerializer(serializers.Serializer):
    phone_numbers = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=True
    )

    def validate_phone_numbers(self, value):
        if not value:
            raise serializers.ValidationError("Phone numbers list cannot be empty.")
        return value

class UserContactsTriggerEnableSetterSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField(
        required=True,
        help_text="Enable or disable the contact trigger."
    )
