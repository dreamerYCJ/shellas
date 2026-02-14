"""所有Prompt模板 — 两阶段RAG版本"""

# ---- 意图解析 ----
INTENT_PROMPT = """你是一个意图分类器。根据用户输入判断属于以下哪个类别，只返回类别名:

类别: disk_ops, network, process, file_ops, service_mgmt, package_mgmt, log_analysis, config_check, general

用户输入: {user_input}

只返回一个类别名，不要解释。"""


# ---- 执行计划（主Prompt） ----
PLAN_PROMPT = """你是一个Shell命令规划器。根据用户需求和系统环境生成执行计划。

## 系统环境
{env_context}

## 用户需求
{user_input}
{rag_docs}

## 输出格式
返回JSON:
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

## 强制规则
1. **一条命令解决**。不要用管道拼接多个命令，除非用户明确需要复杂处理。举例：
   - 查是否安装 → which xxx（不要 dpkg -l | grep xxx）
   - 查端口占用 → ss -tlnp | grep :端口（不要先which再ss再lsof）
   - 查磁盘 → df -h（不要 df -h | grep | awk）
2. **只生成线性步骤**。禁止条件分支，禁止"如果A不行就用B"的逻辑
3. **不要检查工具是否安装**。已安装工具列表已提供，直接使用
4. **sudo规则**：如果用户标注为"无sudo权限"，禁止生成任何sudo命令
5. **只使用已安装工具或Linux内置命令**
6. **候选命令仅供参考**，优先用你认为最合适的标准命令

## 常用标准命令参考（含关键参数）
- 查看端口占用: ss -tlnp | grep :端口号  （-t TCP -l 监听 -n 数字 -p 显示进程PID，必须有-p才能看到进程）
- 查看进程: ps aux | grep 关键词
- 查看磁盘: df -h
- 查看内存: free -h
- 查看GPU: nvidia-smi
- 查找文件: find 路径 -name "模式" -type f
- 查看日志尾部: tail -n 行数 文件
- 系统信息: uname -a

只返回JSON，不要其他文字。"""


# ---- 带语法参考的执行计划 ----
PLAN_PROMPT_WITH_SYNTAX = """你是一个Shell命令规划器。根据用户需求和系统环境生成执行计划。

## 系统环境
{env_context}

## 用户需求
{user_input}

## 命令语法参考
{syntax_reference}

## 输出格式
返回JSON:
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

## 强制规则
1. 能一条命令解决就不要两条
2. 只生成线性步骤，禁止条件分支
3. 不要生成which/type等检测步骤
4. sudo规则：如果用户标注为"无sudo权限"，禁止生成sudo命令

参考上述语法生成正确的命令。只返回JSON。"""


# ---- 错误重试 ----
RETRY_PROMPT = """上次执行失败，请修正命令。

## 系统环境
{env_context}

## 原始需求
{user_input}

## 失败信息
- 命令: {failed_command}
- exit_code: {exit_code}
- 错误输出: {stderr}
{user_feedback}

## 语法参考
{rag_docs}

## 修正规则
1. 分析错误原因（命令不存在？语法错误？权限不足？）
2. 如果命令不存在，换用"已安装工具"中的替代命令
3. 如果权限不足且用户无sudo权限，换用不需要提权的命令
4. 修正后仍然遵守：一条命令解决、禁止条件分支、禁止which检测

返回修正后的JSON:
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


# ---- 动态系统提示构建 ----
def build_system_prompt(context: dict, rag_docs: str = "") -> str:
    """
    构建系统提示，包含环境信息

    优先级：系统环境 > 用户权限 > 已安装工具 > RAG参考
    """
    parts = ["你是一个Shell命令助手。根据系统环境生成准确命令。\n"]

    # 系统信息（高优先级）
    if "os_info" in context:
        info = context["os_info"]
        parts.append(f"## 系统信息")
        parts.append(f"- 发行版: {info['distro']}")
        parts.append(f"- 内核: {info['kernel']}")
        parts.append(f"- 架构: {info.get('arch', 'unknown')}")
        parts.append(f"- 包管理器: {info['pkg_mgr']}")

    # 用户信息 + sudo权限
    if "user_info" in context:
        u = context["user_info"]
        if u["is_root"]:
            perm = "root用户，拥有全部权限"
        elif u.get("has_sudo"):
            perm = "非root用户，有sudo权限（需要时可用sudo）"
        else:
            perm = "非root用户，无sudo权限（禁止生成sudo命令）"
        parts.append(f"\n## 用户信息")
        parts.append(f"- 当前用户: {u['user']}")
        parts.append(f"- 权限: {perm}")

    # 已安装工具（关键信息）
    if "installed_tools" in context:
        tools = context["installed_tools"]
        parts.append(f"\n## 已安装工具（只能使用这些工具或Linux内置命令）")
        parts.append(f"{', '.join(tools)}")

    # 当前目录
    if "cwd_files" in context:
        c = context["cwd_files"]
        parts.append(f"\n## 当前目录")
        parts.append(f"路径: {c['cwd']}")
        if c['files']:
            parts.append(f"文件: {', '.join(c['files'][:15])}" +
                        (f" ...等{len(c['files'])}个" if len(c['files']) > 15 else ""))

    # 其他上下文信息
    if "disk_usage" in context:
        parts.append(f"\n## 磁盘使用\n{context['disk_usage']}")

    if "port_usage" in context:
        parts.append(f"\n## 端口监听\n{context['port_usage']}")

    if "process_list" in context:
        parts.append(f"\n## 进程列表(Top20)\n{context['process_list']}")

    if "service_status" in context:
        parts.append(f"\n## 运行中的服务\n{context['service_status']}")

    if "network_info" in context:
        parts.append(f"\n## 网络配置\n{context['network_info']}")

    # 文件内容
    for k, v in context.items():
        if k.startswith("file_content:"):
            path = k.split(":", 1)[1]
            parts.append(f"\n## 文件内容: {path}\n{v}")

    # RAG文档（最低优先级）
    if rag_docs:
        parts.append(f"\n{rag_docs}")

    return "\n".join(parts)


def build_env_context(context: dict) -> str:
    """
    构建精简的环境上下文（用于重试等场景）
    """
    parts = []

    if "os_info" in context:
        info = context["os_info"]
        parts.append(f"系统: {info['distro']} | 内核: {info['kernel']} | 包管理: {info['pkg_mgr']}")

    if "user_info" in context:
        u = context["user_info"]
        sudo_info = ""
        if not u["is_root"]:
            sudo_info = " | sudo: " + ("有" if u.get("has_sudo") else "无")
        parts.append(f"用户: {u['user']} ({'root' if u['is_root'] else '非root'}{sudo_info})")

    if "installed_tools" in context:
        parts.append(f"已装工具: {', '.join(context['installed_tools'])}")

    if "cwd_files" in context:
        parts.append(f"当前目录: {context['cwd_files']['cwd']}")

    return "\n".join(parts)