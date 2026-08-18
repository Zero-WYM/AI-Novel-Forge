"""
数据库引擎与 ORM 基类（SQLAlchemy 2.x 异步）。
表结构（Novel / Chapter / Character / Foreshadow / WorldEntry / StageSummary）
在 memory_manager.py 中以 Table 定义注册，统一由 init_db() 建表（create_all + ALTER 补齐列）。
"""
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker

from app.core.config import settings

engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():
    """FastAPI 依赖：异步会话。"""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """建表（开发环境简化）；并对已有库无痛补齐 2.0 新增列。

    先 create_all 建缺失的表，再对既有表 ALTER ADD COLUMN IF NOT EXISTS，
    避免本地从 1.0 升级时因缺列导致查询报错（PostgreSQL / SQLite 均支持 IF NOT EXISTS）。
    """
    from sqlalchemy import MetaData, text
    from app.memory.memory_manager import METADATA
    async with engine.begin() as conn:
        await conn.run_sync(METADATA.create_all)
        # 2.0 新增列补齐（列已存在时 IF NOT EXISTS 不会报错）
        alter_cmds = [
            "ALTER TABLE novels ADD COLUMN IF NOT EXISTS owner_id VARCHAR",
            "ALTER TABLE novels ADD COLUMN IF NOT EXISTS world_settings_json JSON",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS level VARCHAR",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS mood VARCHAR",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS equipment TEXT",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS location VARCHAR",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS faction VARCHAR",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS appearance TEXT",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS weakness TEXT",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS relationships TEXT",
            "ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS expected_resolve_chapter INTEGER",
            "ALTER TABLE foreshadows ADD COLUMN IF NOT EXISTS resolved_chapter INTEGER",
        ]
        for cmd in alter_cmds:
            try:
                await conn.execute(text(cmd))
            except Exception:
                # SQLite 旧版本不支持 IF NOT EXISTS 等场景：忽略（全新库本就不需要）
                pass
