import logging
from datetime import timedelta

import sentry_sdk
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from location.chronowave import ChronoWaveMatcher
from location.models import UserLocationHistory

logger: logging.Logger = get_task_logger(__name__)

@shared_task
def perform_chronowave_match_all():
    BATCH_SIZE = 50

    queryset = ChronoWaveMatcher.geohashes_queryset()

    iterator = queryset.iterator(chunk_size=BATCH_SIZE)

    for geohash in iterator:
        perform_chronowave_match.delay(geohash)

@shared_task(bind=True, max_retries=3)
def perform_chronowave_match(self, geohash: str):
    try:
        matcher = ChronoWaveMatcher(geohash)

        logger.debug(f"Starting ChronoWave matching for geohash: {geohash}")
        matcher.execute()
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        raise self.retry(exc=exc, countdown=60)

@shared_task
def flush_location_history(max_history_per_user: int = 5, max_age_hours: int = 72):
    """
    사용자별 위치 기록을 정리합니다.

    ChronoWave 기능을 위해 최근 위치 기록을 유지하되,
    불필요하게 많은 기록이나 오래된 기록은 삭제합니다.

    Args:
        max_history_per_user: 각 사용자당 유지할 최대 위치 기록 개수 (기본값: 5)
        max_age_hours: 위치 기록을 유지할 최대 시간 (시간 단위, 기본값: 72시간 = 3일)
    """

    logger.info(f"Starting location history flush. Max history per user: {max_history_per_user}, Max age: {max_age_hours} hours")

    total_deleted = 0
    users_processed = 0

    try:
        with transaction.atomic():
            # 1. 오래된 기록 삭제 (max_age_hours보다 오래된 기록)
            cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
            old_records = UserLocationHistory.objects.filter(
                created_at__lt=cutoff_time
            )
            old_count = old_records.count()
            if old_count > 0:
                old_records.delete()
                total_deleted += old_count
                logger.info(f"Deleted {old_count} location history records older than {max_age_hours} hours")

            # 2. 각 사용자별로 최신 N개만 유지
            # 사용자별 위치 기록 개수를 카운트
            user_history_counts = (
                UserLocationHistory.objects
                .values('user')
                .annotate(count=Count('id'))
                .filter(count__gt=max_history_per_user)
            )

            for user_data in user_history_counts:
                user_id = user_data['user']

                # 해당 사용자의 최신 max_history_per_user개를 제외한 나머지 ID 가져오기
                ids_to_keep = list(
                    UserLocationHistory.objects
                    .filter(user_id=user_id)
                    .order_by('-created_at')
                    .values_list('id', flat=True)[:max_history_per_user]
                )

                # 유지할 ID를 제외한 나머지 삭제
                deleted = UserLocationHistory.objects.filter(
                    user_id=user_id
                ).exclude(
                    id__in=ids_to_keep
                ).delete()[0]

                if deleted > 0:
                    total_deleted += deleted
                    users_processed += 1
                    logger.debug(f"Deleted {deleted} excess location history records for user {user_id}")

        logger.info(
            f"Location history flush completed. "
            f"Total deleted: {total_deleted} records, "
            f"Users processed: {users_processed}"
        )

        return {
            'total_deleted': total_deleted,
            'users_processed': users_processed,
            'status': 'success'
        }

    except Exception as e:
        logger.error(f"Error during location history flush: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }