#!/bin/bash
# Download the OLMo-2-7B *base* model (fp32 safetensors, ~29 GB) into the HF cache.
# Resumable: re-running continues where it stopped. Writes results/logs/download.{done,failed}.
set -u
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
EXP=${EXP:-$(cd "$SCRIPT_DIR/../.." && pwd)}
MLXPY=${MLXPY:-python3}
LOG=$EXP/build/logs
# hf-mirror is domestic: connect directly (the local proxy dropped out on 09-28 and killed
# the download), and use plain HTTP transfers -- the mirror does not serve the Xet protocol.
export HF_ENDPOINT=${HF_ENDPOINT:-https://hf-mirror.com} HF_HUB_DISABLE_XET=1
unset HTTPS_PROXY HTTP_PROXY https_proxy http_proxy ALL_PROXY all_proxy
rm -f "$LOG/download.failed"
echo "[$(date '+%m-%d %H:%M:%S')] download start ($HF_ENDPOINT, direct)"
for attempt in $(seq 1 20); do
  if env -u PYTHONPATH "$MLXPY" -c "
from huggingface_hub import snapshot_download
p = snapshot_download('allenai/OLMo-2-1124-7B', allow_patterns=['*.json', '*.safetensors', '*.txt'])
print('saved to', p)
"; then
    echo "[$(date '+%m-%d %H:%M:%S')] download done"; touch "$LOG/download.done"; exit 0
  fi
  echo "[$(date '+%m-%d %H:%M:%S')] attempt $attempt failed, retrying in 60s"; sleep 60
done
touch "$LOG/download.failed"; exit 1
