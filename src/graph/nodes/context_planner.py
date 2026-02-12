"""Context Planner — 按意图决定需要采集哪些环境信息"""
from ..state import AgentState

INTENT_CONTEXT_MAP = {
    "disk_ops":     ["os_info", "disk_usage", "cwd_files", "user_info"],
    "network":      ["os_info", "port_usage", "network_info", "user_info"],
    "process":      ["os_info", "process_list", "user_info"],
    "file_ops":     ["os_info", "cwd_files", "user_info", "installed_tools"],
    "service_mgmt": ["os_info", "service_status", "user_info"],
    "package_mgmt": ["os_info", "installed_tools", "user_info"],
    "log_analysis": ["os_info", "cwd_files", "user_info"],
    "config_check": ["os_info", "user_info"],
    "general":      ["os_info", "user_info"],
}


def plan_context(state: AgentState) -> AgentState:
    intent = state.get("intent", "general")
    required = INTENT_CONTEXT_MAP.get(intent, INTENT_CONTEXT_MAP["general"])
    return {**state, "required_contexts": required}
