"""工作流集成测试（不需要LLM和向量库）"""
import pytest
from src.graph.state import AgentState
from src.graph.nodes.context_planner import plan_context, INTENT_CONTEXT_MAP
from src.graph.nodes.error_handler import classify_error_code


def _make_state(user_input: str, **kwargs) -> AgentState:
    base = AgentState(
        user_input=user_input, intent="", required_contexts=[], context={},
        retrieved_docs="", target_command=None, query_analysis=None,
        execution_plan=[], current_step=0,
        execution_results=[], risk_level="", needs_confirmation=False,
        error=None, error_type=None, retry_count=0, max_retries=0,
        user_feedback=None, correction_rounds=0, final_response="",
    )
    base.update(kwargs)
    return base


def test_plan_context_disk():
    state = _make_state("磁盘满了", intent="disk_ops")
    result = plan_context(state)
    assert "disk_usage" in result["required_contexts"]
    assert "os_info" in result["required_contexts"]


def test_plan_context_network():
    state = _make_state("端口被占了", intent="network")
    result = plan_context(state)
    assert "port_usage" in result["required_contexts"]


def test_plan_context_fallback():
    state = _make_state("随便说点什么", intent="unknown_intent")
    result = plan_context(state)
    assert "os_info" in result["required_contexts"]


def test_plan_context_all_have_tools():
    """所有意图都应包含 installed_tools"""
    for intent, contexts in INTENT_CONTEXT_MAP.items():
        assert "installed_tools" in contexts, f"{intent} 缺少 installed_tools"


# ---- 错误分类测试 ----
def test_error_classify_permission():
    assert classify_error_code(1, "Permission denied") == "permission_denied"


def test_error_classify_not_found():
    assert classify_error_code(127, "command not found") == "not_found"


def test_error_classify_syntax():
    assert classify_error_code(2, "invalid option -- 'z'") == "syntax_error"


def test_error_classify_timeout():
    assert classify_error_code(124, "timed out") == "timeout"
