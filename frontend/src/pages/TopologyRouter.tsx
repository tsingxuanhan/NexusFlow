import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Network, Route, BarChart3 } from 'lucide-react'

const routeHistory = [
  { id: 1, topology: 'star', agents: ['Orchestrator', 'Executor-α', 'Executor-β'], success: true, latency: '12ms' },
  { id: 2, topology: 'mesh', agents: ['Coordinator', 'Executor-α', 'Executor-δ'], success: true, latency: '18ms' },
  { id: 3, topology: 'star', agents: ['Orchestrator', 'Executor-γ'], success: false, latency: 'timeout' },
  { id: 4, topology: 'tree', agents: ['Coordinator', 'Executor-β', 'Executor-δ'], success: true, latency: '8ms' },
  { id: 5, topology: 'ring', agents: ['Orchestrator', 'Coordinator', 'Executor-α', 'Executor-β'], success: true, latency: '22ms' },
  { id: 6, topology: 'star', agents: ['Orchestrator', 'Executor-δ'], success: true, latency: '6ms' },
]

const successRates = [
  { topology: 'star', rate: 0.94, count: 142 },
  { topology: 'mesh', rate: 0.87, count: 89 },
  { topology: 'tree', rate: 0.91, count: 67 },
  { topology: 'ring', rate: 0.78, count: 34 },
  { topology: 'hybrid', rate: 0.83, count: 52 },
]

// SVG positions for star topology
const currentTopo = {
  nodes: [
    { x: 200, y: 100, label: 'Orchestrator', color: '#6366f1', r: 24 },
    { x: 100, y: 50, label: 'α', color: '#0EA5E9', r: 16 },
    { x: 300, y: 50, label: 'β', color: '#F97316', r: 16 },
    { x: 80, y: 160, label: 'γ', color: '#10B981', r: 16 },
    { x: 320, y: 160, label: 'δ', color: '#0EA5E9', r: 16 },
  ],
  edges: [[0,1],[0,2],[0,3],[0,4]] as [number, number][],
}

export function TopologyRouter() {
  return (
    <div className="space-y-5">
      {/* Topology SVG Visualization */}
      <Card title="动态拓扑可视化" icon={<Network className="w-4 h-4" />} action={<Badge color="green">star · fitness 0.94</Badge>}>
        <div className="flex justify-center py-4">
          <svg width="400" height="210" viewBox="0 0 400 210" className="overflow-visible">
            {/* Edges */}
            {currentTopo.edges.map(([a, b], i) => (
              <line key={i}
                x1={currentTopo.nodes[a].x} y1={currentTopo.nodes[a].y}
                x2={currentTopo.nodes[b].x} y2={currentTopo.nodes[b].y}
                stroke="#E5E7EB" strokeWidth="2" strokeDasharray="4 2"
              />
            ))}
            {/* Animated data flow dots */}
            {currentTopo.edges.map((_, i) => (
              <circle key={`dot-${i}`} r="3" fill="#6366f1">
                <animateMotion dur={`${2 + i * 0.5}s`} repeatCount="indefinite">
                  <mpath xlinkHref={`#path-${i}`} />
                </animateMotion>
              </circle>
            ))}
            {/* Hidden paths for animation */}
            {currentTopo.edges.map(([a, b], i) => (
              <path key={`path-${i}`} id={`path-${i}`}
                d={`M${currentTopo.nodes[a].x},${currentTopo.nodes[a].y} L${currentTopo.nodes[b].x},${currentTopo.nodes[b].y}`}
                fill="none" stroke="none"
              />
            ))}
            {/* Nodes */}
            {currentTopo.nodes.map((n, i) => (
              <g key={i}>
                <circle cx={n.x} cy={n.y} r={n.r} fill={n.color} opacity="0.15" />
                <circle cx={n.x} cy={n.y} r={n.r - 4} fill={n.color} />
                <text x={n.x} y={n.y + n.r + 14} textAnchor="middle" className="text-[10px] fill-gray-500" fontFamily="system-ui">
                  {n.label}
                </text>
              </g>
            ))}
          </svg>
        </div>
        <div className="flex justify-center gap-4 mt-2">
          {['star', 'mesh', 'tree', 'ring', 'hybrid'].map(t => (
            <button key={t} className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${t === 'star' ? 'bg-[#6366f1] text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'}`}>
              {t}
            </button>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Route Decision History */}
        <Card title="路由决策历史" icon={<Route className="w-4 h-4" />}>
          <div className="space-y-2">
            {routeHistory.map(r => (
              <div key={r.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                <div className="flex items-center gap-2">
                  <Badge color={r.success ? 'green' : 'red'}>{r.success ? '✓' : '✗'}</Badge>
                  <Badge color="indigo">{r.topology}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex -space-x-1">
                    {r.agents.slice(0, 3).map((ag, i) => (
                      <span key={i} className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-100 border border-white text-[8px] font-medium text-gray-600">
                        {ag[0]}
                      </span>
                    ))}
                  </div>
                  <span className="text-xs text-gray-400">{r.latency}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Success Rate Bar Chart */}
        <Card title="拓扑成功率" icon={<BarChart3 className="w-4 h-4" />}>
          <div className="space-y-3">
            {successRates.map(s => (
              <div key={s.topology} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-12">{s.topology}</span>
                <div className="flex-1 h-7 bg-gray-100 rounded-md overflow-hidden relative">
                  <div
                    className="h-full rounded-md transition-all flex items-center justify-end pr-2"
                    style={{
                      width: `${s.rate * 100}%`,
                      background: s.rate > 0.9 ? 'linear-gradient(90deg, #6366f1, #0EA5E9)' : s.rate > 0.8 ? 'linear-gradient(90deg, #0EA5E9, #10B981)' : 'linear-gradient(90deg, #F97316, #F59E0B)',
                    }}
                  >
                    <span className="text-[10px] font-semibold text-white">{(s.rate * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <span className="text-[10px] text-gray-400 w-12 text-right">{s.count} runs</span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
