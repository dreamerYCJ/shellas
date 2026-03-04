"""动态环境采集器 — 按需采集"""
import os
import platform
import subprocess
import shutil


class ContextCollector:
    def __init__(self):
        self._os_cache = None
        self._tools_cache = None

    COLLECTORS = {
        "os_info":         "_collect_os",
        "cwd_files":       "_collect_cwd",
        "disk_usage":      "_collect_disk",
        "process_list":    "_collect_processes",
        "port_usage":      "_collect_ports",
        "network_info":    "_collect_network",
        "installed_tools": "_collect_tools",
        "service_status":  "_collect_services",
        "user_info":       "_collect_user",
        "shell_history":   "_collect_history",
    }

    def collect(self, required: list[str]) -> dict:
        result = {}
        for ctx in required:
            if ctx.startswith("file_content:"):
                result[ctx] = self._safe_read_file(ctx.split(":", 1)[1])
            elif ctx in self.COLLECTORS:
                try:
                    result[ctx] = getattr(self, self.COLLECTORS[ctx])()
                except Exception as e:
                    result[ctx] = f"[采集失败] {e}"

        # installed_tools特殊处理：prompt里只放运维相关工具摘要
        if "installed_tools" in result and isinstance(result["installed_tools"], list):
            full_list = result["installed_tools"]
            result["_all_tools"] = set(full_list)
            RELEVANT_TOOLS = {
                "nvidia-smi", "rocm-smi", "docker", "podman", "kubectl",
                "git", "python3", "node", "java", "go", "gcc", "make",
                "nginx", "mysql", "psql", "redis-cli", "mongosh",
                "curl", "wget", "jq", "htop", "iotop", "iftop",
                "nmap", "tcpdump", "strace", "ltrace",
                "apt", "dnf", "yum", "pacman", "snap", "pip",
                "systemctl", "journalctl", "lsof", "ss", "ip",
                "tar", "gzip", "zip", "rsync", "scp",
                "tmux", "screen", "crontab",
            }
            result["installed_tools"] = sorted(
                t for t in full_list if t in RELEVANT_TOOLS
            )
        return result

    # ---- 各维度采集 ----

    def _collect_os(self):
        if self._os_cache:
            return self._os_cache
        try:
            import distro as distro_mod
            distro_name = distro_mod.name(pretty=True)
        except ImportError:
            distro_name = platform.platform()
        self._os_cache = {
            "system": platform.system(),
            "distro": distro_name,
            "kernel": platform.release(),
            "arch": platform.machine(),
            "pkg_mgr": self._detect_pkg_manager(),
        }
        return self._os_cache

    def _collect_cwd(self):
        cwd = os.getcwd()
        try:
            files = os.listdir(cwd)[:50]
        except PermissionError:
            files = ["[无权限]"]
        return {"cwd": cwd, "files": files}

    def _collect_disk(self):
        r = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=5)
        return r.stdout if r.returncode == 0 else "采集失败"

    def _collect_processes(self):
        r = subprocess.run(
            ["ps", "aux", "--sort=-%mem"], capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0:
            return "\n".join(r.stdout.split("\n")[:20])
        return "采集失败"

    def _collect_ports(self):
        r = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
        return r.stdout if r.returncode == 0 else "采集失败"

    def _collect_network(self):
        r = subprocess.run(["ip", "a"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            return r.stdout
        r2 = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5)
        return r2.stdout if r2.returncode == 0 else "采集失败"

    def _collect_tools(self):
        if self._tools_cache:
            return self._tools_cache
        found = set()
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for d in path_dirs:
            try:
                for f in os.listdir(d):
                    full = os.path.join(d, f)
                    if os.access(full, os.X_OK) and os.path.isfile(full):
                        found.add(f)
            except (PermissionError, FileNotFoundError):
                continue
        self._tools_cache = sorted(found)
        return self._tools_cache

    def has_tool(self, name: str) -> bool:
        """检查某个工具是否已安装"""
        tools = self._collect_tools()
        return name in tools

    def _collect_services(self):
        r = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=running",
             "--no-pager", "-q"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return "\n".join(r.stdout.split("\n")[:20])
        return "采集失败（可能不是systemd系统）"

    def _collect_user(self):
        has_sudo = False
        try:
            r = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True, timeout=3,
            )
            has_sudo = (r.returncode == 0)
        except Exception:
            pass

        # FIX: os.geteuid() 仅在 Unix 上可用
        is_root = False
        try:
            is_root = os.geteuid() == 0
        except AttributeError:
            # Windows 上没有 geteuid
            is_root = False

        return {
            "user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "is_root": is_root,
            "has_sudo": has_sudo,
            "home": os.path.expanduser("~"),
            "shell": os.environ.get("SHELL", "unknown"),
        }

    def _collect_history(self):
        hist_file = os.path.expanduser("~/.bash_history")
        if not os.path.exists(hist_file):
            hist_file = os.path.expanduser("~/.zsh_history")
        if not os.path.exists(hist_file):
            return "无历史记录"
        try:
            with open(hist_file, errors="ignore") as f:
                lines = f.readlines()
            return "\n".join(lines[-20:])
        except Exception:
            return "读取失败"

    def _detect_pkg_manager(self):
        for pm in ["apt", "dnf", "yum", "pacman", "apk", "zypper", "brew"]:
            if shutil.which(pm):
                return pm
        return "unknown"

    def _safe_read_file(self, path: str):
        from ..safety.guard import is_file_blocked
        if is_file_blocked(path):
            return "[安全限制] 不允许读取该文件"
        if not os.path.exists(path):
            return f"[文件不存在] {path}"
        size = os.path.getsize(path)
        try:
            with open(path, errors="ignore") as f:
                content = f.read(10240)
            if size > 10240:
                content += f"\n...[截断, 总大小 {size} 字节]"
            return content
        except Exception as e:
            return f"[读取失败] {e}"
