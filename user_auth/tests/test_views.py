import json
import jwt

from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.http.request import HttpRequest
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from rest_framework.test import APITestCase

from user_auth.models import UserSession

User = get_user_model()

class RequestTokenTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword'
        )
        self.payload = {
            'username': 'testuser',
            'password': 'testpassword',
            'device_info': 'test_device',
            'turnstile_token': 'test_turnstile_token'
        }

    @patch('user_auth.views.validate_turnstile')
    def test_request_token_success(self, mock_validate_turnstile):
        """토큰 발급 성공 테스트"""
        mock_validate_turnstile.return_value = {'success': True, 'action': 'request_token'}

        response = self.client.post(
            '/auth/token',  # 실제 URL 경로에 맞게 수정
            data=json.dumps(self.payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = json.loads(response.content)
        self.assertIn('token', response_data)
        
        # 토큰 검증
        token = response_data['token']
        decoded_token = jwt.decode(token, key=settings.SECRET_KEY, algorithms=['HS256'])
        
        # 세션 ID가 토큰에 포함되어 있는지 확인
        self.assertIn('sub', decoded_token)
        
        # 세션이 데이터베이스에 생성되었는지 확인
        session = UserSession.objects.filter(id=decoded_token['sub']).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.description, 'test_device')

    @patch('user_auth.views.validate_turnstile')
    def test_request_token_invalid_credentials(self, mock_validate_turnstile):
        """잘못된 자격 증명으로 토큰 발급 시도 테스트"""
        mock_validate_turnstile.return_value = {'success': True, 'action': 'request_token'}

        invalid_payload = self.payload.copy()
        invalid_payload['password'] = 'wrongpassword'

        response = self.client.post(
            '/auth/token',  # 실제 URL 경로에 맞게 수정
            data=json.dumps(invalid_payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401) 

    @patch('user_auth.views.validate_turnstile')
    def test_request_token_user_not_found(self, mock_validate_turnstile):
        """존재하지 않는 사용자로 토큰 발급 시도 테스트"""
        mock_validate_turnstile.return_value = {'success': True, 'action': 'request_token'}

        nonexistent_payload = self.payload.copy()
        nonexistent_payload['username'] = 'nonexistentuser'

        response = self.client.post(
            '/auth/token',  # 실제 URL 경로에 맞게 수정
            data=json.dumps(nonexistent_payload),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 401)

    def test_request_token_invalid_method(self):
        """GET 메서드로 토큰 발급 시도 테스트"""
        response = self.client.get('/auth/token')  # 실제 URL 경로에 맞게 수정
        
        self.assertEqual(response.status_code, 405)  # UnsupportedOperationException

    def test_request_token_without_device_info(self):
        """device_info가 없는 요청으로 토큰 발급 테스트 - 이제는 실패해야 함"""
        minimal_payload = {
            'username': 'testuser',
            'password': 'testpassword',
            'turnstile_token': 'test_turnstile_token'
        }

        response = self.client.post(
            '/auth/token',  # 실제 URL 경로에 맞게 수정
            data=json.dumps(minimal_payload),
            content_type='application/json'
        )

        # device_info가 필수 필드이므로 400 에러 반환
        self.assertEqual(response.status_code, 400)
