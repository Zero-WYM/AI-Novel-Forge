"""共享访问口令鉴权（A 方案）。

所有人输入同一个 ACCESS_PASSWORD 才能访问业务接口，用于挡住外部陌生人。
- ACCESS_PASSWORD 未配置（本地开发）时不启用鉴权，请求直接放行，开发无感。
- 线上在服务器 .env 写入 ACCESS_PASSWORD=你的口令 即生效。
- 登录成功后返回的 token 即为该口令，前端存入 localStorage 并在后续请求头携带。
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 启动即读取一次；如需热更新改口令，重启后端容器即可（线上改动极小）。
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")


def auth_enabled() -> bool:
    return bool(ACCESS_PASSWORD)


class LoginRequest(BaseModel):
    password: str = ""


def require_access(authorization: str | None = Header(default=None)) -> None:
    """业务路由依赖：未启用则直接放行；启用后必须携带正确的 Bearer token。"""
    if not auth_enabled():
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    token = authorization.split(" ", 1)[1].strip()
    if token != ACCESS_PASSWORD:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")


@router.post("/login")
async def login(body: LoginRequest):
    if not auth_enabled():
        # 未启用鉴权：视为已登录，返回空 token（前端仍走统一逻辑）
        return {"authenticated": True, "token": "", "message": "未启用鉴权"}
    if body.password != ACCESS_PASSWORD:
        raise HTTPException(status_code=401, detail="访问口令错误")
    return {"authenticated": True, "token": ACCESS_PASSWORD}
