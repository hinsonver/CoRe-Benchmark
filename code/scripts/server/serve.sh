#!/bin/bash
# Start a vLLM OpenAI-compatible server for one model from models.tsv, in the foreground.
# GPUs are shared with other users: unless GPUS is set (e.g. GPUS=2,3), the TP cards with the
# most free memory are used, and vLLM may take only what is free now minus a 2 GB margin.
# Usage: WORK=/data/<dir> [GPUS=0,1] [TP=4] bash scripts/server/serve.sh qwen2.5-7b
set -euo pipefail
source "$(dirname "$0")/config.sh"
name=$1
IFS=$'\t' read -r _ repo tp maxlen _ _ < <(awk -F'\t' -v n="$name" '$1==n' "$(dirname "$0")/models.tsv")
tp=${TP:-$tp}   # e.g. TP=4 when others leave too little free memory for the default split
if [ -z "${GPUS:-}" ]; then
  GPUS=$(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits | sort -t, -k2 -nr | head -n "$tp" | cut -d, -f1 | tr -d ' ' | paste -sd, -)
fi
util=$(nvidia-smi --query-gpu=index,memory.free,memory.total --format=csv,noheader,nounits | \
  awk -F', ' -v g=",$GPUS," 'index(g, ","$1",") {u=($2-2048)/$3; if (m=="" || u<m) m=u} END {m=int(m*100)/100; if (m>0.9) m=0.9; print m}')
echo "model=$name gpus=$GPUS tp=$tp max_model_len=$maxlen gpu_memory_utilization=$util"
export CUDA_VISIBLE_DEVICES=$GPUS
exec "$VENV/bin/vllm" serve "$MODELS/$name" --served-model-name "$name" --host 127.0.0.1 --port "$PORT" \
  --tensor-parallel-size "$tp" --max-model-len "$maxlen" --gpu-memory-utilization "$util" \
  --max-num-seqs 16 ${VLLM_EXTRA:-}  # e.g. VLLM_EXTRA=--enforce-eager when torch.compile fails
