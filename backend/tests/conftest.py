# -*- coding: utf-8 -*-
"""
共享测试夹具：统一 SQLite 库（避免各测试模块设置不同 DATABASE_URL 导致引擎绑定错乱），
并在每个测试前 drop_all + create_all 保证表结构干净。重型依赖（zhipuai/asyncpg）用桩模块。
"""
import os, sys
from unittest.mock import MagicMock

_STUB = os.path.join(os.path.dirname(__file__), "_stubs")
if _STUB not in sys.path:
    sys.path.insert(0, _STUB)

os.environ.setdefault("ZHIPU_API_KEY", "fake")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_shared.db"
sys.modules.setdefault("zhipuai", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())

import asyncio  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    from app.models.db import engine  # noqa: E402
    from app.memory.memory_manager import METADATA  # noqa: E402

    async def _go():
        async with engine.begin() as conn:
            await conn.run_sync(METADATA.drop_all)
            await conn.run_sync(METADATA.create_all)
        # 释放连接池，避免 aiosqlite 连接被绑定到本 reset 的临时事件循环，
        # 导致后续测试在各自事件循环中复用已关闭连接而报 OperationalError。
        await engine.dispose()

    asyncio.run(_go())
    yield
