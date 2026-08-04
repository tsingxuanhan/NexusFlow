import { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import {
  Brain, Database, Layers, TrendingUp, Moon, GitBranch,
  Sparkles, Search, Plus, Loader, Wifi, WifiOff, Zap,
} from 'lucide-react'

// ─── Types ───

interface MemoryBlock {
  key: string
  value: string
  type: string
  confidence: number
}

interface CoreMemoryResponse {
  prompt: string
  stats: {
    blocks: MemoryBlock[]
  }
}

interface ConfidenceResponse {
  confidence: number
  factors: Record<string, unknown>
}

interface Gap {
  description: string
  severity: string
  domain: string
}

interface GapsResponse {
  gaps: Gap[]
  total: number
}

interface ImprovementItem {
  area: string
  before: number
  after: number
  delta: string
}

interface SelfImproveResponse {
  status?: string
  improvements?: ImprovementItem[]
  results?: ImprovementItem[]
  message?: string
  [key: string]: unknown
}

interface DreamResult {
  cycles: number
  patterns_consolidated: number
  patterns_pruned: number
  duration: number
}

interface DreamResponse {
  status: string
  dream: DreamResult
}

interface Analogy {
  source: string
  target: string
  confidence: number
  mapping: Record<string, unknown>
}

interface AnalogyResponse {
  analogies: Analogy[]
  total: number
}

interface RecallItem {
  content?: string
  text?: string
  memory?: string
  key?: string
  score?: number
  confidence?: number
  metadata?: Record<string, unknown>
  [key: string]: unknown
}

interface RecallResponse {
  results?: RecallItem[]
  memories?: RecallItem[]
  [key: string]: unknown
}

interface StatsResponse {
  [key: string]: unknown
}

type ConnectionStatus = 'connecting' | 'connected' | 'error'

// ─── API Helpers ───

const AGENTOS = '/agentos'

async function agentosGet<T>(path: string): Promise<T> {
  const res = await fetch(`${AGENTOS}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}`)
  const text = await res.text()
  return (text ? JSON.parse(text) : {}) as T
}

async function agentosPost<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${AGENTOS}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  const text = await res.text()
  return (text ? JSON.parse(text) : {}) as T
}

// ─── Helpers ───

const typeColors: Record<string, 'indigo' | 'orange' | 'sky'> = {
  core: 'indigo',
  episodic: 'orange',
  semantic: 'sky',
}

function getSeverityColor(severity: string | undefined): 'red' | 'orange' | 'gray' {
  const s = (severity ?? '').toLowerCase()
  if (s === 'high' || s === 'critical') return 'red'
  if (s === 'low') return 'gray'
  return 'orange'
}

function extractLearningData(stats: StatsResponse | null): Array<{ label: string; value: number }> {
  if (!stats) return []
  const candidates = ['learning_history', 'learning_curve', 'accuracy_history', 'training_history', 'epochs']
  for (const key of candidates) {
    const val = stats[key]
    if (Array.isArray(val) && val.length > 0) {
      return val.map((item: unknown, i: number) => {
        if (typeof item === 'number') {
          return { label: `E${i + 1}`, value: item }
        }
        if (typeof item === 'object' && item !== null) {
          const obj = item as Record<string, unknown>
          const numVal = obj.accuracy ?? obj.score ?? obj.value ?? obj.accuracy_rate
          if (typeof numVal === 'number') {
            const labelVal = obj.epoch ?? obj.step ?? obj.label
            return { label: String(labelVal ?? `E${i + 1}`), value: numVal }
          }
        }
        return { label: `E${i + 1}`, value: 0 }
      }).filter(d => d.value > 0)
    }
  }
  return []
}

function getRecallItems(data: RecallResponse): RecallItem[] {
  if (Array.isArray(data.results)) return data.results
  if (Array.isArray(data.memories)) return data.memories
  return []
}

function getImprovementItems(data: SelfImproveResponse): ImprovementItem[] {
  if (Array.isArray(data.improvements)) return data.improvements
  if (Array.isArray(data.results)) return data.results
  return []
}

// ─── Component ───

