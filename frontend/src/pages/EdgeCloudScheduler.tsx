import React, { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { apiScheduler, api } from '@/api/client'
import { Loader, Server, Activity, AlertTriangle, BarChart3, Gauge, Cpu, HardDrive, Wifi } from 'lucide-react'

interface FaultType { value: string; label: string; icon: React.ReactNode; color: string; description: string; }

const FAULT_TYPES: FaultType[] = [
  { value: 'crash', label: '立即崩溃', icon: <AlertTriangle className="w-3.5 h-3.5" />, color: '#EF4444', description: '节点立即停止工作' },
  { value: 'hang', label: '挂起无响应', icon: <Loader className="w-3.5 h-3.5" />, color: '#F59E0B', description: '节点停止响应但保持在线' },
  { value: 'slow_death', label: '渐进式退化', icon: <Gauge className="w-3.5 h-3.5" />, color: '#F97316', description: '性能逐步下降直至不可用' },
]

export function EdgeCloudScheduler() {
  const [data, setData] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [tiers, setTiers] = useState<any>(null)
  const [monitor, setMonitor] = useState<any>(null)
  const [agents, setAgents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedFault, setSelectedFault] = useState('crash')
  const [faultConfig, setFaultConfig] = useState<any>({})
  const [injecting, setInjecting] = useState(false)
  const [injectResult, setInjectResult] = useState<any>(null)
  const [resourceType, setResourceType] = useState('memory')
  const [threshold, setThreshold] = useState(95)

  const fetchAll = useCallback(async () => {
    try {
      const [s, st, t, m, a] = await Promise.all([
        apiScheduler.getStatus(),
        apiScheduler.getStats(),
        apiScheduler.getTiers(),
        apiScheduler.getResourceMonitor(),
        api.getAgents()
      ])
      setData(s)
      setStats(st)
      setTiers(t)
      setMonitor(m)
      setAgents(a.agents || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll(); const iv = setInterval(fetchAll, 10000); return () => clearInterval(iv) }, [fetchAll])

  const handleInject = async () => {
    setInjecting(true)
    setInjectResult(null)
    try {
      const config = {
        type: selectedFault === 'resource_exhaust' ? 'resource_exhaust' : 'agent_fault',
        fault_type: selectedFault,
        resource_type: resourceType,
        threshold_pct: threshold,
        ...faultConfig
      }
      const res = await apiScheduler.injectAnomaly(config)
      setInjectResult(res)
    } catch (e: any) {
      setInjectResult({ success: false, message: e.message || '注入失败' })
    } finally {
      setInjecting(false)
    }
  }

  const getNodeColor = (status: string) => {
    if (status === 'online' || status === 'active') return '#10B981'
    if (status === 'warning' || status === 'overload') return '#F97316'
    if (status === 'offline' || status === 'error' || status === 'down') return '#EF4444'
    return '#9CA3AF'
  }

  const getTierLabel = (tier: string) => {
    const labels: Record<string, string> = { endpoint: '端侧', edge: '边缘', cloud: '云端' }
    return labels[tier] || tier
  }

  if (loading) return <div className="flex items-center justify-center py-16"><Loader className="w-6 h-6 text-[#6366f1] animate-spin" /></div>

  const nodes = data?.nodes || {}
  const nodeEntries = Object.entries(nodes)

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-bold text-gray-800">端边云调度</h2>

      {/* Status Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card title="调度策略">
          <Badge color="indigo">{data?.strategy || stats?.strategy || 'adaptive'}</Badge>
        </Card>
        <Card title="队列任务">
          <p className="text-3xl font-bold text-[#6366f1]">{data?.queue_length ?? 0}</p>
        </Card>
        <Card title="已完成调度">
          <p className="text-3xl font-bold text-[#10B981]">{data?.completed ?? 0}</p>
        </Card>
      </div>

      {/* Three-Tier Resource Topology */}
      <Card title="三层资源拓扑" icon={<Server className="w-4 h-4" />}>
        <div className="space-y-4">
          {/* Tier Visualization */}
          <div className="grid grid-cols-3 gap-4">
            {['endpoint', 'edge', 'cloud'].map(tier => {
              const tierNodes = nodeEntries.filter(([, v]: [string, any]) => v?.tier === tier || v?.layer === tier)
              return (
                <div key={tier} className="p-3 rounded-lg border border-gray-100">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: tier === 'endpoint' ? '#10B981' : tier === 'edge' ? '#0EA5E9' : '#6366f1' }}></div>
                    <span className="text-xs font-semibold text-gray-700">{getTierLabel(tier)}</span>
                    <Badge color="gray">{tierNodes.length}</Badge>
                  </div>
                  <div className="space-y-1.5">
                    {tierNodes.length > 0 ? tierNodes.map(([k, v]: [string, any]) => (
                      <div key={k} className="flex items-center justify-between p-1.5 rounded bg-gray-50">
                        <span className="text-xs text-gray-600 truncate">{k}</span>
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getNodeColor(v.status) }}></div>
                      </div>
                    )) : (
                      <p className="text-xs text-gray-400 text-center py-2">无节点</p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Tier Stats */}
          {tiers?.tiers && (
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(tiers.tiers).map(([tier, info]: [string, any]) => (
                <div key={tier} className="p-2 rounded-lg bg-gray-50 border border-gray-100">
                  <p className="text-xs font-medium text-[#6366f1]">{getTierLabel(tier)}</p>
                  <p className="text-lg font-bold text-gray-800">{info?.nodes || 0} <span className="text-xs text-gray-400 font-normal">节点</span></p>
                  {info?.capacity && <p className="text-xs text-gray-500">容量: {info.capacity}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Scheduling Statistics */}
      <Card title="调度统计" icon={<BarChart3 className="w-4 h-4" />}>
        <div className="space-y-3">
          {stats ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg border border-gray-100">
                  <p className="text-xs text-gray-500 mb-1">总调度次数</p>
                  <p className="text-2xl font-bold text-[#6366f1]">{stats?.total_scheduled ?? 0}</p>
                </div>
                <div className="p-3 rounded-lg border border-gray-100">
                  <p className="text-xs text-gray-500 mb-1">调度策略</p>
                  <p className="text-sm font-semibold text-[#6366f1]">{stats?.strategy || 'adaptive'}</p>
                </div>
              </div>
              {stats?.simulation && (
                <div className="p-3 rounded-lg bg-indigo-50/50 border border-indigo-100/50">
                  <p className="text-xs font-semibold text-[#6366f1] mb-2">调度模拟</p>
                  <pre className="text-xs text-gray-600 overflow-x-auto">{JSON.stringify(stats.simulation, null, 2)}</pre>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-6 text-sm text-gray-400">暂无统计数据</div>
          )}
        </div>
      </Card>

      {/* Resource Monitoring */}
      <Card title="资源监控" icon={<Gauge className="w-4 h-4" />}>
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-3 rounded-lg border border-gray-100">
              <div className="flex items-center gap-1.5 mb-1">
                <Cpu className="w-3.5 h-3.5 text-[#6366f1]" />
                <span className="text-xs text-gray-500">CPU</span>
              </div>
              <p className="text-xl font-bold text-gray-800">{monitor?.cpu ?? 0}<span className="text-xs text-gray-400 ml-0.5">%</span></p>
              <div className="mt-1.5 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                <div className="h-full bg-[#6366f1] rounded-full transition-all" style={{ width: `${monitor?.cpu ?? 0}%` }}></div>
              </div>
            </div>
            <div className="p-3 rounded-lg border border-gray-100">
              <div className="flex items-center gap-1.5 mb-1">
                <HardDrive className="w-3.5 h-3.5 text-[#0EA5E9]" />
                <span className="text-xs text-gray-500">内存</span>
              </div>
              <p className="text-xl font-bold text-gray-800">{monitor?.memory ?? 0}<span className="text-xs text-gray-400 ml-0.5">%</span></p>
              <div className="mt-1.5 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                <div className="h-full bg-[#0EA5E9] rounded-full transition-all" style={{ width: `${monitor?.memory ?? 0}%` }}></div>
              </div>
            </div>
            <div className="p-3 rounded-lg border border-gray-100">
              <div className="flex items-center gap-1.5 mb-1">
                <HardDrive className="w-3.5 h-3.5 text-[#10B981]" />
                <span className="text-xs text-gray-500">磁盘</span>
              </div>
              <p className="text-xl font-bold text-gray-800">{monitor?.disk ?? 0}<span className="text-xs text-gray-400 ml-0.5">%</span></p>
              <div className="mt-1.5 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                <div className="h-full bg-[#10B981] rounded-full transition-all" style={{ width: `${monitor?.disk ?? 0}%` }}></div>
              </div>
            </div>
            <div className="p-3 rounded-lg border border-gray-100">
              <div className="flex items-center gap-1.5 mb-1">
                <Cpu className="w-3.5 h-3.5 text-[#F59E0B]" />
                <span className="text-xs text-gray-500">GPU</span>
              </div>
              <p className="text-xl font-bold text-gray-800">{monitor?.gpu ?? 0}<span className="text-xs text-gray-400 ml-0.5">%</span></p>
              <div className="mt-1.5 bg-gray-100 rounded-full h-1.5 overflow-hidden">
                <div className="h-full bg-[#F59E0B] rounded-full transition-all" style={{ width: `${monitor?.gpu ?? 0}%` }}></div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 rounded-lg border border-gray-100">
              <p className="text-xs text-gray-500 mb-1">计算延迟</p>
              <p className="text-xl font-bold text-[#6366f1]">{monitor?.latency ?? 0}<span className="text-xs text-gray-400 ml-1">ms</span></p>
            </div>
            <div className="p-3 rounded-lg border border-gray-100">
              <p className="text-xs text-gray-500 mb-1">预估延迟</p>
              <p className="text-xl font-bold text-[#0EA5E9]">{monitor?.estimated_latency ?? 0}<span className="text-xs text-gray-400 ml-1">ms</span></p>
            </div>
            <div className="p-3 rounded-lg border border-gray-100">
              <div className="flex items-center gap-1.5 mb-1">
                <Wifi className="w-3.5 h-3.5 text-[#10B981]" />
                <span className="text-xs text-gray-500">网络带宽</span>
              </div>
              <p className="text-xl font-bold text-[#10B981]">{monitor?.bandwidth ?? 0}<span className="text-xs text-gray-400 ml-1">Mbps</span></p>
            </div>
          </div>
        </div>
      </Card>

      {/* Node Status */}
      <Card title="节点状态" icon={<Server className="w-4 h-4" />}
        action={<Badge color="indigo">{nodeEntries.length} 节点</Badge>}>
        <div className="space-y-2">
          {nodeEntries.length > 0 ? nodeEntries.map(([k, v]: [string, any]) => (
            <div key={k} className="flex items-center justify-between p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getNodeColor(v.status) }}></div>
                <div>
                  <span className="text-xs font-medium text-gray-700">{k}</span>
                  {v.tier && <span className="text-xs text-gray-400 ml-2">({getTierLabel(v.tier || v.layer)})</span>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {v.failure_mode && <Badge color="orange">{v.failure_mode}</Badge>}
                <Badge color={v.status === 'online' || v.status === 'active' ? 'green' : v.status === 'warning' ? 'yellow' : 'gray'}>
                  {v.status}
                </Badge>
              </div>
            </div>
          )) : (
            <div className="text-center py-6 text-xs text-gray-400">暂无节点信息</div>
          )}
        </div>
      </Card>

      {/* Degradation Strategy */}
      <Card title="降级策略" icon={<AlertTriangle className="w-4 h-4" />}>
        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-indigo-50/50 border border-indigo-100/50">
            <p className="text-xs text-gray-600">
              <span className="font-medium text-[#6366f1]">渐进式退化：</span>
              当节点资源不足时，系统会自动执行降级策略，从非关键任务开始逐步释放资源，
              确保核心任务继续运行。支持资源调度验证和降级策略测试。
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="p-2 rounded-lg border border-gray-100 text-center">
              <p className="text-xs text-gray-500">降级级别</p>
              <p className="text-sm font-semibold text-[#6366f1]">3 级</p>
            </div>
            <div className="p-2 rounded-lg border border-gray-100 text-center">
              <p className="text-xs text-gray-500">触发次数</p>
              <p className="text-sm font-semibold text-[#F59E0B]">{data?.degradation_count ?? 0}</p>
            </div>
            <div className="p-2 rounded-lg border border-gray-100 text-center">
              <p className="text-xs text-gray-500">恢复次数</p>
              <p className="text-sm font-semibold text-[#10B981]">{data?.recovery_count ?? 0}</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Anomaly Injection */}
      <Card title="异常注入" icon={<AlertTriangle className="w-4 h-4" />}
        action={injectResult && (
          <div className={`flex items-center gap-1 text-xs ${injectResult.success ? 'text-[#10B981]' : 'text-red-500'}`}>
            {injectResult.success ? '✓ 成功' : '✗ 失败'}
          </div>
        )}>
        <div className="space-y-4">
          <p className="text-xs text-gray-500">模拟资源耗尽场景，验证资源调度和降级策略</p>

          {/* Fault Type Selection */}
          <div>
            <label className="text-xs text-gray-500 block mb-2">故障类型</label>
            <div className="grid grid-cols-3 gap-2">
              {FAULT_TYPES.map(f => (
                <button key={f.value} onClick={() => { setSelectedFault(f.value); setFaultConfig({}) }}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-left text-xs transition-all border ${
                    selectedFault === f.value ? 'shadow-sm' : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                  }`}
                  style={selectedFault === f.value ? { borderColor: f.color, backgroundColor: `${f.color}10` } : {}}>
                  <span style={{ color: f.color }}>{f.icon}</span>
                  <span className="text-gray-700">{f.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Resource Exhaust Configuration */}
          <div>
            <label className="text-xs text-gray-500 block mb-2">资源类型</label>
            <div className="flex flex-wrap gap-2">
              {['memory', 'cpu', 'disk', 'gpu', 'network'].map(t => (
                <button key={t} onClick={() => setResourceType(t)}
                  className={`px-2.5 py-1 text-xs rounded-lg border transition-colors ${
                    resourceType === t ? 'border-[#6366f1] bg-[#6366f1]/5 text-[#6366f1]' : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}>
                  {{ memory: '内存', cpu: 'CPU', disk: '磁盘 I/O', gpu: 'GPU 显存', network: '网络带宽' }[t]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-500 block mb-2">耗尽阈值: {threshold}%</label>
            <input type="range" min={70} max={100} step={1} value={threshold}
              onChange={e => setThreshold(Number(e.target.value))}
              className="w-full h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-[#6366f1]" />
          </div>

          <Button onClick={handleInject} disabled={injecting} variant="danger" className="w-full justify-center">
            {injecting ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5 mr-1" />}
            注入异常
          </Button>
        </div>
      </Card>
    </div>
  )
}
