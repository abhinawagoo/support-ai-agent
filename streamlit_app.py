from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import streamlit as st

from src.agent_support import ToolTraceEntry, run_support_agent, to_openai_messages
from src.config import Settings


def _default_docs_root() -> str:
    return str((Path(__file__).resolve().parent / "docs"))


def _is_railway() -> bool:
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))


st.set_page_config(page_title="Support AI Agent", layout="wide")

settings = Settings.load()

if _is_railway():
    st.info(
        "Running on **Railway**: set `OPENAI_API_KEY` (and optional `EXA_API_KEY`) in the service "
        "**Variables**. Leave the sidebar key fields empty to use those values."
    )

st.title("Support AI Agent")
st.caption("OpenAI tool-calling + local docs + URL fetch + Exa search (optional).")

with st.sidebar:
    st.subheader("Configuration")
    openai_key = st.text_input(
        "OpenAI API key (optional override)",
        value="",
        type="password",
        help="Railway/local: leave blank to use OPENAI_API_KEY from environment.",
    )
    exa_key = st.text_input(
        "Exa API key (optional override)",
        value="",
        type="password",
        help="Railway/local: leave blank to use EXA_API_KEY from environment.",
    )
    model = st.text_input("OpenAI model", value=settings.openai_model)
    docs_root = st.text_input("Docs folder", value=_default_docs_root())

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
if prompt:
    openai_api_key = openai_key.strip() or settings.openai_api_key
    exa_api_key = (exa_key.strip() or (settings.exa_api_key or "")).strip() or None

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
            user_messages=user_msgs,
            openai_api_key=openai_api_key,
            openai_model=model.strip(),
            exa_api_key=exa_api_key,
            docs_root=docs_root.strip(),
            status_callback=cb,
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
