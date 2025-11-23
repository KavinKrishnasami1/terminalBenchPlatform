#!/bin/bash
# Celery worker startup script for Terminal-Bench platform

set -e

echo "Starting Docker daemon for Harbor execution..."

# Start Docker daemon in the background
dockerd --host=unix:///var/run/docker.sock --host=tcp://0.0.0.0:2375 &

# Wait for Docker socket to be available
echo "Waiting for Docker daemon to be ready..."
while ! docker info > /dev/null 2>&1; do
    sleep 1
done

echo "Docker daemon is ready!"

echo "🚀 Starting Celery worker for Terminal-Bench platform..."

# Get concurrency from environment (default: 5)
CONCURRENCY=${CELERY_CONCURRENCY:-5}

# Get max tasks per child from environment (default: 50)
MAX_TASKS_PER_CHILD=${CELERY_MAX_TASKS_PER_CHILD:-50}

echo "📊 Configuration:"
echo "   - Concurrency: $CONCURRENCY concurrent tasks"
echo "   - Max tasks per child: $MAX_TASKS_PER_CHILD tasks before worker restart"
echo "   - Redis URL: ${REDIS_URL:-not set}"

# Start Celery worker
exec /app/venv/bin/celery -A celery_app worker \
    --loglevel=info \
    --concurrency=$CONCURRENCY \
    --max-tasks-per-child=$MAX_TASKS_PER_CHILD \
    --queues=harbor \
    --hostname=worker@%h
