#!/bin/bash
MODEL="./weights/Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"
echo "🚀 Starting vLLM with $MODEL ..."
vllm serve "$MODEL" \
  --host 0.0.0.0 --port 8000 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.85 \
  --quantization awq
