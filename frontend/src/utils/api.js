import axios from 'axios'
import { ElMessage } from 'element-plus'
import { authState, clearToken } from './auth'
const http = axios.create({ baseURL: '/api', timeout: 120000 })

// 请求拦截：已登录则自动在请求头携带 JWT
http.interceptors.request.use((config) => {
  if (authState.token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${authState.token}`
  }
  return config
})

// L4：统一响应拦截器，避免每个按钮重复写 catch { ElMessage.error(...) }。
// 非 2xx 时自动弹错（优先展示后端 detail 文案），并继续 reject 让调用方仍能按需处理。
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response && error.response.status
    const data = error.response && error.response.data
    const detail = data && (data.detail || data.message)

    // 401：未登录 / 令牌失效 / 登录失败
    if (status === 401) {
      clearToken()
      const url = (error.config && error.config.url) || ''
      if (url.includes('/auth/login') || url.includes('/auth/register')) {
        // 登录 / 注册接口本身失败：保留弹窗并提示具体原因（如「用户名或密码错误」「用户名已被占用」）
        ElMessage.error(typeof detail === 'string' ? detail : '账号或密码错误')
        return Promise.reject(error)
      }
      // 业务接口未授权：清空登录态并弹出登录框
      authState.showLogin = true
      ElMessage.error('登录已过期，请重新登录')
      return Promise.reject(error)
    }

    let msg = detail || error.message || '请求失败'
    // 429 / 503：智谱服务拥堵（点太快或模型繁忙），统一给友好提示，不暴露原始报错
    if (status === 429 || status === 503) {
      msg = '⏳ API 服务拥堵，请稍后重试（您点得太快或智谱模型当前繁忙，稍等片刻再试即可）'
    }
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(error)
  }
)
export default {
  // B 方案：账号体系
  register: (username, password) =>
    http.post('/auth/register', { username, password }).then(r => r.data),
  login: (username, password) =>
    http.post('/auth/login', { username, password }).then(r => r.data),
  me: () => http.get('/auth/me').then(r => r.data),
  createNovel: (data) => http.post('/novel/create', data).then(r => r.data),
  listNovels: () => http.get('/novel/list').then(r => r.data),
  getNovel: (id) => http.get(`/novel/detail?novel_id=${id}`).then(r => r.data),
  genOutline: (data) => http.post('/novel/generate-outline', data).then(r => r.data),
  getOutline: (id) => http.get(`/novel/outline?novel_id=${id}`).then(r => r.data),
  // 一键成书是重活（WorldBuilder→两遍式大纲→CharacterDesigner 串行 4 次 LLM），给足 300s
  bootstrap: (id) => http.post('/novel/bootstrap', { novel_id: id }, { timeout: 300000 }).then(r => r.data),
  genChapter: (data) => http.post('/novel/generate-chapter', data).then(r => r.data),
  generateWorld: (id) => http.post('/novel/generate-world', { novel_id: id }).then(r => r.data),
  getWorld: (id) => http.get(`/novel/world?novel_id=${id}`).then(r => r.data),
  updateWorld: (id, data) => http.put(`/novel/world?novel_id=${id}`, data).then(r => r.data),
  generateCharacters: (id) => http.post('/novel/generate-characters', { novel_id: id }).then(r => r.data),
  reviewChapter: (data) => http.post('/novel/review-chapter', data).then(r => r.data),
  updateChapter: (novel_id, chapter_no, data) => http.put(`/novel/${novel_id}/chapter/${chapter_no}`, data).then(r => r.data),
  getCharacters: (id) => http.get(`/novel/characters?novel_id=${id}`).then(r => r.data),
  updateCharacters: (id, chars) => http.put(`/novel/characters?novel_id=${id}`, chars).then(r => r.data),
  getMemory: (id) => http.get(`/novel/memory?novel_id=${id}`).then(r => r.data),
  getChapters: (id) => http.get(`/novel/${id}/chapters`).then(r => r.data),
  getChapter: (id, chNo) => http.get(`/novel/${id}/chapter/${chNo}`).then(r => r.data),
  ragIngest: (data) => http.post('/rag/rag-ingest', data).then(r => r.data),
  ragQuery: (data) => http.post('/rag/rag-query', data).then(r => r.data),
  // 模型设置（前端「模型设置」面板）
  getModelConfig: () => http.get('/config/model').then(r => r.data),
  saveModelConfig: (data) => http.put('/config/model', data).then(r => r.data),
}
