#!/usr/bin/env python3
"""构建ChromaDB向量索引"""
import json
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
# ✅ 新代码 (修复后)
from langchain_core.documents import Document


def build_chunks(tldr_data: list[dict]) -> list[Document]:
    chunks = []
    for cmd_data in tldr_data:
        for ex in cmd_data["examples"]:
            text = (
                f"命令: {cmd_data['command']}\n"
                f"功能: {cmd_data['description']}\n"
                f"场景: {ex['description']}\n"
                f"用法: {ex.get('command', '')}"
            )
            metadata = {
                "command": cmd_data["command"],
                "platform": cmd_data["platform"],
                "example_desc": ex["description"],
                "example_cmd": ex.get("command", ""),
                "full_description": cmd_data["description"],
            }
            chunks.append(Document(page_content=text, metadata=metadata))
    return chunks


def build_vectorstore(chunks: list[Document], persist_dir: str):
    embeddings = HuggingFaceBgeEmbeddings(
        model_name="BAAI/bge-base-zh-v1.5",
        model_kwargs={"device": "cuda"},
        encode_kwargs={"normalize_embeddings": True},
    )
    batch_size = 500
    vs = None
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        if vs is None:
            vs = Chroma.from_documents(batch, embeddings, persist_directory=persist_dir)
        else:
            vs.add_documents(batch)
        print(f"   已索引 {min(i + batch_size, len(chunks))}/{len(chunks)}")
    return vs


if __name__ == "__main__":
    with open("./data/tldr_parsed.json", encoding="utf-8") as f:
        data = json.load(f)
    chunks = build_chunks(data)
    print(f"📦 共 {len(chunks)} 个检索单元")
    build_vectorstore(chunks, "./data/chroma_db")
    print("✅ 索引构建完成")
