"""
Scenarios for validating Dottle ingest — different traces you should see in the dashboard.

Run with DOTTLE_API_KEY set. HTTP scenarios assert on status codes; the class-based smoke
uses the same code path as production (with DOTTLE_TEST_SYNC=1).
"""

from __future__ import annotations

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


def scenario_http_multi_llm_rounds() -> None:
    """Multi-step agent: several LLM calls in one session (tool-calling loop simulation)."""
    sid = str(uuid.uuid4())
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/start",
            {
                "session_id": sid,
                "agent_name": "dottle-test-platform",
                "started_at": now(),
                "user_id": "multi-step",
                "user_email": None,
            },
        ),
        "session/start",
    )
    for i, (inp, out, dur) in enumerate(
        [
            ("User question about billing", "I'll search our docs…", 400),
            ("(tools ran) summarize hits", "Here is what I found…", 650),
            ("User follow-up", "Does that apply to annual plans?", 520),
        ],
        start=1,
    ):
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
                            "input_tokens": 80 + i * 40,
                            "output_tokens": 30 + i * 10,
                            "input_text": inp,
                            "output_text": out,
                            "duration_ms": dur,
                        }
                    ],
                },
            ),
            f"spans/llm_round_{i}",
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


def scenario_http_batch_spans_single_post() -> None:
    """One ingest payload with multiple spans (batch) — exercises multi-span ingestion."""
    sid = str(uuid.uuid4())
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/start",
            {
                "session_id": sid,
                "agent_name": "dottle-test-platform-batch",
                "started_at": now(),
                "user_id": None,
                "user_email": "batch@example.com",
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
                        "model": "gpt-4o",
                        "input_tokens": 500,
                        "output_tokens": 120,
                        "input_text": "Compare plans",
                        "output_text": "Calling tools…",
                        "duration_ms": 700,
                    },
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "tool",
                        "name": "search_local_docs",
                        "status": "ok",
                        "started_at": now(),
                        "error_message": None,
                        "duration_ms": 18,
                    },
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "tool",
                        "name": "exa_web_search",
                        "status": "ok",
                        "started_at": now(),
                        "error_message": None,
                        "duration_ms": 210,
                    },
                    {
                        "span_id": str(uuid.uuid4()),
                        "span_type": "llm",
                        "name": "openai.chat.completion",
                        "status": "ok",
                        "started_at": now(),
                        "model": "gpt-4o",
                        "input_tokens": 900,
                        "output_tokens": 200,
                        "input_text": "(tool results attached)",
                        "output_text": "Based on the docs and web…",
                        "duration_ms": 1100,
                    },
                ],
            },
        ),
        "spans/batch_four",
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


def scenario_http_long_text_payload() -> None:
    """Long input_text / output_text for UI truncation and storage behavior."""
    sid = str(uuid.uuid4())
    chunk = (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "This paragraph simulates a large retrieved doc chunk. "
    )
    long_text = (chunk * 120)[:8000]
    assert_ingest_ok(
        ingest_post_sync(
            "/ingest/session/start",
            {
                "session_id": sid,
                "agent_name": "dottle-test-platform",
                "started_at": now(),
                "user_id": "long-payload",
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
                        "input_tokens": 6000,
                        "output_tokens": 400,
                        "input_text": long_text[:4000],
                        "output_text": long_text[:4000],
                        "duration_ms": 3200,
                    }
                ],
            },
        ),
        "spans/llm_long_text",
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
    ("http_multi_llm_rounds", scenario_http_multi_llm_rounds),
    ("http_batch_spans_single_post", scenario_http_batch_spans_single_post),
    ("http_long_text_payload", scenario_http_long_text_payload),
    ("client_class_smoke", scenario_client_class_smoke),
]
