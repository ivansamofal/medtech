"""
Celery tasks for Quest – equivalent to PHP Messenger handlers.
"""
import asyncio
import logging

from core.celery_app import celery_app
from core.database import get_db

logger = logging.getLogger(__name__)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_order_service():
    from quest.repositories.quest_order_repository import QuestOrderRepository
    from quest.services.quest_api_client import QuestApiClient
    from quest.services.quest_order_service import QuestOrderService

    db = get_db()
    return QuestOrderService(QuestOrderRepository(db), QuestApiClient())


@celery_app.task(
    name="quest.tasks.quest_tasks.create_quest_order",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def create_quest_order(
    self,
    patient_id: int,
    order_id: str,
    test_codes: list[str],
    hl7_message: str,
    external_order_item_id: int | None = None,
) -> None:
    """
    Submit a Quest order.
    Equivalent to QuestCreateOrderHandler → QuestService::orderSubmit().
    """
    logger.info("Submitting Quest order %s for patient %d", order_id, patient_id)
    try:
        service = _make_order_service()
        _run(
            service.submit_order(
                patient_id, order_id, test_codes, hl7_message, external_order_item_id
            )
        )
    except Exception as exc:
        logger.error("Failed to submit Quest order %s: %s", order_id, exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    name="quest.tasks.quest_tasks.collect_results",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def collect_results(self) -> None:
    """
    Poll Quest API for results on all SENT orders.
    Scheduled hourly via Celery beat.
    Equivalent to CollectResultsHandler → QuestService::collectResults().
    """
    logger.info("Running Quest collect-results task")
    try:
        service = _make_order_service()
        _run(service.collect_results())
    except Exception as exc:
        logger.error("Quest collect-results task failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)
