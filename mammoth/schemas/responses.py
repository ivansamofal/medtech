from typing import Any
from pydantic import BaseModel


class MammothPatientCreateResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    phone: str
    status: str


class MammothPatientValueObject(BaseModel):
    patient_id: str
    updated_at: str
    status: str
    overview: dict[str, Any]
    vital_signs: list[dict[str, Any]]
    procedures: list[dict[str, Any]]
    medications: list[dict[str, Any]]
    social_histories: list[dict[str, Any]]
    insurance_providers: list[dict[str, Any]]
    allergies: list[dict[str, Any]]
    family_histories: list[dict[str, Any]]
    encounters: list[dict[str, Any]]
    care_plans: list[dict[str, Any]]
    lab_result_groups: list[dict[str, Any]]
    lab_results: list[dict[str, Any]]
    conditions: list[dict[str, Any]]
    immunization: list[dict[str, Any]]


class MammothWidgetInfo(BaseModel):
    is_mammoth_auth: bool
    filled_fields: dict[str, Any]
