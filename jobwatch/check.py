"""One-shot check: scrape feeds, match new offers, notify, update state.

Usage:
    python -m jobwatch.check                # real run (needs TELEGRAM_* env)
    python -m jobwatch.check --dry-run      # print digest to stdout, no state write
    python -m jobwatch.check --dry-run --keep-state   # dry run but persist state
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date

from . import profesia
from .config import load_config, telegram_credentials
from .matcher import Matcher
from .notifier import format_digest, send_telegram
from .state import load_state, mark_seen, save_state


def run_check(dry_run: bool = False, write_state: bool | None = None,
              log=print) -> list[profesia.Offer]:
    cfg = load_config()
    matcher = Matcher(cfg)
    state = load_state()
    first_run = not state
    count_days = int(cfg["first_run_days"] if first_run else cfg["count_days"])
    if write_state is None:
        write_state = not dry_run

    session = profesia.make_session()
    delay = float(cfg["request_delay"])

    new_offers: list[profesia.Offer] = []
    scanned_ids: set[str] = set()
    for region in cfg["regions"]:
        for job_type in cfg["job_types"]:
            log(f"[feed] {region} / {job_type} (last {count_days}d)")
            try:
                offers = profesia.fetch_feed(
                    session, region, job_type, count_days,
                    max_pages=int(cfg["max_pages"]), delay=delay,
                )
            except RuntimeError as exc:
                log(f"[warn] feed failed: {exc}")
                continue
            log(f"[feed] {len(offers)} offers")
            for o in offers:
                if o.offer_id in state or o.offer_id in scanned_ids:
                    continue
                scanned_ids.add(o.offer_id)
                new_offers.append(o)
            time.sleep(delay)

    if not new_offers:
        log("[info] no new offers in feeds")

    matches: list[profesia.Offer] = []
    for o in new_offers:
        blocked = matcher.title_blocked(o.title)
        if blocked:
            log(f"[skip] {o.offer_id} '{o.title[:50]}' blocked by '{blocked}'")
            mark_seen(state, o.offer_id, 0, False)
            continue
        text = f"{o.title} {o.company}"
        if cfg["fetch_details"]:
            time.sleep(delay)
            o.detail_text = profesia.fetch_detail_text(session, o)
            text = f"{text} {o.detail_text}"
        o.score, o.matched = matcher.score(text)
        is_match = matcher.is_match(o.score)
        mark_seen(state, o.offer_id, o.score, is_match)
        log(f"[{'MATCH' if is_match else 'no   '}] score={o.score:<3} {o.title[:60]}")
        if is_match:
            matches.append(o)

    matches.sort(key=lambda o: (-("stáž" in o.job_type or "internship" in o.job_type), -o.score))

    day_str = date.today().strftime("%d.%m.%Y")
    digest = format_digest(matches, scanned=len(new_offers), day_str=day_str)

    if dry_run:
        log("\n----- DIGEST (dry run) -----\n")
        log(digest)
    elif matches or cfg["notify_empty"]:
        token, chat_id = telegram_credentials()
        if not token or not chat_id:
            log("[error] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
            sys.exit(2)
        send_telegram(token, chat_id, digest)
        log(f"[done] sent digest: {len(matches)} matches")

    if write_state:
        save_state(state)
        log(f"[state] saved ({len(state)} seen offers)")
    return matches


def main() -> None:
    ap = argparse.ArgumentParser(description="profesia.sk one-shot check")
    ap.add_argument("--dry-run", action="store_true", help="print digest instead of sending")
    ap.add_argument("--keep-state", action="store_true",
                    help="persist seen-offers state even with --dry-run")
    args = ap.parse_args()
    run_check(dry_run=args.dry_run, write_state=True if args.keep_state else None)


if __name__ == "__main__":
    main()
