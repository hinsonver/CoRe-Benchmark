#!/bin/bash
# P2 on given tables only, for the open models, with the settings of their first runs
# (models.tsv max_tokens, 16 workers, --spread). Calls src.probe_clean directly, so no other
# table is touched; answers already cached for an unchanged prompt are reused.
#   SEEDED  tables for models with seed runs; MAIN  tables for OLMo-2 (no seed runs)
#   WAIT_FOR  a log line to wait for first (e.g. the end of a P1 queue)
# Models as name or name:tp. OLMo-2 is served with VLLM_USE_AOT_COMPILE=0: since 10-01 its
# AOT compile fails ("Source mismatch for collections.abc") with the same versions as on 09-30.
# A server that fails to start (shared GPUs) is retried twice, 10 minutes apart.
# Usage: WORK=/path/to/work SEEDED="..." MAIN="..." [WAIT_FOR="file:pattern"] setsid nohup bash \
#          scripts/server/rerun_tables.sh qwen2.5-7b qwen2.5-14b:4 olmo2-7b > $WORK/logs/x.log 2>&1 < /dev/null &
set -uo pipefail
source "$(dirname "$0")/config.sh"
here=$(cd "$(dirname "$0")" && pwd)
if [ -n "${WAIT_FOR:-}" ]; then
  until grep -qE "${WAIT_FOR#*:}" "${WAIT_FOR%%:*}" 2>/dev/null; do sleep 120; done
fi
while pgrep -f "src.pipeline --model local:" >/dev/null; do sleep 60; done

for item in "$@"; do
  name=${item%%:*}; tp=""; [ "$item" != "$name" ] && tp=${item#*:}
  tables=$SEEDED; aot=""
  if [ "$name" = olmo2-7b ]; then tables=$MAIN; aot=0; fi
  IFS=$'\t' read -r _ _ _ _ maxtok extra < <(awk -F'\t' -v n="$name" '$1==n' "$here/models.tsv")
  [ "$extra" = "-" ] && extra=""
  up=0
  for try in 1 2 3; do
    for _ in $(seq 1 60); do curl -s -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null || break; sleep 5; done
    echo "$(date '+%m-%d %H:%M') start $name tp=${tp:-default} ($tables), try $try"
    # only OLMo-2 gets the variable: an empty value would turn AOT compile off for the others too
    if [ -n "$aot" ]; then
      TP=$tp VLLM_USE_AOT_COMPILE=$aot bash "$here/serve.sh" "$name" > "$LOGS/serve_$name.log" 2>&1 &
    else
      TP=$tp bash "$here/serve.sh" "$name" > "$LOGS/serve_$name.log" 2>&1 &
    fi
    server=$!
    for _ in $(seq 1 180); do
      curl -s -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null && { up=1; break; }
      kill -0 $server 2>/dev/null || break
      sleep 10
    done
    [ $up = 1 ] && break
    kill $server 2>/dev/null; wait $server 2>/dev/null
    sleep 600
  done
  if [ $up = 1 ]; then
    (cd "$CODE" && LOCAL_BASE_URL="http://127.0.0.1:$PORT/v1" LOCAL_EXTRA_BODY="$extra" \
      "$VENV/bin/python" -m src.probe_clean --model "local:$name" --dataset $tables --spread \
      --workers 16 --max-tokens "$maxtok") > "$LOGS/rerun_tables_$name.log" 2>&1
    rc=$?   # before $(date ...), which resets $?
    echo "$(date '+%m-%d %H:%M') end $name exit $rc, failed calls: $(grep -c 'call failed' "$LOGS/rerun_tables_$name.log")"
  else
    echo "$(date '+%m-%d %H:%M') FAIL $name: server did not start, see $LOGS/serve_$name.log"
  fi
  kill $server 2>/dev/null; wait $server 2>/dev/null
done
echo "$(date '+%m-%d %H:%M') rerun_tables all done"
