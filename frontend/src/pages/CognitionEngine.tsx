import React, { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { apiCognition } from '@/api/client'
import { Loader, Brain, Search, Plus, Moon, GitBranch, Zap, Shield } from 'lucide-react'

interface CognitionStatus { active_processes: number; total_completed: number; avg_reasoning_time_ms: number; strategies: string[] }

export function CognitionEngine() {
  const [status, setStatus] = useState<CognitionStatus | null>(null)
  const [memory, setMemory] = useState<any>(null)
  const [dreamLog, setDreamLog] = useState<any[]>([])
  const [blindSpots, setBlindSpots] = useState<any[]>([])
  const [crossDomain, setCrossDomain] = useState<any>(null)
  const [selfImprovement, setSelfImprovement] = useState<any>(null)
  const [learningCurve, setLearningCurve] = useState<any[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [memoryInput, setMemoryInput] = useState('')
  const [analogyQuery, setAnalogyQuery] = useState('')
  const [analogies, setAnalogies] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [searching, setSearching] = useState(false)
  const [dreaming, setDreaming] = useState(false)
  const [improving, setImproving] = useState(false)
  const [memorizing, setMemorizing] = useState(false)
  const [searchingAnalogies, setSearchingAnalogies] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [s, m, d, b, c, si, lc] = await Promise.all([
        apiCognition.getStatus(),
        apiCognition.getMemory(),
        apiCognition.getDreamLog(),
        apiCognition.getBlindSpots(),
        apiCognition.getCrossDomainMigration(),
        apiCognition.getSelfImprovement(),
        apiCognition.getLearningCurve()
      ])
      setStatus(s)
      setMemory(m)
      setDreamLog(d.logs || [])
      setBlindSpots(b.spots || [])
      setCrossDomain(c)
      setSelfImprovement(si)
      setLearningCurve(lc.curve || [])
    } catch (e) {
      console.error('Failed to fetch cognition data:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll(); const iv = setInterval(fetchAll, 10000); return () => clearInterval(iv) }, [fetchAll])

  const handleSearchMemory = async () => {
    if (!searchQuery.trim() || searching) return
    setSearching(true)
    try {
      const res = await apiCognition.searchMemory(searchQuery)
      setSearchResults(res.results || [])
    } catch (e) {
      console.error(e)
    } finally {
      setSearching(false)
    }
  }

  const handleAddMemory = async () => {
    if (!memoryInput.trim() || memorizing) return
    setMemorizing(true)
    try {
      await apiCognition.addToMemory(memoryInput)
      setMemoryInput('')
      await fetchAll()
    } catch (e) {
      console.error(e)
    } finally {
      setMemorizing(false)
    }
  }

  const handleTriggerDream = async () => {
    if (dreaming) return
    setDreaming(true)
    try {
      await apiCognition.triggerDream()
      await fetchAll()
    } catch (e) {
      console.error(e)
    } finally {
      setDreaming(false)
    }
  }

  const handleSearchAnalogies = async () => {
    if (!analogyQuery.trim() || searchingAnalogies) return
    setSearchingAnalogies(true)
    try {
      const res = await apiCognition.findAnalogies(analogyQuery)
      setAnalogies(res.analogies || [])
    } catch (e) {
      console.error(e)
    } finally {
      setSearchingAnalogies(false)
    }
  }

  const handleTriggerImprovement = async () => {
    if (improving) return
    setImproving(true)
    try {
      await apiCognition.triggerSelfImprovement()
      await fetchAll()
    } catch (e) {
      console.error(e)
    } finally {
      setImproving(false)
    }
  }

  if (loading) return <div className="flex items-center justify-center py-16"><Loader className="w-6 h-6 text-[#6366f1] animate-spin" /></div>

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-bold text-gray-800">认知引擎</h2>
      
      {/* Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card title="活跃推理">
          <p className="text-3xl font-bold text-[#6366f1]">{status?.active_processes ?? 0}</p>
        </Card>
        <Card title="已完成任务">
          <p className="text-3xl font-bold text-[#10B981]">{status?.total_completed ?? 0}</p>
        </Card>
        <Card title="平均推理时间">
          <p className="text-3xl font-bold text-[#0EA5E9]">{status?.avg_reasoning_time_ms ?? 0}<span className="text-sm text-gray-400 ml-1">ms</span></p>
        </Card>
      </div>

      {/* Reasoning Strategies */}
      <Card title="推理任务列表" icon={<Brain className="w-4 h-4" />}>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            {(status?.strategies || []).map(s => <Badge key={s} color="sky">{s}</Badge>)}
            {(!status?.strategies || status.strategies.length === 0) && <span className="text-xs text-gray-400">暂无推理策略</span>}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
              <span className="font-medium text-[#6366f1]">🔍 证据拆分</span>
              <p className="text-gray-600 mt-1">分证据集并行，需通信拼链</p>
            </div>
            <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
              <span className="font-medium text-[#6366f1]">⚔️ 角色约束</span>
              <p className="text-gray-600 mt-1">质疑者 vs 辩护者对抗</p>
            </div>
            <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
              <span className="font-medium text-[#6366f1]">📐 层级分离</span>
              <p className="text-gray-600 mt-1">高层策略 + 底层验证</p>
            </div>
            <div className="p-3 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
              <span className="font-medium text-[#6366f1]">📊 模态拆分</span>
              <p className="text-gray-600 mt-1">结构化 + 非结构化互补</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Blind Spots */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="认知盲区检测" icon={<Search className="w-4 h-4" />}>
          <div className="space-y-2">
            {blindSpots.length > 0 ? (
              blindSpots.map((spot: any, i: number) => (
                <div key={i} className="p-2.5 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-700">{spot.area || spot.name || '未知盲区'}</p>
                      <p className="text-xs text-gray-500 mt-0.5">{spot.description || spot.reason || ''}</p>
                    </div>
                    {spot.severity && <Badge color={spot.severity === 'high' ? 'red' : 'yellow'}>{spot.severity}</Badge>}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-xs text-gray-400 text-center py-6">暂无盲区</p>
            )}
          </div>
        </Card>

        {/* Self Improvement */}
        <Card title="自我改进" icon={<Zap className="w-4 h-4" />}
          action={<Button size="sm" onClick={handleTriggerImprovement} disabled={improving}>
            {improving ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Zap className="w-3.5 h-3.5 mr-1" />}
            触发改进
          </Button>}>
          <div className="space-y-3">
            {selfImprovement?.status === 'idle' ? (
              <div className="text-center py-6 text-xs text-gray-400">点击"触发改进"启动自我评估与优化</div>
            ) : selfImprovement?.improvements?.length > 0 ? (
              <div className="space-y-2">
                {selfImprovement.improvements.map((imp: any, i: number) => (
                  <div key={i} className="p-2.5 rounded-lg border border-gray-100">
                    <p className="text-xs font-medium text-gray-700">{imp.title || imp.area || `改进 #${i+1}`}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{imp.description || imp.reason || ''}</p>
                    {imp.impact && <p className="text-xs text-[#10B981] mt-1">影响: {imp.impact}</p>}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-xs text-gray-400">暂无改进记录</div>
            )}
          </div>
        </Card>
      </div>

      {/* Memory System */}
      <Card title="三层记忆架构" icon={<Brain className="w-4 h-4" />}>
        <div className="space-y-4">
          {/* Memory Layers */}
          <div className="grid grid-cols-3 gap-3">
            {memory?.layers && Object.entries(memory.layers).map(([layer, data]: [string, any]) => (
              <div key={layer} className="p-3 rounded-lg border border-gray-100">
                <p className="text-xs font-semibold text-[#6366f1] mb-1">{layer}</p>
                <p className="text-2xl font-bold text-gray-800">{data?.count || 0}</p>
                <p className="text-xs text-gray-500 mt-1">{data?.description || '条记忆'}</p>
              </div>
            ))}
            {!memory?.layers && (
              <>
                <div className="p-3 rounded-lg border border-gray-100">
                  <p className="text-xs font-semibold text-[#6366f1] mb-1">工作记忆</p>
                  <p className="text-2xl font-bold text-gray-800">0</p>
                </div>
                <div className="p-3 rounded-lg border border-gray-100">
                  <p className="text-xs font-semibold text-[#6366f1] mb-1">短期记忆</p>
                  <p className="text-2xl font-bold text-gray-800">0</p>
                </div>
                <div className="p-3 rounded-lg border border-gray-100">
                  <p className="text-xs font-semibold text-[#6366f1] mb-1">长期记忆</p>
                  <p className="text-2xl font-bold text-gray-800">0</p>
                </div>
              </>
            )}
          </div>

          {/* Search Memory */}
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !searching) handleSearchMemory() }}
              placeholder="搜索记忆..."
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30"
            />
            <Button onClick={handleSearchMemory} disabled={searching || !searchQuery.trim()}>
              {searching ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Search className="w-3.5 h-3.5 mr-1" />}
              搜索
            </Button>
          </div>

          {searchResults.length > 0 && (
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {searchResults.map((result: any, i: number) => (
                <div key={i} className="p-2.5 rounded-lg bg-gray-50 border border-gray-100">
                  <p className="text-xs text-gray-700">{result.content || result.text || JSON.stringify(result)}</p>
                  {result.relevance && <p className="text-xs text-gray-400 mt-1">相关度: {(result.relevance * 100).toFixed(0)}%</p>}
                </div>
              ))}
            </div>
          )}

          {/* Add Memory */}
          <div className="flex gap-2">
            <input
              type="text"
              value={memoryInput}
              onChange={e => setMemoryInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !memorizing) handleAddMemory() }}
              placeholder="输入要记忆的内容..."
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30"
            />
            <Button onClick={handleAddMemory} disabled={memorizing || !memoryInput.trim()} variant="secondary">
              {memorizing ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}
              记忆
            </Button>
          </div>
        </div>
      </Card>

      {/* Dream Integration */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card title="梦境整合日志" icon={<Moon className="w-4 h-4" />}
          action={<Button size="sm" onClick={handleTriggerDream} disabled={dreaming}>
            {dreaming ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Moon className="w-3.5 h-3.5 mr-1" />}
            触发梦境
          </Button>}>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {dreamLog.length > 0 ? dreamLog.map((log: any, i: number) => (
              <div key={i} className="p-2.5 rounded-lg border border-gray-100">
                <div className="flex items-center justify-between mb-1">
                  <Badge color="indigo">{log.type || '整合'}</Badge>
                  {log.time && <span className="text-xs text-gray-400">{new Date(log.time).toLocaleString()}</span>}
                </div>
                <p className="text-xs text-gray-600">{log.message || log.description || JSON.stringify(log).slice(0, 100)}</p>
              </div>
            )) : (
              <div className="text-center py-6 text-xs text-gray-400">点击"触发梦境"启动睡眠时整合</div>
            )}
          </div>
        </Card>

        {/* Cross-Domain Knowledge Migration */}
        <Card title="跨域知识迁移" icon={<GitBranch className="w-4 h-4" />}>
          <div className="space-y-3">
            {/* Automatic Migration */}
            <div className="p-3 rounded-lg border border-gray-100">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-gray-700">自动跨层迁移</span>
                <Badge color="green">运行中</Badge>
              </div>
              {crossDomain?.migrations?.length > 0 ? (
                <div className="space-y-1.5 max-h-32 overflow-y-auto">
                  {crossDomain.migrations.slice(0, 5).map((m: any, i: number) => (
                    <div key={i} className="text-xs text-gray-600 p-1.5 bg-gray-50 rounded">
                      {m.source} → {m.target}: {m.reason || m.description || '知识迁移'}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-gray-400">暂无迁移记录</p>
              )}
            </div>

            {/* Find Analogies */}
            <div className="space-y-2">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={analogyQuery}
                  onChange={e => setAnalogyQuery(e.target.value)}
                  placeholder="搜索类比..."
                  className="flex-1 px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30"
                />
                <Button size="sm" onClick={handleSearchAnalogies} disabled={searchingAnalogies || !analogyQuery.trim()}>
                  {searchingAnalogies ? <Loader className="w-3 h-3 mr-1 animate-spin" /> : <Search className="w-3 h-3 mr-1" />}
                  搜索
                </Button>
              </div>
              {analogies.length > 0 && (
                <div className="space-y-1.5 max-h-32 overflow-y-auto">
                  {analogies.map((a: any, i: number) => (
                    <div key={i} className="text-xs p-2 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
                      <span className="font-medium text-[#6366f1]">{a.source} ↔ {a.target}</span>
                      <p className="text-gray-600 mt-0.5">{a.reason || a.description || ''}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Manual Migration */}
            <Button size="sm" variant="secondary" className="w-full justify-center">
              <GitBranch className="w-3.5 h-3.5 mr-1" />
              手动迁移
            </Button>
          </div>
        </Card>
      </div>

      {/* Learning Curve */}
      <Card title="持续学习曲线" icon={<Zap className="w-4 h-4" />}>
        <div className="space-y-2">
          {learningCurve.length > 0 ? (
            <div className="space-y-2">
              {learningCurve.map((point: any, i: number) => (
                <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg border border-gray-100">
                  <span className="text-xs text-gray-500 w-20">{point.time || point.step || `#${i+1}`}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2 overflow-hidden">
                    <div className="h-full bg-[#6366f1] rounded-full transition-all" style={{ width: `${(point.accuracy || point.score || 0) * 100}%` }}></div>
                  </div>
                  <span className="text-xs font-medium text-[#6366f1] w-12 text-right">
                    {((point.accuracy || point.score || 0) * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-xs text-gray-400">暂无学习曲线数据</div>
          )}
        </div>
      </Card>

      {/* Adversarial Defense */}
      <Card title="辩护者对抗" icon={<Shield className="w-4 h-4" />}>
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm">🔴</span>
              <span className="text-xs font-semibold text-gray-700">质疑者</span>
            </div>
            <p className="text-xs text-gray-500">负责发现逻辑漏洞、证据不足和推理错误</p>
          </div>
          <div className="p-3 rounded-lg border border-gray-100">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm">🟢</span>
              <span className="text-xs font-semibold text-gray-700">辩护者</span>
            </div>
            <p className="text-xs text-gray-500">负责为结论辩护、补充证据和强化论证</p>
          </div>
        </div>
        <div className="mt-3 p-3 bg-indigo-50/50 rounded-lg border border-indigo-100/50">
          <p className="text-xs text-gray-600">
            <span className="font-medium text-[#6366f1]">对抗验证机制：</span>
            质疑者与辩护者通过多轮对话式对抗，逐步消除推理偏差，提升结论的可靠性。
          </p>
        </div>
      </Card>
    </div>
  )
}
