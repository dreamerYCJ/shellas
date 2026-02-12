"""gather_context + retrieve_docs + plan_execution 三个节点"""
import json
from ..state import AgentState
from ...context.collector import ContextCollector
from ...rag.retriever import ShellRetriever
from ...rag.query_rewriter import rewrite_query
from ...llm.client import LLMClient
from ...llm.prompts import build_system_prompt, PLAN_PROMPT
from ...safety.guard import classify_risk

_collector = None
_retriever = None
_llm = None


def _get_collector():
    global _collector
    if _collector is None:
        _collector = ContextCollector()
    return _collector


def _get_retriever(platform="linux"):
    global _retriever
    if _retriever is None:
        _retriever = ShellRetriever(current_platform=platform)
    return _retriever


def _get_llm():
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def gather_context(state: AgentState) -> AgentState:
    collector = _get_collector()
    required = state.get("required_contexts", ["os_info", "user_info"])
    context = collector.collect(required)
    return {**state, "context": context}


def retrieve_docs(state: AgentState) -> AgentState:
    platform = state.get("context", {}).get("os_info", {}).get("system", "linux").lower()
    retriever = _get_retriever(platform)
    query = rewrite_query(state["user_input"])
    docs = retriever.search(query, top_k=5)
    return {**state, "retrieved_docs": docs}


def plan_execution(state: AgentState) -> AgentState:
    # print("\n[DEBUG] RAG 检索到的内容:")
    # print(state.get("retrieved_docs", "没有检索到任何内容"))
    # print("-" * 30 + "\n")

    llm = _get_llm()
    env_context = build_system_prompt(state.get("context", {}), state.get("retrieved_docs", ""))

    # 如果是重试，使用不同的prompt
    if state.get("error"):
        from ...llm.prompts import RETRY_PROMPT
        last = state["execution_results"][-1]
        feedback = ""
        if state.get("user_feedback") and state["user_feedback"] != "__abort__":
            feedback = f"用户补充: {state['user_feedback']}"
        prompt = RETRY_PROMPT.format(
            env_context=env_context,
            rag_docs=state.get("retrieved_docs", ""),
            user_input=state["user_input"],
            failed_command=last["command"],
            exit_code=last["exit_code"],
            stderr=last["stderr"],
            user_feedback=feedback,
        )
    else:
        prompt = PLAN_PROMPT.format(
            env_context=env_context,
            rag_docs=state.get("retrieved_docs", ""),
            user_input=state["user_input"],
        )

    raw = llm.chat_json("你是Shell命令规划器。", prompt)

    # 解析JSON
    try:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        plan = json.loads(raw)
        steps = plan.get("steps", [])
    except (json.JSONDecodeError, KeyError):
        steps = [{"step_id": 1, "description": "直接执行", "command": raw.strip(), "depends_on": []}]

    # 为第一步设置风险等级
    risk = "medium"
    if steps:
        risk = classify_risk(steps[state.get("current_step", 0)]["command"])

    return {
        **state,
        "execution_plan": steps,
        "current_step": state.get("current_step", 0),
        "risk_level": risk,
        "error": None,
    }
