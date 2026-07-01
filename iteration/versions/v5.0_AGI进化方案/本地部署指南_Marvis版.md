# xuanshu-agents v5.0 本地部署指南
## 配合腾讯Marvis执行

---

## 一、硬件确认

| 项目 | 你的配置 | v5.0要求 |
|------|----------|----------|
| CPU | i9-12900H (14C/20T) | ✅ 远超 |
| RAM | 32GB | ✅ P0+P1+P2全跑（需~1.5GB） |
| GPU | RTX 3080 Ti 16GB VRAM | ✅ 可跑qwen2.5:14b主力 |
| 存储 | 401GB可用 | ✅ 模型约需25GB |
| OS | Windows 11 64-bit | ✅ |

**结论：你的电脑可以完整运行v5.0全部三个Phase，无需任何阉割。**

---

## 二、部署架构

```
你的电脑 (Win11)
├── Marvis (桌面管家，日常操作用)
├── Ollama (本地模型服务)
│   ├── qwen2.5:14b → 主力推理（铸师/矿工）
│   ├── qwen2.5:7b  → 快速响应（试金石/匠人）
│   └── deepseek-coder:6.7b → 代码专用
├── xuanshu-agents v5.0 (研究框架)
│   ├── P0 轻量核心层 (~400MB RAM)
│   ├── P1 增强层 (~950MB RAM)
│   └── P2 完整层 (~150MB RAM)
├── SQLite + 向量索引 (本地数据库)
└── 知识库v2 (524篇论文)
```

**端口分配：**
- Ollama: 127.0.0.1:11434
- xuanshu-agents API: 127.0.0.1:8000
- 全部走127.0.0.1，不暴露外网

---

## 三、部署步骤（交给Marvis执行）

> 以下每一步都可以直接复制给Marvis执行。
> 建议在**隐私模式**下执行（数据不出本机）。

---

### Step 0: 检查基础环境

把这段话发给Marvis：

```
请帮我检查以下环境，在终端执行命令并把结果告诉我：
1. python --version
2. pip --version
3. git --version
4. nvidia-smi
5. 查看 C:\Users 下有没有 .ollama 目录
把每条命令的输出都列出来。
```

**期望结果：**
- Python: 3.10+ （如果没有，下一步装）
- pip: 任意版本
- git: 任意版本
- nvidia-smi: 应显示RTX 3080 Ti 16GB
- .ollama: 可能不存在

---

### Step 1: 安装Ollama

把这段话发给Marvis：

```
帮我执行以下操作：

1. 用浏览器打开 https://ollama.com/download/windows
2. 下载 Windows 安装包（应该自动开始）
3. 等下载完成后，运行安装程序
4. 安装完成后，在终端执行 `ollama --version` 确认安装成功
5. 启动Ollama服务：在终端执行 `ollama serve`（后台运行）
```

**验证：** 浏览器打开 http://127.0.0.1:11434 应显示 "Ollama is running"

---

### Step 2: 拉取模型

把这段话发给Marvis：

```
请在终端依次执行以下命令（每个模型需要下载，耐心等待）：

1. ollama pull qwen2.5:14b
2. ollama pull qwen2.5:7b
3. ollama pull deepseek-coder:6.7b

每个完成后用 `ollama list` 确认。最后告诉我每个模型的大小。
```

**模型大小预估：**
| 模型 | 大小 | 用途 |
|------|------|------|
| qwen2.5:14b | ~9GB | 主力推理（矿工/铸师） |
| qwen2.5:7b | ~4.5GB | 快速响应（试金石/匠人） |
| deepseek-coder:6.7b | ~4GB | 代码生成 |
| **合计** | **~17.5GB** | 你的存储还剩401GB，足够 |

---

### Step 3: 验证模型

把这段话发给Marvis：

```
请在终端执行以下测试：

1. ollama run qwen2.5:14b "你好，请用一句话介绍自己"
2. ollama run qwen2.5:7b "1+1等于几"
3. ollama run deepseek-coder:6.7b "用Python写一个hello world"

每个测完告诉我响应速度和结果质量。
```

---

### Step 4: 创建项目目录

把这段话发给Marvis：

```
请在 D盘（或其他你想放的盘）创建以下目录结构：

D:\xuanshu-agents\
├── v5.0\
│   ├── core\          # 核心框架代码
│   ├── config\        # 配置文件
│   ├── data\          # 数据（知识库、向量索引）
│   ├── logs\          # 运行日志
│   └── tests\         # 测试脚本

用命令：
mkdir D:\xuanshu-agents\v5.0\core
mkdir D:\xuanshu-agents\v5.0\config
mkdir D:\xuanshu-agents\v5.0\data
mkdir D:\xuanshu-agents\v5.0\logs
mkdir D:\xuanshu-agents\v5.0\tests
```

---

### Step 5: 克隆仓库

把这段话发给Marvis：

```
请在终端执行：

cd D:\xuanshu-agents\v5.0\core
git clone https://github.com/Simple-Logic/xuanshu-agents.git .

如果git clone失败（网络问题），试试：
git clone https://ghproxy.com/https://github.com/Simple-Logic/xuanshu-agents.git .

克隆完成后，用 `ls` 或 `dir` 告诉我目录里有什么文件。
```

> ⚠️ 注意：当前GitHub仓库可能还没有v5.0代码，需要先推送。
> 如果仓库为空，先跳过这步，等代码准备好再clone。

---

### Step 6: 安装Python依赖

把这段话发给Marvis：

```
请在终端执行以下命令：

cd D:\xuanshu-agents\v5.0\core

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装基础依赖
pip install numpy scipy scikit-learn sqlite-utils requests

# 安装v5.0新增依赖（P0）
pip install pyactup dowhy ewc

# 安装v5.0新增依赖（P1）
pip install causal-learn dspy-ai

# 安装v5.0新增依赖（P1 Grounding）
pip install browsergym

# 安装开发工具
pip install pytest black

安装完成后，执行 `pip list` 告诉我所有已安装的包。
```

> ⚠️ 注意：部分pip包名可能与实际不同，我会在代码推送前确认准确的包名。
> 如果某个包安装失败，告诉我错误信息，我来解决。

---

### Step 7: 配置环境变量

把这段话发给Marvis：

```
请在终端执行以下命令设置环境变量（当前会话有效）：

set OLLAMA_BASE_URL=http://127.0.0.1:11434
set XUANSHU_ENV=local
set XUANSHU_DATA_DIR=D:\xuanshu-agents\v5.0\core\data
set XUANSHU_LOG_DIR=D:\xuanshu-agents\v5.0\core\logs

如果要永久生效，请在系统环境变量里添加以上四个变量：
- 右键"此电脑" → 属性 → 高级系统设置 → 环境变量
- 在"用户变量"中新建以上四个
```

---

### Step 8: 初始化数据库和知识库

把这段话发给Marvis：

```
请在终端执行：

cd D:\xuanshu-agents\v5.0\core
.venv\Scripts\activate

# 初始化SQLite数据库
python -c "import sqlite3; conn = sqlite3.connect('D:/xuanshu-agents/v5.0/data/xuanshu.db'); conn.execute('CREATE TABLE IF NOT EXISTS papers (id INTEGER PRIMARY KEY, title TEXT, abstract TEXT, category TEXT); print(\"数据库初始化成功\")')"

# 检查知识库数据（如果有的话）
python -c "import sqlite3; conn = sqlite3.connect('D:/xuanshu-agents/v5.0/data/xuanshu.db'); cursor = conn.execute('SELECT COUNT(*) FROM papers'); print(f'知识库条目: {cursor.fetchone()[0]}')"
```

> ⚠️ 知识库v2的数据需要从云电脑迁移过来，或者重新从论文列表导入。
> 我会单独准备知识库迁移脚本。

---

### Step 9: 运行框架测试

把这段话发给Marvis：

```
请在终端执行：

cd D:\xuanshu-agents\v5.0\core
.venv\Scripts\activate

# 运行基础测试
python -c "
from core.base_agent import BaseAgent
from core.providers import NGramTFIDFProvider
print('✅ 核心模块导入成功')

# 测试Ollama连接
import requests
resp = requests.get('http://127.0.0.1:11434/api/tags')
models = resp.json().get('models', [])
print(f'✅ Ollama可用，已加载模型: {[m[\"name\"] for m in models]}')

# 测试单Agent对话
agent = BaseAgent(role='miner', model='qwen2.5:14b')
response = agent.chat('你好，测试连接')
print(f'✅ Agent响应: {response[:100]}...')

print('🎉 基础测试全部通过！')
"
```

