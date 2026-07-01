# -*- coding: utf-8 -*-
"""
铉枢·炉守 Guardrails模块
XuanHub Guardrails - Input/Output Validation & Safety

参考: OpenAI Agents SDK Guardrails, LangGraph interrupt_before
提供在Agent执行前后的校验钩子，支持：
- Input Guardrail: 用户输入校验（注入检测、长度限制、敏感词过滤）
- Output Guardrail: 输出校验（幻觉标记、格式校验、安全过滤）
- Tool Guardrail: 工具调用校验（权限检查、参数安全）
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("Guardrails")


class GuardrailAction(Enum):
    """Guardrail动作"""
    PASS = "pass"           # 通过
    WARN = "warn"           # 警告但放行
    BLOCK = "block"         # 阻止执行
    MODIFY = "modify"       # 修改后放行


@dataclass
class GuardrailResult:
    """Guardrail校验结果"""
    action: GuardrailAction = GuardrailAction.PASS
    message: str = ""
    modified_value: Optional[Any] = None  # MODIFY时的替换值
    metadata: Dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.action in (GuardrailAction.PASS, GuardrailAction.WARN, GuardrailAction.MODIFY)

    @property
    def blocked(self) -> bool:
        return self.action == GuardrailAction.BLOCK


class InputGuardrail:
    """输入Guardrail基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    def check(self, user_input: str) -> GuardrailResult:
        """校验用户输入，子类重写"""
        return GuardrailResult(action=GuardrailAction.PASS)


class OutputGuardrail:
    """输出Guardrail基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    def check(self, agent_output: str) -> GuardrailResult:
        """校验Agent输出，子类重写"""
        return GuardrailResult(action=GuardrailAction.PASS)


class ToolGuardrail:
    """工具调用Guardrail基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    def check(self, tool_name: str, tool_params: Dict) -> GuardrailResult:
        """校验工具调用，子类重写"""
        return GuardrailResult(action=GuardrailAction.PASS)


# ============ 内置Guardrail实现 ============

class PromptInjectionGuard(InputGuardrail):
    """Prompt注入检测
    
    检测常见的注入模式：
    - 忽略之前指令
    - 角色切换攻击
    - 系统提示泄露
    """

    # 注入模式（中英文）
    INJECTION_PATTERNS = [
        r"(?i)(ignore|忽略)\s*(previous|above|prior|之前的|上面的)",
        r"(?i)(forget|忘记)\s*(everything|all|所有)",
        r"(?i)(you\s+are\s+now|你现在|你从现在起)",
        r"(?i)(system\s*prompt|系统提示|system\s*instruction)",
        r"(?i)(pretend|假装|act\s+as|roleplay)",
        r"(?i)(jailbreak|越狱|break\s+out)",
        r"(?i)(reveal|显示|show)\s*(your|你的)\s*(instructions|指令|prompt)",
    ]

    def __init__(self, strict: bool = False):
        super().__init__("prompt_injection", "检测Prompt注入攻击")
        self.strict = strict
        self._patterns = [re.compile(p) for p in self.INJECTION_PATTERNS]

    def check(self, user_input: str) -> GuardrailResult:
        matches = []
        for pattern in self._patterns:
            if pattern.search(user_input):
                matches.append(pattern.pattern)

        if matches:
            action = GuardrailAction.BLOCK if self.strict else GuardrailAction.WARN
            return GuardrailResult(
                action=action,
                message=f"检测到可能的Prompt注入: {len(matches)}个模式匹配",
                metadata={"matched_patterns": matches}
            )

        return GuardrailResult(action=GuardrailAction.PASS)


class InputLengthGuard(InputGuardrail):
    """输入长度限制"""

    def __init__(self, max_length: int = 10000, warn_length: int = 8000):
        super().__init__("input_length", "限制用户输入长度")
        self.max_length = max_length
        self.warn_length = warn_length

    def check(self, user_input: str) -> GuardrailResult:
        length = len(user_input)

        if length > self.max_length:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                message=f"输入过长: {length} > {self.max_length}",
                metadata={"length": length, "max": self.max_length}
            )

        if length > self.warn_length:
            return GuardrailResult(
                action=GuardrailAction.WARN,
                message=f"输入较长: {length}字符",
                metadata={"length": length}
            )

        return GuardrailResult(action=GuardrailAction.PASS)


