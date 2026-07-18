"""Long-running Telegram bot mode (for VPS / Docker).

- Runs the check automatically every day at cfg['run_at'] (local TZ).
- Commands: /check (run now), /status, /start, /help.
- Only the chat from TELEGRAM_CHAT_ID is served; other chats get their
  chat_id echoed back so you can configure it.

Usage: python -m jobwatch.bot
"""
from __future__ import annotations

import datetime as dt
import os
import time
import zoneinfo

import requests

from .check import run_check
from .config import load_config, telegram_credentials
from .notifier import API, send_telegram
from .state import last_run_info

POLL_TIMEOUT = 50


def tg(token: str, method: str, **params):
    resp = requests.post(API.format(token=token, method=method),
                         json=params, timeout=POLL_TIMEOUT + 10)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"telegram {method} failed: {data}")
    return data["result"]


def local_now(tz_name: str) -> dt.datetime:
    return dt.datetime.now(zoneinfo.ZoneInfo(tz_name))


def do_check_and_report(token: str, chat_id: str) -> None:
    try:
        matches = run_check(dry_run=False)
        print(f"[bot] check done, {len(matches)} matches")
    except SystemExit:
        pass
    except Exception as exc:  # noqa: BLE001 - keep the bot alive
        send_telegram(token, chat_id, f"⚠️ profesia-watch: ошибка проверки: {exc}")


def main() -> None:
    cfg = load_config()
    token, chat_id = telegram_credentials()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")
    tz_name = os.environ.get("TZ", "Europe/Bratislava")
    run_at = str(cfg.get("run_at", "08:00"))
    run_h, run_m = (int(x) for x in run_at.split(":"))

    me = tg(token, "getMe")
    print(f"[bot] @{me['username']} started; daily run at {run_at} {tz_name}; "
          f"chat_id={chat_id or 'NOT SET'}")

    offset = 0
    last_run_date: dt.date | None = None
    if chat_id:
        send_telegram(token, chat_id,
                      f"🤖 profesia-watch запущен. Автопроверка ежедневно в {run_at}. "
                      f"Команды: /check /status")

    while True:
        # 1) scheduled daily run
        now = local_now(tz_name)
        if chat_id and last_run_date != now.date() and (now.hour, now.minute) >= (run_h, run_m):
            last_run_date = now.date()
            print(f"[bot] scheduled run {now:%F %T}")
            do_check_and_report(token, chat_id)

        # 2) poll updates
        try:
            updates = tg(token, "getUpdates", offset=offset, timeout=POLL_TIMEOUT,
                         allowed_updates=["message"])
        except Exception as exc:  # noqa: BLE001
            print(f"[bot] poll error: {exc}; retry in 10s")
            time.sleep(10)
            continue

        for upd in updates:
            offset = upd["update_id"] + 1
            msg = upd.get("message") or {}
            text = (msg.get("text") or "").strip().lower()
            from_chat = str(msg.get("chat", {}).get("id", ""))
            if not text:
                continue
            if chat_id and from_chat != str(chat_id):
                tg(token, "sendMessage", chat_id=from_chat,
                   text=f"Ваш chat_id: {from_chat}. Бот приватный.")
                continue
            if text.startswith("/check"):
                tg(token, "sendMessage", chat_id=from_chat, text="⏳ Проверяю profesia.sk…")
                do_check_and_report(token, from_chat)
            elif text.startswith("/status"):
                tg(token, "sendMessage", chat_id=from_chat,
                   text=f"✅ Работаю. Последняя проверка: {last_run_info()}. "
                        f"Автозапуск: {run_at} {tz_name}.")
            elif text.startswith("/start") or text.startswith("/help"):
                tg(token, "sendMessage", chat_id=from_chat,
                   text=f"Ваш chat_id: {from_chat}\n"
                        f"/check — проверить сейчас\n/status — статус\n"
                        f"Автопроверка ежедневно в {run_at}.")


if __name__ == "__main__":
    main()
