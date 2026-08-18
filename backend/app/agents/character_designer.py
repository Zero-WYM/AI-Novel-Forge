"""
CharacterDesigner（角色设计师）：主角/配角/反派人设卡（14 字段结构化）。
处于「大纲↔角色」两遍式循环的居中：消费 PlotArchitect 大纲骨架 + WorldBuilder 势力/种族，
生成人设卡；随后被 Pass-2 大纲反向消费（动机织入章节）。
输出约束：严格合法 JSON {"characters":[{14 字段}]}。
"""
from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent


class CharacterDesigner(BaseAgent):
    name = "CharacterDesigner"
    tools = ["memory.upsert_character"]

    def system_prompt(self) -> str:
        return (
            "你是网文角色设计师，擅长塑造性格鲜明、动机清晰、成长弧光完整的小说人物。"
            "任务：基于提供的小说大纲与世界观，设计主角、关键配角与反派的完整人设卡。"
            "硬约束："
            "1) 输出严格合法 JSON：{\"characters\": [{\"name\": 名, \"role\": 身份, "
            "\"personality\": 性格, \"motivation\": 动机, \"current_status\": 当前状态, "
            "\"growth_arc\": 成长弧, \"level\": 境界/实力层级, \"mood\": 当前心境, "
            "\"equipment\": 装备/法宝, \"location\": 当前所在地, \"faction\": 所属势力"
            "(必须引用已提供的世界观势力之一), \"appearance\": 外貌特征, "
            "\"weakness\": 弱点/软肋, \"relationships\": 与其他角色的关系网}]}，不得附加说明；"
            "2) role 取值仅限：主角 / 配角 / 反派 / 势力代表；"
            "3) **反派必须具备独立动机**：不可纯恶脸谱化，其目标应与主角成长弧在中段产生真实冲突与交汇；"
            "4) 角色数量由提供的大纲事件推导决定，不得为凑数生硬增加；"
            "5) faction 必须引用已提供的世界观势力（或注明「无阵营」），禁止凭空新造未在设定中的势力；"
            "6) 人物动机与 premise 一致，成长弧光覆盖全书；禁止擅自新增与设定矛盾的亲属关系。"
        )

    def build_user_prompt(self, *, novel_id: str, premise: str = "", genre: str = "",
                          outline_json: Any = None, world_settings: Any = None, **_: Any) -> str:
        parts = [f"novel_id={novel_id}", f"题材：{genre}", f"核心设定：{premise}"]
        if world_settings:
            parts.append("世界观设定（势力/种族等）：\n" + _json_str(world_settings))
        if outline_json:
            parts.append("当前大纲（据此推导需要哪些角色及各自出场节点）：\n" + _json_str(outline_json))
        parts.append("请生成人设卡，仅输出 JSON。")
        return "\n\n".join(parts)


def _json_str(obj: Any) -> str:
    import json
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return str(obj)