class OutputLengthGuard(OutputGuardrail):
    """输出长度限制"""

    def __init__(self, max_length: int = 50000):
        super().__init__("output_length", "限制Agent输出长度")
        self.max_length = max_length

    def check(self, agent_output: str) -> GuardrailResult:
        length = len(agent_output)

        if length > self.max_length:
            # 截断而非阻止
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                message=f"输出截断: {length} -> {self.max_length}",
                modified_value=agent_output[:self.max_length] + "\n...[输出已截断]",
                metadata={"original_length": length, "truncated_to": self.max_length}
            )

        return GuardrailResult(action=GuardrailAction.PASS)


class SensitiveContentGuard(OutputGuardrail):
    """敏感内容过滤（输出侧）"""

    # 需要过滤的模式
    FILTER_PATTERNS = [
        (r'(?i)(api[_-]?key|secret|password|passwd|token)\s*[=:]\s*["\']?[\w\-\.]{6,}', "凭据泄露"),
        (r'\b\d{16,19}\b', "可能的银行卡号"),
        (r'(?i)(Bearer\s+sk-[\w-]+)', "API密钥"),
    ]

    def __init__(self, mode: str = "mask"):
        super().__init__("sensitive_content", "过滤敏感信息")
        self.mode = mode  # mask | block
        self._patterns = [(re.compile(p), desc) for p, desc in self.FILTER_PATTERNS]

    def check(self, agent_output: str) -> GuardrailResult:
        found = []

        for pattern, desc in self._patterns:
            matches = pattern.findall(agent_output)
            if matches:
                found.append((desc, len(matches)))

        if not found:
            return GuardrailResult(action=GuardrailAction.PASS)

        if self.mode == "mask":
            masked = agent_output
            for pattern, _ in self._patterns:
                masked = pattern.sub("[REDACTED]", masked)
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                message=f"检测到敏感内容，已脱敏: {found}",
                modified_value=masked,
                metadata={"found": found}
            )
        else:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                message=f"输出包含敏感内容: {found}",
                metadata={"found": found}
            )


class ToolPermissionGuard(ToolGuardrail):
    """工具调用权限Guardrail
    
    限制某些工具只能在特定条件下被调用
    """

    def __init__(
        self,
        allowed_tools: Optional[List[str]] = None,
        blocked_tools: Optional[List[str]] = None,
        max_calls_per_tool: Optional[Dict[str, int]] = None
    ):
        super().__init__("tool_permission", "工具调用权限控制")
        self.allowed_tools = set(allowed_tools) if allowed_tools else None
        self.blocked_tools = set(blocked_tools) if blocked_tools else set()
        self.max_calls_per_tool = max_calls_per_tool or {}
        self._call_counts: Dict[str, int] = {}

    def check(self, tool_name: str, tool_params: Dict) -> GuardrailResult:
        # 黑名单检查
        if tool_name in self.blocked_tools:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                message=f"工具 '{tool_name}' 被禁止调用"
            )

        # 白名单检查
        if self.allowed_tools and tool_name not in self.allowed_tools:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                message=f"工具 '{tool_name}' 不在允许列表中"
            )

        # 调用次数限制
        if tool_name in self.max_calls_per_tool:
            self._call_counts[tool_name] = self._call_counts.get(tool_name, 0) + 1
            limit = self.max_calls_per_tool[tool_name]

            if self._call_counts[tool_name] > limit:
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    message=f"工具 '{tool_name}' 超过调用限制 ({limit})",
                    metadata={"calls": self._call_counts[tool_name], "limit": limit}
                )

        return GuardrailResult(action=GuardrailAction.PASS)

    def reset_counts(self) -> None:
        """重置调用计数"""
        self._call_counts.clear()


