// 角色关系网络：Canvas 3D 力导向图引擎
// 由 ChapterView 与 CharactersView 共用，避免重复维护。
import { ref, computed, watch } from 'vue'

export function useForceGraph(store) {
const rawEdges = computed(() => {
  const edges = []
  const chars = store.characters || []
  for (const c of chars) {
    const rels = c.relationships || c.relationship || []
    if (typeof rels === 'string') parseRelString(c.name, rels, edges)
    else if (Array.isArray(rels)) { for (const r of rels) { typeof r === 'string' ? parseRelString(c.name, r, edges) : edges.push({ from: c.name, to: r.target || r.with || '', label: r.relation || r.type || '' }) } }
  }
  return edges
})

function parseRelString(sourceName, str, out) {
  const parts = str.split(/[,，、;；]/)
  for (const p of parts) {
    const m = p.match(/(\S+?)【(.+?)】|(\S+?)（(.+?)）|(\S+?)\((.+?)\)/)
    if (m) { const target = m[1] || m[3] || m[5]; const label = m[2] || m[4] || m[6]; if (target) out.push({ from: sourceName, to: target, label: label.trim() }) }
    else { const t = p.trim(); if (t && t.length < 20) out.push({ from: sourceName, to: '', label: t }) }
  }
}

function classifyRelation(label) {
  const l = (label || '').toLowerCase()
  if (/友|盟|亲|师|徒|父|母|兄|弟|姐|妹|爱|恋|伴|护|忠|义|助|援|伙伴|同门|师兄|师弟|师父|长辈|传人/.test(l)) return 'ally'
  if (/敌|仇|恨|杀|对立|对手|宿敌|死敌|敌人|对抗|追杀|暗杀|陷害|背叛|反目|仇人/.test(l)) return 'enemy'
  return 'neutral'
}

const allCharNames = computed(() => {
  const names = new Set()
  ;(store.characters || []).forEach(c => { if (c.name) names.add(c.name) })
  rawEdges.value.forEach(e => { if (e.from) names.add(e.from); if (e.to) names.add(e.to) })
  return [...names]
})

// ========== 迷你预览图（防重叠） ==========
const miniNodes = computed(() => {
  const names = allCharNames.value
  if (!names.length) return []
  const cx = 100, cy = 70
  // 半径随数量自适应
  const r = Math.max(40, Math.min(50, names.length * 6))
  return names.map((nm, i) => {
    const a = (2 * Math.PI * i) / names.length - Math.PI / 2
    return { name: nm, cx: cx + r * Math.cos(a), cy: cy + r * Math.sin(a), highlight: i < 3 }
  })
})
const miniEdges = computed(() => {
  const nm = new Map(miniNodes.value.forEach(n => [n.name, n]))
  return rawEdges.value.filter(e => e.to && nm.has(e.from) && nm.has(e.to)).map(e => ({
    x1: nm.get(e.from).cx, y1: nm.get(e.from).cy,
    x2: nm.get(e.to).cx, y2: nm.get(e.to).cy,
  }))
})

// ========== 弹窗大图（3D Canvas 力导向） ==========
const showRelDialog = ref(false)
const showHidePanel = ref(false)  // 隐藏面板开关
const centerChar = ref('')
const relCanvas = ref(null)

watch(showRelDialog, (v) => { if (v && !centerChar.value && allCharNames.value.length) centerChar.value = allCharNames.value[0] })

function setCenter(name) { centerChar.value = name; onCenterChange() }
function onCenterChange() { _pinnedNodes.clear(); initForceNodes(); runForceSim() }
function shuffleLayout() { _pinnedNodes.clear(); _hiddenNodes.clear(); initForceNodes(true); runForceSim() }

// ---- 节点隐藏/显示 ----
let _hiddenNodes = new Set()  // 被隐藏的节点名集合

function toggleNodeVisibility(nm) {
  if (_hiddenNodes.has(nm)) { _hiddenNodes.delete(nm) } else { _hiddenNodes.add(nm) }
  // 中心节点不能隐藏
  if (nm === centerChar.value) { _hiddenNodes.delete(nm); return }
  runForceStabilize()
  render3DGraph()
}
function showAllNodes() { _hiddenNodes.clear(); runForceStabilize(); render3DGraph() }
function hideAllNodesExceptCenter() {
  _hiddenNodes.clear()
  for (const n of allCharNames.value) { if (n !== centerChar.value) _hiddenNodes.add(n) }
  runForceStabilize()
  render3DGraph()
}

// ---- Canvas 3D 引擎 ----
let _forceAnimId = null
let _forceNodes = []   // { name, x, y, z, vx, vy, vz, isCenter, isNeighbor, r, pinned }
let _forceEdges = []   // { source, target, label, colorClass, colorHex }
let _canvasW = 920, _canvasH = 580
let _hoverNode = null
let _dragNode = null
let _scale = 1
let _panX = 0, _panY = 0  // 画布平移偏移（像素）
let _isPanning = false, _panStartX = 0, _panStartY = 0
let _isDark = true // 跟随主题
let _pinnedNodes = new Set()  // 手动拖动过、被钉住的节点名集合

/** 初始化节点位置（可随机打散，螺旋布局减少重叠） */
function initForceNodes(randomize = false) {
  const names = allCharNames.value
  if (!names.length) { _forceNodes = []; _forceEdges = []; return }
  const cc = centerChar.value || names[0]
  const neighbors = new Set()
  rawEdges.value.forEach(e => {
    if (e.from === cc && e.to) neighbors.add(e.to)
    if (e.to === cc && e.from) neighbors.add(e.from)
  })
  const cx = _canvasW / 2, cy = _canvasH / 2

  if (randomize) {
    // 完全随机
    _forceNodes = names.map(nm => ({
      name: nm,
      x: 80 + Math.random() * (_canvasW - 160),
      y: 80 + Math.random() * (_canvasH - 160),
      z: (Math.random() - 0.5) * 300,
      vx: 0, vy: 0, vz: 0,
      isCenter: nm === cc,
      isNeighbor: neighbors.has(nm),
      r: nm === cc ? 28 : (neighbors.has(nm) ? 20 : 14),
      pinned: false,
    }))
  } else {
    // 螺旋布局（中心→邻居环→外围环，角度均分防重叠）
    const nbrArr = [...neighbors]
    const others = names.filter(n => n !== cc && !neighbors.has(n))
    const nodes = []
    // 中心
    nodes.push({ name: cc, x: cx, y: cy, z: 0, vx: 0, vy: 0, vz: 0, isCenter: true, isNeighbor: false, r: 28, pinned: false })
    // 邻居环
    const nbrR = Math.max(170, 40 + nbrArr.length * 30)
    nbrArr.forEach((nm, i) => {
      const a = -Math.PI / 2 + (2 * Math.PI * i) / Math.max(nbrArr.length, 1)
      nodes.push({ name: nm, x: cx + nbrR * Math.cos(a), y: cy + nbrR * Math.sin(a), z: (Math.random() - 0.5) * 120, vx: 0, vy: 0, vz: 0, isCenter: false, isNeighbor: true, r: 20, pinned: false })
    })
    // 外围环（更大半径，错开半格）
    const otherR = nbrR + 120
    const offset = nbrArr.length > 0 ? Math.PI / nbrArr.length / 2 : 0
    others.forEach((nm, i) => {
      const a = -Math.PI / 2 + offset + (2 * Math.PI * i) / Math.max(others.length, 1)
      nodes.push({ name: nm, x: cx + otherR * Math.cos(a), y: cy + otherR * Math.sin(a), z: (Math.random() - 0.5) * 180, vx: 0, vy: 0, vz: 0, isCenter: false, isNeighbor: false, r: 14, pinned: false })
    })
    _forceNodes = nodes
  }
  // 边
  const nodeMap = new Map(_forceNodes.map(n => [n.name, n]))
  _forceEdges = rawEdges.value
    .filter(e => e.to && nodeMap.has(e.from) && nodeMap.has(e.to))
    .map(e => ({
      source: nodeMap.get(e.from),
      target: nodeMap.get(e.to),
      label: e.label,
      colorClass: classifyRelation(e.label),
      colorHex: classifyRelation(e.label) === 'ally' ? '#22c55e'
             : classifyRelation(e.label) === 'enemy' ? '#ef4444'
             : '#94a3b8',
    }))
}

/** 运行力导向模拟（迭代 300 帧稳定，pinned 节点不受力） */
function runForceSim(restart = true) {
  if (restart && _forceAnimId) cancelAnimationFrame(_forceAnimId)
  const nodes = _forceNodes
  const edges = _forceEdges
  if (!nodes.length) return
  const cx = _canvasW / 2, cy = _canvasH / 2
  let iter = 0
  const MAX_ITER = 300

  function step() {
    iter++
    // 过滤出可见节点（hidden 不参与任何力计算）
    const visibleNodes = nodes.filter(n => !_hiddenNodes.has(n.name))
    const visibleEdges = edges.filter(e => !_hiddenNodes.has(e.source.name) && !_hiddenNodes.has(e.target.name))

    // ---- 力计算 ----
    // 1) 节点间斥力（库仑）— pinned 节点对别人仍有斥力，但自己不移动
    for (let i = 0; i < visibleNodes.length; i++) {
      for (let j = i + 1; j < visibleNodes.length; j++) {
        const a = nodes[i], b = nodes[j]
        let dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z
        let d2 = dx * dx + dy * dy + dz * dz
        if (d2 < 1) d2 = 1
        const d = Math.sqrt(d2)
        const F = 12000 / d2  // 加大斥力强度（原 8000 → 12000）
        const fx = F * dx / d, fy = F * dy / d, fz = F * dz / d
        // 只对未 pinned 的节点施加速度
        if (!_pinnedNodes.has(a.name)) { a.vx -= fx; a.vy -= fy; a.vz -= fz }
        if (!_pinnedNodes.has(b.name)) { b.vx += fx; b.vy += fy; b.vz += fz }
      }
    }
    // 2) 边弹簧引力
    for (const e of visibleEdges) {
      const s = e.source, t = e.target
      let dx = t.x - s.x, dy = t.y - s.y, dz = t.z - s.z
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1
      const idealLen = s.isCenter || t.isCenter ? 180 : 240
      const F = (d - idealLen) * 0.04
      const ffx = F * dx / d, ffy = F * dy / d, ffz = F * dz / d
      if (!_pinnedNodes.has(s.name)) { s.vx += ffx; s.vy += ffy; s.vz += ffz }
      if (!_pinnedNodes.has(t.name)) { t.vx -= ffx; t.vy -= ffy; t.vz -= ffz }
    }
    // 3) 向中心引力 + z 轴归零（仅未 pinned + 可见）
    for (const n of visibleNodes) {
      if (_pinnedNodes.has(n.name)) continue
      n.vx += (cx - n.x) * 0.006
      n.vy += (cy - n.y) * 0.006
      n.vz -= n.z * 0.01
    }
    // 4) 中心节点强力固定在中心附近（即使 pinned 也微调）
    const centerN = nodes.find(n => n.isCenter)
    if (centerN && !_pinnedNodes.has(centerN.name)) {
      centerN.vx += (cx - centerN.x) * 0.18
      centerN.vy += (cy - centerN.y) * 0.18
      centerN.vz *= 0.5
    }

    // ---- 应用速度 + 阻尼 ----
    for (const n of visibleNodes) {
      if (_pinnedNodes.has(n.name)) continue  // pinned 节点完全不动
      n.vx *= 0.72; n.vy *= 0.72; n.vz *= 0.72  // 加大阻尼（原 0.78 → 0.72），更快稳定
      n.x += n.vx; n.y += n.vy; n.z += n.vz
      // 边界约束
      const margin = 60
      if (n.x < margin) { n.x = margin; n.vx *= -0.5 }
      if (n.x > _canvasW - margin) { n.x = _canvasW - margin; n.vx *= -0.5 }
      if (n.y < margin) { n.y = margin; n.vy *= -0.5 }
      if (n.y > _canvasH - margin) { n.y = _canvasH - margin; n.vy *= -0.5 }
      if (n.z < -250) n.z = -250
      if (n.z > 250) n.z = 250
    }

    render3DGraph()

    if (iter < MAX_ITER && !_dragNode) {
      _forceAnimId = requestAnimationFrame(step)
    } else {
      _forceAnimId = null
    }
  }
  step()
}

// ---- 3D 渲染器 ----
function render3DGraph() {
  const cv = relCanvas.value
  if (!cv) return
  const ctx = cv.getContext('2d')
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  const W = _canvasW, H = _canvasH
  const cx = W / 2, cy = H / 2

  // 清屏（带深色背景）
  ctx.fillStyle = _isDark ? '#0c1220' : '#f1f5f9'
  ctx.fillRect(0, 0, W, H)

  // 绘制微弱的网格背景（增加空间感，固定在屏幕空间）
  ctx.strokeStyle = _isDark ? 'rgba(56,81,120,0.12)' : 'rgba(148,163,184,0.15)'
  ctx.lineWidth = 0.5
  const gridStep = 50
  for (let x = gridStep; x < W; x += gridStep) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke() }
  for (let y = gridStep; y < H; y += gridStep) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke() }

  // 整体缩放+平移：围绕画布中心缩放，再叠加平移偏移
  ctx.save()
  ctx.translate(cx + _panX, cy + _panY)
  ctx.scale(_scale, _scale)
  ctx.translate(-cx, -cy)

  // 深度排序：先画远的（z 小），后画近的（z 大），排除隐藏节点
  const visibleNodes = _forceNodes.filter(n => !_hiddenNodes.has(n.name))
  const sorted = [...visibleNodes].sort((a, b) => a.z - b.z)

  // ---- 绘制边（连线）—— 只画两端都可见的边 ----
  for (const e of _forceEdges) {
    if (_hiddenNodes.has(e.source.name) || _hiddenNodes.has(e.target.name)) continue
    const s = e.source, t = e.target
    const avgZ = (s.z + t.z) / 2
    const depth = 1 - (avgZ + 250) / 500  // 0(远) ~ 1(近)
    const alpha = 0.25 + depth * 0.55
    const lw = 1 + depth * 2.5

    // 解析颜色 + 加透明度
    const hex = e.colorHex
    const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16)

    ctx.beginPath()
    ctx.moveTo(s.x, s.y)
    ctx.lineTo(t.x, t.y)
    ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`
    ctx.lineWidth = lw
    ctx.stroke()

    // 边标签（中点偏移，带背景框）
    const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2
    const perpX = -(t.y - s.y), perpY = (t.x - s.x)
    const plen = Math.hypot(perpX, perpY) || 1
    const labelOff = 14
    const lx = mx + (perpX / plen) * labelOff, ly = my + (perpY / plen) * labelOff

    ctx.font = `${_isDark ? '700' : '700'} 15px system-ui, -apple-system, sans-serif`
    const tw = ctx.measureText(e.label).width
    ctx.fillStyle = _isDark ? `rgba(12,18,32,${0.75 + depth * 0.2})` : `rgba(255,255,255,${0.75 + depth * 0.2})`
    const pad = 5
    roundRect(ctx, lx - tw / 2 - pad, ly - 10 - pad, tw + pad * 2, 20 + pad * 2, 4)
    ctx.fill()
    ctx.fillStyle = _isDark ? `rgba(${200+Math.floor(depth*55)},${210+Math.floor(depth*45)},230,${0.85 + depth*0.15})` : `rgba(15,23,42,${0.8 + depth*0.2})`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(e.label, lx, ly)
  }

  // ---- 绘制节点（3D 球体）----
  for (const n of sorted) {
    const depth = 1 - (n.z + 250) / 500
    const sr = n.r * (0.6 + depth * 0.55)  // 近大远小（缩放由外层 transform 处理）
    const isHover = _hoverNode === n

    // 外辉光（仅中心/邻居/hover）
    if (n.isCenter || n.isNeighbor || isHover) {
      const glowR = sr * (1.8 + (isHover ? 0.6 : 0))
      const glow = ctx.createRadialGradient(n.x, n.y, sr * 0.5, n.x, n.y, glowR)
      if (n.isCenter) {
        glow.addColorStop(0, _isDark ? 'rgba(59,130,246,0.35)' : 'rgba(37,99,235,0.25)')
        glow.addColorStop(1, 'transparent')
      } else if (n.isNeighbor) {
        glow.addColorStop(0, _isDark ? 'rgba(96,165,250,0.25)' : 'rgba(59,130,246,0.15)')
        glow.addColorStop(1, 'transparent')
      } else {
        glow.addColorStop(0, _isDark ? 'rgba(148,163,184,0.2)' : 'rgba(100,116,139,0.15)')
        glow.addColorStop(1, 'transparent')
      }
      ctx.beginPath()
      ctx.arc(n.x, n.y, glowR, 0, Math.PI * 2)
      ctx.fillStyle = glow
      ctx.fill()
    }

    // 球体本体（径向渐变模拟 3D）
    const ballGrad = ctx.createRadialGradient(
      n.x - sr * 0.3, n.y - sr * 0.35, sr * 0.08,  // 高光点（左上）
      n.x, n.y, sr
    )
    if (n.isCenter) {
      ballGrad.addColorStop(0, '#93c5fd')     // 亮面
      ballGrad.addColorStop(0.5, '#3b82f6')    // 本色
      ballGrad.addColorStop(1, '#1e3a8a')      // 暗面
    } else if (n.isNeighbor) {
      ballGrad.addColorStop(0, '#bfdbfe')
      ballGrad.addColorStop(0.5, '#60a5fa')
      ballGrad.addColorStop(1, '#1e40af')
    } else {
      ballGrad.addColorStop(0, _isDark ? '#94a3b8' : '#e2e8f0')
      ballGrad.addColorStop(0.5, _isDark ? '#475569' : '#94a3b8')
      ballGrad.addColorStop(1, _isDark ? '#1e293b' : '#475569')
    }

    ctx.beginPath()
    ctx.arc(n.x, n.y, sr, 0, Math.PI * 2)
    ctx.fillStyle = ballGrad
    ctx.fill()

    // hover 高亮环
    if (isHover) {
      ctx.strokeStyle = _isDark ? '#60a5fa' : '#3b82f6'
      ctx.lineWidth = 2.5
      ctx.stroke()
    }

    // pinned 标记（小钉子图标）
    if (_pinnedNodes.has(n.name)) {
      const pinX = n.x + sr * 0.7, pinY = n.y - sr * 0.7
      const pinR = Math.max(5, sr * 0.28)
      ctx.beginPath()
      ctx.arc(pinX, pinY, pinR, 0, Math.PI * 2)
      ctx.fillStyle = _isDark ? 'rgba(251,191,36,0.9)' : 'rgba(217,119,6,0.9)'
      ctx.fill()
      ctx.strokeStyle = _isDark ? '#fbbf24' : '#d97706'
      ctx.lineWidth = 1.5
      ctx.stroke()
      // 钉子内部小白点
      ctx.beginPath()
      ctx.arc(pinX, pinY, pinR * 0.4, 0, Math.PI * 2)
      ctx.fillStyle = _isDark ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.6)'
      ctx.fill()
    }

    // 投影（底部椭圆）
    const shadowY = n.y + sr * 0.9 + depth * 10
    const shadowRx = sr * 0.85
    const shadowRy = sr * 0.2
    const shadow = ctx.createRadialGradient(n.x, shadowY, 0, n.x, shadowY, shadowRx)
    shadow.addColorStop(0, `rgba(0,0,0,${0.18 + depth * 0.12})`)
    shadow.addColorStop(1, 'transparent')
    ctx.beginPath()
    ctx.ellipse(n.x, shadowY, shadowRx, shadowRy, 0, 0, Math.PI * 2)
    ctx.fillStyle = shadow
    ctx.fill()

    // 名字标签
    const ty = n.y + sr + (n.isCenter ? 20 : (n.isNeighbor ? 17 : 14))
    ctx.font = `${n.isCenter ? '700' : '600'} ${n.isCenter ? 15 : 12.5}px system-ui, -apple-system, sans-serif`
    const txt = n.name
    const tw2 = ctx.measureText(txt).width
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'

    // 文字背景
    ctx.fillStyle = _isDark ? `rgba(15,23,42,${0.72 + depth * 0.2})` : `rgba(255,255,255,${0.72 + depth * 0.2})`
    roundRect(ctx, n.x - tw2 / 2 - 5, ty - 2, tw2 + 10, 18 + 4, 5)
    ctx.fill()
    ctx.strokeStyle = _isDark ? `rgba(71,85,105,${0.4 + depth * 0.3})` : `rgba(203,213,225,${0.5 + depth * 0.3})`
    ctx.lineWidth = 1
    ctx.stroke()

    // 文字
    ctx.fillStyle = _isDark
      ? (n.isCenter ? '#f8fafc' : `rgba(${220 + Math.floor(depth*35)},${225 + Math.floor(depth*30)},245,${0.9 + depth * 0.1})`)
      : (n.isCenter ? '#0f172a' : `rgba(${15 + Math.floor((1-depth)*30)},${23 + Math.floor((1-depth)*30)},42,${0.88 + depth * 0.12})`)
    ctx.fillText(txt, n.x, ty + 3)
  }
  ctx.restore()
}

/** 圆角矩形辅助 */
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.lineTo(x + w - r, y)
  ctx.quadraticCurveTo(x + w, y, x + w, y + r)
  ctx.lineTo(x + w, y + h - r)
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
  ctx.lineTo(x + r, y + h)
  ctx.quadraticCurveTo(x, y + h, x, y + h - r)
  ctx.lineTo(x, y + r)
  ctx.quadraticCurveTo(x, y, x + r, y)
  ctx.closePath()
}

// ---- 鼠标交互 ----
function getMousePos(evt) {
  const cv = relCanvas.value
  if (!cv) return { x: 0, y: 0 }
  const rect = cv.getBoundingClientRect()
  return { x: evt.clientX - rect.left, y: evt.clientY - rect.top }
}

function findNodeAt(x, y) {
  // 从前向后找（先找近的/大的），排除隐藏节点
  const cx = _canvasW / 2, cy = _canvasH / 2
  const sorted = [..._forceNodes].filter(n => !_hiddenNodes.has(n.name)).sort((a, b) => b.z - a.z)
  for (const n of sorted) {
    const depth = 1 - (n.z + 250) / 500
    const sr = n.r * (0.6 + depth * 0.55) * _scale
    // 世界坐标 → 屏幕坐标（含缩放+平移）
    const screenX = cx + (n.x - cx) * _scale + _panX
    const screenY = cy + (n.y - cy) * _scale + _panY
    const dx = x - screenX, dy = y - screenY
    if (dx * dx + dy * dy <= (sr + 6) * (sr + 6)) return n
  }
  return null
}

function onCanvasMouseDown(evt) {
  const pos = getMousePos(evt)
  const n = findNodeAt(pos.x, pos.y)
  if (n) {
    _dragNode = n
    n.vx = 0; n.vy = 0; n.vz = 0
    relCanvas.value.style.cursor = 'grabbing'
  } else {
    // 空白区域 → 开始平移画布
    _isPanning = true
    _panStartX = pos.x - _panX
    _panStartY = pos.y - _panY
    relCanvas.value.style.cursor = 'grabbing'
  }
}

function onCanvasMouseMove(evt) {
  const pos = getMousePos(evt)
  if (_dragNode) {
    const cx = _canvasW / 2, cy = _canvasH / 2
    // 屏幕坐标 → 世界坐标（抵消缩放+平移变换）
    _dragNode.x = cx + (pos.x - cx - _panX) / _scale
    _dragNode.y = cy + (pos.y - cy - _panY) / _scale
    render3DGraph()
  } else if (_isPanning) {
    _panX = pos.x - _panStartX
    _panY = pos.y - _panStartY
    render3DGraph()
  } else {
    const n = findNodeAt(pos.x, pos.y)
    if (n !== _hoverNode) {
      _hoverNode = n
      relCanvas.value.style.cursor = n ? 'pointer' : 'grab'
      render3DGraph()
    }
  }
}

function onCanvasMouseUp(evt) {
  if (_dragNode) {
    // 标记为钉住——松手后不再被力模拟推动
    _pinnedNodes.add(_dragNode.name)
    _dragNode.vx = 0; _dragNode.vy = 0; _dragNode.vz = 0
    _dragNode = null
    relCanvas.value.style.cursor = _hoverNode ? 'pointer' : 'grab'
    // 只对未 pinned 的节点做几帧微调稳定（不重启完整 300 帧模拟）
    runForceStabilize()
  } else if (_isPanning) {
    _isPanning = false
    relCanvas.value.style.cursor = _hoverNode ? 'pointer' : 'grab'
  }
}

/** 轻量稳定（只跑 30 帧，让未 pinned 节点适应当前布局） */
function runForceStabilize() {
  if (_forceAnimId) cancelAnimationFrame(_forceAnimId)
  const nodes = _forceNodes
  const edges = _forceEdges
  if (!nodes.length) return
  let iter = 0
  const MAX_ITER = 30
  const cx = _canvasW / 2, cy = _canvasH / 2

  function step() {
    iter++
    const visibleNodes = nodes.filter(n => !_hiddenNodes.has(n.name))
    const visibleEdges = edges.filter(e => !_hiddenNodes.has(e.source.name) && !_hiddenNodes.has(e.target.name))
    // 简化版力计算（只做斥力+弹簧，不做中心引力）
    for (let i = 0; i < visibleNodes.length; i++) {
      for (let j = i + 1; j < visibleNodes.length; j++) {
        const a = visibleNodes[i], b = visibleNodes[j]
        if (_pinnedNodes.has(a.name) && _pinnedNodes.has(b.name)) continue
        let dx = b.x - a.x, dy = b.y - a.y
        let d2 = dx * dx + dy * dy
        if (d2 < 1) d2 = 1
        const d = Math.sqrt(d2)
        const F = 6000 / d2
        const fx = F * dx / d, fy = F * dy / d
        if (!_pinnedNodes.has(a.name)) { a.vx -= fx; a.vy -= fy }
        if (!_pinnedNodes.has(b.name)) { b.vx += fx; b.vy += fy }
      }
    }
    for (const e of visibleEdges) {
      const s = e.source, t = e.target
      if (_pinnedNodes.has(s.name) && _pinnedNodes.has(t.name)) continue
      let dx = t.x - s.x, dy = t.y - s.y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const idealLen = 200
      const F = (d - idealLen) * 0.02
      if (!_pinnedNodes.has(s.name)) { s.vx += F * dx / d; s.vy += F * dy / d }
      if (!_pinnedNodes.has(t.name)) { t.vx -= F * dx / d; t.vy -= F * dy / d }
    }
    for (const n of visibleNodes) {
      if (_pinnedNodes.has(n.name)) continue
      n.vx *= 0.6; n.vy *= 0.6
      n.x += n.vx; n.y += n.vy
      const margin = 60
      if (n.x < margin) n.x = margin
      if (n.x > _canvasW - margin) n.x = _canvasW - margin
      if (n.y < margin) n.y = margin
      if (n.y > _canvasH - margin) n.y = _canvasH - margin
    }
    render3DGraph()
    if (iter < MAX_ITER) {
      _forceAnimId = requestAnimationFrame(step)
    } else {
      _forceAnimId = null
    }
  }
  step()
}

function onCanvasClick(evt) {
  const pos = getMousePos(evt)
  const n = findNodeAt(pos.x, pos.y)
  if (n && !wasDragging) setCenter(n.name)
}
function onCanvasDblClick(evt) {
  const pos = getMousePos(evt)
  const n = findNodeAt(pos.x, pos.y)
  if (n && _pinnedNodes.has(n.name)) {
    // 双击 pinned 节点 → 取消钉住，让它重新参与力模拟
    _pinnedNodes.delete(n.name)
    runForceStabilize()
    render3DGraph()
  }
}
let wasDragging = false
let _moveCount = 0
function onCanvasMD(evt) { wasDragging = false; _moveCount = 0; onCanvasMouseDown(evt) }
function onCanvasMM(evt) { if (_dragNode) { _moveCount++; if (_moveCount > 3) wasDragging = true }; onCanvasMouseMove(evt) }

function onCanvasWheel(evt) {
  evt.preventDefault()
  const delta = evt.deltaY > 0 ? 0.92 : 1.08
  _scale = Math.max(0.4, Math.min(2.5, _scale * delta))
  render3DGraph()
}

// ---- 生命周期 ----
function startForceGraph() {
  _isDark = !!document.querySelector('.theme-dark') || localStorage.getItem('global_theme_dark') !== 'false'
  _panX = 0; _panY = 0; _isPanning = false
  // 画布自适应：取 canvas-wrap 容器的实际尺寸
  const cv = relCanvas.value
  if (cv) {
    cv.style.cursor = 'grab'
    const wrap = cv.parentElement
    if (wrap) {
      _canvasW = Math.max(600, wrap.clientWidth - 4)
      _canvasH = Math.max(400, window.innerHeight - 280)
      cv.width = _canvasW
      cv.height = _canvasH
      cv.style.width = _canvasW + 'px'
      cv.style.height = _canvasH + 'px'
    }
  }
  initForceNodes()
  runForceSim()
  // 绑定事件
  if (cv) {
    cv.addEventListener('mousedown', onCanvasMD)
    window.addEventListener('mousemove', onCanvasMM)
    window.addEventListener('mouseup', onCanvasMouseUp)
    cv.addEventListener('click', onCanvasClick)
    cv.addEventListener('dblclick', onCanvasDblClick)
    cv.addEventListener('wheel', onCanvasWheel, { passive: false })
  }
}

function stopForceGraph() {
  if (_forceAnimId) { cancelAnimationFrame(_forceAnimId); _forceAnimId = null }
  const cv = relCanvas.value
  if (cv) {
    cv.removeEventListener('mousedown', onCanvasMD)
    window.removeEventListener('mousemove', onCanvasMM)
    window.removeEventListener('mouseup', onCanvasMouseUp)
    cv.removeEventListener('click', onCanvasClick)
    cv.removeEventListener('dblclick', onCanvasDblClick)
    cv.removeEventListener('wheel', onCanvasWheel)
  }
  _hoverNode = null
  _pinnedNodes.clear()
  _dragNode = null
}

  return {
    showRelDialog, showHidePanel, centerChar, relCanvas,
    allCharNames, rawEdges, miniNodes, miniEdges, _hiddenNodes,
    setCenter, onCenterChange, shuffleLayout,
    toggleNodeVisibility, showAllNodes, hideAllNodesExceptCenter,
    startForceGraph, stopForceGraph,
    onCanvasMD, onCanvasMM, onCanvasMouseUp, onCanvasClick, onCanvasDblClick, onCanvasWheel,
  }
}
