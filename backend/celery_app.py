"""Celery app configuration for distributed Harbor execution"""
import os
from celery import Celery
from kombu import serialization

# Redis URL from environment variable
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
app = Celery(
    'tbench',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['celery_worker']  # Import worker tasks
)

# Celery configuration
app.conf.update(
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Task routing
    task_routes={
        'celery_worker.execute_harbor_task': {'queue': 'harbor'},
    },

    # Worker settings
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time per worker
    worker_max_tasks_per_child=int(os.getenv('CELERY_MAX_TASKS_PER_CHILD', 50)),  # Restart worker after N tasks
    worker_concurrency=int(os.getenv('CELERY_CONCURRENCY', 5)),  # 5 concurrent tasks per worker

    # Task result expiration
    result_expires=86400,  # Results expire after 24 hours

    # Task time limits
    task_time_limit=3600,  # Hard limit: 1 hour
    task_soft_time_limit=3000,  # Soft limit: 50 minutes (gives time to cleanup)

    # Task retry settings
    task_acks_late=True,  # Acknowledge tasks after completion (not on start)
    task_reject_on_worker_lost=True,  # Requeue tasks if worker dies

    # Visibility timeout - how long before task is requeued if worker crashes
    broker_transport_options={
        'visibility_timeout': 3600,  # 1 hour
        'fanout_prefix': True,
        'fanout_patterns': True,
    },

    # Result backend settings
    result_backend_transport_options={
        'retry_policy': {
            'timeout': 5.0
        }
    },
)

if __name__ == '__main__':
    app.start()
