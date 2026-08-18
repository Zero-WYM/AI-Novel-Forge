"""
MemoryKeeper（记忆管家）：跨章节一致性管家——角色状态更新、伏笔埋设/回收、时间线、风险预警。
2.0 升级：结构化输出 character_updates(含 old/new/reason) + foreshadows{planted/resolved(含 expected_resolve_chapter)}
+ timeline + warnings；消费章节正文与既有角色/伏笔。
"""
from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent


class MemoryKeeper(BaseAgent):
    name = "MemoryKeeper"
    tools = ["memory.upsert_character", "memory.add_foreshadow", "memory.resolve_foreshadow"]

    def system_prompt(self) -> str:
        return (
            "你是跨章节一致性管家，负责网文长篇创作中的角色状态、伏笔与时间线追踪。"
            "任务：基于新写章节与既有记忆，输出需更新的角色状态、伏笔状态、时间线及风险预警。\n"
            "硬约束：\n"
            "1) 输出严格合法 JSON，结构如下，不附加说明文字：\n"
            "{\n"
            '  "character_updates": [{"name": 角色名, "old": {变更前关键字段}, '
            '"new": {变更后字段(如 level/mood/location/equipment/current_status)}, "reason": 变更原因}],\n'
            '  "foreshadows": {"planted": [{"description": 新埋伏笔, "planted_chapter": 章号, '
            '"expected_resolve_chapter": 预计回收章号或 null}], '
            '"resolved": [{"id": 既有伏笔id, "resolved_chapter": 章号}]},\n'
            '  "timeline": [{"chapter": 章号, "event": 关键事件}],\n'
            '  "warnings": [一致性风险预警字符串]\n'
            "}\n"
            "2) 仅依据已提供章节文本与既有记忆做判断，禁止臆造新情节；\n"
            "3) character_updates.new 必须是提供的既有角色名，只更新确实有变化的字段；\n"
            "4) planted 伏笔必须给出 expected_resolve_chapter（无明确预期则填 null）；"
            "resolved 必须引用提供的既有伏笔 id。"
        )

    def build_user_prompt(self, *, novel_id: str, chapter_no: int, chapter_text: str = "",
                          characters: list[dict] | None = None,
                          open_foreshadows: list[dict] | None = None, **_: Any) -> str:
        import json
        parts = [f"novel_id={novel_id} 第 {chapter_no} 章"]
        if characters:
            slim = [{k: c.get(k) for k in ("name", "role", "level", "mood", "location",
                                           "equipment", "current_status") if c.get(k)}
                    for c in characters]
            parts.append("【当前角色人设（name=角色名，仅可更新这些角色）】\n" +
                         json.dumps(slim, ensure_ascii=False, indent=2))
        if open_foreshadows:
            parts.append("【未回收伏笔（可引用其 id 进行 resolved）】\n" +
                         json.dumps(open_foreshadows, ensure_ascii=False, indent=2))
        if chapter_text:
            parts.append("【本章正文】\n" + chapter_text)
        parts.append("请输出记忆更新 JSON。")
        return "\n\n".join(parts)
