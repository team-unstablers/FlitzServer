from unittest import mock
import json

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from messaging.models import (
    DirectMessageConversation, DirectMessageParticipant,
    DirectMessage, DirectMessageAttachment
)
from flitz.test_utils import create_test_user, create_test_user_with_session

class DirectMessageConversationViewSetTests(APITestCase):
    def setUp(self):
        self.user1, self.session1 = create_test_user_with_session(1)
        self.user2 = create_test_user(2)
        
        # API 클라이언트 설정 및 인증
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)
    
    def test_create_conversation(self):
        """대화방 생성 API 테스트"""
        url = reverse('DirectMessageConversation-list')
        data = {
            'initial_participants': [self.user1.id, self.user2.id]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        
        # 생성된 대화방 확인
        conversation_id = response.data['id']
        conversation = DirectMessageConversation.objects.get(id=conversation_id)
        
        # 참여자 확인
        participants = conversation.participants.all()
        self.assertEqual(participants.count(), 2)
        
    def test_list_conversations(self):
        """대화방 목록 조회 API 테스트"""
        # 대화방 생성
        conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)
        
        url = reverse('DirectMessageConversation-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_delete_conversation(self):
        """대화방 삭제 API 테스트"""
        # 대화방 생성
        conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)

        url = reverse('DirectMessageConversation-detail', args=[conversation.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # 소프트 삭제 확인
        conversation.refresh_from_db()
        self.assertIsNotNone(conversation.deleted_at)


class DirectMessageViewSetTests(APITestCase):
    def setUp(self):
        self.user1, self.session1 = create_test_user_with_session(1)
        self.user2 = create_test_user(2)
        
        # 대화방 생성
        self.conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)
        
        # API 클라이언트 설정 및 인증
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)
    
    @mock.patch('messaging.views.get_channel_layer')
    @mock.patch('messaging.views.async_to_sync')
    def test_create_message(self, mock_async_to_sync, mock_get_channel_layer):
        """메시지 생성 API 테스트 및 실시간 이벤트 발송 테스트"""
        # 채널 레이어 모킹
        mock_channel_layer = mock.MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        mock_group_send = mock.MagicMock()
        mock_async_to_sync.return_value = mock_group_send
        
        url = reverse('DirectMessage-list', args=[self.conversation.id])
        data = {
            'content': {
                'type': 'text',
                'text': 'Test message via API'
            }
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content']['text'], 'Test message via API')
        
        # 실시간 이벤트 발송 확인
        mock_group_send.assert_called_once()
        call_args = mock_group_send.call_args[0]
        
        # 대화방 ID 확인
        self.assertEqual(call_args[0], f'direct_message_{self.conversation.id}')
        
        # 이벤트 데이터 확인
        event_data = call_args[1]
        self.assertEqual(event_data['type'], 'dm_message')
        self.assertEqual(event_data['message']['sender'], str(self.user1.id))
        self.assertEqual(event_data['message']['content']['text'], 'Test message via API')
    
    def test_list_messages(self):
        """메시지 목록 조회 API 테스트"""
        # 메시지 생성
        message = DirectMessage.objects.create(
            conversation=self.conversation,
            sender=self.user1,
            content={'type': 'text', 'text': 'Test message'}
        )
        
        url = reverse('DirectMessage-list', args=[self.conversation.id])
        response = self.client.get(url)

        container = response.data
        results = container.get('results', [])
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]['content']['text'], 'Test message')
    
    @mock.patch('messaging.views.get_channel_layer')
    @mock.patch('messaging.views.async_to_sync')
    def test_mark_as_read(self, mock_async_to_sync, mock_get_channel_layer):
        """읽음 표시 API 테스트 및 실시간 이벤트 발송 테스트"""
        # 채널 레이어 모킹
        mock_channel_layer = mock.MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        mock_group_send = mock.MagicMock()
        mock_async_to_sync.return_value = mock_group_send
        
        url = reverse('DirectMessage-mark-as-read', args=[self.conversation.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 읽음 상태 업데이트 확인
        participant = DirectMessageParticipant.objects.get(
            conversation=self.conversation,
            user=self.user1
        )
        self.assertIsNotNone(participant.read_at)
        
        # 실시간 이벤트 발송 확인
        mock_group_send.assert_called_once()
        call_args = mock_group_send.call_args[0]
        
        # 이벤트 데이터 확인
        event_data = call_args[1]
        self.assertEqual(event_data['type'], 'dm_read_event')
        self.assertEqual(event_data['user_id'], str(self.user1.id))
    
    def test_delete_message(self):
        """메시지 삭제 API 테스트"""
        # 메시지 생성
        message = DirectMessage.objects.create(
            conversation=self.conversation,
            sender=self.user1,
            content={'type': 'text', 'text': 'Test message for deletion'}
        )
        
        url = reverse('DirectMessage-detail', args=[self.conversation.id, message.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # 소프트 삭제 확인
        message.refresh_from_db()
        self.assertIsNotNone(message.deleted_at)


class DirectMessageAttachmentViewSetTests(APITestCase):
    def setUp(self):
        self.user1, self.session1 = create_test_user_with_session(1)
        self.user2 = create_test_user(2)
        
        # 대화방 생성
        self.conversation = DirectMessageConversation.create_conversation(self.user1, self.user2)
        
        # API 클라이언트 설정 및 인증
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)
    
    @mock.patch('messaging.views.generate_thumbnail')
    @mock.patch('messaging.views.get_channel_layer')
    @mock.patch('messaging.views.async_to_sync')
    def test_upload_attachment(self, mock_async_to_sync, mock_get_channel_layer, 
                               mock_generate_thumbnail):
        """첨부파일 업로드 API 테스트 및 실시간 이벤트 발송 테스트"""
        # 채널 레이어 모킹
        mock_channel_layer = mock.MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        mock_group_send = mock.MagicMock()
        mock_async_to_sync.return_value = mock_group_send
        
        # 썸네일 생성 모킹 - 실제 파일 객체 반환
        from io import BytesIO
        from django.core.files.base import ContentFile
        thumbnail_content = BytesIO(b'fake thumbnail content')
        mock_generate_thumbnail.return_value = ContentFile(thumbnail_content.getvalue(), name='thumbnail.jpg')
        
        # 테스트 이미지 파일 생성
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_image = SimpleUploadedFile(
            name='test_image.jpg',
            content=b'fake image content',
            content_type='image/jpeg'
        )
        
        url = reverse('DirectMessageAttachments-list', args=[self.conversation.id])
        data = {'file': test_image}
        
        response = self.client.post(url, data, format='multipart')
        
        # 상태 코드 확인
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 첨부파일 메시지 이벤트 발송 확인
        mock_group_send.assert_called_once()
        call_args = mock_group_send.call_args[0]
        
        # 이벤트 데이터 확인
        event_data = call_args[1]
        self.assertEqual(event_data['type'], 'dm_message')
        
        # 썸네일 생성 함수 호출 확인
        mock_generate_thumbnail.assert_called_once()
