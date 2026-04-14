from enum import Enum
import re


class MammothPatientStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class MammothDataTypesEnum(str, Enum):
    OVERVIEW = "overview"
    VITAL_SIGNS = "vitalSigns"
    PROCEDURES = "procedures"
    MEDICATIONS = "medications"
    SOCIAL_HISTORIES = "socialHistories"
    INSURANCE_PROVIDERS = "insuranceProviders"
    ALLERGIES = "allergies"
    FAMILY_HISTORIES = "familyHistories"
    ENCOUNTERS = "encounters"
    CARE_PLANS = "carePlans"
    LAB_RESULT_GROUPS = "labResultGroups"
    CONDITIONS = "conditions"
    IMMUNIZATION = "immunization"

    @classmethod
    def get_urls(cls) -> dict[str, str]:
        """Returns {field_name: url_segment} – camelCase → kebab-case."""
        result = {}
        for member in cls:
            url = re.sub(r"([a-z])([A-Z])", r"\1-\2", member.value).lower()
            result[member.value] = url
        return result

    @classmethod
    def fields_with_title(cls) -> list[str]:
        return [
            cls.CONDITIONS.value,
            cls.PROCEDURES.value,
            cls.MEDICATIONS.value,
            cls.IMMUNIZATION.value,
        ]
