"""gather_context + retrieve_docs + plan_execution 三个节点 — 两阶段RAG版本"""
import json
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
    context = collector.collect(required)
    return {**state, "context": context}


def retrieve_docs(state: AgentState) -> AgentState:
    """
    阶段一：智能RAG检索
    
    根据查询复杂度决定RAG策略：
    - explicit_command: 用户明确指定命令 → 只检索该命令的语法
    - simple query: 简单查询 → RAG作为弱参考或跳过
    - complex query: 复杂查询 → 提供候选命令列表
    """
    user_input = state["user_input"]
    platform = state.get("context", {}).get("os_info", {}).get("system", "linux").lower()
    retriever = _get_retriever(platform)

    # ---- 新增：拿到已安装工具集 ----
    installed_tools = state.get("context", {}).get("_all_tools", None)

    # 分析查询复杂度
    analysis = analyze_query_complexity(user_input)
    explicit_cmd = analysis.get("explicit_command")
    rag_mode = analysis.get("rag_mode", "candidates")

    rag_docs = ""
    target_command = None

    if explicit_cmd:
        # 用户明确指定了命令，只检索该命令的语法（阶段二前置）
        syntax_results = retriever.retrieve_by_command(explicit_cmd, top_k=3)
        if syntax_results:
            rag_docs = retriever.format_syntax_reference(syntax_results)
        target_command = explicit_cmd

    elif rag_mode == "weak_reference":
        query = rewrite_query(user_input)
        results = retriever.retrieve_by_intent(query, top_k=3)  # 改这里
        rag_docs = retriever.format_candidates(results)

    elif rag_mode in ("full", "candidates"):
        query = rewrite_query(user_input)
        results = retriever.retrieve_by_intent(query, top_k=5)  # 改这里
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
    else:
        prompt = PLAN_PROMPT.format(
            env_context=env_context,
            rag_docs=state.get("retrieved_docs", ""),
            user_input=state["user_input"],
        )

    raw = llm.chat_json("你是Shell命令规划器。", prompt)

    # ---- 改进的JSON解析 ----
    steps = None
    try:
        cleaned = raw.strip()
        # 去掉markdown代码块
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        plan = json.loads(cleaned)
        steps = plan.get("steps", [])
    except (json.JSONDecodeError, KeyError):
        pass

    # JSON解析失败：尝试提取单条命令，而不是把整个raw当命令
    if not steps:
        # 尝试从raw里找反引号包裹的命令
        import re
        cmds = re.findall(r'`([^`]+)`', raw)
        if cmds:
            steps = [{"step_id": i+1, "description": "", "command": c, "depends_on": []} for i, c in enumerate(cmds)]
        else:
            # 如果raw看起来像单条shell命令（不含换行不含{），作为命令用
            single_line = raw.strip().split("\n")[0].strip()
            if single_line and "{" not in single_line and len(single_line) < 200:
                steps = [{"step_id": 1, "description": "", "command": single_line, "depends_on": []}]
            else:
                # 真的解析不了，返回错误而不是把JSON当命令执行
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

    return {
        **state,
        "execution_plan": steps,
        "current_step": state.get("current_step", 0),
        "risk_level": risk,
        "error": None,
    }


def _handle_retry(state: AgentState, llm: LLMClient, context: dict) -> AgentState:
    """处理重试场景"""
    from ...llm.prompts import RETRY_PROMPT

    last = state["execution_results"][-1]
    failed_cmd = last["command"].split()[0]  # 提取命令名

    # 为失败的命令检索语法参考
    platform = context.get("os_info", {}).get("system", "linux").lower()
    retriever = _get_retriever(platform)
    syntax_results = retriever.retrieve_by_command(failed_cmd, top_k=3)
    syntax_docs = retriever.format_syntax_reference(syntax_results) if syntax_results else ""

    feedback = ""
    if state.get("user_feedback") and state["user_feedback"] != "__abort__":
        feedback = f"\n用户补充: {state['user_feedback']}"

    prompt = RETRY_PROMPT.format(
        env_context=build_env_context(context),
        user_input=state["user_input"],
        failed_command=last["command"],
        exit_code=last["exit_code"],
        stderr=last["stderr"],
        user_feedback=feedback,
        rag_docs=syntax_docs,
    )

    raw = llm.chat_json("你是Shell命令规划器。", prompt)
    steps = _parse_plan_json(raw)

    risk = "medium"
    if steps:
        risk = classify_risk(steps[0]["command"])

    return {
        **state,
        "execution_plan": steps,
        "current_step": 0,
        "risk_level": risk,
        "error": None,
    }


def _enhance_with_syntax(state: AgentState, steps: list[dict]) -> list[dict]:
    """
    阶段二：为已生成的命令补充语法验证
    
    这是可选的增强步骤，用于检查生成的命令是否有对应的文档
    如果有，可以进行语法校验（当前版本暂不实现复杂校验）
    """
    # 当前版本：直接返回，不做额外处理
    # 未来可以在这里添加：
    # 1. 检查命令是否存在于系统
    # 2. 语法格式校验
    # 3. 参数合理性检查
    return steps


def _parse_plan_json(raw: str) -> list[dict]:
    """解析LLM返回的JSON计划"""
    try:
        raw = raw.strip()
        # 移除markdown代码块标记
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        plan = json.loads(raw)
        steps = plan.get("steps", [])
        
        # 验证步骤格式
        valid_steps = []
        for step in steps:
            if isinstance(step, dict) and "command" in step:
                valid_steps.append({
                    "step_id": step.get("step_id", len(valid_steps) + 1),
                    "description": step.get("description", ""),
                    "command": step["command"],
                    "depends_on": step.get("depends_on", []),
                })
        return valid_steps

    except (json.JSONDecodeError, KeyError, TypeError):
        # 如果JSON解析失败，尝试提取命令
        raw = raw.strip()
        if raw:
            return [{
                "step_id": 1,
                "description": "直接执行",
                "command": raw,
                "depends_on": [],
            }]
        return []
