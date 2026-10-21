#!/bin/bash
# P1 (row continuation) on the OLMo-2-7B *base* model, converted to MLX 4-bit on 09-28.
# Base models are the proper memorization test (no instruction tuning suppressing verbatim
# recall). Movies is left out: its long prompts pushed the 16 GB M1 into Metal OOM before.
# Progress: results/logs/base_p1.log   Stop: kill "$(cat results/logs/base_p1.pid)"
set -u
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
EXP=${EXP:-$(cd "$SCRIPT_DIR/../.." && pwd)}
MLXPY=${MLXPY:-python3}
BASE=$EXP/models/OLMo-2-1124-7B-mlx-4bit
LOG=$EXP/build/logs
cd "$EXP" || exit 1
echo $$ > "$LOG/base_p1.pid"
say() { echo "[$(date '+%m-%d %H:%M:%S')] $*"; }

start_server() {
  lsof -ti :8080 | xargs kill 2>/dev/null; sleep 3
  env -u PYTHONPATH "$MLXPY" -m mlx_lm.server --model "$BASE" --host 127.0.0.1 --port 8080 \
    --prompt-cache-size 1 \
    >> "$LOG/server_base.log" 2>&1 &
  echo $! > "$LOG/server.pid"
  for _ in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:8080/v1/models >/dev/null && break; sleep 3; done
}

# Each run gets a fresh server. If the server dies (Metal OOM), the probe aborts after 3 failed
# calls; restart and resume, since answered rows come back from the response cache.
for ds in hospital flights beers rayyan tax; do
  for src in clean dirty; do
    for attempt in 1 2 3; do
      start_server
      LOCAL_BASE_URL=http://127.0.0.1:8080/v1 .venv/bin/python -m src.probe_rowcont \
        --model "localbase:$BASE" --dataset "$ds" --source "$src" --n 50 \
        >> "$LOG/probe_summaries_base.jsonl" 2>> "$LOG/probe_errors_base.log"
      rc=$?
      say "$ds $src attempt $attempt (exit $rc)"
      [ $rc -eq 0 ] && break
    done
  done
done
lsof -ti :8080 | xargs kill 2>/dev/null
say "base-model P1 finished"
