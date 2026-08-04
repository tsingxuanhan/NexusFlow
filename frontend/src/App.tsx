import { useState } from 'react'
import { CommandCenter } from '@/pages/CommandCenter'
import { CognitionEngine } from '@/pages/CognitionEngine'
import { EdgeCloudScheduler } from '@/pages/EdgeCloudScheduler'
import { TopologyRouter } from '@/pages/TopologyRouter'
import { LayoutDashboard, Brain, Server, Network, ChevronRight } from 'lucide-react'

const pages = [
  { id: 'command', label: '指挥中心', icon: LayoutDashboard, component: CommandCenter },
  { id: 'cognition', label: '认知引擎', icon: Brain, component: CognitionEngine },
  { id: 'scheduler', label: '端边云调度', icon: Server, component: EdgeCloudScheduler },
  { id: 'topology', label: '拓扑路由', icon: Network, component: TopologyRouter },
]

const pageColors = ['text-[#6366f1]', 'text-[#F97316]', 'text-[#0EA5E9]', 'text-[#10B981]']

export default function App() {
  const [active, setActive] = useState('command')
  const ActivePage = pages.find(p => p.id === active)?.component || CommandCenter

  return (
    <div className="flex min-h-screen bg-[#F8FAFC]">
      {/* Sidebar */}
      <nav className="w-14 bg-[#1E1B4B] flex flex-col items-center py-4 gap-1 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#6366f1] to-[#0EA5E9] flex items-center justify-center mb-6">
          <span className="text-white text-xs font-bold">NF</span>
        </div>
        {pages.map((page, i) => {
          const Icon = page.icon
          const isActive = active === page.id
          return (
            <button
              key={page.id}
              onClick={() => setActive(page.id)}
              className={`w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200 group relative ${
                isActive ? 'bg-white/15 shadow-lg' : 'hover:bg-white/8'
              }`}
              title={page.label}
            >
              <Icon className={`w-4.5 h-4.5 ${isActive ? pageColors[i] : 'text-gray-400 group-hover:text-gray-200'} transition-colors`} />
              {isActive && <div className={`absolute left-0 w-0.5 h-5 rounded-r ${pageColors[i].replace('text-', 'bg-')}`} />}
            </button>
          )
        })}
      </nav>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-sm border-b border-gray-100 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {(() => { const p = pages.find(p => p.id === active)!; const i = pages.findIndex(p => p.id === active); const Icon = p.icon; return <><Icon className={`w-4 h-4 ${pageColors[i]}`} /></> })()}
            <h1 className="text-sm font-semibold text-gray-800">{pages.find(p => p.id === active)?.label}</h1>
            <ChevronRight className="w-3 h-3 text-gray-300" />
            <span className="text-xs text-gray-400">NexusFlow Dashboard</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#10B981]/10 rounded-full">
              <div className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
              <span className="text-[10px] font-medium text-[#10B981]">System Online</span>
            </div>
            <span className="text-xs text-gray-400">v3.6</span>
          </div>
        </header>
        <div className="p-6">
          <ActivePage />
        </div>
      </main>
    </div>
  )
}
