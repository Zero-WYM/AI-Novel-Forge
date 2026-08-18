<template>
  <div class="page" :class="isDark ? 'theme-dark' : 'theme-light'">
    <div class="head">
      <h2>角色面板</h2>
      <div>
        <el-button type="primary" :disabled="!store.currentId || store.loading" @click="gen">AI 生成角色</el-button>
        <el-button :disabled="!store.currentId" @click="refreshChars">加载</el-button>
        <el-button type="success" :disabled="!store.characters.length" @click="showRelDialog = true">🔗 关系图谱</el-button>
        <el-button v-if="anyEditing" type="success" @click="onSaveAll">💾 保存全部修改</el-button>
        <el-button v-if="anyEditing" @click="cancelAll">取消</el-button>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="charLoading" class="loading-row">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在加载角色数据…</span>
    </div>

    <!-- 空状态 -->
    <el-empty
      v-else-if="!store.characters.length"
      description="暂无角色，点击「AI 生成角色」由 CharacterDesigner 基于大纲与世界观设计人设卡"
    />

    <!-- 角色卡片列表 -->
    <div v-else class="cards">
      <el-card
        v-for="(c, idx) in store.characters"
        :key="c.name || idx"
        class="card" :class="[roleClass(c.role), isDark ? 'card-dark' : 'card-light']"
      >
        <template #header>
          <div class="card-head">
            <span class="cname">{{ c.name }}</span>
            <div class="card-actions">
              <el-tag :type="roleType(c.role)" size="small">{{ c.role || '未分类' }}</el-tag>
              <el-button
                link type="primary" size="small" @click="toggleEdit(idx)"
              >
                {{ editingIdx === idx ? '完成编辑' : '✏ 编辑' }}
              </el-button>
            </div>
          </div>
        </template>

        <!-- 阅读模式 -->
        <template v-if="editingIdx !== idx">
          <div class="row"><b>性格：</b><span>{{ c.personality || '-' }}</span></div>
          <div class="row"><b>动机：</b><span>{{ c.motivation || '-' }}</span></div>
          <div class="row" v-if="c.faction"><b>势力：</b><span>{{ c.faction }}</span></div>
          <div class="row" v-if="c.level"><b>境界：</b><span>{{ c.level }}</span></div>
          <div class="row" v-if="c.mood"><b>心境：</b><span>{{ c.mood }}</span></div>
          <div class="row" v-if="c.equipment"><b>装备：</b><span>{{ c.equipment }}</span></div>
          <div class="row" v-if="c.location"><b>所在地：</b><span>{{ c.location }}</span></div>
          <div class="row" v-if="c.appearance"><b>外貌：</b><span>{{ c.appearance }}</span></div>
          <div class="row" v-if="c.weakness"><b>弱点：</b><span>{{ c.weakness }}</span></div>
          <div class="row" v-if="c.relationships"><b>关系：</b><span>{{ c.relationships }}</span></div>
          <div class="row"><b>当前状态：</b><span>{{ c.current_status || '-' }}</span></div>
          <div class="row"><b>成长弧：</b><span>{{ c.growth_arc || '-' }}</span></div>
        </template>

        <!-- 编辑模式 -->
        <template v-else>
          <div class="edit-grid">
            <label>性格</label><el-input v-model="editBuf.personality" placeholder="角色性格特征" />
            <label>动机</label><el-input v-model="editBuf.motivation" placeholder="驱动角色的核心动机" />
            <label>势力</label><el-input v-model="editBuf.faction" placeholder="所属势力" />
            <label>境界</label><el-input v-model="editBuf.level" placeholder="修为境界" />
            <label>心境</label><el-input v-model="editBuf.mood" placeholder="当前心境" />
            <label>装备</label><el-input v-model="editBuf.equipment" placeholder="随身装备" />
            <label>所在地</label><el-input v-model="editBuf.location" placeholder="当前位置" />
            <label>外貌</label><el-input v-model="editBuf.appearance" placeholder="外形特征" />
            <label>弱点</label><el-input v-model="editBuf.weakness" placeholder="致命弱点" />
            <label>关系</label><el-input v-model="editBuf.relationships" placeholder="与其他角色关系" />
            <label>当前状态</label><el-input v-model="editBuf.current_status" placeholder="此刻状态" />
            <label>成长弧</label><el-input v-model="editBuf.growth_arc" placeholder="角色成长轨迹" />
          </div>
          <div class="edit-bar">
            <el-button type="primary" size="small" @click="saveOne(idx)">保存此角色</el-button>
            <el-button size="small" @click="cancelOne(idx)">还原</el-button>
          </div>
        </template>
      </el-card>
    </div>

    <!-- ====== 角色关系网弹窗（3D Canvas 力导向 · 全屏） ====== -->
    <el-dialog v-model="showRelDialog" title="🔗 角色关系网络" :fullscreen="true" class="rel-dialog" draggable :close-on-click-modal="false"
      @opened="startForceGraph" @close="stopForceGraph">
      <div class="rel-dialog-body">
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

        <div class="rel-main-area">
          <div class="canvas-wrap">
            <canvas ref="relCanvas" class="rel-canvas" />
          </div>
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

        <div class="rel-manual">
          <div class="rm-title">📖 操作手册</div>
          <div class="rm-grid">
            <div class="rm-item"><span class="rm-icon">🖱️</span><div class="rm-text"><b>拖拽节点</b>移动位置，松手后自动<b>钉住</b>（金色📌），不再回弹。</div></div>
            <div class="rm-item"><span class="rm-icon">👆</span><div class="rm-text"><b>单击节点</b>切换为新的<b>中心角色</b>。</div></div>
            <div class="rm-item"><span class="rm-icon">👆👆</span><div class="rm-text"><b>双击已钉住节点</b>取消钉住。</div></div>
            <div class="rm-item"><span class="rm-icon">👁</span><div class="rm-text"><b>隐藏节点</b>简化视图，隐藏的不参与布局。</div></div>
            <div class="rm-item"><span class="rm-icon">🔄</span><div class="rm-text"><b>打散重排</b>清除钉住并随机重布。</div></div>
            <div class="rm-item"><span class="rm-icon">🔘</span><div class="rm-text"><b>滚轮缩放</b>整个图。</div></div>
            <div class="rm-item"><span class="rm-icon">🎨</span><div class="rm-text">连线：<span class="leg-dot ally"></span><b>盟友</b> · <span class="leg-dot neutral"></span><b>中立</b> · <span class="leg-dot enemy"></span><b>敌对</b>。</div></div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { useNovelStore } from '../stores/novel'
