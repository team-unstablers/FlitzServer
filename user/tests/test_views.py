from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock

from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate
from rest_framework import status

from user.models import User
from user.views import PublicUserViewSet
from user_auth.models import UserSession


class PublicUserViewSetTests(APITestCase):
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

        self.factory = APIRequestFactory()
        self.view = PublicUserViewSet.as_view({
            'get': 'get_self',
            'put': 'set_apns_token',
            'post': 'set_profile_image'
        })
        
        # 별도 경로의 뷰
        self.register_view = PublicUserViewSet.as_view({'post': 'register'})
        self.username_view = PublicUserViewSet.as_view({'get': 'get_by_username'})
        self.list_view = PublicUserViewSet.as_view({'get': 'list'})

    def test_list_not_allowed(self):
        """리스트 조회가 불허용되는지 테스트"""
        request = self.factory.get('/')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.list_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)  # UnsupportedOperationException 실제로는 400 코드를 반환

    def test_get_self(self):
        """자신의 정보 조회 테스트"""
        request = self.factory.get('/')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['display_name'], 'Test User')
        self.assertIn('free_coins', response.data)
        self.assertIn('paid_coins', response.data)

    def test_set_apns_token(self):
        """APNS 토큰 설정 테스트"""
        data = {'apns_token': 'new_test_token'}
        request = self.factory.put('/', data, format='json')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_success'])
        
        # 세션 다시 로드
        self.session.refresh_from_db()
        self.assertEqual(self.session.apns_token, 'new_test_token')

    @patch('user.views.generate_thumbnail')
    @patch('django.core.files.storage.default_storage.save')
    @patch('django.core.files.storage.default_storage.url')
    def test_set_profile_image(self, mock_url, mock_save, mock_thumbnail):
        """프로필 이미지 설정 테스트"""
        # Mock setup
        mock_thumbnail.return_value = b'thumbnail_data'
        mock_url.return_value = 'https://example.com/image.jpg'
        
        # Create file
        image_file = SimpleUploadedFile(
            'test_image.jpg',
            b'file_content',
            content_type='image/jpeg'
        )
        
        # Request
        request = self.factory.post('/', {'file': image_file}, format='multipart')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.view(request)
        
        # Tests
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that methods were called
        mock_thumbnail.assert_called_once()
        mock_save.assert_called_once()
        mock_url.assert_called_once()
        
        # Check user was updated
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.profile_image_key)
        self.assertIsNotNone(self.user.profile_image_url)

    def test_get_by_username(self):
        """사용자명으로 사용자 정보 조회 테스트"""
        request = self.factory.get('/')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.username_view(request, username='testuser')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['display_name'], 'Test User')
        # 다른 사용자 정보 조회시 free_coins, paid_coins 등이 없어야 함
        self.assertNotIn('free_coins', response.data)
        self.assertNotIn('paid_coins', response.data)

    def test_register(self):
        """회원가입 테스트"""
        data = {
            'username': 'newuser',
            'password': 'newpassword'
        }
        request = self.factory.post('/', data, format='json')
        response = self.register_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_success'])
        
        # Check that the user was created
        new_user = User.objects.filter(username='newuser').first()
        self.assertIsNotNone(new_user)
        self.assertTrue(new_user.check_password('newpassword'))
        self.assertTrue(new_user.is_active)

    def test_authentication_required(self):
        """인증이 필요한지 테스트"""
        # No authentication
        request = self.factory.get('/')
        response = self.view(request)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)  # Django REST framework는 인증 실패시 403을 반환
