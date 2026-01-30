#!/usr/bin/env bash
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root where docker-compose.yml is located
cd "$PROJECT_ROOT"

echo "📥 Pulling latest code from Git..."
git pull origin main

echo "⬇️ Pulling updated Docker images..."
docker compose -f docker/docker-compose.yml pull

echo "⏬ Bringing down existing containers..."
docker compose -f docker/docker-compose.yml down

echo "🚀 Starting containers in detached mode..."
docker compose -f docker/docker-compose.yml up -d

echo "📝 Streaming logs (press Ctrl-C to stop)..."
docker compose -f docker/docker-compose.yml logs -f
