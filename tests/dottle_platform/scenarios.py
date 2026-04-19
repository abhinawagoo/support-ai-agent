"""
Scenarios for validating Dottle ingest — different traces you should see in the dashboard.

Run with DOTTLE_API_KEY set. HTTP scenarios assert on status codes; the class-based smoke
uses the same code path as production (with DOTTLE_TEST_SYNC=1).
"""

from __future__ import annotations

import os
import uuid

from src.dottle import DottleSession, ingest_post_sync, now


def assert_ingest_ok(resp, label: str) -> None:
    assert resp is not None, f"{label}: set DOTTLE_API_KEY"
    assert resp.status_code < 400, f"{label}: HTTP {resp.status_code} {resp.text[:1200]}"


def scenario_http_session_lifecycle() -> None:
    """Minimal session start → end (completed)."""
    sid = str(uuid.uuid4())
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/start",
            {
                "session_id": sid,
                "agent_name": "dottle-test-platform",
                "started_at": now(),
                "user_id": "qa-user",
                "user_email": "qa@example.com",
            },
        ),
        "session/start",
    )
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/end",
            {
                "session_id": sid,
                "status": "completed",
                "ended_at": now(),
                "error_message": None,
            },
        ),
        "session/end",
    )


def scenario_http_llm_tool_error_chain() -> None:
    """One LLM span, successful tool, failed tool, then completed."""
    sid = str(uuid.uuid4())
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/start",
            {
                "session_id": sid,
                "agent_name": "dottle-test-platform",
                "started_at": now(),
                "user_id": None,
                "user_email": None,
            },
        ),
        "session/start",
    )
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/spans",
            {
                "session_id": sid,
                "spans": [
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "llm",
                        "name": "openai.chat.completion",
                        "status": "ok",
                        "started_at": now(),
                        "model": "gpt-4o-mini",
                        "input_tokens": 120,
                        "output_tokens": 45,
                        "input_text": "What is our refund policy?",
                        "output_text": "I'll check the docs…",
                        "duration_ms": 890,
                    }
                ],
            },
        ),
        "spans/llm",
    )
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/spans",
            {
                "session_id": sid,
                "spans": [
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "tool",
                        "name": "search_local_docs",
                        "status": "ok",
                        "started_at": now(),
                        "error_message": None,
                        "duration_ms": 22,
                    }
                ],
            },
        ),
        "spans/tool_ok",
    )
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/spans",
            {
                "session_id": sid,
                "spans": [
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "tool",
                        "name": "fetch_url",
                        "status": "error",
                        "started_at": now(),
                        "error_message": "injected: upstream timeout",
                        "duration_ms": 5000,
                    }
                ],
            },
        ),
        "spans/tool_error",
    )
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/end",
            {
                "session_id": sid,
                "status": "completed",
                "ended_at": now(),
                "error_message": None,
            },
        ),
        "session/end",
    )


def scenario_http_session_end_error() -> None:
    """Session ends with error status (agent-level failure)."""
    sid = str(uuid.uuid4())
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/start",
            {
                "session_id": sid,
                "agent_name": "dottle-test-platform",
                "started_at": now(),
                "user_id": "error-case",
                "user_email": None,
            },
        ),
        "session/start",
    )
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/end",
            {
                "session_id": sid,
                "status": "error",
                "ended_at": now(),
                "error_message": "injected: missing OPENAI_API_KEY in worker",
            },
        ),
        "session/end_error",
    )


def scenario_client_class_smoke() -> None:
    """Uses production DottleSession + _post (sync); confirms client wiring.
    Expect DOTTLE_TEST_SYNC=1 (set by the runner or pytest)."""
    s = DottleSession(
        "dottle-test-platform-client",
        user_id="class-smoke",
        user_email=None,
    )
    sid = s.session_id
    s.llm(
        "anthropic.messages",
        model="claude-sonnet-4-6",
        input_tokens=200,
        output_tokens=90,
        input_text="hello",
        output_text="hello back",
        duration_ms=1200,
    )
    s.tool("exa_web_search", status="ok", duration_ms=140)
    s.tool("fetch_url", status="error", error_message="injected DNS failure", duration_ms=300)
    s.finish("completed")
    assert sid, "session_id should be set"


SCENARIOS: list[tuple[str, object]] = [
    ("http_session_lifecycle", scenario_http_session_lifecycle),
    ("http_llm_tool_error_chain", scenario_http_llm_tool_error_chain),
    ("http_session_end_error", scenario_http_session_end_error),
    ("client_class_smoke", scenario_client_class_smoke),
]
