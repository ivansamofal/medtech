"""
Orchestrates Quest appointment operations.
Mirrors PHP QuestBookingService.
"""
import logging
from datetime import datetime, timedelta
from typing import Any

from quest.enums import QuestAppointmentStatusEnum, QuestBookingEndpointEnum, QuestOrderStatusEnum
from quest.models.quest_appointment import QuestAppointment
from quest.models.quest_location import QuestLocation
from quest.repositories.quest_appointment_repository import QuestAppointmentRepository
from quest.repositories.quest_order_repository import QuestOrderRepository
from quest.schemas.requests import (
    CreateAppointmentRequest,
    GetAppointmentSlotsRequest,
    LocationsRequest,
)
from quest.services.quest_booking_client import QuestBookingClient
from quest.services.quest_booking_parser import QuestBookingParser
from quest.services.quest_location_service import QuestLocationService

logger = logging.getLogger(__name__)


class NoWorkingHoursError(Exception):
    pass


class QuestBookingService:
    def __init__(
        self,
        booking_client: QuestBookingClient,
        parser: QuestBookingParser,
        location_service: QuestLocationService,
        appointment_repo: QuestAppointmentRepository,
        order_repo: QuestOrderRepository,
    ) -> None:
        self._client = booking_client
        self._parser = parser
        self._location_svc = location_service
        self._appt_repo = appointment_repo
        self._order_repo = order_repo

    # ── Patient Service Centers (staff / admin) ───────────────────

    async def get_patient_service_centers(self) -> dict[str, Any]:
        xml_string = await self._client.request(
            QuestBookingEndpointEnum.PATIENT_SERVICE_CENTERS.value,
            method="GET",
        )
        locations = self._parser.parse_locations_xml(xml_string)

        # De-duplicate by siteCode and coordinates
        seen_codes: set[str] = set()
        seen_coords: set[str] = set()
        unique: list[QuestLocation] = []
        for loc in locations:
            coord_key = f"{loc.latitude},{loc.longitude}"
            if loc.site_code in seen_codes or coord_key in seen_coords:
                continue
            seen_codes.add(loc.site_code)
            seen_coords.add(coord_key)
            unique.append(loc)

        await self._location_svc.truncate_and_save_many(unique)
        logger.info("Saved %d unique Quest locations", len(unique))
        return {"count": len(unique)}

    # ── Locations ─────────────────────────────────────────────────

    async def get_locations(self, request: LocationsRequest) -> list[dict[str, Any]]:
        locations = await self._location_svc.find_by_filters(
            request.city, request.state, request.search
        )
        return self._location_svc.to_value_objects(locations)

    # ── Appointment Slots ─────────────────────────────────────────

    async def get_appointment_slots(
        self, request: GetAppointmentSlotsRequest
    ) -> dict[str, Any]:
        locations = await self._resolve_locations(request)
        if not locations:
            return {"slots": {}, "locations": []}

        # Fetch available slots from Quest API
        body = self._parser.prepare_appointments_request_xml(request, locations)
        try:
            xml_string = await self._client.request(
                QuestBookingEndpointEnum.APPOINTMENTS.value, body
            )
        except Exception:
            xml_string = ""

        slot_objects = (
            self._parser.parse_appointment_slots_xml(xml_string, request.activity_id)
            if xml_string
            else []
        )

        appointment_length = slot_objects[0]["appointmentLength"] if slot_objects else 10
        if appointment_length <= 0:
            appointment_length = 10

        # Group available slots by location
        available_by_location: dict[str, dict[str, dict]] = {}
        for slot in slot_objects:
            code = slot["siteCode"]
            time_key = slot["appointmentDateTime"].strftime("%Y-%m-%d %H:%M")
            available_by_location.setdefault(code, {})[time_key] = slot

        result_by_location: dict[str, list[dict]] = {}
        for loc in locations:
            hours = self._get_location_hours(loc, request.date)
            if hours is None:
                result_by_location[loc.site_code] = []
                continue

            slots_for_location = self._generate_slots(
                request.date,
                hours["from"],
                hours["to"],
                appointment_length,
                loc.site_code,
                loc.location_id or "",
                request.activity_id,
                available_by_location.get(loc.site_code, {}),
            )
            result_by_location[loc.site_code] = slots_for_location

        return {
            "slots": result_by_location,
            "locations": self._location_svc.to_value_objects(locations),
        }

    # ── Create Appointment ────────────────────────────────────────

    async def create_appointment(
        self, request: CreateAppointmentRequest, patient_id: int
    ) -> dict[str, Any]:
        location = await self._location_svc.find_by_site_code(request.site_code)
        body = self._parser.prepare_create_appointment_request_xml(request, location)
        xml_string = await self._client.request(
            QuestBookingEndpointEnum.CREATE_APPOINTMENT.value, body
        )

        # Resolve linked Quest orders
        if request.quest_order_ids:
            db_orders = await self._order_repo.find_by_order_ids(request.quest_order_ids)
        else:
            db_orders = await self._order_repo.find_by_patient_id_and_status(
                patient_id, QuestOrderStatusEnum.SENT.value
            )
        order_ids = [o.order_id for o in db_orders]

        appointment = self._parser.parse_appointment_entity_from_xml(
            xml_string, patient_id, order_ids
        )
        appointment.status = QuestAppointmentStatusEnum.BOOKED.value
        saved = await self._appt_repo.upsert_by_confirmation_id(appointment)

        logger.info(
            "Created Quest appointment %s for patient %d",
            saved.confirmation_id,
            patient_id,
        )
        return saved.to_value_object()

    # ── Modify Appointment ────────────────────────────────────────

    async def modify_appointment(
        self,
        confirmation_id: str,
        date: str,
        time: str,
        site_code: str,
    ) -> dict[str, Any]:
        appointment = await self._appt_repo.find_by_confirmation_id(confirmation_id)
        if appointment is None:
            raise ValueError(f"Appointment {confirmation_id} not found")

        body = self._parser.prepare_modify_appointment_request_xml(
            confirmation_id, date, time, site_code, appointment.time_zone
        )
        xml_string = await self._client.request(
            QuestBookingEndpointEnum.MODIFY_APPOINTMENT.value, body
        )

        self._parser.update_appointment_from_modify_response(appointment, xml_string)
        await self._appt_repo.save(appointment)
        return appointment.to_value_object()

    # ── Get Appointment Details ───────────────────────────────────

    async def get_appointment_details(self, confirmation_id: str) -> dict[str, Any]:
        xml_string = await self._client.request(
            QuestBookingEndpointEnum.APPOINTMENT_DETAILS.value + confirmation_id,
            method="GET",
        )
        api_data = self._parser.parse_appointment_details_entity(xml_string)
        existing = await self._appt_repo.find_by_confirmation_id(confirmation_id)

        if existing:
            # Sync fields from API response
            existing.appointment_start = api_data.appointment_start
            existing.appointment_end = api_data.appointment_end
            existing.location_code = api_data.location_code
            existing.location_id = api_data.location_id
            existing.location_name = api_data.location_name
            existing.location_address1 = api_data.location_address1
            existing.location_address2 = api_data.location_address2
            existing.location_city = api_data.location_city
            existing.location_state = api_data.location_state
            existing.location_zip = api_data.location_zip
            existing.time_zone = api_data.time_zone
            existing.short_qr_token = api_data.short_qr_token
            existing.long_qr_token = api_data.long_qr_token
            existing.first_name = api_data.first_name
            existing.last_name = api_data.last_name
            existing.activity_id = api_data.activity_id
            await self._appt_repo.save(existing)
            return existing.to_value_object()

        saved = await self._appt_repo.upsert_by_confirmation_id(api_data)
        return saved.to_value_object()

    # ── Cancel Appointment ────────────────────────────────────────

    async def cancel_appointment(self, confirmation_id: str) -> dict[str, Any]:
        xml_string = await self._client.request(
            QuestBookingEndpointEnum.CANCEL_APPOINTMENT.value + confirmation_id,
            method="GET",
        )
        response = self._parser.parse_cancel_appointment_response(xml_string)

        if response.get("respmessage") == "Success":
            appointment = await self._appt_repo.find_by_confirmation_id(confirmation_id)
            if appointment is None:
                raise ValueError(f"Appointment {confirmation_id} not found locally")
            appointment.status = QuestAppointmentStatusEnum.CANCELLED.value
            await self._appt_repo.save(appointment)
            return {"confirmationId": confirmation_id}
        else:
            raise ValueError(
                f"Quest cancellation failed: {response.get('respmessage')}"
            )

    # ── Patient Appointments ──────────────────────────────────────

    async def get_patient_appointments(self, patient_id: int) -> dict[str, Any]:
        appointments = await self._appt_repo.find_by_patient_id(patient_id)
        now = datetime.utcnow()

        upcoming = []
        previous = []
        for appt in appointments:
            vo = appt.to_value_object()
            if appt.appointment_start >= now:
                upcoming.append(vo)
            else:
                previous.append(vo)

        return {"upcoming": upcoming, "previous": previous}

    # ── private helpers ───────────────────────────────────────────

    async def _resolve_locations(
        self, request: GetAppointmentSlotsRequest
    ) -> list[QuestLocation]:
        codes = [loc["code"] for loc in request.locations if "code" in loc]

        if request.search:
            return await self._location_svc.find_by_filters(
                None, None, request.search, codes or None
            )
        if codes:
            return await self._location_svc.find_by_site_codes(codes)
        return []

    def _get_location_hours(
        self, location: QuestLocation, date_str: str
    ) -> dict[str, str] | None:
        weekday = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
        hours_map = location.standardized_drug_screen_hours

        if not hours_map or weekday not in hours_map:
            return {"from": "09:00", "to": "18:00"}

        hours_str = hours_map[weekday]
        if hours_str in ("X", "VARY"):
            return None

        parts = hours_str.split("-", 1)
        if len(parts) != 2:
            return {"from": "09:00", "to": "18:00"}
        return {"from": parts[0], "to": parts[1]}

    def _generate_slots(
        self,
        date_str: str,
        time_from: str,
        time_to: str,
        length_minutes: int,
        site_code: str,
        location_id: str,
        activity_id: str,
        available_slots: dict[str, dict],
    ) -> list[dict[str, Any]]:
        start = datetime.strptime(f"{date_str} {time_from}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{date_str} {time_to}", "%Y-%m-%d %H:%M")
        delta = timedelta(minutes=length_minutes)

        result = []
        current = start
        while current < end:
            time_key = current.strftime("%Y-%m-%d %H:%M")
            if time_key in available_slots:
                result.append(available_slots[time_key])
            else:
                result.append({
                    "siteCode": site_code,
                    "locationId": location_id,
                    "appointmentLength": length_minutes,
                    "appointmentDateTime": current.isoformat(),
                    "activityId": activity_id,
                    "status": QuestAppointmentStatusEnum.DISABLED.value,
                })
            current += delta

        return result
