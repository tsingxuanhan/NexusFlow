export const agents = [
  { id: 'orchestrator', name: 'Orchestrator', role: 'orchestrator', tier: 'cloud', status: 'online', tasks: 12, load: 78 },
  { id: 'coordinator', name: 'Coordinator', role: 'coordinator', tier: 'cloud', status: 'online', tasks: 8, load: 45 },
  { id: 'executor-alpha', name: 'Executor-α', role: 'executor', tier: 'edge', status: 'online', tasks: 5, load: 62 },
  { id: 'executor-beta', name: 'Executor-β', role: 'executor', tier: 'edge', status: 'busy', tasks: 7, load: 91 },
  { id: 'executor-gamma', name: 'Executor-γ', role: 'executor', tier: 'device', status: 'idle', tasks: 0, load: 12 },
  { id: 'executor-delta', name: 'Executor-δ', role: 'executor', tier: 'device', status: 'online', tasks: 3, load: 34 },
  { id: 'analyst', name: 'Analyst', role: 'coordinator', tier: 'cloud', status: 'online', tasks: 4, load: 55 },
  { id: 'executor-epsilon', name: 'Executor-ε', role: 'executor', tier: 'edge', status: 'offline', tasks: 0, load: 0 },
]

export const tasks = [
  { id: 'T-1001', title: '数据清洗与特征提取', status: 'running', agent: 'Executor-α', priority: 'high', created: '14:23', duration: '12m' },
  { id: 'T-1002', title: '模型推理 - Batch A', status: 'running', agent: 'Executor-β', priority: 'critical', created: '14:18', duration: '25m' },
  { id: 'T-1003', title: '日志聚合分析', status: 'queued', agent: '-', priority: 'medium', created: '14:30', duration: '-' },
  { id: 'T-1004', title: '跨域知识迁移', status: 'completed', agent: 'Executor-δ', priority: 'low', created: '13:45', duration: '8m' },
  { id: 'T-1005', title: 'API 网关压力测试', status: 'queued', agent: '-', priority: 'medium', created: '14:32', duration: '-' },
  { id: 'T-1006', title: '安全扫描 - 模块 C', status: 'failed', agent: 'Executor-α', priority: 'high', created: '14:10', duration: '3m' },
]

export const logs = [
  { time: '14:32:05', level: 'info', agent: 'Orchestrator', message: 'Task T-1005 queued, awaiting executor' },
  { time: '14:31:42', level: 'warn', agent: 'Executor-β', message: 'Memory pressure detected (91%), consider migration' },
  { time: '14:30:18', level: 'info', agent: 'Coordinator', message: 'Dispatching T-1003 to edge tier' },
  { time: '14:28:55', level: 'success', agent: 'Executor-δ', message: 'T-1004 completed: cross-domain mapping (0.89 confidence)' },
  { time: '14:25:10', level: 'error', agent: 'Executor-α', message: 'T-1006 failed: security guardrail blocked output' },
  { time: '14:23:01', level: 'info', agent: 'Orchestrator', message: 'Task T-1001 assigned to Executor-α (edge)' },
  { time: '14:20:33', level: 'info', agent: 'SleeptimeEngine', message: 'Dream cycle #47 completed: 3 patterns consolidated' },
  { time: '14:18:00', level: 'info', agent: 'MetaCognition', message: 'Self-assessment: confidence 0.87, gaps detected in domain-B' },
  { time: '14:15:22', level: 'success', agent: 'TopologyOptimizer', message: 'Topology switched to star (fitness: 0.94)' },
  { time: '14:12:45', level: 'warn', agent: 'GuardRail', message: 'Output filtered: PII detected in response payload' },
]

