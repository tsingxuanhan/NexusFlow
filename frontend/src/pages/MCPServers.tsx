import { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { apiMCP, type MCPServerConfig, type MCPTemplate } from '@/api/client'
import { Loader, Plug, RefreshCw, Plus, Check, AlertCircle, Trash2, Unplug, Server, Info } from 'lucide-react'

const statusMap: Record<string, { color: string; label: string }> = {
  connected: { color: 'green', label: '已连接' },
  connecting: { color: 'sky', label: '连接中' },
  disconnected: { color: 'gray', label: '未连接' },
  error: { color: 'red', label: '错误' },
}

export function MCPServers() {
  const [servers, setServers] = useState<MCPServerConfig[]>([])
  const [presets, setPresets] = useState<MCPTemplate[]>([])
  const [installStatus, setInstallStatus] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [showPresets, setShowPresets] = useState(false)
  const [actionId, setActionId] = useState<string | null>(null)

  const fetchServers = useCallback(async () => {
    try {
      const data = await apiMCP.getServers()
      setServers(data.servers || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchPresets = useCallback(async () => {
    try {
      const data = await apiMCP.getPresets()
      setPresets(data || [])
    } catch (e) {
      console.error(e)
    }
  }, [])

  useEffect(() => { fetchServers(); fetchPresets() }, [fetchServers, fetchPresets])

  // Auto-check install status for all servers
  useEffect(() => {
    servers.forEach(s => {
      if (!installStatus[s.id]) checkInstalled(s.id)
    })
  }, [servers])

  const checkInstalled = async (id: string) => {
    try {
      const status = await apiMCP.checkInstalled(id)
      setInstallStatus(prev => ({ ...prev, [id]: status }))
      return status
    } catch {
      return { installed: false }
    }
  }

  const handleAddPreset = async (id: string) => {
    setActionId(id)
    try {
      await apiMCP.addFromPreset(id)
      await fetchServers()
    } catch (e) {
      console.error('Failed to add preset:', e)
    } finally {
      setActionId(null)
    }
  }

  const handleConnect = async (id: string) => {
    setActionId(id)
    try {
      const status = await checkInstalled(id)
      if (!status.installed) {
        setInstallStatus(prev => ({ ...prev, [id]: status }))
        setActionId(null)
        return
      }
      await apiMCP.connectServer(id)
      await fetchServers()
    } catch (e) {
      console.error('Connect failed:', e)
    } finally {
      setActionId(null)
    }
  }

  const handleDisconnect = async (id: string) => {
    setActionId(id)
    try {
      await apiMCP.disconnectServer(id)
      await fetchServers()
    } catch (e) {
      console.error('Disconnect failed:', e)
    } finally {
      setActionId(null)
    }
  }

  const handleRemove = async (id: string) => {
    setActionId(id)
    try {
      await apiMCP.removeServer(id)
      await fetchServers()
    } catch (e) {
      console.error('Remove failed:', e)
    } finally {
      setActionId(null)
    }
  }

  if (loading) return <div className="flex items-center justify-center py-16"><Loader className="w-6 h-6 text-[#6366f1] animate-spin" /></div>

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-gray-800">MCP 服务器管理</h2>
          <p className="text-xs text-gray-500 mt-0.5">通过 MCP 协议连接外部工具服务器，即插即用扩展 NexusFlow 能力</p>
        </div>
        <Button onClick={() => setShowPresets(!showPresets)} size="sm" variant="secondary">
          {showPresets ? '收起' : <><Plus className="w-3.5 h-3.5 mr-1" />添加服务器</>}
        </Button>
      </div>

      {/* Available Templates */}
      {showPresets && (
        <Card title="可用模板" icon={<Server className="w-4 h-4" />}>
          <div className="space-y-3">
            {presets.map(t => {
              const alreadyAdded = servers.some(s => s.id === t.id)
              const isActing = actionId === t.id
              return (
                <div key={t.id} className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 hover:border-gray-200 transition-colors">
                  <div className="p-2 rounded-lg bg-[#6366f1]/10 text-[#6366f1]">
                    <Plug className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800">{t.name}</span>
                      <Badge color="indigo">{t.transport}</Badge>
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{t.description}</p>
                    <div className="flex items-center gap-1 mt-1.5">
                      <Info className="w-3 h-3 text-gray-400" />
                      <code className="text-[10px] text-gray-400 font-mono">{t.command} {t.args?.join(' ')}</code>
                    </div>
                  </div>
                  <Button
                    onClick={() => handleAddPreset(t.id)}
                    disabled={alreadyAdded || isActing}
                    size="sm"
                    variant={alreadyAdded ? 'secondary' : 'primary'}>
                    {isActing ? <Loader className="w-3.5 h-3.5 animate-spin" /> : alreadyAdded ? <Check className="w-3.5 h-3.5 text-[#10B981]" /> : <Plus className="w-3.5 h-3.5" />}
                    <span className="ml-1">{alreadyAdded ? '已添加' : '添加'}</span>
                  </Button>
                </div>
              )
            })}
            {presets.length === 0 && <p className="text-center py-4 text-xs text-gray-400">暂无可用模板</p>}
          </div>
        </Card>
      )}

      {/* Configured Servers */}
      <Card title="已配置的服务器" icon={<Server className="w-4 h-4" />}
        action={<Badge color="indigo">{servers.length} 个</Badge>}>
        {servers.length === 0 ? (
          <div className="text-center py-8">
            <Server className="w-8 h-8 mx-auto text-gray-300 mb-2" />
            <p className="text-sm text-gray-500">尚未配置 MCP 服务器</p>
            <p className="text-xs text-gray-400 mt-1">点击「添加服务器」从模板添加，如 OfficeCLI</p>
          </div>
        ) : (
          <div className="space-y-3">
            {servers.map(server => {
              const st = statusMap[server.status] || statusMap.disconnected
              const install = installStatus[server.id]
              const isActing = actionId === server.id
              return (
                <div key={server.id} className="p-4 rounded-lg border border-gray-100 space-y-3">
                  {/* Server Header */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${
                        server.status === 'connected' ? 'bg-[#10B981]/10 text-[#10B981]' : 'bg-gray-100 text-gray-500'
                      }`}>
                        <Plug className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-gray-800">{server.name}</span>
                          <Badge color={st.color}>{st.label}</Badge>
                          {server.tools_count > 0 && <Badge color="sky">{server.tools_count} 工具</Badge>}
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">{server.description}</p>
                      </div>
                    </div>
                    {/* Action Buttons */}
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => checkInstalled(server.id)}
                        className="p-1.5 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                        title="刷新安装状态">
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                      {server.status === 'connected' ? (
                        <button onClick={() => handleDisconnect(server.id)} disabled={isActing}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium text-orange-600 bg-orange-50 hover:bg-orange-100 transition-colors">
                          {isActing ? <Loader className="w-3 h-3 animate-spin" /> : <Unplug className="w-3 h-3" />}
                          断开
                        </button>
                      ) : (
                        <button onClick={() => handleConnect(server.id)} disabled={isActing}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium text-white bg-[#10B981] hover:bg-[#059669] transition-colors">
                          {isActing ? <Loader className="w-3 h-3 animate-spin" /> : <Plug className="w-3 h-3" />}
                          连接
                        </button>
                      )}
                      <button onClick={() => handleRemove(server.id)} disabled={isActing}
                        className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                        title="删除">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Installation Warning */}
                  {install && !install.installed && (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200">
                      <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-xs font-medium text-amber-800">需要先安装 {install.binary || server.name}</p>
                        <div className="mt-1.5 space-y-1">
                          {install.install_commands && (Object.entries(install.install_commands) as [string, string][]).map(([platform, cmd]) => (
                            <div key={platform} className="flex items-center gap-2">
                              <span className="text-[10px] font-medium text-amber-600 uppercase w-14 shrink-0">{platform}</span>
                              <code className="text-[10px] bg-amber-100 px-2 py-0.5 rounded text-amber-900 font-mono select-all">{cmd}</code>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Installation Success */}
                  {install?.installed && (
                    <div className="flex items-center gap-2 text-xs text-[#10B981]">
                      <Check className="w-3.5 h-3.5" />
                      已安装 {install.version ? `v${install.version}` : ''}
                      {install.path && <span className="text-gray-400 font-mono text-[10px]">{install.path}</span>}
                    </div>
                  )}

                  {/* Error Display */}
                  {server.error && (
                    <div className="flex items-center gap-2 p-2 rounded-lg bg-red-50 text-xs text-red-600">
                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                      {server.error}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {/* About MCP Integration */}
      <div className="p-4 rounded-lg bg-gray-50 border border-gray-100">
        <h3 className="text-xs font-semibold text-gray-600 mb-2">关于 MCP 集成</h3>
        <ul className="space-y-1.5 text-xs text-gray-500">
          <li>• MCP（Model Context Protocol）是 Anthropic 提出的标准协议，用于 AI 连接外部工具</li>
          <li>• 任何支持 MCP 协议的工具都可以通过「添加服务器」接入 NexusFlow</li>
          <li>• 连接的 MCP 工具会自动注册到 Agent 工具系统，可被任务自动调用</li>
          <li>• 工具二进制需要在本机安装，NexusFlow 通过 MCP 协议与之通信</li>
        </ul>
      </div>
    </div>
  )
}
