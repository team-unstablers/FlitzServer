from rest_framework import serializers


class TokenRequestSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    device_info = serializers.CharField(required=False, default='unknown')
    apns_token = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class UserCreationSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
