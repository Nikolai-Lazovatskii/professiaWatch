"""Telegram delivery: digest formatting and sendMessage with 4096-char chunking."""
from __future__ import annotations

import html
import time

import requests

from .profesia import Offer

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4000  # keep margin below Telegram's 4096 limit


def esc(text: str) -> str:
    return html.escape(text or "", quote=False)


def format_offer(o: Offer) -> str:
    icon = "🎓" if "internship" in o.job_type or "stáž" in o.job_type else "🧰"
    lines = [f'{icon} <a href="{o.url}">{esc(o.title)}</a>']
    meta1 = " — ".join(x for x in [esc(o.company), esc(o.location)] if x)
    if meta1:
        lines.append(f"   {meta1}")
    bits = []
    if o.salary:
        bits.append(f"💶 {esc(o.salary)}")
    bits.append(f"🏷 {esc(o.job_type)}")
    bits.append(f"⭐ {o.score}")
    lines.append("   " + " | ".join(bits))
    if o.matched:
        lines.append(f"   🔑 {esc(', '.join(o.matched[:8]))}")
    return "\n".join(lines)


def format_digest(offers: list[Offer], scanned: int, day_str: str) -> str:
    if not offers:
        return (f"🔎 profesia.sk, {day_str}: новых подходящих вакансий нет "
                f"(просмотрено {scanned} новых объявлений).")
    interns = [o for o in offers if "stáž" in o.job_type or "internship" in o.job_type]
    brigady = [o for o in offers if o not in interns]
    parts = [f"🔎 <b>profesia.sk, {day_str}</b> — новые подходящие вакансии: "
             f"{len(offers)} (из {scanned} новых)"]
    if interns:
        parts.append("\n<b>Стажировки / internship</b>")
        parts.extend(format_offer(o) for o in interns)
    if brigady:
        parts.append("\n<b>Бригады / dohoda</b>")
        parts.extend(format_offer(o) for o in brigady)
    return "\n\n".join(parts)


def _chunks(text: str) -> list[str]:
    if len(text) <= MAX_LEN:
        return [text]
    out, cur = [], ""
    for block in text.split("\n\n"):
        candidate = (cur + "\n\n" + block) if cur else block
        if len(candidate) > MAX_LEN and cur:
            out.append(cur)
            cur = block
        else:
            cur = candidate
    if cur:
        out.append(cur)
    return out


def send_telegram(token: str, chat_id: str, text: str) -> None:
    for chunk in _chunks(text):
        resp = requests.post(
            API.format(token=token, method="sendMessage"),
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Telegram API error {resp.status_code}: {resp.text[:300]}")
        time.sleep(0.5)
