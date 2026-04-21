"""Named UI demo scenarios — multi-tool prompts + which simulation mode to pair for Dottle."""

from __future__ import annotations

from typing import TypedDict


class DemoScenario(TypedDict):
    id: str
    label: str
    sim_mode: str
    prompt: str
    hint: str


# sim_mode must match SimulationContext / run_support_agent allowed set
DEMO_SCENARIOS: list[DemoScenario] = [
    {
        "id": "free",
        "label": "— Custom: type in chat only (no preset) —",
        "sim_mode": "off",
        "prompt": "",
        "hint": "Use the failure dropdown below when typing freely.",
    },
    {
        "id": "crm_happy",
        "label": "CRM · lookup Acme contact (happy path)",
        "sim_mode": "off",
        "prompt": (
            "Use **crm_query** with query_type **contact** and query **contact@acme.com**. "
            "Summarize tier, health score, and open tickets from the CRM result only."
        ),
        "hint": "Expect crm_query → ok.",
    },
    {
        "id": "crm_deal_example",
        "label": "CRM · deal DEAL-2025-01 + fetch https://example.com",
        "sim_mode": "off",
        "prompt": (
            "(1) **crm_query** with query_type **deal** and query **DEAL-2025-01**. "
            "(2) **fetch_url** on **https://example.com** for a short public snippet. "
            "Keep CRM facts separate from web copy."
        ),
        "hint": "CRM + fetch_url — two integration types.",
    },
    {
        "id": "crm_fail",
        "label": "CRM · same lookup · simulated Salesforce 429 ✗",
        "sim_mode": "crm",
        "prompt": (
            "Look up CRM **contact** for **contact@acme.com**. "
            "When the tool fails, explain briefly and suggest retry without inventing CRM data."
        ),
        "hint": "Forces crm_query error span in Dottle.",
    },
    {
        "id": "drive_happy",
        "label": "Google Drive · read Q2 contract (happy path)",
        "sim_mode": "off",
        "prompt": (
            "Use **google_drive_get** with file_id **demo-contract-q2**. "
            "Quote renewal / SLA / billing contact from the extracted text only."
        ),
        "hint": "Expect google_drive_get → ok.",
    },
    {
        "id": "drive_fail",
        "label": "Google Drive · same file · simulated 403 permission ✗",
        "sim_mode": "drive",
        "prompt": (
            "Read Drive file **demo-contract-q2**. If access fails, say so and do not guess contract terms."
        ),
        "hint": "Forces google_drive_get error span.",
    },
    {
        "id": "docs_happy",
        "label": "Internal docs · billing / refund search (happy path)",
        "sim_mode": "off",
        "prompt": (
            "Use **search_local_docs** for **billing** and **refund**. "
            "Summarize policy bullets from snippets only."
        ),
        "hint": "Uses ./docs markdown.",
    },
    {
        "id": "docs_fail",
        "label": "Internal docs · simulated index unreachable ✗",
        "sim_mode": "docs",
        "prompt": (
            "Search internal docs for **Enterprise plan**. If the tool errors, acknowledge and stop."
        ),
        "hint": "Forces search_local_docs error span.",
    },
    {
        "id": "url_fail",
        "label": "Public URL fetch · simulated timeout ✗",
        "sim_mode": "fetch_url",
        "prompt": (
            "Use **fetch_url** on https://example.com to get marketing copy. "
            "If it fails, note the outage."
        ),
        "hint": "Forces fetch_url error (simulated); model may still answer minimally.",
    },
    {
        "id": "exa_fail",
        "label": "Exa web search · simulated 503 ✗",
        "sim_mode": "exa",
        "prompt": (
            "Use **exa_web_search** for **Acme Corp enterprise SLA 2025**. "
            "If Exa fails, say so (requires EXA_API_KEY in env or sidebar)."
        ),
        "hint": "If Exa not configured, session shows configuration error instead.",
    },
    {
        "id": "chain_happy",
        "label": "🔀 Chain: CRM + Drive + docs (all happy)",
        "sim_mode": "off",
        "prompt": (
            "Enterprise escalation: "
            "(1) **crm_query** contact **contact@acme.com**. "
            "(2) **google_drive_get** **demo-contract-q2**. "
            "(3) **search_local_docs** for **refund** and **billing**. "
            "Produce a short reconciliation; cite tools only."
        ),
        "hint": "Multiple ok spans — ideal Dottle timeline.",
    },
    {
        "id": "chain_crm_fail",
        "label": "🔀 Same chain · CRM fails (realistic partial outage)",
        "sim_mode": "crm",
        "prompt": (
            "Same as full chain: CRM contact@acme.com, Drive demo-contract-q2, docs refund/billing. "
            "Continue with Drive + docs if CRM fails."
        ),
        "hint": "CRM error then recovery pattern.",
    },
    {
        "id": "chain_drive_fail",
        "label": "🔀 Same chain · Drive fails",
        "sim_mode": "drive",
        "prompt": (
            "CRM contact@acme.com, Drive demo-contract-q2, docs billing — "
            "handle Drive permission failure gracefully."
        ),
        "hint": "Drive error span mid-chain.",
    },
    {
        "id": "stress",
        "label": "⚡ Stress: many tools (CRM + Drive + docs + optional Exa)",
        "sim_mode": "off",
        "prompt": (
            "Run useful tools: CRM **contact** **person@startup.io**, "
            "Drive **readme-internal**, **search_local_docs** **Enterprise**, "
            "and **exa_web_search** **vendor incident page** only if Exa is configured."
        ),
        "hint": "Volume of spans for dashboards.",
    },
    {
        "id": "random_flaky",
        "label": "🎲 Random flaky (~38% per tool)",
        "sim_mode": "random",
        "prompt": (
            "Try **crm_query** contact **contact@acme.com** and **google_drive_get** **demo-contract-q2**. "
            "Retry mentally once if a tool fails (like a real agent)."
        ),
        "hint": "Mixed ok/error spans across runs.",
    },
    {
        "id": "first_tool_fail",
        "label": "⚠️ First tool call only fails (cold-start)",
        "sim_mode": "first_any",
        "prompt": (
            "Use tools in order: **crm_query** contact@acme.com, then **search_local_docs** **billing**. "
            "If the first tool fails, continue with docs."
        ),
        "hint": "Simulates first integration timeout; second often succeeds.",
    },
    {
        "id": "second_tool_fail",
        "label": "⚠️ Second tool call fails (partial success)",
        "sim_mode": "second_any",
        "prompt": (
            "Run **crm_query** contact@acme.com then **google_drive_get** demo-contract-q2. "
            "Interpret mixed success."
        ),
        "hint": "First ok, second error — common pattern.",
    },
]


def scenario_by_label(label: str) -> DemoScenario | None:
    for s in DEMO_SCENARIOS:
        if s["label"] == label:
            return s
    return None
