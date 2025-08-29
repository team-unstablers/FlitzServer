from typing import Tuple, List, Literal

import requests
from celery import shared_task
from celery.utils.log import get_task_logger

from django.conf import settings

logger = get_task_logger(__name__)

@shared_task
def send_email(to: str, subject: str, text: str, html: str = '', files: List[Tuple[Literal['inline'], Tuple[str, any, str]]] = None):
    if not settings.MAILGUN_API_KEY or not settings.MAILGUN_DOMAIN:
        logger.error("Mailgun settings are not configured properly.")
        return

    url = f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages"
    auth = ("api", settings.MAILGUN_API_KEY)
    data = {
        "from": f"Flitz <donotreply@{settings.MAILGUN_DOMAIN}>",
        "to": [to],
        "subject": subject,
        "text": text,
    }

    if html:
        data["html"] = html

    try:
        response = requests.post(url,
                                 auth=auth,
                                 data=data,
                                 files=files,
                                 timeout=10)

        response.raise_for_status()
        logger.info(f"Email sent to {to} with subject '{subject}'")
    except requests.RequestException as e:
        logger.error(f"Failed to send email to {to}: {e}")
        raise e