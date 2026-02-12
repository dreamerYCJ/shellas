"""安全分级 + 错误策略"""
import re
import yaml

# 加载规则
_rules = None

def _load_rules():
    global _rules
    if _rules is None:
        with open("./config/safety_rules.yaml") as f:
            _rules = yaml.safe_load(f)
    return _rules


def classify_risk(command: str) -> str:
    rules = _load_rules()
    levels = rules.get("risk_levels", {})

    for pattern in levels.get("high", {}).get("patterns", []):
        if re.search(pattern, command):
            return "high"
    for pattern in levels.get("low", {}).get("patterns", []):
        if re.search(pattern, command):
            return "low"
    for pattern in levels.get("medium", {}).get("patterns", []):
        if re.search(pattern, command):
            return "medium"
    return "medium"  # 默认中风险


ERROR_STRATEGY = {
    "syntax_error":      {"action": "auto_retry",  "max_retries": 2},
    "not_found":         {"action": "auto_retry",  "max_retries": 1},
    "permission_denied": {"action": "suggest_fix", "max_retries": 0},
    "resource_error":    {"action": "suggest_fix", "max_retries": 0},
    "timeout":           {"action": "auto_retry",  "max_retries": 1},
    "unknown":           {"action": "ask_user",    "max_retries": 0},
}


def is_file_blocked(path: str) -> bool:
    rules = _load_rules()
    blocked = rules.get("file_access", {}).get("blocked_paths", [])
    return any(b in path for b in blocked)
