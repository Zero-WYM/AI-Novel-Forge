# AI-Novel-Forge · 项目结构与最新状态快照 (v0.1 基线)
> 生成时间：2026-08-12 ｜ 用途：2.0 迭代前的"最新状态基线"。
> 后续对话直接引用本文件即可，无需回放历史长对话。
> 本文内容均以 2026-08-12 实际读取的源码为准（非 README 的旧描述）。

---

## 0. 一句话定位
RAG + 多 Agent 协作的网文自动创作系统（爽文/玄幻/修仙/都市异能）。
后端 FastAPI + SQLAlchemy(async Core) + ChromaDB + PostgreSQL；前端 Vue3 + Vite + Element Plus + Pinia。
底层 LLM：智谱 **GLM-4.7-Flash**（zhipuai SDK）。

---

## 1. 目录结构（2026-08-12 真实状态）
```
AI-Novel-Forge/
├── .env                         # 根目录真实配置（含 ZHIPU_API_KEY，仅本地）
├── README.md                    # ⚠️ 已过时（见 §6 差异清单）
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 入口（lifespan 建表 + 注册 2 个路由）
│   │   ├── agents/              # 6 个 Agent（见 §3.6）
│   │   │   ├── base.py
│   │   │   ├── plot_architect.py      # 已接入
│   │   │   ├── chapter_writer.py       # 已接入
│   │   │   ├── conflict_editor.py      # 已接入
│   │   │   ├── world_builder.py        # 未接入（stub）
│   │   │   ├── character_designer.py   # 未接入（stub）
│   │   │   └── memory_keeper.py        # 未接入（stub）
│   │   ├── api/
│   │   │   ├── novel.py         # 实际生效路由（prefix /api/novel）
│   │   │   ├── rag_query.py     # 实际生效路由（prefix /api/rag）
│   │   │   └── chapter.py       # ⚠️ 死代码（从未被 main.py 注册，见 §6.1）
│   │   ├── core/
│   │   │   ├── config.py        # Settings 单例（env 变量）
│   │   │   └── llm_client.py    # LLMClient 单例（generate/generate_json/stream_generate）
│   │   ├── memory/
│   │   │   └── memory_manager.py # SQLAlchemy Core Table + MemoryManager（5 张表 CRUD）
│   │   ├── models/
│   │   │   ├── db.py            # async engine + SessionLocal + init_db()
│   │   │   └── __init__.py      # 仅 re-export engine/session（无 ORM 模型）
│   │   ├── rag/
│   │   │   ├── chroma_store.py  # Chroma PersistentClient 封装
│   │   │   └── retriever.py     # BM25 + 向量混合检索
│   │   └── schemas/novel.py     # Pydantic v2 Schema
│   ├── alembic/                 # 迁移环境（env.py 引用 METADATA；与 init_db 并存）
│   ├── tests/                   # test_smoke.py / test_e2e.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue              # 左侧菜单 + 全局 loading 遮罩
│   │   ├── router/index.js      # 6 条路由
│   │   ├── stores/novel.js      # Pinia store（全局状态）
│   │   ├── utils/api.js         # axios 封装（baseURL=/api）
│   │   ├── vite.config.js       # /api → backend:8000 代理（不 rewrite）
│   │   └── views/               # 6 个视图（见 §4）
│   ├── package.json
│   └── index.html
├── shared/types.ts              # 前后端共享 TS 类型（与 schemas 一一对应）
└── deploy/
    ├── docker-compose.yml       # postgres + backend + frontend
    ├── Dockerfile.backend
    └── Dockerfile.frontend
```

---

## 2. 后端架构

### 2.1 入口 main.py
- `lifespan`：启动时 `init_db()` 建表（开发环境，METADATA.create_all）。
- CORS：`allow_origins=["http://localhost:5173","http://localhost:3000"]`。
- 注册路由：**仅** `novel_api.router`、`rag_api.router`。`chapter_api` 未注册。
- `GET /health` → `{"status":"ok","service":"ai-novel-forge"}`。

