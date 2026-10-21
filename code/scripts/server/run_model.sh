#!/bin/bash
# Serve one model, run every experiment against it (src.pipeline), stop the server.
# Usage: WORK=/data/<dir> [GPUS=0,1] nohup bash scripts/server/run_model.sh qwen2.5-7b [--p1] &
set -uo pipefail
source "$(dirname "$0")/config.sh"
name=$1; shift
IFS=$'\t' read -r _ _ _ _ maxtok extra < <(awk -F'\t' -v n="$name" '$1==n' "$(dirname "$0")/models.tsv")
# The previous model's server may still answer on the port while it shuts down; the readiness
# check below would then pass against it (10-01: qwen2.5-14b P1 ran against the exiting 32B
# server and every call failed). Wait until the port is free first.
for _ in $(seq 1 60); do curl -s -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null || break; sleep 5; done
bash "$(dirname "$0")/serve.sh" "$name" > "$LOGS/serve_$name.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null' EXIT
for _ in $(seq 1 180); do   # loading a 32B model can take several minutes
  curl -s -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null && break
  kill -0 $server 2>/dev/null || { echo "server died, see $LOGS/serve_$name.log"; exit 1; }
  sleep 10
done
cd "$CODE"
[ "$extra" = "-" ] && extra=""
LOCAL_BASE_URL="http://127.0.0.1:$PORT/v1" LOCAL_EXTRA_BODY="$extra" \
  "$VENV/bin/python" -m src.pipeline --model "local:$name" --workers 16 --max-tokens "$maxtok" "$@"
