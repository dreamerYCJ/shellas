#!/bin/bash
set -e

MODEL="./weights/Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"

if [ ! -d "$MODEL" ]; then
    echo "❌ 模型未找到: $MODEL"
    echo "   请先运行: bash scripts/download_model.sh"
    exit 1
fi

echo "🚀 Starting vLLM with $MODEL ..."
vllm serve "$MODEL" \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.6 \
    --quantization awq
