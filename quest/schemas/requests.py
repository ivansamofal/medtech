"""
Request DTOs for Quest endpoints – mirrors PHP Domain value objects.
"""
from pydantic import BaseModel


class CreateAppointmentPatientRequest(BaseModel):
    lastname: str
    firstname: str
    phone: str
    email: str
    birth_date: str          # YYYY-MM-DD
    external_id: str = ""
    survey0: str = ""
    survey1: str = ""
    remind_via_phone: bool = False
    sms_optin: bool = False
    email_optin: bool = False


class CreateAppointmentQrData(BaseModel):
    short_qr_token: str = ""
    long_qr_token: str = ""


class CreateAppointmentRequest(BaseModel):
    date: str                # YYYY-MM-DD
    time: str                # HH:MM
    site_code: str
    site_id: str
    activity_id: str
    labcard_status: bool = False
    patient: CreateAppointmentPatientRequest
    qr_data: CreateAppointmentQrData = CreateAppointmentQrData()
    facilities_service_id: str = ""
    quest_order_ids: list[str] = []


class GetAppointmentSlotsRequest(BaseModel):
    date: str                # YYYY-MM-DD
    activity_id: str
    locations: list[dict]    # [{"code": "..."}]
    search: str | None = None


class LocationsRequest(BaseModel):
    city: str | None = None
    state: str | None = None
    search: str | None = None


class ModifyAppointmentRequest(BaseModel):
    date: str
    time: str
    site_code: str
