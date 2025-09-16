import logging
from datetime import timedelta
from typing import Optional

import pygeohash as pgh
import sentry_sdk

from django.db.models import QuerySet, Q
from django.utils import timezone

from card.models import CardDistribution
from location.models import UserLocation, DiscoveryHistory
from user.models import User, UserIdentity


class ChronoWaveMatcher:
    """
    ChronoWave 방식의 매칭을 시도합니다.
    """

    logger: logging.Logger

    geohash: str

    area_latitude: float
    area_longitude: float

    @staticmethod
    def geohashes_queryset():
        """
        returns a queryset of all geohashes in UserLocation model.
        """

        # SELECT DISTINCT geohash FROM user_location WHERE geohash IS NOT NULL AND geohash != '';
        queryset = UserLocation.objects\
            .exclude(geohash__isnull=True)\
            .exclude(geohash='')\
            .values_list('geohash', flat=True)\
            .distinct()

        return queryset

    def __init__(self, geohash: str):
        self.logger = logging.getLogger(__name__)
        self.geohash = geohash

        self.area_latitude, self.area_longitude = pgh.decode(geohash)

    def __distribute_card(self, from_user: User, to_user: User) -> Optional[CardDistribution]:
        already_distributed = from_user.main_card.distributions.only('id').filter(
            user=to_user
        ).exists()

        if already_distributed:
            self.logger.debug(f"[{self.geohash}][{from_user.id} -> {to_user.id}] Card already distributed, skipping...")
            return None

        distribution = from_user.main_card.distributions.create(
            user=to_user,

            latitude=self.area_latitude,
            longitude=self.area_longitude,
            altitude=0,
            accuracy=0,

            distribution_method=CardDistribution.DistributionMethod.CHRONOWAVE,
        )

        distribution.update_reveal_phase()
        distribution.save(update_fields=['reveal_phase', 'deleted_at', 'updated_at'])

        return distribution

    def __try_match(self, user_a: User, user_b: User) -> bool:
        # SANITY CHECK: user_b가 user_a의 조건에 맞는지 다시 한 번 확인
        if not (user_a.identity.is_acceptable(user_b.identity) and user_b.identity.is_acceptable(user_a.identity)):
            # TODO: 쿼리 최적화에 실패한 것이므로 경고 로그를 남기고 넘어간다
            self.logger.warning(
                f'[{self.geohash}] OPTIMIZATION WARNING: sanity check failed for user {user_a.id} and user {user_b.id}')
            return False

        # 매칭 성공!
        self.__distribute_card(user_a, user_b)
        self.__distribute_card(user_b, user_a)

        return True

    def perform_match(self, user_a: User, base_queryset: QuerySet[User]):
        BATCH_SIZE = 300

        identity = user_a.identity

        user_b_queryset = base_queryset.exclude(
            id=user_a.id
        ).filter(
            # (gender & user_a.identity.preferred_genders) != 0
            identity__gender__bitand=identity.preferred_genders,
        ).exclude(
            # user_a를 차단한 사용자는 제외
            blocked_users__id__in=[user_a.id],
        ).exclude(
            # user_a가 차단한 사용자는 제외
            # @claude, is this correct?
            userblock__blocked_by=user_a
        )

        if identity.is_trans and identity.trans_prefers_safe_match:
            # User A가 트랜스젠더이고, 안전한 매칭을 선호하는 경우

            user_b_queryset = user_b_queryset.filter(
                # 매칭 대상은 트랜스젠더 당사자이거나,
                Q(identity__is_trans=True) | \
                # 트랜스젠더에 대해 우호적이어야 한다
                Q(identity__welcomes_trans=True)
            )

        user_b_iterator = user_b_queryset.iterator(chunk_size=BATCH_SIZE)

        for user_b in user_b_iterator:
            try:
                self.__try_match(user_a, user_b)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                self.logger.error(f'[{self.geohash}] Error during matching for users {user_a.id} and {user_b.id}: {e}')

    def execute(self):
        # @claude, should we mark this method as transaction.atomic()?

        BATCH_SIZE = 300

        # 조정 필요
        MAX_DELTA = timedelta(hours=6)
        now = timezone.now()

        # SELECT * FROM user_location WHERE geohash = self.geohash;
        # TODO: exclude(settings__chronowave_enabled=False)
        base_queryset = User.objects.filter(
            location__geohash=self.geohash
        ).exclude(
            # 위치 정보가 너무 오래된 사용자 제외
            location__updated_at__lt=now - MAX_DELTA
        ).select_related('identity', 'main_card')

        if base_queryset.only('id').count() < 2:
            return

        iterator = base_queryset.iterator(chunk_size=BATCH_SIZE)

        for user_a in iterator:
            try:
                self.perform_match(user_a, base_queryset)
            except Exception as e:
                sentry_sdk.capture_exception(e)
                self.logger.error(f'[{self.geohash}] Error during matching for user {user_a.id}: {e}')
