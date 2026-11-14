"""WSGI entrypoint, served by gunicorn (see Procfile)."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bitesize_server.settings")

application = get_wsgi_application()
