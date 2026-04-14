"""
Repository for the `patient_mammoth_data` MongoDB collection.
Mirrors PHP MammothPatientRepository.
"""
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, ReturnDocument

from mammoth.models.mammoth_patient import MammothPatient


COLLECTION = "patient_mammoth_data"


class MammothPatientRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION]

    async def ensure_indexes(self) -> None:
        await self.col.create_index([("patientId", ASCENDING)], unique=True)

    # ── reads ─────────────────────────────────────────────────────

    async def get_by_uid(self, patient_id: str) -> MammothPatient | None:
        doc = await self.col.find_one({"patientId": patient_id})
        return MammothPatient.from_doc(doc) if doc else None

    async def find_all_uids(self) -> list[str]:
        cursor = self.col.find({}, {"patientId": 1, "_id": 0})
        return [doc["patientId"] async for doc in cursor if doc.get("patientId")]

    async def get_hashes(self, patient_id: str) -> dict[str, str]:
        doc = await self.col.find_one({"patientId": patient_id}, {"hashes": 1, "_id": 0})
        return doc.get("hashes", {}) if doc else {}

    # ── writes ────────────────────────────────────────────────────

    async def update_status(
        self,
        patient_id: str,
        status: str,
        updated_at: str,
    ) -> None:
        """Upsert status + updatedAt (creates document if not present)."""
        await self.col.update_one(
            {"patientId": patient_id},
            {"$set": {"status": status, "updatedAt": updated_at}},
            upsert=True,
        )

    async def update_field(
        self,
        patient_id: str,
        field_name: str,
        data: list[Any] | dict[str, Any],
        current_hash: str,
        hash_key: str,
    ) -> None:
        """Update a single data field and its hash atomically."""
        await self.col.update_one(
            {"patientId": patient_id},
            {
                "$set": {
                    field_name: data,
                    f"hashes.{hash_key}": current_hash,
                }
            },
            upsert=True,
        )

    async def delete_by_patient_id(self, patient_id: str) -> None:
        await self.col.delete_one({"patientId": patient_id})

    # ── sorting helpers (mirrors getPatientUidsToUpdate) ──────────

    async def get_patient_uids_to_update(self, uids: list[str]) -> list[str]:
        """Return patient IDs sorted by updatedAt ascending."""
        cursor = self.col.find(
            {"patientId": {"$in": uids}},
            {"patientId": 1, "updatedAt": 1, "_id": 0},
        ).sort("updatedAt", ASCENDING)
        return [doc["patientId"] async for doc in cursor]
