from typing import Optional, TypedDict, Literal
import json
from urllib.parse import parse_qsl
from datetime import datetime

import jwt
from django.conf import settings

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

from messaging.models import DirectMessageConversation, DirectMessage, DirectMessageParticipant
from user_auth.models import UserSession
from user.models import User
from django.utils import timezone

class ReadEvent(TypedDict):
    type: Literal['read_event']
    user_id: str
    read_at: str

class Message(TypedDict):
    type: Literal['message']
    message: dict

class DirectMessageConsumer(AsyncWebsocketConsumer):
    user_id: str
    conversation_id: str

    @staticmethod
    def extract_conversation_id(scope) -> Optional[str]:
        return scope['url_route']['kwargs']['conversation_id']

    @staticmethod
    def extract_token(query_string: str) -> Optional[str]:
        query = dict(parse_qsl(query_string.decode()))
        return query.get('token')

    @property
    def group_name(self) -> str:
        return f'direct_message_{self.conversation_id}'

    @database_sync_to_async
    def get_conversation(self):
        try:
            return DirectMessageConversation.objects.get(id=self.conversation_id)
        except DirectMessageConversation.DoesNotExist:
            return None

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            # JWT 토큰 디코딩
            jwt_payload = jwt.decode(token, key=settings.SECRET_KEY, algorithms=['HS256'])
            session_id = jwt_payload['sub']
            
            # 세션 ID로 세션 조회
            session = UserSession.objects.select_related('user').filter(id=session_id).first()
            
            # 세션이 없거나 무효화되었거나 만료되었다면 None 반환
            if session is None or session.invalidated_at is not None:
                return None
                
            if session.expires_at is not None and session.expires_at < datetime.now(tz=timezone.utc):
                return None
                
            return session.user
            
        except (jwt.InvalidTokenError, Exception):
            return None

    @database_sync_to_async
    def check_participant(self, conversation, user_id):
        return DirectMessageParticipant.objects.filter(
            conversation=conversation,
            user_id=user_id,
            deleted_at__isnull=True
        ).exists()

    @database_sync_to_async
    def update_read_at(self, user_id):
        participant = DirectMessageParticipant.objects.get(
            conversation_id=self.conversation_id,
            user_id=user_id
        )
        participant.read_at = timezone.now()
        participant.save()
        return participant.read_at

    async def connect(self):
        # 대화방 ID 추출
        self.conversation_id = self.extract_conversation_id(self.scope)
        if not self.conversation_id:
            await self.close()
            return
        
        # 인증 토큰 추출
        token = self.extract_token(self.scope["query_string"])
        if not token:
            await self.close()
            return
        
        # 토큰으로부터 사용자 정보 가져오기
        user = await self.get_user_from_token(token)
        if not user:
            await self.close()
            return
        
        self.user_id = str(user.id)
        
        # 대화방 존재 여부 확인
        conversation = await self.get_conversation()
        if not conversation:
            await self.close()
            return
        
        # 사용자가 대화방에 참여하고 있는지 확인
        participant_exists = await self.check_participant(conversation, self.user_id)
        if not participant_exists:
            await self.close()
            return
        
        # WebSocket 그룹에 추가
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # 연결 수락
        await self.accept()
        
        # 읽음 상태 업데이트 및 이벤트 발송
        read_at = await self.update_read_at(self.user_id)
        
        # 다른 참여자들에게 읽음 상태 알림
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "dm_read_event",
                "user_id": self.user_id,
                "read_at": read_at.isoformat()
            }
        )

    async def disconnect(self, close_code):
        # WebSocket 그룹에서 제거
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        # 클라이언트로부터 메시지 수신 시 처리 (향후 확장성 대비)
        try:
            data = json.loads(text_data)
            if data.get("type") == "read_receipt":
                # 읽음 상태 업데이트 요청을 받으면 처리
                read_at = await self.update_read_at(self.user_id)
                
                # 다른 참여자들에게 읽음 상태 알림
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "dm_read_event",
                        "user_id": self.user_id,
                        "read_at": read_at.isoformat()
                    }
                )
        except json.JSONDecodeError:
            pass

    async def dm_message(self, event):
        # 새 메시지를 클라이언트에게 전송
        message = event["message"]
        
        # 클라이언트에게 메시지 전송
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": message
        }))
        
        # 내가 메시지를 보낸 경우가 아니라면, 읽음 상태 자동 업데이트
        if str(message.get("sender_id")) != self.user_id:
            read_at = await self.update_read_at(self.user_id)
            
            # 다른 참여자들에게 읽음 상태 알림
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "dm_read_event",
                    "user_id": self.user_id,
                    "read_at": read_at.isoformat()
                }
            )

    async def dm_read_event(self, event):
        # 읽음 상태 업데이트 이벤트 처리
        user_id = event["user_id"]
        read_at = event["read_at"]
        
        # 자신이 발생시킨 읽음 이벤트는 자신에게 다시 보내지 않음
        if user_id == self.user_id:
            return
        
        # 클라이언트에게 읽음 상태 전송
        await self.send(text_data=json.dumps({
            "type": "read_event",
            "user_id": user_id,
            "read_at": read_at
        }))
