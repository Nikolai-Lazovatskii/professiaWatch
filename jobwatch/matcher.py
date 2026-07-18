"""Keyword scoring of offers against the CV profile.

Matching is diacritics-insensitive and case-insensitive: both the offer text
and the keywords are normalized (NFKD, combining marks stripped, lowercased),
so "programátor" matches "programator" and vice versa.
"""
from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower())


def _hits(text_norm: str, keywords: list[str]) -> list[str]:
    found = []
    for kw in keywords:
        kw_norm = normalize(kw).strip()
        if not kw_norm:
            continue
        # word-boundary-ish match; keywords may contain +, /, . (c++, ci/cd, node.js)
        pattern = r"(?<![a-z0-9])" + re.escape(kw_norm) + r"(?![a-z0-9])"
        if re.search(pattern, text_norm):
            found.append(kw)
    return found


class Matcher:
    def __init__(self, cfg: dict):
        kw = cfg.get("keywords", {})
        self.strong: list[str] = kw.get("strong", []) or []
        self.weak: list[str] = kw.get("weak", []) or []
        self.negative_title: list[str] = kw.get("negative_title", []) or []
        self.min_score: int = int(cfg.get("min_score", 2))

    def title_blocked(self, title: str) -> str | None:
        """Return the blocking keyword if the title is an obvious non-IT trade."""
        blocked = _hits(normalize(title), self.negative_title)
        return blocked[0] if blocked else None

    def score(self, text: str) -> tuple[int, list[str]]:
        text_norm = normalize(text)
        strong_hits = _hits(text_norm, self.strong)
        weak_hits = _hits(text_norm, self.weak)
        score = 2 * len(strong_hits) + len(weak_hits)
        return score, strong_hits + weak_hits

    def is_match(self, score: int) -> bool:
        return score >= self.min_score
