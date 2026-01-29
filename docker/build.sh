#!/usr/bin/env bash
set -euo pipefail

# Build from project root with Dockerfile in docker/
docker build --platform linux/amd64 -f docker/Dockerfile -t eddyatmc/executive_assistant:latest .
docker push eddyatmc/executive_assistant:latest
