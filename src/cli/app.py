#!/usr/bin/env python3
"""ShellAgent 主入口"""
import sys
from rich.prompt import Prompt
from .display import (
    console, print_banner, print_intent, print_context_plan,
    print_plan, print_execution, print_result, print_blocked,
    print_suggestion, print_retry,
)
from ..graph.workflow import build_workflow
from ..graph.state import AgentState


def create_initial_state(user_input: str) -> AgentState:
    return AgentState(
        user_input=user_input,
        intent="",
        required_contexts=[],
        context={},
        retrieved_docs="",
        execution_plan=[],
        current_step=0,
        execution_results=[],
        risk_level="",
        needs_confirmation=False,
        error=None,
        error_type=None,
        retry_count=0,
        max_retries=0,
        user_feedback=None,
        correction_rounds=0,
        final_response="",
    )


def main():
    print_banner()
    console.print("[dim]输入自然语言描述你的需求，输入 quit 退出[/dim]\n")

    try:
        app = build_workflow()
    except Exception as e:
        console.print(f"[red]工作流初始化失败: {e}[/red]")
        console.print("[dim]请确认 vLLM 已启动、向量索引已构建[/dim]")
        sys.exit(1)

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]再见！[/dim]")
            break

        if user_input.strip().lower() in ("quit", "exit", "q"):
            console.print("[dim]再见！[/dim]")
            break

        if not user_input.strip():
            continue

        state = create_initial_state(user_input)

        try:
            # 运行LangGraph
            final_state = app.invoke(state)
            response = final_state.get("final_response", "")
            if response:
                console.print(f"\n{response}")
        except KeyboardInterrupt:
            console.print("\n[yellow]已中断[/yellow]")
        except Exception as e:
            console.print(f"\n[red]执行出错: {e}[/red]")


if __name__ == "__main__":
    main()
