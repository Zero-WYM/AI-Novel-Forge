"""
小说 API：创建、大纲生成、章节生成、审校、角色/记忆查询，以及章节/伏笔的只读与写入端点。
B 方案（独立账号 + 数据隔离）：所有路由需 JWT 登录（router 级依赖），并按 owner_id 校验小说归属，
非本人访问一律 404，确保用户只能看到/操作自己的小说。
"""
from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.models.db import SessionLocal
from app.memory.memory_manager import MemoryManager, t_novel
from app.agents.plot_architect import PlotArchitect
from app.agents.conflict_editor import ConflictEditor
from app.agents.world_builder import WorldBuilder
from app.schemas.novel import (
    NovelCreate, NovelOut, OutlineGenerateRequest, OutlineGenerateResponse,
    VolumeOutline, TotalOutline, ChapterGenerateRequest, ChapterGenerateResponse,
    ChapterReviewRequest, ChapterReviewResponse, MemorySnapshot,
    CharacterState, ForeshadowItem, ForeshadowCreate, ChapterUpdateRequest,
    WorldSettings, WorldGenerateRequest, WorldGenerateResponse, CharacterGenerateRequest,
    CharacterGenerateResponse, IssueItem, MemoryUpdateRequest, MemoryUpdateResponse,
    BootstrapRequest, BootstrapResponse,
)
from app.services.coordinator import Coordinator
from app.api.auth import require_user

router = APIRouter(prefix="/api/novel", tags=["novel"], dependencies=[Depends(require_user)])


def _mm() -> MemoryManager:
    return MemoryManager(SessionLocal)


async def _assert_owner(mm: MemoryManager, novel_id: str, user: dict) -> dict:
    """校验小说存在且归属当前用户；否则 404（外人看不到也打不开）。"""
    nov = await mm.get_novel(novel_id)
    if not nov or nov.get("owner_id") != user["id"]:
        raise HTTPException(status_code=404, detail="小说不存在")
    return nov


# ----------------------------- 小说列表 / 单本详情 -----------------------------
@router.get("/list", response_model=list[NovelOut])
async def list_novels(user: dict = Depends(require_user)):
    """列出当前登录用户的小说（按创建时间倒序）。"""
    return await _mm().list_novels(user["id"])


@router.get("/detail", response_model=NovelOut)
async def get_novel_detail(novel_id: str, user: dict = Depends(require_user)):
    """按 novel_id 查询单本小说详情（标题、类型、设定等），用于恢复 book 上下文。"""
    return await _assert_owner(_mm(), novel_id, user)


# ----------------------------- 创建小说 -----------------------------
@router.post("/create", response_model=NovelOut)
async def create_novel(payload: NovelCreate, user: dict = Depends(require_user)):
    novel_id = uuid.uuid4().hex[:12]
    await _mm().create_novel(novel_id, payload.model_dump(), owner_id=user["id"])
    return NovelOut(id=novel_id, created_at=datetime.now(timezone.utc).replace(tzinfo=None), **payload.model_dump())


# ----------------------------- 大纲读取兼容（旧结构 list / 新结构 dict） -----------------------------
def _volumes_from_outline(outline_json) -> list:
    """兼容两种存储：新结构 dict({total_outline, volumes}) 与旧结构 list([volumes])。"""
    if isinstance(outline_json, dict):
        return outline_json.get("volumes", outline_json.get("outline", []))
    if isinstance(outline_json, list):
        return outline_json
    return []


# ----------------------------- 生成大纲 -----------------------------
@router.post("/generate-outline", response_model=OutlineGenerateResponse)
async def generate_outline(payload: OutlineGenerateRequest, user: dict = Depends(require_user)):
    """由 PlotArchitect 生成分卷大纲（含全书总纲）并持久化到 novel.outline_json。"""
    mm = _mm()
    nov = await _assert_owner(mm, payload.novel_id, user)
    # 2.0：把小说设定注入架构师，避免大纲与设定脱节
    settings = {k: nov.get(k) for k in ("title", "genre", "premise", "style")}
    arch = PlotArchitect()
    raw = await arch.run_json(novel_id=payload.novel_id, novel_settings=settings)
    if raw is None:
        raise HTTPException(status_code=502, detail="模型未返回合法的大纲 JSON")
    # 兼容新结构（volumes）与旧结构（outline）
    volumes = raw.get("volumes", raw.get("outline", [])) if isinstance(raw, dict) else []
    total_outline = raw.get("total_outline") if isinstance(raw, dict) else None
    # 完整结构（含 total_outline）持久化，便于前端查看与后续 Agent 复用
    async with SessionLocal() as s:
        await s.execute(t_novel.update().where(t_novel.c.id == payload.novel_id)
                        .values(outline_json=raw if isinstance(raw, dict) else volumes))
        await s.commit()
    outline = [VolumeOutline(**v) for v in volumes]
    return OutlineGenerateResponse(
        novel_id=payload.novel_id,
        total_outline=TotalOutline(**total_outline) if isinstance(total_outline, dict) else None,
        outline=outline,
    )