---

### Step 10: 启动完整系统

```
cd D:\xuanshu-agents\v5.0\core
.venv\Scripts\activate
python main.py
```

**期望输出：**
```
╔══════════════════════════════════════╗
║    xuanshu-agents v5.0 启动中...     ║
║    认知飞轮: 6/6 维度已激活          ║
║    矿工: qwen2.5:14b  ✅             ║
║    试金石: qwen2.5:7b  ✅            ║
║    铸师: qwen2.5:14b  ✅             ║
║    匠人: deepseek-coder:6.7b  ✅     ║
║    知识库: 524篇论文  ✅              ║
║    服务地址: 127.0.0.1:8000          ║
╚══════════════════════════════════════╝
```

---

## 四、Marvis配合技巧

### 日常使用Marvis管理xuanshu-agents

| 场景 | 对Marvis说 |
|------|-----------|
| 启动框架 | "在终端执行 `cd D:\xuanshu-agents\v5.0\core && .venv\Scripts\activate && python main.py`" |
| 查看日志 | "帮我看看 D:\xuanshu-agents\v5.0\logs 目录下最新的日志文件" |
| 检查模型状态 | "在终端执行 `ollama list` 和 `ollama ps`" |
| 清理空间 | "帮我清理 D:\xuanshu-agents\v5.0\logs 下超过7天的日志" |
| 备份数据 | "把 D:\xuanshu-agents\v5.0\data 目录备份到 D:\backup\xuanshu_日期" |

### 隐私建议

- 处理论文/研究数据时 → Marvis切**隐私模式**
- 日常文件整理/系统维护 → Marvis用**效率模式**
- xuanshu-agents全程走127.0.0.1，不经过Marvis的云端

---

## 五、RAM预算（32GB环境）

| 组件 | RAM占用 | 说明 |
|------|---------|------|
| Windows 11 系统 | ~5GB | 基础开销 |
| Marvis (效率模式) | ~1.5GB | 含云端通信 |
| Ollama服务 | ~0.5GB | 进程本身 |
| qwen2.5:14b (VRAM) | ~9GB | 占用显存 |
| qwen2.5:7b (VRAM) | ~4.5GB | 占用显存（按需加载） |
| deepseek-coder (VRAM) | ~4GB | 占用显存（按需加载） |
| xuanshu-agents P0 | ~400MB | 认知模块 |
| xuanshu-agents P1 | ~550MB | 增强模块 |
| xuanshu-agents P2 | ~150MB | 完整模块 |
| Python运行时 | ~500MB | 基础 |
| SQLite + 向量索引 | ~200MB | 数据层 |
| **合计** | **~27GB** | 还剩5GB余量 |

> 注：Ollama模型在VRAM中运行，不占用系统RAM。
> 如果VRAM不够同时加载三个模型，Ollama会自动做LRU调度，按需加载。

---

## 六、故障排查

| 问题 | 解决 |
|------|------|
| `ollama serve` 报错端口被占 | `netstat -ano \| findstr 11434` 找到占用进程，kill掉 |
| 模型下载慢 | 用Marvis效率模式开代理，或手动设置 `set OLLAMA_HOST=...` |
| pip install pyactup 失败 | 试试 `pip install pyactup --pre` 或从GitHub装 |
| Python版本不对 | 去 python.org 下载 3.11，安装时勾选"Add to PATH" |
| VRAM不足 | 关闭其他GPU占用程序（游戏、浏览器硬件加速），Ollama会自动管理 |
| 知识库导入失败 | 检查SQLite路径权限，确保D盘可写 |

---

## 七、部署清单

- [ ] Step 0: 检查基础环境
- [ ] Step 1: 安装Ollama
- [ ] Step 2: 拉取3个模型
- [ ] Step 3: 验证模型可用
- [ ] Step 4: 创建项目目录
- [ ] Step 5: 克隆仓库（等代码推送后）
- [ ] Step 6: 安装Python依赖
- [ ] Step 7: 配置环境变量
- [ ] Step 8: 初始化数据库
- [ ] Step 9: 运行测试
- [ ] Step 10: 启动完整系统

---

*生成日期: 2026-06-13*
*适配环境: Windows 11 + i9-12900H + 32GB RAM + RTX 3080 Ti 16GB*
