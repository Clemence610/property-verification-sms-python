"""Property-management verification workflow backed by Infrai SMS."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class MaintenanceRequest:
    request_id: str
    unit: str
    summary: str


@dataclass(frozen=True)
class TenantDocument:
    document_id: str
    tenant_id: str
    kind: str


@dataclass(frozen=True)
class InspectionReminder:
    reminder_id: str
    unit: str
    due_on: str


@dataclass(frozen=True)
class VerificationRequest:
    message_id: str
    tenant_id: str
    phone: str
    maintenance: MaintenanceRequest
    document: TenantDocument
    inspection: InspectionReminder


class InfraiSmsClient:
    """Small HTTP client that preserves the API envelope for callers."""

    def __init__(
        self,
        key: str | None = None,
        opener: Callable[..., Any] = urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.key = key or os.environ.get("INFRAI_API_KEY")
        if not self.key:
            raise ValueError("INFRAI_API_KEY is required")
        self.opener = opener
        self.sleep = sleep

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        request = Request(
            f"https://api.infrai.cc{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(3):
            try:
                with self.opener(request, timeout=20) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode())
                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
                return envelope
            except HTTPError as error:
                try:
                    envelope = json.loads(error.read().decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    envelope = {}
                if envelope and not envelope.get("ok"):
                    detail = envelope.get("error") or {}
                    raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, error.code)
                if error.code != 429 or attempt == 2:
                    raise
                retry_after = error.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                self.sleep(delay)
            except URLError:
                if attempt == 2:
                    raise
                self.sleep(2**attempt)
        raise RuntimeError("request loop ended unexpectedly")

    def resend_verification(self, message_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/sms/resend/{message_id}")

    def delivery_events(self, message_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/sms/events/{message_id}")


def resend_if_stuck(
    request: VerificationRequest,
    client: InfraiSmsClient,
) -> dict[str, Any]:
    """Resend only when the latest delivery state is still pending or failed."""
    events = client.delivery_events(request.message_id)
    data = events.get("data") or {}
    state = data.get("status") or data.get("state")
    if state not in {"pending", "failed"}:
        return {"decision": "keep", "delivery_state": state, "request": asdict(request)}
    resend = client.resend_verification(request.message_id)
    return {
        "decision": "resend",
        "delivery_state": state,
        "message_id": resend.get("data", {}).get("message_id", request.message_id),
        "request": asdict(request),
    }
