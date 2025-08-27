#!/usr/bin/env bash
# wait-for-dbs.sh
# Waits for Postgres and Qdrant to be ready before starting the app

set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
QDRANT_HOST="${QDRANT_HOST:-qdrant}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
RETRIES="${WAIT_FOR_DB_RETRIES:-20}"
SLEEP="${WAIT_FOR_DB_SLEEP:-2}"

echo "⏳ Waiting for Postgres at $POSTGRES_HOST:$POSTGRES_PORT..."
for i in $(seq 1 $RETRIES); do
    if nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; then
        echo "✅ Postgres is up!"
        break
    fi
    echo "Postgres not ready yet ($i/$RETRIES), retrying in $SLEEP seconds..."
    sleep "$SLEEP"
    if [ "$i" -eq "$RETRIES" ]; then
        echo "❌ Postgres did not become ready in time."
        exit 1
    fi
done

echo "⏳ Waiting for Qdrant at $QDRANT_HOST:$QDRANT_PORT..."
for i in $(seq 1 $RETRIES); do
    if nc -z "$QDRANT_HOST" "$QDRANT_PORT"; then
        echo "✅ Qdrant is up!"
        break
    fi
    echo "Qdrant not ready yet ($i/$RETRIES), retrying in $SLEEP seconds..."
    sleep "$SLEEP"
    if [ "$i" -eq "$RETRIES" ]; then
        echo "❌ Qdrant did not become ready in time."
        exit 1
    fi
done

echo "🚀 Starting application..."
exec "$@"
