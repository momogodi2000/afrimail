
# backend/celery.py

import os
from celery import Celery
from django.conf import settings

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'afrimail.settings')

# Create Celery app
app = Celery('afrimail')

# Configure Celery using Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'schedule-campaigns': {
        'task': 'backend.tasks.schedule_campaigns',
        'schedule': 60.0,  # Every minute
    },
    'update-engagement-scores': {
        'task': 'backend.tasks.update_engagement_scores',
        'schedule': 3600.0,  # Every hour
    },
    'generate-daily-analytics': {
        'task': 'backend.tasks.generate_daily_analytics',
        'schedule': 86400.0,  # Every day
    },
    'cleanup-old-data': {
        'task': 'backend.tasks.cleanup_old_data',
        'schedule': 604800.0,  # Every week
    },
    'reset-daily-email-limits': {
        'task': 'backend.tasks.reset_daily_email_limits',
        'schedule': 86400.0,  # Every day at midnight
    },
    'reset-monthly-email-limits': {
        'task': 'backend.tasks.reset_monthly_email_limits',
        'schedule': 2592000.0,  # Every month (30 days)
    },
}

app.conf.timezone = 'Africa/Douala'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

