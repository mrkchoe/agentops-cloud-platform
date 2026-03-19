from app.core.config import settings
from celery import Celery


celery_app = Celery("agentops_cloud_platform")
celery_app.conf.broker_url = str(settings.celery_broker_url)
celery_app.conf.result_backend = str(settings.celery_result_backend)
celery_app.conf.task_always_eager = bool(settings.celery_task_always_eager)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"

# Ensure task modules are registered when the worker starts.
import app.tasks.celery_tasks  # noqa: E402,F401

