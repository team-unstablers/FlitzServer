from unittest.mock import patch

from django.test import TestCase, override_settings
from django.db import transaction

from safety.models import UserBlock, UserContactsTrigger
from safety.utils.phone_number import hash_phone_number, normalize_phone_number
from flitz.test_utils import create_test_user

# Test salt for phone number hashing
TEST_PHONE_HASH_SALT = "test_salt_for_unit_tests"


class UserBlockTests(TestCase):
    def setUp(self):
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2)

    def test_user_block_creation(self):
        """사용자 차단 관계 생성 테스트"""
        block = UserBlock.objects.create(user=self.user1, blocked_by=self.user2)

        self.assertEqual(block.user, self.user1)
        self.assertEqual(block.blocked_by, self.user2)
        self.assertIsNotNone(block.id)
        self.assertIsNotNone(block.created_at)
    
    def test_user_block_with_types_and_reasons(self):
        """다양한 차단 유형과 사유에 대한 테스트"""
        # BLOCK + BY_USER
        block1 = UserBlock.objects.create(
            user=self.user1, 
            blocked_by=self.user2, 
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        self.assertEqual(block1.type, UserBlock.Type.BLOCK)
        self.assertEqual(block1.reason, UserBlock.Reason.BY_USER)
        
        # LIMIT + BY_USER
        block2 = UserBlock.objects.create(
            user=self.user1, 
            blocked_by=self.user2, 
            type=UserBlock.Type.LIMIT,
            reason=UserBlock.Reason.BY_USER
        )
        self.assertEqual(block2.type, UserBlock.Type.LIMIT)
        self.assertEqual(block2.reason, UserBlock.Reason.BY_USER)
        
        # BLOCK + BY_TRIGGER
        block3 = UserBlock.objects.create(
            user=self.user1, 
            blocked_by=self.user2, 
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_TRIGGER
        )
        self.assertEqual(block3.type, UserBlock.Type.BLOCK)
        self.assertEqual(block3.reason, UserBlock.Reason.BY_TRIGGER)
    
    def test_user_block_defaults(self):
        """차단 유형과 사유의 기본값 테스트"""
        block = UserBlock.objects.create(user=self.user1, blocked_by=self.user2)
        
        self.assertEqual(block.type, UserBlock.Type.BLOCK)
        self.assertEqual(block.reason, UserBlock.Reason.BY_USER)


@override_settings(PHONE_NUMBER_HASH_SALT=TEST_PHONE_HASH_SALT)
class UserContactsTriggerTests(TestCase):
    def setUp(self):
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2, phone_number="+82-10-1234-5678")
        
        # Create expected hash for testing
        self.test_phone_number = "+82-10-1234-5678"
        self.expected_hash = hash_phone_number(normalize_phone_number(self.test_phone_number))
        
        # Verify the user2 has the same hash
        self.user2.phone_number_hashed = self.expected_hash
        self.user2.save()
    
    def test_user_contacts_trigger_creation(self):
        """연락처 트리거 생성 테스트"""
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=self.expected_hash
        )
        
        self.assertEqual(trigger.user, self.user1)
        self.assertEqual(trigger.phone_number_hashed, self.expected_hash)
        self.assertIsNone(trigger.related_object)
        self.assertIsNotNone(trigger.id)
        self.assertIsNotNone(trigger.created_at)
    
    def test_set_phone_number(self):
        """전화번호 설정 및 해싱 테스트"""
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed="placeholder"
        )
        
        trigger.set_phone_number(self.test_phone_number)
        self.assertEqual(trigger.phone_number_hashed, self.expected_hash)
        
        # Save and verify from DB
        trigger.save()
        refreshed_trigger = UserContactsTrigger.objects.get(id=trigger.id)
        self.assertEqual(refreshed_trigger.phone_number_hashed, self.expected_hash)
    
    def test_evaluate_with_matching_user(self):
        """evaluate 메서드 테스트 - 일치하는 사용자가 있는 경우"""
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=self.expected_hash
        )
        
        result = trigger.evaluate()
        self.assertEqual(result, self.user2)
    
    def test_evaluate_with_no_matching_user(self):
        """evaluate 메서드 테스트 - 일치하는 사용자가 없는 경우"""
        # Use a different phone number that won't match any user
        different_phone = "+82-10-9876-5432"
        different_hash = hash_phone_number(different_phone)
        
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=different_hash
        )
        
        result = trigger.evaluate()
        self.assertIsNone(result)
    
    def test_perform_block_with_matching_user(self):
        """perform_block 메서드 테스트 - 일치하는 사용자가 있는 경우"""
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=self.expected_hash
        )
        
        # Verify no blocks exist before perform_block
        self.assertEqual(UserBlock.objects.count(), 0)
        
        trigger.perform_block()
        
        # Verify a block was created
        self.assertEqual(UserBlock.objects.count(), 1)
        block = UserBlock.objects.first()
        
        # Verify block properties
        self.assertEqual(block.user, self.user2)
        self.assertEqual(block.blocked_by, self.user1)
        self.assertEqual(block.reason, UserBlock.Reason.BY_TRIGGER)
        
        # Verify trigger was updated with related_object
        trigger.refresh_from_db()
        self.assertEqual(trigger.related_object, block)
    
    def test_perform_block_with_no_matching_user(self):
        """perform_block 메서드 테스트 - 일치하는 사용자가 없는 경우"""
        # Use a different phone number that won't match any user
        different_phone = "+82-10-9876-5432"
        different_hash = hash_phone_number(different_phone)
        
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=different_hash
        )
        
        # Verify no blocks exist before perform_block
        self.assertEqual(UserBlock.objects.count(), 0)
        
        trigger.perform_block()
        
        # Verify no block was created
        self.assertEqual(UserBlock.objects.count(), 0)
        
        # Verify trigger was not updated
        trigger.refresh_from_db()
        self.assertIsNone(trigger.related_object)
    
    def test_transaction_in_perform_block(self):
        """perform_block 메서드의 트랜잭션 처리 테스트"""
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=self.expected_hash
        )
        
        # Mock the save method to raise an exception
        with patch.object(UserContactsTrigger, 'save') as mock_save:
            mock_save.side_effect = Exception("Test exception")
            
            # The transaction should roll back
            with self.assertRaises(Exception):
                trigger.perform_block()
            
            # Verify no block was created due to transaction rollback
            self.assertEqual(UserBlock.objects.count(), 0)
    
    def test_delete_trigger_deletes_related_block(self):
        """UserContactsTrigger 삭제 시 연결된 UserBlock도 함께 삭제되는지 테스트"""
        # 트리거 생성 및 차단 수행
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=self.expected_hash
        )
        trigger.perform_block()
        
        # 관련 객체 확인
        trigger.refresh_from_db()
        related_block_id = trigger.related_object.id
        self.assertIsNotNone(trigger.related_object)
        self.assertEqual(UserBlock.objects.count(), 1)
        
        # 트리거 삭제
        trigger.delete()
        
        # 연결된 UserBlock도 함께 삭제되었는지 확인
        self.assertEqual(UserBlock.objects.count(), 0)
        self.assertFalse(UserBlock.objects.filter(id=related_block_id).exists())
    
    def test_delete_block_does_not_delete_trigger(self):
        """UserBlock 삭제 시 연결된 UserContactsTrigger는 삭제되지 않는지 테스트"""
        # 트리거 생성 및 차단 수행
        trigger = UserContactsTrigger.objects.create(
            user=self.user1,
            phone_number_hashed=self.expected_hash
        )
        trigger.perform_block()
        
        # 관련 객체 확인
        trigger.refresh_from_db()
        related_block = trigger.related_object
        trigger_id = trigger.id
        self.assertIsNotNone(related_block)
        
        # UserBlock 삭제
        related_block.delete()
        
        # 트리거는 여전히 존재하는지 확인 (related_object만 NULL로 설정됨)
        self.assertTrue(UserContactsTrigger.objects.filter(id=trigger_id).exists())
        trigger.refresh_from_db()
        self.assertIsNone(trigger.related_object)
