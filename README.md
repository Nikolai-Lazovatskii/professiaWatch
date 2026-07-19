# profesia-watch

A Telegram bot that checks [Profesia.sk](https://www.profesia.sk) once per day for new internship and short-term job listings in the Bratislava and Trnava regions that match an IT, DevOps, or MLOps-oriented profile. Each alert includes a link, salary information, and the keywords that matched.

## How it works

1. Pulls four feeds: `{bratislavsky-kraj, trnavsky-kraj} × {internship-staz, na-dohodu-brigady}` for the last `count_days` days.
2. Filters out previously seen offers from `data/seen_offers.json` and obvious non-IT titles using `negative_title`.
3. Opens each new listing and matches the full text against strong and weak keywords (diacritics are ignored). A posting is accepted only when it shows a real IT signal, such as at least `min_strong: 2` strong terms in the text or one strong term in the title.
4. Sends a digest to Telegram.

## Create a bot (about 1 minute)

1. Open [@BotFather](https://t.me/BotFather) in Telegram and run `/newbot`.
2. Choose a name for the bot and save the generated token.
3. Start a conversation with the bot so it can reply to you.
4. Retrieve your `chat_id` by running the bot once and using the `/start` response, or by calling `https://api.telegram.org/bot<token>/getUpdates`.

## Deployment options

### Option A: GitHub Actions

1. Create a private repository and upload the contents of this folder.
2. Go to the repository settings, open Secrets and variables → Actions, and add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.
3. Open the Actions tab and run `daily-job-check` once to create the initial state.

The workflow runs daily at 08:00 according to the schedule in `.github/workflows/daily.yml`. In this setup, the bot sends a daily digest only; the chat `/check` command is not available.

### Option B: VPS / Docker

```bash
cp .env.example .env   # add the token; chat_id can be filled after the first /start
docker compose up -d --build
docker compose logs -f
```

This setup provides a full bot experience with `/check`, `/status`, and `/start`, and it can run daily checks at the configured `run_at` time (08:00, Europe/Bratislava).

### Option C: Local execution

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
python -m jobwatch.check            # run one check and send notifications
python -m jobwatch.check --dry-run  # print results without sending anything
```

## Configuration

The main settings live in `config.yaml`:

- `keywords.strong` / `keywords.weak` — add or remove technologies; matching is based on whole words, and diacritics are ignored.
- `negative_title` — stop words for titles such as `vodič` or `skladník`.
- `min_strong` — the main strictness setting. A value of `2` means the bot expects two strong IT terms in the text or one strong term in the title.
- `min_score` — an additional threshold based on the total score.
- `job_types` — uncomment `skrateny-uvazok` if needed.
- `notify_empty: false` — suppress notifications when there are no new offers.

## Validation and debugging

```bash
python -m jobwatch.selftest      # offline parser and matcher test (20 checks)
python -m jobwatch.debug_parse   # live parser test against a real page
```

If `debug_parse` reports `0 offers parsed`, the site markup may have changed and the selectors should be updated.

## Notes and limitations

- This project scrapes public pages. The request interval is roughly 1 second, and running it more than once per day is not recommended.
- Applications should be submitted manually through the job link. Automated applications via Profesia without a login are not supported.
