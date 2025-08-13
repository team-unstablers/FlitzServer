from django.test import TestCase
from django.contrib.auth import get_user_model

from user.serializers import (
    PublicUserSerializer,
    PublicSimpleUserSerializer,
    PublicSelfUserSerializer
)

User = get_user_model()

class PublicUserSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword',

            title='테스트 유저',
            bio='안녕! 저는 테스트 사용자입니다.',
            hashtags=['테스트', '유저'],

            profile_image=None
        )
        self.serializer = PublicUserSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        """PublicUserSerializer가 예상된 필드를 포함하는지 테스트"""
        data = self.serializer.data
        self.assertEqual(set(data.keys()), {'id', 'username', 'display_name', 'title', 'bio', 'hashtags', 'profile_image_url'})

    def test_field_content(self):
        """직렬화된 데이터의 내용이 올바른지 테스트"""
        data = self.serializer.data
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['display_name'], 'Test User')
        self.assertEqual(data['profile_image_url'], None)
        self.assertEqual(str(data['id']), str(self.user.id))


class PublicSimpleUserSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword',

            title='테스트 유저',
            bio='안녕! 저는 테스트 사용자입니다.',
            hashtags=['테스트', '유저'],

            profile_image=None,
        )
        self.serializer = PublicSimpleUserSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        """PublicSimpleUserSerializer가 예상된 필드를 포함하는지 테스트"""
        data = self.serializer.data
        self.assertEqual(set(data.keys()), {'id', 'username', 'display_name', 'title', 'bio', 'hashtags', 'profile_image_url'})

    def test_field_content(self):
        """직렬화된 데이터의 내용이 올바른지 테스트"""
        data = self.serializer.data
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['display_name'], 'Test User')
        self.assertEqual(data['profile_image_url'], None)
        self.assertEqual(str(data['id']), str(self.user.id))


class PublicSelfUserSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword',
            profile_image=None,
            free_coins=100,
            paid_coins=50
        )
        self.serializer = PublicSelfUserSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        """PublicSelfUserSerializer가 예상된 필드를 포함하는지 테스트"""
        data = self.serializer.data
        self.assertEqual(set(data.keys()),
                         {'id', 'username', 'display_name',
                          'title', 'bio',
                          'hashtags',
                          'profile_image_url',
                          'phone_number', 'email', 'birth_date',
                          'free_coins', 'paid_coins'})

    def test_field_content(self):
        """직렬화된 데이터의 내용이 올바른지 테스트"""
        data = self.serializer.data
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['display_name'], 'Test User')
        # FIXME: 프로필 이미지는 아직 없음
        self.assertEqual(data['profile_image_url'], None)
        self.assertEqual(data['free_coins'], 100)
        self.assertEqual(data['paid_coins'], 50)
        self.assertEqual(str(data['id']), str(self.user.id))
