#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('CREATE EXTENSION IF NOT EXISTS postgis')
"
python manage.py migrate
python - <<'EOF' || true
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()
from apps.accounts.models import User
phone = os.environ.get('DJANGO_SUPERUSER_PHONE')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
if phone and password and not User.objects.filter(phone_number=phone).exists():
    User.objects.create_superuser(phone_number=phone, password=password, email=email)
    print(f'Superuser created: {phone}')
EOF
