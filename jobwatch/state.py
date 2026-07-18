"""Persistent 'already seen' offer store (JSON file)."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import DATA_DIR

STATE_PATH = DATA_DIR / "seen_offers.json"
KEEP_DAYS = 120


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_state(state: dict) -> None:
    cutoff = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
    pruned = {k: v for k, v in state.items() if v.get("date", "9999") >= cutoff}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pruned, f, ensure_ascii=False, indent=0, sort_keys=True)
    tmp.replace(STATE_PATH)


def mark_seen(state: dict, offer_id: str, score: int, matched: bool) -> None:
    state[offer_id] = {
        "date": date.today().isoformat(),
        "score": score,
        "matched": matched,
    }


def last_run_info() -> str:
    if STATE_PATH.exists():
        ts = datetime.fromtimestamp(STATE_PATH.stat().st_mtime)
        return ts.strftime("%Y-%m-%d %H:%M")
    return "never"
