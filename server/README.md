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
| `DJANGO_SESSION_DAYS` | `365` | How long a login lasts |
| `DJANGO_LOGIN_FAILURES_PER_ACCOUNT` | `5` | Failed PINs before the account locks |
| `DJANGO_LOGIN_FAILURES_PER_IP` | `20` | Failed PINs before the client IP locks |
| `DJANGO_LOGIN_LOCKOUT_MINUTES` | `15` | Lock length, counted from the last failure |
| `DJANGO_INVITE_DAYS` | `14` | How long a sign-up invite stays valid |

## Accounts

The `accounts` app handles sign-up (name, Send-to-Kindle address, 4–6 digit PIN), login and logout.

Sign-up is invite-only. Staff create single-use links at `/invites/` (or in the admin); a link works at `/signup/<token>/` until it is used, revoked or expired. Every other sign-up URL shows the same "you need an invite" page, without saying why. The invite is spent in the same transaction that creates the user.

There is no self-service PIN reset. Staff reset a PIN in the admin (Users → the user → "Reset password"): for non-staff users it takes a 4–6 digit PIN; staff accounts keep Django's password validators. The PIN is stored as Django's password hash; trivial PINs (`1234`, `0000`, `9876`) are refused. Names are unique and matched case-insensitively. Pages extend `server/templates/base.html`: plain forms, no JavaScript, large tap targets for the Kindle browser.

Failed logins are counted per account and per client IP in Django's cache. The cache is `DatabaseCache` in the SQLite file, not the default in-process `LocMemCache`: gunicorn runs two workers, and per-process counters would let an attacker get double the attempts and lose them on every restart. A database cache needs no extra service on the droplet. Migration `accounts/0001` creates the table, so `migrate` stays the only deploy step. The client IP is the rightmost `X-Forwarded-For` entry, the one Dokku's nginx writes.

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
