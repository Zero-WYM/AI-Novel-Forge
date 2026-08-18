<template>
  <div class="page">
    <h2>小说工作台</h2>

    <!-- 当前有书：显示书名 + 操作 -->
    <el-card v-if="store.currentId && store.currentNovel">
      <div class="book-head">
        <div class="book-title">
          <div class="bt">{{ store.currentNovel.title || '(未命名)' }}</div>
          <div class="bmeta">
            <el-tag size="small">{{ store.currentNovel.genre }}</el-tag>
            <span class="muted">· 目标 {{ store.currentNovel.target_chapters }} 章</span>
            <span class="muted">· {{ store.currentNovel.premise }}</span>
          </div>
        </div>
        <div class="book-id muted">ID: {{ store.currentId }}</div>
      </div>
      <el-divider class="mt-0" />
      <el-button type="success" size="large" @click="onBootstrap" :loading="store.loading">
        ✦ 一键成书（世界观 + 大纲 + 角色 一次性生成）
      </el-button>
      <div class="mt">
        <el-button @click="onOutline">① 仅生成大纲</el-button>
        <el-button type="primary" @click="goOutline">② 去大纲选章节写作 →</el-button>
        <el-button @click="openSwitcher">切换 / 新建</el-button>
      </div>
    </el-card>

    <!-- 当前没书：直接展示创建表单，并给出「切换」的入口 -->
    <el-card v-else>
      <h3>创建新书</h3>
      <el-form :model="form" label-width="100px">
        <el-form-item label="书名"><el-input v-model="form.title" placeholder="例：凡人修仙模拟器" /></el-form-item>
        <el-form-item label="类型"><el-input v-model="form.genre" placeholder="玄幻修仙 / 都市 / 科幻 …" /></el-form-item>
        <el-form-item label="核心设定"><el-input v-model="form.premise" type="textarea" :rows="3" placeholder="一两句话描述主要剧情" /></el-form-item>
        <el-form-item label="目标章数"><el-input-number v-model="form.target_chapters" :min="1" :max="1000" /></el-form-item>
        <el-form-item label="风格"><el-input v-model="form.style" placeholder="爽文，节奏快 …" /></el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onCreate">创建并开始</el-button>
          <el-button @click="openSwitcher" v-if="store.novels.length">从已有书目切换</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 「切换 / 新建」弹窗 -->
    <el-dialog v-model="switcherVisible" title="选择小说" width="640px">
      <div class="lib-head">
        <span class="muted">共 {{ store.novels.length }} 本书</span>
        <el-button size="small" type="primary" @click="goCreate">+ 新建一本</el-button>
      </div>
      <el-table :data="store.novels" stripe style="width:100%">
        <el-table-column prop="title" label="书名" min-width="160" />
        <el-table-column prop="genre" label="类型" width="120" />
        <el-table-column prop="premise" label="设定" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.id !== store.currentId" type="primary" size="small" @click="pickNovel(row)">切到这本</el-button>
            <el-tag v-else type="success">当前</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useNovelStore } from '../stores/novel'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const store = useNovelStore()
const router = useRouter()

const form = ref({ title: '', genre: '玄幻修仙', premise: '', target_chapters: 100, style: '爽文，节奏快' })
const switcherVisible = ref(false)

function formatDate(s) {
  if (!s) return ''
  try { return new Date(s).toLocaleString() } catch { return s }
}

// 挂载时：尝试恢复当前书的详情（从本地缓存的 ID）+ 拉取所有书目
onMounted(async () => {
  await Promise.all([store.loadCurrentNovel(), store.loadNovelList()])
})

async function onCreate() {
  if (!form.value.title.trim()) { ElMessage.warning('请先填写书名'); return }
  try {
    await store.create(form.value)
    ElMessage.success('创建成功，现在可以「一键成书」了')
    // 留在首页展示成书入口；不自动跳走
  } catch (e) {
    // 错误已由全局拦截器统一弹提示（如书名重复 / 服务端异常），此处不再重复弹
  }
}

async function onBootstrap() {
  if (!store.currentId) { ElMessage.warning('请先创建或选择一本小说'); return }
  try {
    const r = await store.bootstrap()
    ElMessage.success(`成书完成：已生成 ${r.character_count} 个角色、${r.outline_volumes} 卷大纲`)
    router.push('/outline')
  } catch (e) {
    // 错误已由全局拦截器统一弹友好提示（含 429「请稍后重试」），此处仅阻止跳转
  }
}

async function onOutline() {
  try {
    await store.genOutline()
    ElMessage.success('大纲生成完成')
    router.push('/outline')
  } catch (e) {
    // 错误已由全局拦截器统一弹提示，此处仅阻止跳转
  }
}

function goOutline() { router.push('/outline') }

async function openSwitcher() {
  await store.loadNovelList()
  switcherVisible.value = true
}

function pickNovel(row) {
  store.setCurrentId(row.id)        // 触发 loadCurrentNovel 刷新书名
  store.currentNovel = row           // 立即用列表里的数据，省一次请求
  switcherVisible.value = false
  ElMessage.success(`已切换到「${row.title || '(未命名)'}」`)
}

function goCreate() {
  // 在弹窗里直接新建：清掉当前 ID，关闭弹窗，让首页的创建表单出现
  store.currentId = ''
  store.currentNovel = null
  localStorage.removeItem('novel_id')
  switcherVisible.value = false
}
</script>

<style scoped>
.page { max-width: 880px; margin: 20px auto; }
.mt-0 { margin-top: 0; }
.muted { color: #94a3b8; font-size: 12px; }
.book-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.bt { font-size: 22px; font-weight: 700; color: #1f2937; }
.bmeta { margin-top: 6px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.book-id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.lib-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
</style>
