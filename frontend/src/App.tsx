import { useState, useEffect, useCallback } from 'react'
import { CommandCenter } from '@/pages/CommandCenter'
import { CognitionEngine } from '@/pages/CognitionEngine'
import { EdgeCloudScheduler } from '@/pages/EdgeCloudScheduler'
import { TopologyRouter } from '@/pages/TopologyRouter'
import { MCPServers } from '@/pages/MCPServers'
import { Settings } from '@/pages/Settings'
import { api } from '@/api/client'
import type { SystemStatus } from '@/api/client'
import { LayoutDashboard, Brain, Server, Network, Settings as SettingsIcon, Plug, ChevronRight, Activity, CheckCircle } from 'lucide-react'

const pages = [
  { id: 'command', label: '指挥中心', icon: LayoutDashboard, component: CommandCenter },
  { id: 'cognition', label: '认知引擎', icon: Brain, component: CognitionEngine },
  { id: 'scheduler', label: '端边云调度', icon: Server, component: EdgeCloudScheduler },
  { id: 'topology', label: '拓扑路由', icon: Network, component: TopologyRouter },
  { id: 'mcp', label: 'MCP 工具', icon: Plug, component: MCPServers },
  { id: 'settings', label: '设置', icon: SettingsIcon, component: Settings },
]

const pageColors = ['text-[#6366f1]', 'text-[#F97316]', 'text-[#0EA5E9]', 'text-[#10B981]']

export default function App() {
  const [active, setActive] = useState('command')
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const ActivePage = pages.find(p => p.id === active)?.component || CommandCenter

  const fetchSystemStatus = useCallback(async () => {
    try {
      const data = await api.getSystemStatus()
      setSystemStatus(data)
    } catch {
      // silent fail — header shows "连接中..."
    }
  }, [])

  useEffect(() => {
    fetchSystemStatus()
    const interval = setInterval(fetchSystemStatus, 10000)
    return () => clearInterval(interval)
  }, [fetchSystemStatus])

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
            {systemStatus ? (
              <>
                <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#0EA5E9]/10 rounded-full">
                  <Activity className="w-3 h-3 text-[#0EA5E9]" />
                  <span className="text-[10px] font-medium text-[#0EA5E9]">{systemStatus.tasks_running} 活跃</span>
                </div>
                <div className="flex items-center gap-1.5 px-2.5 py-1 bg-[#10B981]/10 rounded-full">
                  <CheckCircle className="w-3 h-3 text-[#10B981]" />
                  <span className="text-[10px] font-medium text-[#10B981]">{systemStatus.tasks_completed} 完成</span>
                </div>
              </>
            ) : (
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-100 rounded-full">
                <div className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-pulse" />
                <span className="text-[10px] font-medium text-gray-500">连接中...</span>
              </div>
            )}
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
