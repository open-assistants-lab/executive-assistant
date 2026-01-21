#!/usr/bin/env bash
set -euo pipefail

echo "📥 Pulling latest code from Git..."
git pull origin main  # Synchronize with your main branch  [oai_citation:1‡docs.dify.ai](https://docs.dify.ai/en/getting-started/install-self-hosted/docker-compose?utm_source=chatgpt.com)

echo "⬇️ Pulling updated Docker images..."
docker compose pull

echo "⏬ Bringing down existing containers..."
docker compose down

echo "🚀 Starting containers in detached mode..."
docker compose up -d

echo "📝 Streaming logs (press Ctrl-C to stop)..."
docker compose logs -f
