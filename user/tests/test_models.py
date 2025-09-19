from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest import mock, skip
from unittest.mock import patch, MagicMock
import unittest

from user.models import UserLike, UserMatch, Notification, UserIdentity, UserGenderBit
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

    @patch('user.tasks.send_push_message_ex.delay_on_commit')
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


class UserIdentityTests(TestCase):
    def setUp(self):
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2)
        self.user3 = create_test_user(3)
        self.user4 = create_test_user(4)
        
    def test_identity_creation(self):
        """UserIdentity 생성 테스트"""
        identity = UserIdentity.objects.create(
            user=self.user1,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN
        )
        
        self.assertEqual(identity.user, self.user1)
        self.assertEqual(identity.gender, UserGenderBit.MAN)
        self.assertEqual(identity.preferred_genders, UserGenderBit.MAN)
        self.assertFalse(identity.is_trans)
        self.assertFalse(identity.display_trans_to_others)
        self.assertFalse(identity.welcomes_trans)
        self.assertFalse(identity.trans_prefers_safe_match)
    
    def test_is_acceptable_basic_gender_preference(self):
        """기본 성별 선호도 매칭 테스트"""
        # user1: 남성, 남성 선호
        identity1 = UserIdentity.objects.create(
            user=self.user1,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN
        )
        
        # user2: 남성
        identity2 = UserIdentity.objects.create(
            user=self.user2,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN
        )
        
        # user3: 여성
        identity3 = UserIdentity.objects.create(
            user=self.user3,
            gender=UserGenderBit.WOMAN,
            preferred_genders=UserGenderBit.MAN
        )
        
        # user1은 남성을 선호하므로 user2(남성)는 OK, user3(여성)는 NO
        self.assertTrue(identity1.is_acceptable(identity2))
        self.assertFalse(identity1.is_acceptable(identity3))
    
    def test_is_acceptable_multiple_gender_preference(self):
        """다중 성별 선호도 매칭 테스트 (비트마스크)"""
        # user1: 남성과 논바이너리 선호
        identity1 = UserIdentity.objects.create(
            user=self.user1,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN | UserGenderBit.NON_BINARY
        )
        
        # user2: 남성
        identity2 = UserIdentity.objects.create(
            user=self.user2,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN
        )
        
        # user3: 논바이너리
        identity3 = UserIdentity.objects.create(
            user=self.user3,
            gender=UserGenderBit.NON_BINARY,
            preferred_genders=UserGenderBit.MAN
        )
        
        # user4: 여성
        identity4 = UserIdentity.objects.create(
            user=self.user4,
            gender=UserGenderBit.WOMAN,
            preferred_genders=UserGenderBit.MAN
        )
        
        # user1은 남성과 논바이너리를 선호
        self.assertTrue(identity1.is_acceptable(identity2))  # 남성 OK
        self.assertTrue(identity1.is_acceptable(identity3))  # 논바이너리 OK
        self.assertFalse(identity1.is_acceptable(identity4))  # 여성 NO
    
    def test_is_acceptable_trans_safe_match_required(self):
        """트랜스젠더 안전 매칭 테스트 - 안전 매칭 필요한 경우"""
        # user1: 트랜스젠더, 안전 매칭 원함
        identity1 = UserIdentity.objects.create(
            user=self.user1,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            is_trans=True,
            trans_prefers_safe_match=True
        )
        
        # user2: 일반 사용자, 트랜스 환영
        identity2 = UserIdentity.objects.create(
            user=self.user2,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            welcomes_trans=True
        )
        
        # user3: 일반 사용자, 트랜스 환영 안 함
        identity3 = UserIdentity.objects.create(
            user=self.user3,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            welcomes_trans=False
        )
        
        # user4: 트랜스젠더
        identity4 = UserIdentity.objects.create(
            user=self.user4,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            is_trans=True
        )
        
        # 안전 매칭을 원하는 트랜스젠더는 트랜스 환영하는 사람이나 트랜스젠더와만 매칭
        self.assertTrue(identity1.is_acceptable(identity2))  # welcomes_trans=True
        self.assertFalse(identity1.is_acceptable(identity3))  # welcomes_trans=False
        self.assertTrue(identity1.is_acceptable(identity4))  # is_trans=True
    
    def test_is_acceptable_trans_no_safe_match_required(self):
        """트랜스젠더 안전 매칭 테스트 - 안전 매칭 필요 없는 경우"""
        # user1: 트랜스젠더, 안전 매칭 원하지 않음
        identity1 = UserIdentity.objects.create(
            user=self.user1,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            is_trans=True,
            trans_prefers_safe_match=False
        )
        
        # user2: 일반 사용자, 트랜스 환영 안 함
        identity2 = UserIdentity.objects.create(
            user=self.user2,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            welcomes_trans=False
        )
        
        # 안전 매칭을 원하지 않는 트랜스젠더는 누구와도 매칭 가능 (성별 선호만 맞으면)
        self.assertTrue(identity1.is_acceptable(identity2))
    
    def test_is_acceptable_mutual_acceptance(self):
        """양방향 수용 가능성 테스트"""
        # user1: 남성, 남성 선호
        identity1 = UserIdentity.objects.create(
            user=self.user1,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN
        )
        
        # user2: 남성, 여성 선호
        identity2 = UserIdentity.objects.create(
            user=self.user2,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.WOMAN
        )
        
        # user1은 user2(남성)를 받아들이지만, user2는 user1(남성)을 받아들이지 않음
        self.assertTrue(identity1.is_acceptable(identity2))
        self.assertFalse(identity2.is_acceptable(identity1))
    
    def test_is_acceptable_with_unset_gender(self):
        """성별 미설정 사용자 테스트"""
        # user1: 남성, 모든 성별 선호
        identity1 = UserIdentity.objects.create(
            user=self.user1,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.ALL()
        )
        
        # user2: 성별 미설정
        identity2 = UserIdentity.objects.create(
            user=self.user2,
            gender=UserGenderBit.UNSET,
            preferred_genders=UserGenderBit.MAN
        )
        
        # UNSET(0)은 어떤 비트마스크와도 매칭되지 않음
        self.assertFalse(identity1.is_acceptable(identity2))
