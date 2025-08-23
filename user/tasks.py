import json
from logging import Logger
from typing import Optional

from uuid import UUID
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.cache import cache
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from flitz.apns import APNS
from flitz.gpgenc import gpg_encrypt
from user.models import User, PushNotificationType, UserIdentity, UserGenderBit, UserDeletionPhase, \
    UserDeletionReviewRequestReason, UserDeletionReviewRequest, DeletedUserArchive
from user.objdef import DeletedUserArchiveData
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

@transaction.atomic
def execute_deletion_phase_sensitive_data(user_id: UUID):
    """
    사용자 삭제 페이즈 1: 프로필 정보 및 민감한 데이터를 삭제합니다.
      - 휴대폰 번호, 이메일 등의 기본 정보는 범죄 방지를 위하여 일정 기간동안 아카이브로써 보관합니다.
    """

    from card.models import CardFlag
    from location.models import UserLocation, DiscoverySession, DiscoveryHistory
    from messaging.models import DirectMessageFlag

    user = User.objects.get(id=user_id)

    # PREREQUISITES: 사용자가 문제 행동을 일으킨 적이 있는지 확인
    content_flags_count = CardFlag.objects.filter(
        card__user=user,
        resolved_at__isnull=True,
    ).only('id').count()

    message_flags_count = DirectMessageFlag.objects.filter(
        message__sender=user,
        resolved_at__isnull=True,
    ).only('id').count()

    # TODO: 사용자의 프로필 플래그 확인
    profile_flags_count = 0

    deletion_needs_review = (
        content_flags_count > 0 or
        message_flags_count > 0 or
        profile_flags_count > 0
    )

    if deletion_needs_review:
        reason = 0
        reason_text = f'컨텐츠 신고 {content_flags_count}건, 메시지 신고 {message_flags_count}건, 프로필 신고 {profile_flags_count}건'

        if content_flags_count > 0:
            reason |= UserDeletionReviewRequestReason.HAS_FLAGGED_CONTENT
        if message_flags_count > 0:
            reason |= UserDeletionReviewRequestReason.HAS_FLAGGED_MESSAGE
        if profile_flags_count > 0:
            reason |= UserDeletionReviewRequestReason.HAS_FLAGGED_PROFILE

        # 추후 페이즈는 리뷰 후 삭제가 진행될 수 있도록 합니다
        review_request, created = UserDeletionReviewRequest.objects.update_or_create(
            user=user,
            defaults={
                'reason': reason,
                'reason_text': reason_text,

                'reviewed_at': None,  # 미검토
            }
        )
        
        # Slack 알림 전송
        if created:
            from flitz.utils.slack import post_slack_message
            
            # 신고 사유 텍스트 생성
            reasons = []
            if reason & UserDeletionReviewRequestReason.HAS_FLAGGED_CONTENT:
                reasons.append("컨텐츠 신고 이력 있음")
            if reason & UserDeletionReviewRequestReason.HAS_FLAGGED_MESSAGE:
                reasons.append("메시지 신고 이력 있음")
            if reason & UserDeletionReviewRequestReason.HAS_FLAGGED_PROFILE:
                reasons.append("프로필 신고 이력 있음")
            if reason & UserDeletionReviewRequestReason.OTHER:
                reasons.append("기타")
            
            reason_display = ", ".join(reasons) if reasons else "알 수 없음"
            
            slack_message = f"""🚨 *계정 삭제 리뷰 요청*

*사용자 ID:* `{user.id}`
*사용자명:* {user.username}
*표시 이름:* {user.display_name}
*신고 사유:* {reason_display}
*상세 내용:* {reason_text}
*요청 시간:* {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} (UTC)

⚠️ 이 사용자는 신고 이력이 있어 계정 삭제 전 검토가 필요합니다."""
            
            # Slack 알림을 별도 태스크로 전송
            post_slack_message.delay(slack_message)

    # 범죄 방지를 위해 기본적인 정보를 30일동안 아카이브로써 보관합니다.
    archive_data = DeletedUserArchiveData(
        id=str(user.id),

        username=user.username,
        display_name=user.display_name,
        email=user.email,
        phone_number=user.phone_number,
    )

    try:
        encrypted_archive_data = gpg_encrypt(
            json.dumps(archive_data).encode('utf-8'),
            pubkey_file=settings.GPG_PUBLIC_KEY_FILE  # 공개키 파일 경로
        )

        archive, _ = DeletedUserArchive.objects.update_or_create(
            original_user_id=user.id,
            defaults={
                'delete_scheduled_at': timezone.now() + timezone.timedelta(days=30),  # 30일 후에 삭제 예정
            }
        )

        with NamedTemporaryFile() as temp_file:
            temp_file.write(encrypted_archive_data)
            temp_file.flush()

            # 아카이브 데이터를 저장합니다
            archive.archived_data.save(f"{user.id}.enc", File(temp_file), save=False)
            archive.save()
    except Exception as e:
        logger.error(f"execute_deletion_phase_sensitive_data(): error encrypting and saving archive data for user {user_id}: {e}", exc_info=True)
        # 아카이브 실패 시, 일단 사용자 삭제를 중단합니다
        raise

    # 0. 모든 세션 무효화
    UserSession.objects.filter(
        user=user,
        invalidated_at__isnull=True
    ).update(invalidated_at=timezone.now())

    # 1. 민감 정보 삭제: 정체성 및 성적 선호도
    UserIdentity.objects.filter(
        user=user
    ).update(
        gender=UserGenderBit.UNSET,
        is_trans=False,
        display_trans_to_others=False,
        preferred_genders=0,
        welcomes_trans=False,
        trans_prefers_safe_match=False
    )

    # 2. 민감 정보 삭제: 위치 정보 기록
    UserLocation.objects.filter(
        user=user
    ).delete()

    DiscoverySession.objects.filter(
        user=user,
        is_active=True
    ).update(
        is_active=False
    )

    # 이거도 범죄 방지를 위해 며칠 미뤄야 하지 않을지?
    DiscoveryHistory.objects.filter(
        session__user=user,
        discovered__user=user
    ).delete()

    # 3-3. 사용자 프로필 정보 삭제
    user.username = f'__DELETED__{user.id}'
    user.display_name = f'__DELETED__'
    user.phone_number = None
    user.phone_number_hashed = None

    if user.profile_image.name:
        # TODO: 프로필 이미지 삭제는 나중에 아카이브로 옮겨야 할까요?
        user.profile_image.delete(save=False)

    user.title = ''
    user.bio = ''
    user.hashtags = []

    user.birth_date = None
    user.email = ''

    user.deletion_phase = UserDeletionPhase.SENSITIVE_DATA_DELETED

    tomorrow_midnight = timezone.now() + timezone.timedelta(days=1)
    tomorrow_midnight = tomorrow_midnight.replace(hour=0, minute=0, second=0, microsecond=0)

    user.deletion_phase_scheduled_at = tomorrow_midnight
    user.save()


