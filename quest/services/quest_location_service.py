"""
Location search service – mirrors PHP QuestLocationService.
"""
import logging
from typing import Any

from core.config import settings
from quest.models.quest_location import QuestLocation
from quest.repositories.quest_location_repository import QuestLocationRepository

logger = logging.getLogger(__name__)


class QuestLocationService:
    def __init__(self, repo: QuestLocationRepository) -> None:
        self._repo = repo

    async def find_by_site_code(self, code: str) -> QuestLocation | None:
        return await self._repo.find_by_site_code(code)

    async def find_by_site_codes(self, codes: list[str]) -> list[QuestLocation]:
        return await self._repo.find_by_site_codes(codes)

    async def find_by_filters(
        self,
        city: str | None,
        state: str | None,
        search: str | None = None,
        site_codes: list[str] | None = None,
    ) -> list[QuestLocation]:
        """
        Mirrors PHP logic:
         1. If search looks like a ZIP code → zipcode search (with geocoding radius fallback).
         2. Otherwise → text / city / state filter.
        """
        if search and search.strip().isdigit() and len(search.strip()) == 5:
            return await self._find_by_zip(search.strip(), city, state, site_codes)

        return await self._repo.find_by_filters(city, state, search, site_codes)

    async def _find_by_zip(
        self,
        zip_code: str,
        city: str | None,
        state: str | None,
        site_codes: list[str] | None,
    ) -> list[QuestLocation]:
        exact = await self._repo.find_by_zipcode(zip_code, city, state, site_codes)
        if exact:
            return exact

        # Fallback: find a reference location for this ZIP and do radius search
        reference = await self._repo.find_by_zipcode(zip_code)
        if reference:
            ref = reference[0]
            return await self._repo.find_near_coordinates(
                ref.latitude,
                ref.longitude,
                settings.quest_zip_search_radius_meters,
                site_codes,
            )

        return []

    async def truncate_and_save_many(self, locations: list[QuestLocation]) -> None:
        await self._repo.truncate_and_save_many(locations)

    def to_value_objects(self, locations: list[QuestLocation]) -> list[dict[str, Any]]:
        return [loc.to_value_object() for loc in locations]
