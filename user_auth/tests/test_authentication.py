import jwt
from django.test import TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from rest_framework.test import APIRequestFactory
from datetime import datetime, timedelta, timezone

from user_auth.models import UserSession
from user_auth.authentication import UserSessionAuthentication
from flitz.test_utils import create_test_user, create_test_session, create_test_user_with_session

User = get_user_model()

class UserSessionAuthenticationTests(TestCase):
    def setUp(self):
        # 사용자와 세션을 함께 생성
        self.user, self.session = create_test_user_with_session()
        self.auth = UserSessionAuthentication()
        self.factory = APIRequestFactory()
        
        # 유효한 JWT 토큰 생성
        self.valid_payload = {
            'sub': str(self.session.id),
            'iat': datetime.now(tz=timezone.utc),
            'exp': datetime.now(tz=timezone.utc) + timedelta(days=30),
            'x-flitz-options': '--with-love',
        }
        self.valid_token = jwt.encode(
            self.valid_payload,
            key=settings.SECRET_KEY,
            algorithm='HS256'
        )

    def test_no_auth_header(self):
        """인증 헤더가 없는 경우 테스트"""
        request = self.factory.get('/')
        result = self.auth.authenticate(request)
        
        self.assertIsNone(result)

    def test_invalid_auth_header_format(self):
        """잘못된 형식의 인증 헤더 테스트"""
        request = self.factory.get('/', HTTP_AUTHORIZATION='Token ' + self.valid_token)
        result = self.auth.authenticate(request)
        
        self.assertIsNone(result)

    def test_valid_token_authentication(self):
        """유효한 토큰으로 인증 테스트"""
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer ' + self.valid_token)
        result = self.auth.authenticate(request)
        
        self.assertIsNotNone(result)
        user, session = result
        self.assertEqual(user, self.user)
        self.assertEqual(session, self.session)

    def test_invalid_token(self):
        """유효하지 않은 토큰으로 인증 테스트"""
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer invalidtoken')
        result = self.auth.authenticate(request)
        
        self.assertIsNone(result)

    def test_expired_token(self):
        """만료된 토큰으로 인증 테스트"""
        expired_payload = self.valid_payload.copy()
        expired_payload['exp'] = datetime.now(tz=timezone.utc) - timedelta(days=1)
        
        expired_token = jwt.encode(
            expired_payload,
            key=settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer ' + expired_token)
        result = self.auth.authenticate(request)
        
        self.assertIsNone(result)

    def test_invalidated_session(self):
        """무효화된 세션으로 인증 테스트"""
        # 세션 무효화
        self.session.invalidated_at = datetime.now(tz=timezone.utc)
        self.session.save()
        
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer ' + self.valid_token)
        result = self.auth.authenticate(request)
        
        self.assertIsNone(result)

    def test_expired_session(self):
        """만료된 세션으로 인증 테스트"""
        # 만료 시간 설정
        self.session.expires_at = datetime.now(tz=timezone.utc) - timedelta(days=1)
        self.session.save()
        
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer ' + self.valid_token)
        result = self.auth.authenticate(request)
        
        self.assertIsNone(result)

    def test_nonexistent_session(self):
        """존재하지 않는 세션 ID로 인증 테스트"""
        nonexistent_payload = self.valid_payload.copy()
        nonexistent_payload['sub'] = '00000000-0000-0000-0000-000000000000'  # 유효한 UUID 형식
        
        nonexistent_token = jwt.encode(
            nonexistent_payload,
            key=settings.SECRET_KEY,
            algorithm='HS256'
        )
        
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer ' + nonexistent_token)
        result = self.auth.authenticate(request)
        
        self.assertIsNone(result)

    def test_valid_session_with_future_expiry(self):
        """미래 만료 시간을 가진 유효한 세션 테스트"""
        # 만료 시간 설정
        self.session.expires_at = datetime.now(tz=timezone.utc) + timedelta(days=7)
        self.session.save()
        
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer ' + self.valid_token)
        result = self.auth.authenticate(request)
        
        self.assertIsNotNone(result)
        user, session = result
        self.assertEqual(user, self.user)
        self.assertEqual(session, self.session)
