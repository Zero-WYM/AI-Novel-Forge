<template>
  <div class="page">
    <h2>RAG 检索调试面板</h2>
    <el-form label-width="100px">
      <el-form-item label="集合"><el-select v-model="form.collection"><el-option label="world" value="world"/><el-option label="chapter" value="chapter"/><el-option label="skill" value="skill"/></el-select></el-form-item>
      <el-form-item label="注入文档"><el-input v-model="docText" type="textarea" :rows="3" placeholder="一行一条或整段设定文本"/></el-form-item>
      <el-button @click="onIngest" type="success">注入知识库</el-button>
      <el-divider />
      <el-form-item label="检索 query"><el-input v-model="form.query"/></el-form-item>
      <el-button @click="onQuery" type="primary">检索</el-button>
    </el-form>
    <el-card v-if="results.length" class="mt">
      <div v-for="(r,i) in results" :key="i" class="res">{{ i+1 }}. {{ r.document }}</div>
    </el-card>
  </div>
</template>
<script setup>
import { ref, reactive } from 'vue'
import { useNovelStore } from '../stores/novel'
import api from '../utils/api'
const store = useNovelStore()
const form = reactive({ collection:'world', query:'' })
const docText = ref(''); const results = ref([])
async function onIngest(){
  if(!store.currentId){ alert('请先在工作台创建小说'); return }
  await api.ragIngest({novel_id:store.currentId, collection:form.collection, documents:[docText.value]})
  alert('已注入'); docText.value=''
}
async function onQuery(){
  const r = await api.ragQuery({novel_id:store.currentId, ...form, top_k:5})
  results.value = r.results
}
</script>
<style scoped>.page{max-width:900px;margin:20px auto}.mt{margin-top:16px}.res{line-height:1.7;padding:6px 0;border-bottom:1px dashed #e5e7eb}</style>
