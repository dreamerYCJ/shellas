# 🐚 ShellAgent — 环境感知的智能 Shell 执行代理

用自然语言操作 Linux，ShellAgent 自动理解你的意图、感知系统环境、生成并执行 Shell 命令。

## 功能特点

- **自然语言 → Shell 命令**：输入"查看谁在占用8080端口"，自动生成 `ss -tlnp | grep :8080`
- **环境感知**：自动采集操作系统、已安装工具、用户权限等信息，生成适配当前环境的命令
- **两阶段 RAG**：基于 tldr 文档的向量检索，提供命令语法参考和候选命令
- **三级安全防护**：高危命令拦截、中危命令确认、低危命令自动执行
- **智能纠错**：执行失败后自动分类错误并重试（最多3轮），支持用户补充反馈
- **纯本地部署**：全部在本地运行，不依赖云端 API

## 技术架构

```
用户输入 → 意图解析(LLM) → 环境采集 → RAG检索 → 命令规划(LLM) → 安全检查 → 执行 → 错误处理 → 输出
```

| 组件 | 技术选型 |
|------|---------|
| 推理模型 | Qwen2.5-Coder-14B-Instruct-AWQ |
| 推理引擎 | vLLM (OpenAI 兼容 API) |
| Embedding | BGE-base-zh-v1.5 |
| 向量数据库 | ChromaDB |
| 流程编排 | LangGraph |
| 终端UI | Rich |

## 环境要求

- **操作系统**: Linux (Ubuntu 20.04+ 推荐)
- **Python**: 3.10+
- **GPU**: NVIDIA GPU，显存 ≥ 12GB（推荐 16GB+）
- **CUDA**: 11.8 或 12.x
- **磁盘**: ≥ 20GB（模型 + 索引）

## 快速开始

### 第一步：克隆项目

```bash
git clone <你的仓库地址>
cd ShellAgent
```

### 第二步：创建虚拟环境并安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

如果需要 vLLM（GPU 服务器上）：

```bash
pip install vllm>=0.5.0
```

### 第三步：下载模型和数据

**方法一：使用 ModelScope（国内推荐）**

```bash
pip install modelscope
# 下载推理模型（约 8GB）
modelscope download --model Qwen/Qwen2.5-Coder-14B-Instruct-AWQ \
    --local_dir ./weights/Qwen/Qwen2.5-Coder-14B-Instruct-AWQ

# 下载 Embedding 模型（约 400MB）
modelscope download --model AI-ModelScope/bge-base-zh-v1.5 \
    --local_dir ./weights/bge-base-zh-v1.5
```

**方法二：使用脚本下载**

```bash
bash scripts/download_model.sh
```

### 第四步：解析 tldr 文档并构建向量索引

```bash
# 克隆 tldr 文档（如果还没有）
git clone --depth 1 https://github.com/tldr-pages/tldr.git ./data/tldr

# 解析为结构化 JSON
python scripts/parse_tldr.py

# 构建 ChromaDB 向量索引（需要 GPU）
python scripts/build_index.py
```

### 第五步：启动 vLLM 推理服务

新开一个终端：

```bash
source venv/bin/activate
bash scripts/start_vllm.sh
```

等待出现 `Uvicorn running on http://0.0.0.0:8000` 说明服务就绪。

**验证 vLLM 是否正常：**

```bash
curl http://localhost:8000/v1/models
```

### 第六步：运行 ShellAgent

```bash
python -m src
```

然后输入自然语言指令，例如：
- "查看磁盘使用情况"
- "谁在占用8080端口"
- "查看最近修改的文件"
- "把project目录打包压缩"

输入 `quit` 退出。

## 项目结构

```
ShellAgent/
├── config/
│   ├── model_config.yaml      # 模型和 vLLM 配置
│   ├── settings.yaml           # 项目配置
│   └── safety_rules.yaml       # 安全规则（风险正则）
├── src/
│   ├── cli/                    # 终端交互
│   │   ├── app.py              # 主入口
│   │   └── display.py          # Rich UI 组件
│   ├── context/                # 环境采集
│   │   └── collector.py        # 动态采集器
│   ├── graph/                  # LangGraph 工作流
│   │   ├── state.py            # 状态定义
│   │   ├── workflow.py         # 工作流编排
│   │   └── nodes/              # 各节点实现
│   │       ├── intent_parser.py
│   │       ├── context_planner.py
│   │       ├── planner.py
│   │       ├── executor.py
│   │       ├── output_parser.py
│   │       └── error_handler.py
│   ├── llm/                    # LLM 封装
│   │   ├── client.py           # vLLM 客户端
│   │   └── prompts.py          # Prompt 模板
│   ├── rag/                    # RAG 检索
│   │   ├── retriever.py        # 向量检索器
│   │   └── query_rewriter.py   # 查询改写
│   └── safety/                 # 安全模块
│       └── guard.py            # 风险分级
├── scripts/                    # 构建脚本
├── eval/                       # 评估基准
├── tests/                      # 测试
├── requirements.txt
└── pyproject.toml
```

## 安全机制

| 级别 | 处理 | 示例 |
|------|------|------|
| 🚫 高危 | 直接拦截 | `rm -rf /`、`mkfs.ext4 /dev/sda`、`dd if=/dev/zero of=/dev/sda` |
| ⚠️ 中危 | 用户确认 | `sudo apt update`、`kill -9 1234`、`systemctl restart nginx` |
| ⚡ 低危 | 自动执行 | `ls -la`、`df -h`、`ps aux`、`uname -a` |

## 运行测试

```bash
# 不需要 GPU 的测试（安全规则、Query改写、工作流）
pytest tests/test_safety.py tests/test_workflow.py tests/test_query_rewriter.py -v

# 需要 GPU + 索引的测试
pytest tests/test_rag.py -v
```

## 常见问题

**Q: vLLM 启动报 OOM？**
调低 `scripts/start_vllm.sh` 中的 `--gpu-memory-utilization`（如 0.5）或 `--max-model-len`（如 4096）。

**Q: 提示"工作流初始化失败"？**
检查 vLLM 是否已启动（`curl http://localhost:8000/v1/models`），以及向量索引是否已构建（`./data/chroma_db` 目录是否存在）。

**Q: Embedding 模型加载慢？**
首次启动需要加载 Embedding 模型到 GPU，后续会缓存。如果没有 GPU，修改 `config/model_config.yaml` 中 `embedding.device` 为 `"cpu"`。

**Q: 如何在无 GPU 的机器上测试？**
可以将 vLLM 部署在远程 GPU 服务器上，修改 `config/model_config.yaml` 中的 `base_url` 指向远程地址即可。
