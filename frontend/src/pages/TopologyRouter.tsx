import { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { apiTopology } from '@/api/client'
import { Loader, GitBranch, Route, Shuffle, AlertTriangle, BarChart3, Layers, Zap } from 'lucide-react'

export function TopologyRouter() {
  const [stats, setStats] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [agents, setAgents] = useState<any[]>([])
  const [optimization, setOptimization] = useState<any>(null)
  const [routeInput, setRouteInput] = useState('')
  const [routeResult, setRouteResult] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [routing, setRouting] = useState(false)
  const [injecting, setInjecting] = useState(false)
  const [injectResult, setInjectResult] = useState<any>(null)
  const [targetTopology, setTargetTopology] = useState('mesh')
  const [disruptTiming, setDisruptTiming] = useState('immediate')
  const [anomalyType, setAnomalyType] = useState('topology_disrupt')

  const fetchAll = useCallback(async () => {
    try {
      const [s, h, a, o] = await Promise.all([
        apiTopology.getStats(),
        apiTopology.getRouteHistory(),
        apiTopology.getAgents(),
        apiTopology.getOptimization()
      ])
      setStats(s)
      setHistory(h.history || [])
      setAgents(a.agents || [])
      setOptimization(o)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll(); const iv = setInterval(fetchAll, 10000); return () => clearInterval(iv) }, [fetchAll])

  const handleSimulateRoute = async () => {
    if (!routeInput.trim() || routing) return
    setRouting(true)
    try {
      const res = await apiTopology.simulateRoute(routeInput)
      setRouteResult(res)
    } catch (e: any) {
      setRouteResult({ error: e.message || '路由模拟失败' })
    } finally {
      setRouting(false)
    }
  }

  const handleInjectAnomaly = async () => {
    if (injecting) return
    setInjecting(true)
    setInjectResult(null)
    try {
      let config: any = { type: anomalyType }
      if (anomalyType === 'topology_disrupt') {
        config.target_topology = targetTopology
        config.disrupt_timing = disruptTiming
      } else if (anomalyType === 'data_corrupt') {
        config.severity = 'partial'
      } else if (anomalyType === 'node_fail') {
        config.failure_mode = 'crash'
      }
      const res = await apiTopology.injectAnomaly(config)
      setInjectResult(res)
    } catch (e: any) {
      setInjectResult({ success: false, message: e.message || '注入失败' })
    } finally {
      setInjecting(false)
    }
  }

  const getTopologyColor = (topology: string) => {
    const colors: Record<string, string> = {
      mesh: 'indigo', tree: 'green', ring: 'sky', star: 'orange', hybrid: 'yellow'
    }
    return colors[topology] || 'gray'
  }

  const getTopologyIcon = (topology: string) => {
    const icons: Record<string, string> = {
      mesh: '🕸️', tree: '🌳', ring: '⭕', star: '⭐', hybrid: '🔀'
    }
    return icons[topology] || '📊'
  }

  if (loading) return <div className="flex items-center justify-center py-16"><Loader className="w-6 h-6 text-[#6366f1] animate-spin" /></div>

  const currentTopology = stats?.topology || 'mesh'
  const recommendations = stats?.recommendations || []
  const successRates = optimization?.success_rates || []
  const optStats = optimization?.stats || {}

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-bold text-gray-800">拓扑路由</h2>

      {/* Status Overview */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card title="当前拓扑">
          <div className="flex items-center gap-2">
            <span className="text-lg">{getTopologyIcon(currentTopology)}</span>
            <Badge color={getTopologyColor(currentTopology)}>{currentTopology}</Badge>
          </div>
        </Card>
        <Card title="路由决策次数">
          <p className="text-3xl font-bold text-[#6366f1]">{stats?.decisions ?? 0}</p>
        </Card>
      </div>

      {/* Dynamic Topology Visualization */}
      <Card title="动态拓扑可视化" icon={<GitBranch className="w-4 h-4" />}>
        <div className="space-y-4">
          {/* Topology Types */}
          <div className="flex flex-wrap gap-2">
            {['mesh', 'tree', 'ring', 'star', 'hybrid'].map(t => (
              <div key={t} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
                t === currentTopology ? 'border-[#6366f1] bg-[#6366f1]/5 text-[#6366f1]' : 'border-gray-200 text-gray-500'
              }`}>
                <span>{getTopologyIcon(t)}</span>
                <span className="capitalize">{t}</span>
              </div>
            ))}
          </div>

          {/* Agent Network Visualization */}
          <div className="p-4 rounded-lg bg-slate-50 border border-gray-100 min-h-[120px]">
            {agents.length > 0 ? (
              <div className="flex flex-wrap gap-3 justify-center">
                {agents.map((agent: any, i: number) => (
                  <div key={agent.id || i} className="relative">
                    <div className={`flex flex-col items-center p-2.5 rounded-lg border transition-colors ${
                      agent.status === 'online' ? 'bg-white border-[#10B981]/30' : 'bg-gray-50 border-gray-200'
                    }`}>
                      <span className="text-lg">{agent.icon || '🤖'}</span>
                      <span className="text-[10px] text-gray-600 mt-1 text-center max-w-[60px] truncate">{agent.name || agent.id}</span>
                      <Badge color={agent.status === 'online' ? 'green' : 'gray'}>
                        {agent.load_state || agent.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 text-center py-6">暂无拓扑节点</p>
            )}
          </div>

          {/* Layer Separation */}
          <div className="p-3 rounded-lg bg-indigo-50/50 border border-indigo-100/50">
            <div className="flex items-center gap-2 mb-2">
              <Layers className="w-3.5 h-3.5 text-[#6366f1]" />
              <span className="text-xs font-semibold text-[#6366f1]">层级分离</span>
            </div>
            <p className="text-xs text-gray-600">
              高层策略 + 底层验证，不同抽象层并行分析。系统支持跨层级的路由决策优化。
            </p>
          </div>
        </div>
      </Card>

      {/* Route Decision History */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="路由决策历史" icon={<Route className="w-4 h-4" />}>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {history.length > 0 ? history.map((h: any, i: number) => (
              <div key={i} className="p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                <div className="flex items-center justify-between mb-1">
                  <Badge color={getTopologyColor(h.topology || currentTopology)}>{h.topology || currentTopology}</Badge>
                  <span className="text-[10px] text-gray-400">
                    {h.time ? new Date(h.time).toLocaleTimeString() : `#${h.decision_id || i + 1}`}
                  </span>
                </div>
                <p className="text-xs text-gray-600">{h.task || h.description || h.reason || '路由决策'}</p>
                {h.confidence && (
                  <p className="text-xs text-[#6366f1] mt-1">置信度: {(h.confidence * 100).toFixed(0)}%</p>
                )}
              </div>
            )) : (
              <div className="text-center py-6 text-xs text-gray-400">暂无决策历史</div>
            )}
          </div>
        </Card>

        {/* Route Simulation */}
        <Card title="路由模拟" icon={<Shuffle className="w-4 h-4" />}>
          <div className="space-y-3">
            <textarea
              value={routeInput}
              onChange={e => setRouteInput(e.target.value)}
              placeholder="输入任务描述，例如：分析用户上传的 CSV 数据并生成报告..."
              className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg h-20 resize-none focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30"
            />
            <Button onClick={handleSimulateRoute} disabled={routing || !routeInput.trim()} className="w-full justify-center">
              {routing ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Route className="w-3.5 h-3.5 mr-1" />}
              执行路由
            </Button>

            {routeResult && (
              <div className="space-y-2">
                {routeResult.error ? (
                  <div className="p-3 rounded-lg bg-red-50 border border-red-200">
                    <p className="text-xs text-red-600">{routeResult.error}</p>
                  </div>
                ) : (
                  <div className="p-3 rounded-lg bg-indigo-50/50 border border-indigo-100/50">
                    <p className="text-xs font-semibold text-[#6366f1] mb-2">路由结果</p>
                    {routeResult.plan && (
                      <div className="space-y-1.5">
                        {routeResult.plan.steps?.map((step: any, i: number) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="text-[#6366f1] font-semibold">Step {i + 1}</span>
                            <span className="text-gray-600">{step.agent || step.description || JSON.stringify(step).slice(0, 60)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    {routeResult.topology && (
                      <p className="text-xs text-gray-500 mt-2">
                        推荐拓扑: <Badge color={getTopologyColor(routeResult.topology)}>{routeResult.topology}</Badge>
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Topology Success Rate */}
      <Card title="拓扑成功率" icon={<BarChart3 className="w-4 h-4" />}>
        <div className="space-y-3">
          {successRates.length > 0 ? (
            <div className="space-y-3">
              {successRates.map((sr: any, i: number) => (
                <div key={i} className="p-3 rounded-lg border border-gray-100">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span>{getTopologyIcon(sr.topology)}</span>
                      <span className="text-xs font-semibold text-gray-700 capitalize">{sr.topology}</span>
                    </div>
                    <span className="text-xs text-gray-500">{sr.count || 0} 次</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                      <div className="h-full bg-[#6366f1] rounded-full transition-all" style={{ width: `${(sr.success_rate || 0) * 100}%` }}></div>
                    </div>
                    <span className="text-xs font-medium text-[#6366f1] w-12 text-right">
                      {((sr.success_rate || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-sm text-gray-400">暂无统计数据</div>
          )}
        </div>
      </Card>

      {/* Optimization Stats & Recommendations */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="优化统计" icon={<Zap className="w-4 h-4" />}>
          <div className="space-y-2">
            {Object.keys(optStats).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(optStats).map(([key, value]: [string, any]) => (
                  <div key={key} className="flex items-center justify-between p-2 rounded-lg bg-gray-50">
                    <span className="text-xs text-gray-600">{key}</span>
                    <span className="text-xs font-semibold text-[#6366f1]">{typeof value === 'number' ? value.toFixed(2) : value}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-sm text-gray-400">暂无优化数据</div>
            )}
          </div>
        </Card>

        <Card title="优化建议">
          <div className="space-y-2">
            {recommendations.length > 0 ? recommendations.map((r: any, i: number) => {
              const text = typeof r === 'string' ? r : (r.description || r.reason || r.suggestion || JSON.stringify(r).slice(0, 80))
              const topo = typeof r === 'object' && r ? (r.topology || r.type || '') : ''
              return (
                <div key={i} className={`flex items-start gap-2 py-1.5 px-3 rounded-lg border ${
                  topo ? 'bg-indigo-50/50 border-indigo-100/50' : 'bg-gray-50 border-gray-100'
                }`}>
                  {topo ? (
                    <>
                      <span className="text-xs text-[#6366f1] font-medium shrink-0">{getTopologyIcon(topo)} {topo}:</span>
                      <span className="text-xs text-gray-600">{text}</span>
                    </>
                  ) : (
                    <span className="text-xs text-gray-600">{text}</span>
                  )}
                </div>
              )
            }) : (
              <div className="text-center py-6 text-xs text-gray-400">暂无优化建议</div>
            )}
          </div>
        </Card>
      </div>

      {/* Anomaly Injection */}
      <Card title="异常注入" icon={<AlertTriangle className="w-4 h-4" />}
        action={injectResult && (
          <div className={`flex items-center gap-1 text-xs ${injectResult.success ? 'text-[#10B981]' : 'text-red-500'}`}>
            {injectResult.success ? '✓ 成功' : '✗ 失败'}
          </div>
        )}>
        <div className="space-y-4">
          {/* Anomaly Type */}
          <div>
            <label className="text-xs text-gray-500 block mb-2">异常类型</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: 'topology_disrupt', label: '拓扑扰动', icon: '🔀', color: '#0EA5E9', desc: '强制切换拓扑结构' },
                { value: 'data_corrupt', label: '数据损坏', icon: '💥', color: '#F97316', desc: '注入乱码数据' },
                { value: 'node_fail', label: '节点失效', icon: '⚡', color: '#EF4444', desc: '模拟节点故障' },
              ].map(t => (
                <button key={t.value} onClick={() => setAnomalyType(t.value)}
                  className={`flex flex-col items-center gap-1 px-3 py-2.5 rounded-lg text-center transition-all border ${
                    anomalyType === t.value ? 'shadow-sm' : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                  }`}
                  style={anomalyType === t.value ? { borderColor: t.color, backgroundColor: `${t.color}10` } : {}}>
                  <span className="text-lg">{t.icon}</span>
                  <span className="text-xs font-medium text-gray-700">{t.label}</span>
                  <span className="text-[10px] text-gray-400">{t.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Topology Disrupt Options */}
          {anomalyType === 'topology_disrupt' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 block mb-2">强制切换到</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { value: 'star', label: '星形' },
                    { value: 'mesh', label: '网状' },
                    { value: 'tree', label: '树形' },
                    { value: 'ring', label: '环形' },
                    { value: 'hybrid', label: '混合' },
                  ].map(t => (
                    <button key={t.value} onClick={() => setTargetTopology(t.value)}
                      className={`px-2.5 py-1 text-xs rounded-lg border transition-colors ${
                        targetTopology === t.value ? 'border-[#0EA5E9] bg-[#0EA5E9]/5 text-[#0EA5E9]' : 'border-gray-200 text-gray-600 hover:border-gray-300'
                      }`}>
                      {getTopologyIcon(t.value)} {t.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-2">扰动时机</label>
                <div className="flex flex-wrap gap-2">
                  {[
                    { value: 'immediate', label: '立即执行' },
                    { value: 'next_step', label: '下一步触发' },
                    { value: 'mid_execution', label: '执行中途' },
                  ].map(t => (
                    <button key={t.value} onClick={() => setDisruptTiming(t.value)}
                      className={`px-2.5 py-1 text-xs rounded-lg border transition-colors ${
                        disruptTiming === t.value ? 'border-[#0EA5E9] bg-[#0EA5E9]/5 text-[#0EA5E9]' : 'border-gray-200 text-gray-600 hover:border-gray-300'
                      }`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          <Button onClick={handleInjectAnomaly} disabled={injecting} variant="danger" className="w-full justify-center">
            {injecting ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5 mr-1" />}
            注入异常
          </Button>
        </div>
      </Card>
    </div>
  )
}
