"""账号体系与 JWT 鉴权（B 方案：独立账号 + 数据隔离）。

- 开放注册：任何人可 `POST /api/auth/register` 创建账号（username 唯一）。
- 登录：`POST /api/auth/login` 校验密码，返回 JWT（HS256，有效期 30 天）。
- 业务路由依赖 `require_user`：解析 Bearer JWT，注入当前用户 dict；无效则 401。
- `SECRET_KEY` 读环境变量；未配置时回退开发默认值（仅本地，生产务必在 .env 配置）。
- 取代原 A 方案共享口令（`ACCESS_PASSWORD`）。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select

from app.models.db import SessionLocal
from app.memory.memory_manager import t_users

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

# 开放注册开关：默认开启（任何人可自助注册）；设为 false/0/no 则仅已有账号可登录。
ALLOW_OPEN_REGISTER = os.getenv("ALLOW_OPEN_REGISTER", "true").lower() not in ("0", "false", "no")

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ----------------------------- Schemas -----------------------------
class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str


# bcrypt 最大只支持 72 字节；超过会抛 ValueError，用户看不懂。这里统一拦截并转中文提示。
_MAX_PWD_BYTES = 72


def _check_password_length(p: str):
    if len(p.encode("utf-8")) > _MAX_PWD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="密码太长：最多支持 72 字节（约 24 个中文或 72 个英文字母），请缩短后重试")


def _hash_password(p: str) -> str:
    try:
        return _pwd.hash(p)
    except ValueError as exc:
        if "cannot be longer than" in str(exc):
            raise HTTPException(
                status_code=400,
                detail="密码太长：最多支持 72 字节（约 24 个中文或 72 个英文字母），请缩短后重试") from exc
        raise


def _verify_password(p: str, h: str) -> bool:
    try:
        return _pwd.verify(p, h)
    except ValueError as exc:
        if "cannot be longer than" in str(exc):
            raise HTTPException(
                status_code=400,
                detail="密码太长：最多支持 72 字节（约 24 个中文或 72 个英文字母），请缩短后重试") from exc
        raise


def _create_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


async def _get_user_by_username(username: str):
    async with SessionLocal() as s:
        row = (await s.execute(
            select(t_users).where(t_users.c.username == username))).mappings().first()
    return dict(row) if row else None


async def _get_user_by_id(uid: str):
    async with SessionLocal() as s:
        row = (await s.execute(
            select(t_users).where(t_users.c.id == uid))).mappings().first()
    return dict(row) if row else None


# ----------------------------- 鉴权依赖（须先于使用它的路由定义） -----------------------------
async def _require_user(authorization: str | None = Header(default=None)) -> dict:
    """业务路由依赖：解析 Bearer JWT，返回当前用户 dict；无效则 401。

    供本模块及其他路由（novel / rag / config）import 使用。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
        if not uid:
            raise HTTPException(status_code=401, detail="无效令牌")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    user = await _get_user_by_id(uid)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


# 供其他路由 import 的依赖别名
require_user = _require_user
get_current_user = _require_user


# ----------------------------- 路由 -----------------------------
@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterRequest):
    if not ALLOW_OPEN_REGISTER:
        raise HTTPException(status_code=403, detail="注册已关闭，请联系管理员获取账号")
    if not body.username or not body.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    _check_password_length(body.password)
    if await _get_user_by_username(body.username):
        raise HTTPException(status_code=409, detail="用户名已被占用")
    user_id = os.urandom(12).hex()
    async with SessionLocal() as s:
        await s.execute(t_users.insert().values(
            id=user_id, username=body.username, password_hash=_hash_password(body.password)))
        await s.commit()
    return UserOut(id=user_id, username=body.username)


@router.post("/login")
async def login(body: LoginRequest):
    _check_password_length(body.password)
    user = await _get_user_by_username(body.username)
    if not user or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = _create_token(user["id"], user["username"])
    return {
        "authenticated": True,
        "token": token,
        "user": UserOut(id=user["id"], username=user["username"]),
    }


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(require_user)):
    return UserOut(id=user["id"], username=user["username"])
