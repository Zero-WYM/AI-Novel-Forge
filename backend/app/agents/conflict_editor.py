"""
ConflictEditor（冲突编辑/审校）：审校章节，检查爽点密度、节奏、逻辑一致性、文笔。
2.0 升级：四维评分（hook/pacing/logic/writing，各 1-10）+ verdict + 结构化 issues。
输出约束：严格合法 JSON（见 system_prompt）。
"""
from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent


class ConflictEditor(BaseAgent):
    name = "ConflictEditor"
    tools = ["memory.build_generation_context"]

    def system_prompt(self) -> str:
        return (
            "你是网文审校编辑，专注爽文节奏、爽点密度、逻辑一致性与文笔评估。"
            "任务：审校给定章节，输出结构化评分与改进建议。\n"
            "硬约束：\n"
            "1) 输出严格合法 JSON，结构如下，不附加说明文字：\n"
            "{\n"
            '  "scores": {"hook": 钩子吸引力(1-10), "pacing": 节奏紧凑度(1-10), '
            '"logic": 逻辑一致性(1-10), "writing": 文笔流畅度(1-10)},\n'
            '  "total": 四者之和(4-40),\n'
            '  "verdict": "通过" | "打回重写" | "大修",\n'
            '  "issues": [{"severity": 严重|中等|轻微, "type": 节奏|逻辑|爽点|文笔|设定, '
            '"location": 问题位置(如第3段), "problem": 问题描述, "fix": 修改建议}],\n'
            '  "suggestion": 总体改进建议\n'
            "}\n"
            "2) total < 24 必须 verdict='打回重写'；24-31 为'大修'；≥32 为'通过'；\n"
            "3) 仅基于已提供章节正文与设定审校，禁止臆造未出现的情节；"
            "issues 至少 0 条，严重问题务必列出 location 与 fix。"
        )

    def build_user_prompt(self, *, novel_id: str, chapter_no: int,
                          chapter_text: str = "", **_: Any) -> str:
        head = f"novel_id={novel_id} 第 {chapter_no} 章。"
        if chapter_text:
            return head + "\n\n【待审校章节正文】\n" + chapter_text
        return head + "\n（服务层未注入正文，请要求注入后再审校）"
