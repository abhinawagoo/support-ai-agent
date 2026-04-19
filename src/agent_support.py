from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from openai import OpenAI

from .tools import exa_search, fetch_url_text, search_local_docs


SYSTEM_PROMPT = """You are a careful customer-support agent.

Rules:
- Prefer verified information from the provided tools over assumptions.
- If tools disagree or data is missing, say what is unknown and suggest next steps.
- When citing the web, ground claims in tool results (URLs/snippets), not memory.
- Be concise, friendly, and action-oriented.
"""


@dataclass(frozen=True)
class ToolTraceEntry:
    name: str
    arguments: dict[str, Any]
    result_preview: str


def _tools_schema() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_local_docs",
                "description": "Search local markdown/text documentation on disk (project docs folder).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_files": {"type": "integer", "default": 10},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch a specific URL and extract readable text (support pages, docs HTML, etc.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_chars": {"type": "integer", "default": 12000},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "exa_web_search",
                "description": "Semantic web search via Exa (good for discovery when you don't know the exact URL).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "num_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
    ]


def _preview(text: str, limit: int = 2500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[preview truncated]"


def run_support_agent(
    *,
    user_messages: list[dict[str, Any]],
    openai_api_key: str,
    openai_model: str,
    exa_api_key: str | None,
    docs_root: str,
    status_callback: Callable[[str], None] | None = None,
) -> tuple[str, list[ToolTraceEntry]]:
    if not openai_api_key:
        raise ValueError("Missing OPENAI_API_KEY (env or sidebar).")

    client = OpenAI(api_key=openai_api_key)
    tools = _tools_schema()

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *user_messages,
    ]

    trace: list[ToolTraceEntry] = []

    def emit(msg: str) -> None:
        if status_callback:
            status_callback(msg)

    for _ in range(12):
        emit(f"Calling model: {openai_model}…")
        resp = client.chat.completions.create(
            model=openai_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )

        choice = resp.choices[0]
        msg = choice.message
        tool_calls = msg.tool_calls or []

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

            try:
                if name == "search_local_docs":
                    result = search_local_docs(
                        str(args.get("query", "")),
                        docs_root,
                        max_files=int(args.get("max_files", 10)),
                    )
                elif name == "fetch_url":
                    result = fetch_url_text(
                        str(args.get("url", "")),
                        max_chars=int(args.get("max_chars", 12000)),
                    )
                elif name == "exa_web_search":
                    if not exa_api_key:
                        result = json.dumps(
                            {"error": "EXA_API_KEY not configured"},
                            ensure_ascii=False,
                        )
                    else:
                        result = exa_search(
                            str(args.get("query", "")),
                            int(args.get("num_results", 5)),
                            exa_api_key,
                        )
                else:
                    result = json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
            except Exception as e:  # noqa: BLE001 - tool boundary
                result = json.dumps({"error": repr(e)}, ensure_ascii=False)

            trace.append(
                ToolTraceEntry(
                    name=name,
                    arguments=args,
                    result_preview=_preview(result),
                )
            )

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return (
        "Stopped early: too many tool/model steps for one reply. Ask a narrower question.",
        trace,
    )


def to_openai_messages(
    history: Iterable[tuple[str, str]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for role, content in history:
        if role not in {"user", "assistant"}:
            continue
        out.append({"role": role, "content": content})
    return out
