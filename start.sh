#!/usr/bin/env bash
set -e

# Start Celery worker + beat in background
celery -A config.celery worker --beat --loglevel=info --concurrency=1 &

# Start daphne (ASGI web server) in foreground
exec daphne -b 0.0.0.0 -p $PORT config.asgi:application
