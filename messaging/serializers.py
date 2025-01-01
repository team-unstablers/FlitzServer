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
        read_only=True
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
        read_only_fields = ('id', 'sender')
        fields = (*read_only_fields, 'content', 'sent_by', 'parent_conversation')


class DirectMessageFlagSerializer(serializers.ModelSerializer):
    """
    | write: target_message(id), reason, user_description
    | read: conversation(dict), user(dict), message(dict), reason, user_description, resolved_at
    |
    | 시리얼라이저를 통해서는 create 만 지원. update 는 UnsupportedOperationException 을 발생시킵니다.
    """

    conversation = DirectMessageConversationSerializer(
        read_only=True
    )

    user = PublicUserSerializer(
        read_only=True
    )

    message = DirectMessageSerializer(
        read_only=True
    )
    target_message = serializers.PrimaryKeyRelatedField(
        queryset=DirectMessage.objects.all(),
        write_only=True
    )

    def set_fields_using_target_message(self, validated_data):
        target_message: DirectMessage = validated_data.pop('target_message')
        validated_data['message'] = target_message
        validated_data['conversation'] = target_message.conversation_id
        validated_data['user'] = target_message.sender_id
        return validated_data

    def create(self, validated_data):
        return super().create(self.set_fields_using_target_message(validated_data))

    def update(self, instance, validated_data):
        return UnsupportedOperationException()

    class Meta:
        model = DirectMessageFlag
        read_only_fields = (
            'id',
            'message',
            'conversation',
            'user',
            'reason',
            'user_description',
            'resolved_at',
        )
        fields = (
            *read_only_fields,
            'target_message',
        )


class DirectMessageAttachmentSerializer(serializers.ModelSerializer):
    """
    DM 첨부파일 정보를 fetch할 때 사용되는 serializer
    """
    class Meta:
        model = DirectMessageAttachment
        fields = ('id', 'type', 'public_url', 'mimetype', 'size', 'created_at', 'updated_at')
