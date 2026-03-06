#!/usr/bin/env bash
set -euo pipefail

echo "⏬ Building new images..."
docker compose build

echo "⏬ Bringing down existing containers..."
docker compose down

echo "⬇️ Pulling updated Docker images..."
docker compose pull

echo "🚀 Starting containers in detached mode..."
docker compose up -d

echo "📝 Streaming logs (press Ctrl-C to stop)..."
docker compose logs -f
