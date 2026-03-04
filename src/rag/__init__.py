from .query_rewriter import rewrite_query

# ShellRetriever requires langchain/chromadb — lazy import to avoid hard failure
try:
    from .retriever import ShellRetriever
except ImportError:
    ShellRetriever = None
