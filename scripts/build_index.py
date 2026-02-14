#!/usr/bin/env python3
"""构建向量索引 — 中英双语chunk"""
import json
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_core.documents import Document

# 命令→中文关键词映射，覆盖高频运维场景
CMD_ZH_KEYWORDS = {
    "ss":        "端口 网络连接 监听 进程 PID 网络诊断 socket",
    "netstat":   "端口 网络连接 监听 进程 PID 网络状态",
    "lsof":      "端口占用 文件打开 进程 PID 谁在用",
    "fuser":     "端口占用 文件占用 进程 PID 谁在用",
    "ps":        "进程 查看进程 CPU 内存 PID 运行",
    "top":       "进程 CPU占用 内存占用 实时监控 负载",
    "htop":      "进程 CPU占用 内存占用 实时监控 负载",
    "kill":      "杀进程 终止进程 PID 信号",
    "pkill":     "杀进程 终止进程 按名字杀",
    "df":        "磁盘 空间 使用率 存储 剩余",
    "du":        "磁盘 目录大小 文件大小 占用空间",
    "free":      "内存 使用率 可用 swap 交换空间",
    "find":      "查找文件 搜索 文件名 目录 大小 时间",
    "grep":      "搜索内容 查找文本 匹配 过滤 正则",
    "tail":      "查看日志 文件末尾 实时跟踪 最后几行",
    "head":      "文件开头 前几行",
    "cat":       "查看文件 输出内容 显示文件",
    "ls":        "列出文件 目录内容 文件列表",
    "cp":        "复制文件 复制目录",
    "mv":        "移动文件 重命名",
    "rm":        "删除文件 删除目录",
    "chmod":     "修改权限 文件权限 读写执行",
    "chown":     "修改所有者 文件归属",
    "tar":       "压缩 解压 打包 归档 备份",
    "gzip":      "压缩 解压 gz",
    "zip":       "压缩 解压 zip",
    "unzip":     "解压 zip",
    "scp":       "远程复制 传输文件 SSH",
    "rsync":     "同步文件 远程同步 备份 增量",
    "ssh":       "远程登录 远程连接 SSH",
    "curl":      "HTTP请求 下载 API调用 网页",
    "wget":      "下载文件 HTTP下载",
    "ping":      "网络连通 延迟 丢包 诊断",
    "traceroute":"路由追踪 网络路径 跳数",
    "dig":       "DNS查询 域名解析",
    "nslookup":  "DNS查询 域名解析",
    "ip":        "网络接口 IP地址 路由 网卡",
    "ifconfig":  "网络接口 IP地址 网卡",
    "systemctl": "服务管理 启动 停止 重启 状态 开机启动",
    "journalctl":"系统日志 服务日志 查看日志",
    "crontab":   "定时任务 计划任务 自动执行",
    "docker":    "容器 镜像 运行 停止 Docker",
    "nvidia-smi":"GPU 显卡 显存 占用率 温度 CUDA",
    "apt":       "安装软件 卸载 更新 包管理 Ubuntu Debian",
    "yum":       "安装软件 卸载 更新 包管理 CentOS",
    "dnf":       "安装软件 卸载 更新 包管理 Fedora",
    "pacman":    "安装软件 卸载 更新 包管理 Arch",
    "pip":       "Python包 安装 卸载",
    "git":       "版本控制 提交 分支 克隆 推送",
    "awk":       "文本处理 列提取 格式化",
    "sed":       "文本替换 编辑 流处理",
    "sort":      "排序 文本排序",
    "uniq":      "去重 重复行",
    "wc":        "统计 行数 字数 字符数",
    "uname":     "系统信息 内核版本 操作系统",
    "hostname":  "主机名 计算机名",
    "uptime":    "运行时间 负载 开机时长",
    "lscpu":     "CPU信息 处理器 核心数",
    "mount":     "挂载 磁盘 文件系统 U盘",
    "umount":    "卸载 磁盘",
    "fdisk":     "分区 磁盘分区",
    "useradd":   "添加用户 创建用户",
    "passwd":    "修改密码 设置密码",
    "su":        "切换用户",
    "sudo":      "提权 管理员权限 root",
    "iptables":  "防火墙 规则 端口开放 网络安全",
    "ufw":       "防火墙 简易防火墙",
    "nmap":      "端口扫描 网络扫描 安全",
    "strace":    "系统调用 跟踪 调试",
    "ldd":       "动态链接库 依赖",
    "screen":    "终端复用 后台运行 会话",
    "tmux":      "终端复用 后台运行 会话 分屏",
}


def build_chunks(tldr_data: list[dict]) -> list[Document]:
    chunks = []
    for cmd_data in tldr_data:
        cmd_name = cmd_data["command"]
        zh_keywords = CMD_ZH_KEYWORDS.get(cmd_name, "")

        for ex in cmd_data["examples"]:
            # 中英双语chunk：中文关键词 + 英文原文
            text = (
                f"命令: {cmd_name}\n"
                f"中文关键词: {zh_keywords}\n"
                f"功能: {cmd_data['description']}\n"
                f"场景: {ex['description']}\n"
                f"用法: {ex.get('command', '')}"
            )
            metadata = {
                "command": cmd_name,
                "platform": cmd_data["platform"],
                "example_desc": ex["description"],
                "example_cmd": ex.get("command", ""),
                "full_description": cmd_data["description"],
            }
            chunks.append(Document(page_content=text, metadata=metadata))
    return chunks


def build_vectorstore(chunks: list[Document], persist_dir: str):
    embeddings = HuggingFaceBgeEmbeddings(
        model_name="./weights/bge-base-zh-v1.5",
        model_kwargs={"device": "cuda"},
        encode_kwargs={"normalize_embeddings": True},
    )
    batch_size = 500
    vs = None
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        if vs is None:
            vs = Chroma.from_documents(batch, embeddings, persist_directory=persist_dir)
        else:
            vs.add_documents(batch)
        print(f"   已索引 {min(i + batch_size, len(chunks))}/{len(chunks)}")
    return vs


if __name__ == "__main__":
    with open("./data/tldr_parsed.json", encoding="utf-8") as f:
        data = json.load(f)
    chunks = build_chunks(data)
    print(f"📦 共 {len(chunks)} 个检索单元")

    # 删除旧索引
    import shutil, os
    if os.path.exists("./data/chroma_db"):
        shutil.rmtree("./data/chroma_db")
        print("🗑️  已删除旧索引")

    build_vectorstore(chunks, "./data/chroma_db")
    print("✅ 索引构建完成")