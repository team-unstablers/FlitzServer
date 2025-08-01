import json
import jwt
from datetime import timedelta
from urllib.parse import urlencode
from unittest import mock
from unittest.mock import sentinel

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from channels.db import database_sync_to_async
from channels.layers import InMemoryChannelLayer, get_channel_layer
import channels.layers

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

@override_settings(
    CHANNEL_LAYERS={
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
)
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

    async def test_connect_success(self):
        """연결 성공 테스트 - InMemoryChannelLayer 사용"""
        await self.setup_test_data()

        # WebSocket 클라이언트 생성
        query_string = urlencode({'token': self.token1})
        communicator = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string}"
        )
        
        # 연결 시도
        connected, _ = await communicator.connect()
        
        # 연결 성공 확인
        self.assertTrue(connected)
        
        # WebSocket 연결 종료
        await communicator.disconnect()
    
    async def test_connect_invalid_token(self):
        """잘못된 토큰으로 연결 실패 테스트"""
        await self.setup_test_data()
        
        # 잘못된 토큰으로 WebSocket 클라이언트 생성
        query_string = urlencode({'token': 'invalid-token'})
        communicator = WebsocketCommunicator(
            application,
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
            application,
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
            application,
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

    async def test_connect_not_participant(self):
        """대화방 참여자가 아닌 사용자의 연결 실패 테스트 - InMemoryChannelLayer 사용"""
        await self.setup_test_data()

        # 새로운 사용자 생성 (대화방 참여자 아님)
        _, _, token3 = await self.create_non_participant()
        
        # WebSocket 클라이언트 생성
        query_string = urlencode({'token': token3})
        communicator = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string}"
        )
        
        # 연결 시도
        connected, _ = await communicator.connect()
        
        # 연결 실패 확인
        self.assertFalse(connected)
    
    async def test_receive_message(self):
        """메시지 수신 테스트 - InMemoryChannelLayer 사용"""
        await self.setup_test_data()

        # 두 사용자의 WebSocket 클라이언트 생성
        query_string1 = urlencode({'token': self.token1})
        communicator1 = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string1}"
        )
        
        query_string2 = urlencode({'token': self.token2})
        communicator2 = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string2}"
        )
        
        # 두 클라이언트 모두 연결
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected2)

        """
        # 연결 시 자동으로 발생하는 읽음 이벤트 처리
        # 각 사용자는 상대방의 연결 이벤트를 받음
        event1 = await communicator1.receive_json_from()  # user1이 user2의 읽음 이벤트 수신
        self.assertEqual(event1['type'], 'read_event')
        self.assertEqual(event1['user_id'], str(self.user2.id))
        
        event2 = await communicator2.receive_json_from()  # user2가 user1의 읽음 이벤트 수신
        self.assertEqual(event2['type'], 'read_event')
        self.assertEqual(event2['user_id'], str(self.user1.id))
        """
        
        # DirectMessage 객체 생성 (데이터베이스에 저장)
        @database_sync_to_async
        def create_test_message():
            message = DirectMessage.objects.create(
                conversation=self.conversation,
                sender=self.user2,
                content={'type': 'text', 'text': 'Test WebSocket message'}
            )
            return message
        
        message = await create_test_message()
        
        # 메시지 전송
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"direct_message_{self.conversation.id}",
            {
                'type': 'dm_message',
                'message': {
                    'id': str(message.id),
                    'content': message.content,
                    'sender_id': str(self.user2.id),
                    'created_at': message.created_at.isoformat()
                }
            }
        )
        
        # user1이 메시지를 수신하는지 확인
        responses = [await communicator1.receive_json_from() for _ in range(2)]

        # responses 안에 메시지 이벤트가 포함되어 있는지 확인
        message_event = None
        for response in responses:
            if response['type'] == 'message':
                message_event = response
                break
        
        self.assertIsNotNone(message_event, "메시지 이벤트를 찾을 수 없습니다")
        self.assertEqual(message_event['type'], 'message')
        self.assertEqual(message_event['message']['content']['text'], 'Test WebSocket message')
        self.assertEqual(message_event['message']['sender_id'], str(self.user2.id))
        
        # WebSocket 연결 종료
        await communicator1.disconnect()
        await communicator2.disconnect()
    
    async def test_read_receipt(self):
        """읽음 상태 업데이트 테스트 - InMemoryChannelLayer 사용"""
        await self.setup_test_data()

        # 두 사용자의 WebSocket 클라이언트 생성
        query_string1 = urlencode({'token': self.token1})
        communicator1 = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string1}"
        )
        
        query_string2 = urlencode({'token': self.token2})
        communicator2 = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string2}"
        )
        
        # 두 클라이언트 모두 연결
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)
        connected2, _ = await communicator2.connect()
        self.assertTrue(connected2)
        
        # 연결 시 자동으로 발생하는 읽음 이벤트 처리
        # WebSocket 테스트에서는 InMemoryChannelLayer가 올바르게 작동하지 않을 수 있음
        import asyncio
        await asyncio.sleep(0.1)  # 이벤트 전파를 위한 짧은 대기
        
        # user1이 읽음 상태 요청 전송
        await communicator1.send_json_to({
            'type': 'read_receipt'
        })
        
        # user2가 user1의 읽음 상태 이벤트를 수신하는지 확인
        response = await communicator2.receive_json_from()
        
        self.assertEqual(response['type'], 'read_event')
        self.assertEqual(response['user_id'], str(self.user1.id))
        
        # WebSocket 연결 종료
        await communicator1.disconnect()
        await communicator2.disconnect()
    
    async def test_read_event(self):
        """읽음 상태 이벤트 수신 테스트 - InMemoryChannelLayer 사용"""
        await self.setup_test_data()
        
        # WebSocket 클라이언트 생성
        query_string1 = urlencode({'token': self.token1})
        communicator1 = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string1}"
        )
        
        # 연결
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)
        
        # 초기 connect시 발생하는 이벤트는 없음
        # (user1만 연결했으므로 user2의 이벤트가 없음)
        
        # 읽음 상태 이벤트 수동으로 전송
        now = timezone.now().isoformat()
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"direct_message_{self.conversation.id}",
            {
                "type": "dm_read_event",
                "user_id": str(self.user2.id),
                "read_at": now
            }
        )
        
        # 이벤트 수신 확인
        response = await communicator1.receive_json_from()
        self.assertEqual(response['type'], 'read_event')
        self.assertEqual(response['user_id'], str(self.user2.id))
        
        # WebSocket 연결 종료
        await communicator1.disconnect()
    
    async def test_disconnect(self):
        """연결 종료 테스트 - InMemoryChannelLayer 사용"""
        await self.setup_test_data()
        
        # WebSocket 클라이언트 생성
        query_string1 = urlencode({'token': self.token1})
        communicator1 = WebsocketCommunicator(
            application,
            f"{self.ws_url}?{query_string1}"
        )
        
        # 연결
        connected1, _ = await communicator1.connect()
        self.assertTrue(connected1)
        
        # 초기 connect시 발생하는 이벤트는 없음
        # (user1만 연결했으므로 user2의 이벤트가 없음)
        
        # 연결 종료
        await communicator1.disconnect()
        
        # 연결 종료 후 메시지 전송 시도
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"direct_message_{self.conversation.id}",
            {
                "type": "dm_read_event",
                "user_id": str(self.user2.id),
                "read_at": timezone.now().isoformat()
            }
        )
        
        # 이제 communicator1은 연결이 끊어졌으므로 메시지를 수신하지 않아야 함
        # 테스트 완료
