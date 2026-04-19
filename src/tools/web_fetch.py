from __future__ import annotations

import re

import httpx
import trafilatura


def fetch_url_text(url: str, max_chars: int = 12000) -> str:
    """Download a page and extract main text (best-effort)."""
    max_chars = max(1000, min(int(max_chars), 50_000))
    headers = {
        "User-Agent": "SupportAgentBot/1.0 (+https://example.invalid)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()

    downloaded = resp.text
    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        url=url,
    )
    if not extracted:
        extracted = re.sub(r"<[^>]+>", " ", downloaded)
        extracted = re.sub(r"\s+", " ", extracted).strip()

    extracted = extracted.strip()
    if len(extracted) > max_chars:
        extracted = extracted[:max_chars] + "\n\n[truncated]"
    return extracted
