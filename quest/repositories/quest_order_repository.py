"""
Repository for the `quest_orders` MongoDB collection.
"""
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING

from quest.models.quest_order import QuestOrder

COLLECTION = "quest_orders"


class QuestOrderRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION]

    async def ensure_indexes(self) -> None:
        await self.col.create_index([("patientId", ASCENDING)], unique=True)

    async def find_by_patient_id(self, patient_id: int) -> list[QuestOrder]:
        cursor = self.col.find({"patientId": patient_id})
        return [QuestOrder.from_doc(doc) async for doc in cursor]

    async def find_by_order_ids(self, order_ids: list[str]) -> list[QuestOrder]:
        cursor = self.col.find({"orderId": {"$in": order_ids}})
        return [QuestOrder.from_doc(doc) async for doc in cursor]

    async def find_by_patient_id_and_status(
        self, patient_id: int, status: str
    ) -> list[QuestOrder]:
        cursor = self.col.find({"patientId": patient_id, "status": status})
        return [QuestOrder.from_doc(doc) async for doc in cursor]

    async def find_by_external_order_item_id(self, item_id: int) -> QuestOrder | None:
        doc = await self.col.find_one({"externalOrderItemId": item_id})
        return QuestOrder.from_doc(doc) if doc else None

    async def find_all_sent(self) -> list[QuestOrder]:
        cursor = self.col.find({"status": "sent"})
        return [QuestOrder.from_doc(doc) async for doc in cursor]

    async def upsert(self, order: QuestOrder) -> QuestOrder:
        doc = order.to_doc()
        result = await self.col.find_one_and_update(
            {"orderId": order.order_id},
            {"$set": doc},
            upsert=True,
            return_document=True,
        )
        return QuestOrder.from_doc(result)

    async def save(self, order: QuestOrder) -> None:
        await self.col.update_one(
            {"orderId": order.order_id},
            {"$set": order.to_doc()},
            upsert=True,
        )
