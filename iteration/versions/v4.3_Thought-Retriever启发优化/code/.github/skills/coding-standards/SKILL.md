---
name: coding-standards
description: >
  xuanshu-agents 仓库编码规范。定义文件命名、模块结构、文档字符串、
  类型注解、错误处理、日志、测试等标准。当创建新模块、修改现有代码、
  或进行代码审查时必须遵守此规范。
license: MIT
metadata:
  version: "3.3.0"
  scope: repository-wide
---

# xuanshu-agents 编码规范

## 1. 文件与目录

### 命名
| 类型 | 规则 | 示例 |
|------|------|------|
| 模块文件 | snake_case.py | `base_agent.py`, `vector_memory.py` |
| 包目录 | snake_case/ | `agents/`, `tools/` |
| Skill 目录 | kebab-case/ | `.github/skills/quality-control/` |
| 测试文件 | test_{module}.py | `test_vector_memory.py` |
| 配置文件 | lowercase | `config.py`, `requirements.txt` |
| 知识文件 | kebab-case.md | `low-carbon-cement-systems.md` |

### 模块结构 (每个 .py 文件)
```python
# -*- coding: utf-8 -*-
"""
中文模块名 — 一句话描述
English Module Name - One-line description
"""

import 标准库
import 第三方库
import 项目内模块

# 常量 (UPPER_SNAKE_CASE)
MAX_RETRIES = 3

# 类定义
class MyClass:
    """中文类描述

    English class description
    """

# 函数定义
def my_function(param: str) -> bool:
    """一句话描述

    Args:
        param: 参数说明

    Returns:
        返回值说明
    """
```

### 目录规范
```
xuanshu-agents/
├── .github/skills/        # Agent Skills 规范描述 (每个模块一个 SKILL.md)
├── agents/                # 业务Agent实现
├── tools/                 # 工具框架
├── knowledge/             # 领域知识库
├── examples/              # 使用示例
├── control-panel/         # Web控制面板
├── demo/                  # UI演示
├── docs/                  # 项目文档
├── reports/               # 运行报告
├── scripts/               # 运维脚本
├── data/                  # 运行时数据 (gitignore)
└── archive/               # 历史备份 (gitignore)
```

## 2. 文档字符串

### 双语规则
- 模块级和类级 docstring: 中文 + 英文
- 方法级 docstring: 仅中文 (简洁优先)
- SKILL.md: 中文为主，技术术语用英文

### 格式
```python
def method(self, param: str) -> Optional[str]:
    """一句话描述做什么

    Args:
        param: 参数说明

    Returns:
        返回值说明，None时说明原因
    """
```

## 3. 类型注解

**必须** 为所有公开方法添加类型注解：
```python
# ✓ 正确
def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:

# ✗ 错误
def search(self, query, top_k=5):
```

内部私有方法 (`_method`) 鼓励但不强制。

## 4. 错误处理

### 分层策略
```python
# 外部API调用 → 熔断器 + 降级
with self.api_circuit:
    response = self._call_api(...)

# 内部操作 → 日志 + 优雅降级
try:
    result = self._compress_l2()
except Exception as e:
    logger.warning(f"[{self.name}] L2压缩失败: {e}")
    # 不中断流程，降级为不压缩

# 用户输入 → Guardrails 阻断
result = self.guardrails.check_input(user_input)
if result.blocked:
    return f"[Guardrail] 输入被阻止: {result.message}"
```

### 日志规范
```python
logger = logging.getLogger("ModuleName")

# 格式: [agent_name] 事件描述
logger.info(f"[{self.name}] 初始化完成")
logger.warning(f"[{self.name}] 降级到flash模型")
logger.error(f"[{self.name}] API调用失败: {e}")
```

## 5. 新增模块 Checklist

创建新模块时，必须完成：

- [ ] 文件头: `# -*- coding: utf-8 -*-` + 双语 docstring
- [ ] 类型注解: 所有公开方法
- [ ] 日志: `logging.getLogger("ModuleName")`
- [ ] 可选导入: 用 `_MODULE_AVAILABLE` 标志位
- [ ] SKILL.md: 在 `.github/skills/` 创建对应描述
- [ ] `__init__.py`: 新模块需在包入口导出
- [ ] 测试: `test_{module}.py` 覆盖核心路径
- [ ] 无硬编码密钥: API Key 必须走 config.py 或环境变量

## 6. 安全规范

- **绝不** 在代码中硬编码 API Key（config.py 是唯一例外，必须 .gitignore）
- **绝不** 在 README 或文档中暴露真实 Key
- Guardrails 默认启用，不因性能关闭
- 敏感操作（删除/发送/发布）需要用户确认

## 7. 依赖管理

- 核心功能零外部依赖（NGramTFIDFProvider 而非 chromadb）
- 可选依赖用 `_AVAILABLE` 标志位优雅降级
- requirements.txt 只列运行时必需依赖
- 可选依赖在 docstring 中说明安装方式

## 8. Git 规范

### Commit Message
```
<type>(<scope>): <subject>

type: feat/fix/refactor/docs/test/chore
scope: agent/memory/a2a/guardrails/quality/tools/mcp/config
```

示例:
```
feat(quality): add QualityDials and ReviewPipeline from Taste-Skill/Impeccable
fix(memory): resolve RRF fusion score overflow on empty results
refactor(agent): extract react() loop to separate mixin
```

### .gitignore 必须包含
```
__pycache__/
*.pyc
*.pyo
data/
archive/
.env
config.py  # 含API Key
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/
```
