"""RAG检索器 — 基于tldr + ChromaDB"""
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings


class ShellRetriever:
    def __init__(self, persist_dir: str = "./data/chroma_db", current_platform: str = "linux"):
        self.current_platform = current_platform
        embeddings = HuggingFaceBgeEmbeddings(
            model_name="./weights/bge-base-zh-v1.5",
            model_kwargs={"device": "cuda"},
            encode_kwargs={"normalize_embeddings": True},
        )
        self.vectorstore = Chroma(
            persist_directory=persist_dir, embedding_function=embeddings
        )

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        raw = self.vectorstore.similarity_search_with_score(query, k=top_k * 3)
        filtered = []
        for doc, score in raw:
            plat = doc.metadata.get("platform", "common")
            if plat in ("common", self.current_platform):
                filtered.append({
                    "command": doc.metadata["command"],
                    "platform": plat,
                    "description": doc.metadata["example_desc"],
                    "example": doc.metadata["example_cmd"],
                    "full_description": doc.metadata["full_description"],
                    "score": float(score),
                })
        filtered.sort(key=lambda x: x["score"])
        return filtered[:top_k]

    def format_for_prompt(self, results: list[dict]) -> str:
        if not results:
            return ""
        lines, seen = ["相关命令参考:"], set()
        for r in results:
            if r["command"] not in seen:
                seen.add(r["command"])
                lines.append(f"\n[{r['command']}] {r['full_description']}")
            lines.append(f"  场景: {r['description']}")
            lines.append(f"  用法: {r['example']}")
        return "\n".join(lines)

    def search(self, query: str, top_k: int = 5) -> str:
        """一步到位：检索 + 格式化"""
        results = self.retrieve(query, top_k)
        return self.format_for_prompt(results)
