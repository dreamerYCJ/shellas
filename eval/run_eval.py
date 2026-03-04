#!/usr/bin/env python3
"""
ShellAgent 评估脚本
- 对每条用例分别生成 有RAG / 无RAG 的命令
- 自动判断命令是否匹配 acceptable 列表（首词匹配）
- 安全用例检查 risk_level 是否为 high
- 输出 eval_results.csv，支持人工复核修正

用法:
    cd ShellAgent项目根目录
    python eval/run_eval.py
"""
import yaml
import json
import csv
import time
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_benchmark(path="./eval/benchmark.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_command(llm_output: str) -> str:
    """从 LLM 输出中提取命令"""
    try:
        cleaned = llm_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(cleaned)
        steps = data.get("steps", [])
        if steps:
            cmds = [s.get("command", "") for s in steps]
            return " && ".join(cmds) if len(cmds) > 1 else cmds[0]
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    first_line = llm_output.strip().split("\n")[0].strip()
    if "{" not in first_line and len(first_line) < 300:
        return first_line
    return "[解析失败]"


def auto_check(cmd: str, acceptable: list[str]) -> str:
    """自动判断命令是否正确: Y / N / ?（不确定）"""
    if not acceptable or cmd.startswith("["):
        return ""
    # 提取命令首词（处理 && 连接的多命令）
    first_cmd = cmd.split("&&")[0].strip().split("|")[0].strip()
    first_word = first_cmd.split()[0] if first_cmd.split() else ""
    # 去掉路径前缀 (/usr/bin/ls → ls)
    first_word = first_word.rsplit("/", 1)[-1]

    for acc in acceptable:
        if acc in first_word or first_word.startswith(acc):
            return "Y"
    return "?"  # 不确定，留给人工


def run_eval():
    from src.llm.client import LLMClient
    from src.llm.prompts import PLAN_PROMPT
    from src.rag.retriever import ShellRetriever
    from src.rag.query_rewriter import rewrite_query
    from src.safety.guard import classify_risk
    from src.context.collector import ContextCollector
    from src.llm.prompts import build_system_prompt

    cases = load_benchmark()
    llm = LLMClient()
    retriever = ShellRetriever()
    collector = ContextCollector()

    # 采集一次环境信息（所有 case 共用）
    env_info = collector.collect(["os_info", "user_info", "installed_tools"])
    env_context = build_system_prompt(env_info)

    results = []
    total = len(cases)
    stats = {"total": 0, "skipped": 0, "auto_y_no_rag": 0, "auto_y_with_rag": 0}

    print(f"=" * 60)
    print(f"ShellAgent 评估 - 共 {total} 条用例")
    print(f"=" * 60)

    for i, case in enumerate(cases):
        cid = case.get("id", f"UNKNOWN_{i}")
        user_input = case.get("input", "")
        expected = case.get("expected_behavior", "")
        category = case.get("category", "")
        difficulty = case.get("difficulty", "")
        acceptable = case.get("acceptable", [])

        print(f"[{i+1}/{total}] {cid}: {user_input[:40]}", end="  ", flush=True)

        row = {
            "id": cid,
            "input": user_input,
            "category": category,
            "difficulty": difficulty,
            "expected_behavior": expected,
            "cmd_no_rag": "",
            "cmd_with_rag": "",
            "risk_no_rag": "",
            "risk_with_rag": "",
            "correct_no_rag": "",
            "correct_with_rag": "",
            "notes": "",
        }

        # 跳过边界 case
        if expected in ("empty_input", "not_shell"):
            row["cmd_no_rag"] = f"[跳过: {expected}]"
            row["cmd_with_rag"] = f"[跳过: {expected}]"
            results.append(row)
            stats["skipped"] += 1
            print("跳过")
            continue

        # 安全测试：只生成一次，检查风险等级
        if expected == "block":
            try:
                prompt = PLAN_PROMPT.format(
                    env_context=env_context, rag_docs="", user_input=user_input
                )
                output = llm.chat_json("你是Shell命令规划器。", prompt)
                cmd = extract_command(output)
                risk = classify_risk(cmd)
                row["cmd_no_rag"] = cmd
                row["risk_no_rag"] = risk
                row["cmd_with_rag"] = "(同左)"
                row["risk_with_rag"] = risk
                row["correct_no_rag"] = "Y" if risk == "high" else "N"
                row["correct_with_rag"] = row["correct_no_rag"]
                stats["total"] += 1
                print(f"安全测试 risk={risk} {'✅' if risk == 'high' else '❌'}")
            except Exception as e:
                row["notes"] = f"LLM错误: {e}"
                print(f"错误: {e}")
            results.append(row)
            time.sleep(0.3)
            continue

        stats["total"] += 1

        # ---- 无 RAG ----
        try:
            prompt_no_rag = PLAN_PROMPT.format(
                env_context=env_context, rag_docs="", user_input=user_input
            )
            output_no_rag = llm.chat_json("你是Shell命令规划器。", prompt_no_rag)
            cmd_no_rag = extract_command(output_no_rag)
            row["cmd_no_rag"] = cmd_no_rag
            row["risk_no_rag"] = classify_risk(cmd_no_rag)
            row["correct_no_rag"] = auto_check(cmd_no_rag, acceptable)
            if row["correct_no_rag"] == "Y":
                stats["auto_y_no_rag"] += 1
        except Exception as e:
            row["cmd_no_rag"] = f"[错误: {e}]"
            cmd_no_rag = "[错误]"

        # ---- 有 RAG ----
        try:
            query = rewrite_query(user_input)
            rag_docs = retriever.search(query, top_k=5)
            prompt_with_rag = PLAN_PROMPT.format(
                env_context=env_context, rag_docs=rag_docs, user_input=user_input
            )
            output_with_rag = llm.chat_json("你是Shell命令规划器。", prompt_with_rag)
            cmd_with_rag = extract_command(output_with_rag)
            row["cmd_with_rag"] = cmd_with_rag
            row["risk_with_rag"] = classify_risk(cmd_with_rag)
            row["correct_with_rag"] = auto_check(cmd_with_rag, acceptable)
            if row["correct_with_rag"] == "Y":
                stats["auto_y_with_rag"] += 1
        except Exception as e:
            row["cmd_with_rag"] = f"[错误: {e}]"
            cmd_with_rag = "[错误]"

        results.append(row)
        mark_no = "✅" if row["correct_no_rag"] == "Y" else "❓" if row["correct_no_rag"] == "?" else "❌"
        mark_rag = "✅" if row["correct_with_rag"] == "Y" else "❓" if row["correct_with_rag"] == "?" else "❌"
        print(f"{mark_no} {cmd_no_rag[:30]:30s} | {mark_rag} {cmd_with_rag[:30]}")

        # 避免 vLLM 过载
        time.sleep(0.3)

    # ---- 保存 CSV ----
    output_path = "./eval/eval_results.csv"
    fieldnames = [
        "id", "input", "category", "difficulty", "expected_behavior",
        "cmd_no_rag", "cmd_with_rag",
        "risk_no_rag", "risk_with_rag",
        "correct_no_rag", "correct_with_rag", "notes",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # ---- 打印统计 ----
    print(f"\n{'=' * 60}")
    print(f"评估完成！结果已保存到 {output_path}")
    print(f"{'=' * 60}")
    print(f"总计: {stats['total']} 条 (跳过 {stats['skipped']} 条)")
    if stats["total"] > 0:
        print(f"自动判断正确 (无RAG): {stats['auto_y_no_rag']}/{stats['total']} "
              f"= {stats['auto_y_no_rag']/stats['total']:.1%}")
        print(f"自动判断正确 (有RAG): {stats['auto_y_with_rag']}/{stats['total']} "
              f"= {stats['auto_y_with_rag']/stats['total']:.1%}")
    print(f"\n标记为 ? 的用例需要人工复核（自动判断无法确定）")
    print(f"在 CSV 中将 ? 改为 Y 或 N，然后运行:")
    print(f"  python eval/calc_accuracy.py")


if __name__ == "__main__":
    run_eval()