# ============ Guardrail管理器 ============

class GuardrailManager:
    """Guardrail管理器
    
    统一管理输入/输出/工具三类Guardrail，
    支持链式执行和短路阻断。
    """

    def __init__(self):
        self._input_guardrails: List[InputGuardrail] = []
        self._output_guardrails: List[OutputGuardrail] = []
        self._tool_guardrails: List[ToolGuardrail] = []
        self._stats = {
            "input_checks": 0,
            "input_blocks": 0,
            "output_checks": 0,
            "output_blocks": 0,
            "tool_checks": 0,
            "tool_blocks": 0,
        }

    def add_input(self, guardrail: InputGuardrail) -> None:
        self._input_guardrails.append(guardrail)

    def add_output(self, guardrail: OutputGuardrail) -> None:
        self._output_guardrails.append(guardrail)

    def add_tool(self, guardrail: ToolGuardrail) -> None:
        self._tool_guardrails.append(guardrail)

    def check_input(self, user_input: str) -> GuardrailResult:
        """校验用户输入，链式执行，遇到BLOCK短路"""
        self._stats["input_checks"] += 1
        warnings = []
        modified = user_input

        for gr in self._input_guardrails:
            result = gr.check(modified)
            if result.action == GuardrailAction.BLOCK:
                self._stats["input_blocks"] += 1
                return result
            elif result.action == GuardrailAction.WARN:
                warnings.append(f"[{gr.name}] {result.message}")
            elif result.action == GuardrailAction.MODIFY:
                modified = result.modified_value

        if warnings:
            logger.warning(f"[Guardrail] Input warnings: {warnings}")

        if modified != user_input:
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                message="输入已被Guardrail修改",
                modified_value=modified,
                metadata={"warnings": warnings}
            )

        return GuardrailResult(action=GuardrailAction.PASS)

    def check_output(self, agent_output: str) -> GuardrailResult:
        """校验Agent输出"""
        self._stats["output_checks"] += 1
        warnings = []
        modified = agent_output

        for gr in self._output_guardrails:
            result = gr.check(modified)
            if result.action == GuardrailAction.BLOCK:
                self._stats["output_blocks"] += 1
                return result
            elif result.action == GuardrailAction.WARN:
                warnings.append(f"[{gr.name}] {result.message}")
            elif result.action == GuardrailAction.MODIFY:
                modified = result.modified_value

        if warnings:
            logger.warning(f"[Guardrail] Output warnings: {warnings}")

        if modified != agent_output:
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                message="输出已被Guardrail修改",
                modified_value=modified,
                metadata={"warnings": warnings}
            )

        return GuardrailResult(action=GuardrailAction.PASS)

    def check_tool(self, tool_name: str, tool_params: Dict) -> GuardrailResult:
        """校验工具调用"""
        self._stats["tool_checks"] += 1

        for gr in self._tool_guardrails:
            result = gr.check(tool_name, tool_params)
            if result.action == GuardrailAction.BLOCK:
                self._stats["tool_blocks"] += 1
                return result

        return GuardrailResult(action=GuardrailAction.PASS)

    def get_stats(self) -> Dict:
        return self._stats.copy()

    def reset(self) -> None:
        for gr in self._tool_guardrails:
            if isinstance(gr, ToolPermissionGuard):
                gr.reset_counts()
        self._stats = {k: 0 for k in self._stats}


# ============ Anti-Pattern Output Guardrail ============
# 灵感: Impeccable 27条确定性反模式 + Taste-Skill "Anti-Slop" 理念
# 通用化: 从前端反模式扩展到通用AI输出反模式

