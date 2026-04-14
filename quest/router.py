"""
FastAPI router for /integration/quest/* endpoints.
Mirrors the PHP Http actions.
"""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from core.database import get_db
from quest.repositories.quest_appointment_repository import QuestAppointmentRepository
from quest.repositories.quest_location_repository import QuestLocationRepository
from quest.repositories.quest_order_repository import QuestOrderRepository
from quest.schemas.requests import (
    CreateAppointmentRequest,
    GetAppointmentSlotsRequest,
    LocationsRequest,
    ModifyAppointmentRequest,
)
from quest.services.quest_api_client import QuestApiClient
from quest.services.quest_booking_client import QuestBookingClient, QuestApiError
from quest.services.quest_booking_parser import QuestBookingParser
from quest.services.quest_booking_service import QuestBookingService
from quest.services.quest_location_service import QuestLocationService
from quest.services.quest_order_service import QuestOrderService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integration/quest", tags=["Quest"])


# ── dependency factories ──────────────────────────────────────────

def get_booking_service() -> QuestBookingService:
    db = get_db()
    return QuestBookingService(
        booking_client=QuestBookingClient(),
        parser=QuestBookingParser(),
        location_service=QuestLocationService(QuestLocationRepository(db)),
        appointment_repo=QuestAppointmentRepository(db),
        order_repo=QuestOrderRepository(db),
    )


def get_order_service() -> QuestOrderService:
    db = get_db()
    return QuestOrderService(QuestOrderRepository(db), QuestApiClient())


# ── Appointment endpoints ─────────────────────────────────────────


@router.post(
    "/appointments",
    status_code=status.HTTP_201_CREATED,
    summary="Create Quest appointment",
)
async def create_appointment(
    patient_id: int,
    body: CreateAppointmentRequest,
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    POST /integration/quest/appointments
    Calls the Quest Booking API to book an appointment.
    """
    try:
        return await svc.create_appointment(body, patient_id)
    except QuestApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/appointments",
    summary="Get patient appointments",
)
async def get_appointments(
    patient_id: int,
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    GET /integration/quest/appointments
    Returns upcoming and past appointments for the patient.
    """
    return await svc.get_patient_appointments(patient_id)


@router.get(
    "/appointments/slots",
    summary="Get available appointment slots",
)
async def get_appointment_slots(
    date: str,
    activity_id: str,
    location_codes: str = "",   # comma-separated
    search: str | None = None,
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    GET /integration/quest/appointments/slots
    Returns slot availability by location for the given date.
    """
    codes = [{"code": c.strip()} for c in location_codes.split(",") if c.strip()]
    request = GetAppointmentSlotsRequest(
        date=date,
        activity_id=activity_id,
        locations=codes,
        search=search,
    )
    return await svc.get_appointment_slots(request)


@router.get(
    "/appointments/{confirmation_id}",
    summary="Get appointment details",
)
async def get_appointment_details(
    confirmation_id: str,
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    GET /integration/quest/appointments/{confirmationId}
    Fetches live appointment data from Quest API and syncs to DB.
    """
    try:
        return await svc.get_appointment_details(confirmation_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/appointments/{confirmation_id}/modify",
    summary="Modify appointment",
)
async def modify_appointment(
    confirmation_id: str,
    body: ModifyAppointmentRequest,
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    POST /integration/quest/appointments/{confirmationId}/modify
    Reschedules an existing Quest appointment.
    """
    try:
        return await svc.modify_appointment(
            confirmation_id, body.date, body.time, body.site_code
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/appointments/{confirmation_id}",
    summary="Cancel appointment",
)
async def cancel_appointment(
    confirmation_id: str,
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    DELETE /integration/quest/appointments/{confirmationId}
    Cancels the appointment via Quest API and updates DB status.
    """
    try:
        return await svc.cancel_appointment(confirmation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Location endpoints ────────────────────────────────────────────


@router.post(
    "/locations",
    summary="Search Quest locations",
)
async def get_locations(
    body: LocationsRequest,
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    POST /integration/quest/locations
    Returns Quest patient service centers matching the filters.
    """
    locations = await svc.get_locations(body)
    return {"locations": locations}


@router.post(
    "/patient-service-centers",
    summary="Refresh Quest PSC locations (staff/admin)",
)
async def refresh_patient_service_centers(
    svc: QuestBookingService = Depends(get_booking_service),
) -> dict[str, Any]:
    """
    POST /integration/quest/patient-service-centers
    Fetches all Quest PSCs from the API and replaces the local DB.
    """
    return await svc.get_patient_service_centers()


@router.get(
    "/locations/cities",
    summary="Get distinct Quest location cities",
)
async def get_location_cities(
    state: str | None = None,
) -> dict[str, Any]:
    db = get_db()
    repo = QuestLocationRepository(db)
    if state:
        cities = await repo.get_cities_by_state(state)
    else:
        cities = await repo.get_all_cities()
    return {"cities": sorted(cities)}
