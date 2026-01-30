#!/usr/bin/env bash
set -euo pipefail

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root for build context
cd "$PROJECT_ROOT"

# Build from project root with Dockerfile in docker/
docker build --platform linux/amd64 -f docker/Dockerfile -t eddyatmc/executive_assistant:latest .
docker push eddyatmc/executive_assistant:latest
