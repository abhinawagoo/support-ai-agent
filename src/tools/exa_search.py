from __future__ import annotations

import json
from typing import Any


def exa_search(query: str, num_results: int, exa_api_key: str) -> str:
    """Run an Exa search and return a compact text summary for the model."""
    from exa_py import Exa

    exa = Exa(api_key=exa_api_key)
    num_results = max(1, min(int(num_results or 5), 10))

    results = exa.search_and_contents(
        query,
        num_results=num_results,
        text={"max_characters": 2500},
        highlights={"highlights_per_url": 2, "num_sentences": 2},
    )

    out: list[dict[str, Any]] = []
    for r in getattr(results, "results", []) or []:
        item: dict[str, Any] = {
            "title": getattr(r, "title", None),
            "url": getattr(r, "url", None),
        }
        text = getattr(r, "text", None)
        if text:
            item["text_excerpt"] = text[:4000]
        hl = getattr(r, "highlights", None)
        if hl:
            item["highlights"] = hl
        out.append(item)

    return json.dumps({"results": out}, ensure_ascii=False)
