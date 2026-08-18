<template>
  <div class="page">
    <h2>大纲编辑器</h2>
    <el-button type="primary" @click="onGen" :disabled="!store.currentId">生成大纲</el-button>
    <el-button @click="store.loadChapters()" :disabled="!store.currentId" class="ml">刷新已写列表</el-button>

    <div v-if="writtenSet.size" class="mt hint">
      已自动保存到数据库的章节：<el-tag
        v-for="n in Array.from(writtenSet).sort((a,b)=>a-b)"
        :key="n" type="success" size="small" effect="plain" class="tag">{{ n }}</el-tag>
    </div>

    <el-collapse v-if="store.outline.length" class="mt">
      <el-collapse-item v-for="vol in store.outline" :key="vol.volume" :title="vol.volume + (vol.arc ? ' · ' + vol.arc : '')">
        <el-table :data="vol.chapters" size="small">
          <el-table-column prop="chapter" label="章号" width="80">
            <template #default="{ row }">
              <span class="ch-no" :class="{ 'ch-written': writtenSet.has(row.chapter) }">{{ row.chapter }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="标题" min-width="160" />
          <el-table-column prop="hook" label="钩子" min-width="220" show-overflow-tooltip />
          <el-table-column prop="development" label="发展" min-width="220" show-overflow-tooltip />
          <el-table-column prop="climax" label="高潮" min-width="220" show-overflow-tooltip />
          <el-table-column prop="ending_hook" label="章末钩子" min-width="220" show-overflow-tooltip />
          <el-table-column label="操作" width="180" align="center" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                :type="writtenSet.has(row.chapter) ? 'default' : 'primary'"
                @click="onWrite(row.chapter)">
                {{ writtenSet.has(row.chapter) ? '重写这章' : '写这章' }}
              </el-button>
              <el-button
                size="small"
                type="info"
                :disabled="!writtenSet.has(row.chapter)"
                @click="onJump(row.chapter)">
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-collapse-item>
    </el-collapse>

    <el-empty v-else-if="store.currentId" description="还没有大纲，点击右上角「生成大纲」开始" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useNovelStore } from '../stores/novel'

const store = useNovelStore()
const router = useRouter()

// 已写章节的快速查询（Set O(1)）
const writtenSet = computed(() => new Set((store.chapters || []).map(c => c.chapter_no)))

onMounted(() => {
  if (store.currentId) {
    store.loadChapters()
    store.loadOutline() // 成书后或刷新时直接读取已存大纲，不再重复生成
  }
})

async function onGen() {
  try { await store.genOutline(); ElMessage.success('大纲生成完成') }
  catch (e) { ElMessage.error('大纲生成失败：' + (e?.response?.data?.detail || e.message)) }
}

// 大纲行 → 直接写该章节；写完后跳到章节页查看，并刷新"已写"标签
async function onWrite(chapterNo) {
  try {
    await store.genChapter(chapterNo)
    ElMessage.success(`第 ${chapterNo} 章已生成并保存到数据库`)
    router.push('/chapter')
  } catch (e) {
    ElMessage.error(`第 ${chapterNo} 章生成失败：` + (e?.response?.data?.detail || e.message))
  }
}

// 点击「✓ 已写」或章号 → 跳转到章节页并加载该章内容
function onJump(chapterNo) {
  store.chapter = null  // 清掉旧章节，避免闪现错位内容
  router.push({ path: '/chapter', query: { ch: chapterNo } })
}
</script>

<style scoped>
.page{max-width:1000px;margin:20px auto}
.mt{margin-top:16px}
.ml{margin-left:8px}
.ml-tag{margin-left:6px}
.ch-no{cursor:default;font-variant-numeric:tabular-nums}
.ch-written{color:#409eff;font-weight:700}
.jump-btn{margin-left:6px;font-size:12px}
.hint{color:#475569;font-size:13px}
.tag{margin-right:6px}
</style>