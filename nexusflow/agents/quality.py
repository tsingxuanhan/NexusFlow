# -*- coding: utf-8 -*-
"""
铉枢·炉守 质量调控模块
XuanHub Quality Control - Dials, Modes & Self-Review

参考:
  - Taste-Skill (28.5K⭐): 参数化"品味旋钮"(DESIGN_VARIANCE/MOTION_INTENSITY/VISUAL_DENSITY)
  - Impeccable (31.6K⭐): 23条自检命令 + 27条确定性反模式 + 12规则LLM评审

通用化思路:
  Taste-Skill 的旋钮 → QualityDials (可调参数控制Agent输出风格)
  Impeccable 的命令  → ReviewCommand (自检/评审/精炼管道)
  两者的反模式      → AntiPatternGuard (guardrails.py中实现)
  Impeccable 的模式  → AgentMode (预设行为档案)
"""

import re
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("Quality")


# ============================================================
# 1. Quality Dials — 参数化输出质量旋钮
#    灵感: Taste-Skill 的 DESIGN_VARIANCE / MOTION_INTENSITY / VISUAL_DENSITY
#    通用化: 从"前端设计"泛化为"Agent输出质量控制"
# ============================================================

@dataclass
class QualityDials:
    """Agent输出质量旋钮
    
    每个旋钮范围 0.0-1.0，控制Agent不同维度的输出倾向。
    类似Taste-Skill的"品味旋钮"，但泛化到通用Agent场景。
    
    Dials:
        creativity: 创造性 — 0=严格遵循事实/模板, 1=大胆探索/非结构化
        precision:  精确性 — 0=模糊概括, 1=精确引用/数据支撑
        verbosity:  详细度 — 0=极简一句话, 1=详尽展开
        caution:    谨慎度 — 0=果断断言, 1=附带条件/不确定性标注
    """
    creativity: float = 0.5
    precision: float = 0.7
    verbosity: float = 0.5
    caution: float = 0.5

    def __post_init__(self):
        for name in ("creativity", "precision", "verbosity", "caution"):
            val = getattr(self, name)
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"QualityDials.{name} 必须在 [0.0, 1.0] 范围内, 当前: {val}")

    def to_generation_params(self) -> Dict[str, Any]:
        """根据旋钮推导LLM生成参数 (temperature/top_p/max_tokens)"""
        # creativity → temperature: 0.3~1.2
        temperature = 0.3 + self.creativity * 0.9
        # precision → top_p: 高精确性用更窄的采样
        top_p = 1.0 - self.precision * 0.3  # 0.7~1.0
        # verbosity → max_tokens: 512~8192
        max_tokens = int(512 + self.verbosity * 7680)
        return {
            "temperature": round(temperature, 2),
            "top_p": round(top_p, 2),
            "max_tokens": max_tokens
        }

    def to_prompt_suffix(self) -> str:
        """根据旋钮生成附加到system prompt的约束指令"""
        parts = []
        if self.creativity < 0.3:
            parts.append("严格遵循已有模板和事实，不要发挥。")
        elif self.creativity > 0.7:
            parts.append("鼓励突破常规思路，大胆提出非共识观点。")
        
        if self.precision > 0.7:
            parts.append("每个论断需要具体数据、引用或代码引用支撑，避免模糊表述。")
        elif self.precision < 0.3:
            parts.append("允许概括性表述，不需要每个点都有数据支撑。")
        
        if self.verbosity < 0.3:
            parts.append("回答极简，一到两句话即可，不要展开。")
        elif self.verbosity > 0.7:
            parts.append("详细展开每个要点，包含示例、对比和边界条件。")
        
        if self.caution > 0.7:
            parts.append("对不确定的结论标注置信度，区分事实与推测。")
        elif self.caution < 0.3:
            parts.append("直接给出判断，不需要附带免责声明。")
        
        return "\n".join(parts) if parts else ""

    def to_dict(self) -> Dict[str, float]:
        return {
            "creativity": self.creativity,
            "precision": self.precision,
            "verbosity": self.verbosity,
            "caution": self.caution
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "QualityDials":
        return cls(**{k: v for k, v in d.items() if k in ("creativity", "precision", "verbosity", "caution")})


# ============================================================
# 2. Agent Mode — 预设行为档案
#    灵感: Taste-Skill 的10个变体 (minimalist/brutalist/soft/...)
#    通用化: 从"视觉风格"泛化为"Agent行为模式"
# ============================================================

class AgentMode(Enum):
    """Agent行为模式预设
    
    基础6档 + 科研3档（借鉴Mira平台模式预设思路，一键折叠多参数）
    科研3档不仅调Dials，还联动模型选择、审查管道、工具权限。
    """
    # 基础6档
    PRECISE = "precise"        # 高精确、低创造 — 学术/科研场景
    CREATIVE = "creative"      # 高创造、低谨慎 — 头脑风暴/探索
    CONCISE = "concise"        # 低详细、直接 — 快速问答
    THOROUGH = "thorough"      # 高详细、高精确 — 深度分析
    BALANCED = "balanced"      # 均衡 — 默认
    CAUTIOUS = "cautious"      # 高谨慎 — 高风险决策
    # 科研3档（Mira-inspired 一键预设）
    RESEARCH = "research"      # 科研模式 — Pro模型+严格审查+全工具+高精确
    ENGINEERING = "engineering"  # 工程模式 — Pro规划+Flash执行+代码工具+中等
    CASUAL = "casual"          # 普通模式 — Flash模型+快速审查+轻量交互


MODE_PROFILES: Dict[AgentMode, QualityDials] = {
    # 基础6档
    AgentMode.PRECISE:     QualityDials(creativity=0.2, precision=0.9, verbosity=0.6, caution=0.6),
    AgentMode.CREATIVE:    QualityDials(creativity=0.9, precision=0.3, verbosity=0.6, caution=0.2),
    AgentMode.CONCISE:     QualityDials(creativity=0.3, precision=0.5, verbosity=0.1, caution=0.3),
    AgentMode.THOROUGH:    QualityDials(creativity=0.4, precision=0.9, verbosity=0.9, caution=0.6),
    AgentMode.BALANCED:    QualityDials(creativity=0.5, precision=0.5, verbosity=0.5, caution=0.5),
    AgentMode.CAUTIOUS:    QualityDials(creativity=0.2, precision=0.8, verbosity=0.5, caution=0.9),
    # 科研3档 — 一键折叠模型+审查+工具
    AgentMode.RESEARCH:    QualityDials(creativity=0.2, precision=0.9, verbosity=0.7, caution=0.7),
    AgentMode.ENGINEERING: QualityDials(creativity=0.4, precision=0.7, verbosity=0.5, caution=0.4),
    AgentMode.CASUAL:      QualityDials(creativity=0.6, precision=0.4, verbosity=0.3, caution=0.3),
}


# ============================================================
# 2b. Research Preset — 科研3档完整配置（Mira-inspired）
#     不仅仅调Dials，还联动模型、审查管道、工具权限、记忆策略
# ============================================================

@dataclass
class ResearchPreset:
    """科研模式完整预设 — 一键切换所有参数
    
    借鉴Mira的"普通/工程/科研"三档思路，将分散在多个模块的配置
    折叠为一键操作。set_mode("research") 等价于手动设置7项参数。
    """
    dials: QualityDials
    model: str                    # 默认模型: "pro" / "flash"
    plan_model: str               # 规划用模型
    exec_model: str               # 执行用模型
    review_pipeline: str          # 审查管道: "strict" / "default" / "quick" / "none"
    auto_review: bool             # 是否自动审查每条输出
    enabled_tools: List[str]      # 可用工具列表（空=全部）
    memory_strategy: str          # 记忆策略: "full" / "selective" / "minimal"
    guardrails_level: str         # 护栏等级: "strict" / "normal" / "relaxed"


RESEARCH_PRESETS: Dict[AgentMode, ResearchPreset] = {
    AgentMode.RESEARCH: ResearchPreset(
        dials=MODE_PROFILES[AgentMode.RESEARCH],
        model="pro",
        plan_model="pro",
        exec_model="flash",
        review_pipeline="strict",
        auto_review=True,
        enabled_tools=[],  # 全部工具
        memory_strategy="full",
        guardrails_level="strict",
    ),
    AgentMode.ENGINEERING: ResearchPreset(
        dials=MODE_PROFILES[AgentMode.ENGINEERING],
        model="pro",
        plan_model="pro",
        exec_model="flash",
        review_pipeline="default",
        auto_review=False,
        enabled_tools=["code_exec", "file_ops", "git_ops", "calculator", "api_caller", "browser", "web_search"],
        memory_strategy="selective",
        guardrails_level="normal",
    ),
    AgentMode.CASUAL: ResearchPreset(
        dials=MODE_PROFILES[AgentMode.CASUAL],
        model="flash",
        plan_model="flash",
        exec_model="flash",
        review_pipeline="quick",
        auto_review=False,
        enabled_tools=["web_search", "calculator", "file_ops"],
        memory_strategy="minimal",
        guardrails_level="relaxed",
    ),
}


def get_research_preset(mode: str) -> Optional[ResearchPreset]:
    """获取科研模式预设
    
    Args:
        mode: "research" / "engineering" / "casual"
    
    Returns:
        ResearchPreset 或 None（非科研模式）
    """
    try:
        agent_mode = AgentMode(mode)
    except ValueError:
        return None
    return RESEARCH_PRESETS.get(agent_mode)


# ============================================================
# 3. Review Command — 自检命令管道
#    灵感: Impeccable 的 /audit /critique /polish /distill 等23条命令
#    通用化: 从"前端设计审查"泛化为"Agent输出质量审查"
# ============================================================

class ReviewAction(Enum):
    """审查动作类型"""
    AUDIT = "audit"          # 技术质量检查 — 一致性、完整性、正确性
    CRITIQUE = "critique"    # 评审 — 识别弱点、遗漏、潜在问题
    POLISH = "polish"        # 精炼 — 修正表述、对齐、格式
    DISTILL = "distill"      # 提炼 — 去冗余、保留核心
    BOLDER = "bolder"        # 加大胆 — 强化观点、减少模棱两可
    QUIETER = "quieter"      # 收敛 — 降调、增加限定
    VERIFY = "verify"        # 事实核查 — 标注不确定声明


@dataclass
class ReviewResult:
    """审查结果"""
    action: ReviewAction
    passed: bool = True
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    revised_output: Optional[str] = None
    score: float = 1.0  # 0.0-1.0 质量评分


class ReviewCommand:
    """自检命令基类
    
    灵感来自 Impeccable 的 /audit /critique /polish 命令系统。
    每个命令是一个可组合的审查步骤，输入Agent原始输出，输出ReviewResult。
    """

    def __init__(self, action: ReviewAction, description: str = ""):
        self.action = action
        self.description = description

    def execute(self, output: str, context: Optional[Dict] = None) -> ReviewResult:
        """执行审查，子类重写"""
        return ReviewResult(action=self.action)


class PatternAuditCommand(ReviewCommand):
    """反模式审计 — 检测输出中的常见AI反模式
    
    参考: Impeccable 的27条确定性反模式规则 + Taste-Skill 的"Anti-Slop"理念
    通用化: 从前端反模式扩展到通用AI输出反模式
    """

    # 确定性反模式规则 (类似Impeccable的27条deterministic rules)
    ANTI_PATTERNS = [
        # (pattern, name, severity)
        (r"作为一个AI[,，]?\s*(我|语言模型)", "ai_disclaimer", "high"),
        (r"(总之|综上所述|总而言之)[，,]?\s*(我|AI)", "generic_summary", "medium"),
        (r"(需要注意的是|值得注意的是|需要强调的是)\s*[，,]?\s*(这|它|以上)", "hedge_overuse", "medium"),
        (r"(然而|但是|不过)\s*[，,]?\s*(这也|这同样|这依然)", "qualifier_chain", "low"),
        (r"(首先|其次|最后|第一|第二|第三).*?(首先|其次|最后|第一|第二|第三)", "enumeration_fatigue", "medium"),
        (r"(非常重要|至关重要|不可或缺|必不可少)", "intensity_inflation", "low"),
        (r"在.{2,15}(领域|方面|背景下|环境中)[，,]?\s*(它|这|该)", "contextual_padding", "low"),
    ]

    def __init__(self):
        super().__init__(
            ReviewAction.AUDIT,
            "检测AI输出中的常见反模式 (AI声明/过度修饰/枚举疲劳等)"
        )

    # 自动修复规则（Mira-inspired: 缺失字段自动补全而非报错）
    AUTO_FIXES = {
        "ai_disclaimer": (r"作为一个AI[,，]?\s*(我|语言模型)[，,]?\s*", ""),
        "generic_summary": (r"(总之|综上所述|总而言之)[，,]?\s*(我|AI)[，,]?\s*(认为|觉得|相信)?\s*", ""),
        "hedge_overuse": (r"(需要注意的是|值得注意的是|需要强调的是)\s*[，,]?\s*(这|它|以上)\s*", ""),
        "intensity_inflation": (r"(非常重要|至关重要|不可或缺|必不可少)", "重要"),
    }

    def execute(self, output: str, context: Optional[Dict] = None) -> ReviewResult:
        issues = []
        suggestions = []
        severity_scores = {"high": 0.3, "medium": 0.15, "low": 0.05}
        total_deduction = 0.0
        
        # 自动修复
        revised = output
        auto_fixes_applied = []

        for pattern, name, severity in self.ANTI_PATTERNS:
            matches = re.findall(pattern, output, re.IGNORECASE)
            if matches:
                count = len(matches)
                deduction = severity_scores.get(severity, 0.1) * min(count, 3)
                total_deduction += deduction
                issues.append(f"[{severity}] 反模式 '{name}' 出现 {count} 次")
                
                # 自动修复（Mira-inspired）
                if name in self.AUTO_FIXES:
                    fix_pattern, fix_replacement = self.AUTO_FIXES[name]
                    new_revised = re.sub(fix_pattern, fix_replacement, revised, flags=re.IGNORECASE)
                    if new_revised != revised:
                        revised = new_revised
                        auto_fixes_applied.append(name)
                        suggestions.append(f"自动修复: '{name}' 已移除/替换")
                    else:
                        if name == "ai_disclaimer":
                            suggestions.append("移除'作为AI'式声明，直接给出内容")
                else:
                    if name == "generic_summary":
                        suggestions.append("避免泛化总结，给出具体结论")
                    elif name == "enumeration_fatigue":
                        suggestions.append("减少机械枚举，改用自然叙事结构")
                    elif name == "qualifier_chain":
                        suggestions.append("减少缓冲性表述，直接陈述")
                    elif name == "intensity_inflation":
                        suggestions.append("降低强度词使用，让事实说话")

        score = max(0.0, 1.0 - total_deduction)
        passed = score >= 0.7

        return ReviewResult(
            action=self.action,
            passed=passed,
            issues=issues,
            suggestions=suggestions,
            revised_output=revised if revised != output else None,
            score=score
        )


class StructureAuditCommand(ReviewCommand):
    """结构审计 — 检查输出的结构质量
    
    参考: Impeccable 的 /audit 命令 (技术质量检查)
    """

    def __init__(self):
        super().__init__(
            ReviewAction.AUDIT,
            "检查输出结构完整性 (段落/代码块/列表一致性)"
        )

    def execute(self, output: str, context: Optional[Dict] = None) -> ReviewResult:
        issues = []
        suggestions = []
        score = 1.0

        # 检查代码块是否闭合
        code_fences = output.count("```")
        if code_fences % 2 != 0:
            issues.append("[high] 代码块未闭合 (``` 不成对)")
            suggestions.append("检查并补全代码块的闭合标记")
            score -= 0.2

        # 检查列表标记一致性
        bullet_styles = set(re.findall(r'^(\s*)([-*+])\s', output, re.MULTILINE))
        if len(bullet_styles) > 2:
            issues.append("[low] 列表标记风格不统一")
            suggestions.append("统一使用一种列表标记符号")
            score -= 0.05

        # 检查标题层级跳跃
        headers = re.findall(r'^(#{1,6})\s', output, re.MULTILINE)
        if len(headers) >= 2:
            levels = [len(h) for h in headers]
            for i in range(1, len(levels)):
                if levels[i] - levels[i-1] > 1:
                    issues.append(f"[medium] 标题层级跳跃: {'#'*levels[i-1]} → {'#'*levels[i]}")
                    suggestions.append("标题应逐级递进，不要跳级")
                    score -= 0.1
                    break

        # 检查空段
        paragraphs = [p.strip() for p in output.split("\n\n") if p.strip()]
        if len(paragraphs) > 3 and any(len(p) < 10 for p in paragraphs):
            issues.append("[low] 存在过短段落")
            score -= 0.05

        return ReviewResult(
            action=self.action,
            passed=score >= 0.7,
            issues=issues,
            suggestions=suggestions,
            score=max(0.0, score)
        )


class PolishCommand(ReviewCommand):
    """精炼命令 — 修正格式和对齐
    
    参考: Impeccable 的 /polish 命令 (发布前精修)
    """

    def __init__(self):
        super().__init__(
            ReviewAction.POLISH,
            "精修输出格式和对齐 (间距/标点/一致性)"
        )

    def execute(self, output: str, context: Optional[Dict] = None) -> ReviewResult:
        issues = []
        revised = output

        # 修正连续多个空行
        if "\n\n\n" in revised:
            revised = re.sub(r'\n{3,}', '\n\n', revised)
            issues.append("[auto] 压缩多余空行")

        # 修正中英文间距 (中文后直接跟英文加空格)
        revised = re.sub(r'([\u4e00-\u9fff])([a-zA-Z])', r'\1 \2', revised)
        revised = re.sub(r'([a-zA-Z])([\u4e00-\u9fff])', r'\1 \2', revised)

        # 修正中文标点后的多余空格
        revised = re.sub(r'([，。！？；：）】》])\s+', r'\1', revised)

        changed = revised != output

        return ReviewResult(
            action=self.action,
            passed=True,
            issues=issues,
            revised_output=revised if changed else None,
            score=1.0
        )


class DistillCommand(ReviewCommand):
    """提炼命令 — 去冗余保留核心
    
    参考: Impeccable 的 /distill 命令 (简化复杂UI→简化复杂输出)
    """

    def __init__(self, target_ratio: float = 0.6):
        """
        Args:
            target_ratio: 目标压缩比 (0.6 = 保留60%篇幅)
        """
        super().__init__(
            ReviewAction.DISTILL,
            f"提炼输出，目标压缩比 {target_ratio:.0%}"
        )
        self.target_ratio = target_ratio

    def execute(self, output: str, context: Optional[Dict] = None) -> ReviewResult:
        issues = []
        suggestions = []

        lines = output.split("\n")
        # 识别可删除的行: 纯缓冲/过渡句
        removable_patterns = [
            r'^[\s]*(需要注意的是|值得注意的是|需要强调的是|此外|另外)',
            r'^[\s]*(总而言之|综上所述|总的来说|整体来看)',
            r'^[\s]*(毫无疑问|不可否认|毋庸置疑)',
        ]
        removable_indices = []
        for i, line in enumerate(lines):
            for pat in removable_patterns:
                if re.match(pat, line) and len(line.strip()) < 80:
                    removable_indices.append(i)
                    break

        if removable_indices:
            issues.append(f"[medium] 发现 {len(removable_indices)} 行缓冲/过渡句可删除")
            suggestions.append("删除过渡句和重复总结，只保留核心信息")

        current_ratio = 1.0 - len(removable_indices) / max(len(lines), 1)
        score = 1.0 if current_ratio <= self.target_ratio else 0.5 + 0.5 * (self.target_ratio / current_ratio)

        return ReviewResult(
            action=self.action,
            passed=score >= 0.7,
            issues=issues,
            suggestions=suggestions,
            score=score
        )


class BolderCommand(ReviewCommand):
    """加胆命令 — 强化观点、减少模棱两可
    
    参考: Impeccable 的 /bolder 命令
    """

    HEDGES = [
        (r'可能(?:是)?(?:一个)?(?:比较好)?的(?:选择|方案|方向)', '直接给出推荐'),
        (r'也许|或许|大概|可能(?![是的有])', '用更确定的表述替换'),
        (r'(?:在一定程度上|某种程度上|某种意义上)', '删除限定词'),
    ]

    def __init__(self):
        super().__init__(
            ReviewAction.BOLDER,
            "强化观点，减少模棱两可的表述"
        )

    def execute(self, output: str, context: Optional[Dict] = None) -> ReviewResult:
        issues = []
        suggestions = []

        for pattern, fix in self.HEDGES:
            matches = re.findall(pattern, output)
            if matches:
                issues.append(f"[medium] 发现缓冲表述: '{matches[0]}'")
                suggestions.append(f"→ {fix}")

        return ReviewResult(
            action=self.action,
            passed=len(issues) == 0,
            issues=issues,
            suggestions=suggestions,
            score=max(0.0, 1.0 - 0.15 * len(issues))
        )


# ============================================================
# 4. Review Pipeline — 组合式审查管道
#    灵感: Impeccable 的命令可组合调用
# ============================================================

class ReviewPipeline:
    """自检管道 — 组合多个ReviewCommand顺序执行
    
    用法:
        pipeline = ReviewPipeline()
        pipeline.add(PatternAuditCommand())
        pipeline.add(StructureAuditCommand())
        results = pipeline.run(agent_output)
    """

    def __init__(self, name: str = "default"):
        self.name = name
        self.commands: List[ReviewCommand] = []

    def add(self, command: ReviewCommand) -> "ReviewPipeline":
        self.commands.append(command)
        return self

    def remove(self, action: ReviewAction) -> "ReviewPipeline":
        self.commands = [c for c in self.commands if c.action != action]
        return self

    def run(self, output: str, context: Optional[Dict] = None, auto_fix: bool = False) -> List[ReviewResult]:
        """执行审查管道
        
        Args:
            output: Agent原始输出
            context: 额外上下文
            auto_fix: 是否自动应用可修复的结果 (如PolishCommand的revised_output)
        
        Returns:
            审查结果列表
        """
        results = []
        current_output = output

        for cmd in self.commands:
            result = cmd.execute(current_output, context)
            results.append(result)

            # 自动修复: 如果命令提供了revised_output且启用auto_fix
            if auto_fix and result.revised_output:
                current_output = result.revised_output
                logger.info(f"[ReviewPipeline:{self.name}] {cmd.action.value} auto-fixed output")

        return results

    def run_with_summary(self, output: str, context: Optional[Dict] = None) -> Tuple[str, float, List[str]]:
        """执行管道并返回汇总
        
        Returns:
            (最终输出, 综合评分, 所有问题列表)
        """
        results = self.run(output, context, auto_fix=True)
        
        all_issues = []
        total_score = 0.0
        current_output = output

        for result in results:
            all_issues.extend(result.issues)
            total_score += result.score
            if result.revised_output:
                current_output = result.revised_output

        avg_score = total_score / max(len(results), 1)
        return current_output, round(avg_score, 2), all_issues


# ============================================================
# 5. 便捷工厂
# ============================================================

def create_default_pipeline() -> ReviewPipeline:
    """创建默认审查管道"""
    return (ReviewPipeline("default")
            .add(PatternAuditCommand())
            .add(StructureAuditCommand())
            .add(PolishCommand()))


def create_strict_pipeline() -> ReviewPipeline:
    """创建严格审查管道 (含所有命令)"""
    return (ReviewPipeline("strict")
            .add(PatternAuditCommand())
            .add(StructureAuditCommand())
            .add(PolishCommand())
            .add(DistillCommand())
            .add(BolderCommand()))


def create_quick_pipeline() -> ReviewPipeline:
    """创建快速审查管道 (仅反模式+格式)"""
    return (ReviewPipeline("quick")
            .add(PatternAuditCommand())
            .add(PolishCommand()))
