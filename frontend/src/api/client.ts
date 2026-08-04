const API_BASE = import.meta.env.VITE_API_BASE || ''

// --- Types ---

export interface TaskExecution {
  id: string
  description: string
  max_steps: number
  status: string
  route?: string
  topology?: string
  participants?: string[]
  current_step?: number
  total_steps?: number
  created_at?: string
  tokens_total?: number
  duration_seconds?: number
  error?: string
}

export interface AgentInfo {
  id: string
  name: string
  label?: string
  icon?: string
  tier: string
  state: string
  current_task?: string
  tokens_used?: number
  tasks_completed?: number
  avg_latency_ms?: number
  tier_label?: string
  edge_cloud_layer?: string
  edge_cloud_label?: string
  description?: string
  capabilities?: string[]
}

export interface SystemStatus {
  status: string
  core_engine: boolean
  ollama: boolean
  deepseek: boolean
  agents: AgentInfo[]
  active_tasks: number
  completed_tasks: number
}

export interface UploadResponse {
  success: boolean
  filename: string
  saved_as: string
  path: string
  size: number
  content_type: string
}

export interface CreateTaskResponse {
  task_id: string
  status: string
  max_steps: number
  strategy: string
}

export interface WSEvent {
  type: string
  data: unknown
  timestamp: string
}

// --- API ---

export const api = {
  async createTask(description: string, maxSteps = 5, strategy = 'auto'): Promise<CreateTaskResponse> {
    const res = await fetch(`${API_BASE}/api/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description, max_steps: maxSteps, strategy }),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async uploadFile(file: File, taskId?: string): Promise<UploadResponse> {
    const form = new FormData()
    form.append('file', file)
    if (taskId) form.append('task_id', taskId)
    const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async getTasks(limit = 20): Promise<{ tasks: TaskExecution[] }> {
    const res = await fetch(`${API_BASE}/api/tasks?limit=${limit}`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async getAgents(): Promise<{ agents: AgentInfo[] }> {
    const res = await fetch(`${API_BASE}/api/agents`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async getSystemStatus(): Promise<SystemStatus> {
    const res = await fetch(`${API_BASE}/api/system/status`)
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async injectFault(taskId: string, faultType: string, targetAgent?: string) {
    const res = await fetch(`${API_BASE}/api/tasks/${taskId}/inject-fault`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fault_type: faultType, target_agent: targetAgent }),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  async modifyTask(taskId: string, newRequirements: string) {
    const res = await fetch(`${API_BASE}/api/tasks/${taskId}/modify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_requirements: newRequirements }),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },

  connectEvents(onMessage: (msg: WSEvent) => void): WebSocket {
    const wsUrl = API_BASE
      ? `${API_BASE.replace(/^http/, 'ws')}/ws/events`
      : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/events`
    const ws = new WebSocket(wsUrl)
    ws.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data) as WSEvent) } catch { /* ignore parse errors */ }
    }
    ws.onerror = () => {}
    ws.onclose = () => {
      setTimeout(() => api.connectEvents(onMessage), 3000)
    }
    return ws
  },
}
