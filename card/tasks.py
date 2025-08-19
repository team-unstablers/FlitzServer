from logging import Logger

from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, F
from django.utils import timezone

from card.models import Card, UserCardAsset, CardDistribution

logger: Logger = get_task_logger(__name__)

@shared_task
def perform_gc_asset_references():
    """
    모든 사용자 카드의 애셋 (이미지, 동영상, ...) 등에 대한 가비지 컬렉션을 수행합니다.
    """

    # 300개씩 묶어서 처리합니다.
    CHUNK_SIZE = 300

    logger.info('perform_gc_asset_references task started')

    dirty_cards_queryset = Card.objects.filter(
        # GC가 한번도 실행되지 않았거나, 마지막 GC 실행 이후 카드가 업데이트된 경우
        Q(gc_ran_at__isnull=True) | Q(gc_ran_at__lt=F('updated_at')),
        deleted_at__isnull=True,
        banned_at__isnull=True
        # 'asset_references'를 미리 prefetch한다.
    ).prefetch_related('asset_references')

    iterator = dirty_cards_queryset.iterator(chunk_size=CHUNK_SIZE)

    for card in iterator:
        with transaction.atomic():
            try:
                card.remove_orphaned_assets()
                card.gc_ran_at = timezone.now()
                card.save(update_fields=['gc_ran_at'])
            except Exception as e:
                # TODO: Log to sentry
                logger.error(f"Error while performing GC on card {card.id}: {e}", exc_info=True)
                continue

    logger.info('perform_gc_asset_references task completed')

@shared_task
def update_distribution_reveal_phase():
    """
    카드 배포의 공개 단계 (reveal phase)를 업데이트합니다.
    5분에 한번씩 실행합니다.
    """

    if cache.get('update_distribution_reveal_phase_lock', None):
        logger.info('update_distribution_reveal_phase task is already running, skipping this run')
        return

    # 락을 걸어 중복 실행 방지
    cache.set('update_distribution_reveal_phase_lock', True, timeout=60 * 15) # 15분 동안 락 유지

    try:
        # 300개씩 묶어서 처리합니다.
        CHUNK_SIZE = 300

        logger.info('update_distribution_reveal_phase task started')

        queryset = CardDistribution.objects.filter(
            ~Q(reveal_phase=CardDistribution.RevealPhase.FULLY_REVEALED),
            dismissed_at__isnull=True,
            deleted_at__isnull=True,
        ).select_related(
            'card',
            'card__user',
            'card__user__location',
            'user__location',
         )

        iterator = queryset.iterator(chunk_size=CHUNK_SIZE)
        changed_instances = []

        # 통계용 카운터
        total_count = 0
        updated_count = 0
        error_count = 0

        for distribution in iterator:
            total_count += 1
            try:
                # 변경 전 상태 저장
                old_phase = distribution.reveal_phase
                old_deleted_at = distribution.deleted_at

                # reveal phase 업데이트 (save는 안 함)
                distribution.update_reveal_phase()

                # 실제로 변경되었는지 확인
                if (distribution.reveal_phase != old_phase or
                    distribution.deleted_at != old_deleted_at):
                    changed_instances.append(distribution)
                    updated_count += 1

                    # 메모리 절약을 위해 CHUNK_SIZE만큼 쌓이면 중간에 bulk_update
                    if len(changed_instances) >= CHUNK_SIZE:
                        CardDistribution.objects.bulk_update(
                            changed_instances,
                            ['reveal_phase', 'deleted_at', 'updated_at'],
                            batch_size=CHUNK_SIZE
                        )
                        changed_instances.clear()  # 리스트 비우기

            except Exception as e:
                error_count += 1
                # TODO: Log to sentry
                logger.error(f"Error while updating reveal phase for distribution {distribution.id}: {e}", exc_info=True)
                continue

        # 남은 인스턴스들 처리
        if changed_instances:
            CardDistribution.objects.bulk_update(
                changed_instances,
                ['reveal_phase', 'deleted_at', 'updated_at'],
                batch_size=CHUNK_SIZE
            )

        logger.info(
            f'update_distribution_reveal_phase task completed: '
            f'total={total_count}, updated={updated_count}, errors={error_count}'
        )
    finally:
        # 락 해제
        cache.delete('update_distribution_reveal_phase_lock')
        logger.info('update_distribution_reveal_phase lock released')
