from __future__ import annotations

import json
import re
from pathlib import Path


def _tokenize(q: str) -> list[str]:
    return [t for t in re.split(r"\W+", q.lower()) if len(t) >= 3]


def search_local_docs(
    query: str,
    docs_root: str,
    max_files: int = 12,
    context_chars: int = 900,
) -> str:
    """
    Keyword-ish scan across text-ish files under docs_root.
    Good enough for v1; swap for embeddings / Supermemory later.
    """
    root = Path(docs_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return json.dumps({"error": f"docs path not found: {root}"}, ensure_ascii=False)

    terms = _tokenize(query)
    if not terms:
        terms = [query.lower().strip()]

    exts = {".md", ".txt", ".rst", ".markdown"}
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            files.append(p)

    scored: list[tuple[int, Path]] = []
    for p in files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hay = text.lower()
        score = sum(hay.count(t) for t in terms)
        if score:
            scored.append((score, p))

    scored.sort(key=lambda x: (-x[0], str(x[1])))
    scored = scored[:max(1, min(int(max_files), 50))]

    hits: list[dict[str, str | int]] = []
    for score, p in scored:
        text = p.read_text(encoding="utf-8", errors="ignore")
        excerpt = text.strip().replace("\r\n", "\n")
        if len(excerpt) > context_chars:
            excerpt = excerpt[:context_chars] + "\n\n[truncated]"
        hits.append({"path": str(p.relative_to(root)), "score": score, "excerpt": excerpt})

    return json.dumps({"hits": hits}, ensure_ascii=False)
