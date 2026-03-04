#!/usr/bin/env python3
"""
计算评估准确率 — 支持总体 + 分类别 + 分难度统计

用法:
    python eval/calc_accuracy.py
    python eval/calc_accuracy.py ./eval/eval_results.csv
"""
import csv
import sys
from collections import defaultdict


def calc(path="./eval/eval_results.csv"):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    # 总体统计
    total = 0
    correct_no_rag = 0
    correct_with_rag = 0
    skipped = 0
    uncertain = 0

    # 分类别统计
    by_category = defaultdict(lambda: {"total": 0, "no_rag": 0, "with_rag": 0})
    # 分难度统计
    by_difficulty = defaultdict(lambda: {"total": 0, "no_rag": 0, "with_rag": 0})

    for row in rows:
        c1 = row.get("correct_no_rag", "").strip().upper()
        c2 = row.get("correct_with_rag", "").strip().upper()
        category = row.get("category", "unknown")
        difficulty = row.get("difficulty", "unknown")

        if c1 == "?" or c2 == "?":
            uncertain += 1
            continue
        if c1 not in ("Y", "N") and c2 not in ("Y", "N"):
            skipped += 1
            continue

        total += 1
        cat = by_category[category]
        diff = by_difficulty[difficulty]
        cat["total"] += 1
        diff["total"] += 1

        if c1 == "Y":
            correct_no_rag += 1
            cat["no_rag"] += 1
            diff["no_rag"] += 1
        if c2 == "Y":
            correct_with_rag += 1
            cat["with_rag"] += 1
            diff["with_rag"] += 1

    # ---- 打印结果 ----
    print("=" * 65)
    print("ShellAgent 评估结果")
    print("=" * 65)
    print(f"已评估: {total} 条 | 跳过: {skipped} 条 | 待复核(?): {uncertain} 条")

    if total == 0:
        print("\n没有已标注的数据，请先在 CSV 中标注 Y/N")
        return

    pct1 = correct_no_rag / total * 100
    pct2 = correct_with_rag / total * 100
    diff_pct = pct2 - pct1

    print(f"\n{'指标':<20s} {'无RAG':>10s} {'有RAG':>10s} {'提升':>10s}")
    print("-" * 52)
    print(f"{'正确数':<20s} {correct_no_rag:>10d} {correct_with_rag:>10d} "
          f"{correct_with_rag - correct_no_rag:>+10d}")
    print(f"{'准确率':<20s} {pct1:>9.1f}% {pct2:>9.1f}% {diff_pct:>+9.1f}%")

    # 分类别
    print(f"\n{'分类别统计':}")
    print(f"{'类别':<18s} {'数量':>5s} {'无RAG':>8s} {'有RAG':>8s} {'提升':>8s}")
    print("-" * 50)
    for cat in sorted(by_category.keys()):
        s = by_category[cat]
        if s["total"] == 0:
            continue
        p1 = s["no_rag"] / s["total"] * 100
        p2 = s["with_rag"] / s["total"] * 100
        print(f"{cat:<18s} {s['total']:>5d} {p1:>7.0f}% {p2:>7.0f}% {p2-p1:>+7.0f}%")

    # 分难度
    print(f"\n{'分难度统计':}")
    print(f"{'难度':<18s} {'数量':>5s} {'无RAG':>8s} {'有RAG':>8s} {'提升':>8s}")
    print("-" * 50)
    for diff_name in ["easy", "medium"]:
        if diff_name not in by_difficulty:
            continue
        s = by_difficulty[diff_name]
        if s["total"] == 0:
            continue
        p1 = s["no_rag"] / s["total"] * 100
        p2 = s["with_rag"] / s["total"] * 100
        print(f"{diff_name:<18s} {s['total']:>5d} {p1:>7.0f}% {p2:>7.0f}% {p2-p1:>+7.0f}%")

    if uncertain > 0:
        print(f"\n⚠️  还有 {uncertain} 条标记为 ? 的用例需要人工复核")
        print(f"   在 CSV 中将 ? 改为 Y 或 N 后重新运行此脚本")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "./eval/eval_results.csv"
    calc(path)
