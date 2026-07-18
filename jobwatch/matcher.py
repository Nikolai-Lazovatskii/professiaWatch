"""Keyword scoring of offers against the CV profile.

Matching is diacritics-insensitive and case-insensitive: both the offer text
and the keywords are normalized (NFKD, combining marks stripped, lowercased),
so "programátor" matches "programator" and vice versa.

Decision rule (an offer must be genuinely IT, not just any internship):
  matched  =  not blocked by negative_title
              AND total score >= min_score
              AND ( strong hits in full text >= min_strong
                    OR at least one strong hit directly in the TITLE )

Strong keywords are core IT terms (2 points each); weak keywords (1 point)
only reinforce the score — they can never qualify an offer on their own.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


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


@dataclass
class Verdict:
    is_match: bool
    score: int
    strong: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)
    blocked_by: str | None = None

    @property
    def matched(self) -> list[str]:
        return self.strong + self.weak


class Matcher:
    def __init__(self, cfg: dict):
        kw = cfg.get("keywords", {})
        self.strong: list[str] = kw.get("strong", []) or []
        self.weak: list[str] = kw.get("weak", []) or []
        self.negative_title: list[str] = kw.get("negative_title", []) or []
        self.min_score: int = int(cfg.get("min_score", 2))
        self.min_strong: int = int(cfg.get("min_strong", 2))

    def title_blocked(self, title: str) -> str | None:
        """Return the blocking keyword if the title is an obvious non-IT trade."""
        blocked = _hits(normalize(title), self.negative_title)
        return blocked[0] if blocked else None

    def evaluate(self, title: str, full_text: str) -> Verdict:
        blocked = self.title_blocked(title)
        if blocked:
            return Verdict(False, 0, blocked_by=blocked)

        text_norm = normalize(full_text)
        strong_hits = _hits(text_norm, self.strong)
        weak_hits = _hits(text_norm, self.weak)
        score = 2 * len(strong_hits) + len(weak_hits)

        title_strong = _hits(normalize(title), self.strong)
        it_signal = len(strong_hits) >= self.min_strong or bool(title_strong)
        is_match = it_signal and score >= self.min_score
        return Verdict(is_match, score, strong_hits, weak_hits)
