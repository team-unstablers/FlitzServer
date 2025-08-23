# Celery가 자동으로 발견할 수 있도록 utils의 태스크들을 import
from flitz.utils.slack import post_slack_message

__all__ = ['post_slack_message']