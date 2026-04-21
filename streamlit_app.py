from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import streamlit as st

from src.agent_support import ToolTraceEntry, run_support_agent, to_openai_messages
from src.config import Settings
from src.demo_scenarios import DEMO_SCENARIOS, scenario_by_label
from src.models_catalog import ANTHROPIC_MODEL_PRESETS, CUSTOM_SENTINEL, OPENAI_MODEL_PRESETS
from src.simulation import SIMULATION_LABELS


def _default_docs_root() -> str:
    return str((Path(__file__).resolve().parent / "docs"))


def _is_railway() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))


st.set_page_config(page_title="Support AI Agent", layout="wide")

settings = Settings.load()

if _is_railway():
    st.info(
        "Running on **Railway**: set **`OPENAI_API_KEY`** and/or **`ANTHROPIC_API_KEY`** (plus optional "
        "`**EXA_API_KEY**`, **`DOTTLE_API_KEY`** for monitoring) in service **Variables**. "
        "Leave sidebar key fields empty to use env vars."
    )

st.title("Support AI Agent")
st.caption(
    "CRM + Google Drive (simulated) + internal docs + URL fetch + optional Exa. "
    "Use sidebar scenarios and failure simulation to exercise Dottle like real agents."
)

with st.sidebar:
    st.subheader("Configuration")

    default_provider_index = 0 if settings.default_llm_provider == "openai" else 1
    provider_label = st.radio(
        "LLM provider",
        ["OpenAI", "Anthropic"],
        horizontal=True,
        index=default_provider_index,
    )
    provider = "openai" if provider_label == "OpenAI" else "anthropic"

    st.divider()
    st.markdown("**API keys** (optional overrides; prefer Railway/env variables)")
    openai_key = st.text_input(
        "OpenAI API key",
        value="",
        type="password",
        help="Uses `OPENAI_API_KEY` from the environment when left blank.",
    )
    anthropic_key = st.text_input(
        "Anthropic API key",
        value="",
        type="password",
        help="Uses `ANTHROPIC_API_KEY` from the environment when left blank.",
    )
    exa_key = st.text_input(
        "Exa API key (optional)",
        value="",
        type="password",
        help="Uses `EXA_API_KEY` from the environment when left blank.",
    )

    st.divider()
    st.markdown("**Model**")

    if provider == "openai":
        openai_presets = (*OPENAI_MODEL_PRESETS, CUSTOM_SENTINEL)
        if settings.openai_model in OPENAI_MODEL_PRESETS:
            openai_idx = OPENAI_MODEL_PRESETS.index(settings.openai_model)
        else:
            openai_idx = len(OPENAI_MODEL_PRESETS)
        openai_pick = st.selectbox("OpenAI model", openai_presets, index=openai_idx)
        if openai_pick == CUSTOM_SENTINEL:
            model = st.text_input("Custom OpenAI model ID", value=settings.openai_model).strip()
        else:
            model = openai_pick
    else:
        anthropic_presets = (*ANTHROPIC_MODEL_PRESETS, CUSTOM_SENTINEL)
        if settings.anthropic_model in ANTHROPIC_MODEL_PRESETS:
            anthropic_idx = ANTHROPIC_MODEL_PRESETS.index(settings.anthropic_model)
        else:
            anthropic_idx = len(ANTHROPIC_MODEL_PRESETS)
        anthropic_pick = st.selectbox("Anthropic model", anthropic_presets, index=anthropic_idx)
        if anthropic_pick == CUSTOM_SENTINEL:
            model = st.text_input("Custom Anthropic model ID", value=settings.anthropic_model).strip()
        else:
            model = anthropic_pick

    docs_root = st.text_input("Docs folder", value=_default_docs_root())

    with st.expander("Dottle monitoring (optional)", expanded=False):
        st.caption("Uses `DOTTLE_API_KEY` from the environment when set. Override identity here for local tests.")
        dottle_user_id = st.text_input(
            "Dottle user id override",
            value=settings.dottle_user_id or "",
            help="Saved only for this browser session; prefer `DOTTLE_USER_ID` in env on Railway.",
        )
        dottle_user_email = st.text_input(
            "Dottle user email override",
            value=settings.dottle_user_email or "",
            help="Prefer `DOTTLE_USER_EMAIL` in env for production.",
        )

    st.divider()
    st.markdown("**Demo scenarios** — CRM, Google Drive, internal docs, URL/Exa, multi-tool chains, failures")
    _labels = [s["label"] for s in DEMO_SCENARIOS]
    picked_label = st.selectbox(
        "Choose a preset (or pick “Custom” and type in chat)",
        _labels,
        index=0,
        key="demo_scenario_label",
    )
    _scen = scenario_by_label(picked_label) or DEMO_SCENARIOS[0]
    if _scen.get("hint"):
        st.caption(_scen["hint"])

    q1, q2 = st.columns(2)
    with q1:
        if st.button(
            "Queue preset message",
            type="primary",
            use_container_width=True,
            disabled=not bool(_scen.get("prompt")),
            help="Inserts the prompt below and pairs the matching failure simulation for one turn.",
        ):
            if _scen["prompt"]:
                st.session_state.queued_prompt = _scen["prompt"]
                st.session_state.preset_sim_once = _scen["sim_mode"]
    with q2:
        if st.button("Clear queued preset", use_container_width=True):
            st.session_state.pop("queued_prompt", None)
            st.session_state.pop("preset_sim_once", None)

    with st.expander("Manual failure mode (when you type your own message)", expanded=False):
        st.caption("Used only if you did not queue a preset for this turn.")
        st.selectbox(
            "Simulate tool failure",
            options=list(SIMULATION_LABELS.keys()),
            format_func=lambda k: SIMULATION_LABELS[k],
            index=0,
            key="manual_sim_mode",
        )

    st.divider()
    st.markdown(
        "**Run locally**\n\n"
        "`python -m venv .venv && source .venv/bin/activate`\n\n"
        "`pip install -r requirements.txt`\n\n"
        "`cp .env.example .env` (optional)\n\n"
        "`streamlit run streamlit_app.py`\n\n"
        "**Deploy:** see `README.md` (Railway + GitHub)."
    )

