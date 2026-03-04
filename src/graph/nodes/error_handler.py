"""错误分类 + 重试 + 建议 + 用户反馈"""
from ..state import AgentState
from ...safety.guard import ERROR_STRATEGY


def classify_error_code(exit_code: int, stderr: str) -> str:
    s = stderr.lower()
    if exit_code in (126, 127):
        return "not_found"
    if "permission denied" in s:
        return "permission_denied"
    if "no space left" in s:
        return "resource_error"
    if any(k in s for k in ["syntax error", "invalid option", "unrecognized", "illegal option"]):
        return "syntax_error"
    if "timed out" in s or exit_code == 124:
        return "timeout"
    if any(k in s for k in ["no such file", "not found", "cannot stat"]):
        return "not_found"
    if "address already in use" in s:
        return "resource_error"
    return "unknown"


def classify_error_node(state: AgentState) -> AgentState:
    results = state.get("execution_results", [])
    last = results[-1] if results else {}
    etype = classify_error_code(last.get("exit_code", 1), last.get("stderr", ""))
    strategy = ERROR_STRATEGY.get(etype, ERROR_STRATEGY["unknown"])
    return {
        **state,
        "error_type": etype,
        "max_retries": strategy["max_retries"],
    }


def auto_retry(state: AgentState) -> AgentState:
    return {**state, "retry_count": state.get("retry_count", 0) + 1}


def suggest_fix(state: AgentState) -> AgentState:
    """权限/资源问题，给出建议不重试"""
    results = state.get("execution_results", [])
    last = results[-1] if results else {}
    etype = state.get("error_type", "unknown")

    suggestion = ""
    if etype == "permission_denied":
        cmd = last.get("command", "")
        suggestion = f"💡 权限不足。建议: sudo {cmd}"
    elif etype == "resource_error":
        suggestion = "💡 资源不足（磁盘/内存/端口）。请先释放资源后重试。"
    else:
        suggestion = f"💡 错误: {last.get('stderr', '').strip()}"

    return {**state, "final_response": suggestion}


def ask_user_feedback(state: AgentState) -> AgentState:
    """请求用户反馈"""
    from ...cli.display import ask_for_feedback
    results = state.get("execution_results", [])
    last = results[-1] if results else {}

    feedback = ask_for_feedback(
        command=last.get("command", ""),
        stderr=last.get("stderr", ""),
        correction_round=state.get("correction_rounds", 0) + 1,
    )

    if feedback is None or feedback.strip() == "":
        feedback = "__abort__"

    return {
        **state,
        "user_feedback": feedback,
        "correction_rounds": state.get("correction_rounds", 0) + 1,
    }
