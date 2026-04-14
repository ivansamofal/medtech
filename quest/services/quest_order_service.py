"""
Quest order submission and result collection.
Mirrors PHP QuestService (orderSubmit + collectResults).
"""
import base64
import logging
from datetime import datetime, timezone
from typing import Any

from quest.enums import QuestOrderStatusEnum, QuestOrderUrlEnum, QuestResultTypeEnum
from quest.models.quest_order import QuestOrder, QuestOrderResult
from quest.repositories.quest_order_repository import QuestOrderRepository
from quest.services.quest_api_client import QuestApiClient

logger = logging.getLogger(__name__)


class QuestOrderService:
    def __init__(
        self,
        order_repo: QuestOrderRepository,
        api_client: QuestApiClient,
    ) -> None:
        self._repo = order_repo
        self._api = api_client

    # ── Order Submission ──────────────────────────────────────────

    async def submit_order(
        self,
        patient_id: int,
        order_id: str,
        test_codes: list[str],
        hl7_message: str,
        external_order_item_id: int | None = None,
    ) -> QuestOrder:
        order = QuestOrder(
            orderId=order_id,
            patientId=patient_id,
            testCodes=test_codes,
            externalOrderItemId=external_order_item_id,
            orderMessage=hl7_message,
        )

        try:
            response = await self._api.request(
                QuestOrderUrlEnum.ORDER_SUBMISSION.value,
                method="POST",
                data=hl7_message,
            )
            if response:
                order.status = QuestOrderStatusEnum.SENT.value
                logger.info("Quest order %s submitted successfully", order_id)
            else:
                order.status = QuestOrderStatusEnum.ERROR.value
                logger.error("Quest order %s submission returned empty response", order_id)
        except Exception as exc:
            order.status = QuestOrderStatusEnum.ERROR.value
            logger.error("Quest order %s submission failed: %s", order_id, exc)

        await self._repo.upsert(order)
        return order

    # ── Result Collection ─────────────────────────────────────────

    async def collect_results(self) -> None:
        """
        Poll Quest API for results for all SENT orders.
        Mirrors PHP CollectResultsHandler → QuestService::collectResults().
        """
        sent_orders = await self._repo.find_all_sent()
        if not sent_orders:
            logger.info("No SENT Quest orders to collect results for")
            return

        logger.info("Collecting Quest results for %d orders", len(sent_orders))

        # Request HL7 results
        token = await self._api.request_token()
        result_response = await self._api.request(
            QuestOrderUrlEnum.GET_RESULTS.value,
            method="POST",
            json={"resultType": QuestResultTypeEnum.HL7.value},
        )

        if not result_response:
            logger.warning("Empty Quest results response")
            return

        try:
            results_data: dict = __import__("json").loads(result_response)
        except Exception:
            logger.error("Failed to parse Quest results response as JSON")
            return

        # Map order IDs to orders for fast lookup
        order_map: dict[str, QuestOrder] = {o.order_id: o for o in sent_orders}

        for result_item in results_data.get("results", []):
            order_id: str = result_item.get("orderId", "")
            control_id: str = result_item.get("controlId", "")
            hl7_message: str = result_item.get("hl7Message", "")

            if order_id not in order_map:
                continue

            order = order_map[order_id]
            # Store base64-encoded HL7 message (mirrors PHP implementation)
            encoded = base64.b64encode(hl7_message.encode()).decode()
            order.result_messages[control_id] = encoded

            # Build embedded result object
            order_result = QuestOrderResult(
                controlId=control_id,
                hl7Message=hl7_message,
                parsedData=result_item.get("parsedData", {}),
            )
            # Replace existing result for this controlId
            order.results = [r for r in order.results if r.control_id != control_id]
            order.results.append(order_result)

            order.status = QuestOrderStatusEnum.COMPLETED.value
            order.received_result_at = datetime.now(timezone.utc)
            await self._repo.save(order)

        # Acknowledge results
        await self._api.request(
            QuestOrderUrlEnum.ACKNOWLEDGE_RESULTS.value,
            method="POST",
            json={"resultType": QuestResultTypeEnum.HL7.value},
        )
        logger.info("Quest results collected and acknowledged")

    # ── Documents / Requisitions ──────────────────────────────────

    async def fetch_requisition_documents(self, order: QuestOrder) -> None:
        """Request requisition documents for an order from Quest API."""
        response = await self._api.request(
            QuestOrderUrlEnum.ORDER_DOCUMENT.value,
            method="POST",
            json={"orderId": order.order_id, "documentType": "REQ"},
        )
        if not response:
            return

        try:
            data: dict = __import__("json").loads(response)
            from quest.models.quest_order import QuestRequisitionDocument
            docs = []
            for doc in data.get("documents", []):
                docs.append(QuestRequisitionDocument(
                    documentType=doc.get("type", "REQ"),
                    s3Key=doc.get("s3Key", ""),
                    contentType=doc.get("contentType", "application/pdf"),
                ))
            order.requisition_documents = docs
            await self._repo.save(order)
        except Exception as exc:
            logger.error("Failed to parse requisition documents for order %s: %s", order.order_id, exc)
