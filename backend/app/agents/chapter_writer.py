"""
ChapterWriter（章节写手）：根据大纲章节元信息 + 人设 + 世界观 + 前序摘要，
生成单章正文（2000-3000 字）。每次生成前由服务层自动触发 RAG 检索拼接上下文。

2.0 升级：
- 严格四段结构（开头/发展/爽点/收尾）、对话占比、禁 AI 味套话；
- 正文末尾附单行元数据行 [字数|本章爽点|本章伏笔]，由 write() 解析为 meta；
- 人设结构化字段（境界/势力/装备/外貌/弱点）注入。
"""
from __future__ import annotations
from typing import Any

from app.agents.base import BaseAgent


class ChapterWriter(BaseAgent):
    name = "ChapterWriter"
    tools = ["rag.retrieve_for_generation", "memory.build_generation_context"]

    def system_prompt(self) -> str:
        return (
            "你是资深网文爽文作家，擅长玄幻/修仙/都市异能类快节奏叙事。"
            "任务：根据【章节元信息】【人设与世界观】【前序摘要】创作一章正文。\n"
            "【章节结构】严格按四段推进：\n"
            "① 开头：从冲突/动作/悬念直接切入，≤150字入戏，禁止冗长背景交代；\n"
            "② 发展：推进剧情与人物关系，埋设伏笔；\n"
            "③ 爽点：本章必须出现至少一个明确爽点（打脸/突破/获宝/反转/装逼），详写情绪释放；\n"
            "④ 收尾：留钩子（悬念或新危机）引出下章。\n"
            "【对话与节奏】对话占比 25%-40%，避免大段独白；段落短、节奏快。\n"
            "【文风】口语化、画面感强，禁止 AI 味套话（如『就在这时』『不由得』『仿佛一切都注定』），禁止空泛抒情。\n"
            "【防幻觉】严格沿用提供的人物性格/势力/功法，禁止擅自新增主角亲属、新势力、新功法或与原设定矛盾的情节。\n"
            "【输出格式】仅小说正文纯文本（中文，2000-3000字），不要 JSON/Markdown/元注释；"
            "正文结束后另起一行，用单行元数据行收尾，格式严格为：[字数|本章爽点|本章伏笔]，"
            "例如：[2600|反杀长老打脸|神秘玉佩来历]。"
        )

    def build_user_prompt(self, *, chapter_meta: dict, memory_ctx: dict,
                           rag_context: list[str], rewrite_hint: str = "", **_: Any) -> str:
        novel = memory_ctx.get("novel", {}) or {}
        chars = memory_ctx.get("characters", []) or []
        fores = memory_ctx.get("open_foreshadows", []) or []
        recents = memory_ctx.get("recent_summaries", []) or []

        parts: list[str] = []
        parts.append("【小说信息】")
        parts.append(f"书名：{novel.get('title','')}｜类型：{novel.get('genre','')}｜风格：{novel.get('style','')}")
        parts.append(f"核心设定：{novel.get('premise','')}")

        parts.append("\n【本章元信息】")
        parts.append(f"第 {chapter_meta.get('chapter')} 章《{chapter_meta.get('title')}》")
        parts.append(f"开篇钩子：{chapter_meta.get('hook')}")
        parts.append(f"中段发展：{chapter_meta.get('development','')}")
        parts.append(f"本章高潮：{chapter_meta.get('climax')}")
        parts.append(f"章末钩子：{chapter_meta.get('ending_hook','')}")
        parts.append(f"目标字数：{chapter_meta.get('word_count', 2500)}")

        if chars:
            parts.append("\n【登场人物（人设卡，须严格遵循）】")
            for c in chars:
                parts.append(
                    f"- {c.get('name')}（{c.get('role')}）：性格 {c.get('personality')}；"
                    f"动机 {c.get('motivation')}；当前状态 {c.get('current_status')}；"
                    f"境界 {c.get('level')}；所属 {c.get('faction')}；"
                    f"装备 {c.get('equipment')}；外貌 {c.get('appearance')}；弱点 {c.get('weakness')}"
                )

        if fores:
            parts.append("\n【未回收伏笔（可在本章呼应，不得与设定矛盾）】")
            for f in fores:
                parts.append(f"- {f.get('description')}（埋于第 {f.get('planted_chapter')} 章）")

        if recents:
            parts.append("\n【前序剧情摘要（保持连续性）】")
            for i, s in enumerate(recents, 1):
                parts.append(f"· 第 {i} 段：{s}")

        if rag_context:
            parts.append("\n【检索到的相关设定/同类爽文片段（仅作参考，不照抄）】")
            for r in rag_context[:6]:
                parts.append(f"· {r}")

        parts.append("\n请直接输出本章小说正文（中文，2000-3000 字），并在末尾附元数据行。")
        if rewrite_hint:
            parts.append("\n【审校重写要求】上一版审校不达标，请重点针对以下意见修改后重写：\n" + rewrite_hint)
        return "\n".join(parts)

    # ----------------------- 2.0：带元数据的生成 -----------------------
    async def write(self, *, chapter_meta: dict, memory_ctx: dict, rag_context: list[str],
                   rewrite_hint: str = "") -> dict:
        """生成单章正文并返回 {content, meta}；meta 由末尾元数据行解析。rewrite_hint 用于审校打回后的重写。"""
        user = self.build_user_prompt(
            chapter_meta=chapter_meta, memory_ctx=memory_ctx, rag_context=rag_context,
            rewrite_hint=rewrite_hint)
        # 中文 2500-3000 字 ≈ 3000-5000 token，max_tokens=4000 会砍掉章尾甚至元数据行；
        # 提到 6000 留足余量（含末尾 [字数|爽点|伏笔] 元数据行）。
        raw = await self.llm.generate(self.system_prompt(), user, max_tokens=6000, temperature=0.9)
        content, meta = self._parse_meta(raw)
        return {"content": content, "meta": meta}

    @staticmethod
    def _parse_meta(raw: str) -> tuple[str, dict]:
        """解析末尾元数据行 [字数|爽点|伏笔]，返回 (正文, 元数据dict)。"""
        lines = raw.rstrip().split("\n")
        meta: dict = {}
        if lines and lines[-1].strip().startswith("[") and "|" in lines[-1]:
            row = lines[-1].strip().strip("[]")
            parts = [p.strip() for p in row.split("|")]
            raw_wc = parts[0] if parts else ""
            meta = {
                "word_count": int(raw_wc) if raw_wc.isdigit() else raw_wc,
                "cool_points": parts[1] if len(parts) > 1 else "",
                "foreshadows": parts[2] if len(parts) > 2 else "",
            }
            content = "\n".join(lines[:-1]).strip()
        else:
            content = raw.strip()
        if not isinstance(meta.get("word_count"), int):
            meta["word_count"] = len(content)
        return content, meta
