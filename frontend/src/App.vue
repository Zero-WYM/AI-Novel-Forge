<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">AI Novel Forge</div>
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/"><el-icon><DataLine /></el-icon>工作台</el-menu-item>
        <el-menu-item index="/outline"><el-icon><Files /></el-icon>大纲</el-menu-item>
        <el-menu-item index="/chapter"><el-icon><EditPen /></el-icon>章节</el-menu-item>
        <el-menu-item index="/characters"><el-icon><User /></el-icon>角色</el-menu-item>
        <el-menu-item index="/world"><el-icon><Compass /></el-icon>世界观</el-menu-item>
        <el-menu-item index="/rag"><el-icon><Search /></el-icon>RAG 调试</el-menu-item>
      </el-menu>
      <div class="aside-foot">
        <div class="theme-row">
          <span class="theme-label">🌙 主题</span>
          <el-switch
            v-model="isDark"
            :active-icon="MoonIcon"
            :inactive-icon="SunnyIcon"
            size="small"
            inline-prompt
            active-text=""
            inactive-text=""
            @change="onThemeChange"
          />
        </div>
        <el-button text class="set-btn" @click="openSettings">
          <el-icon><Setting /></el-icon><span>模型设置</span>
        </el-button>
      </div>
    </el-aside>
    <el-main :class="isDark ? 'theme-dark-global' : 'theme-light-global'"><router-view /></el-main>
  </el-container>

  <!-- 全局加载弹窗：大模型响应期间显示，调用结束自动消失 -->
  <div v-if="store.loading" class="llm-mask">
    <div class="llm-box">
      <div class="llm-spinner"></div>
      <div class="llm-text">{{ store.loadingText || '大模型正在响应…' }}</div>
    </div>
  </div>

  <!-- 模型设置弹窗 -->
  <el-dialog v-model="showSettings" title="模型设置" width="680px" :close-on-click-modal="false">

    <!-- 使用指南 -->
    <div class="cfg-guide">
      <div class="cfg-guide-title">📖 使用说明</div>
      <ul class="cfg-guide-list">
        <li>填写 API Key 后选择或手动输入模型信息，保存即可切换 LLM 服务商</li>
        <li>
          获取 API Key：
          <a href="https://open.bigmodel.cn/" target="_blank">智谱 AI</a> ·
          <a href="https://platform.deepseek.com/" target="_blank">DeepSeek</a> ·
          <a href="https://platform.openai.com/api-keys" target="_blank">OpenAI</a> ·
          <a href="https://dashscope.aliyun.com/" target="_blank">通义千问</a>
        </li>
        <li>Base URL 与模型名必须匹配同一服务商；不确定时点击下方「常用模型」卡片自动填充</li>
        <li><strong>API Key 留空 = 不修改</strong>，已保存的 Key 不会丢失</li>
      </ul>
    </div>

    <!-- 常用模型预设 -->
    <div class="cfg-presets">
      <div class="cfg-presets-title">⚡ 常用模型（点击自动填充）</div>
      <div class="preset-grid">
        <div
          v-for="p in presets" :key="p.name"
          class="preset-card"
          :class="{ active: cfg.base_url === p.url && cfg.model === p.model }"
          @click="applyPreset(p)"
        >
          <div class="preset-name">{{ p.name }}</div>
          <div class="preset-model">{{ p.model }}</div>
          <div class="preset-url">{{ p.urlShort }}</div>
        </div>
      </div>
    </div>

    <el-divider />

    <el-form label-width="100px" label-position="left" size="large">
      <el-form-item label="API Key">
        <el-input v-model="cfg.api_key" type="password" show-password placeholder="不修改请留空" />
      </el-form-item>
      <el-form-item label="Base URL">
        <el-input v-model="cfg.base_url" placeholder="智谱: https://open.bigmodel.cn/api/paas/v4" />
      </el-form-item>
      <el-form-item label="模型名">
        <el-input v-model="cfg.model" placeholder="glm-4.7-flash / deepseek-chat / gpt-4o" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="showSettings = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="saveSettings">保存</el-button>
    </template>
  </el-dialog>

  <!-- 访问口令登录弹窗（未登录 / 口令失效时强制弹出） -->
  <el-dialog
    v-model="authState.showLogin"
    title="🔐 访问口令"
    width="420px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
  >
    <p class="login-tip">本站需要访问口令才能进入，请输入好友共享的口令。</p>
    <el-input
      v-model="loginPwd"
      type="password"
      show-password
      placeholder="请输入访问口令"
      @keyup.enter="doLogin"
    />
    <template #footer>
      <el-button type="primary" :loading="logging" @click="doLogin">进入</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelStore } from './stores/novel'
