import { useState, useEffect, useCallback } from 'react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  Server, Monitor, Smartphone, ArrowRightLeft, Zap,
  Activity, BarChart3, Gauge, TrendingUp,
} from 'lucide-react'

// ============ Types ============

interface TierResource {
  name: string
  tier: string
  gpu_type: string
  gpu_count: number
  memory_gb: number
  latency_ms: number
  cost_per_hour: number
  gpu_util: number
  mem_util: number
  active_tasks: number
  state: string
}

interface ScheduleDecision {
  tier: string
  resource: string
  confidence: number
  reason: string
  latency_ms: number
  cost: number
}

interface MigrateResult {
  success: boolean
  task_id: string
  from: string
  to: string
  [key: string]: unknown
}

interface MigrationRecord {
  task_id?: string
  task?: string
  from?: string
  from_tier?: string
  to?: string
  to_tier?: string
  reason?: string
  status?: string
  success?: boolean
  time?: string
  timestamp?: string
  [key: string]: unknown
}

interface SchedulerStats {
  total_decisions?: number
  avg_confidence?: number
  tier_distribution?: Record<string, number>
  tier_dist?: Record<string, number>
  [key: string]: unknown
}

// ============ Constants ============

const TIER_ORDER = ['cloud', 'edge', 'device']
const TIER_DISPLAY: Record<string, string> = { cloud: 'Cloud', edge: 'Edge', device: 'Device' }
const TIER_COLOR: Record<string, string> = { cloud: '#6366f1', edge: '#0EA5E9', device: '#10B981' }

const tierIcons: Record<string, ReactNode> = {
  cloud: <Server className="w-5 h-5" />,
  edge: <Monitor className="w-5 h-5" />,
  device: <Smartphone className="w-5 h-5" />,
}

// ============ Component ============

