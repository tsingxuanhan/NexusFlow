import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api, type AgentInfo, type TaskExecution, type OutputFormat } from '@/api/client'
import { Play, Loader, Activity, Clock, FileText, Upload, X, Zap, AlertTriangle, RotateCcw } from 'lucide-react'

interface LogEntry { time: string; level: string; agent?: string; msg: string }
interface AgentOutput { agent_id: string; content: string; time: string }
interface UploadedFile { id: string; file: File; name: string; size: number; status: 'uploading' | 'success' | 'error'; response?: any; error?: string; taskId?: string }

const STRATEGIES = [
  { value: 'auto', label: '🤖 自动选择' },
  { value: 'evidence_split', label: '🔍 证据拆分' },
  { value: 'role_constraint', label: '⚔️ 角色约束 — 质疑者 vs 辩护者对抗' },
  { value: 'layer_separation', label: '📐 层级分离' },
  { value: 'modality_split', label: '📊 模态拆分' },
  { value: 'time_slice', label: '⏳ 时序切片' },
  { value: 'abstraction_level', label: '🧩 抽象层级' },
]

const FAULT_TYPES = [
  { value: 'node_failure', label: '💥 节点失效', desc: '模拟 Agent 失效，触发降级策略' },
  { value: 'latency_inject', label: '⏱️ 延迟注入', desc: '注入网络/计算延迟，测试超时机制' },
  { value: 'data_corruption', label: '🔀 数据损坏', desc: '注入损坏数据，验证数据校验能力' },
  { value: 'topology_disrupt', label: '🌐 拓扑扰动', desc: '强制切换拓扑结构，测试自适应能力' },
  { value: 'resource_exhaust', label: '📉 资源耗尽', desc: '模拟资源耗尽，验证渐进式退化' },
]

const SEVERITY_LEVELS = [
  { value: 'low', label: '低', color: 'green' },
  { value: 'medium', label: '中', color: 'yellow' },
  { value: 'high', label: '高', color: 'orange' },
  { value: 'critical', label: '严重', color: 'red' },
]

