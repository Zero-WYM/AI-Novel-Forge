<template>
  <div class="page">
    <div class="head">
      <h2>世界观设定</h2>
      <div>
        <el-button type="primary" :disabled="!store.currentId || store.loading" @click="gen">AI 生成世界观</el-button>
        <el-button v-if="store.world" :disabled="store.loading" @click="store.saveWorld()">保存修改</el-button>
      </div>
    </div>

    <el-alert
      v-if="!store.world"
      type="info" :closable="false"
      title="尚未生成世界观"
      description="点击「AI 生成世界观」，由 WorldBuilder 构建修炼体系、地图、势力、宝物功法与种族，并写入知识库供章节检索。"
    />

    <template v-else>
      <el-card v-for="cat in cats" :key="cat.key" class="mt">
        <template #header>
          <div class="card-head">
            <span>{{ cat.label }}</span>
            <el-button link type="primary" size="small" @click="toggleEdit(cat.key)">
              {{ editing[cat.key] ? '完成' : '编辑' }}
            </el-button>
          </div>
        </template>
        <el-input
          v-if="editing[cat.key]" type="textarea" :rows="3"
          v-model="editText[cat.key]" @blur="commitEdit(cat.key)"
          placeholder="每行一项，或用逗号分隔"
        />
        <div v-else class="tags">
          <el-tag v-for="(it, i) in store.world[cat.key]" :key="i" class="tag">{{ it }}</el-tag>
          <span v-if="!store.world[cat.key].length" class="muted">（空）</span>
        </div>
      </el-card>

      <el-card class="mt">
        <template #header>知识条目（写入 RAG，供章节生成检索）</template>
        <el-table :data="store.world.entries" size="small" border>
          <el-table-column prop="title" label="条目" width="160" />
          <el-table-column prop="category" label="类别" width="110" />
          <el-table-column label="内容">
            <template #default="{ row }">
              <el-input type="textarea" :rows="2" v-model="row.content" />
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="mt">
        <template #header>世界观总述</template>
        <el-input type="textarea" :rows="6" v-model="store.world.text" />
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { useNovelStore } from '../stores/novel'

const store = useNovelStore()

const cats = [
  { key: 'cultivation', label: '修炼体系（境界）' },
  { key: 'maps', label: '地图 / 地域' },
  { key: 'factions', label: '势力' },
  { key: 'treasures', label: '宝物 / 功法' },
  { key: 'races', label: '种族' },
]

const editing = reactive({})
const editText = reactive({})

function toggleEdit(key) {
  if (!editing[key]) {
    editText[key] = (store.world[key] || []).join('\n')
    editing[key] = true
  } else {
    commitEdit(key)
  }
}

function commitEdit(key) {
  store.world[key] = (editText[key] || '')
    .split(/[\n,，]/).map(s => s.trim()).filter(Boolean)
  editing[key] = false
}

async function gen() {
  await store.generateWorld()
}

onMounted(() => {
  if (store.currentId) store.loadWorld()
})
</script>

<style scoped>
.page { max-width: 960px; margin: 20px auto; }
.head { display: flex; justify-content: space-between; align-items: center; }
.mt { margin-top: 16px; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { margin: 0; }
.muted { color: #94a3b8; }
</style>
