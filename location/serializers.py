from rest_framework import serializers

class UpdateLocationSerializer(serializers.Serializer):
    """
    사용자의 위치 정보를 업데이트하기 위한 Serializer
    """
    latitude = serializers.FloatField(required=True)
    longitude = serializers.FloatField(required=True)
    altitude = serializers.FloatField(required=False, allow_null=True)

    accuracy = serializers.FloatField(required=False, allow_null=True)

class DiscoveryReportSerializer(serializers.Serializer):
    """
    다른 사용자 발견을 보고하기 위한 Serializer
    """
    session_id = serializers.UUIDField(required=True)
    discovered_session_id = serializers.UUIDField(required=True)
    
    latitude = serializers.FloatField(required=True)
    longitude = serializers.FloatField(required=True)
    altitude = serializers.FloatField(required=False, allow_null=True)
    
    accuracy = serializers.FloatField(required=False, allow_null=True)
    
    def validate(self, data):
        """
        세션 ID가 유효한지, 자신의 세션이 맞는지 등 검증
        """
        if data['session_id'] == data['discovered_session_id']:
            raise serializers.ValidationError("자신의 세션은 발견할 수 없습니다.")
        
        return data
