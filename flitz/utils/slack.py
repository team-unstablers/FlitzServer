import typing

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings

import requests

logger = get_task_logger(__name__)

@shared_task
def post_slack_message(message: str):
    if not settings.SLACK_WEBHOOK_URL:
        return

    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]
    }

    try:
        response = requests.post(
            settings.SLACK_WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        response.raise_for_status()
    except requests.RequestException as e:
        # 로깅 처리
        logger.error(f"Failed to send message to Slack: {e}")

