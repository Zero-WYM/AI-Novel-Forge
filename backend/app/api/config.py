# -*- coding: utf-8 -*-
"""模型运行配置接口：前端「模型设置」面板读写。"""
from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from app.core.runtime_config import (
    get_runtime,
    save_runtime,
    mask_key,
    ModelSettings,
)
from app.api.auth import require_access

router = APIRouter(prefix="/api/config", tags=["config"], dependencies=[Depends(require_access)])


class ModelConfigIn(BaseModel):
    api_key: str = ""        # 留空表示不修改（保留现有 Key）
    base_url: str
    model: str
    embed_model: str = ""


@router.get("/model")
async def get_model_config():
    """返回当前生效的模型设置；API Key 脱敏。"""
    cfg = get_runtime()
    return {
        "api_key_set": bool(cfg.api_key),
        "api_key_masked": mask_key(cfg.api_key),
        "base_url": cfg.base_url,
        "model": cfg.model,
        "embed_model": cfg.embed_model,
    }


@router.put("/model")
async def update_model_config(body: ModelConfigIn):
    """更新模型设置并持久化。api_key 留空则保留现有值。"""
    if not body.base_url or not body.model:
        raise HTTPException(status_code=422, detail="Base URL 与模型名均为必填")

    cur = get_runtime()
    api_key = body.api_key.strip() if body.api_key else ""
    # 首次必须提供 Key；后续留空则沿用
    if not api_key and not cur.api_key:
        raise HTTPException(status_code=422, detail="首次配置必须填写 API Key")
    api_key = api_key or cur.api_key

    new = ModelSettings(
        api_key=api_key,
        base_url=body.base_url.strip(),
        model=body.model.strip(),
        embed_model=(body.embed_model or cur.embed_model or "embedding-3").strip(),
    )
    await save_runtime(new)
    return {"ok": True, "model": new.model, "base_url": new.base_url}
