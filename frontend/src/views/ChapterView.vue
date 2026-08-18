<template>
  <div class="page" :class="isDark ? 'theme-dark' : 'theme-light'">
    <div class="page-header-row">
      <h2>章节编辑器</h2>
    </div>

    <div class="toolbar">
      <span class="label">章节号</span>
      <el-input-number v-model="no" :min="1" :max="1000" />
      <el-button type="primary" @click="onGen" :loading="store.loading" :disabled="!store.currentId">生成本章</el-button>
      <el-button @click="onReview" :loading="revLoading" :disabled="!store.currentId">审校</el-button>
      <el-button type="warning" @click="onEdit" :disabled="!store.chapter || editing">✏ 编辑正文</el-button>
      <el-button @click="onPrev" :disabled="!hasPrev">← 上一章</el-button>
      <el-button @click="onNext" :disabled="!hasNext">下一章 →</el-button>
    </div>

    <!-- 审校结果横幅 -->
    <el-alert v-if="review" :title="`审校评分 ${review.total}/40 · ${review.verdict}`" :type="reviewType" show-icon class="mt review-banner">
      <div class="scores">
        <span>钩子 {{ review.scores?.hook ?? '-' }}</span>
        <span>节奏 {{ review.scores?.pacing ?? '-' }}</span>
        <span>逻辑 {{ review.scores?.logic ?? '-' }}</span>
        <span>文笔 {{ review.scores?.writing ?? '-' }}</span>
      </div>
      <div v-if="review.suggestion" class="sug">建议：{{ review.suggestion }}</div>
      <ul v-if="review.issues?.length" class="issues">
        <li v-for="(it,i) in review.issues" :key="i">
          <b>[{{ it.severity }}/{{ it.type }} {{ it.location }}]</b>：{{ it.problem }}
          <span class="fix">→ 改：{{ it.fix }}</span>
        </li>
      </ul>
    </el-alert>

    <!-- ====== 主内容区（左侧）+ 右侧停靠面板 ====== -->
    <div class="main-wrapper">

      <!-- 左侧：正文区 -->
      <div class="content-area" v-if="store.chapter && store.chapter.chapter_no === no">
        <el-card class="chapter-card">
          <template #header>
            <div class="hdr">
              <b class="ch-title">{{ store.chapter.title }}</b>
              <div class="hdr-tags">
                <el-tag size="small" type="info">{{ store.chapter.word_count }} 字</el-tag>
                <el-tag size="small" type="success" v-if="store.chapter.meta?.cool_points">🔥 {{ store.chapter.meta.cool_points }}</el-tag>
                <el-tag size="small" type="warning" v-if="store.chapter.meta?.foreshadows">📌 {{ store.chapter.meta.foreshadows }}</el-tag>
              </div>
            </div>
          </template>

          <!-- 阅读模式 -->
          <template v-if="!editing">
            <el-alert type="success" :closable="false" show-icon class="saved-hint">
              <template #title>已自动保存到数据库</template>
              <template #default>第 {{ store.chapter.chapter_no }} 章 · {{ store.chapter.title }} · 点击上方「✏ 编辑正文」可手动修改</template>
            </el-alert>
            <div class="content-body">{{ displayed }}<span v-if="typing" class="caret">▌</span></div>
          </template>

          <!-- 编辑模式 -->
          <template v-else>
            <el-alert type="warning" :closable="false" show-icon class="saved-hint">
              <template #title>编辑中</template>
              <template #default>直接修改正文，点「保存修改」写回数据库</template>
            </el-alert>
            <el-input v-model="draft" type="textarea" :autosize="{ minRows: 18, maxRows: 40 }" class="editor" placeholder="在此修改章节正文…" />
            <div class="edit-actions">
              <el-button type="primary" :loading="saving" @click="onSaveEdit">💾 保存修改</el-button>
              <el-button @click="onCancelEdit">取消</el-button>
              <span class="muted">{{ draft.length }} 字</span>
            </div>
          </template>
        </el-card>
      </div>

      <el-empty v-else-if="!store.chapter" description="点「生成本章」开始，或从大纲页点「查看」" />

      <!-- ====== 右侧：停靠面板栏（固定在内容右侧，仅限上下拖动） ====== -->
      <div class="dock-rail" ref="dockRailRef">

        <!-- P1: 本章概要 -->
        <div class="dock-panel" data-key="summary" :style="panelStyle('summary')">
          <div class="dp-header" @mousedown.stop="onHeaderDragStart($event, 'summary')">
            <span class="dp-title">📋 本章概要</span><span class="dp-drag">⠿</span>
          </div>
          <div class="dp-body">
            <div class="info-row"><span class="info-label">章节号</span><span class="info-val">{{ store.chapter?.chapter_no || '-' }} / {{ totalChapters }}</span></div>
            <div class="info-row"><span class="info-label">标题</span><span class="info-val bold">{{ store.chapter?.title || '-' }}</span></div>
            <div class="info-row"><span class="info-label">字数</span><span class="info-val">{{ store.chapter?.word_count || 0 }} 字</span></div>
            <div class="info-row"><span class="info-label">状态</span><el-tag size="small" type="success">已完成</el-tag></div>
          </div>
        </div>

        <!-- P2: 伏笔追踪 -->
        <div class="dock-panel" data-key="foreshadow" :style="panelStyle('foreshadow')">
          <div class="dp-header" @mousedown.stop="onHeaderDragStart($event, 'foreshadow')">
            <span class="dp-title">📌 伏笔追踪</span><span class="dp-drag">⠿</span>
          </div>
          <div class="dp-body">
            <div v-if="foreshadowList.length" class="fs-list">
              <div v-for="(f, i) in foreshadowList" :key="i" class="fs-item">
                <span class="fs-dot"></span><span>{{ f }}</span>
              </div>
            </div>
            <div v-else class="empty-mini">暂无伏笔记录</div>
            <div class="add-fs">
              <el-input v-model="newFs" size="small" placeholder="添加伏笔…" @keyup.enter="addForeshadow" />
              <el-button size="small" type="primary" @click="addForeshadow" :disabled="!newFs.trim()">+</el-button>
            </div>
          </div>
        </div>

        <!-- P3: 出场角色 -->
        <div class="dock-panel" data-key="chars" :style="panelStyle('chars')">
          <div class="dp-header" @mousedown.stop="onHeaderDragStart($event, 'chars')">
            <span class="dp-title">👥 出场角色</span><span class="dp-drag">⠿</span>
          </div>
          <div class="dp-body">
            <div v-if="chapterCharacters.length" class="char-list-sm">
              <div v-for="c in chapterCharacters.slice(0, 6)" :key="c.name" class="char-chip-sm">
                <el-avatar :size="22">{{ c.name?.[0] || '?' }}</el-avatar>
                <span>{{ c.name }}</span>
              </div>
            </div>
            <div v-else class="empty-mini">暂无角色</div>
            <router-link to="/characters" class="fp-link">查看全部 →</router-link>
          </div>
        </div>

        <!-- P4: 角色关系 → 点击打开大弹窗 -->
        <div class="dock-panel" data-key="relation" :style="panelStyle('relation')">
          <div class="dp-header" @mousedown.stop="onHeaderDragStart($event, 'relation')">
            <span class="dp-title">🔗 角色关系</span><span class="dp-drag">⠿</span>
          </div>
          <div class="dp-body">
            <div class="rel-preview" @click="showRelDialog = true">
              <svg viewBox="0 0 200 140" class="mini-graph">
                <circle v-for="(n,i) in miniNodes" :key="'mn'+i" :cx="n.cx" :cy="n.cy" :r="8"
                  :class="['mnode', n.highlight ? 'hi' : '']" />
                <line v-for="(e,i) in miniEdges" :key="'me'+i" :x1="e.x1" :y1="e.y1" :x2="e.x2" :y2="e.y2" class="medge" />
              </svg>
              <p class="rel-hint">点击放大 →</p>
            </div>
          </div>
        </div>

        <!-- P5: 章节笔记 -->
        <div class="dock-panel" data-key="notes" :style="panelStyle('notes')">
          <div class="dp-header" @mousedown.stop="onHeaderDragStart($event, 'notes')">
            <span class="dp-title">📝 章节笔记</span><span class="dp-drag">⠿</span>
          </div>
          <div class="dp-body">
            <el-input v-model="chapterNotes" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" placeholder="记录灵感…" class="notes-in" />
            <div class="notes-ft">
              <span class="muted-xs">{{ chapterNotes.length }} 字</span>
              <el-button size="small" type="primary" @click="saveNotes" :disabled="!chapterNotes.trim()">保存</el-button>
            </div>
          </div>
        </div>

        <!-- P6: 快捷导航 -->
        <div class="dock-panel" data-key="nav" :style="panelStyle('nav')">
          <div class="dp-header" @mousedown.stop="onHeaderDragStart($event, 'nav')">
            <span class="dp-title">🧭 快捷导航</span><span class="dp-drag">⠿</span>
          </div>
          <div class="dp-body">
            <router-link to="/outline" class="nav-link-sm">📑 大纲总览</router-link>
            <router-link to="/world" class="nav-link-sm">🌍 世界观</router-link>
            <router-link to="/characters" class="nav-link-sm">👥 角色设定</router-link>
            <router-link to="/memory" class="nav-link-sm">🧠 记忆库</router-link>
          </div>
        </div>

      </div><!-- /dock-rail -->

    </div><!-- /main-wrapper -->

    <!-- ====== 关系网大弹窗（3D Canvas 力导向 · 全屏） ====== -->
    <el-dialog v-model="showRelDialog" title="🔗 角色关系网络" :fullscreen="true" class="rel-dialog" draggable :close-on-click-modal="false"
      @opened="startForceGraph" @close="stopForceGraph">
      <div class="rel-dialog-body">
        <!-- 顶部工具栏 -->
        <div class="center-picker">
          <span class="cp-label">以谁为中心：</span>
          <el-select v-model="centerChar" size="default" placeholder="选择角色" style="width:180px" @change="onCenterChange">
            <el-option v-for="n in allCharNames" :key="n" :label="n" :value="n" />
          </el-select>
          <span class="cp-legend">
            <span class="leg-dot ally"></span>盟友
            <span class="leg-dot neutral"></span>中立
            <span class="leg-dot enemy"></span>敌对
          </span>
          <el-button size="small" @click="shuffleLayout" style="margin-left:auto">🔄 打散重排</el-button>
          <el-button size="small" type="warning" @click="showHidePanel = !showHidePanel" style="margin-left:6px">
            {{ showHidePanel ? '🙈 隐藏列表' : '👁 隐藏节点' }}
          </el-button>
        </div>

        <!-- 主区域：画布 + 可折叠隐藏面板 -->
        <div class="rel-main-area">
          <!-- 左侧/主画布区 -->
          <div class="canvas-wrap" :style="{ flex: showHidePanel ? '1' : '1', maxWidth: showHidePanel ? '' : '100%' }">
            <canvas ref="relCanvas" class="rel-canvas" />
          </div>

          <!-- 右侧：隐藏/显示节点面板 -->
          <transition name="slide-fade">
            <div v-if="showHidePanel" class="hide-panel">
              <div class="hp-title">👁 节点可见性</div>
              <div class="hp-subtitle">点击切换显示/隐藏，隐藏的节点不参与布局</div>
              <div class="hp-list">
                <label v-for="nm in allCharNames" :key="nm" class="hp-item" :class="{ 'hp-hidden': _hiddenNodes.has(nm) }">
                  <input type="checkbox" :checked="!_hiddenNodes.has(nm)" @change="toggleNodeVisibility(nm)" />
                  <span class="hp-name">{{ nm }}</span>
                  <span class="hp-status">{{ _hiddenNodes.has(nm) ? '已隐藏' : '可见' }}</span>
                </label>
              </div>
              <div class="hp-actions">
                <el-button size="small" @click="showAllNodes">全部显示</el-button>
                <el-button size="small" type="info" @click="hideAllNodesExceptCenter">仅留中心</el-button>
              </div>
            </div>
          </transition>
        </div>

        <!-- 操作手册 -->
        <div class="rel-manual">
          <div class="rm-title">📖 操作手册</div>
          <div class="rm-grid">
            <div class="rm-item"><span class="rm-icon">🖱️</span><div class="rm-text"><b>拖拽节点</b>移动位置，松手后自动<b>钉住</b>（金色📌），不再回弹。</div></div>
            <div class="rm-item"><span class="rm-icon">👆</span><div class="rm-text"><b>单击节点</b>可将其切换为新的<b>中心角色</b>。</div></div>
            <div class="rm-item"><span class="rm-icon">👆👆</span><div class="rm-text"><b>双击已钉住节点</b>取消钉住，重新参与物理布局。</div></div>
            <div class="rm-item"><span class="rm-icon">👁</span><div class="rm-text"><b>隐藏节点</b>：点击「👁 隐藏节点」按钮，勾选要隐藏的角色，简化视图。</div></div>
            <div class="rm-item"><span class="rm-icon">🔄</span><div class="rm-text"><b>打散重排</b>清除所有钉住状态并随机重新布局。</div></div>
            <div class="rm-item"><span class="rm-icon">🔘</span><div class="rm-text"><b>滚轮缩放</b>整个关系图，放大查看细节或缩小纵览全局。</div></div>
            <div class="rm-item"><span class="rm-icon">🎨</span><div class="rm-text">连线颜色：<span class="leg-dot ally"></span><b>盟友（绿）</b> · <span class="leg-dot neutral"></span><b>中立（灰）</b> · <span class="leg-dot enemy"></span><b>敌对（红）</b>。</div></div>
          </div>
        </div>
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useNovelStore } from '../stores/novel'
import { useForceGraph } from '../composables/useForceGraph'

