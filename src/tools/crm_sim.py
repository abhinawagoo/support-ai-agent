"""Sandbox CRM lookup — deterministic fake records (no external API)."""

from __future__ import annotations

import json


def crm_query(query_type: str, query: str) -> str:
    qt = (query_type or "contact").strip().lower()
    q = (query or "").strip().lower()

    if qt == "deal":
        record = {
            "id": "DEAL-2025-01",
            "type": "deal",
            "name": "Acme — Enterprise renewal",
            "stage": "Negotiation",
            "amount_usd": 128000,
            "close_date": "2025-06-30",
            "owner": "sales-east@example.com",
            "account": "Acme Corp",
            "notes": "Legal reviewing Drive contract demo-contract-q2",
        }
        out = {"source": "salesforce_sandbox_sim", "query": q, "records": [record]}
        return json.dumps(out, ensure_ascii=False)

    email = "unknown@example.com"
    if "acme" in q:
        email = "contact@acme.com"
    elif "@" in query:
        email = query.strip()

    record = {
        "id": "003XX000014SIM",
        "type": qt,
        "email": email,
        "account": "Acme Corp" if "acme" in q else "Prospect",
        "tier": "Enterprise" if "acme" in q else "Starter",
        "health_score": 82 if "acme" in q else 55,
        "open_tickets": 1,
        "last_note": "Asked about Q2 renewal and Drive contract PDF",
    }

    out = {
        "source": "salesforce_sandbox_sim",
        "query": q,
        "records": [record],
    }
    return json.dumps(out, ensure_ascii=False)
