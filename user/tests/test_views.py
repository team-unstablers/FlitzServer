import warnings

from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock

from rest_framework.test import APITestCase, APIRequestFactory, force_authenticate
from rest_framework import status

from user.models import User, UserIdentity, UserGenderBit
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

    @patch('user.models.User.set_profile_image')
    def test_set_profile_image(self, mock_set_profile_image):
        """프로필 이미지 설정 테스트"""
        warnings.warn("test_set_profile_image: WARN: 실제 이미지를 전송하도록 수정해야 하지 않을까요?")

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
        mock_set_profile_image.assert_called_once()

        # Check user was updated
        # self.user.refresh_from_db()
        # self.assertIsNotNone(self.user.profile_image.url)

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


class UserIdentityAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword'
        )
        
        self.session = UserSession.objects.create(
            user=self.user,
            description='Test Session',
            initiated_from='127.0.0.1'
        )
        
        self.factory = APIRequestFactory()
        
        # Identity 엔드포인트 뷰 설정
        self.identity_view = PublicUserViewSet.as_view({
            'get': 'dispatch_self_identity',
            'patch': 'dispatch_self_identity'
        })
    
    def test_get_identity_not_found(self):
        """Identity가 없을 때 GET 요청 테스트"""
        request = self.factory.get('/api/users/self/identity')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.identity_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data['is_success'])
        self.assertEqual(response.data['message'], 'Identity not found')
    
    def test_get_identity_success(self):
        """Identity가 있을 때 GET 요청 테스트"""
        # Identity 생성
        identity = UserIdentity.objects.create(
            user=self.user,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN | UserGenderBit.NON_BINARY,
            is_trans=False,
            welcomes_trans=True
        )
        
        request = self.factory.get('/api/users/self/identity')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.identity_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['gender'], UserGenderBit.MAN)
        self.assertEqual(response.data['preferred_genders'], UserGenderBit.MAN | UserGenderBit.NON_BINARY)
        self.assertFalse(response.data['is_trans'])
        self.assertTrue(response.data['welcomes_trans'])
        self.assertFalse(response.data['trans_prefers_safe_match'])
    
    def test_patch_identity_create(self):
        """Identity가 없을 때 PATCH 요청으로 생성 테스트"""
        data = {
            'gender': UserGenderBit.MAN,
            'preferred_genders': UserGenderBit.MAN,
            'is_trans': False,
            'welcomes_trans': True
        }
        
        request = self.factory.patch('/api/users/self/identity', data, format='json')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.identity_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['gender'], UserGenderBit.MAN)
        self.assertEqual(response.data['preferred_genders'], UserGenderBit.MAN)
        self.assertFalse(response.data['is_trans'])
        self.assertTrue(response.data['welcomes_trans'])
        
        # DB에 생성되었는지 확인
        identity = UserIdentity.objects.get(user=self.user)
        self.assertEqual(identity.gender, UserGenderBit.MAN)
        self.assertEqual(identity.preferred_genders, UserGenderBit.MAN)
        self.assertFalse(identity.is_trans)
        self.assertTrue(identity.welcomes_trans)
    
    def test_patch_identity_update(self):
        """기존 Identity를 PATCH 요청으로 업데이트 테스트"""
        # 기존 Identity 생성
        identity = UserIdentity.objects.create(
            user=self.user,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            is_trans=False,
            welcomes_trans=False
        )
        
        # 업데이트 데이터
        data = {
            'preferred_genders': UserGenderBit.MAN | UserGenderBit.WOMAN,
            'welcomes_trans': True
        }
        
        request = self.factory.patch('/api/users/self/identity', data, format='json')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.identity_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['gender'], UserGenderBit.MAN)  # 변경하지 않은 필드
        self.assertEqual(response.data['preferred_genders'], UserGenderBit.MAN | UserGenderBit.WOMAN)  # 변경한 필드
        self.assertTrue(response.data['welcomes_trans'])  # 변경한 필드
        
        # DB에 업데이트되었는지 확인
        identity.refresh_from_db()
        self.assertEqual(identity.gender, UserGenderBit.MAN)
        self.assertEqual(identity.preferred_genders, UserGenderBit.MAN | UserGenderBit.WOMAN)
        self.assertTrue(identity.welcomes_trans)
    
    def test_patch_identity_trans_settings(self):
        """트랜스젠더 관련 설정 업데이트 테스트"""
        # Identity 생성
        identity = UserIdentity.objects.create(
            user=self.user,
            gender=UserGenderBit.MAN,
            preferred_genders=UserGenderBit.MAN,
            is_trans=False,
            trans_prefers_safe_match=False
        )
        
        # 트랜스젠더로 설정 변경
        data = {
            'is_trans': True,
            'display_trans_to_others': True,
            'trans_prefers_safe_match': True
        }
        
        request = self.factory.patch('/api/users/self/identity', data, format='json')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.identity_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_trans'])
        self.assertTrue(response.data['display_trans_to_others'])
        self.assertTrue(response.data['trans_prefers_safe_match'])
        
        # DB에 업데이트되었는지 확인
        identity.refresh_from_db()
        self.assertTrue(identity.is_trans)
        self.assertTrue(identity.display_trans_to_others)
        self.assertTrue(identity.trans_prefers_safe_match)
    
    def test_patch_identity_partial_update(self):
        """부분 업데이트 테스트 (PATCH의 특성)"""
        # Identity 생성
        identity = UserIdentity.objects.create(
            user=self.user,
            gender=UserGenderBit.WOMAN,
            preferred_genders=UserGenderBit.MAN,
            is_trans=True,
            welcomes_trans=False,
            trans_prefers_safe_match=True
        )
        
        # 일부 필드만 업데이트
        data = {
            'welcomes_trans': True  # 한 필드만 변경
        }
        
        request = self.factory.patch('/api/users/self/identity', data, format='json')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.identity_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 변경하지 않은 필드들은 그대로 유지
        self.assertEqual(response.data['gender'], UserGenderBit.WOMAN)
        self.assertEqual(response.data['preferred_genders'], UserGenderBit.MAN)
        self.assertTrue(response.data['is_trans'])
        self.assertTrue(response.data['trans_prefers_safe_match'])
        
        # 변경한 필드만 업데이트
        self.assertTrue(response.data['welcomes_trans'])
    
    def test_patch_identity_invalid_data(self):
        """유효하지 않은 데이터로 PATCH 요청 테스트"""
        data = {
            'gender': 999,  # 유효하지 않은 성별 값
            'preferred_genders': -1  # 유효하지 않은 값
        }
        
        request = self.factory.patch('/api/users/self/identity', data, format='json')
        force_authenticate(request, user=self.user, token=self.session)
        response = self.identity_view(request)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('gender', response.data)  # 에러 메시지에 gender 필드 포함
    
    def test_authentication_required(self):
        """인증 없이 Identity API 접근 테스트"""
        # GET 요청
        request = self.factory.get('/api/users/self/identity')
        response = self.identity_view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # PATCH 요청
        request = self.factory.patch('/api/users/self/identity', {}, format='json')
        response = self.identity_view(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
