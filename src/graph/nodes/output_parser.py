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

    # ---- 核心修复：判断是否是"正常的无结果" ----
    is_normal_empty = False

    # grep/egrep/fgrep 返回1 = 没匹配到，不是错误
    if exit_code == 1 and not stderr.strip():
        grep_cmds = ["grep", "egrep", "fgrep", "awk", "which", "command -v", "type"]
        if any(g in command for g in grep_cmds):
            is_normal_empty = True

    # diff 返回1 = 有差异，也是正常结果
    if exit_code == 1 and "diff" in command:
        is_normal_empty = True

    if exit_code == 0 or is_normal_empty:
        # 成功或正常无结果，推进下一步
        next_step = state["current_step"] + 1
        risk = "low"
        if next_step < len(state["execution_plan"]):
            from ...safety.guard import classify_risk
            risk = classify_risk(state["execution_plan"][next_step]["command"])

        # 如果是grep无结果，给stdout补一个说明
        if is_normal_empty and not stdout.strip():
            new_results = list(results)
            new_results[-1] = {**last, "stdout": "(无匹配结果)", "exit_code": 0}
            return {**state, "execution_results": new_results, "current_step": next_step, "risk_level": risk}

        return {**state, "current_step": next_step, "risk_level": risk}
    else:
        return {**state, "error": stderr or f"exit_code={exit_code}"}


def format_response(state: AgentState) -> AgentState:
    """汇总所有结果，生成最终响应"""
    results = state.get("execution_results", [])
    risk = state.get("risk_level", "")
    plan = state.get("execution_plan", [])

    parts = []

    # 如果被拦截
    if risk == "high" and not results:
        cmd = plan[0]["command"] if plan else "unknown"
        parts.append(f"🚫 高危命令已拦截: {cmd}")
        parts.append("该命令可能造成不可逆的系统损害，已拒绝执行。")
        return {**state, "final_response": "\n".join(parts)}

    # 如果被用户拒绝
    if state.get("needs_confirmation") is True:
        parts.append("⏹ 用户取消执行。")
        return {**state, "final_response": "\n".join(parts)}

    # 正常执行结果
    for r in results:
        status = "✅" if r["exit_code"] == 0 else "❌"
        parts.append(f"{status} $ {r['command']}")
        if r["stdout"].strip():
            # 限制输出长度
            out = r["stdout"].strip()
            if len(out) > 2000:
                out = out[:2000] + "\n... [输出截断]"
            parts.append(out)
        if r["exit_code"] != 0 and r["stderr"].strip():
            parts.append(f"错误: {r['stderr'].strip()}")

    # 如果有错误处理建议
    if state.get("error_type") == "permission_denied":
        parts.append("\n💡 建议: 尝试在命令前加 sudo")
    elif state.get("correction_rounds", 0) >= 3:
        parts.append("\n⚠️ 已达最大修正次数。建议手动调整或重新描述需求。")

    return {**state, "final_response": "\n".join(parts)}
