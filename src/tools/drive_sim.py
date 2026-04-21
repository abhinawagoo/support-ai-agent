"""Sandbox Google Drive file read — deterministic fake excerpts (no OAuth)."""

from __future__ import annotations

import json


def google_drive_get(file_id: str, mime_hint: str | None = None) -> str:
    fid = (file_id or "").strip().lower()
    _ = mime_hint

    # Pretend PDF/text extraction succeeded
    if any(x in fid for x in ("contract", "q2", "renewal", "demo-contract")):
        body = (
            "Q2 Enterprise Agreement — Effective April 1. "
            "Annual renewal March 15. SLA 99.9%. "
            "Billing contact: billing@acme.com. "
            "Stored signatures: DocuSign envelope ENV-9912."
        )
    elif "readme" in fid:
        body = "Internal readme: link CRM contact before quoting discounts."
    else:
        body = f"(Simulated short file body for `{fid}` — no sensitive data.)"

    payload = {
        "source": "google_drive_sim",
        "file_id": file_id,
        "mimeType": mime_hint or "application/pdf",
        "extracted_text": body,
    }
    return json.dumps(payload, ensure_ascii=False)
