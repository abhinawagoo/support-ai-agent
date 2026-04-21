from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Literal

from anthropic import Anthropic
from openai import OpenAI

from .dottle import DottleSession, maybe_session
from .simulation import SimulationContext
from .tools import exa_search, fetch_url_text, search_local_docs
from .tools.crm_sim import crm_query
from .tools.drive_sim import google_drive_get


SYSTEM_PROMPT = """You are a careful customer-support agent.

You may use these integrations (sandbox / read-only):
- **crm_query** — CRM lookup by contact, deal, or ticket (email or id).
- **google_drive_get** — Read shared Drive files by `file_id` (contracts, readme exports).
- **search_local_docs** — Search internal markdown/text docs on disk.
- **fetch_url** — Fetch public URLs when the user provides a link.
- **exa_web_search** — Semantic web discovery when configured (optional).

Rules:
- Prefer verified information from tools over assumptions.
- If tools disagree or data is missing, say what is unknown and suggest next steps.
- When citing the web, ground claims in tool results (URLs/snippets), not memory.
- If a tool fails, acknowledge it and continue with what you still have (do not invent CRM or file contents).
- Be concise, friendly, and action-oriented.
"""


Provider = Literal["openai", "anthropic"]


_TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "crm_query",
        "description": "Read-only CRM lookup (Salesforce-style sandbox). Query contacts, deals, or tickets.",
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "description": "One of: contact, deal, ticket",
                },
                "query": {
                    "type": "string",
                    "description": "Email address, record id, or short search string",
                },
            },
            "required": ["query_type", "query"],
        },
    },
    {
        "name": "google_drive_get",
        "description": "Read a Google Drive file by file_id; returns simulated extracted text (shared drive, read-only).",
        "parameters": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "Drive file id, e.g. demo-contract-q2",
                },
                "mime_hint": {
                    "type": "string",
                    "description": "Optional mime hint (e.g. application/pdf)",
                },
            },
            "required": ["file_id"],
        },
    },
    {
        "name": "search_local_docs",
        "description": "Search local markdown/text documentation on disk (project docs folder).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_files": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch a specific URL and extract readable text (support pages, docs HTML, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "max_chars": {"type": "integer"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "exa_web_search",
        "description": "Semantic web search via Exa (good for discovery when you don't know the exact URL).",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "num_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
]


def _openai_tools() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in _TOOL_SPECS:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                },
            }
        )
    return out


def _anthropic_tools() -> list[dict[str, Any]]:
    return [
        {
            "name": spec["name"],
            "description": spec["description"],
            "input_schema": spec["parameters"],
        }
        for spec in _TOOL_SPECS
    ]


@dataclass(frozen=True)
class ToolTraceEntry:
    name: str
    arguments: dict[str, Any]
    result_preview: str


def _preview(text: str, limit: int = 2500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[preview truncated]"


def _clip_monitor_text(text: str | None, limit: int = 4000) -> str | None:
    if text is None:
        return None
    t = text.strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "\n[truncated]"


def _last_user_text(messages: list[dict[str, Any]]) -> str | None:
    for m in reversed(messages):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
    return None


def _openai_usage_tokens(resp: Any) -> tuple[int, int]:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return 0, 0
    inp = int(getattr(usage, "prompt_tokens", 0) or 0)
    out = int(getattr(usage, "completion_tokens", 0) or 0)
    return inp, out


def _anthropic_usage_tokens(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    inp = int(getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "output_tokens", 0) or 0)
    return inp, out


def _extract_error_message(tool_result: str) -> str | None:
    """Detect structured tool errors returned as JSON payloads."""
    try:
        payload = json.loads(tool_result)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("error"), str):
        err = payload["error"].strip()
        return err or "tool returned error"
    return None


