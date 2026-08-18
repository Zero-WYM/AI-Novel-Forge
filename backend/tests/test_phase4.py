# -*- coding: utf-8 -*-
"""
Phase 4 专项验证（不依赖真实 GLM / Chroma / Postgres）：
- /update-memory：MemoryKeeper 解析章节 → 更新角色状态(level) + 埋设伏笔(expected_resolve_chapter)
- 角色状态随章节演进（林夜 炼气 → 筑基）
- 伏笔可查到（open，含预计回收章号）
"""
import os, sys
from unittest.mock import MagicMock, AsyncMock, patch

_STUB = os.path.join(os.path.dirname(__file__), "_stubs")
if _STUB not in sys.path:
    sys.path.insert(0, _STUB)
sys.modules.setdefault("zhipuai", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_shared.db")
os.environ.setdefault("ZHIPU_API_KEY", "fake")
for f in ("test_shared.db", "test_shared.db-journal"):
    try:
        os.remove(f)
    except FileNotFoundError:
        pass

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.core.llm_client import LLMClient  # noqa: E402
from app.api import novel as novel_module  # noqa: E402
from app.services import coordinator as coord_module  # noqa: E402
from app.agents import character_designer as cd_module  # noqa: E402
from app.agents import chapter_writer as cw_module  # noqa: E402
from app.agents import memory_keeper as mk_module  # noqa: E402

MOCK_CHARS = {"characters": [
    {"name": "林夜", "role": "主角", "personality": "坚毅", "motivation": "守护",
     "current_status": "初入宗门", "growth_arc": "崛起", "level": "炼气",
     "mood": "沉稳", "equipment": "青锋", "location": "天剑宗", "faction": "天剑宗",
     "appearance": "少年", "weakness": "心魔", "relationships": "盟友苏璃"},
]}
MOCK_WRITE = {"content": "林夜于第1章突破。", "meta": {"word_count": 100, "cool_points": "突破", "foreshadows": ""}}
MOCK_MEMORY = {
    "character_updates": [{"name": "林夜", "old": {"level": "炼气"}, "new": {"level": "筑基"}, "reason": "突破"}],
    "foreshadows": {"planted": [{"description": "神秘玉佩", "planted_chapter": 1, "expected_resolve_chapter": 30}], "resolved": []},
    "timeline": [{"chapter": 1, "event": "林夜突破筑基"}],
    "warnings": [],
}


def test_phase4_memory():
    with patch.object(LLMClient, "generate_json", new=AsyncMock(return_value={})), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="摘要。")), \
         patch.object(coord_module, "retrieve_for_generation", new=MagicMock(return_value=[])), \
         patch.object(cd_module.CharacterDesigner, "run_json", new=AsyncMock(return_value=MOCK_CHARS)), \
         patch.object(cw_module.ChapterWriter, "write", new=AsyncMock(return_value=MOCK_WRITE)), \
         patch.object(mk_module.MemoryKeeper, "run_json", new=AsyncMock(return_value=MOCK_MEMORY)):
        with TestClient(app) as client:
            r = client.post("/api/novel/create", json={
                "title": "玄幻", "genre": "玄幻", "premise": "正邪之战", "target_chapters": 50})
            assert r.status_code == 200, r.text
            nid = r.json()["id"]

            # 先建角色（林夜 level=炼气）
            r = client.post("/api/novel/generate-characters", json={"novel_id": nid})
            assert r.status_code == 200, r.text
            r = client.get(f"/api/novel/characters?novel_id={nid}")
            assert r.json()[0]["level"] == "炼气"

            # 生成第1章
            r = client.post("/api/novel/generate-chapter", json={"novel_id": nid, "chapter_no": 1})
            assert r.status_code == 200, r.text

            # 记忆更新：林夜 → 筑基 + 埋设伏笔
            r = client.post("/api/novel/update-memory", json={"novel_id": nid, "chapter_no": 1})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["character_updates"][0]["new"]["level"] == "筑基"
            assert len(body["planted_foreshadows"]) == 1

            # 角色状态已演进
            r = client.get(f"/api/novel/characters?novel_id={nid}")
            byname = {c["name"]: c for c in r.json()}
            assert byname["林夜"]["level"] == "筑基"

            # 伏笔可查（open + 预计回收章号）。注意：2.0 生成单章流水线也会自动跑
            # MemoryKeeper，因此可能已有 1 条伏笔；这里只校验目标伏笔存在即可。
            r = client.get(f"/api/novel/{nid}/foreshadows")
            fs = r.json()
            assert len(fs) >= 1
            assert any(f["expected_resolve_chapter"] == 30 for f in fs)
            assert all(f["status"] == "open" for f in fs)

            # 未生成章节时 update-memory 应 404
            r = client.post("/api/novel/update-memory", json={"novel_id": nid, "chapter_no": 99})
            assert r.status_code == 404

    print("PHASE4_MEMORY_OK")


if __name__ == "__main__":
    test_phase4_memory()
