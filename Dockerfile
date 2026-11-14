# BiteSIze server image (Django + gunicorn). Runs the web and worker processes from Procfile.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=bitesize_server.settings \
    DJANGO_DB_PATH=/app/data/server.sqlite3

WORKDIR /app

# The server wraps the digest pipeline, so it needs both dependency sets.
COPY requirements.txt ./
COPY server/requirements.txt server/
RUN pip install -r requirements.txt -r server/requirements.txt

COPY . .

# collectstatic only reads settings; a throwaway key satisfies the production check.
RUN DJANGO_SECRET_KEY=collectstatic-only python server/manage.py collectstatic --noinput \
 && useradd --create-home --uid 1000 app \
 && mkdir -p /app/data \
 && chown app:app /app/data

USER app

EXPOSE 8000

CMD ["gunicorn", "--chdir", "server", "bitesize_server.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
