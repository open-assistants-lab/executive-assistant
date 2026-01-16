#!/usr/bin/env bash
set -euo pipefail

# Records live LLM interactions into VCR cassettes.
# Requires RUN_LIVE_LLM_TESTS=1 and a provider API key.
RUN_LIVE_LLM_TESTS=${RUN_LIVE_LLM_TESTS:-1} \
  uv run pytest -m "langchain_integration and vcr" --record-mode=once -v "$@"
