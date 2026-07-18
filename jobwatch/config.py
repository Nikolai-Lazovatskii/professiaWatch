"""Configuration loading (config.yaml + environment variables)."""
import os
from pathlib import Path

import yaml

BASE_DIR = Path(os.environ.get("JOBWATCH_HOME", Path(__file__).resolve().parent.parent))
CONFIG_PATH = Path(os.environ.get("JOBWATCH_CONFIG", BASE_DIR / "config.yaml"))
DATA_DIR = Path(os.environ.get("JOBWATCH_DATA", BASE_DIR / "data"))

DEFAULTS = {
    "regions": ["bratislavsky-kraj", "trnavsky-kraj"],
    "job_types": ["internship-staz", "na-dohodu-brigady"],
    "count_days": 2,        # look-back window for daily runs (overlap is deduplicated)
    "first_run_days": 7,    # look-back window when state is empty (first run)
    "max_pages": 5,         # pagination safety cap per feed
    "min_score": 2,         # include offer if score >= min_score
    "fetch_details": True,  # fetch offer detail page for deeper matching
    "request_delay": 0.8,   # seconds between HTTP requests
    "notify_empty": True,   # send "nothing new" message
    "run_at": "08:00",      # daily run time for bot mode (local TZ)
    "keywords": {"strong": [], "weak": [], "negative_title": []},
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        for k, v in user_cfg.items():
            cfg[k] = v
    return cfg


def telegram_credentials() -> tuple[str | None, str | None]:
    return os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
