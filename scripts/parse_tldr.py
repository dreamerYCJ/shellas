#!/usr/bin/env python3
"""解析tldr markdown为结构化JSON"""
import os, re, json
from pathlib import Path


def parse_tldr_page(filepath: str) -> dict | None:
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    lines = content.strip().split("\n")
    command, description, more_info, examples = None, "", "", []

    for line in lines:
        if line.startswith("# "):
            command = line[2:].strip()
        elif line.startswith("> More information:"):
            urls = re.findall(r"<(.+?)>", line)
            more_info = urls[0] if urls else ""
        elif line.startswith("> "):
            desc = line[2:].strip()
            if desc:
                description += desc + " "
        elif line.startswith("- "):
            examples.append({"description": line[2:].strip().rstrip(":")})
        elif line.startswith("`") and line.endswith("`") and examples:
            examples[-1]["command"] = line.strip("`")

    if not command:
        return None
    platform = "common"
    for p in Path(filepath).parts:
        if p in ("linux", "osx", "windows", "common", "android", "sunos", "freebsd"):
            platform = p
            break
    return {
        "command": command,
        "platform": platform,
        "description": description.strip(),
        "more_info": more_info,
        "examples": [e for e in examples if "command" in e],
    }


def build_dataset(tldr_path: str, output: str):
    results = []
    for root, _, files in os.walk(os.path.join(tldr_path, "pages")):
        for f in files:
            if f.endswith(".md"):
                parsed = parse_tldr_page(os.path.join(root, f))
                if parsed and parsed["platform"] != "windows":
                    results.append(parsed)

    total_ex = sum(len(r["examples"]) for r in results)
    print(f"✅ 解析完成: {len(results)} 条命令, {total_ex} 个示例")
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return results


if __name__ == "__main__":
    build_dataset("./data/tldr", "./data/tldr_parsed.json")