@transaction.atomic
def execute_deletion_phase_content(user_id: UUID):
    from card.models import CardFavoriteItem, CardDistribution, Card, UserCardAsset, CardFlag

    user = User.objects.get(id=user_id)

    # 1-1. CardFavoriteItem 삭제
    CardFavoriteItem.objects.filter(
        Q(user=user) | Q(card__user=user)
    ).update(
        deleted_at=timezone.now()
    )

    # 1-2. CardDistribution 삭제
    CardDistribution.objects.filter(
        Q(user=user) | Q(card__user=user),
        ).update(
        deleted_at=timezone.now()
    )

    # 1-3. UserCardAsset 삭제
    queryset = UserCardAsset.objects.filter(
        user=user,
        deleted_at__isnull=True
    ).all()

    iterator = queryset.iterator(chunk_size=1000)
    for asset in iterator:
        try:
            asset.delete_asset()
        except Exception as e:
            logger.error(f"deactivate_user(): error deleting asset {asset.id} for user {user_id}: {e}", exc_info=True)

    queryset.update(
        deleted_at=timezone.now()
    )

    # 1-4. Card 삭제
    queryset = Card.objects.filter(
        user=user,
        deleted_at__isnull=True
    )

    queryset.update(
        content={}
    )

    queryset.update(
        deleted_at=timezone.now()
    )

    user.deletion_phase = UserDeletionPhase.CONTENT_DELETED

    tomorrow_midnight = timezone.now() + timezone.timedelta(days=1)
    tomorrow_midnight = tomorrow_midnight.replace(hour=0, minute=0, second=0, microsecond=0)

    user.deletion_phase_scheduled_at = tomorrow_midnight
    user.save()


