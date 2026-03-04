"""Query改写 + 命令提取 + RAG决策"""
import re


# 简单关键词映射，不依赖LLM，零开销
KEYWORD_MAP = {
    "磁盘": "disk space usage df du",
    "内存": "memory usage free top",
    "端口": "port listen ss lsof netstat",
    "进程": "process ps top kill",
    "日志": "log tail grep journalctl",
    "压缩": "compress tar gzip zip",
    "解压": "extract tar unzip gunzip",
    "查找": "find search grep locate",
    "删除": "remove rm delete",
    "复制": "copy cp scp rsync",
    "移动": "move mv rename",
    "权限": "permission chmod chown",
    "用户": "user useradd passwd",
    "服务": "service systemctl restart stop start",
    "网络": "network ip ifconfig ping curl",
    "防火墙": "firewall iptables ufw",
    "定时": "cron crontab schedule",
    "安装": "install apt yum dnf pacman",
    "容器": "docker container image",
    "硬件": "hardware cpu memory lscpu free",
    "CPU": "cpu processor lscpu top",
    "系统": "system uname hostname uptime",
}


def rewrite_query(user_input: str) -> str:
    """在原始query后追加关键词提升检索召回"""
    extra = []
    for keyword, expansion in KEYWORD_MAP.items():
        if keyword in user_input:
            extra.append(expansion)
    if extra:
        return user_input + " " + " ".join(extra)
    return user_input


def extract_explicit_command(user_input: str) -> str | None:
    """
    检测用户输入中是否明确指定了命令
    """
    user_input = user_input.strip()

    COMMON_COMMANDS = {
        "uname", "hostname", "uptime", "whoami", "id", "groups",
        "lscpu", "lsmem", "lsblk", "lspci", "lsusb", "lshw", "hwinfo",
        "dmidecode", "free", "vmstat", "iostat", "mpstat",
        "ls", "ll", "cat", "head", "tail", "less", "more", "file", "stat",
        "cp", "mv", "rm", "mkdir", "rmdir", "touch", "ln",
        "find", "locate", "which", "whereis", "type",
        "chmod", "chown", "chgrp",
        "grep", "awk", "sed", "cut", "sort", "uniq", "wc", "tr",
        "diff", "comm", "join", "paste",
        "df", "du", "mount", "umount", "fdisk", "parted", "mkfs",
        "ps", "top", "htop", "kill", "killall", "pkill", "pgrep",
        "jobs", "bg", "fg", "nohup",
        "ip", "ifconfig", "ping", "traceroute", "netstat", "ss",
        "curl", "wget", "nc", "telnet", "ssh", "scp", "rsync",
        "dig", "nslookup", "host",
        "systemctl", "service", "journalctl",
        "apt", "apt-get", "yum", "dnf", "pacman", "zypper", "apk",
        "pip", "npm", "cargo",
        "tar", "gzip", "gunzip", "zip", "unzip", "bzip2", "xz",
        "date", "cal", "bc", "expr", "echo", "printf",
        "env", "export", "alias", "history",
        "crontab", "at",
        "docker", "kubectl", "git",
    }

    # 模式1: "用xxx" / "使用xxx" / "运行xxx" / "执行xxx"
    # FIX: 用 [a-zA-Z0-9_-]+ 代替 \w+，避免匹配中文字符
    patterns = [
        r"(?:用|使用|运行|执行)\s*[`'\"]?([a-zA-Z0-9_-]+)[`'\"]?",
        r"[`'\"]?([a-zA-Z0-9_-]+)[`'\"]?\s*命令",
    ]
    for pattern in patterns:
        match = re.search(pattern, user_input)
        if match:
            cmd = match.group(1).lower()
            if cmd in COMMON_COMMANDS:
                return cmd

    # 模式2: 输入直接以命令开头
    first_word = user_input.split()[0].lower() if user_input else ""
    if first_word in COMMON_COMMANDS:
        return first_word

    # 模式3: 输入中包含明确的命令名（被引号或反引号包围）
    quoted_match = re.search(r"[`'\"](\w+)[`'\"]", user_input)
    if quoted_match:
        cmd = quoted_match.group(1).lower()
        if cmd in COMMON_COMMANDS:
            return cmd

    return None


def analyze_query_complexity(user_input: str) -> dict:
    """分析查询复杂度，返回分析结果"""
    explicit_cmd = extract_explicit_command(user_input)

    simple_patterns = [
        r"^查看", r"^显示", r"^列出", r"^看一?下",
        r"当前.*(?:状态|信息|目录)",
        r"^(?:什么|哪个).*(?:命令|工具)",
    ]
    complex_patterns = [
        r"如何|怎么|怎样",
        r"配置|设置|修改",
        r"脚本|批量|循环",
        r"定时|计划|自动",
        r"(?:并|且|然后|接着).*(?:再|又)",
        r"(?:如果|当).*(?:则|就)",
    ]

    is_simple = any(re.search(p, user_input) for p in simple_patterns)
    is_complex = any(re.search(p, user_input) for p in complex_patterns)

    if explicit_cmd:
        return {
            "explicit_command": explicit_cmd,
            "is_simple": True,
            "needs_rag": True,
            "rag_mode": "syntax_only",
            "reason": f"用户明确指定命令: {explicit_cmd}",
        }
    elif is_complex:
        return {
            "explicit_command": None,
            "is_simple": False,
            "needs_rag": True,
            "rag_mode": "full",
            "reason": "复杂查询，需要候选命令和语法参考",
        }
    elif is_simple:
        return {
            "explicit_command": None,
            "is_simple": True,
            "needs_rag": True,
            "rag_mode": "weak_reference",
            "reason": "简单查询，RAG仅作弱参考",
        }
    else:
        return {
            "explicit_command": None,
            "is_simple": False,
            "needs_rag": True,
            "rag_mode": "candidates",
            "reason": "一般查询，提供候选命令供参考",
        }
