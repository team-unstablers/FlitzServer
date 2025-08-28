from rest_framework import serializers


class TokenRequestSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    device_info = serializers.CharField(required=True)
    apns_token = serializers.CharField(required=False, allow_null=True, allow_blank=True)

    turnstile_token = serializers.CharField(required=True, allow_null=False, allow_blank=False)

class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(required=True)
