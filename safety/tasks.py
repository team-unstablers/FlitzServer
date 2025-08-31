from uuid import UUID
from celery import shared_task
from django.db import transaction

from user.models import User
from safety.models import UserBlock, UserContactsTrigger

@shared_task
def evaluate_block_triggers(user_id: UUID):
    """
    사용자의 연락처 기반 차단 트리거를 평가합니다.
    """

    with transaction.atomic():
        user = User.objects.get(id=user_id)
        hashed_phone_numbers = user.contact_triggers.filter(related_object__isnull=True) \
            .values_list('phone_number_hashed', flat=True)

        if not hashed_phone_numbers:
            return

        block_targets = User.objects.filter(phone_number_hashed__in=hashed_phone_numbers)
        for target in block_targets:
            # 이미 차단된 사용자면 건너뜀
            if target.id == user.id:
                # 자기 자신은 차단할 수 없음
                continue

            if UserBlock.objects.filter(user=target, blocked_by=user).exists():
                continue

            try:
                # 차단 생성
                block_object = UserBlock.objects.create(
                    user=target,
                    blocked_by=user,
                    type=UserBlock.Type.BLOCK,
                    reason=UserBlock.Reason.BY_TRIGGER
                )

                # 트리거와 관련된 객체 업데이트
                trigger = user.contact_triggers.get(phone_number_hashed=target.phone_number_hashed)
                trigger.related_object = block_object

                trigger.save()
            except Exception as e:
                # 예외 발생 시 로깅 또는 처리
                print(f"Error processing block for {target.id}: {e}")
                continue

@shared_task
def reverse_evaluate_block_triggers(user_id: UUID):
    """
    사용자의 연락처 기반 차단 트리거를 평가합니다.
    """

    with transaction.atomic():
        user = User.objects.get(id=user_id)
        if not user.phone_number_hashed:
            return

        hashed_phone_number = user.phone_number_hashed

        queryset = UserContactsTrigger.objects.filter(
            hashed_phone_number=hashed_phone_number
        ).select_related('user')

        iterator = queryset.iterator(chunk_size=100)

        for trigger in iterator:
            if trigger.user == user:
                # 자기 자신은 차단할 수 없음
                continue

            if UserBlock.objects.filter(user=user, blocked_by=trigger.user).only('id').exists():
                continue

            try:
                block_object = UserBlock.objects.create(
                    user=user,
                    blocked_by=trigger.user,
                    type=UserBlock.Type.BLOCK,
                    reason=UserBlock.Reason.BY_TRIGGER
                )

                trigger.related_object = block_object
                trigger.save()
            except Exception as e:
                # 예외 발생 시 로깅 또는 처리
                print(f"Error processing block for {trigger.user.id}: {e}")
                continue
