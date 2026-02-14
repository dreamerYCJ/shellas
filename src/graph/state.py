"""LangGraph状态定义 — 两阶段RAG版本"""
from typing import TypedDict, Any


class AgentState(TypedDict):
    # 用户输入
    user_input: str
    intent: str

    # 环境上下文
    required_contexts: list[str]
    context: dict
    
    # RAG相关（两阶段设计）
    retrieved_docs: str           # 格式化后的RAG文档
    target_command: str | None    # 用户明确指定的命令（如果有）
    query_analysis: dict | None   # 查询复杂度分析结果

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
