from rest_framework import serializers

from flitz.exceptions import UnsupportedOperationException
from messaging.models import DirectMessageParticipant, DirectMessage, DirectMessageFlag, DirectMessageConversation, DirectMessageAttachment
from user.models import User
from user.serializers import PublicUserSerializer


class DirectMessageParticipantSerializer(serializers.ModelSerializer):
    """
    | write: unsupported
    | read: user(dict), read_at
    |
    | 시리얼라이저를 통한 create, update 는 지원하지 않습니다.
    | DirectMessageConversation 이 만들어질 때 같이 내부적으로 생성됩니다.
    """

    user = PublicUserSerializer(
        read_only=True
    )

    def create(self, validated_data):
        raise UnsupportedOperationException()

    def update(self, instance, validated_data):
        raise UnsupportedOperationException()

    class Meta:
        model = DirectMessageParticipant
        read_only_fields = ('user', 'read_at')
        fields = (*read_only_fields,)



class DirectMessageSerializer(serializers.ModelSerializer):
    """
    | write: sent_by(id), parent_conversation(id), content
    | read: sender, content
    |
    | 시리얼라이저를 통해서는 create 만 지원. update 는 UnsupportedOperationException 을 발생시킵니다.
    """

    sent_by = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        write_only=True
    )
    sender = serializers.PrimaryKeyRelatedField(
        read_only=True,
        pk_field=serializers.CharField()
    )

    parent_conversation = serializers.PrimaryKeyRelatedField(
        queryset=DirectMessageConversation.objects.all(),
        write_only=True
    )

    def create(self, validated_data):
        validated_data['sender'] = validated_data.pop('sent_by')
        validated_data['conversation'] = validated_data.pop('parent_conversation')
        return super().create(validated_data)

    def update(self, instance, validated_data):
        raise UnsupportedOperationException()

    class Meta:
        model = DirectMessage
        read_only_fields = ('id', 'sender', 'created_at', 'updated_at')
        fields = (*read_only_fields, 'content', 'sent_by', 'parent_conversation', 'created_at', 'updated_at')


class DirectMessageReadOnlySerializer(DirectMessageSerializer):
    content = serializers.SerializerMethodField(method_name='get_content')

    def get_content(self, obj: DirectMessage):
        return obj.get_content_with_url()


class DirectMessageAttachmentSerializer(serializers.ModelSerializer):
    """
    DM 첨부파일 정보를 fetch할 때 사용되는 serializer
    """

    public_url = serializers.FileField(source='object', read_only=True)
    thumbnail_url = serializers.ImageField(source='thumbnail', read_only=True)

    class Meta:
        model = DirectMessageAttachment
        fields = ('id', 'type', 'public_url', 'thumbnail_url', 'mimetype', 'size', 'created_at', 'updated_at')


class DirectMessageConversationSerializer(serializers.ModelSerializer):
    """
    | write: initial_participants(id[])
    | read: latest_message, participants
    |
    | 시리얼라이저를 통해서는 create 만 지원. update 는 UnsupportedOperationException 을 발생시킵니다.
    """

    initial_participants = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        many=True,
        write_only=True
    )

    latest_message = DirectMessageReadOnlySerializer(read_only=True)

    participants = DirectMessageParticipantSerializer(
        many=True,
        read_only=True
    )

    def create(self, validated_data):
        initial_participants = validated_data.pop('initial_participants')

        created = super().create(validated_data)

        for initial_participant in initial_participants:
            DirectMessageParticipant.objects \
                .create(
                    user_id=initial_participant.id,
                    conversation_id=created.id
                ) \
                .save()

        return created

    def update(self, instance, validated_data):
        raise UnsupportedOperationException()

    class Meta:
        model = DirectMessageConversation
        read_only_fields = ('id', 'latest_message', 'participants')
        fields = (*read_only_fields, 'initial_participants')


class DirectMessageFlagSerializer(serializers.ModelSerializer):

    message = serializers.PrimaryKeyRelatedField(
        queryset=DirectMessage.objects.all(),
        required=False
    )

    reason = serializers.JSONField(required=True)
    user_description = serializers.CharField(required=False)

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
    
    def validate_message(self, value: DirectMessage):
        """
        message가 해당 conversation에 속하는지 검증
        """
        if value and 'conversation' in self.context:
            conversation = self.context['conversation']
            if value.conversation_id != conversation.id:
                raise serializers.ValidationError("Message does not belong to this conversation")
        return value
    
    def create(self, validated_data):
        # context에서 user와 conversation 자동 설정
        validated_data['user'] = self.context['request'].user
        validated_data['conversation'] = self.context['conversation']
        return super().create(validated_data)

    class Meta:
        model = DirectMessageFlag
        fields = ('message', 'reason', 'user_description')
