"""Query改写 — 将口语输入转为检索友好的query"""


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