### 2.2 配置 core/config.py（Settings 单例）
| 变量 | 默认 | 说明 |
|---|---|---|
| ZHIPU_API_KEY | "" | 必填，运行时注入环境变量 ZHIPUAI_API_KEY |
| ZHIPU_MODEL | glm-4.7-flash | 模型名 |
| ZHIPU_EMBED_MODEL | embedding-3 | 向量模型 |
| LLM_TEMPERATURE | 0.7 | 采样温度 |
| LLM_MAX_TOKENS | 65536 | 最大生成 token |
| LLM_TIMEOUT | 120 | HTTP 超时（秒） |
| CHROMA_PERSIST_DIR | ./.chroma | Chroma 持久化目录 |
| DATABASE_URL | postgresql+asyncpg://postgres:postgres@localhost:5432/novelforge | PG 异步 DSN |

注：`.env` 中 LLM_TEMPERATURE=0.8、CHROMA=./.chroma，docker 内覆盖为 /tmp/ainovelforge_chroma。

### 2.3 LLM 客户端 core/llm_client.py
- `LLMClient` 单例（首次实例化要求 ZHIPU_API_KEY 非空、zhipuai 已装）。
- 公开方法：`generate(prompt, system, *, temperature, max_tokens, json_mode, thinking)`、`generate_json(...)`、`stream_generate(...)`（流式，已实现对前端的打字机，但路由暂未使用）。
- 同步 SDK 调用包在 `asyncio.to_thread` 中，避免阻塞事件循环。

### 2.4 数据层
- `models/db.py`：`create_async_engine(settings.DATABASE_URL)` + `async_sessionmaker`；`init_db()` 用 `memory_manager.METADATA.create_all` 建表。
- `memory/memory_manager.py`：**纯 SQLAlchemy Core Table**（无 ORM 模型），定义 5 张表：
  `novels / chapters / characters / foreshadows / stage_summaries`。
  `MemoryManager` 提供：create_novel / save_chapter / update_chapter / upsert_character /
  add_foreshadow / list_characters / list_foreshadows / get_novel / list_chapters /
  list_novels / recent_summaries / stage_summaries / build_generation_context /
  `_compress_stage`（每写满 10 章自动生成阶段总结写入 stage_summaries）。
- `models/__init__.py` 仅 re-export `engine, SessionLocal, get_session, init_db`（无 Novel/Chapter 等 ORM 类）。

### 2.5 RAG
- `rag/chroma_store.py`：`PersistentClient`，按 `(novel_id, collection)` 组织 collection（名做合法化裁剪 ≤63 字符）。
- `rag/retriever.py`：`retrieve()` = 向量召回(top_k*2 候选) + BM25 重排（alpha=0.6 加权）；`retrieve_for_generation(novel_id, q)` 自动查 `world/chapter/skill` 三类集合各 top_k=3。
- 集合命名约定：`world / chapter / skill / feedback`。

### 2.6 Agents（app/agents）
基类 `BaseAgent`：`system_prompt()` + `build_user_prompt(**)` + `run()`(文本) / `run_json()`(dict)。

| Agent | 状态 | 接入点 | 说明 |
|---|---|---|---|
| PlotArchitect | 已接入 | `POST /api/novel/generate-outline` | 生成分卷大纲 JSON |
| ChapterWriter | 已接入 | `POST /api/novel/generate-chapter` | 单章正文 2000-3000 字 |
| ConflictEditor | 已接入 | `POST /api/novel/review-chapter` | 评分+问题+建议 JSON |
| WorldBuilder | 未接入 | — | stub，未写入 RAG |
| CharacterDesigner | 未接入 | — | stub，未写入 characters 表 |
| MemoryKeeper | 未接入 | — | stub，未触发记忆后处理 |

### 2.7 实际生效的 API（novel.py 全清单，prefix=/api/novel）
| 方法 & 路径 | 功能 |
|---|---|
| GET `/list` | 全部小说（按创建时间倒序，供切换列表） |
| GET `/detail?novel_id=` | 单本详情 |
| POST `/create` | 创建小说（novel_id=uuid[:12]） |
| POST `/generate-outline` | PlotArchitect 生成 → 存 novels.outline_json |
| POST `/generate-chapter` | 取大纲元信息+记忆+RAG → ChapterWriter → 落库 |
| POST `/review-chapter` | ConflictEditor 审校 |
| PUT `/{novel_id}/chapter/{chapter_no}` | **作者手动编辑**章节（更新 content，可选 title，重算字数） |
| GET `/{novel_id}/chapters` | 章节列表（按章号升序） |
| GET `/{novel_id}/foreshadows` | 伏笔列表（可筛 status） |
| POST `/{novel_id}/foreshadow` | 新增伏笔（status=open） |
| GET `/characters?novel_id=` | 角色状态列表 |
| GET `/memory?novel_id=` | 记忆快照（角色/伏笔/近5章摘要/阶段总结） |

