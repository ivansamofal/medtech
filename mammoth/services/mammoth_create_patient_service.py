"""
Creates a Mammoth patient via the external API.
Mirrors PHP MammothCreatePatientService.
"""
import logging
from typing import Any

from mammoth.schemas.requests import MammothPatientCreateRequest
from mammoth.schemas.responses import MammothPatientCreateResponse
from mammoth.services.mammoth_api_service import MammothApiService

logger = logging.getLogger(__name__)


class MammothCreatePatientService:
    def __init__(self, api_service: MammothApiService) -> None:
        self._api = api_service

    async def create(self, request: MammothPatientCreateRequest) -> MammothPatientCreateResponse:
        payload = request.to_mammoth_payload()
        data: dict[str, Any] = await self._api.create_patient(payload)

        return MammothPatientCreateResponse(
            id=str(data.get("id", "")),
            first_name=data.get("firstName", ""),
            last_name=data.get("lastName", ""),
            phone=data.get("phone", ""),
            status=data.get("status", ""),
        )
