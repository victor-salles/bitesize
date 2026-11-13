release: python server/manage.py migrate --noinput
web: gunicorn --chdir server bitesize_server.wsgi --bind 0.0.0.0:8000 --workers 2 --access-logfile -
worker: python server/manage.py db_worker
