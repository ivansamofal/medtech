"""
HTTP client for the Mammoth EHR API.
Mirrors PHP MammothApiService.
"""
import asyncio
import logging
from typing import Any

import httpx
from cachetools import TTLCache

from core.config import settings

logger = logging.getLogger(__name__)

# Token cache: 14 days TTL, single slot
_TOKEN_CACHE: TTLCache = TTLCache(maxsize=1, ttl=60 * 60 * 24 * 14)
_EMPTY_VALUES = {"n/a", "not specified", "new member", "unknown"}

# Simple in-process rate limiter (tokens per minute)
_RATE_LIMIT = 60
_rate_lock = asyncio.Lock()
_rate_tokens = _RATE_LIMIT
_rate_refill_task: asyncio.Task | None = None


async def _refill_tokens() -> None:
    global _rate_tokens
    while True:
        await asyncio.sleep(60)
        async with _rate_lock:
            _rate_tokens = _RATE_LIMIT


async def _consume_rate_token() -> bool:
    global _rate_tokens, _rate_refill_task
    if _rate_refill_task is None or _rate_refill_task.done():
        loop = asyncio.get_event_loop()
        _rate_refill_task = loop.create_task(_refill_tokens())
    async with _rate_lock:
        if _rate_tokens <= 0:
            return False
        _rate_tokens -= 1
        return True


class MammothApiService:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)
        self._base_url = settings.mammoth_api_base_url.rstrip("/")

    # ── auth ──────────────────────────────────────────────────────

    async def login(self) -> str:
        if "token" in _TOKEN_CACHE:
            return _TOKEN_CACHE["token"]
        token = await self._send_login_request()
        _TOKEN_CACHE["token"] = token
        return token

    async def _send_login_request(self) -> str:
        response = await self._client.post(
            f"{self._base_url}/auth/email/login",
            json={
                "email": settings.mammoth_api_login_email,
                "password": settings.mammoth_api_login_password,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if not token:
            raise RuntimeError("Missing token in Mammoth login response")
        return token

    # ── patient data ──────────────────────────────────────────────

    async def get_patient_data(self, patient_id: str, url: str) -> dict[str, Any] | list[Any]:
        if not await _consume_rate_token():
            raise RuntimeError(f"Mammoth rate limit ({_RATE_LIMIT} req/min) exceeded")

        full_url = f"{self._base_url}/patients/patient/{patient_id}/{url}?limit=1000"
        return await self._send_request(full_url)

    async def get_lab_result(
        self,
        patient_id: str,
        url: str,
        lab_result_id: str,
    ) -> dict[str, Any] | list[Any]:
        full_url = (
            f"{self._base_url}/patients/patient/{patient_id}"
            f"/lab-result-group/{lab_result_id}/{url}?limit=1000"
        )
        return await self._send_request(full_url)

    async def create_patient(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = await self._get_headers()
        response = await self._client.post(
            f"{self._base_url}/patients",
            json=payload,
            headers=headers,
        )
        if response.status_code != 201:
            raise ValueError(f"Mammoth create patient error: {response.status_code} – {response.text}")

        content = response.json()
        if not content.get("success"):
            raise ValueError(f"Unexpected Mammoth response: {content}")
        if "data" not in content:
            raise ValueError("Missing 'data' in Mammoth create patient response")
        return content["data"]

    # ── internals ─────────────────────────────────────────────────

    async def _send_request(self, full_url: str) -> dict[str, Any] | list[Any]:
        try:
            headers = await self._get_headers()
            response = await self._client.get(full_url, headers=headers)

            if response.status_code not in (200, 404):
                raise ValueError(f"Unexpected Mammoth status code: {response.status_code}")

            data: dict = response.json()
            items = data.get("data", {})
            if isinstance(items, dict):
                items = items.get("items", items)

            return self._remove_empty_values(items if isinstance(items, list) else [items])
        except httpx.HTTPStatusError:
            return []

    async def _get_headers(self) -> dict[str, str]:
        token = await self.login()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "*/*",
            "Content-Type": "application/json",
        }

    def _remove_empty_values(self, data: Any) -> Any:
        """Recursively remove keys whose values are in _EMPTY_VALUES."""
        if isinstance(data, list):
            result = []
            for item in data:
                cleaned = self._remove_empty_values(item)
                if cleaned not in (None, {}, []):
                    result.append(cleaned)
            return result
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                cleaned = self._remove_empty_values(v)
                if cleaned not in (None, {}, []):
                    result[k] = cleaned
            return result
        if isinstance(data, str) and data.lower() in _EMPTY_VALUES:
            return None
        return data

    async def close(self) -> None:
        await self._client.aclose()
