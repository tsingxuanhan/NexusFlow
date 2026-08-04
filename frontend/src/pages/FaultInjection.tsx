import { useState, useCallback } from 'react'

import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import type { TaskExecution, AgentInfo } from '@/api/client'
import { AlertTriangle, Loader, Zap, Clock, Database, GitBranch, Cpu, CheckCircle, XCircle } from 'lucide-react'

interface FaultInjectionProps {
  tasks: TaskExecution[]
  agents: AgentInfo[]
  onInject: (taskId: string, faultType: string, params: Record<string, unknown>) => void
  injecting: boolean
}

interface FaultConfig {
  value: string
  label: string
  icon: typeof Zap
  color: string
  description: string
  fields: FieldDef[]
}

interface FieldDef {
  key: string
  label: string
  type: 'select' | 'number' | 'range' | 'select-agents'
  placeholder?: string
  min?: number
  max?: number
  step?: number
  defaultValue: string | number
  options?: { value: string; label: string }[]
  unit?: string
}

const faultConfigs: FaultConfig[] = [
  {
    value: 'node_failure',
    label: '节点失效',
    icon: Zap,
    color: '#EF4444',
    description: '使指定 Agent 离线，系统触发自动恢复机制',
    fields: [
      { key: 'target_agent', label: '目标 Agent', type: 'select-agents', defaultValue: '' },
      { key: 'failure_mode', label: '失效模式', type: 'select', defaultValue: 'crash', options: [
        { value: 'crash', label: '立即崩溃' },
        { value: 'hang', label: '挂起无响应' },
        { value: 'slow_death', label: '渐进式退化' },
      ]},
      { key: 'recovery_delay_s', label: '恢复延迟', type: 'number', min: 0, max: 300, defaultValue: 30, unit: '秒' },
    ],
  },
  {
    value: 'latency_inject',
    label: '延迟注入',
    icon: Clock,
    color: '#F97316',
    description: '向指定 Agent 注入网络/计算延迟，测试超时和降级机制',
    fields: [
      { key: 'target_agent', label: '目标 Agent', type: 'select-agents', defaultValue: '' },
      { key: 'latency_ms', label: '延迟时长', type: 'range', min: 100, max: 30000, step: 100, defaultValue: 2000, unit: 'ms' },
      { key: 'jitter_ms', label: '抖动范围', type: 'range', min: 0, max: 5000, step: 100, defaultValue: 500, unit: 'ms' },
      { key: 'probability', label: '触发概率', type: 'range', min: 10, max: 100, step: 5, defaultValue: 100, unit: '%' },
    ],
  },
  {
    value: 'data_corruption',
    label: '数据损坏',
    icon: Database,
    color: '#8B5CF6',
    description: '注入数据损坏事件，触发数据校验和重新获取流程',
    fields: [
      { key: 'target_agent', label: '目标 Agent', type: 'select-agents', defaultValue: '' },
      { key: 'corruption_type', label: '损坏类型', type: 'select', defaultValue: 'truncation', options: [
        { value: 'truncation', label: '数据截断' },
        { value: 'garbage', label: '乱码注入' },
        { value: 'null_fields', label: '关键字段置空' },
        { value: 'type_mismatch', label: '类型错误' },
      ]},
      { key: 'severity', label: '严重程度', type: 'select', defaultValue: 'partial', options: [
        { value: 'partial', label: '部分损坏（可修复）' },
        { value: 'total', label: '完全损坏（不可修复）' },
      ]},
    ],
  },
  {
    value: 'topology_disrupt',
    label: '拓扑扰动',
    icon: GitBranch,
    color: '#0EA5E9',
    description: '强制切换系统拓扑结构，验证动态重构能力',
    fields: [
      { key: 'target_topology', label: '强制切换到', type: 'select', defaultValue: 'mesh', options: [
        { value: 'star', label: '星形' },
        { value: 'mesh', label: '网状' },
        { value: 'tree', label: '树形' },
        { value: 'ring', label: '环形' },
        { value: 'hybrid', label: '混合' },
      ]},
      { key: 'disrupt_timing', label: '扰动时机', type: 'select', defaultValue: 'immediate', options: [
        { value: 'immediate', label: '立即执行' },
        { value: 'next_step', label: '下一步触发' },
        { value: 'mid_execution', label: '执行中途' },
      ]},
    ],
  },
  {
    value: 'resource_exhaust',
    label: '资源耗尽',
    icon: Cpu,
    color: '#10B981',
    description: '模拟资源耗尽场景，验证资源调度和降级策略',
    fields: [
      { key: 'resource_type', label: '资源类型', type: 'select', defaultValue: 'memory', options: [
        { value: 'memory', label: '内存' },
        { value: 'cpu', label: 'CPU' },
        { value: 'disk', label: '磁盘 I/O' },
        { value: 'gpu', label: 'GPU 显存' },
        { value: 'network', label: '网络带宽' },
      ]},
      { key: 'threshold_pct', label: '耗尽阈值', type: 'range', min: 70, max: 100, step: 1, defaultValue: 95, unit: '%' },
      { key: 'ramp_up_s', label: '爬坡时间', type: 'number', min: 0, max: 120, defaultValue: 10, unit: '秒' },
      { key: 'sustain_s', label: '持续时间', type: 'number', min: 1, max: 600, defaultValue: 60, unit: '秒' },
    ],
  },
]

