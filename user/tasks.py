from logging import Logger
from typing import Optional

from uuid import UUID
from celery import shared_task
from celery.utils.log import get_task_logger
from django.db.models import Q
from django.utils import timezone

from flitz.apns import APNS
from user.models import User, PushNotificationType
from user_auth.models import UserSession

logger: Logger = get_task_logger(__name__)

@shared_task
def send_push_message(user_id: UUID, type: PushNotificationType, title: str, body: str, data: Optional[dict]=None, thread_id: Optional[str]=None, mutable_content: bool=False):
    user = User.objects.get(id=user_id)
    user.send_push_message(type, title, body, data, thread_id=thread_id, mutable_content=mutable_content)

@shared_task
def wake_up_apps():
    """
    모든 사용자의 액티브한 세션에 앱을 깨우는 푸시 메시지를 보냅니다.
    """

    logger.info("wake_up_apps(): sending silent push to wake up apps...")

    apns = APNS.default()

    batch_size = 250

    sessions_to_wake = UserSession.objects.filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),

        apns_token__isnull=False,
        invalidated_at__isnull=True,
    )

    token_iterator = sessions_to_wake.values_list('apns_token', flat=True).iterator(chunk_size=batch_size)

    batch_tokens = []
    total_processed = 0
    batch_count = 0

    for token in token_iterator:
        batch_tokens.append(token)

        if len(batch_tokens) >= batch_size:
            try:
                apns.send_silent_push(
                    device_tokens=batch_tokens,
                    user_info={
                        'type': 'wake_up',
                    }
                )

                batch_count += 1
                total_processed += len(batch_tokens)
                logger.info(f"wake_up_apps(): sent silent push to {len(batch_tokens)} tokens in batch {batch_count}. Total processed: {total_processed}")
            except Exception as e:
                logger.error(f"wake_up_apps(): error sending silent push: {e}")

            batch_tokens = []

    # 마지막 배치 처리
    if batch_tokens:
        try:
            apns.send_silent_push(
                device_tokens=batch_tokens,
                user_info={
                    'type': 'wake_up',
                }
            )

            batch_count += 1
            total_processed += len(batch_tokens)
            logger.info(f"wake_up_apps(): sent silent push to {len(batch_tokens)} tokens in final batch {batch_count}. Total processed: {total_processed}")
        except Exception as e:
            logger.error(f"wake_up_apps(): error sending silent push for final batch: {e}")
