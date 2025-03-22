from uuid import UUID
from celery import shared_task

from user.models import User
from safety.models import UserBlock, UserContactsTrigger

@shared_task
def evaluate_block_triggers(user_id: UUID):
    """
    사용자의 연락처 기반 차단 트리거를 평가합니다.
    """

    user = User.objects.get(id=user_id)
    queryset = user.contact_triggers.filter(related_object__isnull=True)

    for trigger in queryset.iterator():
        try:
            trigger.perform_block()
        except Exception as e:
            print(e)
            # TODO: Sentry integration
