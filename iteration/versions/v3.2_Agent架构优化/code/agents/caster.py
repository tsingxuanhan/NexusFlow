# -*- coding: utf-8 -*-
"""
铸师 (Caster) — 代码/脚本生成Agent
XuanHub Caster Agent for Code Generation
"""

from base_agent import BaseAgent
import logging

logger = logging.getLogger("CasterAgent")

# 铸师系统提示词
CASTER_SYSTEM_PROMPT = """你是"铸师"，铉枢项目中的代码生成专家。

## 核心职责
为铉枢项目编写Python脚本、HTML页面、配置文件、Docker配置等代码。

## 技术栈
- Python (requests, json, subprocess, etc.)
- Ollama (本地LLM服务)
- Docker (容器化部署)
- HTML + CSS + JavaScript
- Git (版本控制)
- Shell脚本 (.bat, .ps1, .sh)

## 代码规范
1. **可直接运行**: 代码必须完整，包含所有import和错误处理
2. **编码规范**:
   - .bat 文件: GBK编码 + CRLF换行
   - .ps1 文件: UTF-8 BOM编码 + CRLF换行
   - 其他文件: UTF-8编码
3. **网络配置**: 所有服务用 127.0.0.1，不用 localhost
4. **硬件约束**: 16GB VRAM是硬约束，优化显存使用
5. **注释风格**: 中文注释，简洁明了
6. **错误处理**: 包含try-except，提供友好的错误信息

## 输出格式
- 代码块必须标注语言类型
- 包含使用说明
- 必要时提供示例"""



class CasterAgent(BaseAgent):
    """铸师 - 代码生成专家"""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="Caster",
            model="pro",
            system_prompt=CASTER_SYSTEM_PROMPT,
            **kwargs
        )
    
    def generate_code(self, requirement: str, language: str = "python") -> str:
        """根据需求生成代码
        
        Args:
            requirement: 功能需求描述
            language: 编程语言
            
        Returns:
            生成的代码
        """
        prompt = f"""请为以下需求生成{language}代码：

{requirement}

要求：
1. 代码完整可运行，包含所有必要的import
2. 包含完善的错误处理
3. 添加中文注释
4. 提供使用说明
5. 遵循{language}最佳实践"""
        
        return self.chat(prompt)
    
    def review_code(self, code: str, language: str = "python") -> str:
        """审查代码
        
        Args:
            code: 要审查的代码
            language: 编程语言
            
        Returns:
            审查报告
        """
        prompt = f"""请审查以下{language}代码：

```{language}
{code}
```

审查维度：
1. 功能正确性
2. 安全性（是否有潜在风险）
3. 性能（是否需要优化）
4. 代码风格
5. 潜在bug

输出格式：
- ✅优点
- ⚠️问题
- 🔧改进建议
- 📝修正后的代码（仅在必要时）"""
        
        return self.chat(prompt)
    
    def generate_ollama_script(self, task: str) -> str:
        """生成Ollama相关脚本
        
        Args:
            task: Ollama任务描述
            
        Returns:
            生成的脚本
        """
        prompt = f"""请生成一个Python脚本，用于{task}。

Ollama API端点: http://127.0.0.1:11434
注意：使用requests库调用API

要求：
1. 处理Ollama服务未启动的情况
2. 适当的超时设置
3. 错误重试机制
4. 中文用户提示"""
        
        return self.chat(prompt)
    
    def generate_docker_config(self, service_name: str, image: str = None) -> str:
        """生成Docker配置
        
        Args:
            service_name: 服务名称
            image: 基础镜像（可选）
            
        Returns:
            Docker配置文件
        """
        prompt = f"""请为 "{service_name}" 服务生成Docker配置。

要求：
1. Dockerfile
2. docker-compose.yml（如果适用）
3. 包含健康检查
4. 适当的资源限制（考虑16GB VRAM约束）
5. 日志配置"""
        
        return self.chat(prompt)
    
    def generate_web_ui(self, description: str) -> str:
        """生成Web前端页面
        
        Args:
            description: 页面功能描述
            
        Returns:
            HTML/CSS/JS代码
        """
        prompt = f"""请为以下功能生成Web前端页面：

{description}

要求：
1. 使用现代HTML5 + CSS3 + JavaScript
2. 响应式设计
3. 美观的UI（可使用Tailwind CSS或类似框架）
4. 与后端API交互的JavaScript代码
5. 包含中文界面"""
        
        return self.chat(prompt)
    
    def fix_code(self, code: str, error: str) -> str:
        """修复代码错误
        
        Args:
            code: 有问题的代码
            error: 错误信息
            
        Returns:
            修复后的代码
        """
        prompt = f"""请修复以下代码的错误：

原始代码：
```
{code}
```

错误信息：
{error}

请：
1. 分析错误原因
2. 提供修复后的代码
3. 解释修复方案"""
        
        return self.chat(prompt)
    
    def generate_shell_script(self, task: str, shell_type: str = "bash") -> str:
        """生成Shell脚本
        
        Args:
            task: 任务描述
            shell_type: shell类型 (bash/sh/ps1/bat)
            
        Returns:
            脚本内容
        """
        encoding_note = ""
        if shell_type == "bat":
            encoding_note = "\n⚠️ 重要：保存为GBK编码 + CRLF换行"
        elif shell_type == "ps1":
            encoding_note = "\n⚠️ 重要：保存为UTF-8 BOM编码 + CRLF换行"
        
        prompt = f"""请生成一个{shell_type}脚本，实现以下功能：

{task}

{encoding_note}

要求：
1. 包含错误处理
2. 添加中文注释
3. 提供使用说明"""
        
        return self.chat(prompt)
