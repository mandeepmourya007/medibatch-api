"""Talks to the upstream Hospital Directory API. Any failure is raised as HospitalApiError."""

import httpx

from app.models import Hospital


class HospitalApiError(Exception):
    """An upstream call failed (network error, timeout, or non-2xx response)."""


class HospitalApiClient:
    def __init__(self, base_url: str, timeout: float = 15.0, transport: httpx.AsyncBaseTransport | None = None):
        # `transport` lets tests swap in a fake server.
        self.http = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def create_hospital(self, hospital: Hospital, batch_id: str) -> int:
        payload = {"name": hospital.name, "address": hospital.address, "phone": hospital.phone, "creation_batch_id": batch_id}
        response = await self._request("POST", "/hospitals/", json=payload)
        try:
            return response.json()["id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise HospitalApiError("Create response did not include a hospital id") from exc

    async def activate_batch(self, batch_id: str) -> None:
        await self._request("PATCH", f"/hospitals/batch/{batch_id}/activate")

    async def delete_batch(self, batch_id: str) -> None:
        await self._request("DELETE", f"/hospitals/batch/{batch_id}")

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            response = await self.http.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise HospitalApiError(f"{method} {url} failed: {type(exc).__name__}") from exc
        if response.is_error:
            raise HospitalApiError(f"{method} {url} returned HTTP {response.status_code}")
        return response
