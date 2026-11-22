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
| `DJANGO_LOG_LEVEL` | `INFO` | Logs go to stdout: one JSON object per line in production, plain text in debug |
| `DJANGO_ADMINS` | empty | Comma-separated emails for Django's error emails. Nothing is sent until an email backend is configured |
| `DJANGO_SERVER_EMAIL` | `root@localhost` | Sender of those error emails |
| `DJANGO_SESSION_DAYS` | `365` | How long a login lasts |
| `DJANGO_LOGIN_FAILURES_PER_ACCOUNT` | `5` | Failed PINs before the account locks |
| `DJANGO_LOGIN_FAILURES_PER_IP` | `20` | Failed PINs before the client IP locks |
| `DJANGO_LOGIN_LOCKOUT_MINUTES` | `15` | Lock length, counted from the last failure |
| `DJANGO_INVITE_DAYS` | `14` | How long a sign-up invite stays valid |
| `DJANGO_ADMIN_PATH` | `admin` | URL path of the Django admin (staff only). Set a non-obvious path in production |
| `DJANGO_HSTS_SECONDS` | `86400` (1 day) | HSTS max-age when `DJANGO_DEBUG` is off. Raise it (e.g. `31536000`) once HTTPS has held up |
| `DJANGO_EDITIONS_DIR` | `server/media/editions` (`/app/data/editions` in the image) | Built EPUBs, under `<user id>/<date>/` |
| `DJANGO_BACKUP_DIR` | `backups/` next to the SQLite file (`/app/data/backups` in the image) | Daily database copies, see [Backups](#backups) |
| `DJANGO_BACKUP_KEEP` | `14` | How many backups to keep; older ones are deleted after each run |
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

Scheduled tasks are not processes: see [Daily schedule](#daily-schedule).

## Edition queue

`editions.services.enqueue_edition(user, date)` creates the user's edition for that date (or re-queues it if it failed) and enqueues `editions.tasks.build_user_edition`. The worker builds editions one at a time, oldest `queued_at` first, and records the counts, EPUB path or error on the edition. Failed editions can be retried from the admin (Editions → "Retry selected failed editions"); a retry goes to the back of the queue.

One at a time is how the server fits the 1 GB droplet:

- `db_worker` runs tasks one after another in a single process, so one `worker` process means one edition at a time. Keep `dokku ps:scale bitesize worker=1`.
- If a second worker runs anyway, a task that finds another edition `running` puts itself back in the queue for a minute later instead of building in parallel.
- An edition `running` for more than `EDITION_STALE_AFTER` (2 hours) lost its worker (crash or deploy); the next task marks it failed so it can be retried.

`/editions/` (where `/` sends logged-in users) shows today's edition, how many queued or running editions are ahead of it, and an estimated wait from the median run time of the last 20 succeeded editions (10 minutes when none has been built yet). It warns when the wait is over twice that median, and a button queues today's edition through `enqueue_edition`.

After an edition is built, the worker sends the `editions.signals.edition_built` signal. Delivery connects there.

## Daily schedule

`python server/manage.py enqueue_due_editions` queues today's edition for every active reader whose delivery time (`Profile.delivery_time`, in `Profile.timezone`) has passed and who has no edition for their local date yet. Running it again the same day queues nothing more. Readers without a Kindle address or without active sources are skipped, with an `INFO` log line saying why. An edition that already exists for the day, failed ones included, counts as done: retry failures from the admin.

Dokku runs it every ten minutes from the `cron` entry in the repo-root `app.json` (`dokku cron:list bitesize` shows it). Cron uses the server's clock (UTC); each reader's time zone is applied by the command. An edition is queued up to ten minutes after the delivery time, plus its wait in the queue and its build time. A delivery time after 23:50 local is never reached, because the next run already falls on the next local day.

`app.json` also runs `backup_database` daily at 03:00 UTC: see [Backups](#backups).

`app.json` also declares a startup healthcheck on `/healthz` (port 8000): Dokku sends traffic to a new deploy only once it answers 200.

## Deploy (Dokku)

```bash
dokku apps:create bitesize
dokku builder:set bitesize selected dockerfile
dokku ports:set bitesize http:80:8000
dokku storage:create bitesize                          # /var/lib/dokku/data/storage/bitesize
chown 1000:1000 /var/lib/dokku/data/storage/bitesize   # the image runs as uid 1000
dokku storage:mount bitesize bitesize --container-dir /app/data
dokku config:set bitesize DJANGO_SECRET_KEY=... \
  DJANGO_ALLOWED_HOSTS=bitesize.victorsalles.com \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://bitesize.victorsalles.com
git push dokku <branch>:main
dokku ps:scale bitesize web=1 worker=1
dokku letsencrypt:enable bitesize
```

`storage:create` replaces the deprecated `storage:ensure-directory`. An app mounted the old way (`dokku storage:mount bitesize /var/lib/dokku/data/storage/bitesize:/app/data`) uses the same host directory and needs no change. `dokku storage:report bitesize` shows the mount.

With `DJANGO_DEBUG` off the app redirects plain HTTP to HTTPS (except `/healthz`, so container health checks can call it directly), sends HSTS, and marks the session and CSRF cookies secure. `python server/manage.py check --deploy` should report only `security.W021` (HSTS preload, deliberately off).

Everything that must survive a deploy lives under the `/app/data` mount: the SQLite file (`DJANGO_DB_PATH`), built EPUBs (`DJANGO_EDITIONS_DIR`) and backups (`DJANGO_BACKUP_DIR`). The image sets the first two to `/app/data/...`, and backups default to the database's folder. Without the mount every deploy starts from an empty database. Cron entries from `app.json` are picked up on deploy (`dokku cron:list bitesize`).

## Backups

`python server/manage.py backup_database` copies the database with SQLite's backup API, which is consistent while the web and worker processes write, to `DJANGO_BACKUP_DIR/server-<UTC timestamp>.sqlite3`, then deletes all but the newest `DJANGO_BACKUP_KEEP`. Dokku runs it daily at 03:00 UTC. On the host the copies are in `/var/lib/dokku/data/storage/bitesize/backups/`.

They sit on the droplet's own disk, so they cover a bad migration or a corrupted file, not losing the droplet. Copy one off now and then:

```bash
scp personal-droplet:/var/lib/dokku/data/storage/bitesize/backups/server-<timestamp>.sqlite3 .
```

To restore, on the droplet:

```bash
dokku ps:stop bitesize
cd /var/lib/dokku/data/storage/bitesize
mv server.sqlite3 server.sqlite3.broken
rm -f server.sqlite3-wal server.sqlite3-shm    # WAL of the old file; would corrupt the restored one
cp backups/server-<timestamp>.sqlite3 server.sqlite3
chown 1000:1000 server.sqlite3
dokku ps:start bitesize
```

Built EPUBs are not backed up.
