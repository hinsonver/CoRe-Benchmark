#!/bin/bash
# Local OLMo-2 pipeline (runs detached; survives the Claude session):
#   1. P1 probes on OLMo-2-7B-Instruct-4bit (anon, named, dirty error-rows) via mlx_lm.server
#   2. wait for the base-model download (scripts/olmo_download.sh) to finish
#   3. stop the server to free memory, convert allenai/OLMo-2-1124-7B to MLX 4-bit, smoke-test it
# Progress: results/logs/pipeline.log   Stop: kill "$(cat results/logs/pipeline.pid)"
set -u
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
EXP=${EXP:-$(cd "$SCRIPT_DIR/../.." && pwd)}
MLXPY=${MLXPY:-python3}
INSTRUCT=mlx-community/OLMo-2-1124-7B-Instruct-4bit
BASE_OUT=$EXP/models/OLMo-2-1124-7B-mlx-4bit
LOG=$EXP/build/logs
cd "$EXP" || exit 1
echo $$ > "$LOG/pipeline.pid"
say() { echo "[$(date '+%m-%d %H:%M:%S')] $*"; }

start_server() {
  if ! curl -s -m 3 http://127.0.0.1:8080/v1/models >/dev/null; then
    say "starting mlx_lm.server"
    env -u PYTHONPATH "$MLXPY" -m mlx_lm.server --model "$INSTRUCT" --host 127.0.0.1 --port 8080 \
      > "$LOG/server.log" 2>&1 &
    echo $! > "$LOG/server.pid"
    for _ in $(seq 1 60); do curl -s -m 2 http://127.0.0.1:8080/v1/models >/dev/null && break; sleep 3; done
  fi
}

# movies_1 is left out of the local pilot: its ~2000-token prompts drove mlx_lm.server into a
# Metal out-of-memory state on the 16 GB M1 twice on 09-28 (the server then hangs).
DATASETS="hospital flights beers rayyan tax"

probe() {
  say "probe start: $*"
  for ds in $DATASETS; do
    LOCAL_BASE_URL=http://127.0.0.1:8080/v1 .venv/bin/python -m src.probe_rowcont \
      --model "local:$INSTRUCT" --dataset "$ds" --n 50 "$@" >> "$LOG/probe_summaries.jsonl" 2>> "$LOG/probe_errors.log"
    say "  $ds done (exit $?)"
  done
}

restart_server() {
  [ -f "$LOG/server.pid" ] && kill "$(cat "$LOG/server.pid")" 2>/dev/null
  lsof -ti :8080 | xargs kill 2>/dev/null
  sleep 5
  start_server
}

# Local pilot, trimmed on 09-28: n=50 and no --named run (on DeepSeek naming the dataset
# changed nothing). The server is restarted between runs to release memory.
start_server
probe
restart_server
probe --source dirty --error-rows

say "waiting for base-model download"
while [ ! -f "$LOG/download.done" ]; do
  [ -f "$LOG/download.failed" ] && { say "download failed; skipping conversion"; exit 1; }
  sleep 60
done

say "stopping server to free memory for conversion"
[ -f "$LOG/server.pid" ] && kill "$(cat "$LOG/server.pid")" 2>/dev/null
lsof -ti :8080 | xargs kill 2>/dev/null
sleep 5

if [ -d "$BASE_OUT" ]; then
  say "conversion output already exists: $BASE_OUT"
else
  say "converting allenai/OLMo-2-1124-7B -> $BASE_OUT (4-bit)"
  env -u PYTHONPATH "$MLXPY" -m mlx_lm.convert --hf-path allenai/OLMo-2-1124-7B \
    -q --q-bits 4 --mlx-path "$BASE_OUT" >> "$LOG/convert.log" 2>&1
  say "conversion exit $?"
fi

say "smoke test"
env -u PYTHONPATH "$MLXPY" -m mlx_lm.generate --model "$BASE_OUT" --max-tokens 40 \
  --prompt "index,ProviderNumber,HospitalName,City,State
1,10018,callahan eye foundation hospital,birmingham,al
2," >> "$LOG/convert.log" 2>&1
say "pipeline finished (exit $?)"
