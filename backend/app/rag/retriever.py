"""
RAG 检索器：BM25 + Chroma 向量余弦 混合检索 + 简单加权重排。
- 向量召回：ChromaDB 按 query_texts 返回 top_k 候选
- 词汇召回：rank-bm25 对同批候选做词汇打分，与向量分加权融合
- 每次 generate-chapter 前自动调用 retrieve_for_generation
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from rank_bm25 import BM25Okapi

from app.rag.chroma_store import query as chroma_query


@dataclass
class RetrievalResult:
    document: str
    metadata: dict
    score: float


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def retrieve(novel_id: str, query: str, collection: str = "world",
             top_k: int = 8, alpha: float = 0.6) -> list[RetrievalResult]:
    """
    hybrid retrieval。
    alpha: 向量分权重（1-alpha 为 BM25 权重）。候选池取 top_k*2 再重排。
    """
    pool = top_k * 2
    res = chroma_query(novel_id, collection, [query], top_k=pool)
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    if not docs:
        return []
    # 防御：chroma 可能返回非字符串/空串条目（如某书尚未建立该集合），
    # 过滤后再判断，避免 BM25Okapi 以空语料初始化导致除零崩溃。
    docs = [d for d in docs if isinstance(d, str) and d.strip()]
    if not docs:
        return []

    # 向量得分归一（chroma 返回 distances，转相似度 1/(1+d)）
    dists = (res.get("distances") or [[]])[0]
    vec_scores = [1.0 / (1.0 + d) for d in dists] if dists else [1.0] * len(docs)

    # BM25 得分
    bm = BM25Okapi([_tokenize(d) for d in docs])
    bm_scores = bm.get_scores(_tokenize(query)).tolist()

    def norm(vs: list[float]) -> list[float]:
        lo, hi = min(vs), max(vs)
        return [0.0 if hi == lo else (v - lo) / (hi - lo) for v in vs]

    nv, nb = norm(vec_scores), norm(bm_scores)
    fused = [alpha * a + (1 - alpha) * b for a, b in zip(nv, nb)]

    items = sorted(zip(fused, docs, metas), key=lambda x: x[0], reverse=True)[:top_k]
    return [RetrievalResult(document=d, metadata=m or {}, score=s) for s, d, m in items]


def retrieve_for_generation(novel_id: str, chapter_query: str) -> list[str]:
    """生成章节时自动触发：检索世界观设定 + 前序章节 + 写作技巧。"""
    out: list[str] = []
    for coll in ("world", "chapter", "skill"):
        for r in retrieve(novel_id, chapter_query, collection=coll, top_k=3):
            out.append(f"[{coll}] {r.document}")
    return out