export function CognitionEngine() {
  // Connection
  const [connStatus, setConnStatus] = useState<ConnectionStatus>('connecting')

  // A. Meta Cognition
  const [confidence, setConfidence] = useState<number | null>(null)
  const [gaps, setGaps] = useState<Gap[]>([])
  const [selfImproveResult, setSelfImproveResult] = useState<SelfImproveResponse | null>(null)
  const [improving, setImproving] = useState(false)

  // B. Memory
  const [coreMemory, setCoreMemory] = useState<CoreMemoryResponse | null>(null)
  const [recallQuery, setRecallQuery] = useState('')
  const [recallResults, setRecallResults] = useState<RecallItem[] | null>(null)
  const [recalling, setRecalling] = useState(false)
  const [rememberContent, setRememberContent] = useState('')
  const [remembering, setRemembering] = useState(false)

  // C. Dream
  const [dreamHistory, setDreamHistory] = useState<DreamResult[]>([])
  const [dreaming, setDreaming] = useState(false)

  // D. Transfer
  const [sourceDomain, setSourceDomain] = useState('')
  const [targetDomain, setTargetDomain] = useState('')
  const [analogies, setAnalogies] = useState<Analogy[]>([])
  const [searchingAnalogy, setSearchingAnalogy] = useState(false)
  const [transferring, setTransferring] = useState(false)
  const [transferResult, setTransferResult] = useState<string | null>(null)

  // E. Stats
  const [stats, setStats] = useState<StatsResponse | null>(null)

  // ─── Fetch functions ───

  const fetchConfidence = useCallback(async () => {
    try {
      const data = await agentosPost<ConfidenceResponse>('/meta/confidence', { query: 'system_health' })
      setConfidence(data.confidence)
      setConnStatus('connected')
    } catch {
      setConnStatus(prev => prev === 'connecting' ? 'error' : prev)
    }
  }, [])

  const fetchGaps = useCallback(async () => {
    try {
      const data = await agentosGet<GapsResponse>('/meta/gaps?domain=general')
      setGaps(data.gaps || [])
      setConnStatus('connected')
    } catch {
      // silent
    }
  }, [])

  const fetchCoreMemory = useCallback(async () => {
    try {
      const data = await agentosGet<CoreMemoryResponse>('/memory/core')
      setCoreMemory(data)
      setConnStatus('connected')
    } catch {
      // silent
    }
  }, [])

  const fetchStats = useCallback(async () => {
    try {
      const data = await agentosGet<StatsResponse>('/stats')
      setStats(data)
      setConnStatus('connected')
    } catch {
      // silent
    }
  }, [])

  // ─── Initial load ───

  useEffect(() => {
    fetchConfidence()
    fetchGaps()
    fetchCoreMemory()
    fetchStats()
  }, [fetchConfidence, fetchGaps, fetchCoreMemory, fetchStats])

  // ─── Actions ───

  const handleSelfImprove = useCallback(async () => {
    setImproving(true)
    try {
      const data = await agentosPost<SelfImproveResponse>('/meta/self-improve', {})
      setSelfImproveResult(data)
    } catch {
      setSelfImproveResult({ status: 'error', message: '自我改进请求失败' })
    } finally {
      setImproving(false)
    }
  }, [])

  const handleRecall = useCallback(async () => {
    if (!recallQuery.trim()) return
    setRecalling(true)
    setRecallResults(null)
    try {
      const data = await agentosPost<RecallResponse>('/memory/recall', {
        query: recallQuery.trim(),
        top_k: 5,
      })
      setRecallResults(getRecallItems(data))
    } catch {
      setRecallResults([])
    } finally {
      setRecalling(false)
    }
  }, [recallQuery])

  const handleRemember = useCallback(async () => {
    if (!rememberContent.trim()) return
    setRemembering(true)
    try {
      await agentosPost<unknown>('/memory/remember', { content: rememberContent.trim() })
      setRememberContent('')
      fetchCoreMemory()
    } catch {
      // silent
    } finally {
      setRemembering(false)
    }
  }, [rememberContent, fetchCoreMemory])

  const handleDream = useCallback(async () => {
    setDreaming(true)
    try {
      const data = await agentosPost<DreamResponse>('/sleeptime/dream')
      if (data.dream) {
        setDreamHistory(prev => [data.dream, ...prev])
      }
    } catch {
      // silent
    } finally {
      setDreaming(false)
    }
  }, [])

  const handleAnalogy = useCallback(async () => {
    if (!sourceDomain.trim() || !targetDomain.trim()) return
    setSearchingAnalogy(true)
    setAnalogies([])
    try {
      const data = await agentosPost<AnalogyResponse>('/transfer/analogy', {
        source_domain: sourceDomain.trim(),
        target_domain: targetDomain.trim(),
      })
      setAnalogies(data.analogies || [])
    } catch {
      // silent
    } finally {
      setSearchingAnalogy(false)
    }
  }, [sourceDomain, targetDomain])

  const handleTransfer = useCallback(async () => {
    if (!sourceDomain.trim() || !targetDomain.trim()) return
    setTransferring(true)
    setTransferResult(null)
    try {
      const data = await agentosPost<Record<string, unknown>>('/transfer/execute', {
        source_domain: sourceDomain.trim(),
        target_domain: targetDomain.trim(),
      })
      setTransferResult(data.status === 'ok' ? '迁移执行成功' : JSON.stringify(data))
    } catch {
      setTransferResult('迁移执行失败')
    } finally {
      setTransferring(false)
    }
  }, [sourceDomain, targetDomain])

  // ─── Derived data ───

  const memoryBlocks = coreMemory?.stats?.blocks ?? []
  const memoryByType: Record<string, MemoryBlock[]> = {
    core: memoryBlocks.filter(b => b.type === 'core'),
    episodic: memoryBlocks.filter(b => b.type === 'episodic'),
    semantic: memoryBlocks.filter(b => b.type === 'semantic'),
  }

  const learningData = extractLearningData(stats)
  const maxLearning = learningData.length > 0 ? Math.max(...learningData.map(d => d.value)) : 0

  const improvementItems = selfImproveResult ? getImprovementItems(selfImproveResult) : []

  // ─── Render ───

  return (
    <div className="space-y-5">
      {/* Connection Status */}
      <div className="flex items-center gap-1.5 text-xs text-gray-400">
        {connStatus === 'connected' ? (
          <><Wifi className="w-3.5 h-3.5 text-[#10B981]" /> AgentOS 已连接</>
        ) : connStatus === 'error' ? (
          <><WifiOff className="w-3.5 h-3.5 text-red-400" /> AgentOS 服务不可用</>
        ) : (
          <><Wifi className="w-3.5 h-3.5 animate-pulse" /> 连接中...</>
        )}
      </div>

      {/* A. Meta Cognition Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Confidence + Gaps */}
        <Card title="置信度" icon={<Brain className="w-4 h-4" />}>
          <div className="flex items-center gap-4">
            <div className="relative w-20 h-20 shrink-0">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="34" fill="none" stroke="#E5E7EB" strokeWidth="6" />
                <circle
                  cx="40" cy="40" r="34" fill="none" stroke="#6366f1" strokeWidth="6"
                  strokeDasharray={`${(confidence ?? 0) * 213.6} 213.6`}
                  strokeLinecap="round"
                  className="transition-all duration-500"
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-[#6366f1]">
                {confidence !== null ? `${Math.round(confidence * 100)}%` : '...'}
              </span>
            </div>
            <div className="min-w-0">
              <p className="text-xs text-gray-400 mb-1.5">认知盲区</p>
              <div className="flex flex-wrap gap-1">
                {gaps.length > 0 ? (
                  gaps.map((g, i) => (
                    <Badge key={i} color={getSeverityColor(g.severity)}>
                      {g.description}
                    </Badge>
                  ))
                ) : (
                  <span className="text-xs text-gray-300">暂无盲区</span>
                )}
              </div>
            </div>
          </div>
        </Card>

        {/* Self-Improve */}
        <Card
          title="自我改进"
          icon={<Sparkles className="w-4 h-4" />}
          className="md:col-span-2"
          action={
            <Button size="sm" onClick={handleSelfImprove} disabled={improving}>
              {improving ? (
                <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 改进中...</>
              ) : (
                <><Zap className="w-3.5 h-3.5 mr-1" /> 触发改进</>
              )}
            </Button>
          }
        >
          {selfImproveResult === null ? (
            <div className="flex items-center justify-center py-8 text-xs text-gray-400">
              点击"触发改进"启动自我评估与优化
            </div>
          ) : improvementItems.length > 0 ? (
            <div className="space-y-3">
              {improvementItems.map((s, i) => (
                <div key={i} className="flex items-center gap-3">
                  <span className="text-xs text-gray-500 w-32 shrink-0">{s.area}</span>
                  <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden relative">
                    <div className="absolute h-full bg-gray-200 rounded-full" style={{ width: `${s.before * 100}%` }} />
                    <div className="absolute h-full bg-gradient-to-r from-[#6366f1] to-[#0EA5E9] rounded-full transition-all" style={{ width: `${s.after * 100}%` }} />
                  </div>
                  <span className="text-xs font-semibold text-[#10B981] w-12 text-right">{s.delta}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              <Badge color={selfImproveResult.status === 'error' ? 'red' : 'green'}>
                {selfImproveResult.status ?? '完成'}
              </Badge>
              {selfImproveResult.message && (
                <p className="text-xs text-gray-500">{selfImproveResult.message}</p>
              )}
              <pre className="text-xs text-gray-400 bg-gray-50 rounded p-2 overflow-auto max-h-32">
                {JSON.stringify(selfImproveResult, null, 2)}
              </pre>
            </div>
          )}
        </Card>
      </div>

      {/* B. Three-Layer Memory */}
      <Card title="三层记忆架构" icon={<Layers className="w-4 h-4" />}>
        {/* Memory blocks by type */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          {(['core', 'episodic', 'semantic'] as const).map(layer => (
            <div key={layer} className="space-y-2">
              <div className="flex items-center gap-2 mb-3">
                <Database className="w-3.5 h-3.5 text-[#6366f1]" />
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">{layer}</span>
                <Badge color={typeColors[layer]}>{memoryByType[layer].length}</Badge>
              </div>
              {memoryByType[layer].length > 0 ? (
                memoryByType[layer].map((item, i) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <p className="text-xs font-mono text-[#6366f1] mb-1">{item.key}</p>
                    <p className="text-xs text-gray-600">{item.value}</p>
                    <div className="mt-2 flex items-center gap-1">
                      <div className="flex-1 h-1 bg-gray-200 rounded-full">
                        <div className="h-full bg-[#10B981] rounded-full" style={{ width: `${item.confidence * 100}%` }} />
                      </div>
                      <span className="text-[10px] text-gray-400">{(item.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-4 text-xs text-gray-300">暂无数据</div>
              )}
            </div>
          ))}
        </div>

        {/* Recall search */}
        <div className="border-t border-gray-100 pt-4 space-y-3">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={recallQuery}
              onChange={e => setRecallQuery(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !recalling) handleRecall() }}
              placeholder="搜索记忆..."
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
            />
            <Button size="sm" onClick={handleRecall} disabled={recalling || !recallQuery.trim()}>
              {recalling ? (
                <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 搜索中</>
              ) : (
                <><Search className="w-3.5 h-3.5 mr-1" /> 搜索</>
              )}
            </Button>
          </div>
          {recallResults !== null && (
            <div className="space-y-2">
              {recallResults.length > 0 ? (
                recallResults.map((r, i) => {
                  const content = String(r.content ?? r.text ?? r.memory ?? r.key ?? JSON.stringify(r))
                  const score = typeof r.score === 'number' ? r.score : typeof r.confidence === 'number' ? r.confidence : null
                  return (
                    <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                      <p className="text-xs text-gray-600">{content}</p>
                      {score !== null && (
                        <div className="mt-2 flex items-center gap-1">
                          <div className="flex-1 h-1 bg-gray-200 rounded-full">
                            <div className="h-full bg-[#10B981] rounded-full" style={{ width: `${score * 100}%` }} />
                          </div>
                          <span className="text-[10px] text-gray-400">{(score * 100).toFixed(0)}%</span>
                        </div>
                      )}
                    </div>
                  )
                })
              ) : (
                <p className="text-xs text-gray-400 text-center py-2">未找到相关记忆</p>
              )}
            </div>
          )}
        </div>

        {/* Remember input */}
        <div className="border-t border-gray-100 pt-4 flex items-center gap-2">
          <input
            type="text"
            value={rememberContent}
            onChange={e => setRememberContent(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !remembering) handleRemember() }}
            placeholder="输入要记忆的内容..."
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
          />
          <Button size="sm" variant="secondary" onClick={handleRemember} disabled={remembering || !rememberContent.trim()}>
            {remembering ? (
              <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 记忆中</>
            ) : (
              <><Plus className="w-3.5 h-3.5 mr-1" /> 记忆</>
            )}
          </Button>
        </div>
      </Card>

      {/* C. Dream Logs + D. Cross-Domain Transfer */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Dream Logs */}
        <Card
          title="梦境整合日志"
          icon={<Moon className="w-4 h-4" />}
          action={
            <Button size="sm" onClick={handleDream} disabled={dreaming}>
              {dreaming ? (
                <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 梦境中</>
              ) : (
                <><Zap className="w-3.5 h-3.5 mr-1" /> 触发梦境</>
              )}
            </Button>
          }
        >
          {dreamHistory.length > 0 ? (
            <div className="space-y-2">
              {dreamHistory.map((d, i) => (
                <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-gray-400">#{d.cycles}</span>
                    <div className="flex gap-1">
                      <Badge color="green">{d.patterns_consolidated} 整合</Badge>
                      <Badge color="orange">{d.patterns_pruned} 剪枝</Badge>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400">{d.duration.toFixed(1)}s</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6 text-xs text-gray-400">
              点击"触发梦境"启动睡眠时整合
            </div>
          )}
        </Card>

        {/* Cross-Domain Transfer */}
        <Card title="跨域知识迁移" icon={<GitBranch className="w-4 h-4" />}>
          <div className="space-y-3">
            {/* Source / Target inputs */}
            <div className="grid grid-cols-2 gap-2">
              <input
                type="text"
                value={sourceDomain}
                onChange={e => setSourceDomain(e.target.value)}
                placeholder="源域 (如 security)"
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
              />
              <input
                type="text"
                value={targetDomain}
                onChange={e => setTargetDomain(e.target.value)}
                placeholder="目标域 (如 network)"
                className="px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
              />
            </div>

            {/* Analogy search button */}
            <Button
              size="sm"
              variant="secondary"
              onClick={handleAnalogy}
              disabled={searchingAnalogy || !sourceDomain.trim() || !targetDomain.trim()}
              className="w-full"
            >
              {searchingAnalogy ? (
                <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 搜索类比</>
              ) : (
                <><Search className="w-3.5 h-3.5 mr-1" /> 查找类比映射</>
              )}
            </Button>

            {/* Analogies list */}
            {analogies.length > 0 && (
              <div className="space-y-2">
                {analogies.map((a, i) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-2 text-xs mb-2">
                      <span className="font-mono text-[#6366f1]">{a.source}</span>
                      <span className="text-gray-300">→</span>
                      <span className="font-mono text-[#0EA5E9]">{a.target}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-gray-200 rounded-full">
                        <div className="h-full bg-[#F97316] rounded-full" style={{ width: `${a.confidence * 100}%` }} />
                      </div>
                      <span className="text-[10px] text-gray-400">{(a.confidence * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Execute transfer button */}
            <Button
              size="sm"
              variant="danger"
              onClick={handleTransfer}
              disabled={transferring || !sourceDomain.trim() || !targetDomain.trim()}
              className="w-full"
            >
              {transferring ? (
                <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 迁移中</>
              ) : (
                <><GitBranch className="w-3.5 h-3.5 mr-1" /> 执行迁移</>
              )}
            </Button>

            {/* Transfer result */}
            {transferResult && (
              <p className={`text-xs text-center ${transferResult.includes('失败') ? 'text-red-500' : 'text-[#10B981]'}`}>
                {transferResult}
              </p>
            )}
          </div>
        </Card>
      </div>

      {/* E. Learning Curve */}
      <Card title="持续学习曲线" icon={<TrendingUp className="w-4 h-4" />}>
        {learningData.length > 0 ? (
          <div className="h-48 flex items-end gap-3 px-4">
            {learningData.map((d, i) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <span className="text-[10px] text-gray-400">{(d.value * 100).toFixed(0)}%</span>
                <div
                  className="w-full rounded-t-md bg-gradient-to-t from-[#6366f1] to-[#0EA5E9] transition-all"
                  style={{ height: `${(d.value / maxLearning) * 140}px` }}
                />
                <span className="text-[10px] text-gray-400">{d.label}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="h-48 flex items-center justify-center text-sm text-gray-400">
            暂无数据
          </div>
        )}
      </Card>
    </div>
  )
}
