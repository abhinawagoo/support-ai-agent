"""Configurable tool failures for demos — surfaces as error spans in Dottle."""

from __future__ import annotations

import random
from dataclasses import dataclass


SIMULATION_LABELS: dict[str, str] = {
    "off": "None — no forced failures",
    "crm": "Always fail · CRM (`crm_query`)",
    "drive": "Always fail · Google Drive (`google_drive_get`)",
    "docs": "Always fail · local docs (`search_local_docs`)",
    "exa": "Always fail · Exa (`exa_web_search`)",
    "fetch_url": "Always fail · URL fetch (`fetch_url`)",
    "random": "Random · ~38% failure per tool call",
    "first_any": "Fail · 1st tool call only (any integration)",
    "second_any": "Fail · 2nd tool call only (any integration)",
}


@dataclass
class SimulationContext:
    """Raising RuntimeError yields a tool error in the agent loop (Dottle sees status=error)."""

    mode: str = "off"
    _invocation: int = 0

    def maybe_fail(self, tool_name: str) -> None:
        m = self.mode
        if m == "off":
            return
        if m == "first_any":
            self._invocation += 1
            if self._invocation == 1:
                raise RuntimeError(
                    "SIMULATED: first tool invocation failed — cold start / TLS handshake timeout"
                )
            return
        if m == "second_any":
            self._invocation += 1
            if self._invocation == 2:
                raise RuntimeError(
                    "SIMULATED: second tool invocation failed — downstream dependency degraded"
                )
            return
        if m == "crm" and tool_name == "crm_query":
            raise RuntimeError(
                "SIMULATED: CRM 429 Too Many Requests — Salesforce API throttle (retry-after: 60s)"
            )
        if m == "drive" and tool_name == "google_drive_get":
            raise RuntimeError(
                "SIMULATED: Google Drive 403 permission_denied — OAuth scope drive.file revoked"
            )
        if m == "docs" and tool_name == "search_local_docs":
            raise RuntimeError(
                "SIMULATED: Docs index unreachable — connection reset reading /var/docs/index.json"
            )
        if m == "exa" and tool_name == "exa_web_search":
            raise RuntimeError("SIMULATED: Exa API 503 — upstream overload")
        if m == "fetch_url" and tool_name == "fetch_url":
            raise RuntimeError(
                "SIMULATED: HTTPS timeout after 30s fetching status.vendor.com/incidents"
            )
        if m == "random":
            if random.random() < 0.38:
                raise RuntimeError(
                    f"SIMULATED: transient infra failure during `{tool_name}` (packet loss / DNS flap)"
                )
