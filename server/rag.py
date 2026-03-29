# -*- coding: utf-8 -*-
"""基于 macau_tower_demo_kb_v1.md 的 BM25 检索（RAG 召回）。"""

import re
from pathlib import Path
from typing import List, Optional, Tuple

import jieba
from rank_bm25 import BM25Okapi

# 停用简单过滤，避免纯标点 chunk
_MIN_CHUNK_LEN = 30


def _default_kb_path() -> Path:
    return Path(__file__).resolve().parent.parent / "macau_tower_demo_kb_v1.md"


def load_kb_text(path: Optional[Path] = None) -> str:
    p = path or _default_kb_path()
    if not p.exists():
        raise FileNotFoundError(f"知识库文件不存在: {p}")
    return p.read_text(encoding="utf-8")


def split_chunks(text: str) -> List[str]:
    """按文档中的 --- 分隔符切分 chunk，保留各节正文。"""
    parts = re.split(r"\n---\s*\n", text)
    chunks: List[str] = []
    for raw in parts:
        s = raw.strip()
        if len(s) < _MIN_CHUNK_LEN:
            continue
        chunks.append(s)
    return chunks


def tokenize(text: str) -> List[str]:
    """中文分词 + 英文按空格，供 BM25 使用。"""
    return [t.strip() for t in jieba.cut_for_search(text) if t.strip()]


class KBIndex:
    """BM25 索引，启动时构建。"""

    def __init__(self, chunks: List[str]):
        self.chunks = chunks
        self._tokenized = [tokenize(c) for c in chunks]
        self._bm25 = BM25Okapi(self._tokenized)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, str]]:
        if not query.strip():
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = self._bm25.get_scores(q)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: List[Tuple[int, float, str]] = []
        for i in ranked[:top_k]:
            out.append((i, float(scores[i]), self.chunks[i]))
        return out


_index: KBIndex | None = None


def get_index() -> KBIndex:
    global _index
    if _index is None:
        text = load_kb_text()
        chunks = split_chunks(text)
        if not chunks:
            raise RuntimeError("知识库切分结果为空，请检查 macau_tower_demo_kb_v1.md")
        _index = KBIndex(chunks)
    return _index


def retrieve_for_query(query: str, top_k: int = 5, max_chars: int = 3500) -> Tuple[str, List[dict]]:
    """
    返回拼好的上下文字符串（供 system 注入）与来源列表（便于调试/前端展示）。
    """
    idx = get_index()
    hits = idx.search(query, top_k=top_k)
    parts: List[str] = []
    sources: List[dict] = []
    total = 0
    for rank, (_, score, chunk) in enumerate(hits, start=1):
        title = ""
        m = re.search(r"^##\s+(.+)$", chunk, re.MULTILINE)
        if m:
            title = m.group(1).strip()
        snippet = chunk[:400] + ("…" if len(chunk) > 400 else "")
        block = f"### 片段 {rank}" + (f"（{title}）\n" if title else "\n") + chunk.strip()
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
        sources.append({"rank": rank, "score": round(score, 4), "title": title, "snippet": snippet})
    context = "\n\n---\n\n".join(parts) if parts else "（当前检索未命中明确片段，请结合常识谨慎回答，并遵守边界约束。）"
    return context, sources
