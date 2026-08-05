import { useState, useEffect, useCallback } from 'react'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { apiSettings, type ModelSettings } from '@/api/client'
import { Settings as SettingsIcon, Loader, CheckCircle, XCircle, Save, Cloud, Server, Key, Globe, Zap, Eye, EyeOff, Plus, Trash2 } from 'lucide-react'

const providerLabels: Record<string, string> = { deepseek: 'DeepSeek', ollama: '本地 Ollama' }
const tierColors: Record<string, string> = { global: 'text-[#6366f1]', cdol: 'text-[#0EA5E9]', assayer: 'text-[#10B981]' }

interface CustomProviderForm { name: string; endpoint: string; api_key: string; models: string; }

export function Settings() {
  const [settings, setSettings] = useState<ModelSettings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editedModels, setEditedModels] = useState<Record<string, { provider: string; model: string }>>({})
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [deepseekKey, setDeepseekKey] = useState('')
  const [deepseekEndpoint, setDeepseekEndpoint] = useState('')
  const [ollamaUrl, setOllamaUrl] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  const [testingProvider, setTestingProvider] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<{ provider: string; success: boolean; message: string } | null>(null)
  const [providerSaveMsg, setProviderSaveMsg] = useState('')
  const [showAddProvider, setShowAddProvider] = useState(false)
  const [customForm, setCustomForm] = useState<CustomProviderForm>({ name: '', endpoint: '', api_key: '', models: '' })
  const [addingProvider, setAddingProvider] = useState(false)

  const fetchSettings = useCallback(async () => {
    try {
      const data = await apiSettings.getModelSettings()
      setSettings(data)
      const initial: Record<string, { provider: string; model: string }> = {}
      for (const am of data.agent_models) { initial[am.agent_id] = { provider: am.provider, model: am.model } }
      setEditedModels(initial)
      if (data.providers.deepseek) setDeepseekEndpoint((data.providers.deepseek as any).endpoint || 'https://api.deepseek.com/chat/completions')
      if (data.providers.ollama) setOllamaUrl((data.providers.ollama as any).url || 'http://localhost:11434')
      setLoading(false)
    } catch { setLoading(false) }
  }, [])

  useEffect(() => { fetchSettings() }, [fetchSettings])

  const handleProviderChange = useCallback((agentId: string, provider: string) => {
    setEditedModels(prev => ({ ...prev, [agentId]: { ...prev[agentId], provider, model: '' } }))
  }, [])
  const handleModelChange = useCallback((agentId: string, model: string) => {
    setEditedModels(prev => ({ ...prev, [agentId]: { ...prev[agentId], model } }))
  }, [])

  const handleSaveModels = useCallback(async () => {
    setSaving(true); setSaveSuccess(false)
    try {
      const agentModels = Object.entries(editedModels).map(([agent_id, config]) => ({ agent_id, provider: config.provider, model: config.model }))
      const result = await apiSettings.updateModelSettings(agentModels)
      setSettings(result); setSaveSuccess(true); setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) { console.error(err) }
    finally { setSaving(false) }
  }, [editedModels])

  const handleSaveProviders = useCallback(async () => {
    const providers: Record<string, any> = {}
    if (deepseekKey) providers.deepseek = { api_key: deepseekKey }
    if (deepseekEndpoint) providers.deepseek = { ...providers.deepseek, endpoint: deepseekEndpoint }
    if (ollamaUrl) providers.ollama = { url: ollamaUrl }
    if (Object.keys(providers).length === 0) return
    try {
      const resp = await fetch('/api/settings/providers', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({providers}) })
      const res = await resp.json()
      if (res.success) { setProviderSaveMsg('已保存'); setDeepseekKey(''); await fetchSettings(); setTimeout(() => setProviderSaveMsg(''), 3000) }
    } catch { setProviderSaveMsg('保存失败') }
  }, [deepseekKey, deepseekEndpoint, ollamaUrl, fetchSettings])

  const handleTestProvider = useCallback(async (providerName: string) => {
    setTestingProvider(providerName); setTestResult(null)
    try {
      const resp = await fetch('/api/settings/providers/test', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({provider: providerName}) })
      const res = await resp.json()
      setTestResult({ provider: providerName, success: res.success, message: res.message })
    } catch (err: any) { setTestResult({ provider: providerName, success: false, message: err.message || '测试失败' }) }
    finally { setTestingProvider(null) }
  }, [])

  const handleAddCustomProvider = useCallback(async () => {
    if (!customForm.name || !customForm.endpoint || !customForm.api_key) return
    setAddingProvider(true)
    const provId = `custom_${customForm.name.toLowerCase().replace(/[^a-z0-9]/g, '_')}`
    const models = customForm.models.split(',').map(s => s.trim()).filter(Boolean)
    try {
      const resp = await fetch('/api/settings/providers', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({providers: {[provId]: { display_name: customForm.name, endpoint: customForm.endpoint, api_key: customForm.api_key, models }}}) })
      const res = await resp.json()
      if (res.success) { setShowAddProvider(false); setCustomForm({name:'',endpoint:'',api_key:'',models:''}); await fetchSettings() }
    } catch (err) { console.error(err) }
    finally { setAddingProvider(false) }
  }, [customForm, fetchSettings])

  const handleDeleteProvider = useCallback(async (provId: string) => {
    if (!confirm(`确定删除 Provider「${provId}」？`)) return
    try { await fetch(`/api/settings/providers/${provId}`, { method: 'DELETE' }); await fetchSettings() } catch (err) { console.error(err) }
  }, [fetchSettings])

  const getProviderModels = useCallback((providerName: string): string[] => {
    const p = settings?.providers?.[providerName]
    if (!p) return []
    if (p.models && p.models.length > 0) return p.models
    if (providerName === 'deepseek') return ['deepseek-v4-flash', 'deepseek-v4-pro']
    return []
  }, [settings])

  if (loading) return <div className="flex items-center justify-center py-16"><Loader className="w-6 h-6 text-[#6366f1] animate-spin" /></div>
  if (!settings) return <div className="text-center py-16"><XCircle className="w-8 h-8 text-red-400 mx-auto mb-2" /><p className="text-sm text-gray-500">无法加载模型配置</p></div>

  return (
    <div className="space-y-5">
      <div><h2 className="text-lg font-bold text-gray-800">模型配置</h2><p className="text-xs text-gray-500 mt-0.5">配置 LLM Provider 连接信息，并为每个 Agent 分配模型</p></div>

      {/* Provider Config */}
      <Card title="Provider 连接配置" icon={<SettingsIcon className="w-4 h-4" />}
            action={<Button onClick={() => setShowAddProvider(!showAddProvider)} size="sm" variant="secondary"><Plus className="w-3.5 h-3.5 mr-1" />添加 Provider</Button>}>
        <div className="space-y-4">
          {/* DeepSeek */}
          <div className="p-4 rounded-lg border border-gray-100 space-y-3">
            <div className="flex items-center gap-2"><Cloud className="w-4 h-4 text-[#6366f1]" /><span className="text-sm font-semibold text-gray-800">DeepSeek</span>
              {settings.providers.deepseek && <Badge color={(settings.providers.deepseek as any).api_key_set ? 'green' : 'orange'}>{(settings.providers.deepseek as any).api_key_set ? 'Key 已配置' : 'Key 未设置'}</Badge>}</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div><label className="flex items-center gap-1 text-xs text-gray-500 mb-1"><Key className="w-3 h-3" /> API Key</label>
                <div className="relative"><input type={showApiKey?'text':'password'} value={deepseekKey} onChange={(e)=>setDeepseekKey(e.target.value)}
                  placeholder={(settings.providers.deepseek as any)?.api_key_set ? '已配置，输入新 Key 以更新' : '输入 DeepSeek API Key...'}
                  className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] pr-8 font-mono" />
                  <button type="button" onClick={()=>setShowApiKey(!showApiKey)} className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                    {showApiKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button></div></div>
              <div><label className="flex items-center gap-1 text-xs text-gray-500 mb-1"><Globe className="w-3 h-3" /> API Endpoint</label>
                <input type="text" value={deepseekEndpoint} onChange={(e)=>setDeepseekEndpoint(e.target.value)}
                  placeholder="https://api.deepseek.com/chat/completions"
                  className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] font-mono" /></div>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={()=>handleTestProvider('deepseek')} variant="secondary" size="sm" disabled={testingProvider==='deepseek'}>
                {testingProvider==='deepseek' ? <Loader className="w-3 h-3 mr-1 animate-spin" /> : <Zap className="w-3 h-3 mr-1" />}测试连接</Button>
              {testResult?.provider==='deepseek' && <span className={`text-xs flex items-center gap-1 ${testResult.success?'text-[#10B981]':'text-red-400'}`}>{testResult.success?<CheckCircle className="w-3 h-3"/>:<XCircle className="w-3 h-3"/>}{testResult.message}</span>}
            </div>
          </div>

          {/* Ollama */}
          <div className="p-4 rounded-lg border border-gray-100 space-y-3">
            <div className="flex items-center gap-2"><Server className="w-4 h-4 text-[#0EA5E9]" /><span className="text-sm font-semibold text-gray-800">本地 Ollama</span>
              {settings.providers.ollama && <Badge color={(settings.providers.ollama as any).enabled?'green':'red'}>{(settings.providers.ollama as any).enabled?'已连接':'未连接'}</Badge>}</div>
            <div><label className="flex items-center gap-1 text-xs text-gray-500 mb-1"><Globe className="w-3 h-3" /> Ollama 服务地址</label>
              <input type="text" value={ollamaUrl} onChange={(e)=>setOllamaUrl(e.target.value)} placeholder="http://localhost:11434"
                className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] font-mono" /></div>
            <div className="flex items-center gap-2">
              <Button onClick={()=>handleTestProvider('ollama')} variant="secondary" size="sm" disabled={testingProvider==='ollama'}>
                {testingProvider==='ollama' ? <Loader className="w-3 h-3 mr-1 animate-spin" /> : <Zap className="w-3 h-3 mr-1" />}测试连接</Button>
              {testResult?.provider==='ollama' && <span className={`text-xs flex items-center gap-1 ${testResult.success?'text-[#10B981]':'text-red-400'}`}>{testResult.success?<CheckCircle className="w-3 h-3"/>:<XCircle className="w-3 h-3"/>}{testResult.message}</span>}
            </div>
          </div>

          {/* Custom Providers */}
          {Object.entries(settings.providers).filter(([name]) => name.startsWith('custom_')).map(([name, info]: [string, any]) => (
            <div key={name} className="p-4 rounded-lg border border-[#6366f1]/20 bg-[#6366f1]/5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2"><Globe className="w-4 h-4 text-[#6366f1]" /><span className="text-sm font-semibold text-gray-800">{info.display_name || name}</span>
                  <Badge color="indigo">自定义</Badge>{info.api_key_set && <Badge color="green">Key 已配置</Badge>}</div>
                <div className="flex items-center gap-1">
                  <Button onClick={()=>handleTestProvider(name)} variant="secondary" size="sm" disabled={testingProvider===name}>
                    {testingProvider===name ? <Loader className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}</Button>
                  <Button onClick={()=>handleDeleteProvider(name)} variant="secondary" size="sm"><Trash2 className="w-3 h-3 text-red-400" /></Button>
                </div>
              </div>
              {testResult?.provider===name && <div className={`text-xs flex items-center gap-1 ${testResult.success?'text-[#10B981]':'text-red-400'}`}>{testResult.success?<CheckCircle className="w-3 h-3"/>:<XCircle className="w-3 h-3"/>}{testResult.message}</div>}
              <div className="text-xs text-gray-500 font-mono truncate">{info.endpoint}</div>
              {info.models?.length > 0 && <div className="flex items-center gap-1 flex-wrap"><span className="text-[10px] text-gray-400">模型:</span>{info.models.map((m:string)=>(<Badge key={m} color="sky">{m}</Badge>))}</div>}
            </div>
          ))}

          {/* Add Custom Provider Form */}
          {showAddProvider && (
            <div className="p-4 rounded-lg border-2 border-dashed border-[#6366f1]/30 space-y-3">
              <h4 className="text-sm font-semibold text-gray-700">添加自定义 Provider（支持 OpenAI / 通义千问 / Moonshot / 智谱 等兼容接口）</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div><label className="text-xs text-gray-500 mb-1 block">名称</label><input type="text" value={customForm.name} onChange={(e)=>setCustomForm(f=>({...f,name:e.target.value}))} placeholder="如：通义千问" className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30" /></div>
                <div><label className="text-xs text-gray-500 mb-1 block">API Endpoint</label><input type="text" value={customForm.endpoint} onChange={(e)=>setCustomForm(f=>({...f,endpoint:e.target.value}))} placeholder="https://api.openai.com/v1/chat/completions" className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 font-mono" /></div>
                <div><label className="text-xs text-gray-500 mb-1 block">API Key</label><input type="password" value={customForm.api_key} onChange={(e)=>setCustomForm(f=>({...f,api_key:e.target.value}))} placeholder="sk-..." className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 font-mono" /></div>
                <div><label className="text-xs text-gray-500 mb-1 block">可用模型（逗号分隔）</label><input type="text" value={customForm.models} onChange={(e)=>setCustomForm(f=>({...f,models:e.target.value}))} placeholder="qwen-turbo, qwen-plus" className="w-full px-3 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 font-mono" /></div>
              </div>
              <div className="flex items-center gap-2">
                <Button onClick={handleAddCustomProvider} disabled={addingProvider||!customForm.name||!customForm.endpoint||!customForm.api_key} size="sm">
                  {addingProvider ? <Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Plus className="w-3.5 h-3.5 mr-1" />}{addingProvider?'添加中...':'添加'}</Button>
                <Button onClick={()=>setShowAddProvider(false)} variant="secondary" size="sm">取消</Button>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 pt-1">
            <Button onClick={handleSaveProviders} size="sm"><Save className="w-3.5 h-3.5 mr-1" />{providerSaveMsg || '保存 Provider 配置'}</Button>
          </div>
        </div>
      </Card>

      {/* Agent Model Assignment */}
      <Card title="Agent 模型分配" icon={<SettingsIcon className="w-4 h-4" />}
            action={<div className="flex items-center gap-2"><Badge color="indigo">{settings.agent_models.length} Agent</Badge>
              <Button onClick={handleSaveModels} disabled={saving} size="sm">
                {saving ? <><Loader className="w-3.5 h-3.5 mr-1 animate-spin" /> 保存中...</> : saveSuccess ? <><CheckCircle className="w-3.5 h-3.5 mr-1 text-[#10B981]" /> 已保存</> : <><Save className="w-3.5 h-3.5 mr-1" /> 保存</>}
              </Button></div>}>
        <div className="space-y-2">
          {settings.agent_models.map(am => {
            const edited = editedModels[am.agent_id] || { provider: am.provider, model: am.model }
            const isModified = edited.provider !== am.provider || edited.model !== am.model
            const currentModels = getProviderModels(edited.provider)
            return (
              <div key={am.agent_id} className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${isModified?'border-[#6366f1]/30 bg-[#6366f1]/5':'border-gray-100'}`}>
                <div className="flex items-center gap-2 min-w-[120px]">
                  <span className="text-base">{am.icon || '🤖'}</span>
                  <div><span className="text-sm font-medium text-gray-800">{am.label || am.agent_id}</span>
                    {am.tier && <span className={`text-[10px] ml-1.5 ${tierColors[am.tier]||'text-gray-400'}`}>{am.tier}</span>}</div>
                </div>
                <div className="w-40">
                  <select value={edited.provider} onChange={(e)=>handleProviderChange(am.agent_id, e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] bg-white">
                    {Object.entries(settings.providers).map(([p, info]: [string, any]) => (<option key={p} value={p}>{(info as any).display_name || providerLabels[p] || p}</option>))}
                  </select>
                </div>
                <div className="flex-1">
                  {currentModels.length > 0 ? (
                    <select value={edited.model} onChange={(e)=>handleModelChange(am.agent_id, e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] bg-white font-mono">
                      <option value="">选择模型...</option>
                      {currentModels.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  ) : (
                    <input type="text" value={edited.model} onChange={(e)=>handleModelChange(am.agent_id, e.target.value)} placeholder="输入模型名称..."
                      className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#6366f1]/30 focus:border-[#6366f1] font-mono" />
                  )}
                </div>
                {isModified && <Badge color="orange">已修改</Badge>}
              </div>
            )
          })}
        </div>
      </Card>

      <div className="p-4 rounded-lg bg-gray-50 border border-gray-100">
        <h3 className="text-xs font-semibold text-gray-600 mb-2">使用说明</h3>
        <ul className="space-y-1.5 text-xs text-gray-500">
          <li>• 先配置 Provider 连接信息（API Key / Ollama 地址），点击「保存 Provider 配置」</li>
          <li>• 然后在下方为每个 Agent 选择 Provider 和模型，点击「保存」生效</li>
          <li>• 修改后无需重启服务，实时生效</li>
          <li>• 配置会持久化到 config/model_settings.json，重启后自动加载</li>
          <li>• 点击「测试连接」可验证 Provider 是否可用</li>
          <li>• 点击「添加 Provider」可接入任意 OpenAI 兼容 API（通义千问、Moonshot、智谱等）</li>
        </ul>
      </div>
    </div>
  )
}
