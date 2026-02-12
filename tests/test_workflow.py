"""工作流集成测试"""
import pytest
from src.graph.state import AgentState
from src.graph.nodes.intent_parser import parse_intent
from src.graph.nodes.context_planner import plan_context, INTENT_CONTEXT_MAP


def _make_state(user_input: str, **kwargs) -> AgentState:
    base = AgentState(
        user_input=user_input, intent="", required_contexts=[], context={},
        retrieved_docs="", execution_plan=[], current_step=0,
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
