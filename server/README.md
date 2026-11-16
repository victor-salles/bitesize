# BiteSIze server

Django app that lets several people sign up and configure their own daily digest. It wraps the same pipeline as the CLI. Server-rendered HTML only: the stock Kindle browser has no JavaScript.

## Run locally

From the repo root:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt          # CLI + server + test deps
export DJANGO_DEBUG=true                     # dev key, localhost hosts
python server/manage.py migrate
python server/manage.py runserver            # http://127.0.0.1:8000/healthz
python server/manage.py db_worker            # task worker, in a second shell
```

The SQLite file defaults to `server/db.sqlite3` (gitignored).

## News sources

`/sources/` (login required) lists a user's feeds and lets them add one by URL (checked as RSS/Atom with feedparser, 10 s timeout; only http/https on ports 80/443, and the host and every redirect must resolve to public IPs), turn it on or off, remove it, or pick from the starter catalogue. The catalogue is the repo's `sources.json`, read at runtime. To give a user the whole catalogue:

```bash
python server/manage.py add_starter_sources <username> [--category Tech ...]
```

## Tests

`pytest` from the repo root runs the CLI tests and `server/tests/` together (see `pytest.ini`).

## Environment

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | none | Required unless `DJANGO_DEBUG` is on |
| `DJANGO_DEBUG` | `false` | `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` in debug, empty otherwise | Comma-separated |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Comma-separated, with scheme: `https://bitesize.example.com` |
| `DJANGO_DB_PATH` | `server/db.sqlite3` (`/app/data/server.sqlite3` in the image) | SQLite file path |
| `DJANGO_TIME_ZONE` | `UTC` | |
| `DJANGO_LOG_LEVEL` | `INFO` | |
| `DJANGO_SESSION_DAYS` | `365` | How long a login lasts |
| `DJANGO_LOGIN_FAILURES_PER_ACCOUNT` | `5` | Failed PINs before the account locks |
| `DJANGO_LOGIN_FAILURES_PER_IP` | `20` | Failed PINs before the client IP locks |
| `DJANGO_LOGIN_LOCKOUT_MINUTES` | `15` | Lock length, counted from the last failure |
| `DJANGO_INVITE_DAYS` | `14` | How long a sign-up invite stays valid |
| `DJANGO_HSTS_SECONDS` | `86400` (1 day) | HSTS max-age when `DJANGO_DEBUG` is off. Raise it (e.g. `31536000`) once HTTPS has held up |
| `DJANGO_EDITIONS_DIR` | `server/media/editions` (`/app/data/editions` in the image) | Built EPUBs, under `<user id>/<date>/` |
| `GEMINI_API_KEY` | empty | Server's Gemini API key. Empty means no AI: editions build without summaries. Set it with `dokku config:set`, never in git |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Any current Gemini model code |
| `GEMINI_DAILY_REQUEST_CAP` | `200` | Gemini requests per day (server time zone), covers included. Past it, editions build without summaries |

## Accounts

The `accounts` app handles sign-up (name, Send-to-Kindle address, 4–6 digit PIN), login and logout.

Sign-up is invite-only. Staff create single-use links at `/invites/` (or in the admin); a link works at `/signup/<token>/` until it is used, revoked or expired. Every other sign-up URL shows the same "you need an invite" page, without saying why. The invite is spent in the same transaction that creates the user.

There is no self-service PIN reset. Staff reset a PIN in the admin (Users → the user → "Reset password"): for non-staff users it takes a 4–6 digit PIN; staff accounts keep Django's password validators. The PIN is stored as Django's password hash; trivial PINs (`1234`, `0000`, `9876`) are refused. Names are unique and matched case-insensitively. Pages extend `server/templates/base.html`: plain forms, no JavaScript, large tap targets for the Kindle browser.

Failed logins are counted per account and per client IP in Django's cache. The cache is `DatabaseCache` in the SQLite file, not the default in-process `LocMemCache`: gunicorn runs two workers, and per-process counters would let an attacker get double the attempts and lose them on every restart. A database cache needs no extra service on the droplet. Migration `accounts/0001` creates the table, so `migrate` stays the only deploy step. The client IP is the rightmost `X-Forwarded-For` entry, the one Dokku's nginx writes.

## AI and the article cache

The server calls the Gemini API directly (`articles.gemini.GeminiClient`, an `ai.AIClient`). Summaries, scores, tags and ad skips are cached in `core.Article` per URL and language (`articles.cache.DatabaseArticleCache`), so an article several users follow goes to Gemini once. A cached row is reused while the article's text hash matches. Section and global covers are per user and are not cached.

`editions.services.edition_config()` gives every queued edition both (`articles.services.get_server_ai_client()` and `get_article_cache()`).

Daily request counts are in the admin under *AI usage*.

## Processes

`Procfile` declares three:

- `release`: `migrate`, run by Dokku before each deploy goes live.
- `web`: gunicorn on port 8000, static files served by WhiteNoise.
- `worker`: `db_worker` from `django-tasks-db`, which runs tasks queued through Django's tasks framework. Run exactly one.

## Edition queue

`editions.services.enqueue_edition(user, date)` creates the user's edition for that date (or re-queues it if it failed) and enqueues `editions.tasks.build_user_edition`. The worker builds editions one at a time, oldest `queued_at` first, and records the counts, EPUB path or error on the edition. Failed editions can be retried from the admin (Editions → "Retry selected failed editions"); a retry goes to the back of the queue.

One at a time is how the server fits the 1 GB droplet:

- `db_worker` runs tasks one after another in a single process, so one `worker` process means one edition at a time. Keep `dokku ps:scale bitesize worker=1`.
- If a second worker runs anyway, a task that finds another edition `running` puts itself back in the queue for a minute later instead of building in parallel.
- An edition `running` for more than `EDITION_STALE_AFTER` (2 hours) lost its worker (crash or deploy); the next task marks it failed so it can be retried.

After an edition is built, the worker sends the `editions.signals.edition_built` signal. Delivery connects there.

## Deploy (Dokku)

```bash
dokku apps:create bitesize
dokku builder:set bitesize selected dockerfile
dokku ports:set bitesize http:80:8000
dokku storage:ensure-directory bitesize
chown 1000:1000 /var/lib/dokku/data/storage/bitesize   # the image runs as uid 1000
dokku storage:mount bitesize /var/lib/dokku/data/storage/bitesize:/app/data
dokku config:set bitesize DJANGO_SECRET_KEY=... \
  DJANGO_ALLOWED_HOSTS=bitesize.victorsalles.com \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://bitesize.victorsalles.com
git push dokku <branch>:main
dokku ps:scale bitesize web=1 worker=1
dokku letsencrypt:enable bitesize
```

With `DJANGO_DEBUG` off the app redirects plain HTTP to HTTPS (except `/healthz`, so container health checks can call it directly), sends HSTS, and marks the session and CSRF cookies secure. `python server/manage.py check --deploy` should report only `security.W021` (HSTS preload, deliberately off).

The `/app/data` mount keeps the SQLite file across deploys; without it every deploy starts from an empty database.
