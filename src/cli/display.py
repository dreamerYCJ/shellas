"""终端UI组件"""
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm

console = Console()


def print_banner():
    console.print(Panel.fit(
        "[bold cyan]🐚 ShellAgent v0.1[/bold cyan]\n"
        "[dim]环境感知的智能Shell执行代理[/dim]",
        border_style="cyan",
    ))


def print_intent(intent: str):
    console.print(f"  [dim]📋 意图: {intent}[/dim]")


def print_context_plan(contexts: list[str]):
    console.print(f"  [dim]🔍 采集: {', '.join(contexts)}[/dim]")


def print_plan(steps: list[dict]):
    console.print("\n[bold]📋 执行计划:[/bold]")
    for step in steps:
        sid = step.get("step_id", "?")
        desc = step.get("description", "")
        cmd = step.get("command", "")
        console.print(f"  {sid}. {desc}")
        console.print(f"     [green]$ {cmd}[/green]")


def print_execution(command: str, risk: str):
    risk_icons = {"low": "⚡", "medium": "⚠️", "high": "🚫"}
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}
    icon = risk_icons.get(risk, "⚡")
    color = risk_colors.get(risk, "white")
    console.print(f"\n{icon} [{color}][{risk}][/{color}] [green]$ {command}[/green]")


def print_result(exit_code: int, stdout: str, stderr: str):
    if exit_code == 0:
        console.print("[green]✅ 成功[/green]")
        if stdout.strip():
            out = stdout.strip()
            if len(out) > 2000:
                out = out[:2000] + "\n... [截断]"
            console.print(out)
    else:
        console.print(f"[red]❌ 失败 (exit_code={exit_code})[/red]")
        if stderr.strip():
            console.print(f"[red]{stderr.strip()}[/red]")


def print_blocked(command: str):
    console.print(f"\n[bold red]🚫 高危命令已拦截: {command}[/bold red]")
    console.print("[red]该命令可能造成不可逆损害，已拒绝执行。[/red]")


def print_suggestion(text: str):
    console.print(f"\n[yellow]{text}[/yellow]")


def print_retry(count: int, max_count: int):
    console.print(f"\n[yellow]🔄 自动修正 ({count}/{max_count})...[/yellow]")


def ask_confirmation(command: str, risk: str) -> bool:
    console.print(f"\n[yellow]⚠️ 中风险命令需要确认:[/yellow]")
    console.print(f"  [green]$ {command}[/green]")
    return Confirm.ask("确认执行?", default=False)


def ask_for_feedback(command: str, stderr: str, correction_round: int) -> str | None:
    console.print(f"\n[yellow]命令执行出错 (第{correction_round}/3轮纠正):[/yellow]")
    console.print(f"  [green]$ {command}[/green]")
    console.print(f"  [red]{stderr.strip()[:500]}[/red]")
    console.print("[dim]输入补充说明帮助修正，直接回车放弃:[/dim]")
    feedback = Prompt.ask("补充", default="")
    return feedback if feedback.strip() else None
