"""
Agent 基类：统一 LLM 调用、工具注册、输出解析。
各业务 Agent 继承并实现 system_prompt() / build_user_prompt()。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from app.core.llm_client import LLMClient


class BaseAgent(ABC):
    name: str = "base"
    # 子类可声明可调用工具名列表（MVP 阶段以 LLM 工具调用占位，后续接入 function calling）
    tools: list[str] = []

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient()

    @abstractmethod
    def system_prompt(self) -> str:
        """返回该 Agent 的 system prompt（含角色边界 + 防幻觉 + 输出格式约束）。"""

    @abstractmethod
    def build_user_prompt(self, **kwargs: Any) -> str:
        """根据输入参数组装 user prompt。"""

    async def run(self, **kwargs: Any) -> str:
        """默认执行：调 LLM 并返回文本。"""
        return await self.llm.generate(self.system_prompt(), self.build_user_prompt(**kwargs))

    async def run_json(self, **kwargs: Any) -> Any:
        """要求模型输出合法 JSON 并解析为 dict。"""
        return await self.llm.generate_json(self.system_prompt(), self.build_user_prompt(**kwargs))
