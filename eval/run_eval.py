#!/usr/bin/env python3
"""评估脚本 — 对比有/无RAG的命令准确率"""
import yaml
import json
from src.llm.client import LLMClient
from src.llm.prompts import PLAN_PROMPT
from src.rag.retriever import ShellRetriever
from src.rag.query_rewriter import rewrite_query
from src.safety.guard import classify_risk


def load_benchmark(path="./eval/benchmark.yaml"):
    with open(path) as f:
        return yaml.safe_load(f)


def extract_command(llm_output: str) -> str:
    """从LLM输出中提取命令"""
    try:
        data = json.loads(llm_output.strip().replace("```json", "").replace("```", ""))
        steps = data.get("steps", [])
        if steps:
            return steps[0].get("command", "")
    except json.JSONDecodeError:
        pass
    return llm_output.strip()


def is_acceptable(generated: str, acceptable: list[str]) -> bool:
    """检查生成的命令是否在可接受范围内"""
    gen = generated.strip().split()[0] if generated.strip() else ""
    for acc in acceptable:
        acc_base = acc.strip().split()[0]
        if gen == acc_base:
            return True
    return False


def run_eval():
    cases = load_benchmark()
    llm = LLMClient()
    retriever = ShellRetriever()

    results_no_rag = {"correct": 0, "total": 0, "safety_blocked": 0}
    results_with_rag = {"correct": 0, "total": 0, "safety_blocked": 0}

    for case in cases:
        # 安全测试
        if case.get("expected_behavior") == "block":
            prompt = PLAN_PROMPT.format(
                env_context="系统: Ubuntu 22.04", rag_docs="", user_input=case["input"]
            )
            output = llm.chat_json("你是Shell命令规划器。", prompt)
            cmd = extract_command(output)
            risk = classify_risk(cmd)
            if risk == "high":
                results_no_rag["safety_blocked"] += 1
                results_with_rag["safety_blocked"] += 1
            print(f"[安全] {case['id']}: cmd={cmd}, risk={risk}")
            continue

        # 无RAG
        prompt = PLAN_PROMPT.format(
            env_context="系统: Ubuntu 22.04", rag_docs="", user_input=case["input"]
        )
        output = llm.chat_json("你是Shell命令规划器。", prompt)
        cmd = extract_command(output)
        correct = is_acceptable(cmd, case["acceptable"])
        results_no_rag["total"] += 1
        results_no_rag["correct"] += int(correct)

        # 有RAG
        query = rewrite_query(case["input"])
        rag_docs = retriever.search(query)
        prompt_rag = PLAN_PROMPT.format(
            env_context="系统: Ubuntu 22.04", rag_docs=rag_docs, user_input=case["input"]
        )
        output_rag = llm.chat_json("你是Shell命令规划器。", prompt_rag)
        cmd_rag = extract_command(output_rag)
        correct_rag = is_acceptable(cmd_rag, case["acceptable"])
        results_with_rag["total"] += 1
        results_with_rag["correct"] += int(correct_rag)

        status = "✅" if correct else "❌"
        status_rag = "✅" if correct_rag else "❌"
        print(f"{case['id']}: 无RAG {status} ({cmd}) | 有RAG {status_rag} ({cmd_rag})")

    print("\n" + "=" * 50)
    print("📊 评估结果:")
    if results_no_rag["total"] > 0:
        acc1 = results_no_rag["correct"] / results_no_rag["total"] * 100
        acc2 = results_with_rag["correct"] / results_with_rag["total"] * 100
        print(f"  无RAG准确率: {acc1:.1f}% ({results_no_rag['correct']}/{results_no_rag['total']})")
        print(f"  有RAG准确率: {acc2:.1f}% ({results_with_rag['correct']}/{results_with_rag['total']})")
        print(f"  RAG提升: {acc2 - acc1:+.1f}%")
    print(f"  安全拦截: {results_no_rag['safety_blocked']}/{sum(1 for c in cases if c.get('expected_behavior') == 'block')}")


if __name__ == "__main__":
    run_eval()
