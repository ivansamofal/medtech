"""
MongoDB document model for quest_locations collection.
Mirrors PHP QuestLocation Doctrine ODM document.
"""
from typing import Any

from pydantic import BaseModel, Field


class QuestLocation(BaseModel):
    id: str | None = Field(None, alias="_id")
    site_code: str = Field(alias="siteCode")
    site_name: str = Field("", alias="siteName")
    city: str = ""
    state: str = ""
    zip_code: str = Field("", alias="zipCode")
    latitude: float = 0.0
    longitude: float = 0.0
    address: str = ""
    phone: str = ""
    fax: str = ""
    # weekday → "HH:MM-HH:MM" | "X" | "VARY"
    standardized_drug_screen_hours: dict[str, str] = Field(
        default_factory=dict, alias="standardizedDrugScreenHours"
    )
    location_id: str | None = Field(None, alias="locationId")

    class Config:
        populate_by_name = True

    def to_doc(self) -> dict[str, Any]:
        return {
            "siteCode": self.site_code,
            "siteName": self.site_name,
            "city": self.city,
            "state": self.state,
            "zipCode": self.zip_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "phone": self.phone,
            "fax": self.fax,
            "standardizedDrugScreenHours": self.standardized_drug_screen_hours,
            "locationId": self.location_id,
        }

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "QuestLocation":
        doc = dict(doc)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls.model_validate(doc)

    def to_value_object(self) -> dict[str, Any]:
        return {
            "siteCode": self.site_code,
            "siteName": self.site_name,
            "city": self.city,
            "state": self.state,
            "zipCode": self.zip_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "address": self.address,
            "phone": self.phone,
            "standardizedDrugScreenHours": self.standardized_drug_screen_hours,
            "locationId": self.location_id,
        }
