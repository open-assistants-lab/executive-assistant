#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$REPO_ROOT/results"
mkdir -p "$RESULTS_DIR"

MODE="${1:-smoke}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H%M%S")

if [ "$MODE" = "smoke" ]; then
    echo "=== HybridDB Smoke Benchmarks ==="
    uv run pytest tests/hybriddb/benchmarks/ \
        --benchmark-only \
        --benchmark-json="$RESULTS_DIR/smoke-$TIMESTAMP.json" \
        -x \
        "$@"
elif [ "$MODE" = "full" ]; then
    echo "=== HybridDB Full Benchmarks ==="
    uv run pytest tests/hybriddb/benchmarks/ \
        --benchmark-full \
        --benchmark-only \
        --benchmark-json="$RESULTS_DIR/full-$TIMESTAMP.json" \
        "$@"
elif [ "$MODE" = "e2e" ]; then
    echo "=== HybridDB Full E2E Benchmarks (live embeddings) ==="
    uv run pytest tests/hybriddb/benchmarks/ \
        --benchmark-full \
        --benchmark-only \
        --precompute-embeddings=false \
        --benchmark-json="$RESULTS_DIR/full-e2e-$TIMESTAMP.json" \
        "$@"
else
    echo "Usage: $0 {smoke|full|e2e}"
    exit 1
fi

echo ""
echo "Benchmark complete. Results saved to $RESULTS_DIR/"
