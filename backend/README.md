# AI Novel Forge · 后端（FastAPI）

## 启动

```bash
# .env 在仓库根目录（非 backend/），由 .env.example 复制而来。
# 本地裸跑需自备 PostgreSQL，或把根 .env 的 DATABASE_URL 改为
# sqlite+aiosqlite:///./dev.db 以零依赖运行。
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# 交互文档：http://localhost:8000/docs
```

> 表结构由 `SQLAlchemy Core` 的 `METADATA` 定义，经 `init_db()`（`app/models/db.py`）自动建表/补齐列；**不使用 Alembic，亦不使用 Redis**。

## 目录

```
app/
├── agents/   6 个业务 Agent（base + plot_architect/world_builder/character_designer/chapter_writer/conflict_editor/memory_keeper）
├── api/      novel.py（路由）+ rag_query.py
├── core/     config.py + llm_client.py（GLM-4.7-Flash 封装）
├── memory/   memory_manager.py（SQLAlchemy Core 表 + MemoryManager）
├── models/   db.py（异步引擎/Session，init_db 自动建表）
├── rag/      chroma_store.py + retriever.py（BM25+向量混合重排）
├── schemas/  novel.py（Pydantic v2）
├── services/ coordinator.py（2.0 编排层：创建新书两遍式 + 单章流水线）
└── main.py   FastAPI 入口
tests/        pytest（phase0-6 + smoke + e2e；桩 chromadb/zhipuai/asyncpg，无需真实 Key）
```

## 核心端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/novel/create | 创建新书（仅元数据） |
| GET  | /api/novel/list | 列出全部小说 |
| GET  | /api/novel/detail?novel_id= | 单本详情 |
| POST | /api/novel/bootstrap | 一键成书（Coordinator 创建流水线） |
| POST | /api/novel/generate-outline | 生成大纲（PlotArchitect，注入设定） |
| GET  | /api/novel/outline?novel_id= | 读取已存大纲（不重新生成） |
| POST | /api/novel/generate-world | 生成世界观 → 落库 + 写 RAG |
| GET  | /api/novel/world?novel_id= | 读取世界观 |
| PUT  | /api/novel/world | 作者手改世界观 |
| POST | /api/novel/generate-characters | 生成人设卡（CharacterDesigner） |
| GET  | /api/novel/characters?novel_id= | 角色状态列表 |
| POST | /api/novel/generate-chapter | 生成单章（Coordinator 单章流水线） |
| PUT  | /api/novel/{novel_id}/chapter/{chapter_no} | 作者手改章节 |
| POST | /api/novel/review-chapter | 审校章节（ConflictEditor，四维评分） |
| POST | /api/novel/update-memory | 章节后记忆更新（MemoryKeeper） |
| GET  | /api/novel/{novel_id}/chapters | 章节列表 |
| GET  | /api/novel/{novel_id}/foreshadows | 伏笔列表 |
| POST | /api/novel/{novel_id}/foreshadow | 新增伏笔 |
| GET  | /api/novel/memory?novel_id= | 记忆快照 |
| POST | /api/rag/rag-ingest | 注入文档到 RAG |
| POST | /api/rag/rag-query | RAG 检索 |
| GET  | /health | 健康检查 |
