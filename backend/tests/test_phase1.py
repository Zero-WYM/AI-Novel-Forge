# -*- coding: utf-8 -*-
"""
Phase 1 专项验证（不依赖真实 GLM / Chroma / Postgres）：
- /generate-world：WorldBuilder 产出结构化世界观 → 落库 world_settings_json + 写入 RAG world 集合
- GET /world：可读取
- PUT /world：作者可手改并保存
- 验证 ingest_world_rag（写 RAG）被调用
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
from app.agents import world_builder as wb_module  # noqa: E402

MOCK_WORLD = {
    "cultivation": ["炼气", "筑基", "金丹", "元婴", "化神", "炼虚", "合体", "大乘", "渡劫"],
    "maps": ["东域", "中州", "西域", "北荒", "南海"],
    "factions": ["天剑宗", "血魔教", "散修联盟"],
    "treasures": [f"宝物{i}" for i in range(1, 22)],  # ≥20
    "races": ["人族", "妖族", "魔族"],
    "entries": [
        {"title": "修炼体系总览", "content": "九大境界由低到高。", "category": "修炼体系"},
        {"title": "天剑宗", "content": "正道第一宗门。", "category": "势力"},
    ],
    "text": "这是一个东方玄幻世界，正邪对立。",
}


def test_phase1_world():
    ingest = MagicMock()
    with patch.object(LLMClient, "generate_json", new=AsyncMock(return_value=MOCK_WORLD)), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="摘要。")), \
         patch.object(novel_module.MemoryManager, "ingest_world_rag", new=ingest), \
         patch.object(wb_module.WorldBuilder, "run_json", new=AsyncMock(return_value=MOCK_WORLD)):
        with TestClient(app) as client:
            r = client.post("/api/novel/create", json={
                "title": "玄幻世界", "genre": "玄幻", "premise": "正邪之战", "target_chapters": 10})
            assert r.status_code == 200, r.text
            nid = r.json()["id"]

            # 生成世界观
            r = client.post("/api/novel/generate-world", json={"novel_id": nid})
            assert r.status_code == 200, r.text
            body = r.json()
            assert len(body["world_settings"]["cultivation"]) >= 5
            assert len(body["world_settings"]["factions"]) >= 3
            assert body["entries_count"] == 2
            # RAG 写入被调用
            assert ingest.called

            # 读取
            r = client.get(f"/api/novel/world?novel_id={nid}")
            assert r.status_code == 200, r.text
            assert r.json()["text"] == "这是一个东方玄幻世界，正邪对立。"

            # 手改并保存
            edited = dict(r.json())
            edited["text"] = "修改后的世界观。"
            r = client.put(f"/api/novel/world?novel_id={nid}", json=edited)
            assert r.status_code == 200, r.text
            r = client.get(f"/api/novel/world?novel_id={nid}")
            assert r.json()["text"] == "修改后的世界观。"

            # 不存在的书应 404
            r = client.get("/api/novel/world?novel_id=notexist")
            assert r.status_code == 404

    print("PHASE1_WORLD_OK")


if __name__ == "__main__":
    test_phase1_world()
