from django.db import transaction
from django.utils import timezone

from card.models import CardDistribution
from location.models import DiscoverySession, DiscoveryHistory
from location.utils.timezone import get_today_start_in_timezone
from user.models import User


class UserMatcher:

    def __init__(self, discoverer: DiscoverySession, discovered: DiscoverySession):
        self.discoverer = discoverer
        self.discovered = discovered

    def __prev_discover_history_exists(self) -> bool:
        """
        오늘 하루동안 같은 사람을 발견한 기록이 있는지 확인합니다.
        """

        # 사용자의 위치 정보로부터 시간대를 결정합니다
        discoverer_timezone = self.discoverer.user.location.timezone_obj

        # 해당 시간대의 '오늘' 시작 시간을 계산합니다
        discoverer_today_start = get_today_start_in_timezone(discoverer_timezone)

        # 오늘 하루동안 같은 사람을 발견한 기록이 있는지 확인합니다.
        prev_discover_history = self.discoverer.discovered.filter(
            created_at__gt=discoverer_today_start
        )

        return prev_discover_history.exists()

    def __create_discover_history(self) -> DiscoveryHistory:
        """
        서로 발견한 사용자를 기록합니다.
        """

        discoverer_location = self.discoverer.user.location

        return DiscoveryHistory.objects.create(
            session=self.discoverer,
            discovered=self.discovered,

            latitude=discoverer_location.latitude,
            longitude=discoverer_location.longitude,
            altitude=discoverer_location.altitude,

            accuracy=discoverer_location.accuracy
        )


    def __is_nearby(self) -> bool:
        """
        서로가 가까이에 있는지 확인합니다. 가까이 있어야만 매칭이 가능합니다.

        :note: 네트워크 조작을 통한 가짜 매칭을 방지하기 위한 조건입니다.
        """
        pass


    def __distribute_card(self, from_user: User, to_user: User, history: DiscoveryHistory):
        """
        사용자의 main_card를 상대편에게 배포합니다.
        """

        already_distributed = from_user.main_card.distributions.filter(
            user=to_user
        ).exists()

        if already_distributed:
            return

        distribution = CardDistribution.objects.create(
            card=from_user.main_card,
            user=to_user,

            latitude=history.latitude,
            longitude=history.longitude,
            altitude=history.altitude,
            accuracy=history.accuracy
        )

        return distribution

    def sanity_check(self) -> bool:
        """
        sanity check: 정상적으로 매칭이 가능한 상태인지 확인합니다.
         - 서로가 가까이에 있어야 합니다.
         - 서로가 '메인 카드'를 등록해 두어야 합니다.

         # TODO: return reason for sanity check failure
        """

        if self.discoverer.user.main_card is None or self.discovered.user.main_card is None:
            # TODO: Sentry.capture_message('FlitzWave: main card not found')
            return False

        if not self.__is_nearby():
            return False

        return True

    def try_match(self) -> bool:
        """
        매칭을 시도합니다.
        """

        with transaction.atomic():
            if self.__prev_discover_history_exists():
                # 이미 오늘 하루동안 같은 사람을 발견한 기록이 있으므로 무시합니다.
                # (= 이제 상대편이 나를 발견할 때까지 기다립니다.)
                return False

            # 나(discoverer)가 상대편(discovered)을 발견한 기록을 생성합니다.
            history_self = self.__create_discover_history()

            # 30분 이내에 서로를 발견했는지 확인 (사용자의 현지 시간대 기준)
            discoverer_timezone = self.discoverer.user.location.timezone_obj
            time_threshold = timezone.now().astimezone(discoverer_timezone) - timezone.timedelta(minutes=30)

            # 반대로, 상대편(discovered)이 나(discoverer)를 발견했는지 확인합니다.
            history_opponent_qs = DiscoveryHistory.objects.filter(
                session=self.discovered,
                discovered=self.discoverer,
                created_at__gt=time_threshold
            )

            if history_opponent_qs.exists():
                # 서로를 발견했습니다! 축하합니다.
                history_opponent = history_opponent_qs.first()

                self.__finalize_match(history_self, history_opponent)
                return True

            return False

    def __finalize_match(self, history_self: DiscoveryHistory, history_opponent: DiscoveryHistory):
        """
        매칭을 완료합니다.
        """

        with transaction.atomic():
            # 서로를 발견하였으므로 카드를 교환합니다.
            user_a = history_self.session.user
            user_b = history_opponent.session.user

            # user_a와 user_b의 카드를 교환합니다.
            self.__distribute_card(user_a, user_b, history_self)
            self.__distribute_card(user_b, user_a, history_opponent)

