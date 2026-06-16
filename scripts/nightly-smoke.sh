#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Source .env for OLLAMA_API_KEY if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

if [ -z "${OLLAMA_API_KEY:-}" ]; then
    echo "ERROR: OLLAMA_API_KEY is not set" >&2
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="data/smoke"
REPORT_FILE="${OUTPUT_DIR}/smoke_report_${TIMESTAMP}.md"

echo "=== Nightly Smoke Suite ==="
echo "Started: $(date)"
echo "Model:   ollama-cloud:deepseek-v4-flash"
echo "Output:  ${OUTPUT_DIR}"
echo ""

uv run python tests/smoke/run_smoke.py \
    --api-key "$OLLAMA_API_KEY" \
    --model "ollama-cloud:deepseek-v4-flash" \
    --output "${OUTPUT_DIR}" \
    --personas 5 \
    --streaming all \
    --verbose

EXIT_CODE=$?

echo ""
echo "Report: ${REPORT_FILE}"
echo "Finished: $(date)"
echo "Exit code: ${EXIT_CODE}"

exit $EXIT_CODE
