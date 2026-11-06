#!/usr/bin/env bash
# Run the full AURA experiment matrix against the OpenAI API.
#
# The API is reachable only outside the offline research sandbox, so this
# script is what you run on your own machine (or via the GitHub Actions
# workflow .github/workflows/aura-eval.yml).  Costs stay low by design:
# gpt-4o-mini at temperature 0, hard LLM-call caps per run; the full
# matrix is estimated at USD 1-3.
#
# Usage:
#   export OPENAI_API_KEY=sk-...        # or create aura/.env (see .env.example)
#   ./experiments/run_openai.sh [--exps A0,A1,A2,A3,S1,B1,B2,B3] [--model gpt-4o-mini]
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

EXPS="A0,A1,A2,A3,S1,B1,B2,B3"
MODEL="gpt-4o-mini"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --exps)  EXPS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${OPENAI_API_KEY:-}" && ! -f aura/.env ]]; then
  echo "OPENAI_API_KEY is not set and aura/.env does not exist." >&2
  exit 1
fi

echo "== validating ground truth (cross-checks bundled interpreters against real toolchains)"
$PY bench/scripts/validate_ground_truth.py

echo "== unit tests"
$PY -m pytest tests -q || true

echo "== experiment matrix with provider=openai model=$MODEL exps=$EXPS"
$PY experiments/run_matrix.py --provider openai --model "$MODEL" \
    --exps "$EXPS" --out results-openai

echo "== aggregating"
$PY experiments/aggregate.py --results results-openai

echo "done: results-openai/summary.md"
