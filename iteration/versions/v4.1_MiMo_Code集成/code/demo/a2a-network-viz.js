/**
 * 铉枢 A2A 网络拓扑可视化
 * XuanHub A2A Network Topology Visualization
 * 
 * 借鉴Mira像素风办公室思路：Agent状态拟人化可视化
 * - 实时显示8个Agent节点和A2A连接
 * - 节点颜色/动画反映Agent状态（idle/working/error）
 * - 连线粗细反映通信频率
 * - 点击节点查看Agent详情（模型、模式、任务队列）
 */

class A2ANetworkViz {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        
        // 配置
        this.config = {
            nodeRadius: 28,
            fontSize: 11,
            labelOffset: 38,
            lineWidth: 1.5,
            animSpeed: 0.02,
            glowIntensity: 12,
            ...options
        };
        
        // Agent定义
        this.agents = {
            miner:     { label: '矿工', emoji: '⛏️', model: 'pro',   role: 'explorer',  x: 0, y: 0 },
            assayer:   { label: '试金', emoji: '🔍', model: 'flash', role: 'validator', x: 0, y: 0 },
            caster:    { label: '铸师', emoji: '⚒️', model: 'pro',   role: 'generator', x: 0, y: 0 },
            artisan:   { label: '匠人', emoji: '✨', model: 'flash', role: 'explainer', x: 0, y: 0 },
            planner:   { label: '规划', emoji: '📋', model: 'pro',   role: 'strategist',x: 0, y: 0 },
            executor:  { label: '执行', emoji: '⚡', model: 'flash', role: 'runner',    x: 0, y: 0 },
            researcher:{ label: '研究', emoji: '🔬', model: 'pro',   role: 'analyst',   x: 0, y: 0 },
            reviewer:  { label: '审查', emoji: '🛡️', model: 'flash', role: 'gate',      x: 0, y: 0 },
        };
        
        // A2A连接（有向边）
        this.connections = [
            { from: 'planner',    to: 'miner',      label: '下发探索',  weight: 3 },
            { from: 'planner',    to: 'caster',     label: '下发生成',  weight: 3 },
            { from: 'miner',      to: 'assayer',    label: '发现→验证', weight: 4 },
            { from: 'caster',     to: 'artisan',    label: '方案→整合', weight: 4 },
            { from: 'assayer',    to: 'reviewer',   label: '验证→审核', weight: 2 },
            { from: 'artisan',    to: 'reviewer',   label: '成果→审核', weight: 2 },
            { from: 'reviewer',   to: 'planner',    label: '反馈→重规划',weight: 2 },
            { from: 'planner',    to: 'executor',   label: '计划→执行', weight: 3 },
            { from: 'executor',   to: 'reviewer',   label: '结果→审核', weight: 2 },
            { from: 'researcher', to: 'assayer',    label: '线索→验证', weight: 2 },
            { from: 'researcher', to: 'miner',      label: '辅助探索',  weight: 1 },
        ];
        
        // 状态
        this.agentStates = {};  // { id: 'idle'|'working'|'error' }
        this.selectedAgent = null;
        this.animFrame = 0;
        this.particles = [];
        
        // 初始化状态
        Object.keys(this.agents).forEach(id => {
            this.agentStates[id] = 'idle';
        });
        
