# AI Novel Forge · 全栈多 Agent 网文创作系统

> 基于 **RAG + 多智能体协作** 的网文（爽文/玄幻/修仙/都市异能）自动创作系统。
> 底层 LLM：**GLM-4.7-Flash（智谱 AI）**｜后端 FastAPI + ChromaDB + PostgreSQL（SQLite 亦可用）｜前端 Vue3 + Element Plus
> 当前版本：**2.0** —— Coordinator 驱动的「创建新书 / 生成单章」两条多 Agent 流水线。

## 架构分层

```
用户交互层(Vue3+ElementPlus) ──▶ API 网关层(FastAPI+Pydantic v2)
        │
        ▼
协调编排层(Coordinator · services/coordinator.py)   ← 2.0 新增：统一编排两条流水线
        │
        ▼
多 Agent 协作层(BaseAgent + 6 业务 Agent + RAG 检索)
        │
        ▼
创作引擎层(GLM-4.7-Flash via zhipuai SDK) ──▶ 记忆管理层(短/中/长期+压缩)
                                                        │
                                                        ▼
                                            存储层(PostgreSQL/SQLite + ChromaDB)
```

| 层 | 核心组件 | 技术选型 | 职责边界 |
|---|---|---|---|
| 用户交互层 | 6 个视图（工作台/大纲/章节/角色/世界观/RAG调试） | Vue3+Vite+ElementPlus+Pinia | 仅负责展示与交互，不含业务逻辑 |
| API 网关层 | FastAPI 路由 + Pydantic Schema | FastAPI+Pydantic v2 | 参数校验、依赖注入、CORS |
| 协调编排层 | Coordinator | `app/services/coordinator.py` | 编排创建/生成流水线、重试与重写、调用链日志 |
| 多 Agent 协作层 | BaseAgent + 6 个业务 Agent + RAG | Python 抽象基类 | 各 Agent 独立 Prompt+工具契约 |
| 创作引擎层 | GLM-4.7-Flash 调用封装 | zhipuai SDK（model=glm-4.7-flash） | 统一 chat/chat_json，支持 thinking |
| 记忆管理层 | MemoryManager | SQLAlchemy 2.x Core | 短(上下文)/中(近5章摘要)/长(角色/伏笔/阶段总结) |
| 存储层 | PostgreSQL 或 SQLite + ChromaDB | asyncpg/aiosqlite + Chroma PersistentClient | 持久化与向量检索 |

> 注：项目**不使用 Redis**，亦**不使用 Alembic**。表结构由 `SQLAlchemy Core` 的 `METADATA` 定义，经 `init_db()`（`app/models/db.py`）执行 `create_all` + 对既有表 `ALTER ... ADD COLUMN IF NOT EXISTS` 自动建表/补齐列。

## 7 个 Agent（6 业务 + RAG 检索）

| Agent | 角色 | 输出 | 关键工具 |
|---|---|---|---|
| PlotArchitect | 剧情架构师 | 分卷大纲 JSON（total_outline + arc + development + ending_hook） | world.query_entries / rag.retrieve |
| WorldBuilder | 世界观构建者 | 世界观条目 JSON→写入 RAG | rag.ingest_world |
| CharacterDesigner | 角色设计师 | 14 字段结构人设卡 JSON | memory.upsert_character |
| ChapterWriter | 章节写手 | 单章正文 2000-3000 字 + 末尾元数据行 | rag.retrieve_for_generation / memory.* |
| ConflictEditor | 冲突编辑 | 四维评分 + verdict + 结构化 issues JSON | memory.build_generation_context |
| MemoryKeeper | 记忆管家 | 状态/伏笔/时间线更新 JSON | memory.* |
| RAG 检索（app/rag） | BM25 + 向量混合重排 | 检索上下文包 | chroma_store / retriever |

每个 Agent 的 Prompt 均含 **防幻觉指令**（禁止擅自新增势力/功法/亲属、严格基于设定）与 **输出格式约束**（正文 or 严格合法 JSON）。
**Coordinator** 不是 Agent，而是编排层：创建新书走「两遍式大纲」（WorldBuilder→Pass-1 大纲骨架→CharacterDesigner→Pass-2 大纲细化→MemoryKeeper 初始化），生成单章走「RAG→写手→审校(<24 自动重写≤2次)→记忆→落库」。

