from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

from user.models import User, UserIdentity, UserGenderBit
from location.models import DiscoverySession, DiscoveryHistory, UserLocation
from location.views import FlitzWaveViewSet
from card.models import Card
from flitz.test_utils import (
    create_test_user, create_test_card, 
    create_test_user_location, create_test_discovery_session,
    create_complete_test_user
)


class FlitzWaveViewSetTest(TestCase):
    def setUp(self):
        """
        테스트를 위한 기본 데이터 설정
        """
        # create_complete_test_user 함수를 사용하여 사용자, 카드, 위치 정보를 한 번에 생성
        test_objects = create_complete_test_user(
            1, 
            with_card=True, 
            with_session=False, 
            with_location=True, 
            with_discovery=False
        )
        
        self.user = test_objects['user']
        self.card = test_objects['card']
        self.location = test_objects['location']
        
        # API 클라이언트 설정
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        # URL 패턴
        self.start_discovery_url = '/wave/discovery/start/'
        self.stop_discovery_url = '/wave/discovery/stop/'
        self.update_location_url = '/wave/discovery/update/'
        self.report_discovery_url = '/wave/discovery/report/'

    def test_start_discovery(self):
        """
        디스커버리 세션 시작 테스트
        """
        # 기존 활성 세션 생성
        existing_session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 새 세션 시작 요청
        response = self.client.post(self.start_discovery_url)
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('session_id', response.data)
        
        # 기존 세션 비활성화 확인
        existing_session.refresh_from_db()
        self.assertFalse(existing_session.is_active)
        
        # 새 세션 생성 확인
        new_session_id = response.data['session_id']
        new_session = DiscoverySession.objects.get(id=new_session_id)
        self.assertTrue(new_session.is_active)
        self.assertEqual(new_session.user, self.user)

    def test_stop_discovery(self):
        """
        디스커버리 세션 중지 테스트
        """
        # 활성 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 세션 중지 요청
        response = self.client.post(self.stop_discovery_url)
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # 세션 비활성화 확인
        session.refresh_from_db()
        self.assertFalse(session.is_active)

    def test_update_location_success(self):
        """
        유효한 세션 ID로 위치 업데이트 테스트
        """
        # 활성 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 위치 업데이트 요청
        location_data = {
            'session_id': str(session.id),
            'latitude': 37.5665,
            'longitude': 126.9780,
            'altitude': 20.0,
            'accuracy': 10.0
        }
        
        with patch.object(User, 'update_location') as mock_update_location:
            response = self.client.post(self.update_location_url, location_data, format='json')
            
            # update_location 메서드 호출 확인
            mock_update_location.assert_called_once_with(
                latitude=37.5665,
                longitude=126.9780,
                altitude=20.0,
                accuracy=10.0
            )
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])


    def test_update_location_invalid_data(self):
        """
        유효하지 않은 데이터로 위치 업데이트 테스트
        """
        # 활성 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 위치 업데이트 요청 (잘못된 데이터)
        invalid_data = {
            'session_id': str(session.id),
            # latitude 누락
            'longitude': 126.9780
        }
        
        response = self.client.post(self.update_location_url, invalid_data, format='json')
        
        # 응답 검증 (400 Bad Request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('location.views.UserMatcher')
    def test_report_discovery_success(self, MockUserMatcher):
        """
        성공적인 디스커버리 보고 테스트
        """
        # UserMatcher 모킹 설정
        mock_matcher_instance = MagicMock()
        mock_matcher_instance.sanity_check.return_value = True
        mock_matcher_instance.try_match.return_value = True
        MockUserMatcher.return_value = mock_matcher_instance
        
        # 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 다른 사용자 생성
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpass123",
            display_name="Other User"
        )
        
        # 다른 사용자의 세션 생성
        other_session = DiscoverySession.objects.create(
            user=other_user,
            is_active=True
        )
        
        # 디스커버리 보고 요청
        report_data = {
            'session_id': str(session.id),
            'discovered_session_id': str(other_session.id),
            'latitude': 37.5665,
            'longitude': 126.9780,
            'altitude': 20.0,
            'accuracy': 10.0
        }
        
        with patch.object(User, 'update_location'):
            response = self.client.post(self.report_discovery_url, report_data, format='json')
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # UserMatcher 호출 확인
        MockUserMatcher.assert_called_once_with(session, other_session)
        mock_matcher_instance.sanity_check.assert_called_once()
        mock_matcher_instance.try_match.assert_called_once()

    @patch('location.views.UserMatcher')
    def test_report_discovery_invalid_session(self, MockUserMatcher):
        """
        유효하지 않은 세션으로 디스커버리 보고 테스트
        """
        # 세션 생성 (하나는 비활성)
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 다른 사용자 생성
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpass123",
            display_name="Other User"
        )
        
        # 다른 사용자의 세션 생성 (비활성)
        other_session = DiscoverySession.objects.create(
            user=other_user,
            is_active=False
        )
        
        # 디스커버리 보고 요청
        report_data = {
            'session_id': str(session.id),
            'discovered_session_id': str(other_session.id),
            'latitude': 37.5665,
            'longitude': 126.9780
        }
        
        with patch.object(User, 'update_location'):
            response = self.client.post(self.report_discovery_url, report_data, format='json')
        
        # 응답 검증 (성공 응답이지만 매칭 시도는 하지 않음)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # UserMatcher가 호출되지 않았는지 확인
        MockUserMatcher.assert_not_called()

    @patch('location.views.UserMatcher')
    def test_report_discovery_with_sanity_check_failed(self, MockUserMatcher):
        """
        sanity_check가 실패하는 경우 디스커버리 보고 테스트
        """
        # UserMatcher 모킹 설정
        mock_matcher_instance = MagicMock()
        mock_matcher_instance.sanity_check.return_value = False  # sanity_check 실패
        MockUserMatcher.return_value = mock_matcher_instance
        
        # 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 다른 사용자 생성
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpass123",
            display_name="Other User"
        )
        
        # 다른 사용자의 세션 생성
        other_session = DiscoverySession.objects.create(
            user=other_user,
            is_active=True
        )
        
        # 디스커버리 보고 요청
        report_data = {
            'session_id': str(session.id),
            'discovered_session_id': str(other_session.id),
            'latitude': 37.5665,
            'longitude': 126.9780
        }
        
        with patch.object(User, 'update_location'):
            response = self.client.post(self.report_discovery_url, report_data, format='json')
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # UserMatcher 호출 확인
        MockUserMatcher.assert_called_once()
        mock_matcher_instance.sanity_check.assert_called_once()
        mock_matcher_instance.try_match.assert_not_called()  # sanity_check 실패로 try_match는 호출되지 않음
    
    @patch('location.views.UserMatcher')
    def test_report_discovery_with_prerequisite_check_failed(self, MockUserMatcher):
        """
        prerequisite_check가 실패하는 경우 디스커버리 보고 테스트
        """
        # UserMatcher 모킹 설정
        mock_matcher_instance = MagicMock()
        mock_matcher_instance.sanity_check.return_value = True  # sanity_check 성공
        mock_matcher_instance.prerequisite_check.return_value = False  # prerequisite_check 실패
        MockUserMatcher.return_value = mock_matcher_instance
        
        # 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 다른 사용자 생성
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpass123",
            display_name="Other User"
        )
        
        # 다른 사용자의 세션 생성
        other_session = DiscoverySession.objects.create(
            user=other_user,
            is_active=True
        )
        
        # 디스커버리 보고 요청
        report_data = {
            'session_id': str(session.id),
            'discovered_session_id': str(other_session.id),
            'latitude': 37.5665,
            'longitude': 126.9780
        }
        
        with patch.object(User, 'update_location'):
            response = self.client.post(self.report_discovery_url, report_data, format='json')
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # UserMatcher 호출 확인
        MockUserMatcher.assert_called_once()
        mock_matcher_instance.sanity_check.assert_called_once()
        mock_matcher_instance.prerequisite_check.assert_called_once()
        mock_matcher_instance.try_match.assert_not_called()  # prerequisite_check 실패로 try_match는 호출되지 않음
    
    @patch('location.views.UserMatcher')
    def test_report_discovery_with_prerequisite_check_gender_mismatch(self, MockUserMatcher):
        """
        성별 선호가 맞지 않아 prerequisite_check가 실패하는 경우 테스트
        """
        # UserMatcher 모킹 설정
        mock_matcher_instance = MagicMock()
        mock_matcher_instance.sanity_check.return_value = True
        mock_matcher_instance.prerequisite_check.return_value = False
        MockUserMatcher.return_value = mock_matcher_instance
        
        # 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 다른 사용자 생성
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpass123",
            display_name="Other User"
        )
        
        # 성별 선호가 맞지 않는 Identity 생성
        UserIdentity.objects.create(
            user=self.user,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN  # 남성 선호
        )
        
        UserIdentity.objects.create(
            user=other_user,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.WOMAN  # 여성 선호 (매칭 불가)
        )
        
        # 다른 사용자의 세션 생성
        other_session = DiscoverySession.objects.create(
            user=other_user,
            is_active=True
        )
        
        # 디스커버리 보고 요청
        report_data = {
            'session_id': str(session.id),
            'discovered_session_id': str(other_session.id),
            'latitude': 37.5665,
            'longitude': 126.9780
        }
        
        with patch.object(User, 'update_location'):
            response = self.client.post(self.report_discovery_url, report_data, format='json')
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # UserMatcher 호출 확인
        MockUserMatcher.assert_called_once()
        mock_matcher_instance.sanity_check.assert_called_once()
        mock_matcher_instance.prerequisite_check.assert_called_once()
        mock_matcher_instance.try_match.assert_not_called()
    
    @patch('location.views.UserMatcher')
    def test_report_discovery_with_prerequisite_check_trans_safe_match(self, MockUserMatcher):
        """
        트랜스젠더 안전 매칭 조건으로 prerequisite_check가 실패하는 경우 테스트
        """
        # UserMatcher 모킹 설정
        mock_matcher_instance = MagicMock()
        mock_matcher_instance.sanity_check.return_value = True
        mock_matcher_instance.prerequisite_check.return_value = False
        MockUserMatcher.return_value = mock_matcher_instance
        
        # 세션 생성
        session = DiscoverySession.objects.create(
            user=self.user,
            is_active=True
        )
        
        # 다른 사용자 생성
        other_user = User.objects.create_user(
            username="otheruser",
            password="testpass123",
            display_name="Other User"
        )
        
        # 트랜스젠더 안전 매칭 조건 설정
        UserIdentity.objects.create(
            user=self.user,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            is_trans=True,
            trans_prefers_safe_match=True  # 안전 매칭 필요
        )
        
        UserIdentity.objects.create(
            user=other_user,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            welcomes_trans=False  # 트랜스 환영하지 않음 (매칭 불가)
        )
        
        # 다른 사용자의 세션 생성
        other_session = DiscoverySession.objects.create(
            user=other_user,
            is_active=True
        )
        
        # 디스커버리 보고 요청
        report_data = {
            'session_id': str(session.id),
            'discovered_session_id': str(other_session.id),
            'latitude': 37.5665,
            'longitude': 126.9780
        }
        
        with patch.object(User, 'update_location'):
            response = self.client.post(self.report_discovery_url, report_data, format='json')
        
        # 응답 검증
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # UserMatcher 호출 확인
        MockUserMatcher.assert_called_once()
        mock_matcher_instance.sanity_check.assert_called_once()
        mock_matcher_instance.prerequisite_check.assert_called_once()
        mock_matcher_instance.try_match.assert_not_called()  # 안전 매칭 조건 불충족으로 try_match 호출 안 됨
