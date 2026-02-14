#!/usr/bin/env python3
"""
评估脚本 — 保存有/无RAG的完整命令输出，供人工判断
不执行任何命令，只调LLM生成命令
输出: eval/eval_results.csv
"""
import yaml
import json
import csv
import time
from datetime import datetime


def load_benchmark(path="./eval/benchmark.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_command(llm_output: str) -> str:
    """从LLM输出中提取完整命令"""
    try:
        cleaned = llm_output.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(cleaned)
        steps = data.get("steps", [])
        if steps:
            # 拼接所有步骤的命令
            cmds = [s.get("command", "") for s in steps]
            return " && ".join(cmds) if len(cmds) > 1 else cmds[0]
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    # JSON解析失败，返回第一行
    first_line = llm_output.strip().split("\n")[0].strip()
    if "{" not in first_line and len(first_line) < 300:
        return first_line
    return "[解析失败]"


def run_eval():
    from src.llm.client import LLMClient
    from src.llm.prompts import PLAN_PROMPT
    from src.rag.retriever import ShellRetriever
    from src.rag.query_rewriter import rewrite_query
    from src.safety.guard import classify_risk
    from src.context.collector import ContextCollector

    cases = load_benchmark()
    llm = LLMClient()
    retriever = ShellRetriever()
    collector = ContextCollector()

    # 采集一次环境信息（所有case共用）
    env_info = collector.collect(["os_info", "user_info", "installed_tools"])
    from src.llm.prompts import build_system_prompt
    env_context = build_system_prompt(env_info)

    results = []
    total = len(cases)

    for i, case in enumerate(cases):
        cid = case.get("id", f"UNKNOWN_{i}")
        user_input = case.get("input", "")
        expected = case.get("expected_behavior", "")
        category = case.get("category", "")
        difficulty = case.get("difficulty", "")

        print(f"[{i+1}/{total}] {cid}: {user_input[:40]}...", end=" ", flush=True)

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
            "correct_no_rag": "",    # 留空，人工填
            "correct_with_rag": "",  # 留空，人工填
            "notes": "",             # 留空，人工填
        }

        # 跳过边界case
        if expected in ("empty_input", "not_shell"):
            row["cmd_no_rag"] = f"[跳过: {expected}]"
            row["cmd_with_rag"] = f"[跳过: {expected}]"
            results.append(row)
            print("跳过")
            continue

        # 安全测试：只生成一次，检查风险等级
        if expected == "block":
            prompt = PLAN_PROMPT.format(
                env_context=env_context, rag_docs="", user_input=user_input
            )
            try:
                output = llm.chat_json("你是Shell命令规划器。", prompt)
                cmd = extract_command(output)
                risk = classify_risk(cmd)
                row["cmd_no_rag"] = cmd
                row["risk_no_rag"] = risk
                row["cmd_with_rag"] = "(同左)"
                row["risk_with_rag"] = risk
                row["correct_no_rag"] = "Y" if risk == "high" else "N"
                row["correct_with_rag"] = row["correct_no_rag"]
                print(f"安全测试 risk={risk} cmd={cmd[:50]}")
            except Exception as e:
                row["notes"] = f"LLM错误: {e}"
                print(f"错误: {e}")
            results.append(row)
            continue

        # ---- 无RAG ----
        try:
            prompt_no_rag = PLAN_PROMPT.format(
                env_context=env_context, rag_docs="", user_input=user_input
            )
            output_no_rag = llm.chat_json("你是Shell命令规划器。", prompt_no_rag)
            cmd_no_rag = extract_command(output_no_rag)
            row["cmd_no_rag"] = cmd_no_rag
            row["risk_no_rag"] = classify_risk(cmd_no_rag)
        except Exception as e:
            row["cmd_no_rag"] = f"[错误: {e}]"

        # ---- 有RAG ----
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
        except Exception as e:
            row["cmd_with_rag"] = f"[错误: {e}]"

        results.append(row)
        print(f"无RAG: {cmd_no_rag[:40]} | 有RAG: {cmd_with_rag[:40]}")

        # 避免vLLM过载
        time.sleep(0.3)

    # ---- 保存CSV ----
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

    print(f"\n✅ 结果已保存到 {output_path}")
    print(f"共 {len(results)} 条")
    print(f"\n请用Excel打开，在 correct_no_rag / correct_with_rag 列填 Y 或 N")
    print(f"填完后运行: python eval/calc_accuracy.py 计算准确率")


if __name__ == "__main__":
    run_eval()