export function FaultInjection({ tasks, agents, onInject, injecting }: FaultInjectionProps) {
  const [selectedFault, setSelectedFault] = useState('node_failure')
  const [taskId, setTaskId] = useState('')
  const [params, setParams] = useState<Record<string, unknown>>({})
  const [injectResult, setInjectResult] = useState<{ success: boolean; message: string } | null>(null)

  const currentConfig = faultConfigs.find(f => f.value === selectedFault)!


  const handleParamChange = (key: string, value: string | number) => {
    setParams(prev => ({ ...prev, [key]: value }))
  }

  const runningTasks = tasks.filter(t => ['pending', 'running', 'planning', 'reviewing'].includes(t.status))

  const handleInject = useCallback(async () => {
    if (!taskId) return
    onInject(taskId, selectedFault, params)
    // Show a mock result for demo (real result comes from WebSocket)
    setInjectResult({ success: true, message: `已注入: ${currentConfig.label} → ${taskId}` })
    setTimeout(() => setInjectResult(null), 5000)
  }, [taskId, selectedFault, params, onInject, currentConfig])

  const renderField = (field: FieldDef) => {
    const value = (params[field.key] ?? field.defaultValue) as string | number

    switch (field.type) {
      case 'select':
        return (
          <select
            value={value as string}
            onChange={e => handleParamChange(field.key, e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
          >
            {field.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        )

      case 'select-agents':
        return (
          <select
            value={value as string}
            onChange={e => handleParamChange(field.key, e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
          >
            <option value="">选择 Agent...</option>
            {agents.map(a => (
              <option key={a.id} value={a.id}>{a.icon || ''} {a.name || a.id} ({a.state})</option>
            ))}
          </select>
        )

      case 'number':
        return (
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={value as number}
              min={field.min}
              max={field.max}
              step={field.step || 1}
              onChange={e => handleParamChange(field.key, Number(e.target.value))}
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
            />
            {field.unit && <span className="text-xs text-gray-400 shrink-0">{field.unit}</span>}
          </div>
        )

      case 'range':
        return (
          <div className="flex items-center gap-3">
            <input
              type="range"
              value={value as number}
              min={field.min}
              max={field.max}
              step={field.step || 1}
              onChange={e => handleParamChange(field.key, Number(e.target.value))}
              className="flex-1 h-1.5 bg-gray-200 rounded-full appearance-none cursor-pointer accent-[#6366f1]"
            />
            <span className="text-xs font-semibold text-[#6366f1] w-16 text-right shrink-0">
              {value as number}{field.unit ? ` ${field.unit}` : ''}
            </span>
          </div>
        )

      default:
        return null
    }
  }

  return (
    <Card
      title="异常注入"
      icon={<AlertTriangle className="w-4 h-4" />}
      action={injectResult && (
        <div className={`flex items-center gap-1 text-xs ${injectResult.success ? 'text-[#10B981]' : 'text-red-500'}`}>
          {injectResult.success ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {injectResult.message}
        </div>
      )}
    >
      <div className="space-y-4">
        {/* Target Task */}
        <div>
          <label className="text-xs text-gray-500 block mb-1">目标任务</label>
          <select
            value={taskId}
            onChange={e => setTaskId(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
          >
            <option value="">选择任务...</option>
            {runningTasks.length > 0 && (
              <optgroup label="运行中">
                {runningTasks.map(t => (
                  <option key={t.id} value={t.id}>{t.id} — {t.description.slice(0, 30)}</option>
                ))}
              </optgroup>
            )}
            <optgroup label="全部任务">
              {tasks.slice(0, 20).map(t => (
                <option key={t.id} value={t.id}>{t.id} — {t.description.slice(0, 30)}</option>
              ))}
            </optgroup>
          </select>
        </div>

        {/* Fault Type Selector (cards) */}
        <div>
          <label className="text-xs text-gray-500 block mb-2">故障类型</label>
          <div className="grid grid-cols-1 gap-1.5">
            {faultConfigs.map(fc => {
              const Icon = fc.icon
              const isActive = selectedFault === fc.value
              return (
                <button
                  key={fc.value}
                  onClick={() => { setSelectedFault(fc.value); setParams({}); setInjectResult(null) }}
                  className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all border ${
                    isActive
                      ? 'border-current bg-opacity-5 shadow-sm'
                      : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                  }`}
                  style={isActive ? { borderColor: fc.color, backgroundColor: `${fc.color}08` } : {}}
                >
                  <Icon className="w-4 h-4 shrink-0" style={{ color: isActive ? fc.color : undefined }} />
                  <div className="flex-1 min-w-0">
                    <span className={`text-xs font-medium ${isActive ? '' : 'text-gray-700'}`} style={isActive ? { color: fc.color } : {}}>
                      {fc.label}
                    </span>
                  </div>
                  {isActive && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: fc.color }} />}
                </button>
              )
            })}
          </div>
        </div>

        {/* Dynamic Parameters */}
        <div className="p-3 rounded-lg bg-gray-50 border border-gray-100 space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <currentConfig.icon className="w-3.5 h-3.5" style={{ color: currentConfig.color }} />
            <span className="text-xs font-semibold" style={{ color: currentConfig.color }}>{currentConfig.label}</span>
            <span className="text-[10px] text-gray-400">— {currentConfig.description}</span>
          </div>
          {currentConfig.fields.map(field => (
            <div key={field.key}>
              <label className="text-xs text-gray-500 block mb-1">{field.label}</label>
              {renderField(field)}
            </div>
          ))}
        </div>

        {/* Inject Button */}
        <Button
          variant="danger"
          size="sm"
          onClick={handleInject}
          disabled={injecting || !taskId}
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
  )
}
