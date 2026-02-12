"""RAG检索测试"""
import pytest
from src.rag.retriever import ShellRetriever
from src.rag.query_rewriter import rewrite_query


@pytest.fixture(scope="module")
def retriever():
    return ShellRetriever(persist_dir="./data/chroma_db", current_platform="linux")


def test_rewrite_query():
    assert "disk" in rewrite_query("磁盘满了")
    assert "port" in rewrite_query("端口被占了")
    assert rewrite_query("hello world") == "hello world"


def test_retrieve_basic(retriever):
    results = retriever.retrieve("查看磁盘空间", top_k=3)
    assert len(results) > 0
    commands = [r["command"] for r in results]
    assert any(c in ["df", "du", "disk"] for c in commands)


def test_retrieve_platform_filter(retriever):
    results = retriever.retrieve("list files", top_k=10)
    for r in results:
        assert r["platform"] in ("common", "linux")


def test_format_for_prompt(retriever):
    results = retriever.retrieve("compress files", top_k=3)
    formatted = retriever.format_for_prompt(results)
    assert "相关命令参考" in formatted or formatted == ""