import { useForceGraph } from '../composables/useForceGraph'

const store = useNovelStore()
const charLoading = ref(false)

// ========== 全局主题（同 App.vue / ChapterView 共用 key） ==========
const THEME_KEY = 'global_theme_dark'
const isDark = ref(true)
function loadTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved !== null) { isDark.value = saved === 'true'; return }
  } catch {}
  isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
}
window.addEventListener('storage', (e) => {
  if (e.key === THEME_KEY && e.newValue !== null) isDark.value = e.newValue === 'true'
})
loadTheme()

// 当前正在编辑的角色索引（-1 = 无）
const editingIdx = ref(-1)
// 编辑缓冲区
const editBuf = reactive({})

// 是否有任意卡片处于编辑态
const anyEditing = computed(() => editingIdx.value >= 0)

function roleClass(role) {
  if (role === '反派') return 'card-villain'
  if (role === '主角') return 'card-protagonist'
  return ''
}
function roleType(role) {
  if (role === '主角') return 'success'
  if (role === '反派') return 'danger'
  if (role === '势力代表') return 'warning'
  return 'info'
}

async function gen() { await store.generateCharacters() }

// 强制刷新角色数据（带 loading 状态）
async function refreshChars() {
  if (!store.currentId) {
    ElMessage.warning('请先在左侧选择或创建一本小说')
    return
  }
  charLoading.value = true
  try {
    await store.loadCharacters()
  } catch (e) {
    console.error('加载角色失败:', e)
  } finally {
    charLoading.value = false
  }
}

