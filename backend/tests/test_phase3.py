# -*- coding: utf-8 -*-
"""
Phase 3 专项验证（不依赖真实 GLM / Chroma / Postgres）：
- ChapterWriter.write：产出正文 + 解析末尾元数据行 [字数|爽点|伏笔] → 落库 meta
- ConflictEditor：四维评分 + verdict + 结构化 issues，端点正确解析
- ChapterWriter._parse_meta 单测（含无元数据行 fallback）
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
from app.agents import chapter_writer as cw_module  # noqa: E402
from app.agents import conflict_editor as ce_module  # noqa: E402

MOCK_WRITE = {"content": "这是一章正文。", "meta": {"word_count": "2500", "cool_points": "反杀长老", "foreshadows": "神秘玉佩"}}
MOCK_REVIEW = {
    "scores": {"hook": 8, "pacing": 7, "logic": 9, "writing": 8},
    "total": 32, "verdict": "通过",
    "issues": [{"severity": "轻微", "type": "文笔", "location": "第2段", "problem": "略啰嗦", "fix": "精简"}],
    "suggestion": "整体不错",
}


def test_phase3_write_and_review():
    with patch.object(LLMClient, "generate_json", new=AsyncMock(return_value={})), \
         patch.object(LLMClient, "generate", new=AsyncMock(return_value="摘要。")), \
         patch.object(coord_module, "retrieve_for_generation", new=MagicMock(return_value=[])), \
         patch.object(cw_module.ChapterWriter, "write", new=AsyncMock(return_value=MOCK_WRITE)), \
         patch.object(ce_module.ConflictEditor, "run_json", new=AsyncMock(return_value=MOCK_REVIEW)):
        with TestClient(app) as client:
            r = client.post("/api/novel/create", json={
                "title": "玄幻", "genre": "玄幻", "premise": "正邪之战", "target_chapters": 10})
            assert r.status_code == 200, r.text
            nid = r.json()["id"]

            r = client.post("/api/novel/generate-chapter", json={"novel_id": nid, "chapter_no": 1})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["meta"]["cool_points"] == "反杀长老"
            assert body["meta"]["foreshadows"] == "神秘玉佩"

            r = client.post("/api/novel/review-chapter", json={"novel_id": nid, "chapter_no": 1})
            assert r.status_code == 200, r.text
            rb = r.json()
            assert rb["total"] == 32
            assert rb["verdict"] == "通过"
            assert rb["scores"]["hook"] == 8
            assert rb["issues"][0]["fix"] == "精简"

            # 未生成章节时审校应 404
            r = client.post("/api/novel/review-chapter", json={"novel_id": nid, "chapter_no": 99})
            assert r.status_code == 404

    print("PHASE3_WRITE_REVIEW_OK")


def test_parse_meta():
    from app.agents.chapter_writer import ChapterWriter
    content, meta = ChapterWriter._parse_meta("正文第一行\n正文第二行\n[2600|反杀|玉佩]")
    assert content == "正文第一行\n正文第二行"
    assert meta["word_count"] == 2600
    assert meta["cool_points"] == "反杀"
    assert meta["foreshadows"] == "玉佩"

    c2, m2 = ChapterWriter._parse_meta("纯正文无元数据")
    assert c2 == "纯正文无元数据"
    assert m2["word_count"] == len("纯正文无元数据")
    print("PHASE3_PARSE_META_OK")


if __name__ == "__main__":
    test_phase3_write_and_review()
    test_parse_meta()