export const memoryStats = {
  core: [
    { key: 'system.identity', value: 'NexusFlow v3.6', type: 'core' as const, confidence: 1.0 },
    { key: 'task.pattern.dispatch', value: 'priority→tier→load', type: 'core' as const, confidence: 0.95 },
    { key: 'agent.coordinator.policy', value: 'balanced', type: 'core' as const, confidence: 0.92 },
  ],
  episodic: [
    { key: 'T-1006.security.fail', value: 'guardrail blocked PII leak', type: 'episodic' as const, confidence: 0.88 },
    { key: 'T-0987.timeout.edge', value: 'Executor-γ timeout at 120s', type: 'episodic' as const, confidence: 0.79 },
  ],
  semantic: [
    { key: 'domain.security', value: '3 rules active, 12 checks/day', type: 'semantic' as const, confidence: 0.85 },
    { key: 'domain.optimization', value: 'star topology preferred (0.94)', type: 'semantic' as const, confidence: 0.91 },
  ],
}

export const metaCognition = {
  confidence: 0.87,
  gaps: ['domain-B reasoning', 'long-horizon planning'],
  selfImprovements: [
    { area: 'task dispatch', before: 0.72, after: 0.89, delta: '+0.17' },
    { area: 'error recovery', before: 0.65, after: 0.78, delta: '+0.13' },
    { area: 'resource allocation', before: 0.81, after: 0.88, delta: '+0.07' },
  ],
}

export const sleeptimeLogs = [
  { cycle: 47, patterns: 3, consolidated: 3, pruned: 1, duration: '4.2s' },
  { cycle: 46, patterns: 5, consolidated: 4, pruned: 2, duration: '5.1s' },
  { cycle: 45, patterns: 2, consolidated: 2, pruned: 0, duration: '3.0s' },
  { cycle: 44, patterns: 7, consolidated: 5, pruned: 3, duration: '6.8s' },
  { cycle: 43, patterns: 4, consolidated: 3, pruned: 1, duration: '4.5s' },
]

export const crossDomainMappings = [
  { source: 'security.analysis', target: 'network.routing', confidence: 0.82, status: 'applied' },
  { source: 'game.strategy', target: 'task.scheduling', confidence: 0.74, status: 'testing' },
  { source: 'bio.evolution', target: 'topology.optimization', confidence: 0.91, status: 'applied' },
]

export const learningCurve = [
  { epoch: 1, accuracy: 0.45 },
  { epoch: 5, accuracy: 0.58 },
  { epoch: 10, accuracy: 0.67 },
  { epoch: 15, accuracy: 0.74 },
  { epoch: 20, accuracy: 0.82 },
  { epoch: 25, accuracy: 0.86 },
  { epoch: 30, accuracy: 0.89 },
]

export const schedulerTiers = [
  { name: 'Cloud', count: 3, avgLoad: 59, tasks: 24, color: '#6366f1' },
  { name: 'Edge', count: 3, avgLoad: 51, tasks: 15, color: '#0EA5E9' },
  { name: 'Device', count: 2, avgLoad: 23, tasks: 3, color: '#10B981' },
]

export const migrationHistory = [
  { task: 'T-0998', from: 'Edge', to: 'Cloud', reason: 'overload', time: '14:05', status: 'success' },
  { task: 'T-0995', from: 'Device', to: 'Edge', reason: 'capability', time: '13:42', status: 'success' },
  { task: 'T-0991', from: 'Cloud', to: 'Edge', reason: 'latency', time: '13:20', status: 'success' },
  { task: 'T-0987', from: 'Edge', to: 'Device', reason: 'cost', time: '12:55', status: 'failed' },
]

export const guardrailRules = [
  { id: 'GR-001', name: 'PII Detection', type: 'output', blocked: 12, active: true },
  { id: 'GR-002', name: 'Prompt Injection', type: 'input', blocked: 5, active: true },
  { id: 'GR-003', name: 'Toxicity Filter', type: 'output', blocked: 3, active: true },
  { id: 'GR-004', name: 'Rate Limit', type: 'input', blocked: 28, active: true },
]
