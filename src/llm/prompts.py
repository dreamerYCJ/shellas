"""所有Prompt模板"""

# ---- 意图解析 ----
INTENT_PROMPT = """你是一个意图分类器。根据用户输入判断属于以下哪个类别，只返回类别名:

类别: disk_ops, network, process, file_ops, service_mgmt, package_mgmt, log_analysis, config_check, general

用户输入: {user_input}

只返回一个类别名，不要解释。"""


# ---- 执行计划 ----
PLAN_PROMPT = """你是一个Shell命令规划器。根据用户需求、环境信息和参考文档，生成执行计划。

{env_context}

{rag_docs}

用户需求: {user_input}

返回JSON格式:
{{
  "steps": [
    {{
      "step_id": 1,
      "description": "步骤说明",
      "command": "具体命令",
      "depends_on": []
    }}
  ]
}}

规则:
1. 使用当前系统实际存在的工具和语法
2. 非root用户需要提权时加sudo
3. 路径使用绝对路径或基于当前目录的相对路径
4. 优先参考"相关命令参考"中的语法
5. 只返回JSON，不要其他文字"""


# ---- 错误重试 ----
RETRY_PROMPT = """上次执行失败，请修正命令。

{env_context}

{rag_docs}

原始需求: {user_input}
失败命令: {failed_command}
exit_code: {exit_code}
stderr: {stderr}
{user_feedback}

分析错误原因，返回修正后的JSON:
{{
  "steps": [
    {{
      "step_id": 1,
      "description": "修正说明",
      "command": "修正后的命令",
      "depends_on": []
    }}
  ]
}}

只返回JSON。"""


# ---- 动态系统提示 ----
def build_system_prompt(context: dict, rag_docs: str) -> str:
    parts = ["你是一个Shell命令助手。根据环境和参考文档生成准确命令。\n"]

    if "os_info" in context:
        info = context["os_info"]
        parts.append(f"系统: {info['distro']} | 内核: {info['kernel']} | 包管理: {info['pkg_mgr']}")
    if "user_info" in context:
        u = context["user_info"]
        parts.append(f"用户: {u['user']} ({'root' if u['is_root'] else '非root'})")
    if "cwd_files" in context:
        c = context["cwd_files"]
        parts.append(f"当前目录: {c['cwd']}")
        parts.append(f"目录文件: {', '.join(c['files'][:20])}")
    if "disk_usage" in context:
        parts.append(f"磁盘:\n{context['disk_usage']}")
    if "port_usage" in context:
        parts.append(f"端口:\n{context['port_usage']}")
    if "process_list" in context:
        parts.append(f"进程(Top20):\n{context['process_list']}")
    if "service_status" in context:
        parts.append(f"服务:\n{context['service_status']}")
    if "network_info" in context:
        parts.append(f"网络:\n{context['network_info']}")
    if "installed_tools" in context:
        parts.append(f"已安装工具: {', '.join(context['installed_tools'])}")

    for k, v in context.items():
        if k.startswith("file_content:"):
            path = k.split(":", 1)[1]
            parts.append(f"\n文件 {path}:\n{v}")

    if rag_docs:
        parts.append(f"\n{rag_docs}")

    parts.append("\n要求: 使用该系统实际存在的工具和正确语法。非root需提权时加sudo。")
    return "\n".join(parts)
