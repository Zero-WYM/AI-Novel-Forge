"""
WorldBuilder（世界观构建者）：修炼体系、地图、势力、功法、种族，写入世界观知识库（RAG world collection）。
输出约束：严格合法 JSON，结构见 WorldSettings（cultivation/maps/factions/treasures/races/entries/text）。
"""
from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent


class WorldBuilder(BaseAgent):
    name = "WorldBuilder"
    tools = ["rag.ingest_world"]

    def system_prompt(self) -> str:
        return (
            "你是网文世界观架构师，擅长为玄幻/修仙/都市异能小说设计自洽的世界观。"
            "任务：根据小说 premise/genre 产出结构化世界观设定，写入知识库。"
            "硬约束："
            "1) 输出严格合法 JSON，结构为 {"
            "\"cultivation\": [修炼境界字符串数组，由低到高 ≥5 个，命名清晰可递进], "
            "\"maps\": [地图/地域描述数组], "
            "\"factions\": [势力描述数组，各 ≥3 个，含名称与定位], "
            "\"treasures\": [宝物/功法/神兵描述数组，≥20 个], "
            "\"races\": [种族描述数组], "
            "\"entries\": [{\"title\": 条目名, \"content\": 设定正文, "
            "\"category\": 修炼体系|地图|势力|功法|种族|其他}], "
            "\"text\": 一段人类可读的完整世界观总述(300-600字)}；不得附加说明文字；"
            "2) 各条目内部逻辑自洽，等级/境界命名清晰、可递进；"
            "3) 严格基于用户 premise/genre，禁止擅自引入与主线冲突的设定；"
            "4) entries 中每条 content 具体可引用（避免空泛），80-200 字；category 必须取自给定枚举。"
        )

    def build_user_prompt(self, *, novel_id: str, premise: str = "", genre: str = "", **_: Any) -> str:
        return (
            f"novel_id={novel_id}\n"
            f"题材类型：{genre}\n"
            f"核心设定：{premise}\n"
            f"请生成结构化世界观设定，仅输出 JSON。"
        )
