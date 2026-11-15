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

`/sources/` (login required) lists a user's feeds and lets them add one by URL (checked as RSS/Atom with feedparser, 10 s timeout), turn it on or off, remove it, or pick from the starter catalogue. The catalogue is the repo's `sources.json`, read at runtime. To give a user the whole catalogue:

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
| `DJANGO_EDITIONS_DIR` | `server/media/editions` (`/app/data/editions` in the image) | Built EPUBs, under `<user id>/<date>/` |

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

The `/app/data` mount keeps the SQLite file across deploys; without it every deploy starts from an empty database.
