"""Production-safe Dottle monitoring — fire-and-forget, never blocks the agent."""

from __future__ import annotations

import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

import requests

# Ingest routes are under /api/v1 (see Dottle API).
_DEFAULT_DOTTLE_URL = "https://dottle-production.up.railway.app/api/v1"


def _dottle_url() -> str:
    return (os.getenv("DOTTLE_URL") or _DEFAULT_DOTTLE_URL).rstrip("/")


def _headers() -> dict[str, str] | None:
    key = (os.getenv("DOTTLE_API_KEY") or "").strip()
    if not key:
        return None
    return {"X-API-Key": key, "Content-Type": "application/json"}


def _test_sync_posts() -> bool:
    """When true, ingest runs synchronously (for scenario tests / CI). Production default: false."""
    return os.getenv("DOTTLE_TEST_SYNC", "").strip().lower() in ("1", "true", "yes")


def _redact_pii_enabled() -> bool:
    return os.getenv("DOTTLE_REDACT_PII", "").strip().lower() in ("1", "true", "yes")


def _tags() -> list[str]:
    raw = (os.getenv("DOTTLE_TAGS") or "").strip()
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _agent_version() -> str | None:
    v = (os.getenv("DOTTLE_AGENT_VERSION") or "").strip()
    return v or None


def _redact_text(text: str | None) -> str | None:
    if text is None:
        return None
    if not _redact_pii_enabled():
        return text
    out = text
    patterns = [
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",  # email
        r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?){2}\d{4}\b",  # phone
        r"\b(?:\d[ -]*?){13,19}\b",  # card-like sequences
        r"\b\d{3}-\d{2}-\d{4}\b",  # ssn
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b",  # ipv4
        r"\b(?:sk|dtl_live|api[_-]?key)[A-Za-z0-9_\-]{8,}\b",  # common API key prefixes
    ]
    for p in patterns:
        out = re.sub(p, "[REDACTED]", out, flags=re.IGNORECASE)
    return out


def ingest_post_sync(path: str, body: dict[str, Any], *, timeout: float = 30.0) -> requests.Response | None:
    """
    Synchronous ingest POST for tests and health checks. Returns None if DOTTLE_API_KEY is unset.
    Raises requests.RequestException on network failure.
    """
    headers = _headers()
    if headers is None:
        return None
    url = f"{_dottle_url()}{path}"
    return requests.post(url, headers=headers, json=body, timeout=timeout)


def _post(path: str, body: dict[str, Any]) -> None:
    """Fire-and-forget in production; synchronous when DOTTLE_TEST_SYNC=1 (tests only)."""
    headers = _headers()
    if headers is None:
        return

    url = f"{_dottle_url()}{path}"

    def _send() -> None:
        try:
            requests.post(url, headers=headers, json=body, timeout=15)
        except Exception:
            pass

    if _test_sync_posts():
        _send()
        return

    threading.Thread(target=_send, daemon=True).start()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def maybe_session(agent_name: str, user_id: str | None, user_email: str | None) -> DottleSession | None:
    """Return a live session only when `DOTTLE_API_KEY` is set; otherwise no-op."""
    if not (os.getenv("DOTTLE_API_KEY") or "").strip():
        return None
    return DottleSession(agent_name, user_id=user_id, user_email=user_email)


class DottleSession:
    def __init__(self, agent_name: str, user_id: str | None = None, user_email: str | None = None) -> None:
        self.session_id = str(uuid.uuid4())
        _post(
            "/ingest/session/start",
            {
                "session_id": self.session_id,
                "agent_name": agent_name,
                "started_at": now(),
                "user_id": user_id,
                "user_email": user_email,
                "tags": _tags(),
                "agent_version": _agent_version(),
            },
        )

    def llm(
        self,
        name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        input_text: str | None = None,
        output_text: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        _post(
            "/ingest/spans",
            {
                "session_id": self.session_id,
                "spans": [
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "llm",
                        "name": name,
                        "status": "ok",
                        "started_at": now(),
                        "model": model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "input_text": _redact_text(input_text),
                        "output_text": _redact_text(output_text),
                        "duration_ms": duration_ms,
                    }
                ],
            },
        )

    def tool(
        self,
        tool_name: str,
        status: str = "ok",
        error_message: str | None = None,
        error_type: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        _post(
            "/ingest/spans",
            {
                "session_id": self.session_id,
                "spans": [
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "tool",
                        "name": tool_name,
                        "status": status,
                        "started_at": now(),
                        "error_message": _redact_text(error_message),
                        "error_type": error_type,
                        "duration_ms": duration_ms,
                    }
                ],
            },
        )

    def finish(
        self,
        status: str = "completed",
        error_message: str | None = None,
        error_type: str | None = None,
    ) -> None:
        _post(
            "/ingest/session/end",
            {
                "session_id": self.session_id,
                "status": status,
                "ended_at": now(),
                "error_message": _redact_text(error_message),
                "error_type": error_type,
            },
        )
