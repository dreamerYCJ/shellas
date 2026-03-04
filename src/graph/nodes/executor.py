"""命令执行节点"""
import subprocess
from ..state import AgentState
from ...cli.display import spinner


def execute_command(state: AgentState) -> AgentState:
    step_idx = state["current_step"]
    step = state["execution_plan"][step_idx]
    command = step["command"]

    # 替换上一步输出中的变量占位符
    results = state.get("execution_results", [])
    for prev in results:
        placeholder = f"{{step{prev.get('step_id', 0)}_output}}"
        if placeholder in command:
            command = command.replace(placeholder, prev.get("stdout", "").strip())

    try:
        with spinner(f"正在执行: {command[:60]}..."):
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        result = {
            "step_id": step.get("step_id", step_idx + 1),
            "command": command,
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired:
        result = {
            "step_id": step.get("step_id", step_idx + 1),
            "command": command,
            "exit_code": 124,
            "stdout": "",
            "stderr": "Command timed out after 30 seconds",
        }

    new_results = list(results) + [result]
    return {**state, "execution_results": new_results}