if "messages" not in st.session_state:
    st.session_state.messages = []  # list[tuple[role, content]]

if "tool_log" not in st.session_state:
    st.session_state.tool_log = []  # list[ToolTraceEntry]


def _render_history() -> None:
    for role, content in st.session_state.messages:
        with st.chat_message(role):
            st.markdown(content)


_render_history()

prompt = st.chat_input("Ask a support question…")
queued = st.session_state.pop("queued_prompt", None)
if queued is not None:
    prompt = queued

if prompt:
    openai_api_key = (openai_key.strip() or settings.openai_api_key).strip() or None
    anthropic_api_key = (anthropic_key.strip() or (settings.anthropic_api_key or "")).strip() or None
    exa_api_key = (exa_key.strip() or (settings.exa_api_key or "")).strip() or None

    preset_sim = st.session_state.pop("preset_sim_once", None)
    effective_sim = preset_sim if preset_sim is not None else st.session_state.get("manual_sim_mode", "off")

    st.session_state.messages.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    status = st.status("Working…", state="running")
    trace: list[ToolTraceEntry] = []

    try:
        user_msgs = to_openai_messages(st.session_state.messages)

        def cb(msg: str) -> None:
            status.update(label=msg)

        answer, trace = run_support_agent(
            provider=provider,
            user_messages=user_msgs,
            model=model,
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
            exa_api_key=exa_api_key,
            docs_root=docs_root.strip(),
            status_callback=cb,
            dottle_agent_name=settings.dottle_agent_name,
            dottle_user_id=(dottle_user_id.strip() or settings.dottle_user_id),
            dottle_user_email=(dottle_user_email.strip() or settings.dottle_user_email),
            simulation_mode=effective_sim,
        )
    except Exception as e:  # noqa: BLE001
        status.update(label="Error", state="error")
        answer = f"**Error:** `{e}`"
        trace = []
    else:
        status.update(label="Done", state="complete")

    st.session_state.messages.append(("assistant", answer))
    st.session_state.tool_log.extend(trace)

    with st.chat_message("assistant"):
        st.markdown(answer)
        st.caption(f"Failure simulation this turn: `{effective_sim}`")

    if trace:
        turn_id = uuid.uuid4().hex[:10]
        with st.expander("Tool calls (latest turn)", expanded=False):
            for i, t in enumerate(trace, start=1):
                st.markdown(f"**{i}. `{t.name}`**")
                st.code(json.dumps(t.arguments, ensure_ascii=False, indent=2), language="json")
                st.text_area(
                    "Result preview",
                    value=t.result_preview,
                    height=220,
                    key=f"tool_preview_{turn_id}_{i}",
                )
