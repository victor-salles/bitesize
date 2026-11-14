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

## Processes

`Procfile` declares three:

- `release`: `migrate`, run by Dokku before each deploy goes live.
- `web`: gunicorn on port 8000, static files served by WhiteNoise.
- `worker`: `db_worker` from `django-tasks-db`, which runs tasks queued through Django's tasks framework. Run exactly one.

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
