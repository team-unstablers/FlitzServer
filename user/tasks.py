from typing import Optional

from uuid import UUID
from celery import shared_task

from user.models import User

@shared_task
def send_push_message(user_id: UUID, title: str, body: str, data: Optional[dict]=None):
    user = User.objects.get(id=user_id)
    user.send_push_message(title, body, data)