# ----------------------------- 读取大纲（不重新生成，仅取已存） -----------------------------
@router.get("/outline", response_model=OutlineGenerateResponse)
async def get_outline(novel_id: str, user: dict = Depends(require_user)):
    """读取已持久化的完整大纲（含 total_outline + volumes），供一键成书后展示与刷新恢复。"""
    nov = await _assert_owner(_mm(), novel_id, user)
    raw = nov.get("outline_json") or {}
    volumes = _volumes_from_outline(raw)
    total = raw.get("total_outline") if isinstance(raw, dict) else None
    return OutlineGenerateResponse(
        novel_id=novel_id,
        total_outline=TotalOutline(**total) if isinstance(total, dict) else None,
        outline=[VolumeOutline(**v) for v in volumes],
    )


# ----------------------------- 生成世界观（WorldBuilder） -----------------------------
@router.post("/generate-world", response_model=WorldGenerateResponse)
async def generate_world(payload: WorldGenerateRequest, user: dict = Depends(require_user)):
    """由 WorldBuilder 生成结构化世界观：落库 world_settings_json（可查看可手改）+ 写入 RAG world 集合。"""
    mm = _mm()
    nov = await _assert_owner(mm, payload.novel_id, user)
    wb = WorldBuilder()
    raw = await wb.run_json(
        novel_id=payload.novel_id,
        premise=nov.get("premise", ""),
        genre=nov.get("genre", ""),
    )
    if not isinstance(raw, dict):
        raise HTTPException(status_code=502, detail="模型未返回合法的世界观 JSON")
    ws = WorldSettings.model_validate(raw)
    await mm.save_world_settings(payload.novel_id, ws.model_dump())
    # 写入 RAG world collection（供章节生成检索）。
    # Chroma 的 add 含磁盘 IO + 嵌入推理，用 to_thread 避免阻塞事件循环。
    await asyncio.to_thread(mm.ingest_world_rag, payload.novel_id, [e.model_dump() for e in ws.entries])
    return WorldGenerateResponse(
        novel_id=payload.novel_id, world_settings=ws, entries_count=len(ws.entries))


# ----------------------------- 世界观读取 / 手改 -----------------------------
@router.get("/world", response_model=WorldSettings)
async def get_world(novel_id: str, user: dict = Depends(require_user)):
    await _assert_owner(_mm(), novel_id, user)
    ws = await _mm().get_world_settings(novel_id)
    if not ws:
        raise HTTPException(status_code=404, detail="世界观尚未生成")
    return WorldSettings.model_validate(ws)


@router.put("/world", response_model=WorldSettings)
async def update_world(novel_id: str, payload: WorldSettings, user: dict = Depends(require_user)):
    """作者手动编辑世界观（可查看可改）。"""
    await _assert_owner(_mm(), novel_id, user)
    await _mm().save_world_settings(novel_id, payload.model_dump())
    return payload


# ----------------------------- 生成角色（CharacterDesigner，两遍式居中） -----------------------------
@router.post("/generate-characters", response_model=CharacterGenerateResponse)
async def generate_characters(payload: CharacterGenerateRequest, user: dict = Depends(require_user)):
    """由 CharacterDesigner 生成结构化人设卡（消费大纲骨架 + 世界观势力/种族），写入 characters 表。"""
    mm = _mm()
    nov = await _assert_owner(mm, payload.novel_id, user)
    from app.agents.character_designer import CharacterDesigner
    designer = CharacterDesigner()
    raw = await designer.run_json(
        novel_id=payload.novel_id,
        premise=nov.get("premise", ""),
        genre=nov.get("genre", ""),
        outline_json=nov.get("outline_json"),
        world_settings=nov.get("world_settings_json"),
    )
    if not isinstance(raw, dict) or "characters" not in raw:
        raise HTTPException(status_code=502, detail="模型未返回合法的人设卡 JSON")
    chars = [CharacterState.model_validate(c) for c in raw.get("characters", [])]
    await mm.save_characters(payload.novel_id, [c.model_dump() for c in chars])
    return CharacterGenerateResponse(
        novel_id=payload.novel_id, characters=chars, count=len(chars))


