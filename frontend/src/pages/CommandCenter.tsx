import { useState, useEffect, useRef, useCallback } from 'react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { api } from '@/api/client'
import type { AgentInfo, TaskExecution, WSEvent, UploadResponse } from '@/api/client'
import {
  Zap, Plus, AlertTriangle, Radio, Circle, Clock,
  CheckCircle, XCircle, Loader, Upload, File as FileIcon,
  Trash2, Wifi, WifiOff,
} from 'lucide-react'

// --- Types ---

interface UploadedFile {
  id: string
  file: File
  name: string
  size: number
  status: 'uploading' | 'success' | 'error'
  error?: string
  response?: UploadResponse
  taskId?: string
}

interface LogEntry {
  time: string
  level: string
  source: string
  message: string
}

// --- Helpers ---

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

const tierColors: Record<string, string> = {
  global: 'text-[#6366f1]',
  cloud: 'text-[#0EA5E9]',
  edge: 'text-[#10B981]',
  device: 'text-[#F97316]',
}

const stateDotColors: Record<string, string> = {
  idle: 'text-gray-300',
  running: 'text-[#0EA5E9]',
  busy: 'text-[#F97316]',
  offline: 'text-red-400',
}

const taskStatusIcons: Record<string, ReactNode> = {
  running: <Loader className="w-3.5 h-3.5 text-[#0EA5E9] animate-spin" />,
  in_progress: <Loader className="w-3.5 h-3.5 text-[#0EA5E9] animate-spin" />,
  queued: <Clock className="w-3.5 h-3.5 text-gray-400" />,
  pending: <Clock className="w-3.5 h-3.5 text-gray-400" />,
  completed: <CheckCircle className="w-3.5 h-3.5 text-[#10B981]" />,
  failed: <XCircle className="w-3.5 h-3.5 text-red-500" />,
}

const taskStatusBadgeColors: Record<string, 'indigo' | 'green' | 'orange' | 'sky' | 'gray' | 'red'> = {
  running: 'sky',
  in_progress: 'sky',
  queued: 'gray',
  pending: 'gray',
  completed: 'green',
  failed: 'red',
}

const logLevelColors: Record<string, string> = {
  info: 'text-[#0EA5E9]',
  warn: 'text-[#F97316]',
  error: 'text-red-500',
  success: 'text-[#10B981]',
  debug: 'text-gray-400',
}

const faultTypes = [
  { value: 'network_latency', label: '网络延迟 +200ms' },
  { value: 'agent_crash', label: 'Agent 宕机' },
  { value: 'memory_pressure', label: '内存压力 95%' },
  { value: 'disk_full', label: '磁盘满载' },
  { value: 'cpu_spike', label: 'CPU 飙升' },
]

const strategies = [
  { value: 'auto', label: 'Auto (自动)' },
  { value: 'cdol', label: 'CDOL' },
  { value: 'simple', label: 'Simple' },
  { value: 'parallel', label: 'Parallel' },
]

// --- Component ---