## 快速开始

```bash
# 0. 配置：复制模板并填入你自己的 Key
cp .env.example .env
#    然后编辑 .env，把 ZHIPU_API_KEY 换成你自己的智谱 API Key（ACCESS_PASSWORD 设访问口令）。

# 1. 后端（推荐用 Docker，自动带 PostgreSQL；见「部署」）
cd backend
pip install -r requirements.txt
#    本地裸跑需自备 PostgreSQL，或把 .env 的 DATABASE_URL 改为
#    sqlite+aiosqlite:///./dev.db 以零依赖运行
uvicorn app.main:app --reload --port 8000
# 交互文档：http://localhost:8000/docs

# 2. 前端（新终端）
cd frontend
npm install
npm run dev                   # http://localhost:5173（/api 已代理到 :8000）

# 3. 测试（隔离 venv + 桩模块，无需真实 API Key / PostgreSQL）
cd backend && pytest -q
```

## 环境变量（根目录 `.env`）

| 变量 | 说明 | 默认 |
|---|---|---|
| ZHIPU_API_KEY | 智谱 API Key（必填） | — |
| ZHIPU_MODEL | 模型名 | glm-4.7-flash |
| ZHIPU_EMBED_MODEL | 向量模型 | embedding-3 |
| LLM_TEMPERATURE | 生成温度 | 0.8 |
| LLM_MAX_TOKENS | 最大 token | 65536 |
| DATABASE_URL | 异步 DSN（PostgreSQL 或 SQLite 均可） | postgresql+asyncpg://postgres:postgres@localhost:5432/novelforge |
| CHROMA_PERSIST_DIR | Chroma 持久化目录 | ./.chroma |
| API_HOST / API_PORT | 服务监听地址/端口 | 0.0.0.0 / 8000 |
| ACCESS_PASSWORD | **共享访问口令**（线上必填）。留空=不启用鉴权（本地开发无感）；填上后所有业务接口需先登录 | — |

## 部署

```bash
# 复制模板并填入你的配置：cp .env.example .env（记得替换 ZHIPU_API_KEY 与 ACCESS_PASSWORD）。
# 如需自定义，直接编辑根目录 .env 即可。
docker compose -f deploy/docker-compose.yml up -d --build
# 前端 http://localhost:5173 ｜ 后端 http://localhost:8000/docs
```

> Docker 会自动拉起 `postgres:16-alpine` 服务，并把 `DATABASE_URL` 改写为容器内的 PG 地址；Chroma 使用容器内 `/tmp/ainovelforge_chroma`。前端开启 `CHOKIDAR_USEPOLLING=true` 以解决 bind mount 下 Vite 热更新不生效的问题。

### 生产部署（自有服务器 / Oracle Always-Free 整机）

把「前端 + 后端 + 数据库 + 向量库」整体跑在一台服务器的一个 Docker Compose 里。前端由 nginx 托管并**同源反代 `/api`**，免 CORS、数据持久化。

```bash
# 0) 服务器上：仓库根目录放一份 .env（含 ZHIPU_API_KEY 等；可复制本地 .env，
#    DATABASE_URL / CHROMA_PERSIST_DIR 会被 compose 覆盖，无需改）
# 1) 首次部署
docker compose -f deploy/docker-compose.prod.yml up -d --build
# 2) 浏览器访问 http://<服务器公网IP>
# 3) 以后更新代码，在服务器上跑一键脚本（git pull + 重建重启 + 清悬空镜像）
./deploy/redeploy.sh
```

- 端口：前端 **80**（HTTP）、后端 **8000**（可选调试 `/docs`）。
- 持久化：`pgdata`（Postgres）、`chroma_data`（Chroma 向量库）均为命名卷，重启/重建不丢。
- 云服务器（如 Oracle Always-Free）记得在**安全组/防火墙放行 80**（和可选 443）入站。
- HTTPS / 域名：可选，后续用 Nginx/Caddy + 免费证书（Let's Encrypt）即可，不影响功能。
- 🔐 **共享访问口令（A 方案）**：在服务器 `.env` 写入 `ACCESS_PASSWORD=你的口令` 即启用。启用后所有人须先在该口令登录页输入正确口令才能进入；留空则不启用（本地开发默认）。注意：这是「挡外部陌生人」的共享口令，**朋友之间仍共用一个数据库、能看到彼此的小说**（每人自己「创建新书」即可互不干扰）。真正的「每人独立账号+数据隔离」为 B 方案，后续再做。
- 📌 改完 `.env` 后需 `docker compose -f deploy/docker-compose.prod.yml up -d --build` 或 `./deploy/redeploy.sh` 让新口令生效。

