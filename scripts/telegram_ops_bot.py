from __future__ import annotations

import os
import re
import time

from src.dottle import maybe_session
from src.tools.exa_search import exa_search
from src.tools.ops_integrations import (
    append_google_sheet,
    read_google_doc_text,
    slack_send_message,
    supabase_insert_json,
    telegram_send_message,
    update_excel_local,
    utc_now_iso,
)
from src.tools.web_fetch import fetch_url_text


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _extract_url(text: str) -> str | None:
    m = re.search(r"https?://\S+", text)
    return m.group(0) if m else None


def _parse_mode_and_query(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    low = raw.lower()
    if low.startswith("/deep"):
        return "deep", raw[5:].strip()
    if low.startswith("/quick"):
        return "quick", raw[6:].strip()
    return "normal", raw


def _help_text() -> str:
    return (
        "Commands:\n"
        "/quick <query> - fast Exa browse (fewer results)\n"
        "/deep <query> - broad Exa browse (more results)\n"
        "/status - show integration readiness\n"
        "/help - show this message\n\n"
        "You can also send plain text or include a URL."
    )


def _status_text() -> str:
    checks = {
        "TELEGRAM_BOT_TOKEN": bool(_env("TELEGRAM_BOT_TOKEN")),
        "EXA_API_KEY": bool(_env("EXA_API_KEY")),
        "SUPABASE_URL": bool(_env("SUPABASE_URL")),
        "SUPABASE_SERVICE_ROLE_KEY": bool(_env("SUPABASE_SERVICE_ROLE_KEY")),
        "GOOGLE_SERVICE_ACCOUNT_JSON": bool(_env("GOOGLE_SERVICE_ACCOUNT_JSON")),
        "GOOGLE_DOC_ID": bool(_env("GOOGLE_DOC_ID")),
        "GOOGLE_SHEET_ID": bool(_env("GOOGLE_SHEET_ID")),
        "SLACK_WEBHOOK_URL": bool(_env("SLACK_WEBHOOK_URL")),
    }
    lines = ["Integration status:"]
    for name, ok in checks.items():
        lines.append(f"- {name}: {'OK' if ok else 'MISSING'}")
    return "\n".join(lines)


def _build_report(instruction: str, web_text: str, doc_text: str) -> str:
    web_summary = web_text[:1200].replace("\n", " ").strip()
    doc_summary = doc_text[:1200].replace("\n", " ").strip()
    return (
        "Ops report generated.\n"
        f"Instruction: {instruction[:600]}\n"
        f"Web data: {web_summary or 'N/A'}\n"
        f"Google Doc context: {doc_summary or 'N/A'}\n"
    )


def _fetch_web_context(instruction: str, mode: str, dottle=None) -> str:
    exa_key = _env("EXA_API_KEY")
    num_results = 5
    if mode == "quick":
        num_results = 3
    elif mode == "deep":
        num_results = 10
    if exa_key:
        t0 = time.perf_counter()
        try:
            # Use Exa discovery first for general user questions.
            out = exa_search(instruction, num_results, exa_key)
            if dottle:
                dottle.tool("exa_web_search", status="ok", duration_ms=int((time.perf_counter() - t0) * 1000))
            return out
        except Exception:
            if dottle:
                dottle.tool(
                    "exa_web_search",
                    status="error",
                    error_message="Exa search failed",
                    error_type="WebSearchError",
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )
            pass
    source_url = _extract_url(instruction)
    if source_url:
        t0 = time.perf_counter()
        try:
            out = fetch_url_text(source_url)
            if dottle:
                dottle.tool("fetch_url", status="ok", duration_ms=int((time.perf_counter() - t0) * 1000))
            return out
        except Exception:
            if dottle:
                dottle.tool(
                    "fetch_url",
                    status="error",
                    error_message="URL fetch failed",
                    error_type="WebFetchError",
                    duration_ms=int((time.perf_counter() - t0) * 1000),
                )
            raise
    return ""


def _run_workflow(chat_id: str, instruction: str) -> str:
    dottle = maybe_session(
        _env("DOTTLE_AGENT_NAME", "telegram-ops-bot"),
        user_id=chat_id,
        user_email=_env("DOTTLE_USER_EMAIL") or None,
    )
    try:
        mode, query = _parse_mode_and_query(instruction)
        effective_query = query or instruction
        source_url = _extract_url(effective_query)
        web_text = _fetch_web_context(effective_query, mode, dottle=dottle)

        sa_json = _env("GOOGLE_SERVICE_ACCOUNT_JSON")
        doc_id = _env("GOOGLE_DOC_ID")
        sheet_id = _env("GOOGLE_SHEET_ID")
        sheet_name = _env("GOOGLE_SHEET_NAME", "Reports")
        excel_path = _env("EXCEL_FILE_PATH", "reports.xlsx")

        doc_text = ""
        if sa_json and doc_id:
            t0 = time.perf_counter()
            try:
                doc_text = read_google_doc_text(service_account_json=sa_json, doc_id=doc_id)
                if dottle:
                    dottle.tool("google_docs_read", status="ok", duration_ms=int((time.perf_counter() - t0) * 1000))
            except Exception as e:
                if dottle:
                    dottle.tool(
                        "google_docs_read",
                        status="error",
                        error_message=str(e),
                        error_type=type(e).__name__,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                raise

        report = _build_report(instruction, web_text, doc_text)
        row = {
            "created_at": utc_now_iso(),
            "chat_id": chat_id,
            "instruction": instruction[:2000],
            "source_url": source_url or "",
            "report": report[:6000],
        }

        supabase_url = _env("SUPABASE_URL")
        supabase_key = _env("SUPABASE_SERVICE_ROLE_KEY")
        supabase_table = _env("SUPABASE_TABLE", "agent_reports")
        if supabase_url and supabase_key:
            t0 = time.perf_counter()
            try:
                supabase_insert_json(
                    supabase_url=supabase_url,
                    supabase_key=supabase_key,
                    table=supabase_table,
                    payload=row,
                )
                if dottle:
                    dottle.tool("supabase_insert", status="ok", duration_ms=int((time.perf_counter() - t0) * 1000))
            except Exception as e:
                if dottle:
                    dottle.tool(
                        "supabase_insert",
                        status="error",
                        error_message=str(e),
                        error_type=type(e).__name__,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                raise

        t0 = time.perf_counter()
        update_excel_local(file_path=excel_path, row=row)
        if dottle:
            dottle.tool("excel_update", status="ok", duration_ms=int((time.perf_counter() - t0) * 1000))
        if sa_json and sheet_id:
            t0 = time.perf_counter()
            try:
                append_google_sheet(
                    service_account_json=sa_json,
                    spreadsheet_id=sheet_id,
                    sheet_name=sheet_name,
                    row=row,
                )
                if dottle:
                    dottle.tool("google_sheet_append", status="ok", duration_ms=int((time.perf_counter() - t0) * 1000))
            except Exception as e:
                if dottle:
                    dottle.tool(
                        "google_sheet_append",
                        status="error",
                        error_message=str(e),
                        error_type=type(e).__name__,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                raise

        slack_webhook = _env("SLACK_WEBHOOK_URL")
        if slack_webhook:
            t0 = time.perf_counter()
            try:
                slack_send_message(webhook_url=slack_webhook, text=report[:2800])
                if dottle:
                    dottle.tool("slack_notify", status="ok", duration_ms=int((time.perf_counter() - t0) * 1000))
            except Exception as e:
                if dottle:
                    dottle.tool(
                        "slack_notify",
                        status="error",
                        error_message=str(e),
                        error_type=type(e).__name__,
                        duration_ms=int((time.perf_counter() - t0) * 1000),
                    )
                raise

        if dottle:
            dottle.finish("completed")
        return report
    except Exception as e:
        if dottle:
            dottle.finish("failed", error_message=str(e), error_type=type(e).__name__)
        raise


def run_bot() -> None:
    token = _env("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    default_chat = _env("TELEGRAM_CHAT_ID")
    offset = 0
    while True:
        try:
            resp = __import__("requests").get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"timeout": 25, "offset": offset},
                timeout=35,
            )
            resp.raise_for_status()
            updates = resp.json().get("result", [])
            for upd in updates:
                offset = int(upd["update_id"]) + 1
                msg = upd.get("message") or {}
                chat_id = str((msg.get("chat") or {}).get("id") or default_chat or "")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue
                if text.lower() == "/help":
                    telegram_send_message(bot_token=token, chat_id=chat_id, text=_help_text())
                    continue
                if text.lower() == "/status":
                    telegram_send_message(bot_token=token, chat_id=chat_id, text=_status_text())
                    continue
                try:
                    report = _run_workflow(chat_id, text)
                    telegram_send_message(bot_token=token, chat_id=chat_id, text=report[:3500])
                except Exception as e:  # noqa: BLE001
                    telegram_send_message(
                        bot_token=token,
                        chat_id=chat_id,
                        text=f"Workflow failed: {type(e).__name__}: {e}",
                    )
        except Exception:
            time.sleep(2)


if __name__ == "__main__":
    run_bot()
