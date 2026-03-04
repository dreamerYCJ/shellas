"""意图解析节点"""
from ...llm.client import LLMClient
from ...llm.prompts import INTENT_PROMPT
from ...cli.display import spinner, print_intent
from ..state import AgentState

VALID_INTENTS = [
    "disk_ops", "network", "process", "file_ops",
    "service_mgmt", "package_mgmt", "log_analysis",
    "config_check", "general",
]

_llm = None


def _get_llm():
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def parse_intent(state: AgentState) -> AgentState:
    llm = _get_llm()
    prompt = INTENT_PROMPT.format(user_input=state["user_input"])

    with spinner("正在分析意图..."):
        raw = llm.chat("你是一个分类器。", prompt).strip().lower()

    # 容错：如果返回的不在列表里，用关键词匹配兜底
    intent = "general"
    for valid in VALID_INTENTS:
        if valid in raw:
            intent = valid
            break

    print_intent(intent)
    return {**state, "intent": intent}
