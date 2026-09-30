"""Mock search over env['docs']: case-insensitive word matching, ranked by matched-word count."""
from __future__ import annotations

from agent_urp.tools.env import VersionedEnv


def search(env: VersionedEnv, query: str, limit: int = 5) -> list[dict]:
    words = [w.lower() for w in query.split()]
    scored = []
    for doc in env.get("docs", []) or []:
        hay = f"{doc.get('title', '')} {doc.get('text', '')}".lower()
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((-score, str(doc.get("id", "")), doc))
    return [d for _, _, d in sorted(scored, key=lambda t: (t[0], t[1]))][:limit]
