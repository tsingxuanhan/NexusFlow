import { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  Network, Route, BarChart3, Lightbulb, RefreshCw,
} from 'lucide-react'

// ============ Types ============

interface RouterAgent {
  agent_id: string
  name: string
  capabilities: string[]
  load_state: string
  tier: string
  score: number
  [key: string]: unknown
}

interface RoutePlan {
  plan_id: string
  topology: string
  agent_chain: string[]
  estimated_latency: number
  confidence: number
  [key: string]: unknown
}

interface OptimizationStats {
  stats: Record<string, unknown>
  suggestions: string[]
  [key: string]: unknown
}

interface TopologyRecommendation {
  [key: string]: unknown
}

// ============ Constants ============

const TOPOLOGIES = ['star', 'mesh', 'tree', 'ring', 'hybrid'] as const
type TopologyType = typeof TOPOLOGIES[number]

const TIER_COLOR: Record<string, string> = { cloud: '#6366f1', edge: '#0EA5E9', device: '#10B981' }
const COMPLEXITIES = ['trivial', 'simple', 'moderate', 'complex', 'epic'] as const


// ============ SVG Layout ============

interface SvgNode { x: number; y: number; r: number; label: string; color: string; tier: string }
interface SvgEdge { from: number; to: number }

function buildLayout(topology: TopologyType, agents: RouterAgent[], cx: number, cy: number): { nodes: SvgNode[]; edges: SvgEdge[] } {
  const n = agents.length
  if (n === 0) return { nodes: [], edges: [] }

  const getColor = (tier: string) => TIER_COLOR[tier?.toLowerCase()] ?? '#6366f1'
  const getLabel = (name: string) => {
    if (!name) return '?'
    if (name.length <= 8) return name
    return name.slice(0, 7) + '…'
  }

  const nodes: SvgNode[] = agents.map((a, i) => {
    const tier = a.tier?.toLowerCase() ?? 'cloud'
    return {
      x: cx, y: cy, r: i === 0 ? 26 : 18,
      label: getLabel(a.name ?? a.agent_id ?? ''),
      color: getColor(tier),
      tier,
    }
  })

  const edges: SvgEdge[] = []

  switch (topology) {
    case 'star': {
      const radius = Math.min(110, 40 + n * 8)
      nodes.forEach((nd, i) => {
        if (i === 0) { nd.x = cx; nd.y = cy; nd.r = 28 }
        else {
          const angle = ((i - 1) / Math.max(1, n - 1)) * Math.PI * 2 - Math.PI / 2
          nd.x = cx + Math.cos(angle) * radius
          nd.y = cy + Math.sin(angle) * radius
        }
      })
      for (let i = 1; i < n; i++) edges.push({ from: 0, to: i })
      break
    }
    case 'mesh': {
      const radius = Math.min(95, 30 + n * 7)
      nodes.forEach((nd, i) => {
        const angle = (i / n) * Math.PI * 2 - Math.PI / 2
        nd.x = cx + Math.cos(angle) * radius
        nd.y = cy + Math.sin(angle) * radius
        nd.r = 20
      })
      for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) edges.push({ from: i, to: j })
      break
    }
    case 'tree': {
      const lv1 = Math.max(1, Math.ceil(n / 2))
      nodes[0].x = cx; nodes[0].y = 40; nodes[0].r = 26
      nodes.forEach((nd, i) => {
        if (i > 0) {
          if (i <= lv1) { nd.x = cx - 90 + (i - 1) * 55; nd.y = 130; nd.r = 20 }
          else { nd.x = cx - 90 + (i - lv1 - 1) * 55; nd.y = 220; nd.r = 18 }
        }
      })
      for (let i = 1; i <= lv1 && i < n; i++) edges.push({ from: 0, to: i })
      for (let i = lv1 + 1; i < n; i++) edges.push({ from: (i - lv1) <= lv1 ? (i - lv1) : 1, to: i })
      break
    }
    case 'ring': {
      const radius = Math.min(100, 35 + n * 6)
      nodes.forEach((nd, i) => {
        const angle = (i / n) * Math.PI * 2 - Math.PI / 2
        nd.x = cx + Math.cos(angle) * radius
        nd.y = cy + Math.sin(angle) * radius
        nd.r = 20
      })
      for (let i = 0; i < n; i++) edges.push({ from: i, to: (i + 1) % n })
      break
    }
    case 'hybrid': {
      const topCount = Math.max(1, Math.floor(n / 3))
      nodes[0].x = cx; nodes[0].y = 45; nodes[0].r = 26
      nodes.forEach((nd, i) => {
        if (i > 0 && i <= topCount) {
          nd.x = cx - 80 + (i - 1) * 55; nd.y = 125; nd.r = 22
        } else if (i > topCount) {
          const k = i - topCount - 1
          const botCount = n - topCount - 1
          const step = botCount > 1 ? 200 / (botCount - 1) : 0
          nd.x = cx - 100 + k * step; nd.y = 215; nd.r = 18
        }
      })
      for (let i = 1; i <= topCount && i < n; i++) edges.push({ from: 0, to: i })
      for (let i = topCount + 1; i < n; i++) edges.push({ from: (i - topCount) <= topCount ? (i - topCount) : 1, to: i })
      if (topCount >= 2 && n > topCount + 1) edges.push({ from: 1, to: topCount })
      break
    }
  }

  return { nodes, edges }
}