# ----------------------------- 生成单章（Coordinator 流水线） -----------------------------
@router.post("/generate-chapter", response_model=ChapterGenerateResponse)
async def generate_chapter(payload: ChapterGenerateRequest, user: dict = Depends(require_user)):
    """由 Coordinator 编排：RAG 上下文 → ChapterWriter → ConflictEditor(四维评分，<24 自动重写≤2次)
    → 落库 → MemoryKeeper(更新角色/伏笔)。"""
    await _assert_owner(_mm(), payload.novel_id, user)
    coord = Coordinator(_mm())
    res = await coord.generate_chapter_pipeline(payload.novel_id, payload.chapter_no)
    return ChapterGenerateResponse(
        novel_id=res["novel_id"], chapter_no=res["chapter_no"],
        title=res["title"], content=res["content"],
        word_count=res["word_count"], retrieved_context=res.get("retrieved_context", []),
        meta=res.get("meta", {}),
    )


# ----------------------------- 一键创建新书（Coordinator 创建流水线） -----------------------------
@router.post("/bootstrap", response_model=BootstrapResponse)
async def bootstrap_book(payload: BootstrapRequest, user: dict = Depends(require_user)):
    """Coordinator 创建新书流水线：WorldBuilder → RAG(world) → 两遍式大纲/角色 → 落库。"""
    await _assert_owner(_mm(), payload.novel_id, user)
    coord = Coordinator(_mm())
    res = await coord.create_book_pipeline(payload.novel_id)
    return BootstrapResponse(
        novel_id=res["novel_id"], steps=res.get("steps", []),
        character_count=res.get("character_count", 0),
        outline_volumes=res.get("outline_volumes", 0),
    )


# ----------------------------- 审校章节 -----------------------------
@router.post("/review-chapter", response_model=ChapterReviewResponse)
async def review_chapter(payload: ChapterReviewRequest, user: dict = Depends(require_user)):
    mm = _mm()
    # 必须注入章节正文，否则审校无意义
    await _assert_owner(mm, payload.novel_id, user)
    chapters = await mm.list_chapters(payload.novel_id)
    ch = next((c for c in chapters if c.get("chapter_no") == payload.chapter_no), None)
    if not ch:
        raise HTTPException(status_code=404, detail="该章节尚未生成，无法审校")
    editor = ConflictEditor()
    result = await editor.run_json(
        novel_id=payload.novel_id, chapter_no=payload.chapter_no,
        chapter_text=ch.get("content", ""), max_tokens=2000,
    )
    if not isinstance(result, dict) or "scores" not in result:
        raise HTTPException(status_code=502, detail="模型未返回合法的四维审校结果（JSON 解析失败）")
    scores = result.get("scores", {})
    raw_total = result.get("total")
    total = raw_total if isinstance(raw_total, int) else sum(
        int(v) for v in scores.values() if isinstance(v, (int, float)))
    issues = [IssueItem(**i) for i in result.get("issues", [])]
    return ChapterReviewResponse(
        novel_id=payload.novel_id, chapter_no=payload.chapter_no,
        scores=scores, total=total, verdict=result.get("verdict", ""),
        issues=issues, suggestion=result.get("suggestion", ""),
    )


# ----------------------------- 章节后记忆更新（MemoryKeeper） -----------------------------
@router.post("/update-memory", response_model=MemoryUpdateResponse)
async def update_memory(payload: MemoryUpdateRequest, user: dict = Depends(require_user)):
    """每章生成后触发：MemoryKeeper 解析章节，更新角色状态、埋设/回收伏笔。"""
    mm = _mm()
    await _assert_owner(mm, payload.novel_id, user)
    chapters = await mm.list_chapters(payload.novel_id)
    ch = next((c for c in chapters if c.get("chapter_no") == payload.chapter_no), None)
    if not ch:
        raise HTTPException(status_code=404, detail="该章节尚未生成，无法更新记忆")
    chars = await mm.list_characters(payload.novel_id)
    open_fs = await mm.list_foreshadows(payload.novel_id, status="open")
    from app.agents.memory_keeper import MemoryKeeper
    keeper = MemoryKeeper()
    raw = await keeper.run_json(
        novel_id=payload.novel_id, chapter_no=payload.chapter_no,
        chapter_text=ch.get("content", ""), characters=chars, open_foreshadows=open_fs)
    if not isinstance(raw, dict):
        raise HTTPException(status_code=502, detail="模型未返回合法的记忆更新 JSON")
    # 复用 Coordinator.apply_memory_updates，与章节生成流水线共用同一套落库逻辑，避免两处漂移
    coord = Coordinator(mm)
    stats = await coord.apply_memory_updates(payload.novel_id, raw, payload.chapter_no)
    return MemoryUpdateResponse(
        novel_id=payload.novel_id, chapter_no=payload.chapter_no,
        character_updates=stats["character_updates"],
        planted_foreshadows=stats["planted_foreshadows"],
        resolved_foreshadows=stats["resolved_foreshadows"],
        warnings=raw.get("warnings", []) or [])


