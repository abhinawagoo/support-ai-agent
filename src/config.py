from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _norm(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t or None


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    anthropic_api_key: str | None
    exa_api_key: str | None
    openai_model: str
    anthropic_model: str
    default_llm_provider: str  # "openai" | "anthropic"
    dottle_agent_name: str
    dottle_user_id: str | None
    dottle_user_email: str | None

    @staticmethod
    def load() -> "Settings":
        prov = (os.getenv("LLM_PROVIDER") or "openai").strip().lower()
        if prov not in {"openai", "anthropic"}:
            prov = "openai"
        return Settings(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            anthropic_api_key=_norm(os.getenv("ANTHROPIC_API_KEY")),
            exa_api_key=_norm(os.getenv("EXA_API_KEY")),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip(),
            default_llm_provider=prov,
            dottle_agent_name=(os.getenv("DOTTLE_AGENT_NAME") or "support-ai-agent").strip(),
            dottle_user_id=_norm(os.getenv("DOTTLE_USER_ID")),
            dottle_user_email=_norm(os.getenv("DOTTLE_USER_EMAIL")),
        )
