# NexusFlow

> 面向超长程复杂任务的群体智能引擎

**NexusFlow** 是一个基于认知分工（Cognitive Division of Labor, CDoL）的多智能体协作框架。不同于传统的任务分割式多Agent系统，NexusFlow 通过**主动制造信息不对称**，迫使每个Agent发展出从他人输出中逆向推断对方所见上下文的能力，从而产生超越任何单Agent的推理深度。

---

## 核心特性

- **CDoL 认知分工引擎**：六种视角分解策略 + 三轮有损通信协议 + 虚假一致检测
- **自适应上下文管理**：解决"大窗口懒惰症"，动态调节Agent上下文窗口
- **三层信息架构**：全局视野层 / CDoL参与层 / 旁观记录层
- **动态拓扑路由**：运行时重建Agent协作图，支持五种拓扑模式
- **端边云三层调度**：隐私优先调度，支持本地Ollama + 云端DeepSeek
- **10个专用Agent角色**：Coordinator、Strategist、Coder、Researcher、Analyst、Critic、Synthesizer、Archivist、Observer、Monitor

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        NexusFlow 系统架构                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  用户    │───▶│  Dashboard   │◀──▶│  FastAPI Server      │   │
│  │         │    │  (WebSocket) │    │                      │   │
│  └─────────┘    └──────────────┘    └──────────┬───────────┘   │
│                                                │                │
│                           ┌────────────────────┼───────────┐   │
│                           ▼                                 ▼   │
│                   ┌───────────────┐              ┌──────────┐ │
│                   │ NexusOrchestrator │              │ LLM Router│ │
│                   └───────┬───────┘              └────┬─────┘ │
│                           │                             │       │
│         ┌─────────────────┼─────────────────────────┤       │
│         ▼                 ▼                         ▼       │
│  ┌────────────┐    ┌────────────┐    ┌──────────────────────┐ │
│  │ CDoL Engine│    │   Memory   │    │  Agent Pool (10个)   │ │
│  │            │    │  Manager   │    │                      │ │
│  │ • Round 0  │    │            │    │ ☁️ Cloud:           │ │
│  │ • Round 1  │    │  • Vector  │    │   Coordinator       │ │
│  │ • Round 2  │    │  • Recall  │    │   Strategist        │ │
│  │ • Fusion   │    │  • Archival│    │   Archivist         │ │
│  │            │    │            │    │   Critic            │ │
│  └────────────┘    └────────────┘    │   Synthesizer       │ │
│                                       │   Researcher        │ │
│                                       ├──────────────────────┤ │
│                                       │ 🖥️ Edge:           │ │
│                                       │   Coder             │ │
│                                       │   Analyst           │ │
│                                       ├──────────────────────┤ │
│                                       │ 📱 Endpoint:        │ │
│                                       │   Observer          │ │
│                                       │   Monitor          │ │
│                                       └──────────────────────┘ │
│                                                        │       │
│                         ┌───────────────────────────────┼───┐   │
│                         ▼                               ▼   │   │
│                  ┌─────────────┐              ┌─────────────┐ │   │
│                  │   Ollama    │              │  DeepSeek   │ │   │
│                  │  (本地)     │              │   (云端)    │ │   │
│                  │ deepseek-r1 │              │ deepseek-chat│ │   │
│                  │ qwen3.5    │              │             │ │   │
│                  └─────────────┘              └─────────────┘ │   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 端边云三层架构

| 层级 | 模型 | Agent | 说明 |
|------|------|-------|------|
| ☁️ 云端 | DeepSeek API | Coordinator, Strategist, Archivist, Critic, Synthesizer, Researcher | 高质量推理 + 广知识 |
| 🖥️ 边端 | Ollama deepseek-r1:14b | Coder, Analyst | 本地大模型，计算密集任务 |
| 📱 终端 | Ollama qwen3.5:9b | Observer, Monitor | 本地小模型，轻量监控 |

---

## 快速开始

### 环境要求

- Python 3.10+
- [Ollama](https://ollama.com/) (本地部署)
- DeepSeek API Key (可选，用于云端Agent)

### 安装

```bash
# 克隆仓库
git clone https://github.com/tsingxuanhan/NexusFlow.git
cd NexusFlow

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp config/.env.example .env
# 编辑 .env 填入你的 API Key
```

### 启动

```bash
# Windows
config\start.bat

# Linux/Mac
python server/nexusflow_server.py
```

访问 Dashboard: http://localhost:8900

---

## 配置说明

### 环境变量 (.env)

```env
# DeepSeek API
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_PRO_MODEL=deepseek-r1:14b
OLLAMA_LITE_MODEL=qwen3.5:9b

# Dashboard
DASHBOARD_PORT=8900
```

### Ollama 模型安装

```bash
ollama pull deepseek-r1:14b
ollama pull qwen3.5:9b
```

---

## Agent 角色表

| Agent | 角色 | 层级 | 职责 |
|-------|------|------|------|
| 🧭 Coordinator | 编排者 | ☁️ 全局 | 任务分发、进度协调、冲突裁决 |
| 📚 Archivist | 档案师 | ☁️ 全局 | 经验蒸馏、知识沉淀 |
| 🧩 Strategist | 策略师 | 🔗 CDoL | 任务分解、视角设计 |
| 🔥 Critic | 批评家 | 🔗 CDoL | 对抗质疑、逻辑审查 |
| 🔬 Synthesizer | 整合师 | 🔗 CDoL | 多视角融合、矛盾解决 |
| 🔍 Researcher | 研究员 | 🔗 CDoL | 联网搜索、文献分析 |
| 💻 Coder | 编码师 | 🖥️ CDoL | 代码开发、工具实现 |
| 📊 Analyst | 分析师 | 🖥️ CDoL | 数据分析、模式识别 |
| 👁 Observer | 观察者 | 📱 旁观 | 元观察、偏见检测 |
| 📡 Monitor | 监控者 | 📱 旁观 | 健康检查、异常检测 |

---

## 技术架构

详见 [docs/architecture.md](docs/architecture.md)

---

## License

MIT License - 详见 [LICENSE](LICENSE)

---

## 参考资料

- [Braintrust AI Evaluation Platform](https://www.braintrust.dev/) - 框架vs模型实证数据
- [清华大学 & OpenBMB - 大窗口懒惰症研究](https://arxiv.org/abs/2606.15378)
- [Arbor - Hypothesis-Tree Refinement](https://arxiv.org/abs/2606.11926)
