from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    exa_api_key: str | None
    openai_model: str

    @staticmethod
    def load() -> "Settings":
        return Settings(
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            exa_api_key=(os.getenv("EXA_API_KEY") or "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        )