def _run_tool(
    name: str,
    args: dict[str, Any],
    *,
    docs_root: str,
    exa_api_key: str | None,
    simulation: SimulationContext,
) -> str:
    if name == "crm_query":
        simulation.maybe_fail("crm_query")
        return crm_query(str(args.get("query_type", "contact")), str(args.get("query", "")))
    if name == "google_drive_get":
        simulation.maybe_fail("google_drive_get")
        return google_drive_get(
            str(args.get("file_id", "")),
            args.get("mime_hint") if args.get("mime_hint") else None,
        )
    if name == "search_local_docs":
        simulation.maybe_fail("search_local_docs")
        return search_local_docs(
            str(args.get("query", "")),
            docs_root,
            max_files=int(args.get("max_files", 10)),
        )
    if name == "fetch_url":
        simulation.maybe_fail("fetch_url")
        return fetch_url_text(
            str(args.get("url", "")),
            max_chars=int(args.get("max_chars", 12000)),
        )
    if name == "exa_web_search":
        simulation.maybe_fail("exa_web_search")
        if not exa_api_key:
            return json.dumps({"error": "EXA_API_KEY not configured"}, ensure_ascii=False)
        return exa_search(
            str(args.get("query", "")),
            int(args.get("num_results", 5)),
            exa_api_key,
        )
    return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)


def _run_openai_loop(
    *,
    client: OpenAI,
    model: str,
    user_messages: list[dict[str, Any]],
    docs_root: str,
    exa_api_key: str | None,
    status_callback: Callable[[str], None] | None,
    dottle: DottleSession | None,
    simulation: SimulationContext,
) -> tuple[str, list[ToolTraceEntry]]:
    tools = _openai_tools()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *user_messages,
    ]
    trace: list[ToolTraceEntry] = []

    def emit(msg: str) -> None:
        if status_callback:
            status_callback(msg)

    for _ in range(12):
        emit(f"OpenAI: {model}…")
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        inp_tok, out_tok = _openai_usage_tokens(resp)

        msg = resp.choices[0].message
        tool_calls = msg.tool_calls or []

        if dottle:
            out_preview = (msg.content or "").strip()
            if not out_preview and tool_calls:
                out_preview = "tool_calls: " + ", ".join(tc.function.name for tc in tool_calls)
            dottle.llm(
                name="openai.chat.completion",
                model=model,
                input_tokens=inp_tok,
                output_tokens=out_tok,
                input_text=_clip_monitor_text(_last_user_text(messages)),
                output_text=_clip_monitor_text(out_preview),
                duration_ms=duration_ms,
            )

        if not tool_calls:
            return (msg.content or "").strip(), trace

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            name = tc.function.name
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}

            emit(f"Tool: {name}({raw_args[:500]})")

            t_tool = time.perf_counter()
            tool_status = "ok"
            tool_err: str | None = None
            try:
                result = _run_tool(
                    name,
                    args,
                    docs_root=docs_root,
                    exa_api_key=exa_api_key,
                    simulation=simulation,
                )
            except Exception as e:  # noqa: BLE001
                tool_status = "error"
                tool_err = repr(e)
                result = json.dumps({"error": tool_err}, ensure_ascii=False)
            parsed_err = _extract_error_message(result)
            if parsed_err:
                tool_status = "error"
                tool_err = parsed_err
            tool_ms = int((time.perf_counter() - t_tool) * 1000)
            if dottle:
                dottle.tool(
                    name,
                    status=tool_status,
                    error_message=tool_err,
                    error_type="ToolError" if tool_err else None,
                    duration_ms=tool_ms,
                )

            trace.append(ToolTraceEntry(name=name, arguments=args, result_preview=_preview(result)))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return (
        "Stopped early: too many tool/model steps for one reply. Ask a narrower question.",
        trace,
    )


