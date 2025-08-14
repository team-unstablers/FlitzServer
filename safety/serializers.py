from rest_framework import serializers
from user.serializers import PublicSimpleUserSerializer
from safety.models import UserBlock, UserWaveSafetyZone


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
