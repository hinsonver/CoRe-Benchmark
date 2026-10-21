#!/bin/bash
# Run several models one after another (run_model.sh each), starting each only once its download
# is complete: no `hf download` still writing to its directory, and every weight shard present.
# name:tp overrides the tensor-parallel size from models.tsv for that model.
# PIPELINE_ARGS is passed on to src.pipeline, e.g. "--datasets hospital movies --no-near" to redo
# only those (cached answers are reused, so only changed tables cost GPU time).
# Usage: WORK=/data/<dir> [PIPELINE_ARGS="..."] nohup bash scripts/server/queue.sh qwen2.5-14b:4 \
#          qwen2.5-32b-awq:4 llama3.1-8b > $WORK/logs/queue.log 2>&1 &
set -uo pipefail
source "$(dirname "$0")/config.sh"
here=$(cd "$(dirname "$0")" && pwd)

ready() {  # all shards of $MODELS/$1 on disk and no download writing there
  local d="$MODELS/$1"
  pgrep -f "local-dir $d --" >/dev/null && return 1
  [ -f "$d/config.json" ] || return 1
  if [ -f "$d/model.safetensors.index.json" ]; then
    "$VENV/bin/python" -c 'import json, os, sys; d = sys.argv[1]
m = json.load(open(d + "/model.safetensors.index.json"))["weight_map"]
sys.exit(0 if all(os.path.exists(os.path.join(d, f)) for f in set(m.values())) else 1)' "$d"
  else
    [ -f "$d/model.safetensors" ]
  fi
}

for item in "$@"; do
  name=${item%%:*}; tp=""; [ "$item" != "$name" ] && tp=${item#*:}
  for _ in $(seq 1 720); do ready "$name" && break; sleep 30; done   # wait up to 6 h
  if ! ready "$name"; then echo "$(date '+%m-%d %H:%M') skip $name: download incomplete"; continue; fi
  echo "$(date '+%m-%d %H:%M') start $name tp=${tp:-default}"
  TP=$tp bash "$here/run_model.sh" "$name" ${PIPELINE_ARGS:-} > "$LOGS/run_$name.log" 2>&1
  rc=$?   # before $(date ...) below, which resets $? (the logs said "exit 0" for failed runs until 10-02)
  echo "$(date '+%m-%d %H:%M') end $name exit $rc"
done
