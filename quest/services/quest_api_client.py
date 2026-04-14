"""
HTTP client for the Quest Orders / Results (JSON) API.
Mirrors PHP QuestApiClient with OAuth2 client_credentials grant.
"""
import logging
from typing import Any

import httpx

from core.config import settings
from quest.enums import QuestOrderUrlEnum

logger = logging.getLogger(__name__)


class QuestApiException(Exception):
    def __init__(self, message: str, status_code: int = 0, body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class QuestApiClient:
    def __init__(self) -> None:
        self._base_url = settings.quest_orders_base_url.rstrip("/")
        self._client_id = settings.quest_client_id
        self._client_secret = settings.quest_client_secret
        self._http = httpx.AsyncClient(timeout=30.0)
        self._token: str | None = None

    async def request_token(self) -> str:
        url = self._base_url + QuestOrderUrlEnum.TOKEN.value
        response = await self._http.post(
            url,
            headers={
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if response.status_code != 200:
            raise QuestApiException(
                "Quest API error while requesting token",
                response.status_code,
                response.text,
            )
        return response.json()["access_token"]

    async def _get_token(self) -> str:
        if self._token is None:
            self._token = await self.request_token()
        return self._token

    async def request(
        self,
        url_path: str,
        method: str = "POST",
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: str | None = None,
    ) -> str:
        token = await self._get_token()
        url = self._base_url + url_path
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        try:
            response = await self._http.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                content=data,
            )

            if response.status_code in (500, 429):
                error_msg = f"Quest API error {response.status_code} for {url}"
                logger.error(error_msg)
                raise QuestApiException(error_msg, response.status_code)

            return response.text

        except QuestApiException:
            raise
        except httpx.HTTPStatusError:
            return ""
        except Exception as exc:
            logger.error("Quest API request failed for %s: %s", url, exc)
            return ""

    async def close(self) -> None:
        await self._http.aclose()