const store = useNovelStore()
const route = useRoute()
const router = useRouter()
const no = ref(parseInt(route.query.ch) || store.chapter?.chapter_no || 1)
const review = ref(null)
const revLoading = ref(false)

// ========== 全局主题（读取 App.vue 写入的同一个 key） ==========
const THEME_KEY = 'global_theme_dark'
const isDark = ref(true)
function loadTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved !== null) { isDark.value = saved === 'true'; return }
  } catch {}
  isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
}
// 监听外部（App.vue）主题变化
window.addEventListener('storage', (e) => {
  if (e.key === THEME_KEY && e.newValue !== null) isDark.value = e.newValue === 'true'
})
loadTheme()

// 编辑态
const editing = ref(false)
const draft = ref('')
const saving = ref(false)

// 打字机效果
const displayed = ref('')
const typing = ref(false)
let _timer = null
function startTypewriter(text) {
  if (_timer) clearInterval(_timer)
  if (!text) { displayed.value = ''; typing.value = false; return }
  displayed.value = ''
  typing.value = true
  let i = 0
  const step = Math.max(20, Math.ceil(text.length / 240))
  _timer = setInterval(() => {
    i += step
    if (i >= text.length) { displayed.value = text; typing.value = false; clearInterval(_timer); _timer = null }
    else displayed.value = text.slice(0, i)
  }, 16)
}
function stopTypewriter() { if (_timer) { clearInterval(_timer); _timer = null } typing.value = false }