@transaction.atomic
def execute_deletion_phase_message(user_id: UUID):
    from messaging.models import DirectMessageFlag, DirectMessageAttachment, DirectMessage, DirectMessageConversation, \
        DirectMessageParticipant

    user = User.objects.get(id=user_id)

    # 2-1. DirectMessageAttachment 삭제
    queryset = DirectMessageAttachment.objects.filter(
        sender=user
    ).all()

    iterator = queryset.iterator(chunk_size=1000)
    for attachment in iterator:
        try:
            attachment.delete_attachment()
        except Exception as e:
            logger.error(f"deactivate_user(): error deleting attachment {attachment.id} for user {user_id}: {e}",
                         exc_info=True)

    queryset.update(
        deleted_at=timezone.now()
    )

    # 2-2. DirectMessage 삭제
    queryset = DirectMessage.objects.filter(
        sender=user
    )

    queryset.update(
        content={}
    )

    queryset.update(
        deleted_at=timezone.now()
    )

    # 2-3. DirectMessageParticipant 삭제
    DirectMessageParticipant.objects.filter(
        user=user
    ).update(
        deleted_at=timezone.now()
    )

    # 2-3. DirectMessageConversation 삭제
    DirectMessageConversation.objects.filter(
        participants__user=user
    ).update(
        deleted_at=timezone.now()
    )

    user.deletion_phase = UserDeletionPhase.MESSAGE_DELETED

    tomorrow_midnight = timezone.now() + timezone.timedelta(days=1)
    tomorrow_midnight = tomorrow_midnight.replace(hour=0, minute=0, second=0, microsecond=0)

    user.deletion_phase_scheduled_at = tomorrow_midnight
    user.save()

@shared_task(max_retries=3, default_retry_delay=60 * 10)
def execute_deletion_phase(user_id: UUID):
    """
    단계적인 사용자 삭제 작업을 실행합니다.
    """

    task_id = f'user_deletion_task:{user_id}'
    if not cache.add(task_id, True, timeout=60 * 5):
        # 이미 실행 중인 작업이 있다면, 이 작업은 무시합니다.
        logger.info(f"execute_deletion_phase(): user {user_id} deletion task already in progress. Skipping execution.")
        return

    try:
        user = User.objects.get(id=user_id)
        now = timezone.now()

        if user.disabled_at is None:
            logger.error(f"execute_deletion_phase(): user {user_id} not disabled.")
            return

        if user.deletion_phase is None:
            # ASSERTION FAILED
            logger.error(f"execute_deletion_phase(): user {user_id} deletion phase is None.")
            return

        # 페이즈를 보고 실제 삭제 태스크로 dispatch.
        phase = user.deletion_phase
        next_phase_at = user.deletion_phase_scheduled_at

        if phase == UserDeletionPhase.INITIATED:
            execute_deletion_phase_sensitive_data(user.id)

        if next_phase_at is not None and next_phase_at > now:
            # 다음 단계가 아직 예정되어 있다면, 현재 작업을 종료합니다.
            logger.info(f"execute_deletion_phase(): user {user_id} next phase scheduled at {next_phase_at}. Skipping execution.")
            return

        needs_review = UserDeletionReviewRequest.objects.filter(
            user=user,
            reviewed_at__isnull=True  # 미검토 상태인 경우
        ).only('id').exists()

        if needs_review:
            logger.info(f"execute_deletion_phase(): user {user_id} needs review before proceeding to next phase.")
            return

        if phase == UserDeletionPhase.SENSITIVE_DATA_DELETED:
            execute_deletion_phase_content(user.id)
        elif phase == UserDeletionPhase.CONTENT_DELETED:
            execute_deletion_phase_message(user.id)
        elif phase == UserDeletionPhase.MESSAGE_DELETED:
            # 최종 삭제 단계
            user.deletion_phase = UserDeletionPhase.FULLY_DELETED
            user.deletion_phase_scheduled_at = None
            user.fully_deleted_at = timezone.now()

            user.save()
    finally:
        # 작업 완료 후 캐시에서 제거
        cache.delete(task_id)
        logger.info(f"execute_deletion_phase(): user {user_id} deletion phase executed successfully.")

@shared_task
def poll_user_deletion_phase():
    """
    사용자 삭제 페이즈를 주기적으로 확인하고, 필요한 경우 삭제 작업을 실행합니다.
    """

    logger.info("poll_user_deletion_phase(): checking for users to process deletion phases...")

    now = timezone.now()

    # 삭제 페이즈가 있는 사용자들을 가져옵니다.
    users_to_process = User.objects.filter(
        # 삭제 예정인 사용자
        disabled_at__isnull=False,
        # ..이면서 삭제 페이즈가 None이 아닌 사용자
        deletion_phase__isnull=False,
        # ..이면서 삭제 페이즈가 scheduled_at이 현재 시간보다 이전인 사용자
        deletion_phase_scheduled_at__lte=now,
    ).exclude(
        deletion_phase=UserDeletionPhase.FULLY_DELETED,
    ).only('id', 'deletion_phase', 'deletion_phase_scheduled_at')

    iterator = users_to_process.iterator(chunk_size=100)

    for user in iterator:
        # Celery를 통해 삭제 페이즈 실행을 예약한다
        execute_deletion_phase.delay(user.id)
