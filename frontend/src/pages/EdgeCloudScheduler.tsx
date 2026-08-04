import { useState } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { schedulerTiers, migrationHistory, agents } from '@/data/mock'
import { Server, Monitor, Smartphone, ArrowRightLeft, Zap, Activity } from 'lucide-react'

const tierIcons: Record<string, React.ReactNode> = { Cloud: <Server className="w-5 h-5" />, Edge: <Monitor className="w-5 h-5" />, Device: <Smartphone className="w-5 h-5" /> }
const strategies = ['balanced', 'latency-first', 'throughput-max', 'cost-optimal']

export function EdgeCloudScheduler() {
  const [activeStrategy, setActiveStrategy] = useState('balanced')
  const tierAgents = (tier: string) => agents.filter(a => a.tier === tier.toLowerCase())

  return (
    <div className="space-y-5">
      {/* Three-Tier Topology */}
      <Card title="三层资源拓扑" icon={<Activity className="w-4 h-4" />}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {schedulerTiers.map(tier => (
            <div key={tier.name} className="relative">
              <div className="p-4 rounded-xl border-2 border-dashed border-gray-200 bg-gray-50/50">
                <div className="flex items-center gap-2 mb-3">
                  <span style={{ color: tier.color }}>{tierIcons[tier.name]}</span>
                  <span className="text-sm font-semibold" style={{ color: tier.color }}>{tier.name}</span>
                  <Badge color="gray">{tier.count} nodes</Badge>
                </div>

                {/* Nodes */}
                <div className="space-y-2">
                  {tierAgents(tier.name).map(a => (
                    <div key={a.id} className="flex items-center justify-between p-2.5 bg-white rounded-lg border border-gray-100">
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${a.status === 'online' ? 'bg-[#10B981]' : a.status === 'busy' ? 'bg-[#F97316]' : a.status === 'idle' ? 'bg-gray-300' : 'bg-red-400'}`} />
                        <span className="text-xs font-medium text-gray-700">{a.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 bg-gray-100 rounded-full">
                          <div className="h-full rounded-full" style={{ width: `${a.load}%`, backgroundColor: a.load > 80 ? '#F97316' : a.load > 60 ? '#0EA5E9' : '#10B981' }} />
                        </div>
                        <span className="text-[10px] text-gray-400 w-7 text-right">{a.load}%</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Summary */}
                <div className="mt-3 pt-3 border-t border-gray-200 flex justify-between text-xs text-gray-500">
                  <span>平均负载 {tier.avgLoad}%</span>
                  <span>{tier.tasks} 任务</span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Migration Flow Arrows */}
        <div className="flex items-center justify-center gap-2 mt-4 text-gray-300">
          <ArrowRightLeft className="w-4 h-4" />
          <span className="text-xs">自动跨层迁移</span>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Scheduling Strategy */}
        <Card title="调度策略" icon={<Zap className="w-4 h-4" />}>
          <div className="grid grid-cols-2 gap-2">
            {strategies.map(s => (
              <button
                key={s}
                onClick={() => setActiveStrategy(s)}
                className={`p-3 rounded-lg text-xs font-medium text-left transition-all border ${
                  activeStrategy === s
                    ? 'bg-[#6366f1] text-white border-[#6366f1] shadow-md shadow-indigo-200'
                    : 'bg-white text-gray-600 border-gray-100 hover:border-[#6366f1]/30'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-3">当前策略: <span className="text-[#6366f1] font-medium">{activeStrategy}</span></p>
        </Card>

        {/* Migration History */}
        <Card title="迁移记录" icon={<ArrowRightLeft className="w-4 h-4" />}>
          <div className="space-y-2">
            {migrationHistory.map((m, i) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                <div className="flex items-center gap-2">
                  <Badge color={m.status === 'success' ? 'green' : 'red'}>{m.status}</Badge>
                  <span className="text-xs font-mono text-gray-500">{m.task}</span>
                </div>
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-gray-500">{m.from}</span>
                  <ArrowRightLeft className="w-3 h-3 text-[#6366f1]" />
                  <span className="text-gray-500">{m.to}</span>
                  <span className="text-gray-300 ml-1">{m.time}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
