# NexusFlow 使用指南

## 1. 安装与启动

### 1.1 环境要求

- Python 3.10+
- [Ollama](https://ollama.com/) 已安装并运行
- DeepSeek API Key（可选，用于云端Agent）

### 1.2 安装步骤

```bash
# 克隆仓库
git clone https://github.com/your-org/nexusflow.git
cd nexusflow

# 安装依赖
pip install -r requirements.txt

# 安装Ollama模型
ollama pull deepseek-r1:14b
ollama pull qwen3.5:9b

# 配置环境变量
cp config/.env.example .env
# 编辑 .env 填入 DEEPSEEK_API_KEY
```

### 1.3 启动服务

```bash
# Windows
start.bat

# Linux/Mac
python server/nexusflow_server.py
```

启动后访问：**http://localhost:8900**

## 2. 核心概念

### 2.1 CDoL 认知分工

CDoL（Cognitive Division of Labor）通过制造信息不对称来驱动深度协作：

- **不是**让多个Agent各自推理后汇总
- **而是**主动限制每个Agent的信息，迫使它们发展逆向推断能力

### 2.2 三轮通信

| 轮次 | 说明 |
|------|------|
| Round 0 | Agent独立推理，仅看到自己的视角 |
| Round 1 | Agent看到他人结论，推断"对方可能看到了什么" |
| Round 2 | Agent修正结论，产出最终答案 |

### 2.3 任务路由

NexusOrchestrator 自动判断任务类型并选择路由：

| 路由 | 适用场景 |
|------|---------|
| simple | 简单问答、翻译 |
| research | 信息检索、文献查找 |
| coding | 代码生成、调试 |
| cdol | 复杂分析、多角度对比 |

## 3. 配置说明

### 3.1 环境变量

```env
# DeepSeek API（云端Agent）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_ENDPOINT=https://api.deepseek.com/v1/chat/completions

# Ollama（本地Agent）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_PRO_MODEL=deepseek-r1:14b
OLLAMA_LITE_MODEL=qwen3.5:9b

# 服务端口
DASHBOARD_PORT=8900
```

### 3.2 Ollama 配置优化

在 `start.bat` 中已配置并行参数：

```bat
set OLLAMA_NUM_PARALLEL=4
set OLLAMA_MAX_LOADED_MODELS=2
set OLLAMA_FLASH_ATTENTION=1
```

## 4. Dashboard 使用

### 4.1 提交任务

在输入框中描述任务，点击「开始协作」。

### 4.2 监控执行

- **Agent状态**：实时查看每个Agent的状态（思考中/等待中/完成）
- **CDoL Pipeline**：可视化三轮通信进度
- **FusionJudge**：矛盾检测与融合结果
- **LazinessDetector**：懒惰检测指标

### 4.3 查看结果

任务完成后自动显示结果，支持复制和下载。

## 5. API 接口

### 5.1 创建任务

```bash
POST /api/tasks
Content-Type: application/json

{
  "description": "分析蛋白质折叠问题并给出实验方案",
  "max_steps": 5
}
```

### 5.2 查询任务

```bash
GET /api/tasks/{task_id}
```

### 5.3 下载结果

```bash
GET /api/tasks/{task_id}/download
```

## 6. 常见问题

### Q: Ollama 模型下载失败？

```bash
# 检查Ollama是否运行
curl http://localhost:11434/api/tags

# 重新拉取模型
ollama pull deepseek-r1:14b
```

### Q: DeepSeek API 调用失败？

检查 `.env` 文件中的 `DEEPSEEK_API_KEY` 是否正确配置。

### Q: Dashboard 无法连接？

确认服务已启动，端口 8900 未被占用。

## 7. 扩展开发

### 7.1 自定义Agent

继承 `BaseAgent` 类：

```python
from base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, agent_id: str, llm_chat):
        super().__init__(
            agent_id=agent_id,
            name="我的Agent",
            llm_chat=llm_chat,
            role="分析师",
            capabilities=["数据分析"],
        )
```

### 7.2 添加分解策略

扩展 `PerspectiveDecomposer`：

```python
PerspectiveDecomposer.STRATEGY_PROMPTS["my_strategy"] = (
    "描述你的策略..."
)
```

---

*文档版本：v1.1*
