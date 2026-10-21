#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}

usage() {
  cat <<'EOF'
Usage:
  scripts/run_experiments.sh --model PROVIDER:MODEL --dataset DATASET [options]

Required:
  --model SPEC             e.g. mock:echo, local:Qwen2.5-7B, openai:gpt-model
  --dataset NAME           hospital, movies, or beers (repeatable)

Options:
  --seed N                 also run construction seed N (repeatable; hospital/movies)
  --workers N              concurrent requests (default: 16)
  --max-tokens N           generation budget (default: 4096)
  --no-near                skip near-entity experiments
  --p1                     also run row-continuation experiments
  --allow-paid-api         acknowledge possible external API charges/data transfer
  --dry-run                print the command without executing it
  -h, --help               show this help

API credentials and endpoint URLs are read only from environment variables.
Outputs, caches, usage records, and logs are written below build/.
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 0
fi

model=""
datasets=()
seeds=()
workers=16
max_tokens=4096
no_near=0
p1=0
allow_paid=0
dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) model=${2:?missing value for --model}; shift 2 ;;
    --dataset) datasets+=("${2:?missing value for --dataset}"); shift 2 ;;
    --seed) seeds+=("${2:?missing value for --seed}"); shift 2 ;;
    --workers) workers=${2:?missing value for --workers}; shift 2 ;;
    --max-tokens) max_tokens=${2:?missing value for --max-tokens}; shift 2 ;;
    --no-near) no_near=1; shift ;;
    --p1) p1=1; shift ;;
    --allow-paid-api) allow_paid=1; shift ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$model" || ${#datasets[@]} -eq 0 ]]; then
  echo "Error: --model and at least one --dataset are required." >&2
  usage >&2
  exit 2
fi

for dataset in "${datasets[@]}"; do
  case "$dataset" in
    hospital|movies|beers) ;;
    *) echo "Error: unknown dataset: $dataset" >&2; exit 2 ;;
  esac
done

provider=${model%%:*}
if [[ "$model" != *:* ]]; then
  echo "Error: --model must use PROVIDER:MODEL syntax." >&2
  exit 2
fi
case "$provider" in
  mock|local|localbase) ;;
  *)
    if [[ $allow_paid -ne 1 ]]; then
      echo "Error: provider '$provider' may incur charges or external data transfer; rerun with --allow-paid-api." >&2
      exit 3
    fi
    ;;
esac

cmd=("$PYTHON" -m src.pipeline --model "$model" --datasets "${datasets[@]}" --workers "$workers" --max-tokens "$max_tokens")
if [[ ${#seeds[@]} -gt 0 ]]; then
  cmd+=(--seeds "${seeds[@]}")
fi
if [[ $no_near -eq 1 ]]; then
  cmd+=(--no-near)
fi
if [[ $p1 -eq 1 ]]; then
  cmd+=(--p1)
fi

printf 'PYTHONPATH=code'
printf ' %s' "${cmd[@]}"
printf '\n'
if [[ $dry_run -eq 1 ]]; then
  exit 0
fi

export PYTHONPATH="$ROOT/code${PYTHONPATH:+:$PYTHONPATH}"
export CORE_ARTIFACT_ROOT="$ROOT"
export CORE_BUILD_DIR="${CORE_BUILD_DIR:-$ROOT/build/experiments}"
mkdir -p "$CORE_BUILD_DIR"
cd "$ROOT"
exec "${cmd[@]}"
