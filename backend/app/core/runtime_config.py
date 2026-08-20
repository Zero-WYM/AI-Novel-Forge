# -*- coding: utf-8 -*-
"""
全局模型运行配置（API Key / Base URL / 模型名）。

优先从数据库 app_config 表加载（用户在前端「模型设置」面板保存的），
若库内为空则用 .env 的默认值预热。支持运行时热更新（PUT /api/config/model），
无需重启服务即可切换服务商 / 模型。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict

from sqlalchemy import text

from app.core.config import settings
from app.models.db import engine


@dataclass
class ModelSettings:
    api_key: str = ""
    base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    model: str = "glm-4.7-flash"
    embed_model: str = "embedding-3"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


# 模块级单例：进程内当前生效的配置
_runtime: ModelSettings | None = None

# .env 默认值（首启动时预热进库）
_DEFAULT = ModelSettings(
    api_key=settings.ZHIPU_API_KEY,
    base_url=settings.ZHIPU_BASE_URL,
    model=settings.ZHIPU_MODEL,
    embed_model=settings.ZHIPU_EMBED_MODEL,
)


def get_runtime() -> ModelSettings:
    """返回当前生效配置；若尚未加载则退回 .env 默认（不写库）。"""
    return _runtime or _DEFAULT


async def load_runtime() -> ModelSettings:
    """启动时从 app_config 表加载；为空则用默认并写回。表未建等异常安全退回默认。"""
    global _runtime
    try:
        async with engine.connect() as conn:
            row = await conn.execute(
                text("SELECT value FROM app_config WHERE key = 'model_settings'"))
            rec = row.fetchone()
        if rec and rec[0]:
            data = json.loads(rec[0])
            _runtime = ModelSettings(
                api_key=data.get("api_key", _DEFAULT.api_key),
                base_url=data.get("base_url", _DEFAULT.base_url),
                model=data.get("model", _DEFAULT.model),
                embed_model=data.get("embed_model", _DEFAULT.embed_model),
            )
            return _runtime
    except Exception:
        # 表尚未建立等异常：退回默认，不阻断启动
        pass
    _runtime = _DEFAULT
    await save_runtime(_runtime)
    return _runtime


async def save_runtime(s: ModelSettings) -> None:
    """持久化到 app_config 表（DELETE + INSERT，跨 PG/SQLite 兼容）。"""
    global _runtime
    _runtime = s
    payload = json.dumps(asdict(s), ensure_ascii=False)
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM app_config WHERE key = 'model_settings'"))
        await conn.execute(
            text("INSERT INTO app_config(key, value) VALUES ('model_settings', :v)"),
            {"v": payload},
        )


def mask_key(key: str) -> str:
    """API Key 脱敏：保留前 4 后 4，中间打码。"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def parse_user_model_settings(user: dict) -> ModelSettings | None:
    """从 user dict 解析其个人模型设置；无 Key 或为空返回 None。"""
    raw = user.get("model_settings_json")
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if not isinstance(raw, dict) or not raw.get("api_key"):
        return None
    return ModelSettings(
        api_key=raw.get("api_key", ""),
        base_url=raw.get("base_url", ""),
        model=raw.get("model", ""),
        embed_model=raw.get("embed_model", ""),
    )


def resolve_user_settings(user: dict) -> ModelSettings:
    """返回当前用户生效的模型设置：有个人 Key 用个人，否则回落站点兜底（.env / app_config）。"""
    own = parse_user_model_settings(user)
    return own if own else get_runtime()
