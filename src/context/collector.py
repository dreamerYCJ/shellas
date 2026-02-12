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
                method = getattr(self, self.COLLECTORS[ctx])
                result[ctx] = method()
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
        # fallback
        r2 = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=5)
        return r2.stdout if r2.returncode == 0 else "采集失败"

    def _collect_tools(self):
        if self._tools_cache:
            return self._tools_cache
        tools_to_check = [
            "git", "docker", "python3", "node", "java", "go",
            "curl", "wget", "vim", "nano", "nginx", "mysql",
            "psql", "redis-cli", "mongosh", "ffmpeg", "jq",
        ]
        self._tools_cache = [t for t in tools_to_check if shutil.which(t)]
        return self._tools_cache

    def _collect_services(self):
        r = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "-q"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            return "\n".join(r.stdout.split("\n")[:20])
        return "采集失败（可能不是systemd系统）"

    def _collect_user(self):
        return {
            "user": os.environ.get("USER", "unknown"),
            "is_root": os.geteuid() == 0,
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
