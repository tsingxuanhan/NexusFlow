# -*- coding: utf-8 -*-
"""
执行者 (Executor) — 代码/脚本生成与执行Agent (Flash模型) + ExecutionAgent能力
XuanHub v4.0 Phase 2 — Planning Engine + TeLLAgent双Agent分离
"""

from base_agent import BaseAgent, AgentRole, AgentRunMode
from vector_memory import get_vector_memory
import logging

logger = logging.getLogger("ExecutorAgent")

EXECUTOR_SYSTEM_PROMPT = """你是"执行者"，铉枢项目中的精确执行核心。

## 核心职责
编写代码、调用工具、完成具体操作。你是手和脚，负责把计划变成现实。

## 执行原则
1. **精确执行**: 严格按照计划步骤执行，不自行发挥
2. **可验证输出**: 每个步骤的输出必须可检查
3. **错误处理**: 包含完整的try-except和友好错误信息
4. **效率优先**: 选择最短路径完成，不做多余操作
5. **记录轨迹**: 关键操作记录日志

## 代码规范
- Python: 包含所有import，完整可运行
- .bat → GBK + CRLF | .ps1 → UTF-8 BOM + CRLF
- 服务地址用 127.0.0.1 不用 localhost
- 16GB VRAM是硬约束

## 执行模式
- 按TaskNode执行：读取任务描述→执行→返回结果
- CodeAct模式：直接写Python代码解决问题
- 工具调用模式：按工具接口规范调用

## 输出格式
- 代码块标注语言类型
- 包含使用说明
- 关键步骤有中文注释"""


class ExecutionAgent:
    """⚠️ DEPRECATED: 使用 ExecutorAgent 代替。此类保留仅为向后兼容。
    
    执行Agent — TeLLAgent双Agent分离的Flash模型端（旧版实现）
    """
    
    def __init__(self, base_agent: BaseAgent):
        self.agent = base_agent
        self.role = AgentRole.EXECUTOR
    
    def execute_task_node(self, task_node) -> str:
        """按TaskNode执行任务
        
        Args:
            task_node: TaskNode对象
            
        Returns:
            执行结果文本
        """
        from task_tree import TaskNode
        
        # 构建执行prompt，含依赖信息
        deps_info = ""
        if task_node.dependencies:
            deps_info = f"\n前置任务已完成: {', '.join(task_node.dependencies)}"
        
        strategy_hint = ""
        if task_node.action_type == "codeact":
            strategy_hint = "\n执行方式: 生成Python代码并执行（CodeAct模式）"
        elif task_node.action_type == "research":
            strategy_hint = "\n执行方式: 检索和验证信息"
        elif task_node.action_type == "tool_call":
            strategy_hint = "\n执行方式: 调用指定工具"
        
        prompt = f"""执行任务：

## 任务描述
{task_node.description}
{deps_info}{strategy_hint}

## 要求
1. 精确执行，不遗漏步骤
2. 输出可验证的结果
3. 如果遇到错误，记录错误并尝试替代方案"""

        result = self.agent.execute_step(prompt)
        
        # 更新TaskNode状态
        if result:
            task_node.update_status("done", result=result)
        else:
            task_node.update_status("failed", error="执行返回空结果")
        
        return result or "执行失败：无返回结果"
    
    def generate_code(self, description: str, language: str = "python") -> str:
        """生成代码"""
        context = ""
        if self.agent.memory:
            context = self.agent.memory.get_context_for_llm(description, max_tokens=500)
        ctx = f"\n\n## 相关参考\n{context}" if context else ""
        
        prompt = f"""请为以下需求生成{language}代码：

{description}
{ctx}

要求：完整可运行，含错误处理和中文注释。"""
        result = self.agent.chat(prompt)
        if self.agent.memory:
            self.agent.memory.add(f"code:{description[:80]} → {result[:200]}", importance=0.6)
        return result
    
    def execute_codeact(self, code_description: str) -> str:
        """CodeAct模式 — 生成代码并描述执行步骤
        
        注：实际代码执行需要Phase 3的CodeExec沙箱。
        当前阶段只生成代码+执行计划。
        """
        prompt = f"""CodeAct执行模式 — 请生成Python代码并说明执行步骤：

## 需求
{code_description}

输出：
1. 完整Python代码（标注```python）
2. 执行步骤说明
3. 预期输出
4. 错误处理方案"""
        return self.agent.chat(prompt)
    
    def execute_with_retry(self, task_node, max_retries: int = 2) -> str:
        """带重试的执行
        
        执行失败后，根据错误信息自动修复并重试。
        """
        result = self.execute_task_node(task_node)
        
        if task_node.status == "done":
            return result
        
        # 重试
        for attempt in range(max_retries):
            error = task_node.error or "未知错误"
            
            prompt = f"""上次执行失败，请修复并重试：

## 任务
{task_node.description}

## 错误信息
{error}

## 修复要求
1. 分析错误原因
2. 提供修复方案
3. 重新执行"""

            result = self.agent.chat(prompt)
            
            if result and "失败" not in result and "错误" not in result[:50]:
                task_node.update_status("done", result=result)
                return result
            
            task_node.error = f"重试{attempt+1}次仍失败"
        
        return result


