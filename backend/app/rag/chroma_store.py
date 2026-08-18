"""
ChromaDB 持久化客户端封装（内嵌 PersistentClient，无需独立服务）。
按 (novel_id, collection) 组织，每本小说、每类知识库独立 collection。
"""
from __future__ import annotations
import uuid
from chromadb import PersistentClient
from chromadb.config import Settings

from app.core.config import settings

_client = PersistentClient(path=settings.CHROMA_PERSIST_DIR, settings=Settings(anonymized_telemetry=False))


def _coll_name(novel_id: str, collection: str) -> str:
    """collection 名称：合法字符 + 唯一前缀避免冲突。"""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in f"{novel_id}_{collection}")
    return safe[:63]


def get_or_create(novel_id: str, collection: str):
    return _client.get_or_create_collection(name=_coll_name(novel_id, collection))


def clear_collection(novel_id: str, collection: str) -> None:
    """删除该 collection 的全部文档（重灌世界观前调用，避免旧条目重复累积）。

    collection 尚不存在时 chromadb 会抛 ValueError，忽略即可（本来就没东西可清）。
    """
    name = _coll_name(novel_id, collection)
    try:
        _client.delete_collection(name)
    except ValueError:
        pass


def add_documents(novel_id: str, collection: str, documents: list[str],
                  metadatas: list[dict] | None = None) -> list[str]:
    """写入文档，返回写入的 id 列表。空文档列表安全短路（避免 ChromaDB 0.5+ 抛 ValueError）。"""
    if not documents:
        return []
    coll = get_or_create(novel_id, collection)
    ids = [str(uuid.uuid4()) for _ in documents]
    coll.add(ids=ids, documents=documents, metadatas=metadatas or [{}] * len(documents))
    return ids


def upsert_documents(novel_id: str, collection: str, documents: list[str],
                     metadatas: list[dict] | None = None,
                     ids: list[str] | None = None) -> list[str]:
    """写入或更新文档（同 id 覆盖，便于章节重生成幂等）。

    与 add_documents 不同：add 遇重复 id 会报 ValueError，upsert 则就地覆盖。
    章节正文落库时据此用确定性 id，避免重生成同一章时累积重复文档。
    空文档列表安全短路。
    """
    if not documents:
        return []
    coll = get_or_create(novel_id, collection)
    ids = ids or [str(uuid.uuid4()) for _ in documents]
    coll.upsert(ids=ids, documents=documents, metadatas=metadatas or [{}] * len(documents))
    return ids


def query(novel_id: str, collection: str, query_texts: list[str], top_k: int = 5):
    """按文本相似度检索，返回 chroma QueryResult。"""
    coll = get_or_create(novel_id, collection)
    return coll.query(query_texts=query_texts, n_results=top_k)
