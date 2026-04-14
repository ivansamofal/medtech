"""
Repository for the `quest_appointments` MongoDB collection.
Mirrors PHP QuestAppointmentRepository.
"""
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from quest.enums import QuestAppointmentStatusEnum
from quest.models.quest_appointment import QuestAppointment

COLLECTION = "quest_appointments"


class QuestAppointmentRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION]

    async def ensure_indexes(self) -> None:
        await self.col.create_index([("confirmationId", ASCENDING)], unique=True)
        await self.col.create_index([("patientId", ASCENDING)])
        await self.col.create_index([("locationCode", ASCENDING), ("appointmentStart", ASCENDING)])

    # ── reads ─────────────────────────────────────────────────────

    async def find_by_confirmation_id(self, confirmation_id: str) -> QuestAppointment | None:
        doc = await self.col.find_one({"confirmationId": confirmation_id})
        return QuestAppointment.from_doc(doc) if doc else None

    async def find_by_patient_id(self, patient_id: int) -> list[QuestAppointment]:
        cursor = self.col.find(
            {
                "patientId": patient_id,
                "status": {"$ne": QuestAppointmentStatusEnum.CANCELLED.value},
            }
        ).sort("appointmentStart", DESCENDING)
        return [QuestAppointment.from_doc(doc) async for doc in cursor]

    async def find_by_location_code(self, code: str) -> list[QuestAppointment]:
        cursor = self.col.find({"locationCode": code}).sort("appointmentStart", ASCENDING)
        return [QuestAppointment.from_doc(doc) async for doc in cursor]

    async def find_by_site_codes(self, codes: list[str]) -> list[QuestAppointment]:
        cursor = self.col.find({"locationCode": {"$in": codes}})
        return [QuestAppointment.from_doc(doc) async for doc in cursor]

    async def find_upcoming(self, from_date: datetime) -> list[QuestAppointment]:
        cursor = self.col.find(
            {
                "appointmentStart": {"$gte": from_date},
                "status": {"$ne": QuestAppointmentStatusEnum.CANCELLED.value},
            }
        ).sort("appointmentStart", ASCENDING)
        return [QuestAppointment.from_doc(doc) async for doc in cursor]

    # ── writes ────────────────────────────────────────────────────

    async def upsert_by_confirmation_id(self, appointment: QuestAppointment) -> QuestAppointment:
        doc = appointment.to_doc()
        doc["updatedAt"] = datetime.now(timezone.utc)
        result = await self.col.find_one_and_update(
            {"confirmationId": appointment.confirmation_id},
            {"$set": doc, "$setOnInsert": {"createdAt": datetime.now(timezone.utc)}},
            upsert=True,
            return_document=True,
        )
        return QuestAppointment.from_doc(result)

    async def save(self, appointment: QuestAppointment) -> None:
        doc = appointment.to_doc()
        doc["updatedAt"] = datetime.now(timezone.utc)
        await self.col.update_one(
            {"confirmationId": appointment.confirmation_id},
            {"$set": doc},
            upsert=True,
        )

    async def save_many(self, appointments: list[QuestAppointment]) -> None:
        for appt in appointments:
            await self.upsert_by_confirmation_id(appt)
