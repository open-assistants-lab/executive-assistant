#!/usr/bin/env bash
set -euo pipefail

docker build --platform linux/amd64 -t eddyatmc/executive_assistant:latest .
docker push eddyatmc/executive_assistant:latest