// ========== 伏笔 ==========
const newFs = ref('')
const foreshadowList = ref([])
function addForeshadow() {
  const t = newFs.value.trim()
  if (!t) return
  foreshadowList.value.push(t)
  newFs.value = ''
  saveLocalData()
}

// ========== 笔记 ==========
const chapterNotes = ref('')

function getLocalKey() { return `ch_notes_${store.currentId}_${no.value}` }
function loadLocalData() {
  try {
    const raw = localStorage.getItem(getLocalKey())
    if (raw) { const d = JSON.parse(raw); foreshadowList.value = d.foreshadows || []; chapterNotes.value = d.notes || '' }
  } catch {}
}
function saveLocalData() {
  try { localStorage.setItem(getLocalKey(), JSON.stringify({ foreshadows: foreshadowList.value, notes: chapterNotes.value })) } catch {}
}
function saveNotes() { saveLocalData(); ElMessage.success('笔记已保存') }

watch(no, async (newNo) => {
  review.value = null; editing.value = false; stopTypewriter()
  if (store.currentId) await store.loadChapter(newNo)
  loadLocalData()
})
watch(() => store.chapter, (ch) => {
  if (ch && ch.chapter_no === no.value && !editing.value) startTypewriter(ch.content)
})

const totalChapters = computed(() => {
  const o = store.outline || []; let max = 0
  for (const vol of o) for (const c of (vol.chapters || [])) { if (typeof c.chapter === 'number' && c.chapter > max) max = c.chapter }
  return max || 30
})
const hasPrev = computed(() => no.value > 1)
const hasNext = computed(() => no.value < totalChapters.value)

