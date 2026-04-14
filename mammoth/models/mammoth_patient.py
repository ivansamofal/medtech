"""
MongoDB document model for patient_mammoth_data collection.
Mirrors the PHP MammothPatient Doctrine ODM document.
"""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class MammothPatient(BaseModel):
    """
    Represents a document in the `patient_mammoth_data` MongoDB collection.
    `patientId` is indexed uniquely (corresponds to the patient's Mammoth UUID).
    """

    id: str | None = Field(None, alias="_id")
    patient_id: str = Field("", alias="patientId")
    updated_at: str = Field("", alias="updatedAt")
    status: str = ""

    # ── data fields ──────────────────────────────────────────────
    overview: dict[str, Any] = Field(default_factory=dict)
    vital_signs: list[dict[str, Any]] = Field(default_factory=list, alias="vitalSigns")
    procedures: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[dict[str, Any]] = Field(default_factory=list)
    social_histories: list[dict[str, Any]] = Field(default_factory=list, alias="socialHistories")
    insurance_providers: list[dict[str, Any]] = Field(default_factory=list, alias="insuranceProviders")
    allergies: list[dict[str, Any]] = Field(default_factory=list)
    family_histories: list[dict[str, Any]] = Field(default_factory=list, alias="familyHistories")
    encounters: list[dict[str, Any]] = Field(default_factory=list)
    care_plans: list[dict[str, Any]] = Field(default_factory=list, alias="carePlans")
    lab_result_groups: list[dict[str, Any]] = Field(default_factory=list, alias="labResultGroups")
    lab_results: list[dict[str, Any]] = Field(default_factory=list, alias="labResults")
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    immunization: list[dict[str, Any]] = Field(default_factory=list)

    # MD5 hashes per data-type URL for change-detection
    hashes: dict[str, str] = Field(default_factory=dict)

    class Config:
        populate_by_name = True

    def to_doc(self) -> dict[str, Any]:
        """Serialise to MongoDB document (camelCase field names)."""
        return {
            "patientId": self.patient_id,
            "updatedAt": self.updated_at,
            "status": self.status,
            "overview": self.overview,
            "vitalSigns": self.vital_signs,
            "procedures": self.procedures,
            "medications": self.medications,
            "socialHistories": self.social_histories,
            "insuranceProviders": self.insurance_providers,
            "allergies": self.allergies,
            "familyHistories": self.family_histories,
            "encounters": self.encounters,
            "carePlans": self.care_plans,
            "labResultGroups": self.lab_result_groups,
            "labResults": self.lab_results,
            "conditions": self.conditions,
            "immunization": self.immunization,
            "hashes": self.hashes,
        }

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "MammothPatient":
        doc = dict(doc)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls.model_validate(doc)

    def formatted_updated_at(self) -> str:
        """Return date formatted as MM/DD/YYYY (same as PHP toValueObject)."""
        if not self.updated_at:
            return ""
        try:
            dt = datetime.fromisoformat(self.updated_at)
            return dt.strftime("%m/%d/%Y")
        except ValueError:
            return self.updated_at
