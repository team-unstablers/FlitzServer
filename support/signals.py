from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction

from flitz.utils.slack import post_slack_message
from user.tasks import send_push_message, send_push_message_ex
from .models import SupportTicket, SupportTicketResponse


@receiver(post_save, sender=SupportTicket)
def notify_support_ticket_created(sender, instance, created, **kwargs):
    """새로운 서포트 티켓이 생성될 때 Slack 알림을 전송합니다."""
    if not created:
        return
    
    # 트랜잭션이 완료된 후에 Celery 태스크 실행
    transaction.on_commit(
        lambda: post_slack_message.delay(
            f"🎫 *새로운 서포트 티켓이 접수되었습니다*\n"
            f"• *제목*: {instance.title}\n"
            f"• *사용자*: {instance.user.username} ({instance.user.display_name})\n"
            f"• *내용*: {instance.content[:200]}{'...' if len(instance.content) > 200 else ''}\n"
            f"• *접수 시간*: {instance.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    )


@receiver(post_save, sender=SupportTicketResponse)
def notify_support_ticket_response_created(sender, instance, created, **kwargs):
    """새로운 서포트 티켓 응답이 생성될 때 Slack 알림 및 사용자 푸시 알림을 전송합니다."""
    if not created:
        return
    
    # 트랜잭션이 완료된 후에 Celery 태스크 실행
    def send_notifications():
        # Slack 알림
        post_slack_message.delay(
            f"💬 *서포트 티켓에 새로운 응답이 등록되었습니다*\n"
            f"• *티켓 제목*: {instance.ticket.title}\n"
            f"• *응답자*: {instance.responder}\n"
            f"• *응답 내용*: {instance.content[:200]}{'...' if len(instance.content) > 200 else ''}\n"
            f"• *응답 시간*: {instance.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # 사용자 푸시 알림
        send_push_message_ex.delay_on_commit(
            user_id=instance.ticket.user.id,
            type='notice',
            aps={
                'alert': {
                    'title': '문의해주신 티켓에 새 답변이 등록되었습니다.',
                    'body': f'"{instance.ticket.title}" 티켓에 새로운 답변이 등록되었습니다.',
                    'title-loc-key': 'fz.notification.support_response.title',
                    'title-loc-args': [],
                    'loc-key': 'fz.notification.support_response.body',
                    'loc-args': [instance.ticket.title],
                },
                'mutable-content': 1,
            },
            user_info={
                'type': 'support_response',
                'ticket_id': str(instance.ticket.id),
                'response_id': str(instance.id)
            }
        )
    
    transaction.on_commit(send_notifications)