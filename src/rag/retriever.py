"""RAG检索器 — 两阶段设计 + 工具可用性过滤"""
import shutil

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

_embeddings = None
_vectorstore = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="./weights/bge-base-zh-v1.5",
            model_kwargs={"device": "cuda"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def _get_vectorstore(persist_dir: str):
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            persist_directory=persist_dir,
            embedding_function=_get_embeddings(),
        )
    return _vectorstore


class ShellRetriever:

    def __init__(self, persist_dir: str = "./data/chroma_db", current_platform: str = "linux"):
        self.current_platform = current_platform
        self.vectorstore = _get_vectorstore(persist_dir)

    @staticmethod
    def _is_installed(cmd: str) -> bool:
        """检查命令是否在系统PATH里"""
        return shutil.which(cmd) is not None

    def retrieve_by_intent(self, query: str, top_k: int = 5) -> list[dict]:
        raw = self.vectorstore.similarity_search_with_score(query, k=top_k * 3)
        filtered = []
        seen_commands = set()

        for doc, score in raw:
            plat = doc.metadata.get("platform", "common")
            if plat not in ("common", self.current_platform):
                continue

            cmd = doc.metadata["command"]
            if not self._is_installed(cmd):
                continue
            if cmd in seen_commands:
                continue
            seen_commands.add(cmd)

            filtered.append({
                "command": cmd,
                "platform": plat,
                "description": doc.metadata["example_desc"],
                "example": doc.metadata["example_cmd"],
                "full_description": doc.metadata["full_description"],
                "score": float(score),
            })

        filtered.sort(key=lambda x: x["score"])
        return filtered[:top_k]

    def retrieve_by_command(self, command: str, top_k: int = 3) -> list[dict]:
        results = self.vectorstore.similarity_search_with_score(
            f"命令: {command}", k=top_k * 3
        )
        filtered = []
        for doc, score in results:
            doc_cmd = doc.metadata.get("command", "").lower()
            if doc_cmd == command.lower():
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

    def format_candidates(self, results: list[dict]) -> str:
        if not results:
            return ""
        lines = ["", "## 候选命令（仅供参考，需结合系统环境和你的判断）"]
        for r in results:
            lines.append(f"- **{r['command']}**: {r['full_description']}")
        lines.append("")
        lines.append("注意：以上命令来自文档库，可能未安装在当前系统。请优先使用你熟悉的标准命令。")
        return "\n".join(lines)

    def format_syntax_reference(self, results: list[dict]) -> str:
        if not results:
            return ""
        cmd_name = results[0]["command"]
        lines = [f"[{cmd_name}] 语法参考:"]
        for r in results:
            lines.append(f"  场景: {r['description']}")
            lines.append(f"  用法: {r['example']}")
        return "\n".join(lines)

    # ---- 兼容旧接口 ----
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        return self.retrieve_by_intent(query, top_k)

    def search(self, query: str, top_k: int = 5) -> str:
        return self.format_candidates(self.retrieve_by_intent(query, top_k))

    def format_for_prompt(self, results: list[dict]) -> str:
        return self.format_candidates(results)