class AntiPatternOutputGuard(OutputGuardrail):
    """AI输出反模式检测Guardrail
    
    检测Agent输出中常见的"AI味"反模式，并提供修复建议。
    与quality.py的PatternAuditCommand互补:
      - PatternAuditCommand: ReviewPipeline中的审查命令，返回ReviewResult
      - AntiPatternOutputGuard: GuardrailManager中的输出守卫，返回GuardrailResult
    
    两者检测相同模式但接口不同，按场景选择:
      - chat()输出拦截 → AntiPatternOutputGuard (自动)
      - review()主动审查 → PatternAuditCommand (按需)
    """

    # 反模式规则: (regex, name, severity, suggestion)
    ANTI_PATTERNS = [
        (r"作为一个AI[,，]?\s*(我|语言模型|助手)", "ai_disclaimer",
         "high", "移除'作为AI'式声明，直接给出内容"),
        (r"(总之|综上所述|总而言之)[，,]?\s*(我|AI|我们)", "generic_summary",
         "medium", "避免泛化总结，给出具体结论"),
        (r"(需要注意的是|值得注意的是|需要强调的是)\s*[，,]?\s*(这|它|以上|该)", "hedge_overuse",
         "medium", "减少缓冲性表述，直接陈述"),
        (r"(然而|但是|不过)\s*[，,]?\s*(这也|这同样|这依然|也需要)", "qualifier_chain",
         "low", "简化限定词链，直接表达转折"),
        (r"(首先|其次|最后|第一|第二|第三).*?(首先|其次|最后|第一|第二|第三)", "enumeration_fatigue",
         "medium", "减少机械枚举，改用自然叙事"),
        (r"(非常重要|至关重要|不可或缺|必不可少|极其关键)", "intensity_inflation",
         "low", "降低强度词，让事实说话"),
        (r"在.{2,15}(领域|方面|背景下|环境中|框架下)[，,]?\s*(它|这|该)", "contextual_padding",
         "low", "删除填充性背景句"),
        (r"(毫无疑问|不可否认|毋庸置疑|不言而喻|众所周知)", "trivial_assertion",
         "medium", "删除不证自明的声明，直接陈述"),
    ]

    def __init__(self, mode: str = "warn", max_issues: int = 5):
        """
        Args:
            mode: "warn"=警告但放行, "modify"=附加建议后放行, "block"=超过阈值阻止
            max_issues: 阻止模式下，触发BLOCK的最小问题数
        """
        super().__init__("anti_pattern", "检测AI输出反模式")
        self.mode = mode
        self.max_issues = max_issues

    def check(self, agent_output: str) -> GuardrailResult:
        issues = []
        severity_scores = {"high": 0.3, "medium": 0.15, "low": 0.05}
        total_deduction = 0.0

        for pattern, name, severity, suggestion in self.ANTI_PATTERNS:
            matches = re.findall(pattern, agent_output, re.IGNORECASE)
            if matches:
                count = len(matches)
                deduction = severity_scores.get(severity, 0.1) * min(count, 3)
                total_deduction += deduction
                issues.append({
                    "name": name,
                    "severity": severity,
                    "count": count,
                    "suggestion": suggestion
                })

        if not issues:
            return GuardrailResult(action=GuardrailAction.PASS, message="无反模式检测")

        score = max(0.0, 1.0 - total_deduction)
        msg_parts = [f"检测到 {len(issues)} 类反模式 (质量分: {score:.2f})"]
        for iss in issues:
            msg_parts.append(f"  - [{iss['severity']}] {iss['name']} x{iss['count']}: {iss['suggestion']}")

        if self.mode == "block" and len(issues) >= self.max_issues:
            return GuardrailResult(
                action=GuardrailAction.BLOCK,
                message="\n".join(msg_parts),
                metadata={"score": score, "issues": issues}
            )
        elif self.mode == "modify":
            return GuardrailResult(
                action=GuardrailAction.MODIFY,
                message="\n".join(msg_parts),
                modified_value=agent_output,  # 不修改内容，仅附加元数据
                metadata={"score": score, "issues": issues}
            )
        else:  # warn
            return GuardrailResult(
                action=GuardrailAction.WARN,
                message="\n".join(msg_parts),
                metadata={"score": score, "issues": issues}
            )


# ============ 便捷工厂 ============

