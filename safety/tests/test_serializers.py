from django.test import TestCase
from rest_framework.renderers import JSONRenderer

from safety.models import UserBlock
from safety.serializers import UserBlockSerializer
from flitz.test_utils import create_test_user


class UserBlockSerializerTests(TestCase):
    def setUp(self):
        # 두 명의 테스트 사용자 생성
        self.user1 = create_test_user(1)
        self.user2 = create_test_user(2)
        
        # 차단 레코드 생성
        self.user_block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        
        self.trigger_block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.LIMIT,
            reason=UserBlock.Reason.BY_TRIGGER
        )
        
    def test_user_block_serializer_fields(self):
        """UserBlockSerializer가 올바른 필드만 포함하는지 테스트합니다."""
        serializer = UserBlockSerializer(self.user_block)
        data = serializer.data
        
        # 필수 필드가 포함되어 있는지 확인
        self.assertIn('id', data)
        self.assertIn('blocked_user', data)
        self.assertIn('created_at', data)
        
        # 'type', 'reason' 필드가 제외되어 있는지 확인 (사용자에게 표시되지 않아야 함)
        self.assertNotIn('type', data)
        self.assertNotIn('reason', data)

        
    def test_blocked_user_representation(self):
        """차단된 사용자 정보가 올바르게 표현되는지 테스트합니다."""
        serializer = UserBlockSerializer(self.user_block)
        data = serializer.data
        
        # blocked_user 필드 확인
        self.assertEqual(data['blocked_user']['id'], str(self.user2.id))
        self.assertEqual(data['blocked_user']['username'], self.user2.username)
        self.assertEqual(data['blocked_user']['display_name'], self.user2.display_name)
        self.assertIn('profile_image_url', data['blocked_user'])
        
    def test_serializer_to_json(self):
        """시리얼라이저가 올바른 JSON을 생성하는지 테스트합니다."""
        serializer = UserBlockSerializer(self.user_block)
        content = JSONRenderer().render(serializer.data)
        
        # JSON에 'reason' 필드가 포함되지 않음을 확인
        self.assertNotIn(b'"reason":', content)
