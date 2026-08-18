# -*- coding: utf-8 -*-
"""
Phase 2 专项验证（不依赖真实 GLM / Chroma / Postgres）：
- /generate-characters：CharacterDesigner 产出 14 字段人设卡 → 写入 characters 表
- GET /characters：可读取（含结构化 level/faction/weakness 等字段）
- 反派具备独立 motivation
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
from app.agents import character_designer as cd_module  # noqa: E402

MOCK_CHARS = {
    "characters": [
        {"name": "林夜", "role": "主角", "personality": "坚毅", "motivation": "守护宗门",
         "current_status": "初入宗门", "growth_arc": "从凡人到巅峰", "level": "炼气",
         "mood": "沉稳", "equipment": "青锋剑", "location": "天剑宗", "faction": "天剑宗",
         "appearance": "黑衣少年", "weakness": "心魔未除", "relationships": "与苏璃为盟友"},
        {"name": "血魔老祖", "role": "反派", "personality": "阴狠",
         "motivation": "复活上古魔神（独立动机，非纯恶）", "current_status": "潜伏",
         "growth_arc": "布局千年", "level": "渡劫", "mood": "狂热", "equipment": "血魂幡",
         "location": "魔渊", "faction": "血魔教", "appearance": "红袍老者",
         "weakness": "真元损耗", "relationships": "与林夜为宿敌"},
    ]
}


def test_phase2_characters():
    with patch.object(LLMClient, "generate_json", new=AsyncMock(return_value=MOCK_CHARS)), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="摘要。")), \
         patch.object(cd_module.CharacterDesigner, "run_json", new=AsyncMock(return_value=MOCK_CHARS)):
        with TestClient(app) as client:
            r = client.post("/api/novel/create", json={
                "title": "玄幻", "genre": "玄幻", "premise": "正邪之战", "target_chapters": 10})
            assert r.status_code == 200, r.text
            nid = r.json()["id"]

            r = client.post("/api/novel/generate-characters", json={"novel_id": nid})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["count"] == 2
            assert body["characters"][1]["role"] == "反派"
            assert "独立动机" in body["characters"][1]["motivation"]

            # 读取：结构化字段齐全
            r = client.get(f"/api/novel/characters?novel_id={nid}")
            assert r.status_code == 200, r.text
            chars = {c["name"]: c for c in r.json()}
            assert chars["林夜"]["faction"] == "天剑宗"
            assert chars["林夜"]["level"] == "炼气"
            assert chars["血魔老祖"]["weakness"] == "真元损耗"

    print("PHASE2_CHARACTERS_OK")


if __name__ == "__main__":
    test_phase2_characters()