const reviewType = computed(() => {
  const v = review.value?.verdict || ''
  if (v.includes('打回')) return 'danger'
  if (v.includes('大修')) return 'warning'
  return 'success'
})

const chapterCharacters = computed(() => store.characters || [])

// ========== 角色关系数据解析（抽成共享 composable，见 useForceGraph.js） ==========
const { showRelDialog, showHidePanel, centerChar, relCanvas, allCharNames, rawEdges, miniNodes, miniEdges, _hiddenNodes, setCenter, onCenterChange, shuffleLayout, toggleNodeVisibility, showAllNodes, hideAllNodesExceptCenter, startForceGraph, stopForceGraph, onCanvasMD, onCanvasMM, onCanvasMouseUp, onCanvasClick, onCanvasDblClick, onCanvasWheel } = useForceGraph(store)

// ========== 右侧停靠面板（固定在视口右侧 + 仅上下重排拖拽） ==========
const DOCK_ORDER_KEY = 'ch_dock_order'

const defaultOrder = { summary:0, foreshadow:1, chars:2, relation:3, notes:4, nav:5 }
const orderMap = reactive({ ...defaultOrder })

function panelStyle(key) { return { order: orderMap[key] } }

function loadDockOrder() {
  try {
    const saved = localStorage.getItem(DOCK_ORDER_KEY)
    if (saved) { const o = JSON.parse(saved); for (const k in defaultOrder) if (typeof o[k] === 'number') orderMap[k] = o[k]; return }
  } catch {}
}
function saveDockOrder() {
  try { localStorage.setItem(DOCK_ORDER_KEY, JSON.stringify({ ...orderMap })) } catch {}
}

