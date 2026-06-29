from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_gis',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'channels',
    'corsheaders',
    'django_filters',
    'cloudinary_storage',
    'cloudinary',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.trips',
    'apps.bookings',
    'apps.pricing',
    'apps.realtime',
    'apps.notifications',
    'apps.payments',
    'apps.dashboard',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': config('DB_NAME', default='twambo_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lusaka'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Cloudinary (persistent media storage) ────────────────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY':    config('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default=''),
}
# Use Cloudinary for all uploaded files (driver docs, vehicle photos, etc.)
# Falls back to local storage if credentials are not set (local dev).
if config('CLOUDINARY_CLOUD_NAME', default=''):
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://localhost:6379')],
        },
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Africa/Lusaka'

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    'create-recurring-trip-instances': {
        'task': 'apps.trips.tasks.create_recurring_trip_instances',
        'schedule': crontab(hour=0, minute=0),
    },
    'expire-booking-windows': {
        'task': 'apps.bookings.tasks.expire_booking_windows',
        'schedule': 60.0,
    },
    'auto-cancel-trips-minimum-not-met': {
        'task': 'apps.trips.tasks.auto_cancel_trips_minimum_not_met',
        'schedule': 60.0,
    },
    'expire-stale-ride-requests': {
        'task': 'apps.trips.tasks.expire_stale_ride_requests',
        'schedule': 60.0,  # runs every minute; task filters by age internally
    },
}

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000', cast=Csv())
CORS_ALLOW_CREDENTIALS = True

FIREBASE_CREDENTIALS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='')

# TWAMBO business constants
TWAMBO_COMMISSION_RATE_LAUNCH = 0.10
TWAMBO_COMMISSION_RATE_STANDARD = 0.15
TWAMBO_PRIVATE_MULTIPLIER = 1.6
TWAMBO_DETOUR_RATE_PER_KM = 2.0
TWAMBO_MIN_FARE = 15.0
TWAMBO_MIN_PRIVATE_FARE = 25.0
TWAMBO_BOOKING_WINDOW_MINUTES = 7
TWAMBO_NO_SHOW_STRIKE_THRESHOLD = 3
TWAMBO_CANCEL_FREE_WINDOW_MINUTES = 2
TWAMBO_STRIKE_BAN_THRESHOLD = 5          # auto-ban after this many strikes
TWAMBO_AUTO_STRIKE_RATING_FLOOR = 3.0   # average rating below this triggers auto-strike
TWAMBO_AUTO_STRIKE_MIN_RATINGS = 5      # minimum ratings before auto-strike kicks in

# Evening surge — 19:00–22:00 Lusaka time
TWAMBO_SURGE_START_HOUR = 19
TWAMBO_SURGE_END_HOUR = 22
TWAMBO_SURGE_MULTIPLIER = 1.25

TWAMBO_ZONE_RATES = {
    'local': 5.0,
    'city': 2.50,
    'intercity': 0.80,
    'longhaul': 0.60,
}

TWAMBO_ZONE_BOUNDARIES_KM = {
    'local': 5,
    'city': 15,
    'intercity': 50,
}
