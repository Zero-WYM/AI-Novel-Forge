# -*- coding: utf-8 -*-
"""
Phase 6（后端部分）验证：GET /api/novel/outline 在成书后正确返回已存完整大纲
（total_outline + volumes，供前端展示与刷新恢复），不触发重新生成。
"""
import os, sys, sqlite3
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

WORLD = {
    "cultivation": ["炼气", "筑基", "金丹", "元婴", "化神"],
    "maps": ["东域"], "factions": ["正道联盟", "魔教", "散修公会"],
    "treasures": [f"宝物{i}" for i in range(20)], "races": ["人族"],
    "entries": [{"title": "修炼体系", "content": "五境。", "category": "修炼体系"}], "text": "总述",
}
SKELETON = {"total_outline": {"core_conflict": "c", "growth_arc": "g", "ultimate_goal": "u"},
            "volumes": [{"volume": "第一卷", "arc": "", "chapters": [
                {"chapter": 1, "title": "开篇", "hook": "", "development": "", "climax": "", "ending_hook": "", "word_count": 2500}]}]}
FINAL_OUTLINE = {"total_outline": {"core_conflict": "c", "growth_arc": "g", "ultimate_goal": "u"},
                 "volumes": [{"volume": "第一卷", "arc": "初入江湖", "chapters": [
                     {"chapter": 1, "title": "穿越之夜", "hook": "雷", "development": "血脉觉醒",
                      "climax": "反杀", "ending_hook": "老者", "word_count": 2500}]}]}
CHARS = {"characters": [{"name": "林逸", "role": "主角", "personality": "坚毅", "motivation": "守护",
        "current_status": "凡", "growth_arc": "崛起", "level": "炼气", "mood": "静", "equipment": "剑",
        "location": "东域", "faction": "正道联盟", "appearance": "少年", "weakness": "弱", "relationships": "对立"}]}


async def _pa_run_json(**kwargs):
    return SKELETON if kwargs.get("pass_no") == 1 else FINAL_OUTLINE


def test_get_outline_after_bootstrap():
    with patch.object(WorldBuilder, "run_json", new=AsyncMock(return_value=WORLD)), \
         patch.object(PlotArchitect, "run_json", new=AsyncMock(side_effect=_pa_run_json)), \
         patch.object(CharacterDesigner, "run_json", new=AsyncMock(return_value=CHARS)), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="小结。")), \
         patch.object(coord_module, "retrieve_for_generation", new=MagicMock(return_value=[])):
        with TestClient(app) as client:
            nid = client.post("/api/novel/create", json={
                "title": "测试", "genre": "玄幻", "premise": "穿越"}).json()["id"]
            client.post("/api/novel/bootstrap", json={"novel_id": nid})
            # 不重新生成，直接读取已存大纲
            r = client.get(f"/api/novel/outline?novel_id={nid}")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["total_outline"]["core_conflict"] == "c"
            assert body["outline"][0]["arc"] == "初入江湖"
            assert body["outline"][0]["chapters"][0]["title"] == "穿越之夜"
            # 不存在的书返回 404
            r2 = client.get("/api/novel/outline?novel_id=nonexist")
            assert r2.status_code == 404
    print("PHASE6_GET_OUTLINE_OK")
