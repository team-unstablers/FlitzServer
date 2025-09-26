from rest_framework import serializers

from card.serializers import PublicCardSerializer
from wavespot.models import WaveSpot, WaveSpotCardDistribution, WaveSpotPost, WaveSpotPostImage


class WaveSpotAuthorizationSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()

    major = serializers.IntegerField()
    minor = serializers.IntegerField()

class WaveSpotAppClipAuthorizationSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()

    major = serializers.IntegerField()
    minor = serializers.IntegerField()

    nickname = serializers.CharField(max_length=16)
    user_agent = serializers.CharField(max_length=256, required=False, allow_blank=True)

class WaveSpotSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaveSpot
        fields = ['id', 'display_name']
        read_only_fields = ['id', 'display_name']

class WaveSpotCardDistributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaveSpotCardDistribution
        fields = ['id', 'card', 'quantity', 'distributed_count']

    card = PublicCardSerializer()

class WaveSpotCardDistributionCreateSerializer(serializers.Serializer):
    card_id = serializers.UUIDField()

class WaveSpotPostAuthorSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=16)
    profile_image_url = serializers.CharField(max_length=4096, required=False)
    author_type = serializers.CharField(read_only=True)

class WaveSpotPostImageSerializer(serializers.ModelSerializer):
    """방명록 게시글 이미지 시리얼라이저"""
    class Meta:
        model = WaveSpotPostImage
        fields = ['id', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # S3 URL로 변환
        if instance.image:
            request = self.context.get('request')
            if request:
                data['image'] = request.build_absolute_uri(instance.image.url)
        return data


class WaveSpotPostSerializer(serializers.ModelSerializer):
    """방명록 게시글 조회용 시리얼라이저"""
    author = serializers.SerializerMethodField()
    images = WaveSpotPostImageSerializer(many=True, read_only=True)

    class Meta:
        model = WaveSpotPost
        fields = ['id', 'author', 'content', 'images', 'created_at', 'updated_at']
        read_only_fields = ['id', 'author', 'images', 'created_at', 'updated_at']

    def get_author(self, obj):
        """author_type에 따라 적절한 author 정보 반환"""
        if obj.author_type == WaveSpotPost.AuthorType.USER and obj.author_user:
            return {
                'nickname': obj.author_user.display_name or obj.author_user.username,
                'profile_image_url': obj.author_user.profile_thumbnail_url if obj.author_user.profile_thumbnail else None,
                'author_type': 'user'
            }
        elif obj.author_type == WaveSpotPost.AuthorType.APP_CLIP and obj.author_app_clip:
            return {
                'nickname': obj.author_app_clip.nickname,
                'profile_image_url': None,  # App Clip은 프로필 이미지 없음
                'author_type': 'app_clip'
            }
        return None


class WaveSpotPostCreateSerializer(serializers.ModelSerializer):
    """방명록 게시글 생성용 시리얼라이저"""
    images = serializers.ListField(
        child=serializers.ImageField(),
        max_length=4,
        required=False,
        write_only=True,
        help_text="최대 4개의 이미지 첨부 가능"
    )

    class Meta:
        model = WaveSpotPost
        fields = ['content', 'images']

    def validate_images(self, value):
        """이미지 검증"""
        if len(value) > 4:
            raise serializers.ValidationError("최대 4개의 이미지만 첨부할 수 있습니다.")

        # 각 이미지 크기 체크 (예: 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        for img in value:
            if img.size > max_size:
                raise serializers.ValidationError(f"이미지 크기는 10MB를 초과할 수 없습니다. ({img.name})")

        return value

    def create(self, validated_data):
        images = validated_data.pop('images', [])

        # request context에서 user 또는 app_clip_session 가져오기
        request = self.context.get('request')
        wavespot = self.context.get('wavespot')  # ViewSet에서 전달

        # author 설정
        if hasattr(request, 'user') and request.user.is_authenticated:
            validated_data['author_user'] = request.user
            validated_data['author_type'] = WaveSpotPost.AuthorType.USER
        elif hasattr(request, 'app_clip_session'):
            validated_data['author_app_clip'] = request.app_clip_session
            validated_data['author_type'] = WaveSpotPost.AuthorType.APP_CLIP
        else:
            raise serializers.ValidationError("인증된 사용자 또는 App Clip 세션이 필요합니다.")

        validated_data['wavespot'] = wavespot

        # 포스트 생성
        post = super().create(validated_data)

        # 이미지 처리 및 저장
        if images:
            from flitz.thumbgen import generate_thumbnail

            for image in images:
                # 썸네일 생성 (선택적)
                # 여기서는 원본을 그대로 저장하거나 리사이즈 처리
                post_image = WaveSpotPostImage.objects.create(
                    post=post,
                    image=image
                )

        return post