export function CommandCenter() {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [tasks, setTasks] = useState<TaskExecution[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [agentOutputs, setAgentOutputs] = useState<Record<string, AgentOutput[]>>({})
  const [activeAgentTab, setActiveAgentTab] = useState<string>('')
  const [taskDesc, setTaskDesc] = useState('')
  const [maxSteps, setMaxSteps] = useState(5)
  const [strategy, setStrategy] = useState('auto')
  const [outputFormat, setOutputFormat] = useState('markdown')
  const [formats, setFormats] = useState<OutputFormat[]>([])
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set())
  const [creating, setCreating] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [_connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'error'>('connecting')
  
  // Fault injection state
  const [showFaultPanel, setShowFaultPanel] = useState(false)
  const [faultTaskId, setFaultTaskId] = useState('')
  const [faultType, setFaultType] = useState('node_failure')
  const [faultTarget, setFaultTarget] = useState('')
  const [faultSeverity, setFaultSeverity] = useState('medium')
  const [faultDuration, setFaultDuration] = useState(1)
  const [injecting, setInjecting] = useState(false)
  const [injectResult, setInjectResult] = useState<{success: boolean; msg: string} | null>(null)
  const [faultState, setFaultState] = useState<{disabled_agents: string[]; faults: any[]; recovery_attempts: any[]} | null>(null)

  const logRef = useRef<HTMLDivElement>(null)
  const outputRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchAll = useCallback(async () => {
    try {
      const [_s, a, t, fmts] = await Promise.all([
        api.getSystemStatus(),
        api.getAgents(),
        api.getTasks(),
        fetch('/api/output/formats').then(r => r.ok ? r.json() : { formats: [] })
      ])
      setAgents(a.agents)
      setTasks(t.tasks)
      setFormats(fmts.formats || [])
      setConnectionStatus('connected')
    } catch {
      setConnectionStatus(prev => prev === 'connecting' ? 'error' : prev)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const ws = api.connectEvents((msg: any) => {
      const d = msg.data || msg  // unwrap data payload
      if (msg.type === 'log') {
        const entry: LogEntry = {
          time: new Date().toLocaleTimeString(),
          level: d.level || 'info',
          agent: d.agent,
          msg: d.message || d.msg || JSON.stringify(d)
        }
        setLogs(prev => [...prev.slice(-500), entry])
      } else if (msg.type === 'agent_output') {
        const aid = d.agent_id || d.agent || 'unknown'
        const entry: AgentOutput = { agent_id: aid, content: d.output || d.content || d.msg || '', time: new Date().toLocaleTimeString() }
        setAgentOutputs(prev => ({ ...prev, [aid]: [...(prev[aid] || []).slice(-100), entry] }))
        setActiveAgentTab(prev => prev || aid)
      } else if (msg.type === 'task_update' || msg.type === 'system_status') {
        fetchAll()
      } else if (msg.type === 'agent_update') {
        api.getAgents().then(a => setAgents(a.agents)).catch(() => {})
      } else if (msg.type === 'fault_injected') {
        setLogs(prev => [...prev, {
          time: new Date().toLocaleTimeString(), level: 'error',
          agent: '系统', msg: d.message || '故障注入'
        }])
        // Refresh fault state after injection
        if (d.task_id) fetchFaultState(d.task_id)
      } else if (msg.type === 'recovery_success') {
        if (d.task_id) fetchFaultState(d.task_id)
      } else if (msg.type === 'recovery_attempt') {
        setLogs(prev => [...prev, {
          time: new Date().toLocaleTimeString(), level: 'warn',
          agent: '系统', msg: `🔧 正在恢复 ${d.agent_id}...`
        }])
      } else if (msg.type === 'history') {
        // Restore state from server-side event history on reconnect
        const events = d.events || (msg as any).events || []
        const restoredLogs: LogEntry[] = []
        const restoredOutputs: Record<string, AgentOutput[]> = {}
        for (const evt of events) {
          const ed = evt.data || evt
          if (evt.type === 'log') {
            restoredLogs.push({
              time: evt.ts ? new Date(evt.ts).toLocaleTimeString() : '',
              level: ed.level || 'info',
              agent: ed.agent,
              msg: ed.message || ed.msg || JSON.stringify(ed)
            })
          } else if (evt.type === 'agent_output') {
            const aid = ed.agent_id || ed.agent || 'unknown'
            if (!restoredOutputs[aid]) restoredOutputs[aid] = []
            restoredOutputs[aid].push({
              agent_id: aid,
              content: ed.output || ed.content || ed.msg || '',
              time: evt.ts ? new Date(evt.ts).toLocaleTimeString() : ''
            })
          }
        }
        if (restoredLogs.length > 0) setLogs(restoredLogs)
        if (Object.keys(restoredOutputs).length > 0) {
          setAgentOutputs(restoredOutputs)
          const firstKey = Object.keys(restoredOutputs)[0]
          if (firstKey) setActiveAgentTab(prev => prev || firstKey)
        }
      }
    })
    return () => { ws.close() }
  }, [fetchAll]) // activeAgentTab intentionally excluded to prevent WS reconnect loop

  useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight }, [logs])
  useEffect(() => { if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight }, [agentOutputs, activeAgentTab])

  // File Upload
  const handleFileUpload = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const newFiles: UploadedFile[] = Array.from(files).map(file => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file, name: file.name, size: file.size, status: 'uploading' as const
    }))
    setUploadedFiles(prev => [...prev, ...newFiles])

    await Promise.all(newFiles.map(async (uf) => {
      try {
        const formData = new FormData()
        formData.append('file', uf.file)
        const r = await fetch('/api/upload', { method: 'POST', body: formData })
        if (!r.ok) throw new Error('Upload failed')
        const resp = await r.json()
        setUploadedFiles(prev => prev.map(f => f.id === uf.id ? { ...f, status: 'success', response: resp } : f))
      } catch (e) {
        setUploadedFiles(prev => prev.map(f => f.id === uf.id ? {
          ...f, status: 'error', error: e instanceof Error ? e.message : 'Upload failed'
        } : f))
      }
    }))
  }, [])

  const removeFile = useCallback((id: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== id))
    setSelectedFiles(prev => { const n = new Set(prev); n.delete(id); return n })
  }, [])

  const toggleFileSelection = useCallback((id: string) => {
    setSelectedFiles(prev => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id); else n.add(id)
      return n
    })
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragOver(true) }, [])
  const handleDragLeave = useCallback((e: React.DragEvent) => { e.preventDefault(); setDragOver(false) }, [])
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFileUpload(e.dataTransfer.files)
  }, [handleFileUpload])

  const handleCreate = async () => {
    if (!taskDesc.trim() || creating) return
    setCreating(true)
    try {
      // Read file contents first and include in task description
      const selectedSuccess = uploadedFiles.filter(f => selectedFiles.has(f.id) && f.status === 'success')
      let fileContextParts: string[] = []
      for (const f of selectedSuccess) {
        try {
          const textExts = ['.txt','.md','.csv','.json','.xml','.yaml','.yml','.log','.py','.js','.html','.css','.ts']
          const ext = f.name.substring(f.name.lastIndexOf('.')).toLowerCase()
          if (textExts.includes(ext) || f.file.type.startsWith('text/') || f.file.type === 'application/json') {
            const text = await f.file.text()
            fileContextParts.push(`\n--- 文件: ${f.name} ---\n${text.substring(0, 30000)}`)
          }
        } catch {}
      }
      
      // Build full description with file contents
      let fullDesc = taskDesc
      if (fileContextParts.length > 0) {
        fullDesc += '\n\n=== 用户上传的文件内容 ===\n' + fileContextParts.join('\n')
      }
      
      const result = await api.createTask(fullDesc, maxSteps, strategy, outputFormat)
      
      // Also upload raw files to server for reference
      if (selectedSuccess.length > 0 && result.task_id) {
        await Promise.all(selectedSuccess.map(async (f) => {
          try {
            const formData = new FormData()
            formData.append('file', f.file)
            formData.append('task_id', result.task_id)
            await fetch('/api/upload', { method: 'POST', body: formData })
            setUploadedFiles(prev => prev.map(uf => uf.id === f.id ? { ...uf, taskId: result.task_id } : uf))
          } catch {}
        }))
      }
      setLogs(prev => [...prev, {
        time: new Date().toLocaleTimeString(), level: 'success',
        msg: `任务已创建: ${result.task_id} — ${taskDesc} (策略: ${strategy})`
      }])
      setTaskDesc('')
      setSelectedFiles(new Set())
      await fetchAll()
    } catch (e) {
      setLogs(prev => [...prev, {
        time: new Date().toLocaleTimeString(), level: 'error',
        msg: `任务创建失败: ${e instanceof Error ? e.message : '未知错误'}`
      }])
    } finally {
      setCreating(false)
    }
  }

  // Fault Injection
  const handleInjectFault = async () => {
    if (!faultTaskId || injecting) return
    setInjecting(true)
    setInjectResult(null)
    try {
      const r = await fetch(`/api/tasks/${faultTaskId}/inject-fault`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          fault_type: faultType,
          target: faultTarget || undefined,
          severity: faultSeverity,
          duration: faultDuration
        })
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: '注入失败' }))
        throw new Error(err.detail || `HTTP ${r.status}`)
      }
      const result = await r.json()
      setInjectResult({ success: true, msg: `${result.type} (${result.fault_id}) 已注入` })
      setLogs(prev => [...prev, {
        time: new Date().toLocaleTimeString(), level: 'error',
        agent: '异常注入', msg: `💥 ${result.type} → ${faultTarget || '系统'} [${faultSeverity}]`
      }])
    } catch (e) {
      setInjectResult({ success: false, msg: e instanceof Error ? e.message : '注入失败' })
    } finally {
      setInjecting(false)
    }
  }

  // Fetch fault state for a task
  const fetchFaultState = async (taskId: string) => {
    try {
      const r = await fetch(`/api/tasks/${taskId}/injections`)
      if (r.ok) {
        const data = await r.json()
        setFaultState({ disabled_agents: data.disabled_agents || [], faults: data.faults || [], recovery_attempts: data.recovery_attempts || [] })
      }
    } catch {}
  }

  // Recover a disabled agent
  const handleRecoverAgent = async (agentId: string) => {
    if (!faultTaskId) return
    try {
      const r = await fetch(`/api/tasks/${faultTaskId}/recover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId })
      })
      if (r.ok) {
        setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), level: 'success', agent: '系统', msg: `🔧 ${agentId} 已手动恢复` }])
        await fetchFaultState(faultTaskId)
      } else {
        const err = await r.json().catch(() => ({ detail: '恢复失败' }))
        setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), level: 'error', agent: '系统', msg: `恢复 ${agentId} 失败: ${err.detail || r.status}` }])
      }
    } catch (e) {
      setLogs(prev => [...prev, { time: new Date().toLocaleTimeString(), level: 'error', agent: '系统', msg: `恢复 ${agentId} 失败: ${e instanceof Error ? e.message : '未知'}` }])
    }
  }

  // Recover all disabled agents
  const handleRecoverAll = async () => {
    if (!faultTaskId || !faultState?.disabled_agents.length) return
    for (const aid of faultState.disabled_agents) {
      await handleRecoverAgent(aid)
    }
  }

  const statusColors: Record<string, string> = { running: 'green', completed: 'blue', failed: 'red', pending: 'yellow', planning: 'indigo', reviewing: 'sky' }
  const logColors: Record<string, string> = { ERROR: 'text-red-400', WARN: 'text-yellow-400', INFO: 'text-sky-400', DEBUG: 'text-gray-400', error: 'text-red-400', warn: 'text-yellow-400', info: 'text-sky-400', debug: 'text-gray-400', success: 'text-[#10B981]' }
  const agentIds = Object.keys(agentOutputs)
  const currentOutputs = agentOutputs[activeAgentTab] || []
  const activeTasks = tasks.filter(t => ['running', 'planning'].includes(t.status))

  return (
    <div className="flex gap-4 h-[calc(100vh-3rem)]">
      {/* ====== LEFT: Agent Output + Logs ====== */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <Card title="Agent 实时输出" icon={<Activity className="w-4 h-4" />}
              action={<Badge color="indigo">{agentIds.length} agents</Badge>}>
          <div className="flex flex-col h-64">
            {agentIds.length > 0 && (
              <div className="flex items-center gap-1 mb-2 overflow-x-auto pb-1 border-b border-gray-100">
                {agentIds.map(aid => {
                    const ag = agents.find((a: any) => a.id === aid)
                    const label = ag ? `${ag.icon || ''} ${ag.name || aid}` : aid
                    return (
                  <button key={aid} onClick={() => setActiveAgentTab(aid)}
                    className={`px-2.5 py-1 text-xs rounded-t-lg whitespace-nowrap transition-colors ${activeAgentTab === aid ? 'bg-[#6366f1] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                    {label}
                  </button>
                    )
                  })}
              </div>
            )}
            <div ref={outputRef} className="flex-1 overflow-y-auto bg-slate-900 rounded-lg p-3 font-mono text-xs text-green-400 min-h-0">
              {currentOutputs.length === 0 ? (
                <p className="text-gray-500 text-center mt-8">等待 Agent 输出...</p>
              ) : (
                currentOutputs.map((o, i) => (
                  <div key={i} className="mb-1.5">
                    <span className="text-gray-500">[{o.time}]</span> <span className="text-[#6366f1]">{o.agent_id}:</span> {o.content}
                  </div>
                ))
              )}
            </div>
          </div>
        </Card>

        <Card title="实时日志" icon={<Clock className="w-4 h-4" />}
              action={<Badge color="sky">{logs.length}</Badge>} className="flex-1">
          <div ref={logRef} className="h-full overflow-y-auto bg-slate-900 rounded-lg p-3 font-mono text-xs min-h-[200px]">
            {logs.length === 0 ? (
              <p className="text-gray-500 text-center mt-8">等待日志...</p>
            ) : (
              logs.map((l, i) => (
                <div key={i} className="mb-0.5">
                  <span className="text-gray-500">{l.time}</span>
                  <span className={`ml-2 ${logColors[l.level] || 'text-gray-300'}`}>[{l.level}]</span>
                  {l.agent && <span className="ml-1 text-[#6366f1]">[{l.agent}]</span>}
                  <span className="ml-1 text-gray-300">{l.msg}</span>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>

      {/* ====== RIGHT: Tasks + Agents + Fault Injection ====== */}
      <div className="w-80 flex flex-col gap-4 shrink-0">
        {/* Task Creation */}
        <Card title="创建任务" icon={<Play className="w-4 h-4" />}>
          <div className="space-y-3">
            <div onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${dragOver ? 'border-[#6366f1] bg-[#6366f1]/5' : 'border-gray-200 hover:border-gray-300'}`}>
              <Upload className={`w-6 h-6 mx-auto mb-2 ${dragOver ? 'text-[#6366f1]' : 'text-gray-400'}`} />
              <p className="text-sm text-gray-500">拖拽文件到此处或点击上传</p>
              <p className="text-xs text-gray-400 mt-0.5">支持多文件上传，可在提交时关联到任务</p>
              <input ref={fileInputRef} type="file" multiple className="hidden"
                onChange={e => { handleFileUpload(e.target.files); if (e.target) e.target.value = '' }} />
            </div>

            {uploadedFiles.length > 0 && (
              <div className="space-y-1.5">
                {uploadedFiles.map(f => (
                  <div key={f.id} className="flex items-center gap-2 p-1.5 rounded-lg bg-gray-50 border border-gray-100">
                    <input type="checkbox" checked={selectedFiles.has(f.id)} onChange={() => toggleFileSelection(f.id)}
                      disabled={f.status !== 'success'} className="w-3 h-3 rounded text-[#6366f1] accent-[#6366f1]" />
                    <FileText className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                    <span className="text-xs text-gray-600 flex-1 truncate">{f.name}</span>
                    <span className="text-[10px] text-gray-400">{(f.size / 1024).toFixed(1)}KB</span>
                    {f.status === 'success' && <span className="text-[10px] text-[#10B981]">✓</span>}
                    {f.status === 'error' && <span className="text-[10px] text-red-400">✗</span>}
                    <button onClick={() => removeFile(f.id)} className="p-0.5 hover:text-red-500 text-gray-400">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <textarea value={taskDesc} onChange={(e) => setTaskDesc(e.target.value)}
              placeholder="描述任务..." className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg h-20 resize-none focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30" />

            <div>
              <label className="text-xs text-gray-500 mb-1 block">推理策略</label>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 bg-white">
                {STRATEGIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>

            <div>
              <label className="text-xs text-gray-500 mb-1 block">最大步数: {maxSteps}</label>
              <input type="range" min={1} max={500} value={maxSteps} onChange={e => setMaxSteps(Number(e.target.value))}
                className="w-full h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-[#6366f1]" />
            </div>

            <div>
              <label className="text-xs text-gray-500 mb-1 block">输出格式</label>
              <select value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 bg-white">
                {formats.length > 0 ? formats.map(f => (
                  <option key={f.id} value={f.id}>{f.name} ({f.ext}){!f.available ? ' [不可用]' : ''}</option>
                )) : (
                  <>
                    <option value="markdown">Markdown (.md)</option>
                    <option value="html">HTML (.html)</option>
                    <option value="docx">Word (.docx)</option>
                    <option value="xlsx">Excel (.xlsx)</option>
                  </>
                )}
              </select>
            </div>

            <Button onClick={handleCreate} disabled={creating || !taskDesc.trim()} className="w-full justify-center">
              {creating ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Play className="w-3.5 h-3.5 mr-1" />}
              {creating ? '创建中...' : '创建任务'}
            </Button>
          </div>
        </Card>

        {/* Fault Injection Panel */}
        <Card title="异常注入" icon={<Zap className="w-4 h-4 text-red-400" />}
              action={<Button variant="secondary" size="sm" onClick={() => setShowFaultPanel(!showFaultPanel)}>
                {showFaultPanel ? '收起' : '展开'}
              </Button>}>
          {!showFaultPanel ? (
            <div className="text-center py-2">
              <p className="text-xs text-gray-400">测试系统韧性和容错能力</p>
              <p className="text-[10px] text-gray-300 mt-1">支持节点失效、延迟注入、数据损坏、拓扑扰动、资源耗尽</p>
            </div>
          ) : (
            <div className="space-y-3">
              {activeTasks.length === 0 ? (
                <div className="text-center py-3">
                  <AlertTriangle className="w-5 h-5 text-yellow-400 mx-auto mb-1" />
                  <p className="text-xs text-gray-500">无运行中的任务</p>
                  <p className="text-[10px] text-gray-400">异常注入需要作用于运行中的任务</p>
                </div>
              ) : (
                <>
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">目标任务</label>
                    <select value={faultTaskId} onChange={e => setFaultTaskId(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-300 bg-white">
                      <option value="">选择任务...</option>
                      {activeTasks.map(t => (
                        <option key={t.id} value={t.id}>{t.id.slice(0,8)} — {t.description.slice(0,30)}{t.description.length > 30 ? '...' : ''}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">故障类型</label>
                    <select value={faultType} onChange={e => setFaultType(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-300 bg-white">
                      {FAULT_TYPES.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
                    </select>
                    <p className="text-[10px] text-gray-400 mt-0.5">{FAULT_TYPES.find(f => f.value === faultType)?.desc}</p>
                  </div>

                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">目标 Agent（可选）</label>
                    <select value={faultTarget} onChange={e => setFaultTarget(e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-300 bg-white">
                      <option value="">全系统</option>
                      {agents.filter(a => a.status === 'online').map(a => (
                        <option key={a.id} value={a.id}>{a.icon || '🤖'} {a.name || a.id}</option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">严重程度</label>
                      <select value={faultSeverity} onChange={e => setFaultSeverity(e.target.value)}
                        className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-300 bg-white">
                        {SEVERITY_LEVELS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">持续步数: {faultDuration}</label>
                      <input type="range" min={1} max={10} value={faultDuration} onChange={e => setFaultDuration(Number(e.target.value))}
                        className="w-full h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-red-500 mt-2" />
                    </div>
                  </div>

                  {injectResult && (
                    <div className={`p-2 rounded-lg text-xs ${injectResult.success ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'}`}>
                      {injectResult.msg}
                    </div>
                  )}

                  <Button onClick={handleInjectFault} disabled={injecting || !faultTaskId}
                    className="w-full justify-center bg-red-500 hover:bg-red-600 text-white">
                    {injecting ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Zap className="w-3.5 h-3.5 mr-1" />}
                    {injecting ? '注入中...' : '执行注入'}
                  </Button>

                  {/* Active Faults & Recovery */}
                  {faultState && faultState.disabled_agents.length > 0 && (
                    <div className="mt-3 p-2.5 rounded-lg border border-red-200 bg-red-50">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-red-700">⚠️ 已禁用 Agent ({faultState.disabled_agents.length})</span>
                        <Button onClick={handleRecoverAll} size="sm" className="bg-green-500 hover:bg-green-600 text-white !py-1 !px-2 !text-[10px]">
                          <RotateCcw className="w-3 h-3 mr-0.5" /> 全部恢复
                        </Button>
                      </div>
                      <div className="space-y-1.5">
                        {faultState.disabled_agents.map((aid: string) => {
                          const ag = agents.find((a: any) => a.id === aid)
                          const fault = faultState.faults.find((f: any) => f.target === aid && f.active)
                          return (
                            <div key={aid} className="flex items-center justify-between bg-white rounded-md px-2.5 py-1.5 border border-red-100">
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs">{ag?.icon || '🤖'}</span>
                                <span className="text-xs font-medium text-gray-700">{ag?.name || aid}</span>
                                {fault && <Badge color="red">{fault.type_label || fault.type}</Badge>}
                              </div>
                              <Button onClick={() => handleRecoverAgent(aid)} size="sm" variant="secondary" className="!py-0.5 !px-2 !text-[10px]">
                                <RotateCcw className="w-3 h-3 mr-0.5" /> 恢复
                              </Button>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )}

                  {/* Recent fault history */}
                  {faultState && faultState.faults.length > 0 && !faultState.disabled_agents.length && (
                    <div className="mt-3 p-2 rounded-lg border border-gray-200 bg-gray-50">
                      <span className="text-[10px] text-gray-500 font-medium">最近故障记录 ({faultState.faults.length})</span>
                      <div className="mt-1 space-y-0.5 max-h-20 overflow-y-auto">
                        {faultState.faults.slice(-3).map((f: any, i: number) => (
                          <div key={i} className="text-[10px] text-gray-500 flex items-center gap-1">
                            <span className={f.active ? 'text-red-500' : 'text-green-500'}>{f.active ? '●' : '○'}</span>
                            {f.type_label || f.type} → {f.target || '系统'} [{f.severity}]
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </Card>

        {/* Task List */}
        <Card title="任务列表" icon={<FileText className="w-4 h-4" />}
              action={<Badge color="indigo">{tasks.length}</Badge>} className="flex-1 overflow-hidden">
          <div className="space-y-2 overflow-y-auto max-h-48">
            {tasks.length === 0 ? <p className="text-xs text-gray-400 text-center py-4">暂无任务</p> :
              tasks.map(t => (
                <div key={t.id} className="p-2.5 rounded-lg border border-gray-100">
                  <div className="flex items-center justify-between mb-1">
                    <Badge color={statusColors[t.status] || 'gray'}>{t.status}</Badge>
                    <span className="text-[10px] text-gray-400">{t.id.slice(0, 8)}</span>
                  </div>
                  <p className="text-xs text-gray-700 line-clamp-2">{t.description}</p>
                </div>
              ))
            }
          </div>
        </Card>

        {/* Agent Status */}
        <Card title="Agent 状态" action={<Badge color="green">{agents.filter(a => a.status === 'online').length} online</Badge>}>
          <div className="space-y-1.5 max-h-36 overflow-y-auto">
            {agents.map(a => (
              <div key={a.id} className="flex items-center gap-2 p-1.5 rounded-lg">
                <span className="text-sm">{a.icon || '🤖'}</span>
                <span className="text-xs font-medium text-gray-700 flex-1">{a.name || a.id}</span>
                {a.layer && <span className="text-[10px] text-gray-400">{a.layer}</span>}
                <Badge color={a.status === 'online' ? 'green' : 'gray'}>{a.status}</Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
