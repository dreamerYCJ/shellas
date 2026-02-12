"""输出解析 + 响应格式化"""
from ..state import AgentState
from ...safety.guard import classify_risk


def parse_output(state: AgentState) -> AgentState:
    """解析执行结果，推进current_step"""
    results = state.get("execution_results", [])
    last = results[-1] if results else {}

    if last.get("exit_code", 0) == 0:
        # 成功，推进到下一步
        next_step = state["current_step"] + 1
        # 设置下一步的风险等级
        risk = "low"
        if next_step < len(state["execution_plan"]):
            risk = classify_risk(state["execution_plan"][next_step]["command"])
        return {**state, "current_step": next_step, "risk_level": risk}
    else:
        # 失败
        return {**state, "error": last.get("stderr", "Unknown error")}


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