class ExecutorAgent(BaseAgent):
    """执行者 - 精确执行核心（Flash模型）"""
    
    def __init__(self, domain_name: str = None, **kwargs):
        super().__init__(
            name="Executor",
            model="flash",
            system_prompt=EXECUTOR_SYSTEM_PROMPT,
            role=AgentRole.EXECUTOR,
            domain_name=domain_name,
            **kwargs
        )
        self.memory = get_vector_memory()
        
        # Phase 2: ExecutionAgent能力
        self.execution = ExecutionAgent(self)
        
        # A2A能力注册
        if self.a2a:
            self.register_a2a_action("generate_code", self.generate_code)
            self.register_a2a_action("execute_step", self.do_execute_step)
            self.register_a2a_action("fix_code", self.fix_code)
            self.register_a2a_action("generate_script", self.generate_script)
            self.register_a2a_action("execute_task_node", self.do_execute_task_node)
            self.register_a2a_action("execute_codeact", self.do_execute_codeact)
            
            self.register_a2a_capability("generate_code", "生成代码", ["代码", "code"])
            self.register_a2a_capability("execute_step", "执行步骤", ["执行", "execute"])
            self.register_a2a_capability("fix_code", "修复代码", ["修复", "fix", "bug"])
            self.register_a2a_capability("generate_script", "生成脚本", ["脚本", "script"])
            self.register_a2a_capability("execute_task_node", "按TaskNode执行", ["任务执行", "task"])
            self.register_a2a_capability("execute_codeact", "CodeAct执行", ["代码执行", "codeact"])
    
    def generate_code(self, requirement: str, language: str = "python") -> str:
        """生成代码"""
        return self.execution.generate_code(requirement, language)
    
    def do_execute_step(self, step: str) -> str:
        """执行具体步骤"""
        return self.execute_step(step)
    
    def do_execute_task_node(self, task_node) -> str:
        """按TaskNode执行"""
        return self.execution.execute_task_node(task_node)
    
    def do_execute_codeact(self, description: str) -> str:
        """CodeAct执行"""
        return self.execution.execute_codeact(description)
    
    def fix_code(self, code: str, error: str) -> str:
        """修复代码"""
        prompt = f"""修复以下代码错误：

```python
{code}
```

错误信息：
{error}

输出修复后的完整代码+修复说明。"""
        return self.chat(prompt)
    
    def generate_script(self, task: str, shell_type: str = "bash") -> str:
        """生成脚本"""
        encoding = ""
        if shell_type == "bat":
            encoding = "\n⚠️ GBK编码+CRLF换行"
        elif shell_type == "ps1":
            encoding = "\n⚠️ UTF-8 BOM编码+CRLF换行"
        
        prompt = f"""生成{shell_type}脚本：

{task}
{encoding}

要求：完整可运行，含错误处理。"""
        return self.chat(prompt)