rag_query.py（prefix=/api/rag）：`POST /rag-ingest`、`POST /rag-query`。

### 2.8 数据库表（列）
- **novels**：id(PK), title, genre, premise(Text), target_chapters(Int=100), style(Text), outline_json(JSON), created_at
- **chapters**：id(PK auto), novel_id(FK), chapter_no, title, content(Text), summary(Text), word_count(Int), created_at
- **characters**：id, novel_id(FK), name, role, personality(Text), motivation(Text), current_status(Text), growth_arc(Text)
- **foreshadows**：id(PK), novel_id(FK), description(Text), planted_chapter(Int), status("open"/"resolved")
- **stage_summaries**：id, novel_id(FK), from_chapter, to_chapter, summary(Text), created_at

---

## 3. 前端架构
- **路由**（router/index.js）：`/`→Dashboard，`/outline`→Outline，`/chapter`→Chapter，`/characters`→Characters，`/world`→World，`/rag`→RAG。
- **Store**（stores/novel.js，Pinia）：`currentId`(localStorage 持久化)、`currentNovel`、`novels`、`outline`、`chapter`、`characters`、`memory`、`chapters`、`loading`/`loadingText`。
  关键 action：create / genOutline / genChapter / review / updateChapter / loadCurrentNovel / loadNovelList / loadChapters / loadCharacters / loadMemory。
- **api**（utils/api.js）：axios `baseURL:'/api'`，全部端点（注意路径带 /api 前缀，与后端一致，代理不 rewrite）。
- **App.vue**：左侧 `el-menu` 导航 + 全局 `store.loading` 遮罩（旋转动画 + 文案）。
- **各视图职责**：
  - DashboardView：创建新书 / 显示书名卡片 / "切换或新建"弹窗列表（表格展示全部书目）。
  - OutlineView：大纲分卷折叠；每章"写这章/重写这章"按钮；已写章节 ✓标签；写完跳 /chapter。
  - ChapterView：章节编辑器。生成本章 / 审校 / 编辑保存 / 上一下一章导航 / "已自动保存到数据库"绿色提示。
  - CharactersView：角色表格（手动加载）。
  - WorldView：记忆快照（未回收伏笔 + 阶段总结）。
  - RAGDebugView：注入/检索调试面板。
- **vite.config.js**：`server.proxy['/api'] → http://backend:8000`，`changeOrigin:true`，**不 rewrite**（后端路由本身带 /api）。

---

## 4. 部署（deploy/）
- `docker-compose.yml`：
  - **postgres**:16-alpine（pgdata 命名卷，端口 5432）。
  - **backend**：build context=../backend，env_file=../.env，覆盖 DATABASE_URL=postgres 服务名，bind mount `../backend:/app`，端口 8000。
  - **frontend**：build context=../frontend，bind mount `../frontend:/app` + 匿名卷 `/app/node_modules`（保留镜像内依赖），`CHOKIDAR_USEPOLLING=true`（根治 Docker 下 Vite HMR 失效），端口 5173。
- `Dockerfile.backend`：python:3.11-slim → pip install → uvicorn app.main:app。
- `Dockerfile.frontend`：node:20-alpine → npm install → `npm run dev -- --host 0.0.0.0 --port 5173`。
- 启动：`docker compose -f deploy/docker-compose.yml up -d --build`
- 访问：前端 http://localhost:5173 ｜ 后端 http://localhost:8000/docs
- ⚠️ 重部署流程（用户习惯）：`docker compose -f deploy/docker-compose.yml down` → `up -d --build`。

---

