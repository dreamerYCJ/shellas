#!/bin/bash
set -e

echo "📥 下载推理模型（Qwen2.5-Coder-14B-Instruct-AWQ）..."
mkdir -p ./weights
modelscope download --model Qwen/Qwen2.5-Coder-14B-Instruct-AWQ --local_dir ./weights/Qwen/Qwen2.5-Coder-14B-Instruct-AWQ

echo ""
echo "📥 下载Embedding模型（bge-base-zh-v1.5）..."
modelscope download --model AI-ModelScope/bge-base-zh-v1.5 --local_dir ./weights/bge-base-zh-v1.5

echo ""
echo "📥 克隆tldr文档..."
[ ! -d "./data/tldr" ] && git clone --depth 1 https://github.com/tldr-pages/tldr.git ./data/tldr

echo ""
echo "✅ 所有资源下载完成"
echo "   模型路径: ./weights/Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"
echo "   Embedding: ./weights/bge-base-zh-v1.5"
echo "   tldr文档:  ./data/tldr"
