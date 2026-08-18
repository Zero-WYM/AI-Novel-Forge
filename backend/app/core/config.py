# -*- coding: utf-8 -*-
"""
应用配置（Settings）。

环境变量命名与 .env / README 保持一致：
  ZHIPU_API_KEY / ZHIPU_MODEL / ZHIPU_EMBED_MODEL
  LLM_TEMPERATURE / LLM_MAX_TOKENS / LLM_TIMEOUT
  CHROMA_PERSIST_DIR / DATABASE_URL
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # 智谱 GLM-4 API
    ZHIPU_API_KEY: str = Field("", description="智谱 API Key（必填）")
    ZHIPU_MODEL: str = Field("glm-4.7-flash", description="使用的模型名称")
    ZHIPU_EMBED_MODEL: str = Field("embedding-3", description="向量模型名称（当前 RAG 用本地嵌入，此项预留）")

    # OpenAI 兼容协议 Base URL：智谱默认填其 OpenAI 兼容端点；
    # 换 DeepSeek/OpenAI/通义等时填对应地址（如 https://api.deepseek.com/v1）
    ZHIPU_BASE_URL: str = Field(
        "https://open.bigmodel.cn/api/paas/v4",
        description="OpenAI 兼容 API Base URL",
    )

    # 生成参数
    LLM_TEMPERATURE: float = Field(0.7, description="采样温度")
    LLM_MAX_TOKENS: int = Field(65536, description="最大生成 token 数")
    LLM_TIMEOUT: int = Field(120, description="HTTP 超时时间（秒）")

    # RAG / 向量数据库
    CHROMA_PERSIST_DIR: str = Field("./.chroma", description="ChromaDB 持久化目录")

    # 数据库（PG 异步 DSN；Docker 内使用服务名 postgres）
    DATABASE_URL: str = Field(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/novelforge",
        description="PostgreSQL 异步连接串",
    )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="allow")


# 全局单例，供各模块 import
settings = Settings()
