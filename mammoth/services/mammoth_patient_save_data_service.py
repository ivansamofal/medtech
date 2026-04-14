"""
Orchestrates fetching & persisting Mammoth patient data.
Mirrors PHP MammothPatientSaveDataService.
"""
import logging
from datetime import datetime, timezone
from typing import Any

from mammoth.enums import MammothDataTypesEnum, MammothPatientStatusEnum
from mammoth.models.mammoth_patient import MammothPatient
from mammoth.repositories.mammoth_patient_repository import MammothPatientRepository
from mammoth.services.mammoth_api_service import MammothApiService
from mammoth.services.mammoth_data_hash_service import MammothDataHashService

logger = logging.getLogger(__name__)

DEFAULT_RETRY_DELAY = 600    # seconds (PHP: 600 000 ms)
DEFAULT_RETRY_COUNT = 2


class MammothPatientSaveDataService:
    def __init__(
        self,
        repository: MammothPatientRepository,
        api_service: MammothApiService,
        hash_service: MammothDataHashService,
    ) -> None:
        self._repo = repository
        self._api = api_service
        self._hash = hash_service

    async def save(self, patient_uid: str, retry_count: int = 0) -> MammothPatient:
        await self._save_patient_data(patient_uid)

        patient = await self._repo.get_by_uid(patient_uid)
        if patient is None:
            raise ValueError(f"Failed to save Mammoth patient {patient_uid}")

        if patient.status == MammothPatientStatusEnum.PENDING.value:
            if retry_count < DEFAULT_RETRY_COUNT:
                # Re-enqueue with delay (handled by Celery task caller)
                from mammoth.tasks.mammoth_tasks import save_mammoth_patient_data
                save_mammoth_patient_data.apply_async(
                    args=[patient_uid, retry_count + 1],
                    countdown=DEFAULT_RETRY_DELAY,
                )
            return patient

        if patient.status == MammothPatientStatusEnum.SUCCESS.value:
            # Trigger lab results save with delay
            from mammoth.tasks.mammoth_tasks import save_mammoth_lab_results
            from core.config import settings
            save_mammoth_lab_results.apply_async(
                args=[patient_uid],
                countdown=settings.mammoth_lab_results_delay,
            )

        return patient

    async def get_mammoth_patient_status(
        self, patient_uid: str
    ) -> MammothPatientStatusEnum | None:
        status_data = await self._api.get_patient_data(patient_uid, "status")
        if isinstance(status_data, dict) and "status" in status_data:
            return MammothPatientStatusEnum(status_data["status"].lower())
        if isinstance(status_data, list) and status_data:
            raw = status_data[0]
            if isinstance(raw, dict) and "status" in raw:
                return MammothPatientStatusEnum(raw["status"].lower())
        return None

    # ── private ───────────────────────────────────────────────────

    async def _save_patient_data(self, patient_id: str) -> None:
        status = await self.get_mammoth_patient_status(patient_id)
        status_value = status.value if status else ""
        updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        await self._repo.update_status(patient_id, status_value, updated_at)

        if status == MammothPatientStatusEnum.SUCCESS:
            await self._update_patient_data_fields(patient_id)

    async def _update_patient_data_fields(self, patient_id: str) -> None:
        stored_hashes = await self._repo.get_hashes(patient_id)

        for field_name, url in MammothDataTypesEnum.get_urls().items():
            try:
                raw = await self._api.get_patient_data(patient_id, url)
                data: list[Any] = raw if isinstance(raw, list) else [raw] if raw else []
            except Exception as exc:
                logger.error(
                    "Error fetching Mammoth data for %s / %s: %s",
                    patient_id,
                    url,
                    exc,
                )
                data = []

            data = self._filter_items_without_title(field_name, data)
            await self._update_field_if_changed(patient_id, url, field_name, data, stored_hashes)

    def _filter_items_without_title(
        self, field_name: str, data: list[Any]
    ) -> list[Any]:
        if field_name not in MammothDataTypesEnum.fields_with_title():
            return data
        return [
            item
            for item in data
            if not isinstance(item, dict) or (item.get("title") not in (None, ""))
        ]

    async def _update_field_if_changed(
        self,
        patient_id: str,
        url: str,
        field_name: str,
        data: list[Any],
        stored_hashes: dict[str, str],
    ) -> None:
        current_hash = self._hash.hash(data)
        stored_hash = stored_hashes.get(url)

        if stored_hash is None or self._hash.has_changed(stored_hash, current_hash):
            await self._repo.update_field(patient_id, field_name, data, current_hash, url)
