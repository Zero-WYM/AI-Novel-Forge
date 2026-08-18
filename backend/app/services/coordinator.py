"""
Coordinator（多 Agent 协调器）：2.0 的唯一编排入口，替代 novel.py 内联调用。

两条流水线：
1) 创建新书：WorldBuilder → RAG(world) → PlotArchitect(Pass-1 骨架)
   → CharacterDesigner(消费大纲+世界观) → PlotArchitect(Pass-2 细化，大纲跟随角色)
   → 落库大纲/角色。
2) 生成单章：RAG context → ChapterWriter → ConflictEditor(四维评分，<24 打回)
   → 最多 2 次重写 → 落库 → MemoryKeeper(更新角色/伏笔)。

所有 Agent 调用经本层，便于调用链日志与重试控制。
"""
from __future__ import annotations
import asyncio
import logging
import uuid

from app.memory.memory_manager import MemoryManager, t_novel
from app.schemas.novel import WorldSettings, CharacterState
from app.agents.world_builder import WorldBuilder
from app.agents.plot_architect import PlotArchitect
from app.agents.character_designer import CharacterDesigner
from app.agents.chapter_writer import ChapterWriter
from app.agents.conflict_editor import ConflictEditor
from app.agents.memory_keeper import MemoryKeeper
from app.rag.retriever import retrieve_for_generation

logger = logging.getLogger("coordinator")

MAX_REWRITE = 2               # 审校打回最多重写次数
REVIEW_PASS_THRESHOLD = 24    # 四维总分(满分40) < 24 视为不达标打回
_INTER_LLM_PAUSE = 3          # 流水线 4 步 LLM 之间各留缓冲，避免突发撞智谱 429


def _volumes_from_outline(outline_json) -> list:
    """兼容新 dict / 旧 list / None。"""
    if isinstance(outline_json, dict):
        return outline_json.get("volumes", outline_json.get("outline", []))
    if isinstance(outline_json, list):
        return outline_json
    return []


def _list_str_field_names(model_cls) -> set[str]:
    """从 Pydantic 模型反射出声明为 list[str] 的字段名集合。

    WorldSettings 是混合类型：cultivation/maps/factions/treasures/races 是 list[str]，
    entries 是 list[WorldSettingItem]。归一化只对前者生效——后者保留 dict 让 Pydantic
    校验成模型实例。
    """
    import typing
    out: set[str] = set()
    for name, field in model_cls.model_fields.items():
        ann = field.annotation
        if ann is None:
            continue
        origin = typing.get_origin(ann)
        if origin is list:
            args = typing.get_args(ann)
            if args and args[0] is str:
                out.add(name)
    return out


# 模块级缓存：WorldSettings 声明为 list[str] 的字段集合（cultivation/maps/factions/treasures/races）
_WORLD_LIST_STR_FIELDS = _list_str_field_names(WorldSettings)


def _flatten_dict_items_in_lists(d: dict, *, list_str_fields: set[str]) -> dict:
    """把 dict 内 **被 schema 声明为 list[str] 的字段** 里出现的 dict 元素压平为
    "k=v; k=v" 单行字符串。

    用途：WorldBuilder 的 schema 部分字段声明 list[str]，但 LLM 经常对结构化字段
    （如 factions）自作主张输出 list[dict]（每项带 name / politics / role 等）。
    本函数在 validate 之前把这些 dict 压平为单行字符串，让 schema 校验不必因为
    LLM 输出格式微调而频繁变动；同时 list[Model] 等非 list[str] 字段保持原样
    让 Pydantic 按模型 schema 校验。

    - 仅作用于 list_str_fields 集合内的字段；
    - 其他 list / dict / 标量字段保持原样。
    """
    if not isinstance(d, dict):
        return d
    out = {}
    for k, v in d.items():
        if k in list_str_fields and isinstance(v, list):
            new_list = []
            for item in v:
                if isinstance(item, dict):
                    parts: list[str] = []
                    for kk, vv in item.items():
                        if vv is None or vv == "":
                            continue
                        if isinstance(vv, (list, tuple)):
                            joined = ", ".join(str(x) for x in vv
                                               if x not in (None, ""))
                            if joined:
                                parts.append(f"{kk}={joined}")
                        elif isinstance(vv, dict):
                            parts.append(f"{kk}={{...}}")  # 嵌套过深，避免失控
                        else:
                            parts.append(f"{kk}={vv}")
                    new_list.append("; ".join(parts) if parts else str(item))
                else:
                    new_list.append(item)
            out[k] = new_list
        else:
            out[k] = v
    return out