        this._layoutNodes();
        this._bindEvents();
        this._animate();
    }
    
    // 布局：环形 + 内外圈
    _layoutNodes() {
        const w = this.canvas.width;
        const h = this.canvas.height;
        const cx = w / 2;
        const cy = h / 2;
        
        // 内圈4个（核心生产链）
        const inner = ['miner', 'assayer', 'caster', 'artisan'];
        const innerR = Math.min(w, h) * 0.22;
        inner.forEach((id, i) => {
            const angle = (i / inner.length) * Math.PI * 2 - Math.PI / 2;
            this.agents[id].x = cx + Math.cos(angle) * innerR;
            this.agents[id].y = cy + Math.sin(angle) * innerR;
        });
        
        // 外圈4个（管理/支撑）
        const outer = ['planner', 'executor', 'researcher', 'reviewer'];
        const outerR = Math.min(w, h) * 0.38;
        outer.forEach((id, i) => {
            const angle = (i / outer.length) * Math.PI * 2 - Math.PI / 4;
            this.agents[id].x = cx + Math.cos(angle) * outerR;
            this.agents[id].y = cy + Math.sin(angle) * outerR;
        });
    }
    
    _bindEvents() {
        this.canvas.addEventListener('click', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            
            this.selectedAgent = null;
            Object.entries(this.agents).forEach(([id, agent]) => {
                const dx = mx - agent.x;
                const dy = my - agent.y;
                if (dx * dx + dy * dy < this.config.nodeRadius * this.config.nodeRadius) {
                    this.selectedAgent = id;
                }
            });
        });
    }
    
    // 更新Agent状态
    updateState(agentId, state) {
        if (this.agentStates.hasOwnProperty(agentId)) {
            this.agentStates[agentId] = state;
        }
    }
    
    // 批量更新
    updateAllStates(states) {
        Object.entries(states).forEach(([id, state]) => {
            this.updateState(id, state);
        });
    }
    
    _animate() {
        this.animFrame++;
        this._draw();
        requestAnimationFrame(() => this._animate());
    }
    
    _draw() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        
        ctx.clearRect(0, 0, w, h);
        
        // 绘制连线
        this.connections.forEach(conn => {
            this._drawConnection(conn);
        });
        
        // 绘制粒子
        this._updateParticles();
        this.particles.forEach(p => this._drawParticle(p));
        
        // 绘制节点
        Object.entries(this.agents).forEach(([id, agent]) => {
            this._drawNode(id, agent);
        });
        
        // 绘制选中Agent详情
        if (this.selectedAgent) {
            this._drawDetail(this.selectedAgent);
        }
    }
    
    _drawConnection(conn) {
        const ctx = this.ctx;
        const from = this.agents[conn.from];
        const to = this.agents[conn.to];
        if (!from || !to) return;
        
        const stateColors = {
            idle: 'rgba(100, 140, 200, 0.3)',
            working: 'rgba(80, 200, 120, 0.5)',
            error: 'rgba(200, 80, 80, 0.5)',
        };
        
        const fromState = this.agentStates[conn.from] || 'idle';
        const toState = this.agentStates[conn.to] || 'idle';
        const active = fromState === 'working' || toState === 'working';
        
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.strokeStyle = active ? 'rgba(80, 200, 120, 0.6)' : 'rgba(100, 140, 200, 0.2)';
        ctx.lineWidth = conn.weight * (active ? 1.5 : 0.8);
        ctx.stroke();
        
        // 箭头
        const angle = Math.atan2(to.y - from.y, to.x - from.x);
        const arrowDist = this.config.nodeRadius + 8;
        const ax = to.x - Math.cos(angle) * arrowDist;
        const ay = to.y - Math.sin(angle) * arrowDist;
        
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax - 8 * Math.cos(angle - 0.4), ay - 8 * Math.sin(angle - 0.4));
        ctx.lineTo(ax - 8 * Math.cos(angle + 0.4), ay - 8 * Math.sin(angle + 0.4));
        ctx.closePath();
        ctx.fillStyle = active ? 'rgba(80, 200, 120, 0.7)' : 'rgba(100, 140, 200, 0.3)';
        ctx.fill();
        
        // 活跃时生成粒子
        if (active && Math.random() < 0.05) {
            this.particles.push({
                x: from.x, y: from.y,
                tx: to.x, ty: to.y,
                progress: 0,
                speed: 0.01 + Math.random() * 0.02,
                color: 'rgba(80, 200, 120, 0.8)',
            });
        }
    }
    
    _updateParticles() {
        this.particles = this.particles.filter(p => {
            p.progress += p.speed;
            p.x = p.x + (p.tx - p.x) * p.speed * 2;
            p.y = p.y + (p.ty - p.y) * p.speed * 2;
            return p.progress < 1;
        });
    }
    
    _drawParticle(p) {
        const ctx = this.ctx;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.fill();
    }
    
    _drawNode(id, agent) {
        const ctx = this.ctx;
        const r = this.config.nodeRadius;
        const state = this.agentStates[id] || 'idle';
        const selected = this.selectedAgent === id;
        
        // 颜色映射
        const stateColors = {
            idle:    { bg: '#1a2540', border: '#2a4070', glow: '#4a7acc' },
            working: { bg: '#1a3020', border: '#2a6040', glow: '#40cc80' },
            error:   { bg: '#301a1a', border: '#602a2a', glow: '#cc4040' },
        };
        const colors = stateColors[state];
        
        // 选中光环
        if (selected) {
            ctx.beginPath();
            ctx.arc(agent.x, agent.y, r + 6, 0, Math.PI * 2);
            ctx.strokeStyle = colors.glow;
            ctx.lineWidth = 2;
            ctx.stroke();
        }
        
        // 工作状态脉冲
        if (state === 'working') {
            const pulse = Math.sin(this.animFrame * this.config.animSpeed * 3) * 0.3 + 0.7;
            ctx.beginPath();
            ctx.arc(agent.x, agent.y, r + 3 + pulse * 4, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(64, 204, 128, ${0.2 * pulse})`;
            ctx.lineWidth = 1;
            ctx.stroke();
        }
        
        // 发光效果
        const glow = ctx.createRadialGradient(agent.x, agent.y, r * 0.5, agent.x, agent.y, r * 1.5);
        glow.addColorStop(0, colors.glow + '20');
        glow.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(agent.x, agent.y, r * 1.5, 0, Math.PI * 2);
        ctx.fillStyle = glow;
        ctx.fill();
        
        // 节点圆
        ctx.beginPath();
        ctx.arc(agent.x, agent.y, r, 0, Math.PI * 2);
        ctx.fillStyle = colors.bg;
        ctx.fill();
        ctx.strokeStyle = selected ? colors.glow : colors.border;
        ctx.lineWidth = selected ? 2 : 1;
        ctx.stroke();
        
        // Emoji
        ctx.font = '18px serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(agent.emoji, agent.x, agent.y - 2);
        
        // 标签
        ctx.font = `${this.config.fontSize}px "SF Mono", "Cascadia Code", monospace`;
        ctx.fillStyle = colors.glow;
        ctx.fillText(agent.label, agent.x, agent.y + this.config.labelOffset);
        
        // 模型标签
        ctx.font = '9px "SF Mono", monospace';
        ctx.fillStyle = 'rgba(150, 170, 200, 0.6)';
        const modelLabel = agent.model === 'pro' ? 'PRO' : 'FLS';
        ctx.fillText(modelLabel, agent.x + r + 4, agent.y - 4);
        
        // 状态指示灯
        const indicatorColor = state === 'working' ? '#40cc80' : state === 'error' ? '#cc4040' : '#4a7acc';
        ctx.beginPath();
        ctx.arc(agent.x + r - 4, agent.y - r + 6, 3, 0, Math.PI * 2);
        ctx.fillStyle = indicatorColor;
        ctx.fill();
    }
    
    _drawDetail(agentId) {
        const ctx = this.ctx;
        const agent = this.agents[agentId];
        const state = this.agentStates[agentId] || 'idle';
        
        // 详情卡片
        const cardW = 180;
        const cardH = 100;
        const cardX = agent.x + this.config.nodeRadius + 20;
        const cardY = agent.y - cardH / 2;
        
        // 修正边界
        const adjustedX = Math.min(cardX, this.canvas.width - cardW - 10);
        const adjustedY = Math.max(10, Math.min(cardY, this.canvas.height - cardH - 10));
        
        // 背景
        ctx.fillStyle = 'rgba(10, 12, 20, 0.9)';
        ctx.strokeStyle = 'rgba(74, 122, 204, 0.5)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(adjustedX, adjustedY, cardW, cardH, 8);
        ctx.fill();
        ctx.stroke();
        
        // 内容
        ctx.font = 'bold 12px "SF Mono", monospace';
        ctx.fillStyle = '#7aacff';
        ctx.textAlign = 'left';
        ctx.fillText(`${agent.emoji} ${agent.label} (${agentId})`, adjustedX + 10, adjustedY + 20);
        
        ctx.font = '10px "SF Mono", monospace';
        ctx.fillStyle = 'rgba(180, 200, 230, 0.8)';
        ctx.fillText(`Model: ${agent.model === 'pro' ? 'DeepSeek V4 Pro' : 'DeepSeek V4 Flash'}`, adjustedX + 10, adjustedY + 40);
        ctx.fillText(`Role: ${agent.role}`, adjustedX + 10, adjustedY + 56);
        ctx.fillText(`State: ${state}`, adjustedX + 10, adjustedY + 72);
        
        const modeText = state === 'working' ? '● Processing...' : state === 'error' ? '✕ Error' : '○ Idle';
        ctx.fillStyle = state === 'working' ? '#40cc80' : state === 'error' ? '#cc4040' : '#4a7acc';
        ctx.fillText(modeText, adjustedX + 10, adjustedY + 88);
    }
    
    resize() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this._layoutNodes();
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { A2ANetworkViz };
}
