#!/bin/bash
# One-time setup on the GPU server: a venv with vLLM and the experiment's dependencies, all
# under $WORK. Usage: WORK=/data/<dir> bash scripts/server/setup_env.sh
set -euo pipefail
source "$(dirname "$0")/config.sh"
PY=${PYTHON:-python3}
"$PY" -c 'import sys; assert (3, 9) <= sys.version_info[:2] <= (3, 12), f"vLLM needs Python 3.9-3.12, got {sys.version}"'
[ -d "$VENV" ] || "$PY" -m venv "$VENV"
"$VENV/bin/pip" install -U pip
"$VENV/bin/pip" install vllm pandas openai python-dotenv huggingface_hub
"$VENV/bin/python" -c 'import vllm, torch; print("vllm", vllm.__version__, "torch", torch.__version__, "cuda", torch.cuda.is_available(), torch.cuda.device_count(), "GPUs")'
