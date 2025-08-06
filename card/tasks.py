from logging import Logger

from celery import shared_task
from celery.utils.log import get_task_logger
from django.db import transaction
from django.db.models import Q, F

from card.models import Card, UserCardAsset

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
                logger.error(f"Error while performing GC on card {card.id}: {e}", exc_info=True)
                continue

    logger.info('perform_gc_asset_references task completed')