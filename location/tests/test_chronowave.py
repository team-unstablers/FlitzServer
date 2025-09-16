from typing import List, Tuple

from django.test import TransactionTestCase
from freezegun import freeze_time


from user.models import User, UserIdentity, UserGenderBit
from card.models import Card, CardDistribution
from location.models import DiscoverySession, DiscoveryHistory, UserLocation
from location.chronowave import ChronoWaveMatcher

class ChronoWaveMatcherTest(TransactionTestCase):

    GENDER_MAN = 1
    GENDER_WOMAN = 2
    GENDER_NON_BINARY = 4

    PREFERENCE_GAY = 1
    PREFERENCE_LESBIAN = 2
    PREFERENCE_BISEXUAL = (1 | 2)
    PREFERENCE_PANSEXUAL = (1 | 2 | 4)

    GEOHASH_시청역 = 'wydm9q'

    GEOHASH_종로 = 'wydm9x'
    GEOHASH_종각_교보문고_광화문점 = 'wydm9r'

    # wydm9q
    LOCATION_시청역_서울광장 = (37.565528, 126.977986)
    # wydm9q
    LOCATION_시청역_플라자호텔 = (37.564580, 126.977893)

    # wydm9x
    LOCATION_종로_탑골공원 = (37.571179, 126.988263)
    # wydm9x
    LOCATION_종로_누누 = (37.571023, 126.989796)
    # wydm9r
    LOCATION_종각_교보문고_광화문점 = (37.570770, 126.977861)

    test_user_gay_1: User
    test_user_gay_2: User
    test_user_lesbian_1: User
    test_user_lesbian_2: User
    test_user_bisexual_mtf: User
    test_user_pansexual_man: User

    def __create_user(self, identifier: int, gender_ident: int, pref_gender: int, is_trans: bool, welcomes_trans: bool) -> User:
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

        identity = UserIdentity.objects.create(
            user=user,
            gender=gender_ident,
            preferred_genders=pref_gender,
            is_trans=is_trans,
            welcomes_trans=welcomes_trans,
        )

        user.main_card = card
        user.save()

        return user

    def __setup_location(self, user: User, latlon: Tuple[float, float]) -> UserLocation:
        user.update_location(latlon[0], latlon[1], 0, 0, True)
        user.save()

    def is_card_distributed(self, from_user: User, to_user: User) -> bool:
        return CardDistribution.objects.filter(card=from_user.main_card, user=to_user).exists()

    def is_card_distributed_mutual(self, from_user: User, to_user: User) -> bool:
        return self.is_card_distributed(from_user, to_user) and self.is_card_distributed(to_user, from_user)

    def is_card_distributed_mutual_or(self, from_user: User, to_user: User) -> bool:
        return self.is_card_distributed(from_user, to_user) or self.is_card_distributed(to_user, from_user)

    def setUp(self):
        # 테스트 사용자 #1: 시스젠더 남성, 남성 선호, 트랜스젠더 환영
        self.test_user_gay_1 = self.__create_user(
            identifier=1,
            gender_ident=self.GENDER_MAN,
            pref_gender=self.PREFERENCE_GAY,
            is_trans=False,
            welcomes_trans=True
        )

        self.test_user_gay_2 = self.__create_user(
            identifier=2,
            gender_ident=self.GENDER_MAN,
            pref_gender=self.PREFERENCE_GAY,
            is_trans=False,
            welcomes_trans=True
        )

        # 테스트 사용자 #3: 시스젠더 여성, 여성 선호, 트랜스젠더 환영
        self.test_user_lesbian_1 = self.__create_user(
            identifier=3,
            gender_ident=self.GENDER_WOMAN,
            pref_gender=self.PREFERENCE_LESBIAN,
            is_trans=False,
            welcomes_trans=True
        )

        self.test_user_lesbian_2 = self.__create_user(
            identifier=4,
            gender_ident=self.GENDER_WOMAN,
            pref_gender=self.PREFERENCE_LESBIAN,
            is_trans=False,
            welcomes_trans=True
        )

        # NOTE: 작업 도중에 헷갈리지 않기 위해 '트랜스젠더 남성/여성' 대신 'FTM/MTF' 용어를 사용합니다. (혹시 실례가 된다면 알려주세요)
        # 테스트 사용자 #5: MTF, 바이섹슈얼, 트랜스젠더 환영
        self.test_user_bisexual_mtf = self.__create_user(
            identifier=5,
            gender_ident=self.GENDER_WOMAN,
            pref_gender=self.PREFERENCE_BISEXUAL,
            is_trans=True,
            welcomes_trans=True
        )

        # 테스트 사용자 #6: 시스젠더 남성, 판섹슈얼, 트랜스젠더 환영
        self.test_user_pansexual_man = self.__create_user(
            identifier=6,
            gender_ident=self.GENDER_MAN,
            pref_gender=self.PREFERENCE_PANSEXUAL,
            is_trans=False,
            welcomes_trans=True
        )

    def test_basic(self):
        """
        테스트 케이스 #1 - 기본적인 매칭 시나리오

        - 같은 영역에 있는 서로의 카드가 교환되어야 합니다.
        - 단, 성별 및 선호도에 따른 매칭 규칙이 적용되어야 합니다.
        """

        self.__setup_location(self.test_user_gay_1, latlon=self.LOCATION_종로_누누)
        self.__setup_location(self.test_user_gay_2, latlon=self.LOCATION_종로_탑골공원)
        self.__setup_location(self.test_user_lesbian_1, latlon=self.LOCATION_종로_탑골공원)
        self.__setup_location(self.test_user_pansexual_man, latlon=self.LOCATION_종각_교보문고_광화문점)

        matcher = ChronoWaveMatcher(self.GEOHASH_종로)
        matcher.execute()

        # 게이 남성 2명 간 서로 카드가 교환되어야 한다
        self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_gay_2))

        # 레즈비언 여성과 게이 남성 간에는 카드가 교환되지 않아야 한다
        self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_lesbian_1, self.test_user_gay_1))
        self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_lesbian_1, self.test_user_gay_2))

        # 다른 구역에 있는 사용자는 카드가 교환되지 않아야 한다
        self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_pansexual_man, self.test_user_gay_1))
        self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_pansexual_man, self.test_user_gay_2))
        self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_pansexual_man, self.test_user_lesbian_1))

    def test_time_lag(self):
        """
        테스트 케이스 #2 - 시간 차이에 따른 매칭

        - 같은 영역에 있더라도, 너무 오래된 위치 정보는 무시되어야 합니다.
        """

        with freeze_time("2025-02-03 09:00:00"):
            self.__setup_location(self.test_user_gay_1, latlon=self.LOCATION_종로_누누)

        with freeze_time("2025-02-03 14:31:23"):
            self.__setup_location(self.test_user_gay_2, latlon=self.LOCATION_종로_누누)

        with freeze_time("2025-02-03 15:29:10"):
            self.__setup_location(self.test_user_pansexual_man, latlon=self.LOCATION_종로_탑골공원)

        with freeze_time("2025-02-03 15:45:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # test_user_gay_2와 test_user_pansexual_man만 매칭되어야 한다
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_2, self.test_user_pansexual_man))

            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_gay_1, self.test_user_gay_2))
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_gay_1, self.test_user_pansexual_man))


    def test_time_lag_2(self):
        """
        테스트 케이스 #3 - 시간 차이에 따른 매칭

        - 같은 영역에 한번이라도 방문한 적이 있는 사용자는 매칭 대상이 됩니다.
        """

        with freeze_time("2025-02-03 09:00:00"):
            self.__setup_location(self.test_user_pansexual_man, latlon=self.LOCATION_종로_탑골공원)

        with freeze_time("2025-02-03 14:31:23"):
            self.__setup_location(self.test_user_gay_1, latlon=self.LOCATION_종로_누누)
            self.__setup_location(self.test_user_gay_2, latlon=self.LOCATION_종각_교보문고_광화문점)

        with freeze_time("2025-02-03 15:29:10"):
            self.__setup_location(self.test_user_gay_1, latlon=self.LOCATION_시청역_서울광장)
            self.__setup_location(self.test_user_gay_2, latlon=self.LOCATION_종로_탑골공원)
            self.__setup_location(self.test_user_pansexual_man, latlon=self.LOCATION_시청역_플라자호텔)

        with freeze_time("2025-02-03 15:45:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # test_user_gay_1과 test_user_gay_2가 매칭되어야 한다
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_gay_2))

            # 단, 시간 차가 너무 나는 test_user_pansexual_man과는 매칭되지 않아야 한다
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_pansexual_man, self.test_user_gay_1))
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_pansexual_man, self.test_user_gay_2))
