export interface TaskExecution { id: string; description: string; status: string; created_at: string; steps?: any[]; }
export interface AgentInfo { id: string; name: string; status: string; role: string; icon: string; layer?: string; }
export interface SystemStatus { status: string; uptime: string; agents_online: number; tasks_total: number; tasks_running: number; tasks_completed: number; }
export interface OutputFormat { id: string; name: string; ext: string; available: boolean; desc: string; }
export interface ModelProviderInfo { enabled: boolean; url?: string; endpoint?: string; api_key_set?: boolean; models?: string[]; display_name?: string; is_custom?: boolean; }
export interface AgentModelConfig { agent_id: string; label: string; icon: string; provider: string; model: string; tier: string; }
export interface ModelSettings { providers: Record<string, ModelProviderInfo>; agent_models: AgentModelConfig[]; }
export interface MCPServerConfig { id: string; name: string; description: string; transport: string; command: string; args: string[]; url: string; env: Record<string,string>; enabled: boolean; status: string; error: string; tools_count: number; }
export interface MCPTemplate { id: string; name: string; description: string; transport: string; command: string; args: string[]; url?: string; }
export interface MCPInstallStatus { installed: boolean; version?: string; path?: string; binary?: string; install_commands?: Record<string, string>; }

export const api = {
  async getSystemStatus(): Promise<SystemStatus> { const r = await fetch('/api/system/status'); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getAgents(): Promise<{agents: AgentInfo[]}> { const r = await fetch('/api/agents'); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getTasks(limit=20): Promise<{tasks: TaskExecution[]}> { const r = await fetch(`/api/tasks?limit=${limit}`); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async createTask(description: string, maxSteps=5, strategy='auto', outputFormat='markdown'): Promise<any> { const r = await fetch('/api/tasks', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({description, max_steps:maxSteps, strategy, output_format: outputFormat}) }); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  connectEvents(onMessage: (msg: any) => void): WebSocket {
    const wsUrl = window.location.protocol === 'https:' ? `wss://${window.location.host}/ws/events` : `ws://${window.location.host}/ws/events`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (e) => { try { onMessage(JSON.parse(e.data)); } catch {} };
    ws.onerror = () => {};
    ws.onclose = () => { setTimeout(() => api.connectEvents(onMessage), 3000); };
    return ws;
  }
};

export const apiSettings = {
  async getModelSettings(): Promise<ModelSettings> { const r = await fetch('/api/settings/models'); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async updateModelSettings(agentModels: {agent_id:string;provider:string;model:string}[]): Promise<ModelSettings> { const r = await fetch('/api/settings/models', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({agent_models: agentModels}) }); if(!r.ok) throw new Error(await r.text()); return r.json(); },
};

export const apiMCP = {
  async getServers(): Promise<{servers: MCPServerConfig[]}> { const r = await fetch('/api/mcp/servers'); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getPresets(): Promise<MCPTemplate[]> { const r = await fetch('/api/mcp/presets'); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async connectServer(id: string): Promise<any> { const r = await fetch(`/api/mcp/servers/${id}/connect`, {method:'POST'}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async disconnectServer(id: string): Promise<any> { const r = await fetch(`/api/mcp/servers/${id}/disconnect`, {method:'POST'}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async addFromPreset(id: string): Promise<any> { const r = await fetch(`/api/mcp/presets/${id}/add`, {method:'POST'}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async removeServer(id: string): Promise<any> { const r = await fetch(`/api/mcp/servers/${id}`, {method:'DELETE'}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async checkInstalled(id: string): Promise<MCPInstallStatus> { const r = await fetch(`/api/mcp/servers/${id}/check`); if(!r.ok) return {installed:false}; return r.json(); },
};

export const apiCognition = {
  async getStatus(): Promise<any> { const r = await fetch('/api/cognition/status'); if(!r.ok) return {active_processes:0,total_completed:0,avg_reasoning_time_ms:0,strategies:[]}; return r.json(); },
  async getMemory(): Promise<any> { const r = await fetch('/api/cognition/memory'); if(!r.ok) return {layers:{},total:0}; return r.json(); },
  async searchMemory(query: string): Promise<any> { const r = await fetch(`/api/cognition/memory/search?q=${encodeURIComponent(query)}`); if(!r.ok) return {results:[]}; return r.json(); },
  async addToMemory(content: string): Promise<any> { const r = await fetch('/api/cognition/memory', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({content})}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getDreamLog(): Promise<any> { const r = await fetch('/api/cognition/dream/log'); if(!r.ok) return {logs:[]}; return r.json(); },
  async triggerDream(): Promise<any> { const r = await fetch('/api/cognition/dream/trigger', {method:'POST'}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getBlindSpots(): Promise<any> { const r = await fetch('/api/cognition/blind-spots'); if(!r.ok) return {spots:[]}; return r.json(); },
  async getCrossDomainMigration(): Promise<any> { const r = await fetch('/api/cognition/migration'); if(!r.ok) return {migrations:[],analogies:[]}; return r.json(); },
  async findAnalogies(query: string): Promise<any> { const r = await fetch(`/api/cognition/migration/analogies?q=${encodeURIComponent(query)}`); if(!r.ok) return {analogies:[]}; return r.json(); },
  async triggerManualMigration(source: string, target: string): Promise<any> { const r = await fetch('/api/cognition/migration/manual', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({source, target})}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getSelfImprovement(): Promise<any> { const r = await fetch('/api/cognition/self-improve'); if(!r.ok) return {status:'idle',improvements:[]}; return r.json(); },
  async triggerSelfImprovement(): Promise<any> { const r = await fetch('/api/cognition/self-improve/trigger', {method:'POST'}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getLearningCurve(): Promise<any> { const r = await fetch('/api/cognition/learning-curve'); if(!r.ok) return {curve:[]}; return r.json(); },
};

export const apiScheduler = {
  async getStatus(): Promise<any> { const r = await fetch('/api/scheduler/status'); if(!r.ok) return {strategy:'adaptive',queue_length:0,completed:0,nodes:{}}; return r.json(); },
  async getStats(): Promise<any> { const r = await fetch('/api/scheduler/stats'); if(!r.ok) return {total_scheduled:0,strategy:'adaptive',simulation:null}; return r.json(); },
  async getTiers(): Promise<any> { const r = await fetch('/api/scheduler/tiers'); if(!r.ok) return {tiers:{}}; return r.json(); },
  async getPolicies(): Promise<any> { const r = await fetch('/api/scheduler/policies'); if(!r.ok) return {policies:[]}; return r.json(); },
  async getResourceMonitor(): Promise<any> { const r = await fetch('/api/scheduler/monitor'); if(!r.ok) return {memory:0,disk:0,cpu:0,gpu:0,latency:0,estimated_latency:0,bandwidth:0}; return r.json(); },
  async injectAnomaly(config: any): Promise<any> { const r = await fetch('/api/scheduler/anomaly', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(config)}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
};

export const apiTopology = {
  async getStats(): Promise<any> { const r = await fetch('/api/topology-optimizer/stats'); if(!r.ok) return {topology:'mesh',decisions:0,recommendations:[]}; return r.json(); },
  async getRecommendations(): Promise<any> { const r = await fetch('/api/topology-optimizer/recommendations'); if(!r.ok) return {recommendations:[]}; return r.json(); },
  async getRouteHistory(): Promise<any> { const r = await fetch('/api/router/history'); if(!r.ok) return {history:[]}; return r.json(); },
  async simulateRoute(task: string): Promise<any> { const r = await fetch('/api/router/route', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({task})}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
  async getAgents(): Promise<any> { const r = await fetch('/api/router/agents'); if(!r.ok) return {agents:[]}; return r.json(); },
  async getOptimization(): Promise<any> { const r = await fetch('/api/router/optimization'); if(!r.ok) return {stats:{},success_rates:[]}; return r.json(); },
  async injectAnomaly(config: any): Promise<any> { const r = await fetch('/api/topology-optimizer/anomaly', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(config)}); if(!r.ok) throw new Error(await r.text()); return r.json(); },
};

export const apiOutput = {
  async getFormats(): Promise<{formats: OutputFormat[]}> { const r = await fetch('/api/output/formats'); if(!r.ok) throw new Error(await r.text()); return r.json(); },
};
