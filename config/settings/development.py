from .base import *
from decouple import config

DEBUG = True
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# SQLite for local development — zero setup, no Docker needed.
# PostgreSQL / PostGIS used in production (Docker / Render).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Disable Celery tasks locally — no Redis needed
CELERY_TASK_ALWAYS_EAGER = True

# In-memory channel layer — no Redis needed for dev WebSocket testing
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

# Fast password hasher for dev — PBKDF2 with 720k iterations takes ~10s on a laptop.
# MD5 is instant. Never use this in production.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Strip GIS apps that require GDAL — not needed for local development
INSTALLED_APPS = [
    app for app in INSTALLED_APPS
    if app not in ('django.contrib.gis', 'rest_framework_gis')
]
