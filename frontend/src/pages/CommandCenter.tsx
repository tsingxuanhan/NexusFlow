import { useState } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { agents, tasks, logs } from '@/data/mock'
import { Zap, Plus, AlertTriangle, Radio, Circle, Clock, CheckCircle, XCircle, Loader } from 'lucide-react'


const taskStatusIcons: Record<string, React.ReactNode> = {
  running: <Loader className="w-3.5 h-3.5 text-[#0EA5E9] animate-spin" />,
  queued: <Clock className="w-3.5 h-3.5 text-gray-400" />,
  completed: <CheckCircle className="w-3.5 h-3.5 text-[#10B981]" />,
  failed: <XCircle className="w-3.5 h-3.5 text-red-500" />,
}

const logLevelColors: Record<string, string> = {
  info: 'text-[#0EA5E9]',
  warn: 'text-[#F97316]',
  error: 'text-red-500',
  success: 'text-[#10B981]',
}

export function CommandCenter() {
  const [newTask, setNewTask] = useState('')

  return (
    <div className="space-y-5">
      {/* Agent Status Bar */}
      <div className="flex items-center gap-3 overflow-x-auto pb-2">
        {agents.map(a => (
          <div key={a.id} className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg border border-gray-100 shadow-sm min-w-fit">
            <Circle className={`w-2 h-2 fill-current ${a.status === 'online' ? 'text-[#10B981]' : a.status === 'busy' ? 'text-[#F97316]' : a.status === 'idle' ? 'text-gray-300' : 'text-red-400'}`} />
            <span className="text-xs font-medium text-gray-700">{a.name}</span>
            <span className="text-[10px] text-gray-400">{a.load}%</span>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Task Creation + List */}
        <div className="lg:col-span-2 space-y-5">
          <Card title="任务创建" icon={<Zap className="w-4 h-4" />}>
            <div className="flex gap-2">
              <input
                type="text"
                value={newTask}
                onChange={e => setNewTask(e.target.value)}
                placeholder="输入任务描述..."
                className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1]"
              />
              <Button><Plus className="w-4 h-4 mr-1" />提交</Button>
            </div>
          </Card>

          <Card title="任务队列" icon={<Radio className="w-4 h-4" />} action={<Badge color="indigo">{tasks.length} 任务</Badge>}>
            <div className="space-y-2">
              {tasks.map(t => (
                <div key={t.id} className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-gray-50 transition-colors">
                  <div className="flex items-center gap-3">
                    {taskStatusIcons[t.status]}
                    <div>
                      <p className="text-sm font-medium text-gray-800">{t.title}</p>
                      <p className="text-xs text-gray-400">{t.id} · {t.agent} · {t.created}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge color={t.priority === 'critical' ? 'red' : t.priority === 'high' ? 'orange' : t.priority === 'medium' ? 'sky' : 'gray'}>
                      {t.priority}
                    </Badge>
                    {t.status === 'running' && <span className="text-xs text-gray-400">{t.duration}</span>}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right Panel: Logs + Fault Injection */}
        <div className="space-y-5">
          <Card title="实时日志流" icon={<Radio className="w-4 h-4" />} action={<Badge color="green">LIVE</Badge>}>
            <div className="space-y-1.5 max-h-80 overflow-y-auto font-mono text-xs">
              {logs.map((log, i) => (
                <div key={i} className="flex gap-2 py-1 px-2 rounded hover:bg-gray-50">
                  <span className="text-gray-300 shrink-0">{log.time}</span>
                  <span className={`${logLevelColors[log.level]} shrink-0 w-12`}>[{log.level.toUpperCase()}]</span>
                  <span className="text-gray-500 shrink-0">{log.agent}:</span>
                  <span className="text-gray-700 truncate">{log.message}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="异常注入" icon={<AlertTriangle className="w-4 h-4" />}>
            <div className="space-y-2">
              {['网络延迟 +200ms', 'Agent 宕机', '内存压力 95%'].map(fault => (
                <Button key={fault} variant="secondary" size="sm" className="w-full justify-start">
                  <AlertTriangle className="w-3.5 h-3.5 mr-2 text-[#F97316]" />
                  注入: {fault}
                </Button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
