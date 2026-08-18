"""
Pydantic v2 Schema：Novel / Chapter / 生成请求与响应。
"""
from __future__ import annotations
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ----------------------------- 小说 -----------------------------
class NovelCreate(BaseModel):
    title: str = Field(..., examples=["我师兄实在太稳健了"])
    genre: str = Field(..., examples=["玄幻修仙"])
    premise: str = Field(..., description="核心设定/卖点")
    target_chapters: int = Field(100, ge=1, le=10000)
    style: str = Field("爽文，节奏快，每章至少一个爽点")


class NovelOut(NovelCreate):
    id: str
    created_at: datetime


# ----------------------------- 大纲 -----------------------------
class ChapterOutline(BaseModel):
    chapter: int
    title: str
    hook: str
    climax: str
    word_count: int = 2500
    # 2.0 补齐：章节中段发展 + 章末钩子（与子提示词1 PlotArchitect 规格对齐）
    development: str = ""
    ending_hook: str = ""


class VolumeOutline(BaseModel):
    volume: str
    chapters: list[ChapterOutline]
    # 2.0 补齐：本卷弧光（主题/情绪基调），由 Pass-2 细化时织入
    arc: str = ""


class TotalOutline(BaseModel):
    """全书总纲（子提示词1 规格）。"""
    core_conflict: str = ""
    growth_arc: str = ""
    ultimate_goal: str = ""


class OutlineGenerateRequest(BaseModel):
    novel_id: str


class OutlineGenerateResponse(BaseModel):
    novel_id: str
    total_outline: TotalOutline | None = None
    outline: list[VolumeOutline]


# ----------------------------- 章节生成 -----------------------------
class ChapterGenerateRequest(BaseModel):
    novel_id: str
    chapter_no: int = Field(..., ge=1, description="要生成的章节序号")


class ChapterGenerateResponse(BaseModel):
    novel_id: str
    chapter_no: int
    title: str
    content: str
    word_count: int
    retrieved_context: list[str] = Field(default_factory=list)
    # 2.0：章节元数据（由 ChapterWriter 解析末尾元数据行得到）
    meta: dict = Field(default_factory=dict, description="爽点/伏笔/字数等元数据")


# ----------------------------- 审校 -----------------------------
class ChapterReviewRequest(BaseModel):
    novel_id: str
    chapter_no: int


class IssueItem(BaseModel):
    """结构化审校问题（子提示词4 ConflictEditor 规格）。"""
    severity: str = ""      # 严重/中等/轻微
    type: str = ""          # 节奏/逻辑/爽点/文笔/设定
    location: str = ""      # 问题位置（如「第3段」）
    problem: str = ""
    fix: str = ""


class ChapterReviewResponse(BaseModel):
    novel_id: str
    chapter_no: int
    # 2.0：四维评分（各 1-10），total = 四者之和（满分 40），<24 视为不达标打回
    scores: dict = Field(default_factory=dict, description="{hook,pacing,logic,writing}")
    total: int = Field(0, ge=0, le=40, description="四维评分之和")
    verdict: str = ""       # 通过 / 打回重写 / 大修
    issues: list[IssueItem] = Field(default_factory=list)
    suggestion: str = ""


# ----------------------------- 作者手动编辑章节 -----------------------------
class ChapterUpdateRequest(BaseModel):
    content: str = Field(..., description="作者修改后的完整章节正文")
    title: str | None = Field(None, description="可选：同时修改章节标题")


# ----------------------------- 角色 / 记忆 / RAG -----------------------------
class CharacterState(BaseModel):
    name: str
    role: str
    personality: str
    motivation: str
    current_status: str
    growth_arc: str
    # 2.0 结构化状态字段（MemoryKeeper 持续更新）
    level: str = ""
    mood: str = ""
    equipment: str = ""
    location: str = ""
    faction: str = ""            # 引用 WorldBuilder 势力
    appearance: str = ""
    weakness: str = ""
    relationships: str = ""      # 与其他角色的关系网


class ForeshadowItem(BaseModel):
    id: str
    description: str
    planted_chapter: int
    status: str  # open / resolved
    expected_resolve_chapter: int | None = None
    resolved_chapter: int | None = None


# ----------------------------- 世界观（WorldBuilder） -----------------------------
class WorldSettingItem(BaseModel):
    title: str
    content: str
    category: str  # 修炼体系/地图/势力/功法/种族/其他


class WorldSettings(BaseModel):
    cultivation: list[str] = Field(default_factory=list, description="修炼体系：≥5 个境界，由低到高")
    maps: list[str] = Field(default_factory=list, description="地图/地域")
    factions: list[str] = Field(default_factory=list, description="势力，各≥3")
    treasures: list[str] = Field(default_factory=list, description="宝物功法，≥20")
    races: list[str] = Field(default_factory=list, description="种族")
    entries: list[WorldSettingItem] = Field(default_factory=list, description="RAG 友好条目（带 category）")
    text: str = ""  # 人类可读的完整世界观文本


class WorldGenerateRequest(BaseModel):
    novel_id: str


class WorldGenerateResponse(BaseModel):
    novel_id: str
    world_settings: WorldSettings
    entries_count: int


class CharacterGenerateRequest(BaseModel):
    novel_id: str


class CharacterGenerateResponse(BaseModel):
    novel_id: str
    characters: list[CharacterState]
    count: int


class ForeshadowCreate(BaseModel):
    clue: str = Field(..., description="伏笔线索/描述")
    planted_chapter: int = Field(..., ge=1, description="埋设章节")


class MemorySnapshot(BaseModel):
    novel_id: str
    characters: list[CharacterState]
    foreshadows: list[ForeshadowItem]
    recent_chapter_summaries: list[str]
    stage_summaries: list[str]


class MemoryUpdateRequest(BaseModel):
    novel_id: str
    chapter_no: int


class MemoryUpdateResponse(BaseModel):
    novel_id: str
    chapter_no: int
    character_updates: list[dict] = Field(default_factory=list)
    planted_foreshadows: list[str] = Field(default_factory=list)
    resolved_foreshadows: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ----------------------------- 一键创建新书（Coordinator 流水线） -----------------------------
class BootstrapRequest(BaseModel):
    novel_id: str


class BootstrapResponse(BaseModel):
    novel_id: str
    steps: list[str] = Field(default_factory=list, description="已完成步骤顺序")
    character_count: int = 0
    outline_volumes: int = 0


class RAGIngestRequest(BaseModel):
    novel_id: str
    collection: str = Field("world", description="world/chapter/skill/feedback")
    documents: list[str]
    metadatas: list[dict[str, Any]] | None = None


class RAGQueryRequest(BaseModel):
    novel_id: str
    query: str
    collection: str = "world"
    top_k: int = 5


class RAGQueryResponse(BaseModel):
    novel_id: str
    results: list[dict[str, Any]]
