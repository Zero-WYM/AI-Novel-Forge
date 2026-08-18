# -*- coding: utf-8 -*-
"""
LLM 调用封装（OpenAI 兼容协议）。

配置（API Key / Base URL / 模型名）从 runtime_config 实时读取，
因此前端「模型设置」面板可自由切换服务商（智谱 / DeepSeek / OpenAI / 通义等
任意 OpenAI 格式 endpoint），无需重启。底层用官方 openai SDK 的同步客户端，
在线程池执行避免阻塞事件循环。
"""
import json
import re
import asyncio
import logging
from typing import Any

from openai import OpenAI, RateLimitError
from fastapi import HTTPException

from app.core.config import settings
from app.core.runtime_config import get_runtime

logger = logging.getLogger(__name__)

# 429 速率限制重试：1 次原始 + 4 次重试，间隔 10/20/40/60 秒（共约 130s）。
RATE_LIMIT_RETRIES = 4
RATE_LIMIT_BACKOFFS = (10, 20, 40, 60)

# client 缓存：key=(api_key, base_url)，避免每次请求重建。
_client_cache: dict[tuple[str, str], OpenAI] = {}


def _get_client(api_key: str, base_url: str) -> OpenAI:
    key = (api_key, base_url)
    client = _client_cache.get(key)
    if client is None:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=settings.LLM_TIMEOUT)
        _client_cache[key] = client
    return client


def _parse_json_response(text: str | None) -> dict | None:
    """把 LLM 返回的（可能带 ```json 围栏的）文本解析为 dict；失败返回 None。"""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


class LLMClient:
    """OpenAI 兼容客户端封装（无状态；配置从 runtime_config 实时读取）。"""

    def _build_params(
        self,
        prompt: str,
        system: str = "",
        *,
        temperature: float = settings.LLM_TEMPERATURE,
        max_tokens: int = settings.LLM_MAX_TOKENS,
        json_mode: bool = False,
    ) -> dict:
        cfg = get_runtime()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        params: dict[str, Any] = {
            "model": cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        return params

    async def generate(
        self,
        prompt: str,
        system: str = "",
        *,
        temperature: float = settings.LLM_TEMPERATURE,
        max_tokens: int = settings.LLM_MAX_TOKENS,
        json_mode: bool = False,
    ) -> str:
        cfg = get_runtime()
        if not cfg.api_key:
            raise RuntimeError(
                "未配置模型 API Key，请在前端「模型设置」中填写"
                "（或在 backend/.env 设置 ZHIPU_API_KEY）"
            )
        client = _get_client(cfg.api_key, cfg.base_url)
        params = self._build_params(
            prompt, system,
            temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
        )

        last_err: Exception | None = None
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                # openai SDK 的 chat.completions.create 为同步接口，在线程池执行避免阻塞事件循环
                resp = await asyncio.to_thread(
                    client.chat.completions.create, **params)
                return resp.choices[0].message.content or ""
            except RateLimitError as e:  # 智谱/OpenAI 统一 429
                last_err = e
                if attempt < RATE_LIMIT_RETRIES:
                    wait = RATE_LIMIT_BACKOFFS[attempt]
                    logger.warning(
                        "LLM 429 速率限制，第 %d/%d 次重试前等 %ds：%s",
                        attempt + 1, RATE_LIMIT_RETRIES + 1, wait, str(e)[:200])
                    await asyncio.sleep(wait)
                    continue
                # 已用尽重试次数：抛 429（而非裸 500），让前端显示「请稍后重试」友好提示
                logger.error("LLM 429 重试 %d 次仍失败，向上抛 429：%s",
                             RATE_LIMIT_RETRIES, str(e)[:300])
                raise HTTPException(
                    status_code=429,
                    detail="⏳ API 服务拥堵，请稍后重试（当前模型访问量较大，"
                           "稍等片刻再点即可）",
                ) from e
        # 理论不会到这里（循环要么 return 要么 raise），写防御性 raise
        raise last_err  # type: ignore[misc]

    async def generate_json(self, prompt: str, system: str = "", **kwargs) -> dict | None:
        """强制 JSON 输出并解析为 dict；解析失败返回 None（由业务层统一处理）。"""
        text = await self.generate(prompt, system, json_mode=True, **kwargs)
        return _parse_json_response(text)


def get_llm() -> LLMClient:
    return LLMClient()
