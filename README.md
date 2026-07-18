# profesia-watch

Telegram-бот, который раз в день сканирует [profesia.sk](https://www.profesia.sk) и присылает новые **стажировки (internship/stáž)** и **бригады (na dohodu)** в Bratislavskom и Trnavskom kraji, подходящие под резюме (IT/DevOps/MLOps-профиль). Каждая вакансия — со ссылкой, зарплатой и списком совпавших ключевых слов.

## Как работает

1. Тянет 4 фида: `{bratislavsky-kraj, trnavsky-kraj} × {internship-staz, na-dohodu-brigady}` за последние `count_days` дней.
2. Отсекает уже виденное (`data/seen_offers.json`) и явный не-IT по заголовку (`negative_title`).
3. Заходит в каждое новое объявление и матчит полный текст по ключевым словам (без учёта диакритики). Правило: вакансия проходит, только если есть настоящий IT-сигнал — минимум `min_strong: 2` сильных слова (python, tester, devops, IT support…) в тексте, либо одно сильное прямо в заголовке. Слабые слова (windows, analyst, sap…) лишь добавляют баллы — по ним одним «stáž в HR с упоминанием Excel» не пройдёт.
4. Шлёт дайджест в Telegram.

## Шаг 0: создать бота (1 минута)

1. В Telegram открой [@BotFather](https://t.me/BotFather) → `/newbot` → имя → получишь **токен**.
2. Напиши своему боту что-нибудь (это нужно, чтобы он мог тебе отвечать).
3. `chat_id` узнаешь после запуска: бот на `/start` отвечает твоим chat_id. Либо сразу: `https://api.telegram.org/bot<ТОКЕН>/getUpdates` → `message.chat.id`.

## Вариант A: GitHub Actions (рекомендую — бесплатно, без сервера)

1. Создай **приватный** репозиторий, залей туда содержимое этой папки.
2. Repo → Settings → Secrets and variables → Actions → добавь `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`.
3. Actions → `daily-job-check` → **Run workflow** (первый запуск, окно 7 дней).

Дальше сам запускается каждый день в 08:00 (cron в `.github/workflows/daily.yml`). Состояние коммитится обратно в репозиторий. В этом варианте работает только ежедневный дайджест, без команды `/check` в чате.

## Вариант B: VPS / Docker (полноценный бот с /check)

```bash
cp .env.example .env   # вписать токен; chat_id можно после первого /start
docker compose up -d --build
docker compose logs -f
```

Бот отвечает на `/check` (проверить сейчас), `/status`, `/start` и сам запускает проверку ежедневно в `run_at` (08:00, Europe/Bratislava).

## Вариант C: локально

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
python -m jobwatch.check            # одна проверка + отправка
python -m jobwatch.check --dry-run  # без отправки, вывод в консоль
```

## Настройка под себя — `config.yaml`

- `keywords.strong / weak` — добавляй/убирай технологии; матч по целым словам, диакритика не важна.
- `negative_title` — заголовки-стоп-слова (vodič, skladník, …).
- `min_strong` — главный регулятор строгости: 2 = нужно два IT-термина в тексте (или один в заголовке); подними до 3, если шумно.
- `min_score` — дополнительный порог по сумме баллов.
- `job_types` — можно раскомментировать `skrateny-uvazok`.
- `notify_empty: false` — не присылать «ничего нового».

## Проверка и отладка

```bash
python -m jobwatch.selftest      # оффлайн-тест парсера и матчинга (20 проверок)
python -m jobwatch.debug_parse   # живой тест парсера на реальной странице
```

Если `debug_parse` покажет `0 offers parsed` — разметка сайта изменилась; пришли вывод Claude, поправим селекторы.

## Ограничения

- Это скрапинг публичных страниц: интервал запросов ~1 с, 1 запуск в день — нагрузка минимальная. Не запускай чаще нескольких раз в день.
- Отклик на вакансию — вручную по ссылке (автоотклик profesia.sk без логина не даёт, и это к лучшему).
