#!/bin/bash
# Quick script to sync task files to all workers via tar streaming

set -e

APP_NAME="tbench-platform-backend"

echo "🔍 Syncing tasks to workers..."

# Get worker IDs
WORKERS="28675d4a445078 683974ec022518"

for WORKER in $WORKERS; do
    echo "📦 Syncing to worker $WORKER..."

    # Create tar on app machine, download, upload to worker, extract
    flyctl ssh console -a $APP_NAME --machine 1850e46f75d558 --command \
        "cd /data && tar czf - uploads" 2>/dev/null | \
        flyctl ssh console -a $APP_NAME --machine $WORKER --command \
        "cd /data && tar xzf -" 2>/dev/null || true

    echo "✅ Worker $WORKER synced"
done

echo "✅ All workers synced!"