import { ElMessage } from 'element-plus'
import { Moon, Sunny as SunnyIcon, Setting } from '@element-plus/icons-vue'
import api from './utils/api'
import { authState, setToken } from './utils/auth'
const MoonIcon = Moon

const route = useRoute()
const store = useNovelStore()

// ========== 全局主题切换 ==========
const THEME_KEY = 'global_theme_dark'
const isDark = ref(true)
function loadGlobalTheme() {
  try {
    const saved = localStorage.getItem(THEME_KEY)
    if (saved !== null) { isDark.value = saved === 'true'; return }
  } catch {}
  isDark.value = window.matchMedia('(prefers-color-scheme: dark)').matches
}
function onThemeChange(val) {
  try { localStorage.setItem(THEME_KEY, String(val)) } catch {}
}
loadGlobalTheme()

// ---- 模型设置弹窗 ----
const showSettings = ref(false)
const saving = ref(false)
const cfg = reactive({ api_key: '', base_url: '', model: '' })

// 常用模型预设（点击自动填充 Base URL + 模型名）
const presets = [
  {
    name: '智谱 AI',
    model: 'glm-4.7-flash',
    url: 'https://open.bigmodel.cn/api/paas/v4',
    urlShort: 'open.bigmodel.cn',
    note: '默认推荐，性价比高',
  },
  {
    name: '智谱 GLM-4-Plus',
    model: 'glm-4-plus',
    url: 'https://open.bigmodel.cn/api/paas/v4',
    urlShort: 'open.bigmodel.cn',
    note: '更强推理能力',
  },
  {
    name: 'DeepSeek',
    model: 'deepseek-chat',
    url: 'https://api.deepseek.com/v1',
    urlShort: 'api.deepseek.com',
    note: '长文本/代码强',
  },
  {
    name: 'DeepSeek V3',
    model: 'deepseek-reasoner',
    url: 'https://api.deepseek.com/v1',
    urlShort: 'api.deepseek.com',
    note: '深度推理',
  },
  {
    name: 'OpenAI GPT-4o',
    model: 'gpt-4o',
    url: 'https://api.openai.com/v1',
    urlShort: 'api.openai.com',
    note: '全能旗舰',
  },
  {
    name: '通义千问',
    model: 'qwen-plus',
    url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    urlShort: 'dashscope.aliyuncs.com',
    note: '阿里云大模型',
  },
]

function applyPreset(p) {
  cfg.base_url = p.url
  cfg.model = p.model
}

onMounted(async () => {
  try {
    const c = await store.loadModelConfig()
    cfg.base_url = c.base_url || ''
    cfg.model = c.model || ''
  } catch { /* 忽略：拦截器已统一提示 */ }
})

async function openSettings() {
  try {
    const c = await store.loadModelConfig()
    cfg.base_url = c.base_url || ''
    cfg.model = c.model || ''
    cfg.api_key = ''   // 留空表示不修改现有 Key
  } catch { /* 忽略 */ }
  showSettings.value = true
}

async function saveSettings() {
  saving.value = true
  try {
    await store.saveModelConfig({
      api_key: cfg.api_key,
      base_url: cfg.base_url,
      model: cfg.model,
    })
    ElMessage.success('模型设置已保存，下次生成即时生效')
    showSettings.value = false
  } catch {
    // 错误已由 api 拦截器统一提示，这里仅避免未处理异常
  } finally {
    saving.value = false
  }
}

