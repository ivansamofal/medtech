"""
HTTP client for the Quest Booking (XML) API.
Mirrors PHP QuestBookingClient with HMAC-SHA1 authentication.
"""
import base64
import hashlib
import hmac
import logging
from email.utils import formatdate
from time import time
from xml.etree import ElementTree

import httpx

from core.config import settings

logger = logging.getLogger(__name__)


class QuestApiError(Exception):
    pass


class QuestBookingClient:
    def __init__(self) -> None:
        self._base_url = settings.quest_booking_base_url.rstrip("/")
        self._token = settings.quest_booking_authorization_token
        self._secret = settings.quest_booking_secret
        self._client = httpx.AsyncClient(timeout=30.0)

    def generate_digest(self, endpoint_url: str, method: str) -> tuple[str, str]:
        """Return (date_header, digest) – HMAC-SHA1 matching PHP implementation."""
        date_header = formatdate(usegmt=True)
        message = f"{method}\n\ntext/xml\n\nx-yournextagency-date:{date_header}\n{endpoint_url}"
        raw_hmac = hmac.new(
            self._secret.encode(),
            message.encode(),
            hashlib.sha1,
        ).digest()
        digest = base64.b64encode(raw_hmac).decode()
        return date_header, digest

    def _get_headers(self, endpoint_url: str, method: str) -> dict[str, str]:
        date_header, digest = self.generate_digest(endpoint_url, method)
        return {
            "Accept": "*/*",
            "Cache-Control": "no-cache",
            "Content-Type": "text/xml",
            "x-yournextagency-date": date_header,
            "Authorization": f"yournextagency {self._token}:{digest}",
        }

    async def request(
        self,
        endpoint_url: str,
        body: str | None = None,
        method: str = "POST",
    ) -> str:
        url = self._base_url + endpoint_url
        headers = self._get_headers(endpoint_url, method)

        try:
            if method == "GET":
                response = await self._client.get(url, headers=headers)
            else:
                response = await self._client.post(url, content=body or "", headers=headers)

            if response.status_code != 200:
                logger.error(
                    "Quest booking API error %d for %s",
                    response.status_code,
                    endpoint_url,
                )

            content = response.text
            return content

        except httpx.HTTPStatusError as exc:
            error_msg = self._parse_error_response(exc.response.text)
            raise QuestApiError(error_msg or "Quest API request failed") from exc

    def _parse_error_response(self, xml_text: str) -> str:
        try:
            root = ElementTree.fromstring(xml_text)
            resp_code = root.findtext("respcode") or ""
            resp_message = root.findtext("respmessage") or ""
            if resp_message:
                return f"{resp_message} (Code: {resp_code})" if resp_code else resp_message
            if resp_code:
                return f"Quest API error (Code: {resp_code})"
            return "Unknown Quest API error"
        except Exception:
            return "Failed to parse Quest API error response"

    async def close(self) -> None:
        await self._client.aclose()