### 方案 C：腾讯云 CloudBase 云托管（国内·推荐）

适合：朋友都在国内、不想自己管服务器、希望国内访问快。自带域名 + HTTPS，支持从 GitHub 授权拉取代码、**push 自动重新部署**。

> 计费：新用户有 **1 个月免费额度**（足够 1核2G 实例常驻 30 天）；之后按量计费（0.5核1G + 缩容到 0 时近乎不花钱）。CFS 持久卷约 ¥0.35/GB/月（本应用几百 MB，可忽略）。需**实名认证**（身份证+手机号）。

**架构**：单容器同时跑 `nginx(80)` + 后端 `(127.0.0.1:8000)`，前端同源反代 `/api` 免 CORS；SQLite 数据库与 Chroma 向量库都落在挂载的 CFS 卷 `/data`，实例销毁数据不丢。**不额外购买云数据库**。

**部署步骤**：
1. 腾讯云控制台 → 搜索「云托管」→ 进入 **CloudBase Run 独立控制台**；按提示开通（实名认证 + 创建一个环境，选「按量计费 / 开通免费资源」）。
2. 新建服务 → 来源选「代码仓库」→ 授权 GitHub 并选中本仓库（私有仓库也可，授权后云托管能拉取）→ 开启「自动部署」。
3. 构建配置：
   - 构建目录：`/`（仓库根）
   - Dockerfile 路径：`deploy/Dockerfile.cloudbase`
   - 监听端口：`80`
4. 环境变量（在服务的「环境变量」里添加，等同本地 `.env`，**不要写进代码仓库**）：
   - `ZHIPU_API_KEY=你的智谱Key`（必填）
   - `ACCESS_PASSWORD=你设的访问口令`（必填，启用共享口令登录）
   - `DATABASE_URL=sqlite+aiosqlite:////data/novelforge.db`（4 个斜杠 = 绝对路径 `/data/novelforge.db`）
   - `CHROMA_PERSIST_DIR=/data/chroma`
   - `CORS_ORIGINS=*`（同源访问其实不触发 CORS，填 `*` 即可）
5. 存储挂载：服务详情 →「存储挂载」→ 启用并新建/选择 **CFS 文件存储**，挂载路径填 `/data`（与上面的 `DATABASE_URL` / `CHROMA_PERSIST_DIR` 对应）。
6. 扩缩容：建议「最小实例数 = 0、最大实例数 = 1」（空闲不收费、单实例避免 SQLite 并发写锁；首次访问有数秒冷启动）。如需随时可点，把最小实例数设为 1（消耗免费额度/小额计费）。
7. 部署完成后，控制台给出访问地址（如 `https://xxx.ap-shanghai.run.tcloudbase.com`），发给朋友即可玩；输入访问口令进入。

**更新代码**：本地改完 `git push` 到 main → 云托管自动重新构建部署（已开启自动部署时）。

**注意**：
- SQLite 跑在 CFS（网络文件系统）上，极低频写入没问题；若日后朋友多、并发写变多，可升级为腾讯云数据库 PostgreSQL（把 `DATABASE_URL` 换成其连接串，Chroma 仍用 CFS 或改 pgvector）。
- 自定义域名 / HTTPS：云托管地址已是 HTTPS；想用自己域名，在「访问服务」里添加域名并做 DNS 解析 + 备案（国内域名必须备案）。

