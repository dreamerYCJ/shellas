#!/usr/bin/env python3
"""从tldr提取跨平台差异"""
import json


def extract_diffs(tldr_data: list[dict]) -> list[dict]:
    by_cmd = {}
    for item in tldr_data:
        by_cmd.setdefault(item["command"], {})[item["platform"]] = item

    diffs = []
    for cmd, platforms in by_cmd.items():
        if len(platforms) > 1:
            diffs.append({
                "command": cmd,
                "platforms": list(platforms.keys()),
                "variants": {
                    p: {
                        "description": d["description"],
                        "examples": [e["command"] for e in d["examples"]],
                    }
                    for p, d in platforms.items()
                },
            })
    return diffs


if __name__ == "__main__":
    with open("./data/tldr_parsed.json", encoding="utf-8") as f:
        data = json.load(f)
    diffs = extract_diffs(data)
    print(f"✅ 发现 {len(diffs)} 个跨平台差异命令")
    with open("./data/compatibility.json", "w", encoding="utf-8") as f:
        json.dump(diffs, f, ensure_ascii=False, indent=2)
