from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from safety.models import UserBlock
from flitz.test_utils import create_test_user, create_test_user_with_session


class UserBlockViewSetTests(APITestCase):
    def setUp(self):
        # 두 명의 테스트 사용자 생성
        self.user1, self.session1 = create_test_user_with_session(1)
        self.user2 = create_test_user(2)
        
        # API 클라이언트 설정
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.session1.create_token()}')
        
        # UserBlock 관련 URL 설정
        self.blocks_url = reverse('UserBlock-list')
        
    def test_block_creation(self):
        """차단 생성이 올바르게 동작하는지 테스트합니다."""
        # 사용자2를 차단하는 요청
        data = {'user_id': str(self.user2.id)}
        response = self.client.post(self.blocks_url, data, format='json')
        
        # 응답 확인
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserBlock.objects.count(), 1)
        
        # 생성된 차단의 세부 사항 확인
        block = UserBlock.objects.first()
        self.assertEqual(block.user, self.user2)
        self.assertEqual(block.blocked_by, self.user1)
        self.assertEqual(block.type, UserBlock.Type.BLOCK)
        self.assertEqual(block.reason, UserBlock.Reason.BY_USER)
        
        # 응답에 reason 필드가 포함되지 않는지 확인
        self.assertNotIn('reason', response.data)
        
    def test_block_duplicate_creation(self):
        """동일한 사용자에 대한 중복 차단 요청이 올바르게 처리되는지 테스트합니다."""
        # 첫 번째 차단 생성
        block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        
        # 동일한 사용자에 대한 차단 요청
        data = {'user_id': str(self.user2.id)}
        response = self.client.post(self.blocks_url, data, format='json')
        
        # 응답 확인 - 성공하지만 새로운 객체는 생성되지 않아야 함
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(UserBlock.objects.count(), 1)
        
    def test_block_list_excludes_trigger_blocks(self):
        """트리거에 의한 차단이 목록에서 제외되는지 테스트합니다."""
        # 사용자 차단 생성
        user_block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        
        # 트리거에 의한 차단 생성
        trigger_block = UserBlock.objects.create(
            user=create_test_user(3),
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_TRIGGER
        )
        
        # 차단 목록 조회
        response = self.client.get(self.blocks_url)

        # 응답 확인
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # 트리거에 의한 차단은 제외되어야 함
        self.assertEqual(response.data['results'][0]['id'], str(user_block.id))
        
    def test_block_deletion(self):
        """사용자에 의한 차단을 삭제할 수 있는지 테스트합니다."""
        # 사용자 차단 생성
        block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        
        # 차단 삭제 요청
        block_detail_url = reverse('UserBlock-detail', kwargs={'pk': block.id})
        response = self.client.delete(block_detail_url)
        
        # 응답 확인
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(UserBlock.objects.count(), 0)  # 직접 삭제되어야 함
        
    def test_trigger_block_deletion_not_allowed(self):
        """트리거에 의한 차단은 삭제할 수 없는지 테스트합니다."""
        # 트리거에 의한 차단 생성
        trigger_block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_TRIGGER
        )
        
        # 차단 삭제 요청
        block_detail_url = reverse('UserBlock-detail', kwargs={'pk': trigger_block.id})
        response = self.client.delete(block_detail_url)
        
        # 응답 확인 - 리소스 조회 자체가 금지되어야 함
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(UserBlock.objects.count(), 1)  # 삭제되지 않아야 함
        
    def test_update_not_allowed(self):
        """차단 레코드 업데이트가 금지되는지 테스트합니다."""
        # 사용자 차단 생성
        block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        
        # 전체 업데이트 요청
        block_detail_url = reverse('UserBlock-detail', kwargs={'pk': block.id})
        data = {'type': UserBlock.Type.LIMIT}
        response = self.client.put(block_detail_url, data, format='json')
        
        # 응답 확인 - 금지되어야 함
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
    def test_partial_update_not_allowed(self):
        """차단 레코드 부분 업데이트가 금지되는지 테스트합니다."""
        # 사용자 차단 생성
        block = UserBlock.objects.create(
            user=self.user2,
            blocked_by=self.user1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        
        # 부분 업데이트 요청
        block_detail_url = reverse('UserBlock-detail', kwargs={'pk': block.id})
        data = {'type': UserBlock.Type.LIMIT}
        response = self.client.patch(block_detail_url, data, format='json')
        
        # 응답 확인 - 금지되어야 함
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
