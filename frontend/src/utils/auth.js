// B 方案：独立账号 + 数据隔离。
// 管理 JWT（token）与当前用户（user: {id, username}），存 localStorage 以便刷新后保持登录。
import { reactive } from 'vue'

const TOKEN_KEY = 'anf_access_token'
const USER_KEY = 'anf_user'

const stored = localStorage.getItem(TOKEN_KEY) || ''

let storedUser = null
try {
  storedUser = JSON.parse(localStorage.getItem(USER_KEY) || 'null')
} catch {
  storedUser = null
}

export const authState = reactive({
  token: stored,
  user: storedUser,
  showLogin: false,   // 控制登录 / 注册弹窗
  mode: 'register',   // 'register' | 'login'，默认开放注册
})

export function setToken(t) {
  authState.token = t || ''
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

export function setUser(u) {
  authState.user = u || null
  if (u) localStorage.setItem(USER_KEY, JSON.stringify(u))
  else localStorage.removeItem(USER_KEY)
}

// 登录成功后一并写入 token + 用户
export function setSession(token, user) {
  setToken(token)
  setUser(user)
}

export function clearToken() {
  setToken('')
  setUser(null)
}

export function isAuthed() {
  return !!authState.token
}