def create_default_guardrails(
    strict_injection: bool = False,
    max_input_length: int = 10000,
    max_output_length: int = 50000,
    sensitive_mode: str = "mask",
    enable_anti_pattern: bool = True,
    anti_pattern_mode: str = "warn"
) -> GuardrailManager:
    """创建默认Guardrail配置
    
    Args:
        strict_injection: 是否严格注入检测
        max_input_length: 最大输入长度
        max_output_length: 最大输出长度
        sensitive_mode: 敏感内容处理模式
        enable_anti_pattern: 是否启用反模式检测 (来自Impeccable/Taste-Skill)
        anti_pattern_mode: 反模式检测模式 "warn"/"modify"/"block"
    """
    mgr = GuardrailManager()
    mgr.add_input(PromptInjectionGuard(strict=strict_injection))
    mgr.add_input(InputLengthGuard(max_length=max_input_length))
    mgr.add_output(OutputLengthGuard(max_length=max_output_length))
    mgr.add_output(SensitiveContentGuard(mode=sensitive_mode))
    if enable_anti_pattern:
        mgr.add_output(AntiPatternOutputGuard(mode=anti_pattern_mode))
    return mgr


# ============ Phase 3: CodeAct Guardrails ============

class CodeActToolGuardrail(ToolGuardrail):
    """CodeAct工具调用Guardrail — 检查代码安全性和参数合法性"""
    
    # 危险工具调用模式
    DANGEROUS_TOOL_PATTERNS = {
        "code_exec": [r"os\.", r"subprocess", r"__import__", r"exec\s*\(", r"eval\s*\("],
        "file_ops": [r"\.\./", r"/etc/", r"/root/", r"/var/", r"\.ssh/", r"\.env"],
        "api_caller": [r"localhost:\d+", r"127\.0\.0\.1:\d+", r"0\.0\.0\.0"],
        "git_ops": [r"reset", r"clean", r"filter-branch"],
    }
    
    def __init__(self, name: str = "codeact_tool"):
        super().__init__(name, "CodeAct tool call safety checks")
    
    def check(self, tool_name: str, tool_params: Dict) -> GuardrailResult:
        """检查工具调用安全性"""
        import re
        
        # 检查已知的危险模式
        patterns = self.DANGEROUS_TOOL_PATTERNS.get(tool_name, [])
        
        # 序列化参数为字符串进行模式匹配
        params_str = json.dumps(tool_params, default=str)
        
        for pattern in patterns:
            if re.search(pattern, params_str):
                return GuardrailResult(
                    action=GuardrailAction.BLOCK,
                    message=f"Dangerous pattern in {tool_name}: {pattern}",
                    metadata={"tool": tool_name, "pattern": pattern}
                )
        
        # 特殊检查：code_exec工具需要额外的代码安全审查
        if tool_name == "code_exec":
            code = tool_params.get("code", "")
            if code:
                from tools.code_exec import CodeActGuardrails
                passed, reason = CodeActGuardrails.check(code)
                if not passed:
                    return GuardrailResult(
                        action=GuardrailAction.BLOCK,
                        message=f"CodeAct security: {reason}",
                        metadata={"tool": "code_exec", "reason": reason}
                    )
        
        return GuardrailResult(action=GuardrailAction.PASS, message="Tool call safe")


def create_codeact_guardrails(
    strict_injection: bool = False,
    max_input_length: int = 10000,
    max_output_length: int = 50000,
    sensitive_mode: str = "mask",
    enable_anti_pattern: bool = True,
    anti_pattern_mode: str = "warn",
) -> GuardrailManager:
    """创建包含CodeAct安全检查的Guardrail配置"""
    mgr = create_default_guardrails(
        strict_injection=strict_injection,
        max_input_length=max_input_length,
        max_output_length=max_output_length,
        sensitive_mode=sensitive_mode,
        enable_anti_pattern=enable_anti_pattern,
        anti_pattern_mode=anti_pattern_mode,
    )
    mgr.add_tool(CodeActToolGuardrail())
    return mgr
