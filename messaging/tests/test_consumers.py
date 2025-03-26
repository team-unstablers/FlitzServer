import json
from unittest.mock import sentinel

import jwt
from unittest import mock
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from channels.db import database_sync_to_async

from flitz.asgi import application
from flitz.test_utils import create_test_user, create_test_user_with_session
from messaging.models import DirectMessageConversation, DirectMessageParticipant, DirectMessage
from messaging.consumers import DirectMessageConsumer
from messaging.routing import websocket_urlpatterns
from user_auth.models import UserSession


def generate_test_token(session_id):
    """테스트용 JWT 토큰 생성"""
    payload = {
        'sub': str(session_id),
        'exp': timezone.now() + timedelta(days=1),
        'iat': timezone.now(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


class DirectMessageConsumerTests(TestCase):
    @database_sync_to_async
    def setup_test_data(self):
        """테스트 데이터 설정"""
        # 테스트 사용자 생성
        self.user1, self.session1 = create_test_user_with_session(1)
        self.user2, self.session2 = create_test_user_with_session(2)
        
        # 대화방 생성
        self.conversation = DirectMessageConversation.create_conversation(
            self.user1, self.user2
        )
        
        # 토큰 생성
        self.token1 = generate_test_token(self.session1.id)
        self.token2 = generate_test_token(self.session2.id)
        
        # 웹소켓 URL
        self.ws_url = f'/ws/direct-messages/{self.conversation.id}/'
    
    @mock.patch("messaging.consumers.DirectMessageConsumer.channel_layer", sentinel.attribute)
    async def test_connect_success(self, mock_channel_layer):
        """연결 성공 테스트"""
        await self.setup_test_data()
        
        # 채널 레이어 모킹
        mock_channel_layer.group_add = mock.AsyncMock()
        mock_channel_layer.group_send = mock.AsyncMock()

        # WebSocket 클라이언트 생성
        query_string = urlencode({'token': self.token1})
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"{self.ws_url}?{query_string}"
        )
        
        # 연결 시도
        connected, _ = await communicator.connect()
        
        # 연결 성공 확인
        self.assertTrue(connected)

        # 그룹 추가 및 읽음 상태 이벤트 발송 확인
        mock_channel_layer.group_add.assert_called_once()
        mock_channel_layer.group_send.assert_called_once()
        
        # WebSocket 연결 종료
        await communicator.disconnect()
    
    async def test_connect_invalid_token(self):
        """잘못된 토큰으로 연결 실패 테스트"""
        await self.setup_test_data()
        
        # 잘못된 토큰으로 WebSocket 클라이언트 생성
        query_string = urlencode({'token': 'invalid-token'})
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"{self.ws_url}?{query_string}"
        )
        
        # 연결 시도
        connected, _ = await communicator.connect()
        
        # 연결 실패 확인
        self.assertFalse(connected)
    
    async def test_connect_no_token(self):
        """토큰 없이 연결 실패 테스트"""
        await self.setup_test_data()
        
        # 토큰 없이 WebSocket 클라이언트 생성
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            self.ws_url
        )
        
        # 연결 시도
        connected, _ = await communicator.connect()
        
        # 연결 실패 확인
        self.assertFalse(connected)
    
    async def test_connect_non_existent_conversation(self):
        """존재하지 않는 대화방으로 연결 실패 테스트"""
        await self.setup_test_data()
        
        # 존재하지 않는 대화방 ID
        non_existent_id = '00000000-0000-0000-0000-000000000000'
        ws_url = f'/ws/direct-messages/{non_existent_id}/'
        
        # WebSocket 클라이언트 생성
        query_string = urlencode({'token': self.token1})
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"{ws_url}?{query_string}"
        )
        
        # 연결 시도
        connected, _ = await communicator.connect()
        
        # 연결 실패 확인
        self.assertFalse(connected)
    
    @database_sync_to_async
    def create_non_participant(self):
        """대화방에 참여하지 않는 사용자 생성"""
        user3, session3 = create_test_user_with_session(3)
        token3 = generate_test_token(session3.id)
        return user3, session3, token3

    @mock.patch("channels.layers.get_channel_layer")
    async def test_connect_not_participant(self, mock_get_channel_layer):
        """대화방 참여자가 아닌 사용자의 연결 실패 테스트"""
        await self.setup_test_data()
        
        # 새로운 사용자 생성 (대화방 참여자 아님)
        _, _, token3 = await self.create_non_participant()
        
        # WebSocket 클라이언트 생성
        query_string = urlencode({'token': token3})
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"{self.ws_url}?{query_string}"
        )
        
        # 연결 시도
        connected, _ = await communicator.connect()
        
        # 연결 실패 확인
        self.assertFalse(connected)
    
    @mock.patch("channels.layers.get_channel_layer")
    async def test_receive_message(self, mock_get_channel_layer):
        """메시지 수신 테스트"""
        await self.setup_test_data()
        
        # 채널 레이어 모킹
        mock_channel_layer = mock.AsyncMock()
        mock_channel_layer.group_add = mock.AsyncMock()
        mock_channel_layer.group_send = mock.AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        # WebSocket 클라이언트 생성
        query_string = urlencode({'token': self.token1})
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"{self.ws_url}?{query_string}"
        )
        
        # 연결
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        
        # 모의 메시지 이벤트 생성
        message_event = {
            'type': 'dm_message',
            'message': {
                'id': '123456',
                'content': {'type': 'text', 'text': 'Test WebSocket message'},
                'sender_id': str(self.user2.id),
                'created_at': timezone.now().isoformat()
            }
        }
        
        # consumer.dm_message 메서드 직접 호출 시뮬레이션
        consumer = DirectMessageConsumer()
        consumer.user_id = str(self.user1.id)
        consumer.send = mock.AsyncMock()
        consumer.channel_layer = mock_channel_layer
        
        await consumer.dm_message(message_event)
        
        # 메시지 전송 확인
        consumer.send.assert_called_once()
        call_args = consumer.send.call_args[1]
        sent_data = json.loads(call_args['text_data'])
        
        self.assertEqual(sent_data['type'], 'message')
        self.assertEqual(sent_data['message']['content']['text'], 'Test WebSocket message')
        
        # WebSocket 연결 종료
        await communicator.disconnect()
    
    @mock.patch("channels.layers.get_channel_layer")
    async def test_read_receipt(self, mock_get_channel_layer):
        """읽음 상태 업데이트 테스트"""
        await self.setup_test_data()
        
        # 채널 레이어 모킹
        mock_channel_layer = mock.AsyncMock()
        mock_channel_layer.group_add = mock.AsyncMock()
        mock_channel_layer.group_send = mock.AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        # WebSocket 클라이언트 생성
        query_string = urlencode({'token': self.token1})
        communicator = WebsocketCommunicator(
            URLRouter(websocket_urlpatterns),
            f"{self.ws_url}?{query_string}"
        )
        
        # 연결
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        
        # 읽음 상태 요청 전송
        await communicator.send_json_to({
            'type': 'read_receipt'
        })
        
        # 그룹 메시지 전송 확인 (첫 번째는 연결 시, 두 번째는 read_receipt 처리 시)
        self.assertEqual(mock_channel_layer.group_send.call_count, 2)
        
        # 두 번째 호출 데이터 확인
        call_args = mock_channel_layer.group_send.call_args[0]
        event_data = call_args[1]
        self.assertEqual(event_data['type'], 'dm_read_event')
        self.assertEqual(event_data['user_id'], str(self.user1.id))
        
        # WebSocket 연결 종료
        await communicator.disconnect()
    
    @mock.patch("channels.layers.get_channel_layer")
    async def test_read_event(self, mock_get_channel_layer):
        """읽음 상태 이벤트 수신 테스트"""
        await self.setup_test_data()
        
        # 채널 레이어 모킹
        mock_channel_layer = mock.AsyncMock()
        mock_channel_layer.group_add = mock.AsyncMock()
        mock_channel_layer.group_send = mock.AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        # consumer.dm_read_event 메서드 직접 호출 시뮬레이션
        consumer = DirectMessageConsumer()
        consumer.user_id = str(self.user1.id)
        consumer.send = mock.AsyncMock()
        consumer.channel_layer = mock_channel_layer
        
        # 읽음 상태 이벤트 생성
        read_event = {
            'type': 'dm_read_event',
            'user_id': str(self.user2.id),
            'read_at': timezone.now().isoformat()
        }
        
        # 읽음 상태 이벤트 처리
        await consumer.dm_read_event(read_event)
        
        # 메시지 전송 확인
        consumer.send.assert_called_once()
        call_args = consumer.send.call_args[1]
        sent_data = json.loads(call_args['text_data'])
        
        self.assertEqual(sent_data['type'], 'read_event')
        self.assertEqual(sent_data['user_id'], str(self.user2.id))
    
    @mock.patch("channels.layers.get_channel_layer")
    async def test_disconnect(self, mock_get_channel_layer):
        """연결 종료 테스트"""
        await self.setup_test_data()
        
        # 채널 레이어 모킹
        mock_channel_layer = mock.AsyncMock()
        mock_channel_layer.group_add = mock.AsyncMock()
        mock_channel_layer.group_discard = mock.AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        # DirectMessageConsumer 인스턴스 생성 및 설정
        consumer = DirectMessageConsumer()
        consumer.conversation_id = str(self.conversation.id)
        consumer.channel_layer = mock_channel_layer
        consumer.channel_name = "test_channel"
        
        # disconnect 메서드 직접 호출
        await consumer.disconnect(1000)
        
        # group_discard 호출 확인
        mock_channel_layer.group_discard.assert_called_once_with(
            f"direct_message_{self.conversation.id}",
            "test_channel"
        )
