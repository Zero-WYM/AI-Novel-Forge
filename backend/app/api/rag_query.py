"""
RAG 路由：向知识库注入文档 / 查询检索结果（调试面板用）。
"""
from __future__ import annotations
import asyncio

from fastapi import APIRouter, Depends

from app.rag.chroma_store import add_documents, query as chroma_query
from app.schemas.novel import RAGIngestRequest, RAGQueryRequest, RAGQueryResponse
from app.api.auth import require_access

router = APIRouter(prefix="/api/rag", tags=["rag"], dependencies=[Depends(require_access)])


@router.post("/rag-ingest")
async def rag_ingest(payload: RAGIngestRequest):
    ids = await asyncio.to_thread(
        add_documents, payload.novel_id, payload.collection,
        payload.documents, payload.metadatas)
    return {"ingested": len(ids), "collection": payload.collection, "ids": ids}


@router.post("/rag-query", response_model=RAGQueryResponse)
async def rag_query(payload: RAGQueryRequest):
    res = await asyncio.to_thread(
        chroma_query, payload.novel_id, payload.collection, [payload.query], payload.top_k)
    docs = res.get("documents") or []
    metas = res.get("metadatas") or []
    if not docs or not isinstance(docs[0], list):
        docs = [docs]
    if not metas or not isinstance(metas[0], list):
        metas = [metas]
    results = [{"document": d, "metadata": m or {}} for d, m in zip(docs[0], metas[0])]
    return RAGQueryResponse(novel_id=payload.novel_id, results=results)