// ============ Component ============

export function TopologyRouter() {
  const [agents, setAgents] = useState<RouterAgent[]>([])
  const [history, setHistory] = useState<RoutePlan[]>([])
  const [optimization, setOptimization] = useState<OptimizationStats | null>(null)
  const [recommendations, setRecommendations] = useState<TopologyRecommendation[]>([])
  const [topologyStats, setTopologyStats] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedTopology, setSelectedTopology] = useState<TopologyType>('star')

  // Route form
  const [routeDesc, setRouteDesc] = useState('')
  const [routeComplexity, setRouteComplexity] = useState<string>('moderate')
  const [routing, setRouting] = useState(false)
  const [routeResult, setRouteResult] = useState<RoutePlan | null>(null)
  const [routeError, setRouteError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [agentsRes, historyRes, optRes, recRes, topoStatsRes] = await Promise.allSettled([
        fetch('/api/router/agents'),
        fetch('/api/router/history?limit=20'),
        fetch('/api/router/optimization'),
        fetch('/api/topology-optimizer/recommendations'),
        fetch('/api/topology-optimizer/stats'),
      ])

      if (agentsRes.status === 'fulfilled' && agentsRes.value.ok) {
        const data = await agentsRes.value.json()
        setAgents(data.agents ?? [])
      }

      if (historyRes.status === 'fulfilled' && historyRes.value.ok) {
        const data = await historyRes.value.json()
        setHistory(data.history ?? [])
      }

      if (optRes.status === 'fulfilled' && optRes.value.ok) {
        const data: OptimizationStats = await optRes.value.json()
        setOptimization(data)
      }

      if (recRes.status === 'fulfilled' && recRes.value.ok) {
        const data = await recRes.value.json()
        const recs = data.recommendations ?? data ?? []
        setRecommendations(Array.isArray(recs) ? recs : [])
      }

      if (topoStatsRes.status === 'fulfilled' && topoStatsRes.value.ok) {
        const data = await topoStatsRes.value.json()
        setTopologyStats(data ?? {})
      }
    } catch (e) {
      setError('无法连接路由器后端')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchData() }, [fetchData])

  const handleRoute = async () => {
    if (!routeDesc.trim()) return
    setRouting(true)
    setRouteError(null)
    setRouteResult(null)
    try {
      const res = await fetch('/api/router/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: routeDesc, complexity: routeComplexity }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: RoutePlan = await res.json()
      setRouteResult(data)
      if (data.topology && (TOPOLOGIES as readonly string[]).includes(data.topology)) {
        setSelectedTopology(data.topology as TopologyType)
      }
    } catch (e) {
      setRouteError(e instanceof Error ? e.message : '路由请求失败')
    } finally {
      setRouting(false)
    }
  }

  // ============ Derived ============

  const { nodes, edges } = buildLayout(selectedTopology, agents, 250, 130)
  const showFallback = !loading && agents.length === 0

  // Success rate from history
  const successRates = TOPOLOGIES.map(topo => {
    const filtered = history.filter(h => (h.topology ?? '').toLowerCase() === topo)
    return { topology: topo, count: filtered.length }
  }).filter(s => s.count > 0)

  const stateColor = (state: string): 'green' | 'orange' | 'red' | 'gray' => {
    const s = state?.toLowerCase() ?? ''
    if (s.includes('online') || s.includes('active') || s.includes('idle')) return 'green'
    if (s.includes('busy') || s.includes('overload') || s.includes('high')) return 'orange'
    if (s.includes('offline') || s.includes('error') || s.includes('down')) return 'red'
    return 'gray'
  }

  const optStats = optimization?.stats ?? topologyStats ?? {}
  const suggestions = optimization?.suggestions ?? []

  // ============ Render ============

  return (
    <div className="space-y-5">
      {/* ===== A. Dynamic Topology SVG ===== */}
      <Card
        title="动态拓扑可视化"
        icon={<Network className="w-4 h-4" />}
        action={
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => void fetchData()} disabled={loading}>
              <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
              {loading ? '刷新中…' : '刷新'}
            </Button>
            {error && <Badge color="red">{error}</Badge>}
          </div>
        }
      >
        <div className="flex justify-center py-4">
          {loading ? (
            <div className="text-gray-400 text-sm py-12">连接中…</div>
          ) : showFallback ? (
            <div className="text-gray-400 text-sm py-12">暂无 Agent 数据</div>
          ) : (
            <svg width="500" height="280" viewBox="0 0 500 280" className="overflow-visible">
              {/* Edges */}
              {edges.map((e, i) => (
                <line key={`edge-${i}`}
                  x1={nodes[e.from]?.x ?? 0} y1={nodes[e.from]?.y ?? 0}
                  x2={nodes[e.to]?.x ?? 0} y2={nodes[e.to]?.y ?? 0}
                  stroke="#E5E7EB" strokeWidth="2" strokeDasharray="4 2"
                />
              ))}
              {/* Animated dots */}
              {edges.map((_e, i) => (
                <circle key={`dot-${i}`} r="3" fill="#6366f1" opacity="0.6">
                  <animateMotion dur={`${2 + (i % 3) * 0.5}s`} repeatCount="indefinite">
                    <mpath xlinkHref={`#topo-path-${i}`} />
                  </animateMotion>
                </circle>
              ))}
              {/* Hidden paths */}
              {edges.map((e, i) => (
                <path key={`path-${i}`} id={`topo-path-${i}`}
                  d={`M${nodes[e.from]?.x ?? 0},${nodes[e.from]?.y ?? 0} L${nodes[e.to]?.x ?? 0},${nodes[e.to]?.y ?? 0}`}
                  fill="none" stroke="none"
                />
              ))}
              {/* Nodes */}
              {nodes.map((nd, i) => (
                <g key={`node-${i}`}>
                  <circle cx={nd.x} cy={nd.y} r={nd.r} fill={nd.color} opacity="0.15" />
                  <circle cx={nd.x} cy={nd.y} r={nd.r - 4} fill={nd.color} />
                  <text x={nd.x} y={nd.y + nd.r + 14} textAnchor="middle" className="text-[10px] fill-gray-500" fontFamily="system-ui">
                    {nd.label}
                  </text>
                  <text x={nd.x} y={nd.y + 3} textAnchor="middle" className="text-[9px] fill-white" fontFamily="system-ui" fontWeight="600">
                    {nd.tier?.[0]?.toUpperCase() ?? 'C'}
                  </text>
                </g>
              ))}
            </svg>
          )}
        </div>

        {/* Topology Switcher */}
        <div className="flex justify-center gap-2 mt-2">
          {TOPOLOGIES.map(t => (
            <button
              key={t}
              onClick={() => setSelectedTopology(t)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                selectedTopology === t ? 'bg-[#6366f1] text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Agent Legend */}
        {agents.length > 0 && (
          <div className="flex flex-wrap gap-2 justify-center mt-3 pt-3 border-t border-gray-100">
            {agents.map(a => {
              const tc = TIER_COLOR[a.tier?.toLowerCase()] ?? '#6366f1'
              return (
                <div key={a.agent_id} className="flex items-center gap-1.5 px-2 py-1 bg-gray-50 rounded-md">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: tc }} />
                  <span className="text-[10px] text-gray-600">{a.name ?? a.agent_id}</span>
                  <Badge color={stateColor(a.load_state)}>{a.load_state ?? 'unknown'}</Badge>
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* ===== B. Route Simulation ===== */}
      <Card title="路由模拟" icon={<Route className="w-4 h-4" />}>
        <div className="space-y-3">
          <textarea
            value={routeDesc}
            onChange={e => setRouteDesc(e.target.value)}
            placeholder="输入任务描述，例如：分析用户上传的 CSV 文件并生成可视化报告"
            rows={2}
            className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg resize-none focus:outline-none focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] text-gray-700"
          />
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] text-gray-400">复杂度:</span>
            {COMPLEXITIES.map(c => (
              <button
                key={c}
                onClick={() => setRouteComplexity(c)}
                className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-all border ${
                  routeComplexity === c
                    ? 'bg-[#6366f1] text-white border-[#6366f1]'
                    : 'bg-white text-gray-500 border-gray-200 hover:border-[#6366f1]/30'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
          <Button size="sm" onClick={() => void handleRoute()} disabled={routing || !routeDesc.trim()} className="w-full">
            {routing ? '路由中…' : '执行路由'}
          </Button>
          {routeError && <div className="text-xs text-red-500 bg-red-50 rounded-md px-3 py-2">{routeError}</div>}
          {routeResult && (
            <div className="rounded-lg border border-indigo-100 bg-indigo-50/40 p-3 space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge color="indigo">{routeResult.topology ?? '—'}</Badge>
                <span className="text-[10px] font-mono text-gray-400">Plan: {routeResult.plan_id ?? '—'}</span>
              </div>
              <div>
                <div className="text-[9px] text-gray-400 mb-1">Agent Chain</div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  {(routeResult.agent_chain ?? []).map((agent, i) => (
                    <div key={i} className="flex items-center gap-1.5">
                      <span className="px-2 py-0.5 bg-white rounded-md text-[10px] font-medium text-gray-600 border border-gray-100">
                        {agent}
                      </span>
                      {i < (routeResult.agent_chain?.length ?? 0) - 1 && (
                        <span className="text-gray-300 text-[10px]">→</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-white rounded-md px-2.5 py-1.5 border border-gray-100">
                  <div className="text-[9px] text-gray-400">预估延迟</div>
                  <div className="text-sm font-semibold text-[#0EA5E9]">{routeResult.estimated_latency ?? '—'}ms</div>
                </div>
                <div className="bg-white rounded-md px-2.5 py-1.5 border border-gray-100">
                  <div className="text-[9px] text-gray-400">置信度</div>
                  <div className="text-sm font-semibold text-[#6366f1]">{(routeResult.confidence ?? 0).toFixed(2)}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* ===== C. History + D. Success Rate (two columns) ===== */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Route History */}
        <Card title="路由决策历史" icon={<Route className="w-4 h-4" />}>
          {loading ? (
            <div className="text-center py-6 text-gray-400 text-sm">连接中…</div>
          ) : history.length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">暂无路由历史</div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {history.map((r, i) => (
                <div key={r.plan_id ?? i} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                  <div className="flex items-center gap-2">
                    <Badge color="green">✓</Badge>
                    <Badge color="indigo">{r.topology ?? '—'}</Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex -space-x-1">
                      {(r.agent_chain ?? []).slice(0, 3).map((ag, j) => (
                        <span key={j} className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-100 border border-white text-[8px] font-medium text-gray-600" title={ag}>
                          {ag?.[0] ?? '?'}
                        </span>
                      ))}
                      {(r.agent_chain?.length ?? 0) > 3 && (
                        <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-100 border border-white text-[8px] font-medium text-gray-400">
                          +{(r.agent_chain?.length ?? 0) - 3}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">{r.estimated_latency ?? '—'}ms</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Success Rate Bar Chart */}
        <Card title="拓扑成功率" icon={<BarChart3 className="w-4 h-4" />}>
          {loading ? (
            <div className="text-center py-6 text-gray-400 text-sm">连接中…</div>
          ) : successRates.length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">暂无统计数据</div>
          ) : (
            <div className="space-y-3">
              {successRates.map(s => {
                // Calculate rate from history: completed routes with this topology / total
                const total = history.length || 1
                const rate = s.count / total
                return (
                  <div key={s.topology} className="flex items-center gap-3">
                    <span className="text-xs text-gray-500 w-12">{s.topology}</span>
                    <div className="flex-1 h-7 bg-gray-100 rounded-md overflow-hidden relative">
                      <div
                        className="h-full rounded-md transition-all flex items-center justify-end pr-2"
                        style={{
                          width: `${Math.max(rate * 100, 5)}%`,
                          background: rate > 0.25 ? 'linear-gradient(90deg, #6366f1, #0EA5E9)' : rate > 0.1 ? 'linear-gradient(90deg, #0EA5E9, #10B981)' : 'linear-gradient(90deg, #F97316, #F59E0B)',
                        }}
                      >
                        <span className="text-[10px] font-semibold text-white">{s.count}</span>
                      </div>
                    </div>
                    <span className="text-[10px] text-gray-400 w-12 text-right">{(rate * 100).toFixed(0)}%</span>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      </div>

      {/* ===== E. Optimization Suggestions + Recommendations ===== */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="优化统计" icon={<BarChart3 className="w-4 h-4" />}>
          {loading ? (
            <div className="text-center py-6 text-gray-400 text-sm">连接中…</div>
          ) : Object.keys(optStats).length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">暂无优化数据</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(optStats).slice(0, 8).map(([key, val]) => (
                <div key={key} className="flex items-center justify-between py-1.5 px-3 bg-gray-50 rounded-lg">
                  <span className="text-xs text-gray-500">{key}</span>
                  <span className="text-xs font-semibold text-gray-700">
                    {typeof val === 'number' ? val.toLocaleString() : typeof val === 'object' ? JSON.stringify(val).slice(0, 30) : String(val)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="优化建议" icon={<Lightbulb className="w-4 h-4" />}>
          {loading ? (
            <div className="text-center py-6 text-gray-400 text-sm">连接中…</div>
          ) : suggestions.length === 0 && recommendations.length === 0 ? (
            <div className="text-center py-6 text-gray-400 text-sm">暂无优化建议</div>
          ) : (
            <div className="space-y-2">
              {suggestions.map((s, i) => (
                <div key={`sug-${i}`} className="flex items-start gap-2 py-1.5 px-3 bg-amber-50/50 rounded-lg border border-amber-100/50">
                  <Lightbulb className="w-3.5 h-3.5 text-[#F97316] flex-shrink-0 mt-0.5" />
                  <span className="text-xs text-gray-600">{s}</span>
                </div>
              ))}
              {recommendations.map((rec, i) => {
                const recText = typeof rec === 'string' ? rec :
                  (rec.description as string) ?? (rec.reason as string) ?? (rec.suggestion as string) ?? JSON.stringify(rec).slice(0, 80)
                const recTitle = typeof rec === 'object' && rec !== null ? (rec.topology as string) ?? (rec.type as string) ?? '' : ''
                return (
                  <div key={`rec-${i}`} className="flex items-start gap-2 py-1.5 px-3 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
                    <Network className="w-3.5 h-3.5 text-[#6366f1] flex-shrink-0 mt-0.5" />
                    <div className="text-xs text-gray-600">
                      {recTitle && <span className="font-medium text-[#6366f1] mr-1">{recTitle}:</span>}
                      {recText}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
