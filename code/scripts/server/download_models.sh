#!/bin/bash
# Download models listed in models.tsv through hf-mirror. Usage:
#   WORK=/data/<dir> bash scripts/server/download_models.sh qwen2.5-7b olmo2-7b   (names from models.tsv)
set -uo pipefail
source "$(dirname "$0")/config.sh"
for name in "$@"; do
  repo=$(awk -F'\t' -v n="$name" '$1==n {print $2}' "$(dirname "$0")/models.tsv")
  [ -n "$repo" ] || { echo "unknown model $name"; continue; }
  for try in 1 2 3 4 5; do
    # huggingface_hub >= 1.0: `hf download`, one --exclude per pattern (bare extra arguments
    # would be read as the only file names to fetch)
    "$VENV/bin/hf" download "$repo" --local-dir "$MODELS/$name" \
      --exclude "*.pth" --exclude "original/*" --exclude "metal/*" && break
    echo "retry $try for $name"; sleep 20
  done
  du -sh "$MODELS/$name"
done
