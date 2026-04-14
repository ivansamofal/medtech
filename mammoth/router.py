"""
FastAPI router for /integration/mammoth/* endpoints.
Mirrors the PHP Http actions.
"""
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from core.config import settings
from core.database import get_db
from mammoth.repositories.mammoth_patient_repository import MammothPatientRepository
from mammoth.schemas.requests import MammothPatientCreateRequest
from mammoth.schemas.responses import (
    MammothPatientCreateResponse,
    MammothPatientValueObject,
    MammothWidgetInfo,
)
from mammoth.services.mammoth_api_service import MammothApiService
from mammoth.services.mammoth_create_patient_service import MammothCreatePatientService
from mammoth.services.mammoth_data_hash_service import MammothDataHashService
from mammoth.services.mammoth_patient_save_data_service import MammothPatientSaveDataService
from mammoth.tasks.mammoth_tasks import save_mammoth_lab_results, save_mammoth_patient_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration/mammoth", tags=["Mammoth"])


# ── dependency helpers ────────────────────────────────────────────

def get_repo():
    return MammothPatientRepository(get_db())


def get_api_service():
    return MammothApiService()


# ── endpoints ─────────────────────────────────────────────────────


@router.post(
    "/patient/registration",
    response_model=MammothPatientCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register patient in Mammoth EHR",
)
async def register_patient(
    body: MammothPatientCreateRequest,
    api_svc: MammothApiService = Depends(get_api_service),
):
    """
    POST /integration/mammoth/patient/registration
    Creates a Mammoth EHR patient, returns the Mammoth patient record.
    After creation it enqueues the data-save background task.
    """
    service = MammothCreatePatientService(api_svc)
    try:
        result = await service.create(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Enqueue data fetch with configurable delay
    save_mammoth_patient_data.apply_async(
        args=[result.id],
        countdown=settings.mammoth_data_save_delay,
    )
    return result


@router.post(
    "/patients/data",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Trigger Mammoth data sync for current patient",
)
async def trigger_data_sync(patient_uid: str):
    """
    POST /integration/mammoth/patients/data
    Dispatches a background job to fetch & save all patient data.
    patient_uid should come from the authenticated patient JWT (simplified here as a query param).
    """
    save_mammoth_patient_data.apply_async(
        args=[patient_uid],
        countdown=settings.mammoth_data_save_delay,
    )


@router.get(
    "/patients/my",
    response_model=MammothPatientValueObject,
    summary="Get current patient's Mammoth data",
)
async def get_my_mammoth_data(
    patient_uid: str,
    repo: MammothPatientRepository = Depends(get_repo),
):
    """
    GET /integration/mammoth/patients/my
    Returns the stored Mammoth EHR data for the authenticated patient.
    """
    patient = await repo.get_by_uid(patient_uid)
    if patient is None:
        raise HTTPException(status_code=404, detail="Mammoth patient data not found")

    return MammothPatientValueObject(
        patient_id=patient.patient_id,
        updated_at=patient.formatted_updated_at(),
        status=patient.status,
        overview=patient.overview,
        vital_signs=patient.vital_signs,
        procedures=patient.procedures,
        medications=patient.medications,
        social_histories=patient.social_histories,
        insurance_providers=patient.insurance_providers,
        allergies=patient.allergies,
        family_histories=patient.family_histories,
        encounters=patient.encounters,
        care_plans=patient.care_plans,
        lab_result_groups=patient.lab_result_groups,
        lab_results=patient.lab_results,
        conditions=patient.conditions,
        immunization=patient.immunization,
    )


@router.get(
    "/patient/lab-results",
    status_code=status.HTTP_200_OK,
    summary="Trigger lab-results fetch for current patient",
)
async def trigger_lab_results(
    patient_uid: str,
    repo: MammothPatientRepository = Depends(get_repo),
):
    """
    GET /integration/mammoth/patient/lab-results
    Enqueues lab-results background job for the patient.
    """
    save_mammoth_lab_results.apply_async(
        args=[patient_uid],
        countdown=settings.mammoth_lab_results_delay,
    )
    return {"message": "Job for lab results sent to queue"}


@router.get(
    "/patient/fields",
    response_model=MammothWidgetInfo,
    summary="Get Mammoth profile completion widget info",
)
async def get_patient_fields(
    patient_uid: str,
    repo: MammothPatientRepository = Depends(get_repo),
):
    """
    GET /integration/mammoth/patient/fields
    Returns whether the patient is registered in Mammoth and which fields are filled.
    """
    patient = await repo.get_by_uid(patient_uid)
    is_mammoth_auth = patient is not None

    filled: dict[str, Any] = {}
    if patient:
        filled = {
            "overview": bool(patient.overview),
            "vitalSigns": bool(patient.vital_signs),
            "procedures": bool(patient.procedures),
            "medications": bool(patient.medications),
            "conditions": bool(patient.conditions),
            "allergies": bool(patient.allergies),
            "labResults": bool(patient.lab_results),
        }

    return MammothWidgetInfo(is_mammoth_auth=is_mammoth_auth, filled_fields=filled)


@router.delete(
    "/patients/{patient_uid}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear Mammoth data for a patient (staff action)",
)
async def clear_mammoth_data(
    patient_uid: str,
    repo: MammothPatientRepository = Depends(get_repo),
):
    """
    DELETE /integration/mammoth/patients/{patient_uid}
    Staff action – removes Mammoth data for a patient.
    """
    await repo.delete_by_patient_id(patient_uid)
