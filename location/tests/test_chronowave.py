from typing import List, Tuple

from django.test import TransactionTestCase
from freezegun import freeze_time


from user.models import User, UserIdentity, UserGenderBit
from card.models import Card, CardDistribution
from location.models import DiscoverySession, DiscoveryHistory, UserLocation
from location.chronowave import ChronoWaveMatcher
from safety.models import UserWaveSafetyZone

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

    def test_safety_zone_respect(self):
        """
        테스트 케이스 #4 - Safety Zone 존중

        - Safety Zone이 설정된 사용자가 해당 구역 내에 있을 때는 ChronoWave 매칭에서 제외되어야 합니다.
        - Safety Zone 밖에 있을 때는 정상적으로 매칭되어야 합니다.
        """

        # test_user_gay_1에 대해 종로 탑골공원을 중심으로 500m 반경의 safety zone 설정
        safety_zone = UserWaveSafetyZone.objects.create(
            user=self.test_user_gay_1,
            latitude=self.LOCATION_종로_탑골공원[0],
            longitude=self.LOCATION_종로_탑골공원[1],
            radius=500,  # 500m 반경
            is_enabled=True,
            enable_wave_after_exit=True
        )

        with freeze_time("2025-02-03 14:00:00"):
            # test_user_gay_1이 safety zone 내에 위치
            self.__setup_location(self.test_user_gay_1, latlon=self.LOCATION_종로_누누)  # 종로 탑골공원에서 가까움
            # test_user_gay_2도 같은 지역에 위치
            self.__setup_location(self.test_user_gay_2, latlon=self.LOCATION_종로_탑골공원)
            # test_user_pansexual_man도 같은 지역에 위치
            self.__setup_location(self.test_user_pansexual_man, latlon=self.LOCATION_종로_누누)

        with freeze_time("2025-02-03 14:30:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # test_user_gay_1은 safety zone 내에 있으므로 매칭되지 않아야 한다
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_gay_1, self.test_user_gay_2))
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_gay_1, self.test_user_pansexual_man))

            # 하지만 test_user_gay_2와 test_user_pansexual_man은 서로 매칭되어야 한다
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_2, self.test_user_pansexual_man))

        # 기존 카드 배포 삭제 (다음 테스트를 위해)
        CardDistribution.objects.all().delete()

        with freeze_time("2025-02-03 15:00:00"):
            # test_user_gay_1이 safety zone 밖으로 이동
            self.__setup_location(self.test_user_gay_1, latlon=self.LOCATION_시청역_서울광장)  # 종로에서 멀리 떨어짐
            # 다른 사용자도 시청역 근처로 이동
            self.__setup_location(self.test_user_gay_2, latlon=self.LOCATION_시청역_플라자호텔)

        with freeze_time("2025-02-03 15:30:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_시청역)
            matcher.execute()

            # 이제 test_user_gay_1은 safety zone 밖에 있으므로 정상적으로 매칭되어야 한다
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_gay_2))

    def test_safety_zone_with_location_history(self):
        """
        테스트 케이스 #5 - Safety Zone과 LocationHistory

        - LocationHistory에서 is_in_safety_zone 플래그가 제대로 설정되고
        - ChronoWave 매칭에서 이를 존중하는지 확인합니다.
        """

        # test_user_lesbian_1에 대해 종로 탑골공원을 중심으로 1km 반경의 safety zone 설정
        safety_zone = UserWaveSafetyZone.objects.create(
            user=self.test_user_lesbian_1,
            latitude=self.LOCATION_종로_탑골공원[0],
            longitude=self.LOCATION_종로_탑골공원[1],
            radius=1000,  # 1km 반경
            is_enabled=True,
            enable_wave_after_exit=True
        )

        with freeze_time("2025-02-03 10:00:00"):
            # test_user_lesbian_1이 여러 위치를 이동하며 기록 생성
            self.__setup_location(self.test_user_lesbian_1, latlon=self.LOCATION_종로_탑골공원)  # safety zone 내
            self.__setup_location(self.test_user_lesbian_2, latlon=self.LOCATION_종로_누누)

        with freeze_time("2025-02-03 11:00:00"):
            self.__setup_location(self.test_user_lesbian_1, latlon=self.LOCATION_종로_누누)  # safety zone 내
            self.__setup_location(self.test_user_bisexual_mtf, latlon=self.LOCATION_종로_탑골공원)

        with freeze_time("2025-02-03 12:00:00"):
            self.__setup_location(self.test_user_lesbian_1, latlon=self.LOCATION_시청역_서울광장)  # safety zone 밖

        # LocationHistory 확인
        from location.models import UserLocationHistory

        lesbian_1_histories = UserLocationHistory.objects.filter(
            user=self.test_user_lesbian_1
        ).order_by('created_at')

        # safety zone 내의 기록들은 is_in_safety_zone=True여야 함
        for history in lesbian_1_histories[:2]:
            self.assertTrue(history.is_in_safety_zone, f"Location at {history.latitude}, {history.longitude} should be in safety zone")

        # safety zone 밖의 기록은 is_in_safety_zone=False여야 함
        if lesbian_1_histories.count() > 2:
            self.assertFalse(lesbian_1_histories[2].is_in_safety_zone, "Location at 시청역 should not be in safety zone")

        with freeze_time("2025-02-03 12:30:00"):
            # 종로 지역에서 ChronoWave 매칭 실행
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # test_user_lesbian_1의 종로 지역 기록은 모두 safety zone 내에 있으므로 매칭되지 않아야 함
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_lesbian_1, self.test_user_lesbian_2))
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_lesbian_1, self.test_user_bisexual_mtf))

            # 하지만 test_user_lesbian_2와 test_user_bisexual_mtf는 서로 매칭되어야 함
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_lesbian_2, self.test_user_bisexual_mtf))

    def test_block_relationship(self):
        """
        테스트 케이스 #6 - Block 관계 존중

        - Block 관계에 있는 사용자들은 ChronoWave 매칭에서 제외되어야 합니다.
        - 단방향 차단과 양방향 차단 모두 테스트합니다.
        """
        from safety.models import UserBlock

        with freeze_time("2025-02-03 14:00:00"):
            # 모든 사용자를 종로 지역에 위치시킴
            self.__setup_location(self.test_user_gay_1, latlon=self.LOCATION_종로_탑골공원)
            self.__setup_location(self.test_user_gay_2, latlon=self.LOCATION_종로_누누)
            self.__setup_location(self.test_user_pansexual_man, latlon=self.LOCATION_종로_탑골공원)
            self.__setup_location(self.test_user_bisexual_mtf, latlon=self.LOCATION_종로_누누)

        # 케이스 1: test_user_gay_1이 test_user_gay_2를 차단
        block_1_to_2 = UserBlock.objects.create(
            user=self.test_user_gay_2,
            blocked_by=self.test_user_gay_1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )

        with freeze_time("2025-02-03 14:30:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # test_user_gay_1과 test_user_gay_2는 차단 관계이므로 매칭되지 않아야 함
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_gay_1, self.test_user_gay_2))

            # 차단 관계가 없는 다른 사용자들끼리는 정상적으로 매칭되어야 함
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_pansexual_man))
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_2, self.test_user_pansexual_man))

        # 기존 카드 배포 삭제 (다음 테스트를 위해)
        CardDistribution.objects.all().delete()
        block_1_to_2.delete()

        # 케이스 2: test_user_gay_2가 test_user_gay_1을 차단 (반대 방향)
        block_2_to_1 = UserBlock.objects.create(
            user=self.test_user_gay_1,
            blocked_by=self.test_user_gay_2,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )

        with freeze_time("2025-02-03 15:00:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # 여전히 test_user_gay_1과 test_user_gay_2는 매칭되지 않아야 함
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_gay_1, self.test_user_gay_2))

            # 차단 관계가 없는 다른 사용자들끼리는 정상적으로 매칭되어야 함
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_pansexual_man))
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_2, self.test_user_pansexual_man))

        # 기존 카드 배포 삭제 (다음 테스트를 위해)
        CardDistribution.objects.all().delete()

        # 케이스 3: 양방향 차단 (서로를 차단)
        block_1_to_2_again = UserBlock.objects.create(
            user=self.test_user_gay_2,
            blocked_by=self.test_user_gay_1,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_USER
        )
        # block_2_to_1은 이미 존재

        with freeze_time("2025-02-03 15:30:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # 양방향 차단 상태에서도 매칭되지 않아야 함
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_gay_1, self.test_user_gay_2))

            # 차단 관계가 없는 다른 사용자들끼리는 정상적으로 매칭되어야 함
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_pansexual_man))
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_2, self.test_user_pansexual_man))

        # 기존 카드 배포 삭제 (다음 테스트를 위해)
        CardDistribution.objects.all().delete()
        block_1_to_2_again.delete()
        block_2_to_1.delete()

        # 케이스 4: 트리거에 의한 차단도 동일하게 작동해야 함
        block_trigger = UserBlock.objects.create(
            user=self.test_user_bisexual_mtf,
            blocked_by=self.test_user_pansexual_man,
            type=UserBlock.Type.BLOCK,
            reason=UserBlock.Reason.BY_TRIGGER  # 연락처 트리거에 의한 차단
        )

        with freeze_time("2025-02-03 16:00:00"):
            matcher = ChronoWaveMatcher(self.GEOHASH_종로)
            matcher.execute()

            # 트리거에 의한 차단도 일반 차단과 동일하게 작동해야 함
            self.assertFalse(self.is_card_distributed_mutual_or(self.test_user_bisexual_mtf, self.test_user_pansexual_man))

            # 차단 관계가 없는 다른 사용자들끼리는 정상적으로 매칭되어야 함
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_gay_2))
            self.assertTrue(self.is_card_distributed_mutual(self.test_user_gay_1, self.test_user_pansexual_man))
