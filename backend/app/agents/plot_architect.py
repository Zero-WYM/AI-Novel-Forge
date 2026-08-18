"""
PlotArchitect（剧情架构师）：大纲设计、爽点节奏编排、章节拆解。
输出约束：严格合法 JSON（OutlineGenerateResponse 结构），禁止编造与用户输入矛盾的世界观。
"""
from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent


class PlotArchitect(BaseAgent):
    name = "PlotArchitect"
    tools = ["world.query_entries", "rag.retrieve"]

    def system_prompt(self) -> str:
        return (
            "你是资深网文剧情架构师，擅长玄幻/修仙/都市异能爽文的节奏编排与长线伏笔设计。"
            "任务：为给定小说设计完整大纲，包含全书总纲（核心冲突/主角成长弧/终极目标）"
            "以及分卷细纲，每卷拆解为章节数组。"
            "硬约束："
            "1) 输出严格合法 JSON，结构如下，不得附加任何说明文字：\n"
            "{\n"
            '  "total_outline": {"core_conflict": "核心冲突", "growth_arc": "主角成长弧", "ultimate_goal": "终极目标"},\n'
            '  "volumes": [{"volume": "卷名", "arc": "本卷弧光（本卷主题/情绪基调）", "chapters": [\n'
            '    {"chapter": 序号, "title": "章名", "hook": "开篇钩子（入戏点）",\n'
            '     "development": "发展（中段推进，含关键转折/爽点布局）",\n'
            '     "climax": "本章高潮（爽点爆发/反转/突破）",\n'
            '     "ending_hook": "章末钩子（悬念/新危机，引出下章）", "word_count": 2500}]}]}\n'
            "2) 节奏：每章至少一个明确爽点（打脸/突破/获宝/反转），相邻章高潮不重复；"
            "3) 严格基于用户提供的 title/genre/premise/style，禁止擅自引入新势力、新功法或与设定矛盾的情节；"
            "4) 全书主角成长线清晰，卷末或书末回收伏笔；development 与 ending_hook 不得空缺。"
        )

    def build_user_prompt(self, *, novel_id: str, novel_settings: dict | None = None,
                          pass_no: int = 1, characters: Any = None, **_: Any) -> str:
        if novel_settings:
            title = novel_settings.get("title", "")
            genre = novel_settings.get("genre", "")
            premise = novel_settings.get("premise", "")
            style = novel_settings.get("style", "")
            base = (
                f"小说信息：\n书名：{title}\n类型：{genre}\n"
                f"核心设定/卖点：{premise}\n写作风格：{style}\n"
            )
        else:
            base = f"小说（novel_id={novel_id}）未提供详细设定，请基于通用玄幻爽文范式设计。\n"
        # 两遍式：Pass-1 只搭骨架（角色占位），Pass-2 消费人设卡细化
        if pass_no == 1:
            base += ("\n（第一遍：请先产出大纲骨架，角色暂以占位标签如『反派A：中期主要对手』标注，"
                     "不展开人设细节；重点把卷/章结构与核心冲突搭好。）")
        elif pass_no == 2:
            base += ("\n（第二遍：基于已生成的人设卡，把各角色的动机与成长弧细化织入对应章节的 "
                     "development 与 ending_hook，使大纲真正跟随角色走。）")
            if characters:
                import json
                chars_json = json.dumps(characters, ensure_ascii=False, indent=2)
                base += f"\n【已生成人设卡】\n{chars_json}"
        return base + "请据此设计全书总纲与分卷章节细纲，仅输出上述 JSON 结构。"