export function CommandCenter() {
  // State
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [tasks, setTasks] = useState<TaskExecution[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([])
  const [newTask, setNewTask] = useState('')
  const [maxSteps, setMaxSteps] = useState(5)
  const [strategy, setStrategy] = useState('auto')
  const [selectedFileIds, setSelectedFileIds] = useState<Set<string>>(new Set())
  const [faultTaskId, setFaultTaskId] = useState('')
  const [faultType, setFaultType] = useState('network_latency')
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'error'>('connecting')
  const [dragOver, setDragOver] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [injecting, setInjecting] = useState(false)

  // Refs
  const logContainerRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetch functions
  const fetchAgents = useCallback(async () => {
    try {
      const data = await api.getAgents()
      setAgents(data.agents || [])
      setConnectionStatus('connected')
    } catch {
      setConnectionStatus(prev => prev === 'connecting' ? 'error' : prev)
    }
  }, [])

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api.getTasks()
      setTasks(data.tasks || [])
    } catch {
      // silent fail
    }
  }, [])

  // Initial fetch + polling
  useEffect(() => {
    fetchAgents()
    fetchTasks()
    const interval = setInterval(() => {
      fetchAgents()
      fetchTasks()
    }, 10000)
    return () => clearInterval(interval)
  }, [fetchAgents, fetchTasks])

  // WebSocket
  useEffect(() => {
    const ws = api.connectEvents((msg: WSEvent) => {
      const time = formatTime(new Date())

      switch (msg.type) {
        case 'log': {
          const d = msg.data as { level?: string; agent?: string; message?: string }
          setLogs(prev => [...prev.slice(-199), {
            time,
            level: d?.level || 'info',
            source: d?.agent || 'system',
            message: d?.message || String(msg.data),
          }])
          break
        }
        case 'task_created':
        case 'task_started':
        case 'task_completed':
        case 'task_failed': {
          const d = msg.data as { description?: string; task_id?: string; error?: string }
          setLogs(prev => [...prev.slice(-199), {
            time,
            level: msg.type === 'task_failed' ? 'error' : msg.type === 'task_completed' ? 'success' : 'info',
            source: 'system',
            message: `${msg.type.replace('task_', 'Task ')}: ${d?.description || d?.task_id || ''}${d?.error ? ' — ' + d.error : ''}`,
          }])
          fetchTasks()
          break
        }
        case 'agent_state_change': {
          fetchAgents()
          break
        }
        default: {
          setLogs(prev => [...prev.slice(-199), {
            time,
            level: 'info',
            source: 'system',
            message: `${msg.type}: ${JSON.stringify(msg.data)}`,
          }])
        }
      }
    })
    return () => { ws.close() }
  }, [fetchAgents, fetchTasks])

  // Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs])

  // File upload
  const handleFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return
    const fileArray = Array.from(files)
    const newFiles: UploadedFile[] = fileArray.map(file => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      file,
      name: file.name,
      size: file.size,
      status: 'uploading' as const,
    }))
    setUploadedFiles(prev => [...prev, ...newFiles])

    await Promise.all(newFiles.map(async (uf) => {
      try {
        const response = await api.uploadFile(uf.file)
        setUploadedFiles(prev => prev.map(f =>
          f.id === uf.id ? { ...f, status: 'success' as const, response } : f
        ))
      } catch (err) {
        setUploadedFiles(prev => prev.map(f =>
          f.id === uf.id
            ? { ...f, status: 'error' as const, error: err instanceof Error ? err.message : 'Upload failed' }
            : f
        ))
      }
    }))
  }, [])

  // Remove file
  const removeFile = useCallback((fileId: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== fileId))
    setSelectedFileIds(prev => {
      const next = new Set(prev)
      next.delete(fileId)
      return next
    })
  }, [])

  // Toggle file selection
  const toggleFileSelection = useCallback((fileId: string) => {
    setSelectedFileIds(prev => {
      const next = new Set(prev)
      if (next.has(fileId)) next.delete(fileId)
      else next.add(fileId)
      return next
    })
  }, [])

  // Submit task
  const handleSubmitTask = useCallback(async () => {
    if (!newTask.trim()) return
    setSubmitting(true)
    try {
      const result = await api.createTask(newTask.trim(), maxSteps, strategy)

      // Re-upload selected files with the new task_id
      const selectedFiles = uploadedFiles.filter(f => selectedFileIds.has(f.id) && f.status === 'success')
      if (selectedFiles.length > 0) {
        await Promise.all(selectedFiles.map(async (uf) => {
          try {
            await api.uploadFile(uf.file, result.task_id)
            setUploadedFiles(prev => prev.map(f =>
              f.id === uf.id ? { ...f, taskId: result.task_id } : f
            ))
          } catch {
            // Ignore re-upload errors
          }
        }))
      }

      setLogs(prev => [...prev.slice(-199), {
        time: formatTime(new Date()),
        level: 'success',
        source: 'system',
        message: `任务已创建: ${result.task_id} — ${newTask.trim()} (步数: ${maxSteps}, 策略: ${strategy})`,
      }])

      setNewTask('')
      setSelectedFileIds(new Set())
      fetchTasks()
    } catch (err) {
      setLogs(prev => [...prev.slice(-199), {
        time: formatTime(new Date()),
        level: 'error',
        source: 'system',
        message: `任务创建失败: ${err instanceof Error ? err.message : '未知错误'}`,
      }])
    } finally {
      setSubmitting(false)
    }
  }, [newTask, maxSteps, strategy, uploadedFiles, selectedFileIds, fetchTasks])

  // Inject fault
  const handleInjectFault = useCallback(async () => {
    if (!faultTaskId) return
    setInjecting(true)
    try {
      await api.injectFault(faultTaskId, faultType)
      setLogs(prev => [...prev.slice(-199), {
        time: formatTime(new Date()),
        level: 'warn',
        source: 'system',
        message: `异常已注入: ${faultType} → 任务 ${faultTaskId}`,
      }])
    } catch (err) {
      setLogs(prev => [...prev.slice(-199), {
        time: formatTime(new Date()),
        level: 'error',
        source: 'system',
        message: `异常注入失败: ${err instanceof Error ? err.message : '未知错误'}`,
      }])
    } finally {
      setInjecting(false)
    }
  }, [faultTaskId, faultType])

  // Render
  return (
    <div className="space-y-5">
      {/* Agent Status Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {agents.length === 0 ? (
          <div className="flex items-center gap-1.5 px-3 py-2 text-xs text-gray-400">
            {connectionStatus === 'error' ? (
              <><WifiOff className="w-3.5 h-3.5" /> 后端连接失败，重试中...</>
            ) : (
              <><Wifi className="w-3.5 h-3.5 animate-pulse" /> 连接中...</>
            )}
          </div>
        ) : (
          agents.map(a => (
            <div key={a.id} className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg border border-gray-100 shadow-sm min-w-fit">
              <Circle className={`w-2 h-2 fill-current ${stateDotColors[a.state] || 'text-gray-300'}`} />
              <span className="text-xs font-medium text-gray-700">{a.label || a.name}</span>
              <span className={`text-[10px] ${tierColors[a.tier] || 'text-gray-400'}`}>{a.tier}</span>
              <span className="text-[10px] text-gray-400">{a.state}</span>
            </div>
          ))
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left Column: Task Creation + Task Queue */}
        <div className="lg:col-span-2 space-y-5">
          <Card title="任务创建" icon={<Zap className="w-4 h-4" />}>
            <div className="space-y-3">
              {/* File Upload Area */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={(e) => { e.preventDefault(); setDragOver(false) }}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-colors ${
                  dragOver ? 'border-[#6366f1] bg-[#6366f1]/5' : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <Upload className={`w-6 h-6 mx-auto mb-2 ${dragOver ? 'text-[#6366f1]' : 'text-gray-400'}`} />
                <p className="text-sm text-gray-500">拖拽文件到此处或点击上传</p>
                <p className="text-xs text-gray-400 mt-0.5">支持多文件上传，可在提交时关联到任务</p>
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => { handleFiles(e.target.files); e.target.value = '' }}
                />
              </div>

              {/* Uploaded Files List */}
              {uploadedFiles.length > 0 && (
                <div className="space-y-1.5">
                  {uploadedFiles.map(uf => (
                    <div key={uf.id} className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg">
                      <input
                        type="checkbox"
                        checked={selectedFileIds.has(uf.id)}
                        onChange={() => toggleFileSelection(uf.id)}
                        disabled={uf.status !== 'success'}
                        className="w-3.5 h-3.5 accent-[#6366f1] cursor-pointer"
                      />
                      <FileIcon className="w-3.5 h-3.5 text-gray-400 shrink-0" />
                      <span className="text-xs text-gray-700 truncate flex-1">{uf.name}</span>
                      {uf.taskId && <Badge color="indigo">已关联</Badge>}
                      <span className="text-[10px] text-gray-400 shrink-0">{formatFileSize(uf.size)}</span>
                      {uf.status === 'uploading' && <Loader className="w-3 h-3 text-[#0EA5E9] animate-spin shrink-0" />}
                      {uf.status === 'success' && <CheckCircle className="w-3 h-3 text-[#10B981] shrink-0" />}
                      {uf.status === 'error' && <span className="text-[10px] text-red-500 shrink-0">失败</span>}
                      <button onClick={() => removeFile(uf.id)} className="text-gray-400 hover:text-red-500 shrink-0">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Task Description Input */}
              <input
                type="text"
                value={newTask}
                onChange={(e) => setNewTask(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !submitting) handleSubmitTask() }}
                placeholder="输入任务描述..."
                className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
              />

              {/* Steps Slider + Strategy Dropdown */}
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs text-gray-500">最大步数</label>
                    <span className="text-xs font-semibold text-[#6366f1]">{maxSteps}</span>
                  </div>
                  <input
                    type="range"
                    min={1}
                    max={100}
                    value={maxSteps}
                    onChange={(e) => setMaxSteps(Number(e.target.value))}
                    className="w-full accent-[#6366f1] cursor-pointer"
                  />
                </div>
                <div className="w-40">
                  <label className="text-xs text-gray-500 block mb-1">策略</label>
                  <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value)}
                    className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] bg-white"
                  >
                    {strategies.map(s => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Submit Button */}
              <Button onClick={handleSubmitTask} disabled={submitting || !newTask.trim()} className="w-full">
                {submitting ? (
                  <><Loader className="w-4 h-4 mr-1 animate-spin" /> 创建中...</>
                ) : (
                  <><Plus className="w-4 h-4 mr-1" /> 提交任务</>
                )}
              </Button>
            </div>
          </Card>

          {/* Task Queue */}
          <Card title="任务队列" icon={<Radio className="w-4 h-4" />} action={<Badge color="indigo">{tasks.length} 任务</Badge>}>
            <div className="space-y-2">
              {tasks.length === 0 ? (
                <div className="text-center py-6 text-xs text-gray-400">
                  {connectionStatus === 'error' ? '后端连接失败' : '暂无任务'}
                </div>
              ) : (
                tasks.map(t => {
                  const progress = t.total_steps ? Math.round(((t.current_step || 0) / t.total_steps) * 100) : 0
                  return (
                    <div key={t.id} className="py-2.5 px-3 rounded-lg hover:bg-gray-50 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3 min-w-0">
                          {taskStatusIcons[t.status] || <Circle className="w-3.5 h-3.5 text-gray-300" />}
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-gray-800 truncate">{t.description}</p>
                            <p className="text-xs text-gray-400">
                              {t.id} · {t.max_steps}步
                              {t.duration_seconds ? ` · ${t.duration_seconds}s` : ''}
                              {t.created_at ? ` · ${t.created_at}` : ''}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Badge color={taskStatusBadgeColors[t.status] || 'gray'}>
                            {t.status}
                          </Badge>
                        </div>
                      </div>
                      {(t.status === 'running' || t.status === 'in_progress') && (
                        <div className="mt-2 h-1 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-[#0EA5E9] rounded-full transition-all"
                            style={{ width: `${progress}%` }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          </Card>
        </div>

        {/* Right Column: Logs + Fault Injection */}
        <div className="space-y-5">
          <Card title="实时日志流" icon={<Radio className="w-4 h-4" />} action={<Badge color="green">LIVE</Badge>}>
            <div ref={logContainerRef} className="space-y-1 max-h-80 overflow-y-auto font-mono text-xs">
              {logs.length === 0 ? (
                <div className="text-center py-6 text-gray-400">等待日志...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex gap-2 py-1 px-2 rounded hover:bg-gray-50">
                    <span className="text-gray-300 shrink-0">{log.time}</span>
                    <span className={`${logLevelColors[log.level] || 'text-gray-500'} shrink-0 w-14`}>
                      [{log.level.toUpperCase()}]
                    </span>
                    <span className="text-gray-500 shrink-0">{log.source}:</span>
                    <span className="text-gray-700 break-all">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card title="异常注入" icon={<AlertTriangle className="w-4 h-4" />}>
            <div className="space-y-3">
              <div>
                <label className="text-xs text-gray-500 block mb-1">目标任务</label>
                <select
                  value={faultTaskId}
                  onChange={(e) => setFaultTaskId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] bg-white"
                >
                  <option value="">选择任务...</option>
                  {tasks.map(t => (
                    <option key={t.id} value={t.id}>{t.id} — {t.description}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-1">注入类型</label>
                <select
                  value={faultType}
                  onChange={(e) => setFaultType(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] bg-white"
                >
                  {faultTypes.map(f => (
                    <option key={f.value} value={f.value}>{f.label}</option>
                  ))}
                </select>
              </div>
              <Button
                variant="danger"
                size="sm"
                onClick={handleInjectFault}
                disabled={injecting || !faultTaskId}
                className="w-full"
              >
                {injecting ? (
                  <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 注入中...</>
                ) : (
                  <><AlertTriangle className="w-3.5 h-3.5 mr-1" /> 执行注入</>
                )}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
