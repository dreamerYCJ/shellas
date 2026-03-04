"""gather_context + retrieve_docs + plan_execution 三个节点 — 两阶段RAG版本"""
import json
import re
from ..state import AgentState
from ...context.collector import ContextCollector
from ...rag.retriever import ShellRetriever
from ...rag.query_rewriter import rewrite_query, analyze_query_complexity
from ...llm.client import LLMClient
from ...llm.prompts import (
    build_system_prompt,
    build_env_context,
    PLAN_PROMPT,
    PLAN_PROMPT_WITH_SYNTAX,
)
from ...safety.guard import classify_risk
from ...cli.display import spinner, print_context_plan, print_plan

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
    """采集系统环境信息"""
    collector = _get_collector()
    required = state.get("required_contexts", ["os_info", "user_info"])

    print_context_plan(required)
    with spinner("正在采集系统环境..."):
        context = collector.collect(required)

    return {**state, "context": context}


def retrieve_docs(state: AgentState) -> AgentState:
    """
    阶段一：智能RAG检索
    根据查询复杂度决定RAG策略
    """
    user_input = state["user_input"]
    platform = state.get("context", {}).get("os_info", {})
    if isinstance(platform, dict):
        platform = platform.get("system", "linux").lower()
    else:
        platform = "linux"
    retriever = _get_retriever(platform)

    installed_tools = state.get("context", {}).get("_all_tools", None)

    analysis = analyze_query_complexity(user_input)
    explicit_cmd = analysis.get("explicit_command")
    rag_mode = analysis.get("rag_mode", "candidates")

    rag_docs = ""
    target_command = None

    with spinner("正在检索命令参考..."):
        if explicit_cmd:
            syntax_results = retriever.retrieve_by_command(explicit_cmd, top_k=3)
            if syntax_results:
                rag_docs = retriever.format_syntax_reference(syntax_results)
            target_command = explicit_cmd
        elif rag_mode == "weak_reference":
            query = rewrite_query(user_input)
            results = retriever.retrieve_by_intent(query, top_k=3)
            rag_docs = retriever.format_candidates(results)
        elif rag_mode in ("full", "candidates"):
            query = rewrite_query(user_input)
            results = retriever.retrieve_by_intent(query, top_k=5)
            rag_docs = retriever.format_candidates(results)

    return {
        **state,
        "retrieved_docs": rag_docs,
        "target_command": target_command,
        "query_analysis": analysis,
    }


def plan_execution(state: AgentState) -> AgentState:
    llm = _get_llm()
    env_context = build_system_prompt(state.get("context", {}), state.get("retrieved_docs", ""))

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
        status_msg = "正在修正命令..."
    else:
        prompt = PLAN_PROMPT.format(
            env_context=env_context,
            rag_docs=state.get("retrieved_docs", ""),
            user_input=state["user_input"],
        )
        status_msg = "正在生成执行计划..."

    with spinner(status_msg):
        raw = llm.chat_json("你是Shell命令规划器。", prompt)

    # ---- 改进的JSON解析 ----
    steps = None
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        plan = json.loads(cleaned)
        steps = plan.get("steps", [])
    except (json.JSONDecodeError, KeyError):
        pass

    # JSON解析失败：尝试提取单条命令
    if not steps:
        cmds = re.findall(r'`([^`]+)`', raw)
        if cmds:
            steps = [{"step_id": i + 1, "description": "", "command": c, "depends_on": []}
                     for i, c in enumerate(cmds)]
        else:
            single_line = raw.strip().split("\n")[0].strip()
            if single_line and "{" not in single_line and len(single_line) < 200:
                steps = [{"step_id": 1, "description": "", "command": single_line, "depends_on": []}]
            else:
                return {
                    **state,
                    "execution_plan": [],
                    "current_step": 0,
                    "risk_level": "low",
                    "error": None,
                    "final_response": f"⚠️ 模型输出解析失败，请换个方式描述需求。\n原始输出: {raw[:200]}",
                }

    risk = "medium"
    if steps:
        risk = classify_risk(steps[state.get("current_step", 0)]["command"])

    # 显示执行计划
    print_plan(steps)

    return {
        **state,
        "execution_plan": steps,
        "current_step": state.get("current_step", 0),
        "risk_level": risk,
        "error": None,
    }
