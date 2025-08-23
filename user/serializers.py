from rest_framework import serializers

from user.models import User, UserIdentity, UserSettings, UserFlag
from user.utils import validate_password


class PublicUserSerializer(serializers.ModelSerializer):
    """
    타 사용자를 fetch할 때 사용되는 serializer
    """

    profile_image_url = serializers.ImageField(source='profile_image', read_only=True)
    online_status = serializers.CharField(read_only=True)
    fuzzy_distance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'display_name', 'title', 'bio', 'hashtags', 'online_status', 'fuzzy_distance', 'profile_image_url')

    def get_fuzzy_distance(self, obj: User):
        request = self.context.get('request')
        user = request.user if request else None

        if user and user.is_authenticated:
            return obj.fuzzy_distance_to(user)

        return 'farthest'

class PublicSimpleUserSerializer(serializers.ModelSerializer):

    profile_image_url = serializers.ImageField(source='profile_image', read_only=True)
    online_status = serializers.CharField(read_only=True)
    fuzzy_distance = serializers.SerializerMethodField()

    """
    타 사용자를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = User
        # FIXME: 이거 앱 호환성때문에 부수 fields가 추가됨... ㅠㅠㅠㅠ
        #        앱 내에서 SimpleUser와 User를 구분하십시오!!
        fields = ('id', 'username', 'display_name', 'title', 'bio', 'hashtags', 'online_status', 'fuzzy_distance', 'profile_image_url')


    def get_fuzzy_distance(self, obj: User):
        request = self.context.get('request')
        user = request.user if request else None

        if user and user.is_authenticated:
            return obj.fuzzy_distance_to(user)

        return 'farthest'

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

    online_status = serializers.CharField(read_only=True)
    fuzzy_distance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'display_name', 'title', 'bio', 'hashtags', 'birth_date', 'phone_number', 'profile_image_url', 'online_status', 'fuzzy_distance', 'free_coins', 'paid_coins')
        read_only_fields = ('id', 'email', 'username', 'birth_date', 'phone_number', 'profile_image_url', 'online_status', 'fuzzy_distance', 'free_coins', 'paid_coins')

    def get_fuzzy_distance(self, obj: User):
        # 자기 자신은 가장 가까운 거리로 표시
        return 'nearest'

class SelfUserIdentitySerializer(serializers.ModelSerializer):
    """
    자신의 정체성 / 선호 정보를 fetch하거나 수정할 때 사용되는 serializer
    """

    class Meta:
        model = UserIdentity
        fields = ('gender', 'is_trans', 'display_trans_to_others', 'preferred_genders', 'welcomes_trans', 'trans_prefers_safe_match')


class UserRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=24, allow_blank=False, allow_null=False)
    password = serializers.CharField(max_length=128, allow_blank=False, allow_null=False)

    display_name = serializers.CharField(max_length=24, allow_blank=False)

    title = serializers.CharField(allow_blank=False, max_length=20)
    bio = serializers.CharField(allow_blank=False, max_length=600)
    hashtags = HashtagListField()

class UserSettingsSerializer(serializers.ModelSerializer):
    """
    자신의 설정 정보를 fetch하거나 수정할 때 사용되는 serializer
    """

    class Meta:
        model = UserSettings
        fields = (
            'messaging_notifications_enabled',
            'match_notifications_enabled',
            'notice_notifications_enabled',
            'marketing_notifications_enabled',

            'marketing_notifications_enabled_at',
        )

        read_only_fields = (
            'marketing_notifications_enabled_at',
        )
    
    def update(self, instance, validated_data):
        # marketing_notifications_enabled 변경 시 날짜 자동 업데이트
        if 'marketing_notifications_enabled' in validated_data:
            from django.utils import timezone
            
            if validated_data['marketing_notifications_enabled']:
                # True로 변경되고, 기존에 동의 날짜가 없으면 현재 시간 설정
                if not instance.marketing_notifications_enabled_at:
                    instance.marketing_notifications_enabled_at = timezone.now()
            else:
                # False로 변경되면 동의 날짜 제거
                instance.marketing_notifications_enabled_at = None
        
        return super().update(instance, validated_data)

class UserPasswdSerializer(serializers.Serializer):
    """
    비밀번호 변경을 위한 serializer
    """

    old_password = serializers.CharField(max_length=128, allow_blank=False, allow_null=False)
    new_password = serializers.CharField(max_length=128, allow_blank=False, allow_null=False)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("현재 비밀번호가 일치하지 않습니다.")
        return value

    def validate_new_password(self, value):
        validated, reason = validate_password(value)

        if not validated:
            raise serializers.ValidationError(reason)

        return value

class UserDeactivationSerializer(serializers.Serializer):
    """
    사용자 탈퇴를 위한 serializer
    """

    password = serializers.CharField(max_length=128, allow_blank=False, allow_null=False)
    feedback = serializers.CharField(max_length=600, allow_blank=True, required=False)

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("비밀번호가 일치하지 않습니다.")
        return value


class UserFlagSerializer(serializers.ModelSerializer):
    """
    사용자 신고를 위한 serializer
    """
    
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
        # context에서 flagged_by와 user 자동 설정
        validated_data['flagged_by'] = self.context['request'].user
        validated_data['user'] = self.context['user']
        return super().create(validated_data)

    class Meta:
        model = UserFlag
        fields = ('reason', 'user_description')