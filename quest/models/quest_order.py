"""
MongoDB document model for quest_orders collection.
Mirrors PHP QuestOrder Doctrine ODM document.
"""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from quest.enums import QuestOrderStatusEnum


class QuestOrderResult(BaseModel):
    """Embedded result for a single control-ID."""
    control_id: str = Field(alias="controlId")
    hl7_message: str = Field("", alias="hl7Message")
    parsed_data: dict[str, Any] = Field(default_factory=dict, alias="parsedData")

    class Config:
        populate_by_name = True


class QuestPdfResultFile(BaseModel):
    control_id: str = Field(alias="controlId")
    s3_key: str = Field("", alias="s3Key")
    content_type: str = Field("application/pdf", alias="contentType")

    class Config:
        populate_by_name = True


class QuestRequisitionDocument(BaseModel):
    document_type: str = Field(alias="documentType")
    s3_key: str = Field("", alias="s3Key")
    content_type: str = Field("application/pdf", alias="contentType")

    class Config:
        populate_by_name = True


class QuestOrder(BaseModel):
    id: str | None = Field(None, alias="_id")
    order_id: str = Field(alias="orderId")
    patient_id: int = Field(alias="patientId")
    test_codes: list[str] = Field(default_factory=list, alias="testCodes")
    external_order_item_id: int | None = Field(None, alias="externalOrderItemId")
    status: str = QuestOrderStatusEnum.NEW.value
    order_message: str = Field("", alias="orderMessage")
    result_messages: dict[str, str] = Field(default_factory=dict, alias="resultMessages")
    results: list[QuestOrderResult] = Field(default_factory=list)
    pdf_result_files: list[QuestPdfResultFile] = Field(default_factory=list, alias="pdfResultFiles")
    requisition_documents: list[QuestRequisitionDocument] = Field(
        default_factory=list, alias="requisitionDocuments"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")
    received_result_at: datetime | None = Field(None, alias="receivedResultAt")

    class Config:
        populate_by_name = True

    def to_doc(self) -> dict[str, Any]:
        return {
            "orderId": self.order_id,
            "patientId": self.patient_id,
            "testCodes": self.test_codes,
            "externalOrderItemId": self.external_order_item_id,
            "status": self.status,
            "orderMessage": self.order_message,
            "resultMessages": self.result_messages,
            "results": [r.model_dump(by_alias=True) for r in self.results],
            "pdfResultFiles": [f.model_dump(by_alias=True) for f in self.pdf_result_files],
            "requisitionDocuments": [d.model_dump(by_alias=True) for d in self.requisition_documents],
            "createdAt": self.created_at,
            "receivedResultAt": self.received_result_at,
        }

    @classmethod
    def from_doc(cls, doc: dict[str, Any]) -> "QuestOrder":
        doc = dict(doc)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls.model_validate(doc)

    def to_value_object(self) -> dict[str, Any]:
        return {
            "orderId": self.order_id,
            "patientId": self.patient_id,
            "testCodes": self.test_codes,
            "status": self.status,
            "externalOrderItemId": self.external_order_item_id,
            "resultMessage": next(iter(reversed(list(self.result_messages.values()))), None),
        }