// 拖拽状态
let _dragKey = null

/** 在拖拽手柄（header）上按下时启动拖拽（仅在本栏内上下重排顺序） */
function onHeaderDragStart(evt, key) {
  if (evt.button !== 0) return
  evt.preventDefault()
  _dragKey = key
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  evt.currentTarget.closest('.dock-panel')?.classList.add('dragging')
}

function onDragMove(evt) {
  if (!_dragKey) return
  evt.preventDefault()
  const railEl = dockRailRef.value
  if (!railEl) return
  const panels = railEl.querySelectorAll('.dock-panel')
  for (const el of panels) {
    const r = el.getBoundingClientRect()
    if (evt.clientY >= r.top && evt.clientY <= r.bottom) {
      const key = el.getAttribute('data-key')
      if (key && key !== _dragKey) {
        const tmp = orderMap[_dragKey]
        orderMap[_dragKey] = orderMap[key]
        orderMap[key] = tmp
      }
      break
    }
  }
}

function onDragEnd() {
  if (_dragKey) {
    saveDockOrder()
    _dragKey = null
    document.querySelectorAll('.dock-panel.dragging').forEach(el => el.classList.remove('dragging'))
  }
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
}

const dockRailRef = ref(null)

onMounted(async () => {
  loadDockOrder()
  loadTheme()
  if (store.currentId) {
    await store.loadChapters()
    await store.loadChapter(no.value)
    if (!store.characters.length) await store.loadCharacters().catch(() => {})
  }
  loadLocalData()
  if (store.chapter && store.chapter.chapter_no === no.value && !editing.value) startTypewriter(store.chapter.content)
})

onBeforeUnmount(() => {
  stopForceGraph()
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
})

async function onGen() {
  if (!store.currentId) { ElMessage.warning('请先在左侧选择/创建小说'); return }
  try { await store.genChapter(no.value); ElMessage.success(`第 ${no.value} 章已生成并保存`) }
  catch (e) { ElMessage.error('生成失败：' + (e?.response?.data?.detail || e.message)) }
}
async function onReview() {
  revLoading.value = true
  try { review.value = await store.review({ novel_id: store.currentId, chapter_no: no.value }) }
  catch (e) { ElMessage.error('审校失败：' + (e?.response?.data?.detail || e.message)) }
  finally { revLoading.value = false }
}
function onEdit() { stopTypewriter(); draft.value = store.chapter.content; editing.value = true }
function onCancelEdit() { editing.value = false }
async function onSaveEdit() {
  if (!store.currentId) return
  saving.value = true
  try { await store.updateChapter(store.currentId, no.value, draft.value, store.chapter.title); editing.value = false; ElMessage.success(`第 ${no.value} 章的修改已保存`) }
  catch (e) { ElMessage.error('保存失败：' + (e?.response?.data?.detail || e.message)) }
  finally { saving.value = false }
}
function onPrev() { if (hasPrev.value) { no.value--; review.value = null } }
function onNext() { if (hasNext.value) { no.value++; review.value = null } }
</script>

<style scoped>
/* ========== 页面基础 ========== */
.page{padding:20px 28px;min-height:100vh;transition:background .3s,color .3s}
.page-header-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}
.page-header-row h2{margin:0;font-size:22px}
.mt{margin-top:16px}
.review-banner{font-size:14px}

/* 工具栏 */
.toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:14px 0;border-bottom:1px solid var(--el-border-color-lighter);margin-bottom:16px}
.label{font-size:15px;font-weight:500}

/* ========== 左右布局 ========== */
.main-wrapper{
  display:flex;
  align-items:flex-start;
  gap:16px;
}
.content-area{flex:1;max-width:960px;min-width:0}