function toggleEdit(idx) {
  if (editingIdx.value === idx) {
    saveOne(idx)
    return
  }
  const c = store.characters[idx]
  editingIdx.value = idx
  Object.keys(editBuf).forEach(k => delete editBuf[k])
  Object.assign(editBuf, { ...c })
}

async function saveOne(idx) {
  Object.assign(store.characters[idx], { ...editBuf })
  try {
    await store.saveCharacters()
    ElMessage.success(`「${store.characters[idx].name}」的修改已保存`)
    editingIdx.value = -1
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e.message))
  }
}
function cancelOne(idx) { editingIdx.value = -1 }

async function onSaveAll() {
  try {
    await store.saveCharacters()
    ElMessage.success('全部角色修改已保存')
    editingIdx.value = -1
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.response?.data?.detail || e.message))
  }
}
function cancelAll() { editingIdx.value = -1 }

// ========== 关系图谱引擎（与 ChapterView 同款） ==========

// ---- 数据解析（已抽成共享 composable，见 useForceGraph.js） ----
const { showRelDialog, showHidePanel, centerChar, relCanvas, allCharNames, rawEdges, miniNodes, miniEdges, _hiddenNodes, setCenter, onCenterChange, shuffleLayout, toggleNodeVisibility, showAllNodes, hideAllNodesExceptCenter, startForceGraph, stopForceGraph, onCanvasMD, onCanvasMM, onCanvasMouseUp, onCanvasClick, onCanvasDblClick, onCanvasWheel } = useForceGraph(store)

onMounted(() => {
  loadTheme()
  if (store.currentId) refreshChars()
})
onBeforeUnmount(() => stopForceGraph())
</script>

<style scoped>
/* ========== 页面基础 ========== */
.page { max-width: 1100px; margin: 20px auto; padding: 0 20px; min-height: 100vh; transition: background .3s, color .3s; }
.head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }

/* ======================================== */
/*  深色主题                                */
/* ======================================== */
.theme-dark { background: transparent; }
.theme-dark .head h2 { margin: 0; font-size: 22px; color: #f8fafc; }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.card-actions { display: flex; align-items: center; gap: 4px; }
.theme-dark .cname { font-weight: 600; font-size: 16px; color: #f1f5f9; }
.theme-dark .row { font-size: 13px; line-height: 1.8; color: #cbd5e1; }
.theme-dark .row b { color: #94a3b8; }
.theme-dark .row span { color: #e2e8f0; }
.card-protagonist { border-top: 3px solid #16a34a; }
.card-villain { border-top: 3px solid #dc2626; }

/* 深色卡片 */
.theme-dark .card-dark { background: rgba(30,41,59,0.7); border: 1px solid rgba(71,85,105,0.4); }
.theme-dark .card-dark :deep(.el-card__header) { background: rgba(15,23,42,0.5); border-bottom: 1px solid rgba(71,85,105,0.3); }
.theme-dark .card-dark :deep(.el-card__body) { background: transparent; }

/* 加载态 */
.loading-row {
  display: flex; align-items: center; gap: 10px;
  padding: 40px 0; font-size: 15px; justify-content: center;
}
.theme-dark .loading-row { color: #94a3b8; }

/* 编辑模式网格 */
.edit-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 6px 10px;
  align-items: center;
  margin-top: 8px;
}
.theme-dark .edit-grid label { font-size: 12.5px; color: #94a3b8; font-weight: 500; text-align: right; white-space: nowrap; }
.theme-dark .edit-grid .el-input { font-size: 13px; }
.edit-bar { margin-top: 12px; padding-top: 10px; display: flex; gap: 8px; }
.theme-dark .edit-bar { border-top: 1px solid rgba(148,163,184,0.15); }

/* ======================================== */
/*  浅色主题                                */
/* ======================================== */
.theme-light { background: transparent; }
.theme-light .head h2 { margin: 0; font-size: 22px; color: #0f172a; }
.theme-light .cname { font-weight: 600; font-size: 16px; color: #0f172a; }
.theme-light .row { font-size: 13px; line-height: 1.8; color: #475569; }
.theme-light .row b { color: #64748b; }
.theme-light .row span { color: #1e293b; }
.theme-light .loading-row { color: #64748b; }

/* 浅色卡片 */
.theme-light .card-light { background: rgba(255,255,255,0.9); border: 1px solid rgba(203,213,225,0.5); }
.theme-light .card-light :deep(.el-card__header) { background: rgba(248,250,252,0.8); border-bottom: 1px solid rgba(203,213,225,0.4); }
.theme-light .card-light :deep(.el-card__body) { background: transparent; }

.theme-light .edit-grid label { font-size: 12.5px; color: #64748b; font-weight: 500; text-align: right; white-space: nowrap; }
.theme-light .edit-grid .el-input { font-size: 13px; }
.theme-light .edit-bar { border-top: 1px solid rgba(203,213,225,0.4); }

/* ====== 关系网弹窗（与 ChapterView 同款） ====== */
.rel-dialog :deep(.el-dialog__header){padding:16px 20px;border-bottom:1px solid var(--el-border-color-lighter)}
.rel-dialog :deep(.el-dialog__title){font-size:18px;font-weight:700}
.rel-dialog :deep(.el-dialog__body){padding:0}
.rel-dialog-body{padding:20px}
.center-picker{display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.cp-legend{display:flex;gap:14px;margin-left:auto;font-size:12px}
.leg-dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:middle}
.leg-dot.ally{background:#22c55e}.leg-dot.neutral{background:#94a3b8}.leg-dot.enemy{background:#ef4444}

.rel-main-area{display:flex;gap:16px;margin-bottom:16px}
.canvas-wrap{flex:1;border-radius:12px;overflow:hidden;border:1px solid var(--el-border-color-lighter);min-height:450px;display:flex;align-items:center;justify-content:center;background:#0c1220}
.rel-canvas{display:block;cursor:grab;border-radius:12px}.rel-canvas:active{cursor:grabbing}

/* 隐藏节点面板 */
.hide-panel{width:200px;flex-shrink:0;background:var(--el-bg-color);border:1px solid var(--el-border-color-lighter);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:8px;max-height:500px;overflow-y:auto}
.hp-title{font-size:15px;font-weight:700;margin:0 0 2px}
.hp-subtitle{font-size:11.5px;color:var(--el-text-color-secondary);margin:0 0 6px;line-height:1.4}
.hp-list{display:flex;flex-direction:column;gap:4px}
.hp-item{display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:6px;cursor:pointer;transition:background .15s;font-size:13px}
.hp-item:hover{background:var(--el-fill-color-light)}
.hp-item.hp-hidden{opacity:0.45}
.hp-item input[type="checkbox"]{cursor:pointer;accent-color:var(--el-color-primary)}
.hp-name{flex:1;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hp-status{font-size:11px;color:var(--el-text-color-secondary);white-space:nowrap}
.hp-actions{display:flex;gap:6px;margin-top:8px;padding-top:8px;border-top:1px solid var(--el-border-color-lighter)}

.slide-fade-enter-active{transition:all .25s ease-out}
.slide-fade-leave-active{transition:all .2s ease-in}
.slide-fade-enter-from{opacity:0;transform:translateX(20px)}
.slide-fade-leave-to{opacity:0;transform:translateX(20px)}

/* 操作手册 */
.rel-manual{border-radius:10px;padding:14px;border:1px solid var(--el-border-color-lighter)}
.rm-title{font-size:15px;font-weight:700;margin-bottom:10px}
.rm-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.rm-item{display:flex;gap:8px;font-size:12.5px;line-height:1.55}
.rm-icon{flex-shrink:0;font-size:16px}
.rm-text{color:var(--el-text-color-primary)}
.rm-text b{color:var(--el-text-color-primary)}
.rm-text .leg-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 2px;vertical-align:middle}
.rm-text .leg-dot.ally{background:#22c55e}.rm-text .leg-dot.neutral{background:#94a3b8}.rm-text .leg-dot.enemy{background:#ef4444}
</style>
