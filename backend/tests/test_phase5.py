# -*- coding: utf-8 -*-
"""
Phase 5 专项验证（不依赖真实 GLM / Chroma / Postgres）：
- Coordinator.create_book_pipeline：WorldBuilder → Pass-1 大纲骨架 → CharacterDesigner
  → Pass-2 大纲细化 → 落库（完整 dict 大纲 + 角色卡）。
- Coordinator.generate_chapter_pipeline：RAG 上下文 → ChapterWriter → ConflictEditor(四维)
  ① 评分≥24 不重写；② 评分<24 自动重写一次后通过；MemoryKeeper 更新。
- /bootstrap 与 /generate-chapter 端点经 Coordinator 编排。
"""
import os, sys, json, sqlite3
from unittest.mock import MagicMock, AsyncMock, patch

_STUB = os.path.join(os.path.dirname(__file__), "_stubs")
if _STUB not in sys.path:
    sys.path.insert(0, _STUB)
sys.modules.setdefault("zhipuai", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())

DB = "test_shared.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///./{DB}")
os.environ.setdefault("ZHIPU_API_KEY", "fake")
for f in (DB, DB + "-journal"):
    try:
        os.remove(f)
    except FileNotFoundError:
        pass

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.llm_client import LLMClient  # noqa: E402
from app.services import coordinator as coord_module  # noqa: E402
from app.agents.world_builder import WorldBuilder  # noqa: E402
from app.agents.plot_architect import PlotArchitect  # noqa: E402
from app.agents.character_designer import CharacterDesigner  # noqa: E402
from app.agents.chapter_writer import ChapterWriter  # noqa: E402
from app.agents.conflict_editor import ConflictEditor  # noqa: E402
from app.agents.memory_keeper import MemoryKeeper  # noqa: E402

WORLD = {
    "cultivation": ["炼气", "筑基", "金丹", "元婴", "化神"],
    "maps": ["东域", "北原"],
    "factions": ["正道联盟（守护苍生）", "魔教（掠夺资源）", "散修公会（中立）"],
    "treasures": [f"宝物{i}" for i in range(20)],
    "races": ["人族", "妖族"],
    "entries": [{"title": "修炼体系", "content": "由低到高五境。", "category": "修炼体系"}],
    "text": "世界观总述",
}
SKELETON = {
    "total_outline": {"core_conflict": "正邪之争", "growth_arc": "崛起", "ultimate_goal": "守护"},
    "volumes": [{"volume": "第一卷", "arc": "", "chapters": [
        {"chapter": 1, "title": "开篇", "hook": "", "development": "", "climax": "", "ending_hook": "", "word_count": 2500}]}],
}
FINAL_OUTLINE = {
    "total_outline": {"core_conflict": "正邪之争", "growth_arc": "崛起", "ultimate_goal": "守护"},
    "volumes": [{"volume": "第一卷", "arc": "初入江湖", "chapters": [
        {"chapter": 1, "title": "穿越之夜", "hook": "雷劫", "development": "林逸觉醒血脉对抗反派",
         "climax": "反杀", "ending_hook": "老者现身", "word_count": 2500}]}],
}
CHARS = {"characters": [
    {"name": "林逸", "role": "主角", "personality": "坚毅", "motivation": "守护苍生",
     "current_status": "凡人", "growth_arc": "崛起", "level": "炼气", "mood": "平静",
     "equipment": "青锋剑", "location": "东域", "faction": "正道联盟（守护苍生）",
     "appearance": "少年", "weakness": "经验不足", "relationships": "与魔教对立"},
    {"name": "血魔尊", "role": "反派", "personality": "冷酷", "motivation": "夺取苍生气运成就永生",
     "current_status": "潜伏", "growth_arc": "逐步现身", "level": "化神", "mood": "阴郁",
     "equipment": "血魂幡", "location": "北原", "faction": "魔教（掠夺资源）",
     "appearance": "中年", "weakness": "血气反噬", "relationships": "与林逸对立"},
]}
REVIEW_PASS = {"scores": {"hook": 8, "pacing": 8, "logic": 7, "writing": 7}, "total": 30,
                "verdict": "通过", "issues": [], "suggestion": ""}
REVIEW_FAIL = {"scores": {"hook": 4, "pacing": 5, "logic": 4, "writing": 5}, "total": 18,
                "verdict": "打回重写", "issues": [
                    {"severity": "中等", "type": "节奏", "location": "第2段",
                     "problem": "铺垫过慢", "fix": "精简开头"}],
                "suggestion": "加快节奏"}
MEM = {"character_updates": [], "foreshadows": {"planted": [], "resolved": []}, "warnings": []}


async def _pa_run_json(**kwargs):
    return SKELETON if kwargs.get("pass_no") == 1 else FINAL_OUTLINE


