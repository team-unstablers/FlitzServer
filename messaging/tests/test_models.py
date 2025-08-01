from django.test import TestCase
from django.utils import timezone

from messaging.models import (
    DirectMessageConversation, DirectMessageParticipant,
    DirectMessage, DirectMessageAttachment
)
from flitz.test_utils import create_test_user

class DirectMessageModelTests(TestCase):
    def setUp(self):
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2)
    
    def test_create_conversation(self):
        """대화방 생성 및 참여자 테스트"""
        conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)
        
        # 대화방 생성 확인
        self.assertIsNotNone(conversation.id)
        
        # 참여자 확인
        participants = conversation.participants.all()
        self.assertEqual(participants.count(), 2)
        self.assertIn(self.user1.id, [p.user_id for p in participants])
        self.assertIn(self.user2.id, [p.user_id for p in participants])
    
    def test_participant_read_at(self):
        """참여자 읽음 상태 업데이트 테스트"""
        conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)
        
        # 참여자 조회
        participant1 = DirectMessageParticipant.objects.get(
            conversation=conversation, 
            user=self.user1
        )
        old_read_at = participant1.read_at
        
        # 1초 지연 후 읽음 상태 업데이트
        import time
        time.sleep(1)
        
        participant1.read_at = timezone.now()
        participant1.save()
        
        # 읽음 상태 업데이트 확인
        updated_participant = DirectMessageParticipant.objects.get(
            conversation=conversation, 
            user=self.user1
        )
        self.assertGreater(updated_participant.read_at, old_read_at)
    
    def test_message_creation(self):
        """메시지 생성 및 내용 테스트"""
        conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)
        
        # 텍스트 메시지 생성
        text_content = {
            "type": "text",
            "text": "Hello, this is a test message"
        }
        
        message = DirectMessage.objects.create(
            conversation=conversation,
            sender=self.user1,
            content=text_content
        )
        
        # 메시지 생성 확인
        self.assertIsNotNone(message.id)
        self.assertEqual(message.content["type"], "text")
        self.assertEqual(message.content["text"], "Hello, this is a test message")
        
        # 대화방 최신 메시지 업데이트
        conversation.latest_message = message
        conversation.save()
        
        # 최신 메시지 확인
        updated_conversation = DirectMessageConversation.objects.get(id=conversation.id)
        self.assertEqual(updated_conversation.latest_message_id, message.id)
    
    def test_message_deletion(self):
        """메시지 소프트 삭제 테스트"""
        conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)
        
        # 메시지 생성
        message = DirectMessage.objects.create(
            conversation=conversation,
            sender=self.user1,
            content={"type": "text", "text": "Test message for deletion"}
        )
        
        # 메시지 소프트 삭제
        message.deleted_at = timezone.now()
        message.save()
        
        # 소프트 삭제 확인
        self.assertIsNotNone(message.deleted_at)
        
        # 삭제된 메시지는 필터링되어야 함 (뷰에서 필터링하는 경우)
        active_messages = DirectMessage.objects.filter(
            conversation=conversation, 
            deleted_at__isnull=True
        )
        self.assertEqual(active_messages.count(), 0)
