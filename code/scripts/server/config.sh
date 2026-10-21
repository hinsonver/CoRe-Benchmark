# Shared settings for the GPU server scripts. Source it: `source scripts/server/config.sh`.
# The system disk (/) of the server is full, so EVERYTHING (venv, pip/HF caches, temp files,
# model weights, code) lives under $WORK on the data disk. Set WORK before use, e.g.
#   export WORK=/data/<your directory>
: "${WORK:?set WORK to the working directory on the data disk}"
export CODE="$WORK/core"                 # the experiment code (pushed from the Mac by push.sh)
export VENV="$WORK/venv"
export MODELS="$WORK/models"
export LOGS="$WORK/logs"
export HF_HOME="$WORK/hf_cache"
export PIP_CACHE_DIR="$WORK/pip_cache"
export TMPDIR="$WORK/tmp"                # /tmp is on the full system disk
export XDG_CACHE_HOME="$WORK/cache"      # vLLM, triton, torch compile caches
export VLLM_CACHE_ROOT="${VLLM_CACHE_ROOT:-$WORK/cache/vllm}"   # can be set to a fresh directory
export FLASHINFER_WORKSPACE_BASE="$WORK/cache"  # FlashInfer JIT cache (default: ~/.cache, system disk)
# The system CUDA toolkit is 12.2, whose nvcc rejects FlashInfer's flags (it JIT-builds for
# CUDA 13). Probes decode greedily (temperature 0), so use PyTorch's sampler: nothing to build.
export VLLM_USE_FLASHINFER_SAMPLER=0
export HF_ENDPOINT="https://hf-mirror.com"
export HF_HUB_DISABLE_XET=1              # the mirror does not serve xet
export PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
export PORT="${PORT:-8000}"
mkdir -p "$MODELS" "$LOGS" "$HF_HOME" "$PIP_CACHE_DIR" "$TMPDIR" "$XDG_CACHE_HOME"
