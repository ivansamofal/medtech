"""
Repository for the `quest_locations` MongoDB collection.
Mirrors PHP QuestLocationRepository (includes geospatial + text search).
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, GEOSPHERE

from quest.models.quest_location import QuestLocation

COLLECTION = "quest_locations"


class QuestLocationRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION]

    async def ensure_indexes(self) -> None:
        await self.col.create_index([("siteCode", ASCENDING)], unique=True)
        # 2dsphere for geospatial search requires a GeoJSON field;
        # we store lat/lon and compute distance via $geoNear in aggregation.

    # ── reads ─────────────────────────────────────────────────────

    async def find_by_site_code(self, code: str) -> QuestLocation | None:
        doc = await self.col.find_one({"siteCode": code})
        return QuestLocation.from_doc(doc) if doc else None

    async def find_by_site_codes(self, codes: list[str]) -> list[QuestLocation]:
        cursor = self.col.find({"siteCode": {"$in": codes}})
        return [QuestLocation.from_doc(doc) async for doc in cursor]

    async def find_all(self) -> list[QuestLocation]:
        cursor = self.col.find({})
        return [QuestLocation.from_doc(doc) async for doc in cursor]

    async def find_by_filters(
        self,
        city: str | None,
        state: str | None,
        search: str | None = None,
        site_codes: list[str] | None = None,
    ) -> list[QuestLocation]:
        query: dict = {}
        if city:
            query["city"] = {"$regex": city, "$options": "i"}
        if state:
            query["state"] = state.upper()
        if search:
            query["$or"] = [
                {"siteName": {"$regex": search, "$options": "i"}},
                {"address": {"$regex": search, "$options": "i"}},
                {"city": {"$regex": search, "$options": "i"}},
            ]
        if site_codes:
            query["siteCode"] = {"$in": site_codes}

        cursor = self.col.find(query)
        return [QuestLocation.from_doc(doc) async for doc in cursor]

    async def find_by_zipcode(
        self,
        zip_code: str,
        city: str | None = None,
        state: str | None = None,
        site_codes: list[str] | None = None,
    ) -> list[QuestLocation]:
        query: dict = {"zipCode": zip_code}
        if city:
            query["city"] = {"$regex": city, "$options": "i"}
        if state:
            query["state"] = state.upper()
        if site_codes:
            query["siteCode"] = {"$in": site_codes}
        cursor = self.col.find(query)
        return [QuestLocation.from_doc(doc) async for doc in cursor]

    async def find_near_coordinates(
        self,
        lat: float,
        lon: float,
        radius_meters: float,
        site_codes: list[str] | None = None,
    ) -> list[QuestLocation]:
        """
        Simple Euclidean distance filter (no 2dsphere index required).
        For production accuracy replace with MongoDB $geoNear + 2dsphere index.
        """
        # Approximate degrees per meter at mid-latitudes
        deg_per_meter = 1 / 111_000
        radius_deg = radius_meters * deg_per_meter

        query: dict = {
            "latitude": {"$gte": lat - radius_deg, "$lte": lat + radius_deg},
            "longitude": {"$gte": lon - radius_deg, "$lte": lon + radius_deg},
        }
        if site_codes:
            query["siteCode"] = {"$in": site_codes}

        cursor = self.col.find(query)
        return [QuestLocation.from_doc(doc) async for doc in cursor]

    async def get_all_cities(self) -> list[str]:
        return await self.col.distinct("city")

    async def get_cities_by_state(self, state: str) -> list[str]:
        return await self.col.distinct("city", {"state": state.upper()})

    # ── writes ────────────────────────────────────────────────────

    async def upsert(self, location: QuestLocation) -> None:
        await self.col.update_one(
            {"siteCode": location.site_code},
            {"$set": location.to_doc()},
            upsert=True,
        )

    async def truncate_and_save_many(self, locations: list[QuestLocation]) -> None:
        await self.col.delete_many({})
        if locations:
            await self.col.insert_many([loc.to_doc() for loc in locations])
