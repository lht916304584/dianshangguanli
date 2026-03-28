import logging
import time

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.send_email", max_retries=3, default_retry_delay=60)
def send_email_task(self, to: str, subject: str, body: str) -> dict:
    """Example task: send an email (replace with real SMTP logic)."""
    try:
        logger.info("Sending email to %s — Subject: %s", to, subject)
        # TODO: integrate with SMTP / SES / SendGrid
        time.sleep(0.5)  # Simulate I/O
        return {"status": "sent", "to": to}
    except Exception as exc:
        logger.exception("Email task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(name="tasks.process_data")
def process_data_task(data: dict) -> dict:
    """Example CPU-bound background task."""
    logger.info("Processing data: %s", data)
    # TODO: heavy processing logic here
    return {"processed": True, "input_keys": list(data.keys())}
