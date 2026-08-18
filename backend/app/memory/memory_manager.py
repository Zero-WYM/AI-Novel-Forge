"""
记忆管理层：短期(上下文拼接) / 中期(近5章摘要) / 长期(角色状态/伏笔/阶段总结)。
- 使用 SQLAlchemy Core Table（轻量、易序列化），由 db.py 统一建表。
- MemoryManager 提供：写入章节、查询角色/伏笔、组装 generation_context。
- 2.0 扩展：世界观落库(world_settings_json)、角色结构化字段、伏笔回收章号、
  MemoryKeeper 更新接口、RAG world 写入。
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import (
    MetaData, Table, Column, String, Integer, Text, Boolean, DateTime,
    ForeignKey, JSON,
)
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.db import engine, SessionLocal
from app.core.llm_client import LLMClient

METADATA = MetaData()

# 全局模型设置（前端「模型设置」面板保存的 API Key / Base URL / 模型名）
t_app_config = Table(
    "app_config", METADATA,
    Column("key", String, primary_key=True),
    Column("value", Text),
)

# 用户表（B 方案：独立账号 + 数据隔离）
t_users = Table(
    "users", METADATA,
    Column("id", String, primary_key=True),
    Column("username", String, unique=True, nullable=False, index=True),
    Column("password_hash", String, nullable=False),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)),
)

t_novel = Table(
    "novels", METADATA,
    Column("owner_id", String, index=True),   # B 方案：小说归属用户
    Column("id", String, primary_key=True),
    Column("title", String, nullable=False),
    Column("genre", String),
    Column("premise", Text),
    Column("target_chapters", Integer, default=100),
    Column("style", Text),
    Column("outline_json", JSON),
    Column("world_settings_json", JSON),   # 2.0：世界观结构化产物（可查看可手改）
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)),
)

t_chapter = Table(
    "chapters", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("novel_id", String, ForeignKey("novels.id"), index=True),
    Column("chapter_no", Integer),
    Column("title", String),
    Column("content", Text),
    Column("summary", Text),
    Column("word_count", Integer),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)),
)

t_character = Table(
    "characters", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("novel_id", String, ForeignKey("novels.id"), index=True),
    Column("name", String),
    Column("role", String),                 # 主角/配角/反派/势力代表
    Column("personality", Text),
    Column("motivation", Text),
    Column("current_status", Text),         # 自由文本（保留兼容）
    Column("growth_arc", Text),
    # 2.0 结构化状态字段
    Column("level", String),
    Column("mood", String),
    Column("equipment", Text),
    Column("location", String),
    Column("faction", String),              # 引用 WorldBuilder 势力
    Column("appearance", Text),
    Column("weakness", Text),
    Column("relationships", Text),          # 与其他角色的关系网
)

t_foreshadow = Table(
    "foreshadows", METADATA,
    Column("id", String, primary_key=True),
    Column("novel_id", String, ForeignKey("novels.id"), index=True),
    Column("description", Text),
    Column("planted_chapter", Integer),
    Column("expected_resolve_chapter", Integer),  # 2.0：预计回收章号
    Column("resolved_chapter", Integer),          # 2.0：实际回收章号
    Column("status", String, default="open"),
)

t_summary = Table(
    "stage_summaries", METADATA,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("novel_id", String, ForeignKey("novels.id"), index=True),
    Column("from_chapter", Integer),
    Column("to_chapter", Integer),
    Column("summary", Text),
    Column("created_at", DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)),
)


class MemoryManager:
    """记忆管家：持久化到 PostgreSQL，组装生成上下文。"""

    def __init__(self, session_factory: async_sessionmaker = SessionLocal):
        self._sf = session_factory
        self._llm: LLMClient | None = None

    @property
    def llm(self) -> LLMClient:
        """延迟初始化 LLM 客户端，避免只读操作（查角色/伏笔/章节）也要求配置 API Key。"""
        if self._llm is None:
            self._llm = LLMClient()
        return self._llm

    # ----------------------------- 写入 -----------------------------
    async def create_novel(self, novel_id: str, data: dict, owner_id: str | None = None) -> None:
        async with self._sf() as s:
            await s.execute(t_novel.insert().values(id=novel_id, owner_id=owner_id, **data))
            await s.commit()

    async def save_chapter(self, novel_id: str, chapter_no: int, title: str,
                           content: str, summary: str, word_count: int) -> None:
        async with self._sf() as s:
            await s.execute(t_chapter.insert().values(
                novel_id=novel_id, chapter_no=chapter_no, title=title,
                content=content, summary=summary, word_count=word_count))
            await s.commit()
        # 每 10 章自动生成阶段摘要（压缩长期记忆）
        if chapter_no % 10 == 0:
            await self._compress_stage(novel_id, chapter_no)

    async def update_chapter(self, novel_id: str, chapter_no: int,
                             content: str, title: str | None = None) -> dict | None:
        """作者手动编辑章节：更新正文（可选同时改标题），并重算字数。

        返回更新后的章节记录(dict)；若该章节不存在则返回 None（供接口判 404）。
        """
        values: dict = {"content": content, "word_count": len(content)}
        if title is not None:
            values["title"] = title
        async with self._sf() as s:
            res = await s.execute(
                t_chapter.update()
                .where(t_chapter.c.novel_id == novel_id,
                       t_chapter.c.chapter_no == chapter_no)
                .values(**values))
            await s.commit()
            if res.rowcount == 0:
                return None
            row = (await s.execute(
                t_chapter.select()
                .where(t_chapter.c.novel_id == novel_id,
                       t_chapter.c.chapter_no == chapter_no))).mappings().first()
        return dict(row) if row else None

    # ---- 2.0 世界观 ----
    async def save_world_settings(self, novel_id: str, data: dict) -> None:
        """保存 WorldBuilder 结构化世界观产物（可查看可手改）。"""
        async with self._sf() as s:
            await s.execute(
                t_novel.update().where(t_novel.c.id == novel_id)
                .values(world_settings_json=data))
            await s.commit()

    async def get_world_settings(self, novel_id: str) -> dict | None:
        async with self._sf() as s:
            row = (await s.execute(
                t_novel.select().where(t_novel.c.id == novel_id))).mappings().first()
        if not row:
            return None
        return row.get("world_settings_json")

    @staticmethod
    def ingest_world_rag(novel_id: str, entries: list[dict]) -> None:
        """把世界观条目写入 RAG 的 world collection（供章节生成检索）。

        重灌前先清空旧条目，保证幂等：同一本小说重复点「一键成书」不会累积重复文档。
        空条目列表时仅清空、不写入（add_documents 内部已对空列表短路）。
        """
        from app.rag.chroma_store import add_documents, clear_collection
        clear_collection(novel_id, "world")
        docs = [e.get("content", "") for e in entries]
        metas = [{"title": e.get("title", ""), "category": e.get("category", "")}
                 for e in entries]
        add_documents(novel_id, "world", docs, metas)

    @staticmethod
    def ingest_chapter_rag(novel_id: str, chapter_no: int, title: str, content: str) -> None:
        """把已生成章节正文写入 RAG 的 chapter collection（供后续章节做跨章召回）。

        使用确定性 id（{novel_id}_ch{chapter_no}）走 upsert：重生成同一章时覆盖旧文档，
        而非在检索库里累积重复条目。正文较长时截断到前 3000 字作为检索文档，
        控制单次召回上下文体量（完整正文仍在 Postgres，不丢失）。
        """
        from app.rag.chroma_store import upsert_documents
        doc = (content or "").strip()
        if not doc:
            return
        cid = f"{novel_id}_ch{chapter_no}"
        upsert_documents(
            novel_id, "chapter", [doc[:3000]],
            [{"chapter_no": chapter_no, "title": title or ""}], ids=[cid])

    # ---- 2.0 角色 ----
    async def save_characters(self, novel_id: str, chars: list[dict]) -> None:
        """创建新书时批量写入角色（先清旧再写，幂等）。"""
        async with self._sf() as s:
            await s.execute(t_character.delete().where(t_character.c.novel_id == novel_id))
            if chars:
                await s.execute(t_character.insert(),
                                [{"novel_id": novel_id, **c} for c in chars])
            await s.commit()

    async def update_character(self, novel_id: str, name: str, updates: dict) -> bool:
        """MemoryKeeper 更新单个角色的状态字段（如 level/mood/location）。"""
        async with self._sf() as s:
            res = await s.execute(
                t_character.update()
                .where(t_character.c.novel_id == novel_id,
                       t_character.c.name == name)
                .values(**updates))
            await s.commit()
            return res.rowcount > 0

    async def upsert_character(self, novel_id: str, char: dict) -> None:
        async with self._sf() as s:
            await s.execute(t_character.insert().values(novel_id=novel_id, **char))
            await s.commit()

    # ---- 2.0 伏笔 ----
    async def add_foreshadow(self, novel_id: str, item: dict) -> None:
        async with self._sf() as s:
            await s.execute(t_foreshadow.insert().values(novel_id=novel_id, **item))
            await s.commit()

    async def resolve_foreshadow(self, foreshadow_id: str, resolved_chapter: int) -> bool:
        async with self._sf() as s:
            res = await s.execute(
                t_foreshadow.update().where(t_foreshadow.c.id == foreshadow_id)
                .values(status="resolved", resolved_chapter=resolved_chapter))
            await s.commit()
            return res.rowcount > 0

    # ----------------------------- 查询 -----------------------------
    async def list_characters(self, novel_id: str) -> list[dict]:
        async with self._sf() as s:
            rows = (await s.execute(
                t_character.select().where(t_character.c.novel_id == novel_id))).mappings().all()
            return [dict(r) for r in rows]

    async def list_foreshadows(self, novel_id: str, status: str | None = None) -> list[dict]:
        async with self._sf() as s:
            stmt = t_foreshadow.select().where(t_foreshadow.c.novel_id == novel_id)
            if status:
                stmt = stmt.where(t_foreshadow.c.status == status)
            rows = (await s.execute(stmt)).mappings().all()
            return [dict(r) for r in rows]

    async def get_novel(self, novel_id: str) -> dict | None:
        """返回小说记录（dict）或 None（不存在）。"""
        async with self._sf() as s:
            row = (await s.execute(
                t_novel.select().where(t_novel.c.id == novel_id))).mappings().first()
        return dict(row) if row else None

    async def list_chapters(self, novel_id: str) -> list[dict]:
        """按章节号升序返回全部章节。"""
        async with self._sf() as s:
            rows = (await s.execute(
                t_chapter.select().where(t_chapter.c.novel_id == novel_id)
                .order_by(t_chapter.c.chapter_no))).mappings().all()
        return [dict(r) for r in rows]

    async def list_novels(self, owner_id: str | None = None) -> list[dict]:
        """返回该用户的小说（按创建时间倒序）；owner_id 为 None 时返回全部（兼容旧数据/管理场景）。"""
        stmt = t_novel.select().order_by(t_novel.c.created_at.desc())
        if owner_id is not None:
            stmt = stmt.where(t_novel.c.owner_id == owner_id)
        async with self._sf() as s:
            rows = (await s.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def recent_summaries(self, novel_id: str, limit: int = 5) -> list[str]:
        async with self._sf() as s:
            stmt = (t_chapter.select()
                    .where(t_chapter.c.novel_id == novel_id)
                    .order_by(t_chapter.c.chapter_no.desc()).limit(limit))
            rows = (await s.execute(stmt)).mappings().all()
            return [r["summary"] for r in reversed(rows) if r.get("summary")]

    async def stage_summaries(self, novel_id: str) -> list[str]:
        async with self._sf() as s:
            rows = (await s.execute(
                t_summary.select().where(t_summary.c.novel_id == novel_id)
                .order_by(t_summary.c.to_chapter))).mappings().all()
            return [r["summary"] for r in rows]

    # ----------------------------- 上下文组装 -----------------------------
    async def build_generation_context(self, novel_id: str, chapter_no: int) -> dict:
        """为 ChapterWriter 组装 短/中/长期 记忆上下文。"""
        async with self._sf() as s:
            nov = (await s.execute(
                t_novel.select().where(t_novel.c.id == novel_id))).mappings().first()
        chars = await self.list_characters(novel_id)
        fores = await self.list_foreshadows(novel_id, status="open")
        recents = await self.recent_summaries(novel_id, limit=5)
        stages = await self.stage_summaries(novel_id)
        return {
            "novel": dict(nov) if nov else {},
            "characters": chars,
            "open_foreshadows": fores,
            "recent_summaries": recents,
            "stage_summaries": stages,
            "chapter_no": chapter_no,
        }

    # ----------------------------- 压缩 -----------------------------
    async def _compress_stage(self, novel_id: str, up_to: int) -> None:
        """每 10 章：用 LLM 对近 10 章内容生成阶段总结，写入 stage_summaries。"""
        async with self._sf() as s:
            stmt = (t_chapter.select()
                    .where(t_chapter.c.novel_id == novel_id,
                           t_chapter.c.chapter_no <= up_to)
                    .order_by(t_chapter.c.chapter_no.desc()).limit(10))
            rows = (await s.execute(stmt)).mappings().all()
        if not rows:
            return
        texts = "\n\n".join(f"第{r['chapter_no']}章 {r['title']}：{r.get('summary') or r['content'][:500]}"
                             for r in reversed(rows))
        prompt = f"以下是小说最近若干章的内容，请生成一段 200 字以内的阶段性剧情总结，保留关键人物状态与未回收伏笔：\n\n{texts}"
        summary = await self.llm.generate(
            prompt,
            system="你是专业的剧情编辑，输出简洁准确的中文总结。",
            max_tokens=400,
            temperature=0.3,
        )
        from_chapter = rows[-1]["chapter_no"]
        async with self._sf() as s:
            await s.execute(t_summary.insert().values(
                novel_id=novel_id, from_chapter=from_chapter, to_chapter=up_to, summary=summary))
            await s.commit()