class Coordinator:
    def __init__(self, mm: MemoryManager):
        self.mm = mm

    # ----------------------------- 创建新书流水线 -----------------------------
    async def create_book_pipeline(self, novel_id: str) -> dict:
        nov = await self.mm.get_novel(novel_id)
        if not nov:
            raise ValueError("小说不存在")
        settings = {k: nov.get(k) for k in ("title", "genre", "premise", "style")}
        steps: list[str] = []

        # 1) WorldBuilder → 落库 + 写 RAG
        wb = WorldBuilder()
        world_raw = await wb.run_json(
            novel_id=novel_id, premise=settings.get("premise", ""), genre=settings.get("genre", ""))
        if world_raw is None:
            raise RuntimeError(
                "WorldBuilder 模型输出无法解析为世界观 JSON（请检查模型返回是否为合法 JSON）")
        # LLM 经常把 factions/geography 等结构化字段展开为 list[dict]（每项带 name + 子字段），
        # 而 schema 声明 list[str]。用归一化器压平为 "k=v; k=v" 单行字符串后再 validate。
        # 仅对 schema 中 list[str] 字段生效，list[Model] 字段（如 entries）保持原样。
        try:
            ws = WorldSettings.model_validate(
                _flatten_dict_items_in_lists(world_raw, list_str_fields=_WORLD_LIST_STR_FIELDS))
        except Exception as e:
            raise RuntimeError(f"WorldBuilder 输出不符合世界观 schema：{e}") from e
        await self.mm.save_world_settings(novel_id, ws.model_dump())
        # 写入 RAG：ingest_world_rag 内部会先清空旧 world collection 再写入，幂等可重复点。
        # Chroma 的 add 含磁盘 IO + 嵌入推理（CPU 重活），用 to_thread 避免阻塞事件循环。
        await asyncio.to_thread(
            self.mm.ingest_world_rag, novel_id, [e.model_dump() for e in ws.entries])
        steps.append("world")
        await asyncio.sleep(_INTER_LLM_PAUSE)  # 4 步间各留缓冲，避免突发撞 429

        # 2) PlotArchitect Pass-1：大纲骨架（角色占位）
        #    M2：若用户已通过「仅生成大纲」产出单遍大纲，则直接复用为 Pass-1 输入，
        #    避免重复劳动，也避免 bootstrap 把已有大纲覆盖掉。
        arch = PlotArchitect()
        existing_outline = nov.get("outline_json")
        if existing_outline and _volumes_from_outline(existing_outline):
            pass1 = existing_outline
            steps.append("outline_reuse")
        else:
            pass1 = await arch.run_json(novel_id=novel_id, novel_settings=settings, pass_no=1)
            steps.append("outline_pass1")
        await asyncio.sleep(_INTER_LLM_PAUSE)

        # 3) CharacterDesigner：消费 Pass-1 大纲 + 世界观 → 人设卡
        designer = CharacterDesigner()
        chars_raw = await designer.run_json(
            novel_id=novel_id, premise=settings.get("premise", ""), genre=settings.get("genre", ""),
            outline_json=pass1, world_settings=ws.model_dump())
        chars = (chars_raw or {}).get("characters", []) if isinstance(chars_raw, dict) else []
        char_states = [CharacterState.model_validate(c) for c in chars]
        await self.mm.save_characters(novel_id, [c.model_dump() for c in char_states])
        steps.append("characters")
        await asyncio.sleep(_INTER_LLM_PAUSE)

        # 4) PlotArchitect Pass-2：消费人设卡 → 细化大纲（大纲跟随角色）
        char_dump = [c.model_dump() for c in char_states]
        pass2 = await arch.run_json(
            novel_id=novel_id, novel_settings=settings, pass_no=2, characters=char_dump)
        steps.append("outline_pass2")

        # 落库最终大纲（完整结构）
        final = pass2 if isinstance(pass2, dict) else _volumes_from_outline(pass2)
        async with self.mm._sf() as s:
            await s.execute(t_novel.update().where(t_novel.c.id == novel_id)
                            .values(outline_json=final))
            await s.commit()

        logger.info("create_book_pipeline done: novel=%s steps=%s chars=%d",
                    novel_id, steps, len(char_states))
        return {
            "novel_id": novel_id, "steps": steps,
            "character_count": len(char_states),
            "outline_volumes": len(_volumes_from_outline(final)),
        }

    # ----------------------------- 记忆后处理（与 /update-memory 端点共用） -----------------------------
    async def apply_memory_updates(self, novel_id: str, mem_raw: dict, chapter_no: int = 0) -> dict:
        """解析 MemoryKeeper 输出并落库：更新角色状态、埋设/回收伏笔。

        供 generate_chapter_pipeline 与 /update-memory 端点复用，避免两处各写一遍导致漂移。
        返回统计：{character_updates, planted_foreshadows, resolved_foreshadows}。
        """
        if not isinstance(mem_raw, dict):
            raise ValueError("记忆更新结果不是合法的 JSON 对象")
        char_updates: list[dict] = []
        for u in mem_raw.get("character_updates", []) or []:
            name = u.get("name")
            new_state = u.get("new") or {}
            if name and isinstance(new_state, dict):
                await self.mm.update_character(novel_id, name, new_state)
                char_updates.append(u)
        fs = mem_raw.get("foreshadows", {}) or {}
        planted_ids: list[str] = []
        for p in fs.get("planted", []) or []:
            fid = uuid.uuid4().hex[:12]
            await self.mm.add_foreshadow(novel_id, {
                "id": fid, "description": p.get("description", ""),
                "planted_chapter": p.get("planted_chapter", chapter_no),
                "expected_resolve_chapter": p.get("expected_resolve_chapter"),
                "status": "open"})
            planted_ids.append(fid)
        resolved_ids: list[str] = []
        for r in fs.get("resolved", []) or []:
            rid = r.get("id")
            if rid and await self.mm.resolve_foreshadow(rid, r.get("resolved_chapter", chapter_no)):
                resolved_ids.append(rid)
        return {
            "character_updates": char_updates,
            "planted_foreshadows": planted_ids,
            "resolved_foreshadows": resolved_ids,
        }

    # ----------------------------- 生成单章流水线 -----------------------------
    async def generate_chapter_pipeline(self, novel_id: str, chapter_no: int) -> dict:
        ctx = await self.mm.build_generation_context(novel_id, chapter_no)
        novel = ctx.get("novel") or {}
        chap_meta = {"chapter": chapter_no, "title": f"第 {chapter_no} 章",
                     "hook": "", "climax": "", "word_count": 2500}
        for vol in _volumes_from_outline(novel.get("outline_json")):
            for c in vol.get("chapters", []):
                if c.get("chapter") == chapter_no:
                    chap_meta.update(c)
                    break

        rag_ctx = await asyncio.to_thread(
            retrieve_for_generation, novel_id, f"{novel.get('title', '')} 第 {chapter_no} 章")

        writer = ChapterWriter()
        attempt = 0
        result = await writer.write(chapter_meta=chap_meta, memory_ctx=ctx, rag_context=rag_ctx)
        content = result["content"]
        last_review: dict | None = None
        last_total = 0

        # 审校 + 自动重写（≤2 次）
        while attempt <= MAX_REWRITE:
            editor = ConflictEditor()
            review = await editor.run_json(
                novel_id=novel_id, chapter_no=chapter_no, chapter_text=content,
                max_tokens=2000)
            last_review = review if isinstance(review, dict) else {}
            scores = last_review.get("scores", {})
            last_total = last_review.get("total") or sum(
                int(v) for v in scores.values() if isinstance(v, (int, float)))
            if last_total >= REVIEW_PASS_THRESHOLD or attempt == MAX_REWRITE:
                break
            # 打回重写：把审校意见注入 writer
            hint = last_review.get("suggestion", "")
            hint += "\n" + "\n".join(
                f"- {i.get('problem', '')}（修改建议：{i.get('fix', '')}）"
                for i in last_review.get("issues", []))
            attempt += 1
            result = await writer.write(
                chapter_meta=chap_meta, memory_ctx=ctx, rag_context=rag_ctx, rewrite_hint=hint)
            content = result["content"]

        # 落库章节
        summary = await writer.llm.generate(
            content, system="用 60 字以内概括以下章节的核心进展，中文。",
            max_tokens=120, temperature=0.3)
        await self.mm.save_chapter(
            novel_id, chapter_no, chap_meta.get("title", ""), content, summary, len(content))
        # H1：把本章正文写入 RAG chapter 集合，供后续章节跨章召回（重生成幂等 upsert）。
        await asyncio.to_thread(
            self.mm.ingest_chapter_rag, novel_id, chapter_no,
            chap_meta.get("title", ""), content)

        # MemoryKeeper：更新角色状态 / 伏笔
        keeper = MemoryKeeper()
        open_fs = await self.mm.list_foreshadows(novel_id, status="open")
        chars = await self.mm.list_characters(novel_id)
        mem_raw = await keeper.run_json(
            novel_id=novel_id, chapter_no=chapter_no, chapter_text=content,
            characters=chars, open_foreshadows=open_fs)
        if isinstance(mem_raw, dict):
            await self.apply_memory_updates(novel_id, mem_raw, chapter_no)

        forced_accept = last_total < REVIEW_PASS_THRESHOLD
        logger.info("generate_chapter_pipeline done: novel=%s ch=%d attempts=%d total=%d forced=%s",
                    novel_id, chapter_no, attempt, last_total, forced_accept)
        return {
            "novel_id": novel_id, "chapter_no": chapter_no,
            "title": chap_meta.get("title", ""), "content": content,
            "word_count": len(content), "meta": result.get("meta", {}),
            "review": last_review, "rewrite_attempts": attempt,
            "forced_accept": forced_accept, "retrieved_context": rag_ctx,
        }
