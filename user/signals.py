from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from celery.utils.log import get_task_logger

from user.models import UserDeletionReviewRequest, UserDeletionReviewRequestReason
from flitz.utils.slack import post_slack_message

logger = get_task_logger(__name__)


@receiver(post_save, sender=UserDeletionReviewRequest)
def notify_deletion_review_request_to_slack(sender, instance, created, **kwargs):
    """
    UserDeletionReviewRequest가 생성되면 Slack에 알림을 보냅니다.
    """
    if not created:
        return
    
    try:
        # 신고 사유 텍스트 생성
        reasons = []
        if instance.reason & UserDeletionReviewRequestReason.HAS_FLAGGED_CONTENT:
            reasons.append("컨텐츠 신고 이력 있음")
        if instance.reason & UserDeletionReviewRequestReason.HAS_FLAGGED_MESSAGE:
            reasons.append("메시지 신고 이력 있음")
        if instance.reason & UserDeletionReviewRequestReason.HAS_FLAGGED_PROFILE:
            reasons.append("프로필 신고 이력 있음")
        if instance.reason & UserDeletionReviewRequestReason.OTHER:
            reasons.append("기타")
        
        reason_text = ", ".join(reasons) if reasons else "알 수 없음"
        
        # Slack 메시지 포맷팅
        message = f"""🚨 *계정 삭제 리뷰 요청*

*사용자 ID:* `{instance.user.id}`
*사용자명:* {instance.user.username}
*표시 이름:* {instance.user.display_name}
*신고 사유:* {reason_text}
*상세 내용:* {instance.reason_text}
*요청 시간:* {instance.created_at.strftime('%Y-%m-%d %H:%M:%S')} (UTC)

⚠️ 이 사용자는 신고 이력이 있어 계정 삭제 전 검토가 필요합니다."""
        
        # Slack으로 메시지 전송 (Celery 태스크 사용)
        post_slack_message.delay(message)
        
        logger.info(f"Sent deletion review request notification to Slack for user {instance.user.id}")
        
    except Exception as e:
        logger.error(f"Failed to send deletion review request notification to Slack: {e}", exc_info=True)