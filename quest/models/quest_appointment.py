"""
MongoDB document model for quest_appointments collection.
Mirrors PHP QuestAppointment Doctrine ODM document.
"""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from quest.enums import QuestAppointmentStatusEnum


class QuestAppointment(BaseModel):
    id: str | None = Field(None, alias="_id")
    confirmation_id: str = Field(alias="confirmationId")
    appointment_start: datetime = Field(alias="appointmentStart")
    appointment_end: datetime = Field(alias="appointmentEnd")
    location_code: str = Field(alias="locationCode")
    location_id: str = Field(alias="locationId")
    location_name: str = Field(alias="locationName")
    location_address1: str = Field(alias="locationAddress1")
    location_address2: str | None = Field(None, alias="locationAddress2")
    location_city: str = Field(alias="locationCity")
    location_state: str = Field(alias="locationState")
    location_zip: str = Field(alias="locationZip")
    time_zone: str = Field(alias="timeZone")
    short_qr_token: str = Field("", alias="shortQRToken")
    long_qr_token: str = Field("", alias="longQRToken")
    patient_id: int = Field(alias="patientId")
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    activity_id: str = Field(alias="activityId")
    quest_order_ids: list[str] = Field(default_factory=list, alias="questOrderIds")
    status: str = QuestAppointmentStatusEnum.AVAILABLE.value
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt")

    class Config:
        populate_by_name = True

    def to_doc(self) -> dict[str, Any]:
        return {
            "confirmationId": self.confirmation_id,
            "appointmentStart": self.appointment_start,
            "appointmentEnd": self.appointment_end,
            "locationCode": self.location_code,
            "locationId": self.location_id,
            "locationName": self.location_name,
            "locationAddress1": self.location_address1,
            "locationAddress2": self.location_address2,
            "locationCity": self.location_city,
            "locationState": self.location_state,
            "locationZip": self.location_zip,
            "timeZone": self.time_zone,
            "shortQRToken": self.short_qr_token,
            "longQRToken": self.long_qr_token,
            "patientId": self.patient_id,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "activityId": self.activity_id,
            "questOrderIds": self.quest_order_ids,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "QuestAppointment":
        doc = dict(doc)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls.model_validate(doc)

    def to_value_object(self) -> dict[str, Any]:
        """Serialisable dict for API responses."""
        from quest.services.quest_booking_parser import localise_dt
        start = localise_dt(self.appointment_start, self.time_zone)
        end = localise_dt(self.appointment_end, self.time_zone)
        return {
            "id": self.id,
            "confirmationId": self.confirmation_id,
            "appointmentStart": start.strftime("%Y-%m-%d %H:%M:%S"),
            "appointmentEnd": end.strftime("%Y-%m-%d %H:%M:%S"),
            "locationCode": self.location_code,
            "locationId": self.location_id,
            "locationName": self.location_name,
            "locationAddress1": self.location_address1,
            "locationAddress2": self.location_address2,
            "locationCity": self.location_city,
            "locationState": self.location_state,
            "locationZip": self.location_zip,
            "timeZone": self.time_zone,
            "shortQRToken": self.short_qr_token,
            "longQRToken": self.long_qr_token,
            "patientId": self.patient_id,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "activityId": self.activity_id,
            "status": self.status,
            "questOrderIds": self.quest_order_ids,
            "createdAt": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updatedAt": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
