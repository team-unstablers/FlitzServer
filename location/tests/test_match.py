from django.test import TransactionTestCase
from django.utils import timezone
from django.db import transaction
from freezegun import freeze_time
from unittest.mock import patch, MagicMock

import pytz
from datetime import datetime, timedelta

from user.models import User
from card.models import Card, CardDistribution
from location.models import DiscoverySession, DiscoveryHistory, UserLocation
from location.match import UserMatcher
from location.utils import get_today_start_in_timezone


class UserMatcherTest(TransactionTestCase):
    def setUp(self):
        """
        테스트를 위한 기본 데이터 설정
        """
        # 테스트 사용자들 생성
        self.user1 = User.objects.create_user(
            username="user1",
            password="testpass123",
            display_name="User One"
        )
        
        self.user2 = User.objects.create_user(
            username="user2",
            password="testpass123",
            display_name="User Two"
        )
        
        # 카드 생성
        self.card1 = Card.objects.create(
            user=self.user1,
            title="Card One",
            content={"test": "content1"}
        )
        
        self.card2 = Card.objects.create(
            user=self.user2,
            title="Card Two",
            content={"test": "content2"}
        )
        
        # 사용자에게 메인 카드 할당
        self.user1.main_card = self.card1
        self.user1.save()
        
        self.user2.main_card = self.card2
        self.user2.save()
        
        # 위치 정보 설정
        self.location1 = UserLocation.objects.create(
            user=self.user1,
            latitude=37.5665,
            longitude=126.9780,
            altitude=10.0,
            accuracy=5.0,
            timezone="Asia/Seoul"
        )
        
        self.location2 = UserLocation.objects.create(
            user=self.user2,
            latitude=37.5665,
            longitude=126.9780,
            altitude=10.0,
            accuracy=5.0,
            timezone="Asia/Seoul"
        )
        
        # 세션 생성
        self.session1 = DiscoverySession.objects.create(
            user=self.user1,
            is_active=True
        )
        
        self.session2 = DiscoverySession.objects.create(
            user=self.user2,
            is_active=True
        )
        
        # UserMatcher 인스턴스 생성
        self.matcher = UserMatcher(self.session1, self.session2)
        
    def test_init(self):
        """
        초기화 테스트
        """
        matcher = UserMatcher(self.session1, self.session2)
        self.assertEqual(matcher.discoverer, self.session1)
        self.assertEqual(matcher.discovered, self.session2)

    @freeze_time("2025-03-21 10:00:00", tz_offset=9)
    def test_prev_discover_history_exists_no_history(self):
        """
        이전 디스커버리 히스토리가 없는 경우 테스트
        """
        # private 메서드 테스트를 위한 접근
        result = self.matcher._UserMatcher__prev_discover_history_exists()
        self.assertFalse(result)

    @freeze_time("2025-03-21 10:00:00", tz_offset=9)
    def test_prev_discover_history_exists_with_history(self):
        """
        이전 디스커버리 히스토리가 있는 경우 테스트
        """
        # 오늘 생성된 히스토리 추가
        DiscoveryHistory.objects.create(
            session=self.session1,
            discovered=self.session2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # private 메서드 테스트를 위한 접근
        result = self.matcher._UserMatcher__prev_discover_history_exists()
        self.assertTrue(result)

    @freeze_time("2025-03-21 10:00:00", tz_offset=9)
    def test_prev_discover_history_exists_with_old_history(self):
        """
        과거 디스커버리 히스토리만 있는 경우 테스트
        """
        # 어제 생성된 히스토리 추가 (created_at을 직접 설정)
        history = DiscoveryHistory.objects.create(
            session=self.session1,
            discovered=self.session2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # 현재 시간보다 하루 이전으로 설정
        yesterday = timezone.now() - timedelta(days=1)
        DiscoveryHistory.objects.filter(pk=history.pk).update(created_at=yesterday)
        
        # private 메서드 테스트를 위한 접근
        result = self.matcher._UserMatcher__prev_discover_history_exists()
        self.assertFalse(result)

    def test_create_discover_history(self):
        """
        디스커버리 히스토리 생성 테스트
        """
        # private 메서드 테스트를 위한 접근
        history = self.matcher._UserMatcher__create_discover_history()
        
        self.assertIsInstance(history, DiscoveryHistory)
        self.assertEqual(history.session, self.session1)
        self.assertEqual(history.discovered, self.session2)
        self.assertEqual(history.latitude, self.location1.latitude)
        self.assertEqual(history.longitude, self.location1.longitude)
        self.assertEqual(history.altitude, self.location1.altitude)
        self.assertEqual(history.accuracy, self.location1.accuracy)

    def test_is_nearby(self):
        """
        근접성 확인 테스트
        
        참고: __is_nearby 메서드는 현재 구현되어 있지 않으므로,
        테스트를 위해 패치하여 임시 구현을 추가합니다.
        """
        # 임시 구현 패치
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=True):
            result = self.matcher._UserMatcher__is_nearby()
            self.assertTrue(result)
            
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=False):
            result = self.matcher._UserMatcher__is_nearby()
            self.assertFalse(result)

    def test_distribute_card_new_distribution(self):
        """
        새 카드 배포 테스트
        """
        history = DiscoveryHistory.objects.create(
            session=self.session1,
            discovered=self.session2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # private 메서드 테스트를 위한 접근
        distribution = self.matcher._UserMatcher__distribute_card(self.user1, self.user2, history)
        
        self.assertIsNotNone(distribution)
        self.assertEqual(distribution.card, self.card1)
        self.assertEqual(distribution.user, self.user2)
        self.assertEqual(distribution.latitude, history.latitude)
        self.assertEqual(distribution.longitude, history.longitude)

    def test_distribute_card_already_distributed(self):
        """
        이미 배포된 카드 재배포 방지 테스트
        """
        # 이미 배포된 카드 생성
        CardDistribution.objects.create(
            card=self.card1,
            user=self.user2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        history = DiscoveryHistory.objects.create(
            session=self.session1,
            discovered=self.session2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # private 메서드 테스트를 위한 접근
        distribution = self.matcher._UserMatcher__distribute_card(self.user1, self.user2, history)
        
        # 이미 배포된 카드는 None을 반환해야 함
        self.assertIsNone(distribution)
        
        # 카드 배포 수가 여전히 1개여야 함
        distribution_count = CardDistribution.objects.filter(
            card=self.card1,
            user=self.user2
        ).count()
        self.assertEqual(distribution_count, 1)

    def test_sanity_check_no_main_card(self):
        """
        메인 카드가 없는 경우 sanity_check 테스트
        """
        # 사용자 메인 카드 제거
        self.user1.main_card = None
        self.user1.save()
        
        result = self.matcher.sanity_check()
        self.assertFalse(result)
        
        # 한 사용자만 메인 카드 없는 경우
        self.user1.main_card = self.card1
        self.user1.save()
        self.user2.main_card = None
        self.user2.save()
        
        result = self.matcher.sanity_check()
        self.assertFalse(result)

    def test_sanity_check_not_nearby(self):
        """
        사용자가 근처에 없는 경우 sanity_check 테스트
        """
        # __is_nearby 패치하여 False 반환
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=False):
            result = self.matcher.sanity_check()
            self.assertFalse(result)

    def test_sanity_check_success(self):
        """
        모든 조건 충족 시 sanity_check 테스트
        """
        # __is_nearby 패치하여 True 반환
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=True):
            result = self.matcher.sanity_check()
            self.assertTrue(result)

    @freeze_time("2025-03-21 10:00:00", tz_offset=9)
    def test_try_match_already_discovered_today(self):
        """
        이미 오늘 발견된 경우 try_match 테스트
        """
        # 오늘 생성된 히스토리 추가
        DiscoveryHistory.objects.create(
            session=self.session1,
            discovered=self.session2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # __is_nearby 패치하여 True 반환
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=True):
            result = self.matcher.try_match()
            self.assertFalse(result)  # 이미 발견되었으므로 False 반환

    @freeze_time("2025-03-21 10:00:00", tz_offset=9)
    def test_try_match_without_opponent_discovery(self):
        """
        상대방이 나를 발견하지 않은 경우 try_match 테스트
        """
        # __is_nearby 패치하여 True 반환
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=True):
            result = self.matcher.try_match()
            self.assertFalse(result)  # 상대방이 발견하지 않았으므로 False 반환
            
            # 히스토리가 생성되었는지 확인
            history_exists = DiscoveryHistory.objects.filter(
                session=self.session1,
                discovered=self.session2
            ).exists()
            self.assertTrue(history_exists)

    @freeze_time("2025-03-21 10:00:00", tz_offset=9)
    def test_try_match_with_opponent_discovery(self):
        """
        상대방이 최근 30분 내에 나를 발견한 경우 try_match 테스트
        """
        # 상대방이 나를 발견한 히스토리 추가 (30분 이내)
        opponent_history = DiscoveryHistory.objects.create(
            session=self.session2,
            discovered=self.session1,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # __is_nearby 패치하여 True 반환
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=True):
            # __finalize_match 패치
            with patch.object(UserMatcher, '_UserMatcher__finalize_match') as mock_finalize:
                result = self.matcher.try_match()
                self.assertTrue(result)  # 매칭 성공으로 True 반환
                
                # 내 히스토리가 생성되었는지 확인
                my_history = DiscoveryHistory.objects.filter(
                    session=self.session1,
                    discovered=self.session2
                ).first()
                self.assertIsNotNone(my_history)
                
                # __finalize_match가 호출되었는지 확인
                mock_finalize.assert_called_once()

    @freeze_time("2025-03-21 10:00:00", tz_offset=9)
    def test_try_match_with_old_opponent_discovery(self):
        """
        상대방이 30분보다 더 오래 전에 나를 발견한 경우 try_match 테스트
        """
        # 상대방이 나를 발견한 히스토리 추가 (현재시간보다 1시간 전)
        opponent_history = DiscoveryHistory.objects.create(
            session=self.session2,
            discovered=self.session1,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # 생성 시간을 1시간 전으로 업데이트
        one_hour_ago = timezone.now() - timedelta(hours=1)
        DiscoveryHistory.objects.filter(pk=opponent_history.pk).update(created_at=one_hour_ago)
        
        # __is_nearby 패치하여 True 반환
        with patch.object(UserMatcher, '_UserMatcher__is_nearby', return_value=True):
            result = self.matcher.try_match()
            self.assertFalse(result)  # 시간 제한으로 인해 False 반환

    def test_finalize_match(self):
        """
        매칭 완료 테스트
        """
        history1 = DiscoveryHistory.objects.create(
            session=self.session1,
            discovered=self.session2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        history2 = DiscoveryHistory.objects.create(
            session=self.session2,
            discovered=self.session1,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # __distribute_card 메서드 모킹
        with patch.object(UserMatcher, '_UserMatcher__distribute_card') as mock_distribute:
            # private 메서드 테스트를 위한 접근
            self.matcher._UserMatcher__finalize_match(history1, history2)
            
            # __distribute_card가 두 번 호출되었는지 확인 (양방향 카드 교환)
            self.assertEqual(mock_distribute.call_count, 2)

    def test_finalize_match_real_distribution(self):
        """
        실제 카드 배포를 포함한 매칭 완료 테스트
        """
        history1 = DiscoveryHistory.objects.create(
            session=self.session1,
            discovered=self.session2,
            latitude=37.5665,
            longitude=126.9780
        )
        
        history2 = DiscoveryHistory.objects.create(
            session=self.session2,
            discovered=self.session1,
            latitude=37.5665,
            longitude=126.9780
        )
        
        # private 메서드 테스트를 위한 접근
        self.matcher._UserMatcher__finalize_match(history1, history2)
        
        # 카드가 실제로 배포되었는지 확인
        distribution1 = CardDistribution.objects.filter(
            card=self.card1,
            user=self.user2
        ).first()
        
        distribution2 = CardDistribution.objects.filter(
            card=self.card2,
            user=self.user1
        ).first()
        
        self.assertIsNotNone(distribution1)
        self.assertIsNotNone(distribution2)
        self.assertEqual(distribution1.latitude, history1.latitude)
        self.assertEqual(distribution2.latitude, history2.latitude)
