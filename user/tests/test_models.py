from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest import mock, skip
from unittest.mock import patch, MagicMock
import unittest

from user.models import UserLike, UserMatch, Notification
from flitz.test_utils import create_test_user

User = get_user_model()

class UserModelTests(TestCase):
    def setUp(self):
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2)

    def test_user_creation(self):
        """사용자 생성이 올바르게 이루어지는지 테스트"""
        self.assertEqual(self.user1.username, 'testuser1')
        self.assertEqual(self.user1.display_name, 'Test User 1')
        self.assertTrue(self.user1.check_password('testpassword1'))
        self.assertEqual(self.user1.free_coins, 0)
        self.assertEqual(self.user1.paid_coins, 0)
        self.assertIsNone(self.user1.disabled_at)
        self.assertIsNone(self.user1.fully_deleted_at)
        self.assertIsNotNone(self.user1.created_at)
        self.assertIsNotNone(self.user1.updated_at)


class UserLikeTests(TestCase):
    def setUp(self):
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2)

    def test_user_like_creation(self):
        """사용자 좋아요 관계 생성 테스트"""
        like = UserLike.objects.create(user=self.user1, liked_by=self.user2)
        
        self.assertEqual(like.user, self.user1)
        self.assertEqual(like.liked_by, self.user2)
        self.assertIsNotNone(like.id)
        self.assertIsNotNone(like.created_at)

    @patch('user.models.UserMatch.create_match')
    def test_try_match_user_with_no_existing_likes(self, mock_create_match):
        """양쪽 좋아요가 없을 때 매칭 시도 테스트"""
        UserLike.try_match_user(self.user1, self.user2)
        
        # 매칭이 생성되지 않아야 함
        mock_create_match.assert_not_called()

    @patch('user.models.UserMatch.create_match')
    def test_try_match_user_with_one_like(self, mock_create_match):
        """한쪽만 좋아요했을 때 매칭 시도 테스트"""
        # user1이 user2를 좋아요
        UserLike.objects.create(user=self.user2, liked_by=self.user1)
        
        UserLike.try_match_user(self.user1, self.user2)
        
        # 매칭이 생성되지 않아야 함
        mock_create_match.assert_not_called()

    @patch('user.models.UserMatch.create_match')
    def test_try_match_user_with_both_likes(self, mock_create_match):
        """양쪽 모두 좋아요했을 때 매칭 시도 테스트"""
        # 양방향 좋아요 생성
        UserLike.objects.create(user=self.user1, liked_by=self.user2)
        UserLike.objects.create(user=self.user2, liked_by=self.user1)
        
        UserLike.try_match_user(self.user1, self.user2)
        
        # UserMatch.create_match가 호출되어야 함
        mock_create_match.assert_called_once()
        args, _ = mock_create_match.call_args
        self.assertIn(self.user1, args)
        self.assertIn(self.user2, args)


class UserMatchTests(TestCase):
    def setUp(self):
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2)

    @patch('user.tasks.send_push_message.delay_on_commit')
    @patch('messaging.models.DirectMessageConversation.create_conversation')
    def test_create_match(self, mock_create_conversation, mock_send_push):
        """매칭 생성 테스트"""
        # Mock 설정
        mock_conversation = MagicMock()
        mock_conversation.id = 'mock-conversation-id'
        mock_create_conversation.return_value = mock_conversation
        
        # Create a match
        UserMatch.create_match(self.user1, self.user2)
        
        # Check if match was created
        match = UserMatch.objects.filter(user_a=self.user1, user_b=self.user2).first()
        self.assertIsNotNone(match)
        
        # Check if conversation was created
        mock_create_conversation.assert_called_once_with(self.user1, self.user2)
        
        # Check if push notifications were sent
        self.assertEqual(mock_send_push.call_count, 2)


class NotificationTests(TestCase):
    def setUp(self):
        self.user = create_test_user(1)

    def test_notification_creation(self):
        """알림 생성 테스트"""
        notification = Notification.objects.create(
            user=self.user,
            type='test_notification',
            content={"message": "Test notification message"}
        )
        
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.type, 'test_notification')
        self.assertEqual(notification.content, {'message': 'Test notification message'})
        self.assertIsNone(notification.read_at)
        self.assertIsNone(notification.deleted_at)
        self.assertIsNotNone(notification.created_at)
