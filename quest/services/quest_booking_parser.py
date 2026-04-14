"""
Parses Quest Booking API XML responses and builds request XML bodies.
Mirrors PHP QuestBookingParser.
"""
import logging
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

import pytz

from quest.enums import QuestAppointmentStatusEnum
from quest.models.quest_appointment import QuestAppointment
from quest.models.quest_location import QuestLocation

logger = logging.getLogger(__name__)


def localise_dt(dt: datetime, tz_name: str) -> datetime:
    """Apply timezone to a naive or UTC datetime."""
    try:
        tz = pytz.timezone(tz_name)
        if dt.tzinfo is None:
            return tz.localize(dt)
        return dt.astimezone(tz)
    except Exception:
        return dt


class QuestBookingParser:

    # ── location parsing ──────────────────────────────────────────

    def parse_locations_xml(self, xml_string: str) -> list[QuestLocation]:
        try:
            root = ElementTree.fromstring(xml_string)
        except ElementTree.ParseError:
            logger.error("Failed to parse Quest locations XML")
            return []

        locations = []
        for node in root.findall(".//psc") + root.findall(".//facility") + root.findall(".//location"):
            try:
                loc = QuestLocation(
                    siteCode=node.findtext("sitecode") or node.findtext("siteCode") or "",
                    siteName=node.findtext("sitename") or node.findtext("siteName") or "",
                    city=node.findtext("city") or "",
                    state=node.findtext("state") or "",
                    zipCode=node.findtext("zip") or node.findtext("zipCode") or "",
                    latitude=float(node.findtext("latitude") or "0"),
                    longitude=float(node.findtext("longitude") or "0"),
                    address=node.findtext("address") or "",
                    phone=node.findtext("phone") or "",
                    fax=node.findtext("fax") or "",
                )
                if loc.site_code:
                    locations.append(loc)
            except Exception as exc:
                logger.warning("Skipping malformed location node: %s", exc)
        return locations

    # ── appointment slot parsing ──────────────────────────────────

    def parse_appointment_slots_xml(
        self, xml_string: str, activity_id: str
    ) -> list[dict[str, Any]]:
        """Returns list of slot dicts: {siteCode, appointmentDateTime, appointmentLength, status}."""
        try:
            root = ElementTree.fromstring(xml_string)
        except ElementTree.ParseError:
            return []

        slots = []
        for slot in root.findall(".//slot") + root.findall(".//appointment"):
            try:
                site_code = slot.findtext("siteCode") or slot.findtext("sitecode") or ""
                dt_str = slot.findtext("startTime") or slot.findtext("appointmentStart") or ""
                length_str = slot.findtext("appointmentLength") or slot.findtext("duration") or "10"
                dt = datetime.fromisoformat(dt_str) if dt_str else datetime.now(timezone.utc)
                slots.append({
                    "siteCode": site_code,
                    "appointmentDateTime": dt,
                    "appointmentLength": int(length_str),
                    "activityId": activity_id,
                    "status": QuestAppointmentStatusEnum.AVAILABLE.value,
                })
            except Exception as exc:
                logger.warning("Skipping malformed slot: %s", exc)
        return slots

    # ── appointment entity parsing ────────────────────────────────

    def parse_appointment_entity_from_xml(
        self,
        xml_string: str,
        patient_id: int,
        order_ids: list[str],
    ) -> QuestAppointment:
        root = ElementTree.fromstring(xml_string)
        return self._build_appointment(root, patient_id, order_ids)

    def parse_appointment_details_entity(self, xml_string: str) -> QuestAppointment:
        root = ElementTree.fromstring(xml_string)
        return self._build_appointment(root, 0, [])

    def _build_appointment(
        self,
        root: ElementTree.Element,
        patient_id: int,
        order_ids: list[str],
    ) -> QuestAppointment:
        def text(tag: str) -> str:
            return root.findtext(tag) or ""

        def parse_dt(val: str) -> datetime:
            if val:
                try:
                    return datetime.fromisoformat(val)
                except ValueError:
                    pass
            return datetime.now(timezone.utc)

        return QuestAppointment(
            confirmationId=text("confirmationId") or text("confirmationid"),
            appointmentStart=parse_dt(text("appointmentStart") or text("startTime")),
            appointmentEnd=parse_dt(text("appointmentEnd") or text("endTime")),
            locationCode=text("siteCode") or text("sitecode"),
            locationId=text("locationId") or text("locationid") or text("siteCode"),
            locationName=text("locationName") or text("sitename"),
            locationAddress1=text("locationAddress1") or text("address1") or text("address"),
            locationAddress2=text("locationAddress2") or text("address2") or None,
            locationCity=text("locationCity") or text("city"),
            locationState=text("locationState") or text("state"),
            locationZip=text("locationZip") or text("zip"),
            timeZone=text("timeZone") or text("timezone") or "America/New_York",
            shortQRToken=text("shortQRToken") or text("shortqrtoken"),
            longQRToken=text("longQRToken") or text("longqrtoken"),
            patientId=patient_id,
            firstName=text("firstName") or text("firstname"),
            lastName=text("lastName") or text("lastname"),
            activityId=text("activityId") or text("activityid"),
            questOrderIds=order_ids,
            status=QuestAppointmentStatusEnum.BOOKED.value,
        )

    def parse_cancel_appointment_response(self, xml_string: str) -> dict[str, str]:
        try:
            root = ElementTree.fromstring(xml_string)
            return {
                "respcode": root.findtext("respcode") or "",
                "respmessage": root.findtext("respmessage") or "",
                "datetime": root.findtext("datetime") or "",
            }
        except Exception:
            return {"respcode": "", "respmessage": "", "datetime": ""}

    def update_appointment_from_modify_response(
        self, appointment: QuestAppointment, xml_string: str
    ) -> None:
        try:
            root = ElementTree.fromstring(xml_string)
            start_str = root.findtext("appointmentStart") or root.findtext("startTime")
            end_str = root.findtext("appointmentEnd") or root.findtext("endTime")
            if start_str:
                appointment.appointment_start = datetime.fromisoformat(start_str)
            if end_str:
                appointment.appointment_end = datetime.fromisoformat(end_str)
        except Exception as exc:
            logger.warning("Could not parse modify response: %s", exc)

    # ── request XML builders ──────────────────────────────────────

    def prepare_appointments_request_xml(
        self, request: Any, locations: list[QuestLocation]
    ) -> str:
        site_codes = "".join(
            f"<siteCode>{loc.site_code}</siteCode>" for loc in locations
        )
        return (
            f"<?xml version='1.0' encoding='UTF-8'?>"
            f"<request>"
            f"<date>{request.date}</date>"
            f"<activityId>{request.activity_id}</activityId>"
            f"<siteCodes>{site_codes}</siteCodes>"
            f"</request>"
        )

    def prepare_create_appointment_request_xml(
        self, request: Any, location: QuestLocation | None
    ) -> str:
        p = request.patient
        return (
            f"<?xml version='1.0' encoding='UTF-8'?>"
            f"<appointment>"
            f"<date>{request.date}</date>"
            f"<time>{request.time}</time>"
            f"<siteCode>{request.site_code}</siteCode>"
            f"<siteId>{request.site_id}</siteId>"
            f"<activityId>{request.activity_id}</activityId>"
            f"<labcardStatus>{'true' if request.labcard_status else 'false'}</labcardStatus>"
            f"<patient>"
            f"<firstName>{p.firstname}</firstName>"
            f"<lastName>{p.lastname}</lastName>"
            f"<phone>{p.phone}</phone>"
            f"<email>{p.email}</email>"
            f"<birthDate>{p.birth_date}</birthDate>"
            f"<externalId>{p.external_id}</externalId>"
            f"<survey0>{p.survey0}</survey0>"
            f"<survey1>{p.survey1}</survey1>"
            f"<remindViaPhone>{'true' if p.remind_via_phone else 'false'}</remindViaPhone>"
            f"<smsOptin>{'true' if p.sms_optin else 'false'}</smsOptin>"
            f"<emailOptin>{'true' if p.email_optin else 'false'}</emailOptin>"
            f"</patient>"
            f"</appointment>"
        )

    def prepare_modify_appointment_request_xml(
        self,
        confirmation_id: str,
        date: str,
        time: str,
        site_code: str,
        time_zone: str,
    ) -> str:
        return (
            f"<?xml version='1.0' encoding='UTF-8'?>"
            f"<appointment>"
            f"<confirmationId>{confirmation_id}</confirmationId>"
            f"<date>{date}</date>"
            f"<time>{time}</time>"
            f"<siteCode>{site_code}</siteCode>"
            f"</appointment>"
        )
