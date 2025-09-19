from typing import Tuple

from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from freezegun import freeze_time

from card.models import CardDistribution, Card
from card.tasks import send_card_distribution_notification
from location.models import UserLocation
from user.models import User

from flitz.test_utils import (
    create_test_user, create_test_card,
    create_test_user_location, create_complete_test_user
)


class CardDistributionNotificationTestCase(TestCase):

    LOCATION_시청역_서울광장 = (37.565528, 126.977986)

    def __create_user(self, identifier: int) -> User:
        user = User.objects.create(
            username=f'user_{identifier}',
            password='testpass123',
            display_name=f'User #{identifier}'
        )

        card = Card.objects.create(
            user=user,
            title=f'Card of User #{identifier}',
            content={'test': f'content_{identifier}'},
        )

        user.main_card = card
        user.save()

        return user

    def __setup_location(self, user: User, latlon: Tuple[float, float]) -> UserLocation:
        user.update_location(latlon[0], latlon[1], 0, 0, True)
        user.save()

    def setUp(self):
        self.user1 = self.__create_user(1)
        self.user2 = self.__create_user(2)


    def test_basic(self):
        with freeze_time("2024-06-01 09:00:00"):
            self.__setup_location(self.user1, self.LOCATION_시청역_서울광장)
            self.__setup_location(self.user2, self.LOCATION_시청역_서울광장)

            # CardDistribution 생성 시 reveal_phase를 FULLY_REVEALED로 설정
            dist1 = CardDistribution.objects.create(
                card=self.user1.main_card,
                user=self.user2,
                reveal_phase=CardDistribution.RevealPhase.FULLY_REVEALED
            )

            dist2 = CardDistribution.objects.create(
                card=self.user2.main_card,
                user=self.user1,
                reveal_phase=CardDistribution.RevealPhase.FULLY_REVEALED
            )

        # 서울 시간대 (GMT+9)로 오후 7시 설정
        with freeze_time("2024-06-01 10:00:00"):  # UTC 10:00 = KST 19:00
            # Celery task의 delay 메서드를 mock
            with patch('card.tasks.send_push_message_ex.delay') as mock_delay:
                send_card_distribution_notification()

                # 두 번 호출되었는지 확인 (user1, user2 각각)
                self.assertEqual(mock_delay.call_count, 2)

                # 호출된 인자들 확인
                calls = mock_delay.call_args_list
                user_ids = [call[0][0] for call in calls]

                # 두 사용자 모두에게 알림이 갔는지 확인
                self.assertIn(self.user1.id, user_ids)
                self.assertIn(self.user2.id, user_ids)

                # 첫 번째 호출 인자 상세 검증
                first_call = calls[0]
                self.assertEqual(first_call[1]['type'], 'match')
                self.assertIn('개의 카드가 교환되었어요', first_call[1]['aps']['alert']['body'])

    def test_only_fully_revealed_cards_trigger_notification(self):
        """HIDDEN이나 BLURRY_SOFT 상태의 카드는 알림 개수에 포함되지 않아야 함"""
        with freeze_time("2024-06-01 10:00:00"):
            self.__setup_location(self.user1, self.LOCATION_시청역_서울광장)

            # HIDDEN 상태 카드
            CardDistribution.objects.create(
                card=self.user2.main_card,
                user=self.user1,
                reveal_phase=CardDistribution.RevealPhase.HIDDEN
            )

        with freeze_time("2024-06-01 10:00:00"):  # UTC 10:00 = KST 19:00
            with patch('card.tasks.send_push_message_ex.delay') as mock_delay:
                send_card_distribution_notification()

                # HIDDEN 카드만 있으므로 알림이 가지 않아야 함
                self.assertEqual(mock_delay.call_count, 0)

    # def test_different_timezone(self):
    #     """다른 타임존에서의 알림 테스트"""
    #     import pytz

    #     with freeze_time("2024-06-01 10:00:00"):
    #         # 사용자1은 서울 (UTC+9)
    #         self.__setup_location(self.user1, self.LOCATION_시청역_서울광장)

    #         # 사용자2는 도쿄 (UTC+9) - 같은 시간대
    #         self.user2.update_location(35.6762, 139.6503, 0, 0, True)  # 도쿄 좌표
    #         self.user2.save()

    #         CardDistribution.objects.create(
    #             card=self.user1.main_card,
    #             user=self.user2,
    #             reveal_phase=CardDistribution.RevealPhase.FULLY_REVEALED
    #         )

    #     # UTC 10:00 = KST/JST 19:00
    #     with freeze_time("2024-06-01 10:00:00"):
    #         with patch('card.tasks.send_push_message_ex.delay') as mock_delay:
    #             send_card_distribution_notification()

    #             # 두 사용자 모두 19시 타임존에 있으므로 알림이 가야 함
    #             self.assertEqual(mock_delay.call_count, 1)