# ----------------------------- 章节列表 / 伏笔 -----------------------------
@router.put("/{novel_id}/chapter/{chapter_no}", response_model=ChapterGenerateResponse)
async def update_chapter(novel_id: str, chapter_no: int, payload: ChapterUpdateRequest,
                         user: dict = Depends(require_user)):
    """作者手动编辑已生成章节：更新正文（及可选标题）并写回数据库。"""
    mm = _mm()
    await _assert_owner(mm, novel_id, user)
    row = await mm.update_chapter(novel_id, chapter_no, payload.content, payload.title)
    if row is None:
        raise HTTPException(status_code=404, detail="该章节不存在，无法更新（请先生成此章）")
    # 手动编辑后同步更新章节 RAG，保证后续跨章召回拿到最新正文（重生成幂等 upsert）
    await asyncio.to_thread(mm.ingest_chapter_rag, novel_id, chapter_no,
                             row.get("title", ""), row.get("content", ""))
    return ChapterGenerateResponse(
        novel_id=novel_id, chapter_no=chapter_no,
        title=row.get("title", ""), content=row.get("content", ""),
        word_count=row.get("word_count", 0), retrieved_context=[],
    )


@router.get("/{novel_id}/chapters")
async def list_chapters(novel_id: str, user: dict = Depends(require_user)):
    await _assert_owner(_mm(), novel_id, user)
    return await _mm().list_chapters(novel_id)


@router.get("/{novel_id}/chapter/{chapter_no}", response_model=ChapterGenerateResponse)
async def get_chapter(novel_id: str, chapter_no: int, user: dict = Depends(require_user)):
    """查询单章详情（供章节页加载已写内容 / 大纲页跳转）。"""
    mm = _mm()
    await _assert_owner(mm, novel_id, user)
    chapters = await mm.list_chapters(novel_id)
    ch = next((c for c in chapters if c.get("chapter_no") == chapter_no), None)
    if not ch:
        raise HTTPException(status_code=404, detail=f"第 {chapter_no} 章尚未生成")
    return ChapterGenerateResponse(
        novel_id=novel_id, chapter_no=chapter_no,
        title=ch.get("title", ""), content=ch.get("content", ""),
        word_count=ch.get("word_count", 0), retrieved_context=[],
    )


@router.get("/{novel_id}/foreshadows", response_model=list[ForeshadowItem])
async def list_foreshadows(novel_id: str, user: dict = Depends(require_user)):
    await _assert_owner(_mm(), novel_id, user)
    return [ForeshadowItem(**f) for f in await _mm().list_foreshadows(novel_id)]


@router.post("/{novel_id}/foreshadow", response_model=ForeshadowItem, status_code=201)
async def add_foreshadow(novel_id: str, payload: ForeshadowCreate, user: dict = Depends(require_user)):
    await _assert_owner(_mm(), novel_id, user)
    fid = uuid.uuid4().hex[:12]
    await _mm().add_foreshadow(novel_id, {
        "id": fid,
        "description": payload.clue,
        "planted_chapter": payload.planted_chapter,
        "status": "open",
    })
    return ForeshadowItem(id=fid, description=payload.clue,
                          planted_chapter=payload.planted_chapter, status="open")


# ----------------------------- 角色状态 -----------------------------
@router.get("/characters", response_model=list[CharacterState])
async def get_characters(novel_id: str, user: dict = Depends(require_user)):
    await _assert_owner(_mm(), novel_id, user)
    return [CharacterState(**c) for c in await _mm().list_characters(novel_id)]


@router.put("/characters", response_model=list[CharacterState])
async def update_characters(novel_id: str, characters: list[CharacterState], user: dict = Depends(require_user)):
    """批量更新角色卡（前端内联编辑后保存）。全量覆盖该小说的所有角色。"""
    await _assert_owner(_mm(), novel_id, user)
    await _mm().save_characters(novel_id, [c.model_dump() for c in characters])
    return [CharacterState(**c) for c in await _mm().list_characters(novel_id)]


# ----------------------------- 记忆快照 -----------------------------
@router.get("/memory", response_model=MemorySnapshot)
async def get_memory(novel_id: str, user: dict = Depends(require_user)):
    mm = _mm()
    await _assert_owner(mm, novel_id, user)
    chars = await mm.list_characters(novel_id)
    fores = await mm.list_foreshadows(novel_id, status="open")
    recents = await mm.recent_summaries(novel_id, limit=5)
    stages = await mm.stage_summaries(novel_id)
    return MemorySnapshot(
        novel_id=novel_id,
        characters=[CharacterState(**c) for c in chars],
        foreshadows=[ForeshadowItem(**f) for f in fores],
        recent_chapter_summaries=recents,
        stage_summaries=stages,
    )
