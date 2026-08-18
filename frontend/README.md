# AI Novel Forge · 前端

Vue 3 + Vite + Element Plus + Pinia + Vue Router。

## 组件树

```
App.vue（侧边菜单 + <router-view/>）
├── DashboardView.vue    工作台：创建新书 / 启动大纲·章节生成
├── OutlineView.vue       大纲编辑器：分卷折叠 + 章节表格
├── ChapterView.vue       章节编辑器：实时生成按钮 + 审校评分
├── CharactersView.vue    角色面板：人设卡表格
├── WorldView.vue         世界观知识库浏览器（记忆快照）
└── RAGDebugView.vue      RAG 检索调试面板：注入/查询
```

## 关键交互

- 工作台创建新书 → 写入 `localStorage.novel_id` 并存入 Pinia → 全局复用 `novel_id`
- 所有视图通过 `utils/api.js`（axios，`/api` 已由 vite 代理到 `:8000`）调用后端
- 章节页"生成本章"调用 `POST /api/novel/generate-chapter`，"审校"调用 `…/review-chapter`
- RAG 调试页可注入文档到指定 collection（world/chapter/skill）并实时检索

## 启动

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # 产出 dist/，供 Dockerfile.frontend 多阶段构建
```
