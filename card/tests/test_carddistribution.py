from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from card.models import CardDistribution, Card
from flitz.test_utils import (
    create_test_user, create_test_card, 
    create_test_user_location, create_complete_test_user
)

# Test settings for reveal conditions
test_settings = {
    'CARD_REVEAL_DISTANCE_ASSERTIVE': 0.5,  # km
    'CARD_REVEAL_DISTANCE_SOFT': 2.0,       # km
    'CARD_REVEAL_DISTANCE_HARD': 15.0,      # km
    'CARD_REVEAL_TIME_SOFT': timedelta(hours=2),
    'CARD_REVEAL_TIME_HARD': timedelta(hours=24),
    'CARD_REVEAL_TIME_BLURRY_STRONG': timedelta(minutes=45),
    'CARD_REVEAL_TIME_BLURRY_SOFT': timedelta(minutes=90),
}

@override_settings(**test_settings)
class CardDistributionTestCase(TestCase):
    def setUp(self):
        """
        테스트에 필요한 기본 객체들을 생성합니다.

        - user1 <-> user2간 거리: 215m
        - user1 <-> 서울광장간 거리: 114m
        - user2 <-> 서울광장간 거리: 103m
        """
        # 사용자 생성
        self.user1 = create_test_user(1)  # 카드 소유자
        self.user2 = create_test_user(2)  # 카드 수신자
        
        # 카드 생성
        self.card = create_test_card(self.user1)
        
        # 위치 정보 생성 - user1 (카드 소유자)
        # 서울시청 근처 좌표
        self.user1_location = create_test_user_location(
            self.user1, 
            latitude=37.5665851,
            longitude=126.9782038
        )
        
        # 위치 정보 생성 - user2 (카드 수신자)
        # 더플라자 호텔
        self.user2_location = create_test_user_location(
            self.user2, 
            latitude=37.5646452,
            longitude=126.9781534
        )
        
        # 카드 배포 생성
        # 서울광장
        self.distribution = CardDistribution.objects.create(
            card=self.card,
            user=self.user2,
            latitude=37.5655675,
            longitude=126.978014,
        )

    def test_reveal_phase_enum(self):
        """RevealPhase 열거형이 올바르게 정의되었는지 테스트합니다."""
        self.assertEqual(CardDistribution.RevealPhase.HIDDEN, 0)
        self.assertEqual(CardDistribution.RevealPhase.BLURRY_STRONG, 1)
        self.assertEqual(CardDistribution.RevealPhase.BLURRY_SOFT, 2)
        self.assertEqual(CardDistribution.RevealPhase.FULLY_REVEALED, 3)

    def test_opponent_property(self):
        """opponent 속성이 카드 소유자를 올바르게 반환하는지 테스트합니다."""
        self.assertEqual(self.distribution.opponent, self.user1)

    @patch('card.models.CardDistribution.distance_to')
    def test_is_okay_to_reveal_assertive_distance(self, mock_distance_to):
        """
        assertive condition에서 거리 조건 테스트합니다.
        - opponent가 너무 가까이 있으면 False 반환
        - opponent가 충분히 멀리 있으면 True 반환
        """
        # 너무 가까운 경우 (기준보다 가까움)
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_ASSERTIVE'] - 0.1
        self.assertFalse(self.distribution.is_okay_to_reveal_assertive)
        
        # 충분히 멀리 있는 경우 (기준보다 멀리 있음)
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_ASSERTIVE'] + 0.1
        self.assertTrue(self.distribution.is_okay_to_reveal_assertive)

    @patch('card.models.CardDistribution.distance_to')
    def test_is_okay_to_reveal_soft(self, mock_distance_to):
        """
        soft condition 테스트합니다.
        - 거리 조건과 시간 조건 모두 충족하면 True 반환
        - 조건 중 하나라도 충족하지 않으면 False 반환
        """
        # 시간, 거리 모두 충족하지 않는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_SOFT'] - 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=1)  # 시간 조건 충족하지 않음
        self.assertFalse(self.distribution.is_okay_to_reveal_soft)
        
        # 시간만 충족하는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_SOFT'] - 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=3)  # 시간 조건 충족
        self.assertFalse(self.distribution.is_okay_to_reveal_soft)
        
        # 거리만 충족하는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_SOFT'] + 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=1)  # 시간 조건 충족하지 않음
        self.assertFalse(self.distribution.is_okay_to_reveal_soft)
        
        # 시간, 거리 모두 충족하는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_SOFT'] + 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=3)  # 시간 조건 충족
        self.assertTrue(self.distribution.is_okay_to_reveal_soft)

    @patch('card.models.CardDistribution.distance_to')
    def test_is_okay_to_reveal_hard(self, mock_distance_to):
        """
        hard condition 테스트합니다.
        - 거리 또는 시간 조건 중 하나라도 충족하면 True 반환
        - 둘 다 충족하지 않으면 False 반환
        """
        # 시간, 거리 모두 충족하지 않는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_HARD'] - 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=20)  # 시간 조건 충족하지 않음
        self.assertFalse(self.distribution.is_okay_to_reveal_hard)
        
        # 시간만 충족하는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_HARD'] - 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=25)  # 시간 조건 충족
        self.assertTrue(self.distribution.is_okay_to_reveal_hard)
        
        # 거리만 충족하는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_HARD'] + 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=20)  # 시간 조건 충족하지 않음
        self.assertTrue(self.distribution.is_okay_to_reveal_hard)
        
        # 시간, 거리 모두 충족하는 경우
        mock_distance_to.return_value = test_settings['CARD_REVEAL_DISTANCE_HARD'] + 0.5
        self.distribution.created_at = timezone.now() - timedelta(hours=25)  # 시간 조건 충족
        self.assertTrue(self.distribution.is_okay_to_reveal_hard)

    @patch('card.models.CardDistribution.is_okay_to_reveal_assertive')
    @patch('card.models.CardDistribution.is_okay_to_reveal_soft')
    @patch('card.models.CardDistribution.is_okay_to_reveal_hard')
    def test_update_reveal_phase_assertive_fails(self, mock_hard, mock_soft, mock_assertive):
        """
        assertive condition이 실패할 경우 update_reveal_phase 메서드 테스트합니다.
        - assertive condition이 충족되지 않으면 reveal_phase가 변경되지 않아야 함
        """
        # 초기 설정
        self.distribution.reveal_phase = CardDistribution.RevealPhase.HIDDEN
        
        # assertive condition 실패
        mock_assertive.__get__ = MagicMock(return_value=False)
        mock_soft.__get__ = MagicMock(return_value=True)
        mock_hard.__get__ = MagicMock(return_value=True)
        
        # 메서드 실행
        self.distribution.update_reveal_phase()
        
        # reveal_phase가 변경되지 않아야 함
        self.assertEqual(self.distribution.reveal_phase, CardDistribution.RevealPhase.HIDDEN)

    @patch('card.models.CardDistribution.is_okay_to_reveal_assertive')
    @patch('card.models.CardDistribution.is_okay_to_reveal_soft')
    @patch('card.models.CardDistribution.is_okay_to_reveal_hard')
    def test_update_reveal_phase_soft_passes(self, mock_hard, mock_soft, mock_assertive):
        """
        soft condition이 충족될 경우 update_reveal_phase 메서드 테스트합니다.
        - assertive condition이 충족되고 soft condition이 충족되면 reveal_phase가 FULLY_REVEALED로 변경
        """
        # 초기 설정
        self.distribution.reveal_phase = CardDistribution.RevealPhase.HIDDEN
        
        # assertive condition 통과, soft condition 통과
        mock_assertive.__get__ = MagicMock(return_value=True)
        mock_soft.__get__ = MagicMock(return_value=True)
        mock_hard.__get__ = MagicMock(return_value=False)  # hard는 상관없음
        
        # 메서드 실행
        self.distribution.update_reveal_phase()
        
        # reveal_phase가 FULLY_REVEALED로 변경되어야 함
        self.assertEqual(self.distribution.reveal_phase, CardDistribution.RevealPhase.FULLY_REVEALED)

    @patch('card.models.CardDistribution.is_okay_to_reveal_assertive')
    @patch('card.models.CardDistribution.is_okay_to_reveal_soft')
    @patch('card.models.CardDistribution.is_okay_to_reveal_hard')
    def test_update_reveal_phase_hard_passes(self, mock_hard, mock_soft, mock_assertive):
        """
        hard condition이 충족될 경우 update_reveal_phase 메서드 테스트합니다.
        - assertive condition이 충족되고, soft는 실패하고 hard condition이 충족되면 reveal_phase가 FULLY_REVEALED로 변경
        """
        # 초기 설정
        self.distribution.reveal_phase = CardDistribution.RevealPhase.HIDDEN
        
        # assertive condition 통과, soft condition 실패, hard condition 통과
        mock_assertive.__get__ = MagicMock(return_value=True)
        mock_soft.__get__ = MagicMock(return_value=False)
        mock_hard.__get__ = MagicMock(return_value=True)
        
        # 메서드 실행
        self.distribution.update_reveal_phase()
        
        # reveal_phase가 FULLY_REVEALED로 변경되어야 함
        self.assertEqual(self.distribution.reveal_phase, CardDistribution.RevealPhase.FULLY_REVEALED)

    @patch('card.models.CardDistribution.is_okay_to_reveal_assertive')
    @patch('card.models.CardDistribution.is_okay_to_reveal_soft')
    @patch('card.models.CardDistribution.is_okay_to_reveal_hard')
    def test_update_reveal_phase_both_fail(self, mock_hard, mock_soft, mock_assertive):
        """
        soft와 hard condition 모두 실패할 경우 update_reveal_phase 메서드 테스트합니다.
        - assertive는 통과하지만 soft, hard 모두 실패하면 reveal_phase가 변경되지 않아야 함
        """
        # 초기 설정
        self.distribution.reveal_phase = CardDistribution.RevealPhase.HIDDEN
        
        # assertive condition 통과, soft와 hard condition 모두 실패
        mock_assertive.__get__ = MagicMock(return_value=True)
        mock_soft.__get__ = MagicMock(return_value=False)
        mock_hard.__get__ = MagicMock(return_value=False)
        
        # 메서드 실행
        self.distribution.update_reveal_phase()
        
        # reveal_phase가 변경되지 않아야 함
        self.assertEqual(self.distribution.reveal_phase, CardDistribution.RevealPhase.HIDDEN)

    @patch('card.models.CardDistribution.is_okay_to_reveal_assertive')
    @patch('card.models.CardDistribution.is_okay_to_reveal_soft')
    @patch('card.models.CardDistribution.is_okay_to_reveal_hard')
    def test_update_reveal_phase_already_revealed(self, mock_hard, mock_soft, mock_assertive):
        """
        이미 완전히 공개된 경우 update_reveal_phase 메서드 테스트합니다.
        - 이미 FULLY_REVEALED 상태라면 어떤 조건이든 상관없이 상태가 유지되어야 함
        """
        # 초기 설정 - 이미 완전히 공개된 상태
        self.distribution.reveal_phase = CardDistribution.RevealPhase.FULLY_REVEALED
        
        # 모든 조건 통과하도록 설정 (사실 호출되지 않을 것임)
        mock_assertive.__get__ = MagicMock(return_value=True)
        mock_soft.__get__ = MagicMock(return_value=True)
        mock_hard.__get__ = MagicMock(return_value=True)
        
        # 메서드 실행
        self.distribution.update_reveal_phase()
        
        # reveal_phase가 그대로 FULLY_REVEALED 유지
        self.assertEqual(self.distribution.reveal_phase, CardDistribution.RevealPhase.FULLY_REVEALED)
        
        # assertive 조건이 확인되지 않아야 함 (이미 FULLY_REVEALED이므로)
        mock_assertive.__get__.assert_not_called()
