# -*- coding: utf-8 -*-
"""模型运行配置接口：前端「模型设置」面板读写。

B 方案下模型设置**按用户独立**：每个用户可填自己的 API Key / Base URL / 模型名，
仅自己生效；未填写个人 Key 时自动回落到站点兜底 Key（.env / app_config），互不干扰。
"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from app.core.runtime_config import (
    get_runtime,
    mask_key,
    ModelSettings,
)
from app.memory.memory_manager import MemoryManager
from app.models.db import SessionLocal
from app.api.auth import require_user

router = APIRouter(prefix="/api/config", tags=["config"], dependencies=[Depends(require_user)])


class ModelConfigIn(BaseModel):
    api_key: str = ""        # 留空表示不修改（保留现有个人 Key）；若无个人 Key 则沿用站点兜底
    base_url: str
    model: str
    embed_model: str = ""


@router.get("/model")
async def get_model_config(user: dict = Depends(require_user)):
    """返回当前用户生效的模型设置（个人优先，否则站点兜底）；API Key 脱敏。"""
    mm = MemoryManager(SessionLocal)
    own = await mm.get_user_model_settings(user["id"])
    if own and own.api_key:
        return {
            "has_own_key": True,
            "api_key_set": True,
            "api_key_masked": mask_key(own.api_key),
            "base_url": own.base_url,
            "model": own.model,
            "embed_model": own.embed_model,
        }
    fb = get_runtime()
    return {
        "has_own_key": False,
        "api_key_set": bool(fb.api_key),
        "api_key_masked": mask_key(fb.api_key),
        "base_url": fb.base_url,
        "model": fb.model,
        "embed_model": fb.embed_model,
    }


@router.put("/model")
async def update_model_config(body: ModelConfigIn, user: dict = Depends(require_user)):
    """更新当前用户的模型设置并持久化（覆盖式）。api_key 留空则沿用个人已有 Key。

    站点兜底 Key（.env / app_config）仍由 save_runtime 管理，仅管理员通过改 .env 重启生效。
    """
    if not body.base_url or not body.model:
        raise HTTPException(status_code=422, detail="Base URL 与模型名均为必填")

    mm = MemoryManager(SessionLocal)
    own = await mm.get_user_model_settings(user["id"]) or ModelSettings()
    api_key = body.api_key.strip() if body.api_key else ""
    # 填了 Key 则覆盖；留空则保留个人已有 Key（首次无 Key 则保持空，走站点兜底）
    if api_key:
        own.api_key = api_key
    own.base_url = body.base_url.strip()
    own.model = body.model.strip()
    own.embed_model = (body.embed_model or own.embed_model or "embedding-3").strip()
    await mm.save_user_model_settings(user["id"], own)
    return {
        "ok": True,
        "model": own.model,
        "base_url": own.base_url,
        "has_own_key": bool(own.api_key),
    }
