"""
Request DTOs – mirrors MammothPatientCreateRequestValueObject /
MammothPatientRegistrationRequestValueObject.
"""
import re
from datetime import date
from pydantic import BaseModel, field_validator


class AddressRequest(BaseModel):
    line: str
    city: str
    state: str
    postal_code: str
    phone: str
    is_current: bool = False

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z]{2}", v):
            raise ValueError("state must be exactly 2 uppercase letters")
        return v

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{5}", v):
            raise ValueError("postalCode must be exactly 5 digits")
        return v


class MammothPatientCreateRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str
    street: str
    city: str
    state: str
    postal_code: str
    gender: str
    dob: date
    additional_addresses: list[AddressRequest] = []

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v:
            raise ValueError("must not be blank")
        if not re.fullmatch(r"[a-zA-Z]+", v):
            raise ValueError("must contain only letters")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.fullmatch(r"^\+?\d{10,15}$", v):
            raise ValueError("invalid phone number")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z]{2}", v):
            raise ValueError("state must be exactly 2 uppercase letters")
        return v

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str) -> str:
        if not re.fullmatch(r"\d{5}", v):
            raise ValueError("postalCode must be exactly 5 digits")
        return v

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        if v not in ("male", "female"):
            raise ValueError("gender must be 'male' or 'female'")
        return v

    def to_mammoth_payload(self) -> dict:
        """Build the JSON payload expected by the Mammoth API."""
        addresses = [
            {
                "line": self.street,
                "city": self.city,
                "state": self.state,
                "postalCode": self.postal_code,
                "phone": self.phone,
                "isCurrent": True,
            }
        ]
        for addr in self.additional_addresses:
            addresses.append(
                {
                    "line": addr.line,
                    "city": addr.city,
                    "state": addr.state,
                    "postalCode": addr.postal_code,
                    "phone": addr.phone,
                    "isCurrent": addr.is_current,
                }
            )

        return {
            "firstName": self.first_name,
            "lastName": self.last_name,
            "phone": self.phone,
            "gender": self.gender,
            "dob": self.dob.strftime("%Y-%m-%d"),
            "livingAddresses": addresses,
        }
