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
            profile_image_url='https://example.com/image.jpg'
        )
        self.serializer = PublicUserSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        """PublicUserSerializer가 예상된 필드를 포함하는지 테스트"""
        data = self.serializer.data
        self.assertEqual(set(data.keys()), {'id', 'username', 'display_name', 'profile_image_url'})

    def test_field_content(self):
        """직렬화된 데이터의 내용이 올바른지 테스트"""
        data = self.serializer.data
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['display_name'], 'Test User')
        self.assertEqual(data['profile_image_url'], 'https://example.com/image.jpg')
        self.assertEqual(str(data['id']), str(self.user.id))


class PublicSimpleUserSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword',
            profile_image_url='https://example.com/image.jpg'
        )
        self.serializer = PublicSimpleUserSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        """PublicSimpleUserSerializer가 예상된 필드를 포함하는지 테스트"""
        data = self.serializer.data
        self.assertEqual(set(data.keys()), {'id', 'username', 'display_name', 'profile_image_url'})

    def test_field_content(self):
        """직렬화된 데이터의 내용이 올바른지 테스트"""
        data = self.serializer.data
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['display_name'], 'Test User')
        self.assertEqual(data['profile_image_url'], 'https://example.com/image.jpg')
        self.assertEqual(str(data['id']), str(self.user.id))


class PublicSelfUserSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            display_name='Test User',
            password='testpassword',
            profile_image_url='https://example.com/image.jpg',
            free_coins=100,
            paid_coins=50
        )
        self.serializer = PublicSelfUserSerializer(instance=self.user)

    def test_contains_expected_fields(self):
        """PublicSelfUserSerializer가 예상된 필드를 포함하는지 테스트"""
        data = self.serializer.data
        self.assertEqual(set(data.keys()), 
                         {'id', 'username', 'display_name', 'profile_image_url', 
                          'free_coins', 'paid_coins'})

    def test_field_content(self):
        """직렬화된 데이터의 내용이 올바른지 테스트"""
        data = self.serializer.data
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['display_name'], 'Test User')
        self.assertEqual(data['profile_image_url'], 'https://example.com/image.jpg')
        self.assertEqual(data['free_coins'], 100)
        self.assertEqual(data['paid_coins'], 50)
        self.assertEqual(str(data['id']), str(self.user.id))
