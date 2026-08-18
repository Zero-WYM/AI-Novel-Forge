// 共享访问口令的全局状态与工具（A 方案：所有人同一口令进入）。
// token 即后端返回的访问口令，存 localStorage 以便刷新后保持登录。
import { reactive } from 'vue'

const TOKEN_KEY = 'anf_access_token'
const stored = localStorage.getItem(TOKEN_KEY) || ''

export const authState = reactive({
  token: stored,
  showLogin: false,
})

export function setToken(t) {
  authState.token = t || ''
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

export function clearToken() {
  setToken('')
}

export function isAuthed() {
  return !!authState.token
}
