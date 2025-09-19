import os

from celery.schedules import crontab
from django.conf import settings

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flitz.settings_dev')

app = Celery('flitz')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object(f'django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'update-distribution-reveal-phase': {
        'task': 'card.tasks.update_distribution_reveal_phase',
        'schedule': crontab(minute='*/5'),  # 매 5분마다 실행
    },

    "perform-gc-asset-references": {
        "task": "card.tasks.perform_gc_asset_references",
        "schedule": crontab(hour=0, minute=0),  # 매일 자정에 실행
    },

    'wake-up-apps': {
        'task': 'user.tasks.wake_up_apps',
        'schedule': crontab(minute='*/20'),  # 매 20분마다 실행
    },

    'poll-user-deletion-phase': {
        'task': 'user.tasks.poll_user_deletion_phase',
        'schedule': crontab(hour='*', minute=0),  # 1시간마다 실행
    },

    'send-card-distribution-notification': {
        'task': 'card.tasks.send_card_distribution_notification',
        'schedule': crontab(hour='*', minute=0),  # 매 1시간마다 실행
    },

    'flush-location-history': {
        'task': 'location.tasks.flush_location_history',
        'schedule': crontab(hour='*/6', minute=0),  # 6시간마다 실행
    },

    'chronowave-match-all': {
        'task': 'location.tasks.perform_chronowave_match_all',
        'schedule': crontab(minute='*/30'),  # 30분마다 실행
    }
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')