export function EdgeCloudScheduler() {
  const [resources, setResources] = useState<TierResource[]>([])
  const [policies, setPolicies] = useState<string[]>([])
  const [activePolicy, setActivePolicy] = useState<string>('')
  const [stats, setStats] = useState<SchedulerStats | null>(null)
  const [migrationHistory, setMigrationHistory] = useState<MigrationRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Schedule form
  const [taskDesc, setTaskDesc] = useState('')
  const [scheduling, setScheduling] = useState(false)
  const [scheduleResult, setScheduleResult] = useState<ScheduleDecision | null>(null)
  const [scheduleError, setScheduleError] = useState<string | null>(null)

  // Migration form
  const [migrateTaskId, setMigrateTaskId] = useState('')
  const [migrateFrom, setMigrateFrom] = useState('edge')
  const [migrateTo, setMigrateTo] = useState('cloud')
  const [migrateReason, setMigrateReason] = useState('')
  const [migrating, setMigrating] = useState(false)
  const [migrateResult, setMigrateResult] = useState<MigrateResult | null>(null)
  const [migrateError, setMigrateError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [tiersRes, statsRes, policiesRes] = await Promise.allSettled([
        fetch('/api/scheduler/tiers'),
        fetch('/api/scheduler/stats'),
        fetch('/api/scheduler/policies'),
      ])

      if (tiersRes.status === 'fulfilled' && tiersRes.value.ok) {
        const data = await tiersRes.value.json()
        setResources(data.resources ?? [])
      }

      if (statsRes.status === 'fulfilled' && statsRes.value.ok) {
        const data: SchedulerStats = await statsRes.value.json()
        setStats(data)
        const hist = (data.migrations as MigrationRecord[]) ??
                     (data.migration_history as MigrationRecord[]) ??
                     []
        setMigrationHistory(Array.isArray(hist) ? hist : [])
      }

      if (policiesRes.status === 'fulfilled' && policiesRes.value.ok) {
        const data = await policiesRes.value.json()
        const pols = data.policies ?? data ?? []
        setPolicies(Array.isArray(pols) ? pols : ['balanced'])
        setActivePolicy(prev => prev || (Array.isArray(pols) && pols.length > 0 ? pols[0] : 'balanced'))
      }
    } catch {
      setError('无法连接调度器后端')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void fetchData() }, [fetchData])

  const handleSchedule = async () => {
    if (!taskDesc.trim()) return
    setScheduling(true)
    setScheduleError(null)
    setScheduleResult(null)
    try {
      const res = await fetch('/api/scheduler/schedule', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: taskDesc }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setScheduleResult(data.decision ?? data)
    } catch (e) {
      setScheduleError(e instanceof Error ? e.message : '调度请求失败')
    } finally {
      setScheduling(false)
    }
  }

  const handleMigrate = async () => {
    if (!migrateTaskId.trim()) return
    setMigrating(true)
    setMigrateError(null)
    setMigrateResult(null)
    try {
      const res = await fetch('/api/scheduler/migrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_id: migrateTaskId, from_tier: migrateFrom, to_tier: migrateTo, reason: migrateReason || 'manual' }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: MigrateResult = await res.json()
      setMigrateResult(data)
      void fetchData()
    } catch (e) {
      setMigrateError(e instanceof Error ? e.message : '迁移请求失败')
    } finally {
      setMigrating(false)
    }
  }

  // ============ Derived ============

  const tierGroups = TIER_ORDER.map(tier => ({
    tier,
    items: resources.filter(r => r.tier?.toLowerCase() === tier),
  }))

  const tierDist = stats?.tier_distribution ?? stats?.tier_dist ?? {}
  const avgConfidence = typeof stats?.avg_confidence === 'number' ? stats.avg_confidence : 0
  const totalDecisions = typeof stats?.total_decisions === 'number' ? stats.total_decisions : 0

  const stateColor = (state: string): 'green' | 'orange' | 'red' | 'gray' => {
    const s = state?.toLowerCase() ?? ''
    if (s.includes('online') || s.includes('active') || s.includes('idle')) return 'green'
    if (s.includes('busy') || s.includes('overload')) return 'orange'
    if (s.includes('offline') || s.includes('error') || s.includes('down')) return 'red'
    return 'gray'
  }

  const stateDot = (state: string): string => {
    const s = state?.toLowerCase() ?? ''
    if (s.includes('online') || s.includes('active') || s.includes('idle')) return '#10B981'
    if (s.includes('busy') || s.includes('overload')) return '#F97316'
    if (s.includes('offline') || s.includes('error') || s.includes('down')) return '#EF4444'
    return '#9CA3AF'
  }

  // ============ Render ============

  return (
    <div className="space-y-5">
      {/* ===== A. Three-Tier Topology ===== */}
      <Card
        title="三层资源拓扑"
        icon={<Activity className="w-4 h-4" />}
        action={
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => void fetchData()} disabled={loading}>
              {loading ? '刷新中…' : '刷新'}
            </Button>
            {error && <Badge color="red">{error}</Badge>}
          </div>
        }
      >
        {loading ? (
          <div className="text-center py-8 text-gray-400 text-sm">连接中…</div>
        ) : tierGroups.every(g => g.items.length === 0) ? (
          <div className="text-center py-8 text-gray-400 text-sm">暂无资源数据</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {tierGroups.map(({ tier, items }) => {
              const color = TIER_COLOR[tier] ?? '#6366f1'
              const totalTasks = items.reduce((s, r) => s + (r.active_tasks ?? 0), 0)
              const avgGpu = items.length > 0 ? items.reduce((s, r) => s + (r.gpu_util ?? 0), 0) / items.length : 0
              const onlineCount = items.filter(r => (r.state?.toLowerCase() ?? '').includes('online')).length
              return (
                <div key={tier}>
                  <div className="p-4 rounded-xl border-2 border-dashed border-gray-200 bg-gray-50/50">
                    <div className="flex items-center gap-2 mb-3">
                      <span style={{ color }}>{tierIcons[tier]}</span>
                      <span className="text-sm font-semibold" style={{ color }}>{TIER_DISPLAY[tier] ?? tier}</span>
                      <Badge color="gray">{items.length} nodes</Badge>
                    </div>
                    <div className="space-y-2">
                      {items.length === 0 ? (
                        <div className="text-center text-xs text-gray-300 py-2">无节点</div>
                      ) : items.map(r => (
                        <div key={`${tier}-${r.name}`} className="p-2.5 bg-white rounded-lg border border-gray-100">
                          <div className="flex items-center justify-between mb-1.5">
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: stateDot(r.state) }} />
                              <span className="text-xs font-medium text-gray-700">{r.name}</span>
                            </div>
                            <Badge color={stateColor(r.state)}>{r.state ?? 'unknown'}</Badge>
                          </div>
                          <div className="flex items-center gap-3 mb-1">
                            <div className="flex-1">
                              <div className="text-[9px] text-gray-400 mb-0.5">GPU</div>
                              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div className="h-full rounded-full" style={{ width: `${r.gpu_util ?? 0}%`, backgroundColor: (r.gpu_util ?? 0) > 80 ? '#F97316' : (r.gpu_util ?? 0) > 60 ? '#0EA5E9' : '#10B981' }} />
                              </div>
                            </div>
                            <div className="flex-1">
                              <div className="text-[9px] text-gray-400 mb-0.5">MEM</div>
                              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div className="h-full rounded-full" style={{ width: `${r.mem_util ?? 0}%`, backgroundColor: (r.mem_util ?? 0) > 80 ? '#F97316' : (r.mem_util ?? 0) > 60 ? '#0EA5E9' : '#10B981' }} />
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center justify-between text-[10px] text-gray-400">
                            <span>{r.gpu_type} ×{r.gpu_count}</span>
                            <span>{r.active_tasks} tasks</span>
                            <span>{r.latency_ms}ms</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 pt-3 border-t border-gray-200 flex justify-between text-xs text-gray-500">
                      <span>在线 {onlineCount}/{items.length}</span>
                      <span>平均GPU {avgGpu.toFixed(0)}%</span>
                      <span>{totalTasks} 任务</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
        <div className="flex items-center justify-center gap-2 mt-4 text-gray-300">
          <ArrowRightLeft className="w-4 h-4" />
          <span className="text-xs">自动跨层迁移</span>
        </div>
      </Card>

      {/* ===== B. Schedule + C. Migrate (two columns) ===== */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Schedule Simulation */}
        <Card title="调度模拟" icon={<Zap className="w-4 h-4" />}>
          <div className="space-y-3">
            <textarea
              value={taskDesc}
              onChange={e => setTaskDesc(e.target.value)}
              placeholder="输入任务描述，例如：高吞吐量 GPU 推理任务"
              rows={2}
              className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg resize-none focus:outline-none focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] text-gray-700"
            />
            <Button size="sm" onClick={() => void handleSchedule()} disabled={scheduling || !taskDesc.trim()} className="w-full">
              {scheduling ? '调度中…' : '执行调度'}
            </Button>
            {scheduleError && <div className="text-xs text-red-500 bg-red-50 rounded-md px-3 py-2">{scheduleError}</div>}
            {scheduleResult && (
              <div className="rounded-lg border border-indigo-100 bg-indigo-50/40 p-3 space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge color="indigo">{scheduleResult.tier ?? '—'}</Badge>
                  <span className="text-xs font-semibold text-gray-700">{scheduleResult.resource ?? '—'}</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-white rounded-md px-2.5 py-1.5 border border-gray-100">
                    <div className="text-[9px] text-gray-400">置信度</div>
                    <div className="text-sm font-semibold text-[#6366f1]">{(scheduleResult.confidence ?? 0).toFixed(2)}</div>
                  </div>
                  <div className="bg-white rounded-md px-2.5 py-1.5 border border-gray-100">
                    <div className="text-[9px] text-gray-400">延迟</div>
                    <div className="text-sm font-semibold text-[#0EA5E9]">{scheduleResult.latency_ms ?? '—'}ms</div>
                  </div>
                  <div className="bg-white rounded-md px-2.5 py-1.5 border border-gray-100">
                    <div className="text-[9px] text-gray-400">成本/时</div>
                    <div className="text-sm font-semibold text-[#F97316]">${scheduleResult.cost ?? '—'}</div>
                  </div>
                </div>
                {scheduleResult.reason && (
                  <div className="text-[10px] text-gray-500 bg-white rounded-md px-2.5 py-1.5 border border-gray-100">{scheduleResult.reason}</div>
                )}
              </div>
            )}
          </div>
        </Card>

        {/* Manual Migration */}
        <Card title="手动迁移" icon={<ArrowRightLeft className="w-4 h-4" />}>
          <div className="space-y-3">
            <input
              value={migrateTaskId}
              onChange={e => setMigrateTaskId(e.target.value)}
              placeholder="任务 ID，如 T-1001"
              className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] text-gray-700"
            />
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[9px] text-gray-400 mb-0.5 block">From</label>
                <select
                  value={migrateFrom}
                  onChange={e => setMigrateFrom(e.target.value)}
                  className="w-full text-xs px-2 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-[#6366f1] text-gray-700"
                >
                  <option value="cloud">Cloud</option>
                  <option value="edge">Edge</option>
                  <option value="device">Device</option>
                </select>
              </div>
              <div>
                <label className="text-[9px] text-gray-400 mb-0.5 block">To</label>
                <select
                  value={migrateTo}
                  onChange={e => setMigrateTo(e.target.value)}
                  className="w-full text-xs px-2 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-[#6366f1] text-gray-700"
                >
                  <option value="cloud">Cloud</option>
                  <option value="edge">Edge</option>
                  <option value="device">Device</option>
                </select>
              </div>
            </div>
            <input
              value={migrateReason}
              onChange={e => setMigrateReason(e.target.value)}
              placeholder="迁移原因（可选）"
              className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:border-[#6366f1] focus:ring-1 focus:ring-[#6366f1] text-gray-700"
            />
            <Button size="sm" variant="danger" onClick={() => void handleMigrate()} disabled={migrating || !migrateTaskId.trim()} className="w-full">
              {migrating ? '迁移中…' : '执行迁移'}
            </Button>
            {migrateError && <div className="text-xs text-red-500 bg-red-50 rounded-md px-3 py-2">{migrateError}</div>}
            {migrateResult && (
              <div className={`rounded-lg border p-3 ${migrateResult.success ? 'border-emerald-100 bg-emerald-50/40' : 'border-red-100 bg-red-50/40'}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Badge color={migrateResult.success ? 'green' : 'red'}>{migrateResult.success ? '成功' : '失败'}</Badge>
                  <span className="text-xs font-mono text-gray-600">{migrateResult.task_id}</span>
                </div>
                <div className="text-xs text-gray-500 flex items-center gap-1.5">
                  <span>{migrateResult.from}</span>
                  <ArrowRightLeft className="w-3 h-3 text-[#6366f1]" />
                  <span>{migrateResult.to}</span>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* ===== D. Policy + E. Stats (two columns) ===== */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="调度策略" icon={<Gauge className="w-4 h-4" />}>
          {policies.length === 0 && loading ? (
            <div className="text-center py-6 text-gray-400 text-sm">连接中…</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2">
                {policies.map(p => (
                  <button
                    key={p}
                    onClick={() => setActivePolicy(p)}
                    className={`p-3 rounded-lg text-xs font-medium text-left transition-all border ${
                      activePolicy === p
                        ? 'bg-[#6366f1] text-white border-[#6366f1] shadow-md shadow-indigo-200'
                        : 'bg-white text-gray-600 border-gray-100 hover:border-[#6366f1]/30'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-3">
                当前策略: <span className="text-[#6366f1] font-medium">{activePolicy || '—'}</span>
              </p>
            </>
          )}
        </Card>

        <Card title="调度统计" icon={<BarChart3 className="w-4 h-4" />}>
          {stats === null && loading ? (
            <div className="text-center py-6 text-gray-400 text-sm">连接中…</div>
          ) : stats === null ? (
            <div className="text-center py-6 text-gray-400 text-sm">暂无统计数据</div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-[10px] text-gray-400 mb-0.5">总调度次数</div>
                  <div className="text-2xl font-bold text-gray-800">{totalDecisions}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-[10px] text-gray-400 mb-0.5">平均置信度</div>
                  <div className="text-2xl font-bold text-[#6366f1]">{avgConfidence.toFixed(2)}</div>
                </div>
              </div>
              {Object.keys(tierDist).length > 0 && (
                <div className="space-y-1.5">
                  <div className="text-[10px] text-gray-400">层级分布</div>
                  {Object.entries(tierDist).map(([tier, count]) => {
                    const total = Object.values(tierDist).reduce((s, v) => s + (v as number), 0) || 1
                    const pct = ((count as number) / total) * 100
                    return (
                      <div key={tier} className="flex items-center gap-2">
                        <span className="text-[10px] text-gray-500 w-12">{tier}</span>
                        <div className="flex-1 h-5 bg-gray-100 rounded-md overflow-hidden">
                          <div
                            className="h-full rounded-md flex items-center justify-end pr-2"
                            style={{ width: `${pct}%`, backgroundColor: TIER_COLOR[tier?.toLowerCase()] ?? '#6366f1' }}
                          >
                            <span className="text-[9px] font-semibold text-white">{String(count)}</span>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      {/* ===== F. Migration History ===== */}
      <Card title="迁移历史" icon={<TrendingUp className="w-4 h-4" />}>
        {loading ? (
          <div className="text-center py-4 text-gray-400 text-sm">连接中…</div>
        ) : migrationHistory.length === 0 ? (
          <div className="text-center py-4 text-gray-400 text-sm">暂无迁移记录</div>
        ) : (
          <div className="space-y-2">
            {migrationHistory.map((m, i) => {
              const taskId = m.task_id ?? m.task ?? '—'
              const from = m.from ?? m.from_tier ?? '—'
              const to = m.to ?? m.to_tier ?? '—'
              const success = m.success ?? (m.status?.toLowerCase() !== 'failed' && m.status?.toLowerCase() !== 'error')
              return (
                <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                  <div className="flex items-center gap-2">
                    <Badge color={success ? 'green' : 'red'}>{success ? '✓' : '✗'}</Badge>
                    <span className="text-xs font-mono text-gray-500">{taskId}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className="text-gray-500">{from}</span>
                    <ArrowRightLeft className="w-3 h-3 text-[#6366f1]" />
                    <span className="text-gray-500">{to}</span>
                    {m.reason && <span className="text-gray-300 ml-1">({m.reason})</span>}
                    {m.time && <span className="text-gray-300 ml-1">{m.time}</span>}
                    {m.timestamp && <span className="text-gray-300 ml-1">{m.timestamp}</span>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Card>
    </div>
  )
}
