from __future__ import annotations

# Preset model IDs for the UI. Users can pick "Custom…" to type any ID your keys can access.
# OpenAI: https://platform.openai.com/docs/models
# Anthropic: https://docs.claude.com/en/docs/about-claude/models

OPENAI_MODEL_PRESETS: tuple[str, ...] = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
)

ANTHROPIC_MODEL_PRESETS: tuple[str, ...] = (
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-3-5-sonnet-20241022",
)

CUSTOM_SENTINEL = "Custom…"