## 5. 关键数据流
1. 创建小说 → `novel_id` 写入 localStorage（`novel_id`）。
2. 生成大纲 → PlotArchitect → `novels.outline_json`。
3. 生成章节 → 取大纲章元信息 + `build_generation_context`(角色/伏笔/近5章/阶段) + `retrieve_for_generation` → ChapterWriter → 落库 `chapters` + 每 10 章自动阶段压缩。
4. 审校 → ConflictEditor → 返回 score/issues/suggestion（前端 alert 展示）。
5. 手动编辑 → `PUT /chapter` 更新 content（可选 title）并重算字数。

---

## 6. ⚠️ 已知问题 / 技术债（2.0 必须处理）
1. **死代码 `backend/app/api/chapter.py`**：从未被 `main.py` 注册；其内部 import 的 `Novel/Chapter/Character/WorldEntry`、`get_db`、`ChapterGenerateReq/ChapterOut/MessageOut/ReviewOut/CharacterOut/MemoryStatus` 在现行代码里**根本不存在**（现行用 Core Table + 另一套 Schema）。属于早期重复实现，**2.0 应直接删除**。
2. **大纲生成未注入小说设定**：`generate-outline` 调 `PlotArchitect.run_json(novel_id=...)`，但 `PlotArchitect.build_user_prompt` 只传了 `novel_id`，**没有把 title/genre/premise/style 喂给模型**。结果大纲质量差、与设定脱节。修复：在 novel.py 取 novel 记录并注入 user_prompt（参考 ChapterWriter 已正确注入 memory_ctx 的做法）。
3. **3 个 Agent 未接入路由**：WorldBuilder / CharacterDesigner / MemoryKeeper 仅有 prompt，没有对应 endpoint 真正把世界观写入 RAG、把角色写入 characters 表、触发记忆后处理。目前 characters/foreshadows 仅有手动/占位写入路径。
4. ~~**README 与 docker-compose 注释写 `cp .env.example .env`，但项目里只有 `.env`（无 .env.example）**；README 还提到 Redis（实际架构无 Redis）、Alembic 为主迁移（实际 init_db 用 create_all）。~~ **已修正（2026-08-14）**：README.md / backend/README.md / deploy/docker-compose.yml 注释已对齐——明确无 `.env.example`（用根目录 `.env`），并注明不使用 Redis、不使用 Alembic（建表靠 `init_db()` 的 `create_all` + `ALTER ADD COLUMN`）。
5. **无流式输出落地**：`LLMClient.stream_generate` 已实现，但路由与前端都未接（前端无打字机效果）。
6. **无鉴权 / 无多用户**：单用户本地，currentId 仅靠 localStorage。
7. **记忆压缩仅"每 10 章触发"**，无定时/事件驱动后处理（MemoryKeeper 未接）。
8. **大纲→章节跳转细节**：OutlineView"写这章"会 `router.push('/chapter')`，ChapterView 的 `no` 初始化为 `store.chapter.chapter_no`，首次跳转能对齐；但若已在 /chapter 页面内则不重置——属边缘体验问题。

---

## 7. 环境 / 凭证
- 根目录 `.env` 含**真实 ZHIPU_API_KEY**（用户确认仅本地自玩，不入库、不轮换）。
- 本地默认 `DATABASE_URL` 指向 localhost PG；Docker 内由 compose 覆盖为 `postgres` 服务名。
- Python 依赖见 `backend/requirements.txt`（fastapi/uvicorn/sqlalchemy[asyncio]/asyncpg/chromadb 0.5.x/zhipuai/rank-bm25/pydantic-settings…）。
- 前端依赖见 `frontend/package.json`（vue3/vue-router4/pinia/element-plus/axios + vite5/@vitejs/plugin-vue）。

---

## 8. 给 2.0 迭代的入口建议
- 改架构/加功能前，先删除 §6.1 死代码、修复 §6.2 大纲注入。
- 设计细节（新增 Agent、新表、新视图、新交互）请以本文件为"当前已有什么"的基线，再提"要加什么"。
- 验证手段沿用：`backend/tests/test_smoke.py`（mock zhipuai/asyncpg 的冒烟）、`test_e2e.py`（SQLite 联调，沙盒可能跳过）。