def _run_anthropic_loop(
    *,
    client: Anthropic,
    model: str,
    user_messages: list[dict[str, Any]],
    docs_root: str,
    exa_api_key: str | None,
    status_callback: Callable[[str], None] | None,
    dottle: DottleSession | None,
    simulation: SimulationContext,
) -> tuple[str, list[ToolTraceEntry]]:
    tools = _anthropic_tools()
    messages: list[dict[str, Any]] = [*user_messages]
    trace: list[ToolTraceEntry] = []

    def emit(msg: str) -> None:
        if status_callback:
            status_callback(msg)

    for _ in range(12):
        emit(f"Anthropic: {model}…")
        t0 = time.perf_counter()
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
            temperature=0.2,
        )
        duration_ms = int((time.perf_counter() - t0) * 1000)
        inp_tok, out_tok = _anthropic_usage_tokens(response)

        tool_uses = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
        text_chunks = [b.text for b in response.content if getattr(b, "type", None) == "text"]

        if dottle:
            out_preview = "\n".join(text_chunks).strip()
            if not out_preview and tool_uses:
                out_preview = "tool_use: " + ", ".join(b.name for b in tool_uses)
            dottle.llm(
                name="anthropic.messages",
                model=model,
                input_tokens=inp_tok,
                output_tokens=out_tok,
                input_text=_clip_monitor_text(_last_user_text(messages)),
                output_text=_clip_monitor_text(out_preview),
                duration_ms=duration_ms,
            )

        if not tool_uses:
            return ("\n".join(text_chunks).strip(), trace)

        messages.append({"role": "assistant", "content": response.content})

        tool_blocks: list[dict[str, Any]] = []
        for block in tool_uses:
            name = block.name
            args = block.input if isinstance(block.input, dict) else {}
            emit(f"Tool: {name}({json.dumps(args)[:500]})")

            t_tool = time.perf_counter()
            tool_status = "ok"
            tool_err: str | None = None
            try:
                result = _run_tool(
                    name,
                    args,
                    docs_root=docs_root,
                    exa_api_key=exa_api_key,
                    simulation=simulation,
                )
            except Exception as e:  # noqa: BLE001
                tool_status = "error"
                tool_err = repr(e)
                result = json.dumps({"error": tool_err}, ensure_ascii=False)
            parsed_err = _extract_error_message(result)
            if parsed_err:
                tool_status = "error"
                tool_err = parsed_err
            tool_ms = int((time.perf_counter() - t_tool) * 1000)
            if dottle:
                dottle.tool(
                    name,
                    status=tool_status,
                    error_message=tool_err,
                    error_type="ToolError" if tool_err else None,
                    duration_ms=tool_ms,
                )

            trace.append(ToolTraceEntry(name=name, arguments=args, result_preview=_preview(result)))
            tool_blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                }
            )

        messages.append({"role": "user", "content": tool_blocks})

    return (
        "Stopped early: too many tool/model steps for one reply. Ask a narrower question.",
        trace,
    )


def run_support_agent(
    *,
    provider: Provider,
    user_messages: list[dict[str, Any]],
    model: str,
    openai_api_key: str | None,
    anthropic_api_key: str | None,
    exa_api_key: str | None,
    docs_root: str,
    status_callback: Callable[[str], None] | None = None,
    dottle_agent_name: str = "support-ai-agent",
    dottle_user_id: str | None = None,
    dottle_user_email: str | None = None,
    simulation_mode: str = "off",
) -> tuple[str, list[ToolTraceEntry]]:
    model = model.strip()
    if not model:
        raise ValueError("Model is empty.")

    if provider == "openai":
        if not (openai_api_key or "").strip():
            raise ValueError("Missing OPENAI_API_KEY (env or sidebar).")
    elif provider == "anthropic":
        if not (anthropic_api_key or "").strip():
            raise ValueError("Missing ANTHROPIC_API_KEY (env or sidebar).")
    else:
        raise ValueError(f"Unknown provider: {provider}")

    dottle = maybe_session(dottle_agent_name, dottle_user_id, dottle_user_email)
    _sm = (simulation_mode or "off").strip().lower()
    _allowed = {"off", "crm", "drive", "docs", "exa", "fetch_url", "random", "first_any", "second_any"}
    simulation = SimulationContext(mode=_sm if _sm in _allowed else "off")
    try:
        if provider == "openai":
            client = OpenAI(api_key=openai_api_key.strip())
            out = _run_openai_loop(
                client=client,
                model=model,
                user_messages=user_messages,
                docs_root=docs_root,
                exa_api_key=exa_api_key,
                status_callback=status_callback,
                dottle=dottle,
                simulation=simulation,
            )
        else:
            client = Anthropic(api_key=anthropic_api_key.strip())
            out = _run_anthropic_loop(
                client=client,
                model=model,
                user_messages=user_messages,
                docs_root=docs_root,
                exa_api_key=exa_api_key,
                status_callback=status_callback,
                dottle=dottle,
                simulation=simulation,
            )
    except Exception as e:
        if dottle:
            dottle.finish("failed", error_message=repr(e), error_type=type(e).__name__)
        raise
    else:
        if dottle:
            dottle.finish("completed")
        return out


def to_openai_messages(history: Iterable[tuple[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for role, content in history:
        if role not in {"user", "assistant"}:
            continue
        out.append({"role": role, "content": content})
    return out
