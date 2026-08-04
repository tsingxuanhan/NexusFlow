import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { memoryStats, metaCognition, sleeptimeLogs, crossDomainMappings, learningCurve } from '@/data/mock'
import { Brain, Database, Layers, TrendingUp, Moon, GitBranch, Sparkles } from 'lucide-react'

const typeColors = { core: 'indigo' as const, episodic: 'orange' as const, semantic: 'sky' as const }

export function CognitionEngine() {
  const maxAccuracy = Math.max(...learningCurve.map(d => d.accuracy))

  return (
    <div className="space-y-5">
      {/* Meta Cognition Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card title="置信度" icon={<Brain className="w-4 h-4" />}>
          <div className="flex items-center gap-4">
            <div className="relative w-20 h-20">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="34" fill="none" stroke="#E5E7EB" strokeWidth="6" />
                <circle cx="40" cy="40" r="34" fill="none" stroke="#6366f1" strokeWidth="6"
                  strokeDasharray={`${metaCognition.confidence * 213.6} 213.6`} strokeLinecap="round" />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-lg font-bold text-[#6366f1]">
                {Math.round(metaCognition.confidence * 100)}%
              </span>
            </div>
            <div>
              <p className="text-xs text-gray-400 mb-1">认知盲区</p>
              {metaCognition.gaps.map(g => (
                <Badge key={g} color="orange">{g}</Badge>
              ))}
            </div>
          </div>
        </Card>

        <Card title="自我改进" icon={<Sparkles className="w-4 h-4" />} className="md:col-span-2">
          <div className="space-y-3">
            {metaCognition.selfImprovements.map(s => (
              <div key={s.area} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-32 shrink-0">{s.area}</span>
                <div className="flex-1 h-6 bg-gray-100 rounded-full overflow-hidden relative">
                  <div className="absolute h-full bg-gray-200 rounded-full" style={{ width: `${s.before * 100}%` }} />
                  <div className="absolute h-full bg-gradient-to-r from-[#6366f1] to-[#0EA5E9] rounded-full transition-all" style={{ width: `${s.after * 100}%` }} />
                </div>
                <span className="text-xs font-semibold text-[#10B981] w-12 text-right">{s.delta}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Three-Layer Memory */}
      <Card title="三层记忆架构" icon={<Layers className="w-4 h-4" />}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(['core', 'episodic', 'semantic'] as const).map(layer => (
            <div key={layer} className="space-y-2">
              <div className="flex items-center gap-2 mb-3">
                <Database className="w-3.5 h-3.5 text-[#6366f1]" />
                <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">{layer}</span>
                <Badge color={typeColors[layer]}>{memoryStats[layer].length}</Badge>
              </div>
              {memoryStats[layer].map(item => (
                <div key={item.key} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <p className="text-xs font-mono text-[#6366f1] mb-1">{item.key}</p>
                  <p className="text-xs text-gray-600">{item.value}</p>
                  <div className="mt-2 flex items-center gap-1">
                    <div className="flex-1 h-1 bg-gray-200 rounded-full">
                      <div className="h-full bg-[#10B981] rounded-full" style={{ width: `${item.confidence * 100}%` }} />
                    </div>
                    <span className="text-[10px] text-gray-400">{(item.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Sleeptime Dream Logs */}
        <Card title="梦境整合日志" icon={<Moon className="w-4 h-4" />}>
          <div className="space-y-2">
            {sleeptimeLogs.map(log => (
              <div key={log.cycle} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-gray-400">#{log.cycle}</span>
                  <div className="flex gap-1">
                    <Badge color="green">{log.consolidated} 整合</Badge>
                    <Badge color="orange">{log.pruned} 剪枝</Badge>
                  </div>
                </div>
                <span className="text-xs text-gray-400">{log.duration}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Cross-Domain Transfer */}
        <Card title="跨域知识迁移" icon={<GitBranch className="w-4 h-4" />}>
          <div className="space-y-3">
            {crossDomainMappings.map((m, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center gap-2 text-xs mb-2">
                  <span className="font-mono text-[#6366f1]">{m.source}</span>
                  <span className="text-gray-300">→</span>
                  <span className="font-mono text-[#0EA5E9]">{m.target}</span>
                  <Badge color={m.status === 'applied' ? 'green' : 'orange'}>{m.status}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-gray-200 rounded-full">
                    <div className="h-full bg-[#F97316] rounded-full" style={{ width: `${m.confidence * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-gray-400">{(m.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Learning Curve */}
      <Card title="持续学习曲线" icon={<TrendingUp className="w-4 h-4" />}>
        <div className="h-48 flex items-end gap-3 px-4">
          {learningCurve.map((d, i) => (
            <div key={i} className="flex-1 flex flex-col items-center gap-1">
              <span className="text-[10px] text-gray-400">{(d.accuracy * 100).toFixed(0)}%</span>
              <div
                className="w-full rounded-t-md bg-gradient-to-t from-[#6366f1] to-[#0EA5E9] transition-all"
                style={{ height: `${(d.accuracy / maxAccuracy) * 140}px` }}
              />
              <span className="text-[10px] text-gray-400">E{d.epoch}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}