// ---- 访问口令登录 ----
const loginPwd = ref('')
const logging = ref(false)
async function doLogin() {
  if (!loginPwd.value) { ElMessage.warning('请输入访问口令'); return }
  logging.value = true
  try {
    const data = await api.login(loginPwd.value)
    setToken(data.token || '')
    authState.showLogin = false
    loginPwd.value = ''
    ElMessage.success('登录成功')
    // 重新加载页面，刷新各视图的初次请求
    setTimeout(() => window.location.reload(), 300)
  } catch {
    // 失败已由拦截器统一提示；清空输入
    loginPwd.value = ''
  } finally {
    logging.value = false
  }
}
</script>

<style>
.layout { height: 100vh; }
.aside { background: #1f2937; color: #fff; display: flex; flex-direction: column; }
.aside-foot { margin-top: auto; padding: 12px; border-top: 1px solid rgba(255,255,255,.08); }
.set-btn { color: #cbd5e1; width: 100%; justify-content: flex-start; gap: 8px; }
.set-btn:hover { color: #fff; }
.brand { font-size: 20px; font-weight: 700; padding: 20px; letter-spacing: 1px; }
.el-menu { border-right: none; background: transparent; }
.el-menu-item { color: #cbd5e1; }
.el-menu-item.is-active { background: #374151; color: #fff; }

/* 大模型加载弹窗 */
.llm-mask {
  position: fixed; inset: 0; background: rgba(15, 23, 42, .55);
  display: flex; align-items: center; justify-content: center; z-index: 9999;
}
.llm-box {
  background: #fff; border-radius: 14px; padding: 30px 40px;
  display: flex; flex-direction: column; align-items: center; gap: 14px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, .25);
}
.llm-spinner {
  width: 46px; height: 46px; border: 4px solid #e5e7eb;
  border-top-color: #409eff; border-radius: 50%;
  animation: llm-spin .9s linear infinite;
}
.llm-text { font-size: 15px; color: #1f2937; font-weight: 500; }
@keyframes llm-spin { to { transform: rotate(360deg); } }

/* 模型设置弹窗 - 使用指南 */
.cfg-guide {
  background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 10px; padding: 16px 20px; margin-bottom: 8px;
}
.cfg-guide-title { font-size: 15px; font-weight: 700; color: #0369a1; margin-bottom: 8px; }
.cfg-guide-list { margin: 0; padding-left: 22px; font-size: 14px; color: #334155; line-height: 2; }
.cfg-guide-list li a { color: #2563eb; text-decoration: none; font-weight: 500; }
.cfg-guide-list li a:hover { text-decoration: underline; }

/* 常用模型预设卡片 */
.cfg-presets { margin-bottom: 8px; }
.cfg-presets-title { font-size: 15px; font-weight: 700; color: #374151; margin-bottom: 12px; }
.preset-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.preset-card {
  border: 2px solid #e5e7eb; border-radius: 10px; padding: 14px 16px;
  cursor: pointer; transition: all .2s; background: #fafafa;
}
.preset-card:hover { border-color: #409eff; background: #eff6ff; box-shadow: 0 4px 12px rgba(64,158,255,.18); transform: translateY(-1px); }
.preset-card.active { border-color: #409eff; background: #e8f4fd; box-shadow: 0 0 0 3px rgba(64,158,255,.2); }
.preset-name { font-size: 15px; font-weight: 700; color: #1f2937; }
.preset-model { font-size: 13.5px; color: #409eff; font-family: 'Courier New', monospace; margin-top: 4px; font-weight: 600; }
.preset-url { font-size: 12.5px; color: #6b7280; margin-top: 4px; }

/* ====== 全局主题（作用于 el-main 内所有页面） ====== */
.theme-dark-global { background: #0f172a; color: #e2e8f0; transition: background .3s, color .3s; }
.theme-light-global { background: #f8fafc; color: #1e293b; transition: background .3s, color .3s; }

/* 侧边栏主题行 */
.theme-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; margin-bottom: 4px; }
.theme-label { color: #cbd5e1; font-size: 13px; }

/* 访问口令登录弹窗 */
.login-tip { font-size: 14px; color: #475569; margin: 0 0 16px; line-height: 1.6; }
</style>
