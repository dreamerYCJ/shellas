"""LangGraph工作流定义"""
from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes.intent_parser import parse_intent
from .nodes.context_planner import plan_context
from .nodes.planner import gather_context, retrieve_docs, plan_execution
from .nodes.executor import execute_command
from .nodes.output_parser import parse_output, format_response
from .nodes.error_handler import (
    classify_error_node, auto_retry, suggest_fix, ask_user_feedback,
)


# ---- 路由函数 ----
def route_by_risk(state: AgentState) -> str:
    risk = state.get("risk_level", "medium")
    if risk == "high":
        return "blocked"
    if risk == "low":
        return "auto_execute"
    return "need_confirm"


def route_by_confirmation(state: AgentState) -> str:
    return "approved" if state.get("needs_confirmation") is False else "rejected"


def route_by_result(state: AgentState) -> str:
    results = state.get("execution_results", [])
    if not results:
        return "done"
    last = results[-1]
    if last.get("exit_code", 0) != 0:
        return "error"
    if state["current_step"] < len(state["execution_plan"]):
        return "next_step"
    return "done"


def route_by_error_type(state: AgentState) -> str:
    from ..safety.guard import ERROR_STRATEGY
    etype = state.get("error_type", "unknown")
    strategy = ERROR_STRATEGY.get(etype, ERROR_STRATEGY["unknown"])
    return strategy["action"]


def route_by_retry_count(state: AgentState) -> str:
    if state["retry_count"] < state["max_retries"]:
        return "retry"
    return "give_up"


def route_by_user_feedback(state: AgentState) -> str:
    if state["correction_rounds"] >= 3:
        return "max_rounds"
    if state.get("user_feedback") == "__abort__":
        return "user_abort"
    if state.get("user_feedback"):
        return "user_provided"
    return "user_abort"


# ---- 人工确认节点 ----
def human_confirm(state: AgentState) -> AgentState:
    step = state["execution_plan"][state["current_step"]]
    from ..cli.display import ask_confirmation
    approved = ask_confirmation(step["command"], state["risk_level"])
    return {**state, "needs_confirmation": not approved}


# ---- 构建Graph ----
def build_workflow():
    wf = StateGraph(AgentState)

    # 节点
    wf.add_node("parse_intent",    parse_intent)
    wf.add_node("plan_context",    plan_context)
    wf.add_node("gather_context",  gather_context)
    wf.add_node("retrieve_docs",   retrieve_docs)
    wf.add_node("plan_execution",  plan_execution)
    wf.add_node("safety_check",    lambda s: s)
    wf.add_node("human_confirm",   human_confirm)
    wf.add_node("execute_command", execute_command)
    wf.add_node("parse_output",    parse_output)
    wf.add_node("classify_error",  classify_error_node)
    wf.add_node("auto_retry",      auto_retry)
    wf.add_node("suggest_fix",     suggest_fix)
    wf.add_node("ask_user",        ask_user_feedback)
    wf.add_node("format_response", format_response)

    # 主链路
    wf.set_entry_point("parse_intent")
    wf.add_edge("parse_intent",    "plan_context")
    wf.add_edge("plan_context",    "gather_context")
    wf.add_edge("gather_context",  "retrieve_docs")
    wf.add_edge("retrieve_docs",   "plan_execution")
    wf.add_edge("plan_execution",  "safety_check")
    wf.add_edge("execute_command", "parse_output")
    wf.add_edge("suggest_fix",     "format_response")
    wf.add_edge("format_response", END)

    # 安全路由
    wf.add_conditional_edges("safety_check", route_by_risk, {
        "auto_execute": "execute_command",
        "need_confirm": "human_confirm",
        "blocked":      "format_response",
    })
    wf.add_conditional_edges("human_confirm", route_by_confirmation, {
        "approved": "execute_command",
        "rejected": "format_response",
    })

    # 执行结果路由
    wf.add_conditional_edges("parse_output", route_by_result, {
        "next_step": "safety_check",
        "done":      "format_response",
        "error":     "classify_error",
    })

    # 错误处理路由
    wf.add_conditional_edges("classify_error", route_by_error_type, {
        "auto_retry":  "auto_retry",
        "suggest_fix": "suggest_fix",
        "ask_user":    "ask_user",
    })
    wf.add_conditional_edges("auto_retry", route_by_retry_count, {
        "retry":   "plan_execution",
        "give_up": "ask_user",
    })
    wf.add_conditional_edges("ask_user", route_by_user_feedback, {
        "user_provided": "plan_execution",
        "user_abort":    "format_response",
        "max_rounds":    "format_response",
    })

    return wf.compile()
