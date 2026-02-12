"""LangGraph状态定义"""
from typing import TypedDict


class AgentState(TypedDict):
    # 用户输入
    user_input: str
    intent: str

    # 环境上下文
    required_contexts: list[str]
    context: dict
    retrieved_docs: str

    # 执行计划
    execution_plan: list[dict]
    current_step: int
    execution_results: list[dict]

    # 安全
    risk_level: str
    needs_confirmation: bool

    # 错误处理
    error: str | None
    error_type: str | None
    retry_count: int
    max_retries: int
    user_feedback: str | None
    correction_rounds: int

    # 输出
    final_response: str
