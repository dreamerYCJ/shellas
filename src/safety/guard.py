"""安全分级 + 错误策略"""
import re
import yaml
from pathlib import Path

# 加载规则
_rules = None

# FIX: 用 __file__ 定位 config，避免依赖 cwd
_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _load_rules():
    global _rules
    if _rules is None:
        rules_path = _CONFIG_DIR / "safety_rules.yaml"
        with open(rules_path) as f:
            _rules = yaml.safe_load(f)
    return _rules


def classify_risk(command: str) -> str:
    """对命令进行风险分级: high / medium / low"""
    rules = _load_rules()
    levels = rules.get("risk_levels", {})

    # 先检查高危
    for pattern in levels.get("high", {}).get("patterns", []):
        if re.search(pattern, command):
            return "high"
    # 再检查低危（安全命令）
    for pattern in levels.get("low", {}).get("patterns", []):
        if re.search(pattern, command):
            return "low"
    # 最后检查中危
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
