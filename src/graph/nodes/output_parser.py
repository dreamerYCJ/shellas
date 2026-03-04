"""输出解析 + 响应格式化"""
from ..state import AgentState
from ...safety.guard import classify_risk


def parse_output(state: AgentState) -> AgentState:
    results = state.get("execution_results", [])
    last = results[-1] if results else {}
    exit_code = last.get("exit_code", 0)
    command = last.get("command", "")
    stdout = last.get("stdout", "")
    stderr = last.get("stderr", "")

    is_normal_nonzero = False

    # grep/awk/which 返回 1 = 没匹配到，不是错误
    if exit_code == 1 and not stderr.strip():
        grep_cmds = ["grep", "egrep", "fgrep", "awk", "which", "command -v", "type"]
        if any(g in command for g in grep_cmds):
            is_normal_nonzero = True

    # diff 返回 1 = 有差异，是正常结果
    if exit_code == 1 and "diff" in command:
        is_normal_nonzero = True

    # systemctl is-active/is-enabled/status 返回非零但有 stdout = 正常查询结果
    # is-active 返回 3（inactive）、is-enabled 返回 1（disabled）都是合法答案
    if exit_code != 0 and stdout.strip() and not stderr.strip():
        systemctl_queries = ["systemctl is-active", "systemctl is-enabled",
                             "systemctl status", "systemctl show"]
        if any(sq in command for sq in systemctl_queries):
            is_normal_nonzero = True

    # 通用规则：查询类命令如果有 stdout 且无 stderr，大概率是正常结果
    # 覆盖 curl --silent 返回非零、python --version 输出到 stderr 等边界情况
    if exit_code != 0 and stdout.strip() and not stderr.strip():
        query_cmds = ["--version", "is-active", "is-enabled", "test -"]
        if any(q in command for q in query_cmds):
            is_normal_nonzero = True

    if exit_code == 0 or is_normal_nonzero:
        next_step = state["current_step"] + 1
        risk = "low"
        if next_step < len(state["execution_plan"]):
            risk = classify_risk(state["execution_plan"][next_step]["command"])

        # 修正 exit_code 让后续格式化输出显示 ✅ 而不是 ❌
        if is_normal_nonzero:
            new_results = list(results)
            new_results[-1] = {**last, "exit_code": 0}
            if not stdout.strip():
                new_results[-1]["stdout"] = "(无匹配结果)"
            return {**state, "execution_results": new_results,
                    "current_step": next_step, "risk_level": risk}

        return {**state, "current_step": next_step, "risk_level": risk}
    else:
        return {**state, "error": stderr or f"exit_code={exit_code}"}


def format_response(state: AgentState) -> AgentState:
    """汇总所有结果，生成最终响应"""
    results = state.get("execution_results", [])
    risk = state.get("risk_level", "")
    plan = state.get("execution_plan", [])

    # 如果已有 final_response（如解析失败），直接返回
    if state.get("final_response"):
        return state

    parts = []

    if risk == "high" and not results:
        cmd = plan[0]["command"] if plan else "unknown"
        parts.append(f"🚫 高危命令已拦截: {cmd}")
        parts.append("该命令可能造成不可逆的系统损害，已拒绝执行。")
        return {**state, "final_response": "\n".join(parts)}

    if state.get("needs_confirmation") is True:
        parts.append("⏹ 用户取消执行。")
        return {**state, "final_response": "\n".join(parts)}

    for r in results:
        status = "✅" if r["exit_code"] == 0 else "❌"
        parts.append(f"{status} $ {r['command']}")
        if r["stdout"].strip():
            out = r["stdout"].strip()
            if len(out) > 2000:
                out = out[:2000] + "\n... [输出截断]"
            parts.append(out)
        if r["exit_code"] != 0 and r["stderr"].strip():
            parts.append(f"错误: {r['stderr'].strip()}")

    if state.get("error_type") == "permission_denied":
        parts.append("\n💡 建议: 尝试在命令前加 sudo")
    elif state.get("correction_rounds", 0) >= 3:
        parts.append("\n⚠️ 已达最大修正次数。建议手动调整或重新描述需求。")

    return {**state, "final_response": "\n".join(parts)}
