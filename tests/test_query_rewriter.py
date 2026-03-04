"""Query改写测试（纯CPU，不依赖模型）"""
import pytest
from src.rag.query_rewriter import (
    rewrite_query,
    extract_explicit_command,
    analyze_query_complexity,
)


def test_rewrite_query_chinese():
    assert "disk" in rewrite_query("磁盘满了")
    assert "port" in rewrite_query("端口被占了")
    assert "process" in rewrite_query("进程卡死了")


def test_rewrite_query_no_match():
    assert rewrite_query("hello world") == "hello world"


def test_extract_explicit_command():
    assert extract_explicit_command("用tar压缩文件") == "tar"
    assert extract_explicit_command("使用grep搜索") == "grep"
    assert extract_explicit_command("df -h 查看磁盘") == "df"
    assert extract_explicit_command("查看磁盘空间") is None


def test_analyze_simple():
    r = analyze_query_complexity("查看磁盘空间")
    assert r["is_simple"] is True
    assert r["rag_mode"] == "weak_reference"


def test_analyze_complex():
    r = analyze_query_complexity("如何配置nginx定时重启")
    assert r["is_simple"] is False
    assert r["rag_mode"] == "full"


def test_analyze_explicit_cmd():
    r = analyze_query_complexity("用tar压缩project目录")
    assert r["explicit_command"] == "tar"
    assert r["rag_mode"] == "syntax_only"
