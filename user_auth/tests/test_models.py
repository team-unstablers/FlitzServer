from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone

from user_auth.models import UserSession

User = get_user_model()

class UserSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword'
        )
        self.session = UserSession.objects.create(
            user=self.user,
            description='Test Session',
            initiated_from='127.0.0.1',
            apns_token='test_token'
        )

    def test_session_creation(self):
        """세션 생성 테스트"""
        self.assertEqual(self.session.user, self.user)
        self.assertEqual(self.session.description, 'Test Session')
        self.assertEqual(self.session.initiated_from, '127.0.0.1')
        self.assertEqual(self.session.apns_token, 'test_token')
        self.assertIsNone(self.session.expires_at)
        self.assertIsNone(self.session.invalidated_at)
        self.assertIsNotNone(self.session.created_at)
        self.assertIsNotNone(self.session.updated_at)

    def test_session_relation(self):
        """사용자-세션 관계 테스트"""
        self.assertIn(self.session, self.user.sessions.all())

    @patch('user_auth.models.APNS')
    def test_send_push_message(self, mock_apns):
        """푸시 메시지 발송 테스트"""
        # Mock setup
        mock_default = MagicMock()
        mock_apns.default.return_value = mock_default
        
        # Call method
        self.session.send_push_message('Test Title', 'Test Body', {'key': 'value'}, thread_id=None)
        
        # Check method calls
        mock_apns.default.assert_called_once()
        mock_default.send_notification.assert_called_once_with(
            'Test Title', 'Test Body', [self.session.apns_token], {'key': 'value'}, thread_id=None
        )

    def test_session_with_expiry(self):
        """만료 시간이 있는 세션 테스트"""
        expiry_time = datetime.now(tz=timezone.utc) + timedelta(days=7)
        session = UserSession.objects.create(
            user=self.user,
            description='Expiring Session',
            initiated_from='127.0.0.1',
            expires_at=expiry_time
        )
        
        self.assertEqual(session.expires_at, expiry_time)
        self.assertIsNone(session.invalidated_at)

    def test_session_invalidation(self):
        """세션 무효화 테스트"""
        invalidation_time = datetime.now(tz=timezone.utc)
        self.session.invalidated_at = invalidation_time
        self.session.save()
        
        # Reload from DB
        self.session.refresh_from_db()
        self.assertEqual(self.session.invalidated_at, invalidation_time)
