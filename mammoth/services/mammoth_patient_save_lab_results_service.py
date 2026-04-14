"""
Fetches & persists lab results for a Mammoth patient.
Mirrors PHP MammothPatientSaveLabResultsService.
"""
import logging
from typing import Any

from mammoth.repositories.mammoth_patient_repository import MammothPatientRepository
from mammoth.services.mammoth_api_service import MammothApiService

logger = logging.getLogger(__name__)


class MammothPatientSaveLabResultsService:
    def __init__(
        self,
        repository: MammothPatientRepository,
        api_service: MammothApiService,
    ) -> None:
        self._repo = repository
        self._api = api_service

    async def save(self, patient_uid: str) -> None:
        patient = await self._repo.get_by_uid(patient_uid)
        if patient is None:
            logger.warning("Mammoth patient not found: %s", patient_uid)
            return

        # Fetch lab-result groups
        raw_groups = await self._api.get_patient_data(patient_uid, "lab-result-groups")
        groups: list[dict[str, Any]] = raw_groups if isinstance(raw_groups, list) else []

        # Only process groups that have location data
        groups_with_location = [g for g in groups if g.get("location")]

        # Fetch individual lab results for each group
        all_lab_results: list[dict[str, Any]] = []
        for group in groups_with_location:
            group_id = group.get("id") or group.get("groupId")
            if not group_id:
                continue
            try:
                results = await self._api.get_lab_result(patient_uid, "lab-results", str(group_id))
                if isinstance(results, list):
                    all_lab_results.extend(results)
            except Exception as exc:
                logger.error(
                    "Error fetching lab results for patient %s, group %s: %s",
                    patient_uid,
                    group_id,
                    exc,
                )

        # Persist
        await self._repo.update_field(
            patient_uid,
            "labResultGroups",
            groups_with_location,
            "",
            "lab-result-groups",
        )
        await self._repo.update_field(
            patient_uid,
            "labResults",
            all_lab_results,
            "",
            "lab-results",
        )
        logger.info(
            "Saved %d lab-result groups and %d lab results for patient %s",
            len(groups_with_location),
            len(all_lab_results),
            patient_uid,
        )
