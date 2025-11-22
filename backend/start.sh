#!/bin/bash
set -e

echo "Starting Docker daemon..."

# Start Docker daemon in the background
dockerd --host=unix:///var/run/docker.sock --host=tcp://0.0.0.0:2375 &

# Wait for Docker socket to be available
echo "Waiting for Docker daemon to be ready..."
while ! docker info > /dev/null 2>&1; do
    sleep 1
done

echo "Docker daemon is ready!"

# Start FastAPI application
echo "Starting FastAPI application..."
exec /app/venv/bin/uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001}
