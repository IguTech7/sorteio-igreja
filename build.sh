#!/usr/bin/env bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py loaddata backup.json || true
python manage.py createsuperuser --noinput --username igor --email admin@admin.com || true