"""
FastAPI 应用入口。
启动：uvicorn app.main:app --reload --port 8000
交互文档：http://localhost:8000/docs
"""
from __future__ import annotations
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import novel as novel_api
from app.api import rag_query as rag_api
from app.api import config as config_api
from app.api import auth as auth_api
from app.models.db import init_db
from app.core.runtime_config import load_runtime

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建表（开发环境）
    await init_db()
    # 加载全局模型设置（前端面板保存的 / .env 默认）
    await load_runtime()
    yield


app = FastAPI(
    title="AI Novel Forge",
    description="全栈多 Agent 网文（爽文/玄幻）自动创作系统 · MVP 后端",
    version="0.1.0",
    lifespan=lifespan,
)

# 允许的来源：默认本地开发；线上把域名写进环境变量 CORS_ORIGINS（逗号分隔）。
# 生产用 nginx 同源反代时其实不会触发 CORS，这里保留以便未来前后端分离。
_cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

app.include_router(auth_api.router)
app.include_router(novel_api.router)
app.include_router(rag_api.router)
app.include_router(config_api.router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-novel-forge"}
