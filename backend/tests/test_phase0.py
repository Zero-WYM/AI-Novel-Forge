# -*- coding: utf-8 -*-
"""
Phase 0 专项验证（不依赖真实 GLM / Chroma / Postgres）：
- PlotArchitect 注入设定后产出完整结构（total_outline / volumes[].arc /
  chapters[].development / chapters[].ending_hook）
- 完整结构以 dict 形态持久化到 outline_json
- generate-chapter 能从新 dict 结构正确归一化读取章节元信息（不报错、标题对得上）
- _volumes_from_outline 兼容 新dict / 旧list / None
"""
import os, sys, json, sqlite3
from unittest.mock import MagicMock, AsyncMock, patch

# 在导入 app 前注入重型依赖的桩模块，避免联网下载大模型依赖
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

MOCK_OUTLINE = {
    "total_outline": {
        "core_conflict": "正邪之争",
        "growth_arc": "从凡人到巅峰",
        "ultimate_goal": "守护苍生",
    },
    "volumes": [
        {
            "volume": "第一卷 崛起",
            "arc": "初入江湖",
            "chapters": [
                {"chapter": 1, "title": "穿越之夜", "hook": "雷劫穿越",
                 "development": "觉醒血脉", "climax": "反杀追杀者",
                 "ending_hook": "神秘老者现身", "word_count": 2500},
                {"chapter": 2, "title": "宗门试炼", "hook": "报名试炼",
                 "development": "结识盟友", "climax": "登顶外门",
                 "ending_hook": "内门来信", "word_count": 2500},
            ],
        }
    ],
}


def test_phase0_outline_and_chapter():
    with patch.object(LLMClient, "generate_json", new=AsyncMock(return_value=MOCK_OUTLINE)), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="测试正文。" * 60)), \
         patch.object(coord_module, "retrieve_for_generation", new=MagicMock(return_value=[])):
        with TestClient(app) as client:
            r = client.post("/api/novel/create", json={
                "title": "测试小说", "genre": "玄幻", "premise": "穿越修仙", "target_chapters": 10})
            assert r.status_code == 200, r.text
            nid = r.json()["id"]

            r = client.post("/api/novel/generate-outline", json={"novel_id": nid})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["total_outline"]["core_conflict"] == "正邪之争"
            assert body["outline"][0]["arc"] == "初入江湖"
            assert body["outline"][0]["chapters"][0]["development"] == "觉醒血脉"
            assert body["outline"][0]["chapters"][0]["ending_hook"] == "神秘老者现身"

            # 验证完整结构以 dict 存进 outline_json
            con = sqlite3.connect("test_shared.db")
            raw = con.execute("select outline_json from novels where id=?", (nid,)).fetchone()[0]
            con.close()
            stored = json.loads(raw)
            assert isinstance(stored, dict)
            assert "total_outline" in stored and "volumes" in stored

            # generate-chapter 从新 dict 结构读取章节元信息（归一化生效）
            r = client.post("/api/novel/generate-chapter", json={"novel_id": nid, "chapter_no": 1})
            assert r.status_code == 200, r.text
            assert r.json()["title"] == "穿越之夜"
            r = client.get(f"/api/novel/{nid}/chapters")
            assert len(r.json()) == 1

    print("PHASE0_OUTLINE_CHAPTER_OK")


def test_normalize_helper():
    assert novel_module._volumes_from_outline({"volumes": [{"a": 1}]}) == [{"a": 1}]
    assert novel_module._volumes_from_outline([{"a": 1}]) == [{"a": 1}]
    assert novel_module._volumes_from_outline(None) == []
    assert novel_module._volumes_from_outline({"outline": [{"b": 2}]}) == [{"b": 2}]
    print("PHASE0_NORMALIZE_OK")
