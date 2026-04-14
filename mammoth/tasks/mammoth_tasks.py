"""
Celery tasks for Mammoth – equivalent to PHP Message/MessageHandler pairs.
"""
import asyncio
import logging

from core.celery_app import celery_app
from core.database import get_db
from mammoth.repositories.mammoth_patient_repository import MammothPatientRepository
from mammoth.services.mammoth_api_service import MammothApiService
from mammoth.services.mammoth_data_hash_service import MammothDataHashService
from mammoth.services.mammoth_patient_save_data_service import MammothPatientSaveDataService
from mammoth.services.mammoth_patient_save_lab_results_service import (
    MammothPatientSaveLabResultsService,
)

logger = logging.getLogger(__name__)


def _run(coro):
    """Execute a coroutine synchronously inside a Celery worker."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_services():
    db = get_db()
    repo = MammothPatientRepository(db)
    api = MammothApiService()
    hash_svc = MammothDataHashService()
    return repo, api, hash_svc


@celery_app.task(
    name="mammoth.tasks.mammoth_tasks.save_mammoth_patient_data",
    bind=True,
    max_retries=2,
    default_retry_delay=600,
)
def save_mammoth_patient_data(self, patient_uid: str, retry_count: int = 0) -> None:
    """
    Fetch & persist all Mammoth data for a patient.
    Equivalent to MammothApiMessageHandler → MammothPatientSaveDataService.save().
    """
    logger.info("Processing Mammoth data save for patient %s (retry=%d)", patient_uid, retry_count)
    try:
        repo, api, hash_svc = _make_services()
        service = MammothPatientSaveDataService(repo, api, hash_svc)
        _run(service.save(patient_uid, retry_count))
    except Exception as exc:
        logger.error("Error saving Mammoth data for %s: %s", patient_uid, exc)
        raise self.retry(exc=exc, countdown=600)


@celery_app.task(
    name="mammoth.tasks.mammoth_tasks.save_mammoth_lab_results",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def save_mammoth_lab_results(self, patient_uid: str) -> None:
    """
    Fetch & persist lab results for a patient.
    Equivalent to MammothLabResultsSaveApiMessageHandler → MammothPatientSaveLabResultsService.save().
    """
    logger.info("Processing Mammoth lab-results save for patient %s", patient_uid)
    try:
        repo, api, _ = _make_services()
        service = MammothPatientSaveLabResultsService(repo, api)
        _run(service.save(patient_uid))
    except Exception as exc:
        logger.error("Error saving Mammoth lab results for %s: %s", patient_uid, exc)
        raise self.retry(exc=exc, countdown=300)
