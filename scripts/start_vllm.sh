#!/usr/bin/env bash
# Start the SILMA-9B vLLM server on port 8001.
# Run this inside WSL2. Requires: vllm installed, NVIDIA GPU, CUDA drivers.
#
# Usage:
#   bash scripts/start_vllm.sh
#   bash scripts/start_vllm.sh --gpu-memory-utilization 0.80   # override any flag

set -euo pipefail

MODEL="${VLLM_MODEL:-SILMA-AI/SILMA-9B-Instruct-v1}"
PORT="${VLLM_PORT:-8001}"

echo "Starting vLLM with model: $MODEL on port $PORT"

vllm serve "$MODEL" \
  --dtype bfloat16 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --port "$PORT" \
  "$@"
