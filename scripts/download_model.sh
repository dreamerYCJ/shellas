#!/bin/bash
echo "📥 下载推理模型..."
huggingface-cli download Qwen/Qwen2.5-Coder-14B-Instruct-AWQ

echo "📥 下载Embedding模型..."
huggingface-cli download BAAI/bge-base-zh-v1.5

echo "📥 克隆tldr..."
[ ! -d "./data/tldr" ] && git clone --depth 1 https://github.com/tldr-pages/tldr.git ./data/tldr

echo "✅ 完成"