/* 右侧停靠轨道 —— 紧贴正文右侧，滚动时粘性固定 */
.dock-rail{
  position:sticky;
  top:84px;
  width:264px;
  flex-shrink:0;
  display:flex;
  flex-direction:column;
  gap:12px;
  padding:2px 4px 2px 2px;
  z-index:50;
  max-height:calc(100vh - 108px);
  overflow-y:auto;
}
.dock-rail::-webkit-scrollbar{width:6px}
.dock-rail::-webkit-scrollbar-thumb{background:rgba(148,163,184,0.4);border-radius:3px}

/* ======================================== */
/*  深色主题                                */
/* ======================================== */
.theme-dark{
  background:#0f172a;
  color:#e2e8f0;
}
.theme-dark .page-header-row h2{color:#f8fafc}
.theme-dark .label{color:#94a3b8}
.theme-dark .ch-title{font-size:22px;color:#f8fafc;font-weight:700}
.theme-dark .content-body{white-space:pre-wrap;line-height:2.2;font-size:18px;color:#f1f5f9;margin-top:16px;letter-spacing:0.5px;text-shadow:0 1px 3px rgba(0,0,0,0.5)}
.theme-dark .editor :deep(textarea){font-size:17px!important;line-height:2.1!important;color:#f1f5f9!important;background:transparent}
.theme-dark .muted{color:#94a3b8;font-size:13px}
.theme-dark .muted-xs{color:#64748b;font-size:11px}
.theme-dark .caret{color:#60a5fa;animation:caret-blink 1s steps(1) infinite;font-weight:700}

/* 停靠面板 — 深色 */
.theme-dark .dock-panel{
  background:rgba(30,41,59,0.95);
  border:1px solid rgba(71,85,105,0.4);
  border-radius:12px;
  overflow:hidden;
  box-shadow:0 4px 16px rgba(0,0,0,0.3);
  transition:box-shadow .2s, transform .15s;
  cursor:default;
  position:relative;
}
.theme-dark .dock-panel:hover{box-shadow:0 6px 24px rgba(0,0,0,0.4)}
.theme-dark .dock-panel.dragging{
  box-shadow:0 8px 32px rgba(0,0,0,0.5);
  transform:scale(1.02);
  z-index:10;
}
.theme-dark .dp-header{
  display:flex;justify-content:space-between;align-items:center;
  padding:9px 12px;background:linear-gradient(135deg,rgba(64,158,255,0.12),rgba(64,158,255,0.04));
  border-bottom:1px solid rgba(71,85,105,0.3);
  cursor:ns-resize;
  user-select:none;
}
.theme-dark .dp-drag{
  font-size:14px;color:#409eff;
  letter-spacing:2px;
  font-weight:700;
  opacity:0.7;
  transition:opacity .2s;
}
.theme-dark .dp-header:hover .dp-drag{opacity:1}
.theme-dark .dp-title{font-size:13px;font-weight:700;color:#e2e8f0}
.theme-dark .dp-body{padding:10px 12px;font-size:13px;color:#cbd5e1}
.theme-dark .info-label{color:#94a3b8}
.theme-dark .info-val{color:#e2e8f0;font-weight:500}
.theme-dark .info-val.bold{font-weight:700;color:#f8fafc}
.theme-dark .fs-item{color:#cbd5e1}
.theme-dark .fs-dot{background:#f59e0b}
.theme-dark .char-chip-sm span{color:#e2e8f0}
.theme-dark .empty-mini{color:#64748b}
.theme-dark .fp-link{color:#409eff}
.theme-dark .rel-hint{color:#64748b}
.theme-dark .notes-in :deep(textarea){color:#e2e8f0!important;background:transparent}
.theme-dark .nav-link-sm{color:#94a3b8}
.theme-dark .nav-link-sm:hover{color:#409eff}
.theme-dark .medge{stroke:#475569;stroke-width:1;stroke-opacity:0.4}
.theme-dark .mnode{fill:#334155;stroke:#64748b;stroke-width:1.5}
.theme-dark .mnode.hi{fill:#409eff;stroke:#93c5fd}
.theme-dark .cp-label{color:#e2e8f0}
.theme-dark .cp-legend{color:#94a3b8}
.theme-dark .rel-dialog :deep(.el-dialog__title){color:#f1f5f9}

/* ======================================== */
/*  浅色主题                                */
/* ======================================== */
.theme-light{
  background:#f8fafc;
  color:#1e293b;
}
.theme-light .page-header-row h2{color:#0f172a}
.theme-light .label{color:#475569}
.theme-light .ch-title{font-size:22px;color:#0f172a;font-weight:700}
.theme-light .content-body{white-space:pre-wrap;line-height:2.2;font-size:18px;color:#1e293b;margin-top:16px;letter-spacing:0.5px}
.theme-light .editor :deep(textarea){font-size:17px!important;line-height:2.1!important;color:#1e293b!important;background:transparent}
.theme-light .muted{color:#64748b;font-size:13px}
.theme-light .muted-xs{color:#94a3b8;font-size:11px}
.theme-light .caret{color:#2563eb;animation:caret-blink 1s steps(1) infinite;font-weight:700}

/* 停靠面板 — 浅色 */
.theme-light .dock-panel{
  background:rgba(255,255,255,0.98);
  border:1px solid rgba(203,213,225,0.6);
  border-radius:12px;
  overflow:hidden;
  box-shadow:0 4px 16px rgba(0,0,0,0.06);
  transition:box-shadow .2s, transform .15s;
  cursor:default;
  position:relative;
}
.theme-light .dock-panel:hover{box-shadow:0 6px 24px rgba(0,0,0,0.1)}
.theme-light .dock-panel.dragging{
  box-shadow:0 8px 32px rgba(0,0,0,0.15);
  transform:scale(1.02);
  z-index:10;
}
.theme-light .dp-header{
  display:flex;justify-content:space-between;align-items:center;
  padding:9px 12px;background:linear-gradient(135deg,rgba(59,130,246,0.06),rgba(59,130,246,0.02));
  border-bottom:1px solid rgba(203,213,225,0.5);
  cursor:ns-resize;
  user-select:none;
}
.theme-light .dp-drag{
  font-size:14px;color:#3b82f6;
  letter-spacing:2px;
  font-weight:700;
  opacity:0.6;
  transition:opacity .2s;
}
.theme-light .dp-header:hover .dp-drag{opacity:1}
.theme-light .dp-title{font-size:13px;font-weight:700;color:#1e293b}
.theme-light .dp-body{padding:10px 12px;font-size:13px;color:#334155}
.theme-light .info-label{color:#64748b}
.theme-light .info-val{color:#1e293b;font-weight:500}
.theme-light .info-val.bold{font-weight:700;color:#0f172a}
.theme-light .fs-item{color:#475569}
.theme-light .fs-dot{background:#d97706}
.theme-light .char-chip-sm span{color:#1e293b}
.theme-light .empty-mini{color:#94a3b8}
.theme-light .fp-link{color:#2563eb}
.theme-light .rel-hint{color:#94a3b8}
.theme-light .notes-in :deep(textarea){color:#1e293b!important;background:transparent}
.theme-light .nav-link-sm{color:#475569}
.theme-light .nav-link-sm:hover{color:#2563eb}
.theme-light .medge{stroke:#94a3b8;stroke-width:1;stroke-opacity:0.35}
.theme-light .mnode{fill:#cbd5e1;stroke:#64748b;stroke-width:1.5}
.theme-light .mnode.hi{fill:#3b82f6;stroke:#93c5fd}
.theme-light .cp-label{color:#1e293b}
.theme-light .cp-legend{color:#64748b}
.theme-light .rel-dialog :deep(.el-dialog__title){color:#0f172a}

/* ======================================== */
/*  通用样式                                */
/* ======================================== */
@keyframes caret-blink{50%{opacity:0}}
.saved-hint{margin-bottom:14px;font-size:14px}
.editor{margin-bottom:12px;font-family:inherit;font-size:17px}
.edit-actions{display:flex;align-items:center;gap:10px}

/* 信息行 */
.info-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px dashed;border-color:rgba(148,163,184,0.2);font-size:13px}
.info-row:last-child{border-bottom:none}

/* 伏笔 */
.fs-list{display:flex;flex-direction:column;gap:6px;margin-bottom:8px}
.fs-item{display:flex;align-items:flex-start;gap:6px;font-size:12px;line-height:1.6}
.fs-dot{width:5px;height:5px;border-radius:50%;margin-top:6px;flex-shrink:0}
.add-fs{display:flex;gap:4px;margin-top:6px}

/* 角色 */
.char-list-sm{display:flex;flex-direction:column;gap:4px;margin-bottom:6px}
.char-chip-sm{display:flex;align-items:center;gap:6px;padding:4px 6px;border-radius:6px;background:rgba(64,158,255,0.06)}
.char-chip-sm span{font-size:12px}
.empty-mini{text-align:center;font-size:12px;padding:8px 0}
.fp-link{display:block;text-align:right;font-size:11px;text-decoration:none;margin-top:4px}
.fp-link:hover{text-decoration:underline}

/* 关系预览 */
.rel-preview{cursor:pointer;text-align:center;padding:4px 0}
.mini-graph{width:100%;height:auto;display:block}
.rel-hint{font-size:11px;margin:4px 0 0}

/* ===== 关系图操作手册 ===== */
.rel-manual{
  margin-top:14px;
  border:1px solid var(--el-border-color-lighter);
  border-radius:12px;
  padding:14px 16px;
  background:rgba(64,158,255,0.04);
}
.rm-title{font-size:14px;font-weight:700;margin-bottom:10px;color:var(--el-text-color-primary)}
.rm-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px}
.rm-item{display:flex;align-items:flex-start;gap:9px;font-size:12.5px;line-height:1.55;color:var(--el-text-color-regular)}
.rm-icon{flex-shrink:0;font-size:16px;line-height:1.4}
.rm-text{flex:1}
.rm-text b{color:var(--el-text-color-primary);font-weight:600}
.rm-text .leg-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 2px;vertical-align:middle}
.rm-text .leg-dot.ally{background:#22c55e}
.rm-text .leg-dot.neutral{background:#94a3b8}
.rm-text .leg-dot.enemy{background:#ef4444}

/* 笔记 */
.notes-ft{display:flex;justify-content:space-between;align-items:center;margin-top:6px}

/* 导航链接 */
.nav-link-sm{display:block;padding:5px 8px;border-radius:6px;font-size:13px;text-decoration:none;transition:all .15s}

/* ====== 关系网弹窗 ====== */
.rel-dialog :deep(.el-dialog__header){padding:16px 20px;border-bottom:1px solid var(--el-border-color-lighter)}
.rel-dialog :deep(.el-dialog__title){font-size:18px;font-weight:700}
.rel-dialog :deep(.el-dialog__body){padding:0}
.rel-dialog-body{padding:20px}

.center-picker{display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.cp-legend{display:flex;gap:14px;margin-left:auto;font-size:12px}
.leg-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:middle}
.leg-dot.ally{background:#22c55e}
.leg-dot.neutral{background:#94a3b8}
.leg-dot.enemy{background:#ef4444}

/* Canvas 3D 关系图 —— 全屏自适应 */
.rel-main-area{display:flex;gap:16px;margin-bottom:16px}
.canvas-wrap{flex:1;border-radius:12px;overflow:hidden;border:1px solid var(--el-border-color-lighter);min-height:450px;display:flex;align-items:center;justify-content:center;background:#0c1220}
.rel-canvas{display:block;cursor:grab;border-radius:12px}
.rel-canvas:active{cursor:grabbing}

/* ====== 隐藏/显示节点面板 ====== */
.hide-panel{
  width:200px;flex-shrink:0;
  background:var(--el-bg-color);
  border:1px solid var(--el-border-color-lighter);
  border-radius:10px;padding:14px;
  display:flex;flex-direction:column;gap:8px;
  max-height:500px;overflow-y:auto;
}
.hp-title{font-size:15px;font-weight:700;margin:0 0 2px}
.hp-subtitle{font-size:11.5px;color:var(--el-text-color-secondary);margin:0 0 6px;line-height:1.4}
.hp-list{display:flex;flex-direction:column;gap:4px}
.hp-item{
  display:flex;align-items:center;gap:8px;
  padding:5px 8px;border-radius:6px;cursor:pointer;
  transition:background .15s;font-size:13px;
}
.hp-item:hover{background:var(--el-fill-color-light)}
.hp-item.hp-hidden{opacity:0.45}
.hp-item input[type="checkbox"]{cursor:pointer;accent-color:var(--el-color-primary)}
.hp-name{flex:1;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hp-status{font-size:11px;color:var(--el-text-color-secondary);white-space:nowrap}
.hp-actions{display:flex;gap:6px;margin-top:8px;padding-top:8px;border-top:1px solid var(--el-border-color-lighter)}

/* 面板滑入滑出动画 */
.slide-fade-enter-active{transition:all .25s ease-out}
.slide-fade-leave-active{transition:all .2s ease-in}
.slide-fade-enter-from{opacity:0;transform:translateX(20px)}
.slide-fade-leave-to{opacity:0;transform:translateX(20px)}
</style>
