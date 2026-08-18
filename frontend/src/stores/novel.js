import { defineStore } from 'pinia'
import api from '../utils/api'

export const useNovelStore = defineStore('novel', {
  state: () => ({
    currentId: localStorage.getItem('novel_id') || '',
    currentNovel: null,           // 当前小说的详细信息（title/genre/premise...）
    novels: [],                   // 所有小说列表（供「切换新书」弹窗）
    outline: [],
    chapter: null,                // 当前已生成的章节（从 /chapter 页面共享）
    characters: [],
    memory: null,
    chapters: [],                   // 已保存到数据库的章节列表（来自后端 /chapters）
    world: null,                    // 世界观设定（WorldSettings）
    // 全局加载态：大模型调用期间为 true，驱动页面中央的加载弹窗
    loading: false,
    loadingText: '',
    modelConfig: null,
  }),
  actions: {
    setCurrentId(id) {
      this.currentId = id
      localStorage.setItem('novel_id', id)
      // 切换后立即重新加载目标书的详情，让首页显示真正的书名
      this.loadCurrentNovel()
    },
    setCurrentNovel(novel) { this.currentNovel = novel },
    _setLoading(text) { this.loading = true; this.loadingText = text },
    _clearLoading() { this.loading = false; this.loadingText = '' },

    async loadCurrentNovel() {
      if (!this.currentId) { this.currentNovel = null; return }
      try {
        this.currentNovel = await api.getNovel(this.currentId)
      } catch {
        this.currentNovel = null  // ID 失效（被删/未创建）时清空
      }
    },
    async loadNovelList() { this.novels = await api.listNovels() },

    async create(payload) {
      this._setLoading('正在创建小说…')
      try {
        const r = await api.createNovel(payload)
        this.setCurrentId(r.id)                 // 这会触发 loadCurrentNovel
        this.currentNovel = r                    // 后端返回的就是完整 NovelOut，节省一次请求
        return r
      } finally { this._clearLoading() }
    },
    async genOutline() {
      this._setLoading('大模型正在生成大纲…')
      try { const r = await api.genOutline({ novel_id: this.currentId }); this.outline = r.outline; return r }
      finally { this._clearLoading() }
    },
    async loadOutline() {
      if (!this.currentId) return null
      try {
        const r = await api.getOutline(this.currentId)
        if (r.outline && r.outline.length) { this.outline = r.outline; return r }
      } catch { /* 尚无大纲 */ }
      return null
    },
    // 2.0 一键成书：WorldBuilder→两遍式大纲/角色 一次性完成，并加载全部产物
    async bootstrap() {
      this._setLoading('正在一键成书：构建世界观 → 生成大纲与角色…（多步 AI 流水线）')
      try {
        const r = await api.bootstrap(this.currentId)
        // 拉取成书后的全部产物，刷新各视图
        await Promise.all([
          this.loadOutline(),
          this.loadCharacters(),
          this.loadWorld().catch(() => {}),
          this.loadChapters(),
        ])
        return r
      } finally { this._clearLoading() }
    },
    async genChapter(no) {
      this._setLoading('大模型正在撰写章节…')
      try {
        const r = await api.genChapter({ novel_id: this.currentId, chapter_no: no })
        this.chapter = r
        // 写完一章后立刻刷新已写章节列表，让大纲页能标出"✓ 已写"
        this.chapters = await api.getChapters(this.currentId).catch(() => this.chapters)
        return r
      } finally { this._clearLoading() }
    },
    async review(payload) {
      this._setLoading('大模型正在审校章节…')
      try { return await api.reviewChapter(payload) }
      finally { this._clearLoading() }
    },
    // 作者手动编辑已生成章节：把修改后的正文写回数据库
    async updateChapter(novel_id, chapter_no, content, title) {
      const r = await api.updateChapter(novel_id, chapter_no, { content, title })
      this.chapter = r                      // 用返回的最新内容刷新当前章节
      this.chapters = await api.getChapters(this.currentId).catch(() => this.chapters)
      return r
    },
    async generateWorld() {
      this._setLoading('大模型正在构建世界观…')
      try { this.world = await api.generateWorld(this.currentId); return this.world }
      finally { this._clearLoading() }
    },
    async loadWorld() {
      try { this.world = await api.getWorld(this.currentId) } catch { this.world = null }
    },
    async saveWorld() {
      if (this.world) this.world = await api.updateWorld(this.currentId, this.world)
    },
    async generateCharacters() {
      this._setLoading('大模型正在设计角色…')
      try { this.characters = await api.generateCharacters(this.currentId); return this.characters }
      finally { this._clearLoading() }
    },
    async loadCharacters() { this.characters = await api.getCharacters(this.currentId) },
    // 批量保存角色编辑（前端内联编辑后全量写回）
    async saveCharacters() {
      if (!this.currentId) return
      this.characters = await api.updateCharacters(this.currentId, this.characters)
    },
    async loadMemory() { this.memory = await api.getMemory(this.currentId) },
    async loadChapters() { this.chapters = await api.getChapters(this.currentId) },
    // 加载单章已写内容（章节页初始化 / 大纲跳转时用）
    async loadChapter(chapterNo) {
      if (!this.currentId) return null
      try {
        this.chapter = await api.getChapter(this.currentId, chapterNo)
        return this.chapter
      } catch { return null }
    },
    // 模型设置
    async loadModelConfig() { this.modelConfig = await api.getModelConfig(); return this.modelConfig },
    async saveModelConfig(data) { return await api.saveModelConfig(data) },
  },
})