def test_create_pipeline():
    with patch.object(WorldBuilder, "run_json", new=AsyncMock(return_value=WORLD)), \
         patch.object(PlotArchitect, "run_json", new=AsyncMock(side_effect=_pa_run_json)), \
         patch.object(CharacterDesigner, "run_json", new=AsyncMock(return_value=CHARS)), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="小结。")), \
         patch.object(coord_module, "retrieve_for_generation", new=MagicMock(return_value=[])):
        with TestClient(app) as client:
            r = client.post("/api/novel/create", json={
                "title": "测试小说", "genre": "玄幻", "premise": "穿越修仙", "target_chapters": 10})
            nid = r.json()["id"]
            r = client.post("/api/novel/bootstrap", json={"novel_id": nid})
            assert r.status_code == 200, r.text
            body = r.json()
            assert "world" in body["steps"] and "outline_pass1" in body["steps"]
            assert "characters" in body["steps"] and "outline_pass2" in body["steps"]
            assert body["character_count"] == 2
            assert body["outline_volumes"] == 1

            con = sqlite3.connect(DB)
            raw = con.execute("select outline_json, world_settings_json from novels where id=?", (nid,)).fetchone()
            con.close()
            outline_stored = json.loads(raw[0])
            world_stored = json.loads(raw[1])
            assert isinstance(outline_stored, dict) and "volumes" in outline_stored
            # Pass-2 已把角色动机织入（development 由占位变为具体）
            assert outline_stored["volumes"][0]["chapters"][0]["development"] != ""
            assert world_stored["cultivation"][0] == "炼气"
            r = client.get("/api/novel/characters", params={"novel_id": nid})
            assert len(r.json()) == 2
    print("PHASE5_CREATE_PIPELINE_OK")


def test_generate_chapter_pass_first():
    with patch.object(WorldBuilder, "run_json", new=AsyncMock(return_value=WORLD)), \
         patch.object(PlotArchitect, "run_json", new=AsyncMock(side_effect=_pa_run_json)), \
         patch.object(CharacterDesigner, "run_json", new=AsyncMock(return_value=CHARS)), \
         patch.object(ChapterWriter, "write", new=AsyncMock(
             return_value={"content": "初版正文", "meta": {"word_count": 2000, "cool_points": "x", "foreshadows": "y"}})), \
         patch.object(ConflictEditor, "run_json", new=AsyncMock(return_value=REVIEW_PASS)), \
         patch.object(MemoryKeeper, "run_json", new=AsyncMock(return_value=MEM)), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="小结。")), \
         patch.object(coord_module, "retrieve_for_generation", new=MagicMock(return_value=[])):
        with TestClient(app) as client:
            nid = client.post("/api/novel/create", json={
                "title": "测试小说", "genre": "玄幻", "premise": "穿越修仙"}).json()["id"]
            client.post("/api/novel/bootstrap", json={"novel_id": nid})
            r = client.post("/api/novel/generate-chapter", json={"novel_id": nid, "chapter_no": 1})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["content"] == "初版正文"
            assert body["meta"]["word_count"] == 2000
            # 评分≥24，不应重写
            r2 = client.get(f"/api/novel/{nid}/chapters")
            assert len(r2.json()) == 1
            r3 = client.get("/api/novel/memory", params={"novel_id": nid})
            assert r3.status_code == 200
    print("PHASE5_CHAPTER_PASS_FIRST_OK")


def test_generate_chapter_rewrite_once():
    writer_calls = [
        {"content": "初版正文", "meta": {"word_count": 1900, "cool_points": "a", "foreshadows": ""}},
        {"content": "重写版正文", "meta": {"word_count": 2100, "cool_points": "b", "foreshadows": ""}},
    ]
    with patch.object(WorldBuilder, "run_json", new=AsyncMock(return_value=WORLD)), \
         patch.object(PlotArchitect, "run_json", new=AsyncMock(side_effect=_pa_run_json)), \
         patch.object(CharacterDesigner, "run_json", new=AsyncMock(return_value=CHARS)), \
         patch.object(ChapterWriter, "write", new=AsyncMock(side_effect=writer_calls)), \
         patch.object(ConflictEditor, "run_json", new=AsyncMock(side_effect=[REVIEW_FAIL, REVIEW_PASS])), \
         patch.object(MemoryKeeper, "run_json", new=AsyncMock(return_value=MEM)), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="小结。")), \
         patch.object(coord_module, "retrieve_for_generation", new=MagicMock(return_value=[])):
        with TestClient(app) as client:
            nid = client.post("/api/novel/create", json={
                "title": "测试小说", "genre": "玄幻", "premise": "穿越修仙"}).json()["id"]
            client.post("/api/novel/bootstrap", json={"novel_id": nid})
            r = client.post("/api/novel/generate-chapter", json={"novel_id": nid, "chapter_no": 1})
            assert r.status_code == 200, r.text
            # 第一次<24 被重写，最终采用重写版
            assert r.json()["content"] == "重写版正文"
    print("PHASE5_CHAPTER_REWRITE_OK")
