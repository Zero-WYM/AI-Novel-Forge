"""
RAG 路由：向知识库注入文档 / 查询检索结果（调试面板用）。
"""
from __future__ import annotations
import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.models.db import SessionLocal
from app.memory.memory_manager import MemoryManager
from app.rag.chroma_store import add_documents, query as chroma_query
from app.schemas.novel import RAGIngestRequest, RAGQueryRequest, RAGQueryResponse
from app.api.auth import require_user

router = APIRouter(prefix="/api/rag", tags=["rag"], dependencies=[Depends(require_user)])


def _mm() -> MemoryManager:
    return MemoryManager(SessionLocal)


async def _assert_owner(novel_id: str, user: dict) -> None:
    """RAG 操作前校验小说归属当前用户；否则 404（外人无法向知识库注入/查询他人小说）。"""
    nov = await _mm().get_novel(novel_id)
    if not nov or nov.get("owner_id") != user["id"]:
        raise HTTPException(status_code=404, detail="小说不存在")


@router.post("/rag-ingest")
async def rag_ingest(payload: RAGIngestRequest, user: dict = Depends(require_user)):
    await _assert_owner(payload.novel_id, user)
    ids = await asyncio.to_thread(
        add_documents, payload.novel_id, payload.collection,
        payload.documents, payload.metadatas)
    return {"ingested": len(ids), "collection": payload.collection, "ids": ids}


@router.post("/rag-query", response_model=RAGQueryResponse)
async def rag_query(payload: RAGQueryRequest, user: dict = Depends(require_user)):
    await _assert_owner(payload.novel_id, user)
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