## 核心端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /api/novel/create | 创建新书（仅元数据） |
| GET  | /api/novel/list | 列出全部小说 |
| GET  | /api/novel/detail?novel_id= | 单本详情 |
| POST | /api/novel/bootstrap | 一键成书（Coordinator 创建流水线：世界→两遍式大纲→角色→落库） |
| POST | /api/novel/generate-outline | 生成大纲（PlotArchitect，注入设定） |
| GET  | /api/novel/outline?novel_id= | 读取已存大纲（不重新生成） |
| POST | /api/novel/generate-world | 生成世界观（WorldBuilder）→ 落库 + 写 RAG |
| GET  | /api/novel/world?novel_id= | 读取世界观（可查看） |
| PUT  | /api/novel/world | 作者手改世界观（可编辑） |
| POST | /api/novel/generate-characters | 生成人设卡（CharacterDesigner）→ 写 characters 表 |
| GET  | /api/novel/characters?novel_id= | 角色状态列表 |
| POST | /api/novel/generate-chapter | 生成单章（Coordinator 单章流水线） |
| PUT  | /api/novel/{novel_id}/chapter/{chapter_no} | 作者手改章节 |
| POST | /api/novel/review-chapter | 审校章节（ConflictEditor） |
| POST | /api/novel/update-memory | 章节后记忆更新（MemoryKeeper） |
| GET  | /api/novel/{novel_id}/chapters | 章节列表 |
| GET  | /api/novel/{novel_id}/foreshadows | 伏笔列表 |
| POST | /api/novel/{novel_id}/foreshadow | 新增伏笔 |
| GET  | /api/novel/memory?novel_id= | 记忆快照 |
| POST | /api/rag/rag-ingest | 注入文档到 RAG |
| POST | /api/rag/rag-query | RAG 检索 |
| GET  | /health | 健康检查 |

## 目录结构

```
ai-novel-forge/
├── backend/                  FastAPI 后端
│   ├── app/
│   │   ├── agents/           6 个业务 Agent（base + plot_architect/world_builder/character_designer/chapter_writer/conflict_editor/memory_keeper）
│   │   ├── api/              路由（novel / rag_query）
│   │   ├── core/             config + LLM 客户端封装
│   │   ├── memory/           MemoryManager + SQLAlchemy Core 表
│   │   ├── models/           db.py 引擎/Session（init_db 自动建表）
│   │   ├── rag/              chroma_store + retriever(BM25+向量混合)
│   │   ├── schemas/          Pydantic v2 Schema
│   │   ├── services/         coordinator.py（2.0 编排层）
│   │   └── main.py           FastAPI 入口
│   ├── tests/                pytest（phase0-6 + smoke + e2e，桩 chromadb/zhipuai/asyncpg）
│   ├── requirements.txt
│   └── （.env 在仓库根目录，非 backend/）
├── frontend/                 Vue3 前端
│   ├── src/{views,stores,utils,router}/
│   ├── package.json / vite.config.js
│   └── index.html
├── prompts/                  8 个 Agent 提示词版本化 JSON（v1.0.0 + index.json）
├── deploy/                    Dockerfile + docker-compose.yml
└── .env.example                环境变量模板（复制为 .env 后填入你的 Key；.env 本身不入库）
```

## 进度

- [x] **1.0（MVP 可跑通）**：FastAPI 入口 + Pydantic Schema + GLM-4.7-Flash 封装 + Chroma 客户端 + RAG 混合检索 + MemoryManager + ChapterWriter + 6 视图 + 部署配置 + 冒烟测试
- [x] **2.0（Coordinator 多 Agent 流水线）**：
  - 全部 6 个业务 Agent 接入路由（WorldBuilder/CharacterDesigner/MemoryKeeper 此前为 stub）
  - **Coordinator 编排层**：创建新书两遍式大纲（Pass-1 骨架→CharacterDesigner→Pass-2 细化）+ 单章流水线（RAG→写→审校四维评分<24 自动重写≤2次→记忆→落库）
  - 世界观落库 `world_settings_json` 且可查看/手改；角色结构化 14 字段；大纲↔角色循环依赖消解
  - 一键成书（`/bootstrap`）+ 前端打字机效果；提示词版本化 `prompts/*.json`
  - 测试：Phase 0-6 全绿（`pytest tests/` → 14 passed, 1 skipped）
- [ ] 后续可选：阶段压缩定时任务、角色/世界观 CRUD 页面增强、流式输出接 SSE

> 设计决策与开发日志见 `2.0_DEV_DIARY.md`；项目权威最新状态见 `PROJECT_STATE.md`。
