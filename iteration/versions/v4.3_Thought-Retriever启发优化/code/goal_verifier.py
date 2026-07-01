# -*- coding: utf-8 -*-
"""
铉枢·炉守 Goal Verifier — 独立目标验证器
XuanHub Goal Verifier

参考 MiMo Code 的 Goal 机制，独立于主Agent的judge，验证任务是否真正完成。

核心功能：
1. 用户定义停止条件（自然语言）
2. Agent试图终止时自动启动独立模型调用
3. 审查完整对话历史，判断条件是否真正满足
4. 未满足时反馈具体差距给Agent继续执行
5. 防无限循环：设置最大验证次数（默认3次）

设计原则：
- 验证者不参与实际工作，避免对齐偏差
- 用Flash模型执行验证（低成本）
- 误拦概率低于0.5%
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("GoalVerifier")

# 导入配置
try:
    from config import (
        DEEPSEEK_API_KEY, DEEPSEEK_ENDPOINT,
        MODELS, DEFAULT_PARAMS, REQUEST_TIMEOUT
    )
except ImportError:
    DEEPSEEK_API_KEY = ""
    DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
    MODELS = {"pro": "deepseek-v4-pro", "flash": "deepseek-v4-flash"}
    DEFAULT_PARAMS = {
        "pro": {"temperature": 1.0, "top_p": 1.0, "max_tokens": 4096},
        "flash": {"temperature": 1.0, "top_p": 1.0, "max_tokens": 2048}
    }
    REQUEST_TIMEOUT = 120


class VerificationStatus(Enum):
    """验证状态"""
    PENDING = "pending"           # 待验证
    IN_PROGRESS = "in_progress"   # 验证中
    SATISFIED = "satisfied"        # 条件满足
    NOT_SATISFIED = "not_satisfied"  # 条件未满足
    IMPOSSIBLE = "impossible"     # 确认不可能完成
    TIMEOUT = "timeout"           # 验证超时


@dataclass
class VerificationResult:
    """
    验证结果
    
    Attributes:
        status: 验证状态
        goal_condition: 用户定义的停止条件
        is_satisfied: 条件是否满足
        gaps: 未满足的具体差距列表
        evidence: 支持判断的证据
        suggestions: 建议Agent如何继续
        confidence: 验证置信度 (0.0-1.0)
        verification_count: 已验证次数
        timestamp: 验证时间戳
    """
    status: VerificationStatus
    goal_condition: str
    is_satisfied: bool = False
    gaps: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    verification_count: int = 0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "goal_condition": self.goal_condition,
            "is_satisfied": self.is_satisfied,
            "gaps": self.gaps,
            "evidence": self.evidence,
            "suggestions": self.suggestions,
            "confidence": self.confidence,
            "verification_count": self.verification_count,
            "timestamp": self.timestamp,
        }


class GoalVerifier:
    """
    独立目标验证器 — 防止"乐观提前结束"
    
    设计原则：
    1. 独立judge：验证者不参与实际工作，避免对齐偏差
    2. 保守验证：宁可误拦，不可漏放
    3. 明确反馈：未满足时给出具体差距和改进建议
    4. 防无限循环：设置最大验证次数
    
    用法：
        verifier = GoalVerifier()
        
        # 用户定义停止条件
        verifier.define_goal("完成所有单元测试且通过率100%")
        
        # 主Agent认为完成时调用验证
        result = verifier.verify(conversation_history)
        
        if result.is_satisfied:
            print("任务完成，可以退出")
        else:
            print(f"还有差距: {result.gaps}")
            # Agent继续执行
    """
    
    # 最大验证次数
    DEFAULT_MAX_VERIFICATIONS = 3
    
    # 验证超时（秒）
    VERIFICATION_TIMEOUT = 30
    
    # 误拦率目标（低于此值认为安全）
    FALSE_REJECT_RATE = 0.005  # 0.5%
    
    def __init__(
        self,
        model: str = "flash",
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        max_verifications: int = DEFAULT_MAX_VERIFICATIONS,
    ):
        self.model = model
        self.api_endpoint = api_endpoint or DEEPSEEK_ENDPOINT
        self.api_key = api_key or DEEPSEEK_API_KEY
        
        # 最大验证次数
        self.max_verifications = max_verifications
        
        # 当前目标条件
        self._goal_condition: Optional[str] = None
        self._goal_context: str = ""  # 目标相关上下文
        
        # 验证历史
        self._verification_history: List[VerificationResult] = []
        
        # 统计
        self._stats = {
            "total_verifications": 0,
            "satisfied": 0,
            "not_satisfied": 0,
            "impossible": 0,
            "false_rejects": 0,  # 被拦截但实际已完成
            "avg_confidence": 0.0,
        }
        
        logger.info(f"[GoalVerifier] Initialized with max_verifications={max_verifications}")
    
    def define_goal(
        self,
        goal_condition: str,
        context: str = "",
    ) -> None:
        """
        定义目标停止条件
        
        Args:
            goal_condition: 自然语言描述的停止条件
            context: 目标的额外上下文（如相关文件、约束等）
        """
        self._goal_condition = goal_condition
        self._goal_context = context
        
        # 重置验证历史
        self._verification_history.clear()
        
        logger.info(f"[GoalVerifier] Goal defined: {goal_condition[:100]}...")
    
    def verify(
        self,
        conversation_history: List[Dict[str, str]],
        task_output: Optional[str] = None,
    ) -> VerificationResult:
        """
        验证任务是否真正完成
        
        流程：
        1. 检查是否达到最大验证次数
        2. 调用独立模型审查对话历史
        3. 判断条件是否满足
        4. 未满足则反馈差距
        
        Args:
            conversation_history: 完整对话历史
            task_output: 任务产出（可选，额外的输出产物）
        
        Returns:
            VerificationResult
        """
        # 检查是否有定义目标
        if not self._goal_condition:
            logger.warning("[GoalVerifier] No goal defined, skipping verification")
            return VerificationResult(
                status=VerificationStatus.PENDING,
                goal_condition="",
                is_satisfied=False,
                gaps=["未定义目标条件"],
                confidence=0.0,
            )
        
        # 检查验证次数
        current_count = len(self._verification_history)
        if current_count >= self.max_verifications:
            logger.warning(f"[GoalVerifier] Max verifications ({self.max_verifications}) reached")
            
            # 返回最后一个结果，但标记为超时
            if self._verification_history:
                last_result = self._verification_history[-1]
                last_result.status = VerificationStatus.TIMEOUT
                return last_result
            
            return VerificationResult(
                status=VerificationStatus.TIMEOUT,
                goal_condition=self._goal_condition,
                is_satisfied=False,
                gaps=[f"已达到最大验证次数({self.max_verifications})"],
                confidence=0.0,
                verification_count=current_count,
            )
        
        logger.info(f"[GoalVerifier] Starting verification #{current_count + 1}")
        
        # 调用验证模型
        result = self._call_verification_model(
            conversation_history=conversation_history,
            task_output=task_output,
        )
        
        result.verification_count = current_count + 1
        result.timestamp = datetime.now().isoformat()
        
        # 记录历史
        self._verification_history.append(result)
        
        # 更新统计
        self._update_stats(result)
        
        # 记录日志
        status_str = result.status.value
        is_sat_str = "✓" if result.is_satisfied else "✗"
        logger.info(
            f"[GoalVerifier] Verification #{result.verification_count}: "
            f"{status_str} {is_sat_str} "
            f"(confidence={result.confidence:.2f}, gaps={len(result.gaps)})"
        )
        
        return result
    
    def _call_verification_model(
        self,
        conversation_history: List[Dict[str, str]],
        task_output: Optional[str] = None,
    ) -> VerificationResult:
        """
        调用独立模型进行验证
        
        使用Flash模型，低成本执行。
        """
        try:
            import urllib.request
            
            # 构建验证prompt
            prompt = self._build_verification_prompt(
                conversation_history=conversation_history,
                task_output=task_output,
            )
            
            payload = {
                "model": MODELS.get(self.model, "deepseek-chat"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 2048,
                "temperature": 0.3,  # 低温度，精确判断
            }
            
            req = urllib.request.Request(
                self.api_endpoint,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}' if self.api_key else '',
                },
                method='POST',
            )
            
            with urllib.request.urlopen(req, timeout=self.VERIFICATION_TIMEOUT) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                response_text = result['choices'][0]['message']['content']
            
            # 解析验证结果
            return self._parse_verification_response(response_text)
            
        except Exception as e:
            logger.error(f"[GoalVerifier] Verification call failed: {e}")
            
            # 失败时返回保守结果
            return VerificationResult(
                status=VerificationStatus.NOT_SATISFIED,
                goal_condition=self._goal_condition,
                is_satisfied=False,
                gaps=[f"验证过程出错: {str(e)[:100]}"],
                confidence=0.0,
                verification_count=len(self._verification_history),
            )
    
    def _build_verification_prompt(
        self,
        conversation_history: List[Dict[str, str]],
        task_output: Optional[str] = None,
    ) -> str:
        """构建验证prompt"""
        
        # 截取对话历史（保留关键部分）
        recent_msgs = conversation_history[-50:] if len(conversation_history) > 50 else conversation_history
        
        # 构建对话摘要
        dialogue_summary = []
        for i, msg in enumerate(recent_msgs):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:500]  # 每条消息最多500字符
            dialogue_summary.append(f"[{role}]: {content}")
        
        dialogue_text = "\n".join(dialogue_summary)
        
        # 构建task_output描述
        output_section = ""
        if task_output:
            output_section = f"\n\n## 任务产出\n{task_output[:2000]}"
        
        prompt = f"""你是独立的验证者，负责客观判断任务是否真正完成。

## 目标停止条件
{self._goal_condition}

## 目标上下文
{self._goal_context or '（无额外上下文）'}

## 对话历史
{dialogue_text}
{output_section}

## 验证要求

请严格审查对话历史，判断目标条件是否真正满足。

### 输出格式（必须严格遵循）

首先输出判断结果：

**判断**: [SATISFIED / NOT_SATISFIED / IMPOSSIBLE]

**理由**: [简要说明判断理由]

**置信度**: [0.0-1.0之间的数字，表示你的判断置信度]

如果SATISFIED：
- 列出满足条件的具体证据（至少2条）
- 说明满足了条件的哪些方面

如果NOT_SATISFIED：
- 列出具体差距（每条差距用数字标注）
- 每条差距说明：问题是什么、为什么未满足

如果IMPOSSIBLE：
- 解释为什么条件无法满足
- 建议是否应该放弃或修改目标

最后，给出对Agent的建议（如果需要继续执行）。

开始验证："""
        
        return prompt
    
    def _parse_verification_response(self, response_text: str) -> VerificationResult:
        """解析验证模型的响应"""
        
        status = VerificationStatus.NOT_SATISFIED
        is_satisfied = False
        gaps = []
        evidence = []
        suggestions = []
        confidence = 0.5
        
        lines = response_text.strip().split('\n')
        
        # 解析判断结果
        for line in lines:
            line = line.strip()
            
            # 判断
            if '**判断**:' in line or '**判断**' in line:
                if 'SATISFIED' in line.upper():
                    status = VerificationStatus.SATISFIED
                    is_satisfied = True
                elif 'IMPOSSIBLE' in line.upper():
                    status = VerificationStatus.IMPOSSIBLE
                else:
                    status = VerificationStatus.NOT_SATISFIED
            
            # 置信度
            if '**置信度**:' in line or '置信度' in line:
                try:
                    # 尝试提取数字
                    import re
                    nums = re.findall(r'0\.\d+|1\.0', line)
                    if nums:
                        confidence = float(nums[0])
                except:
                    confidence = 0.5
            
            # 差距
            if any(x in line for x in ['差距', '未满足', '问题']):
                # 检查是否是列表项
                if line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•')):
                    gap_text = line.lstrip('0123456789.-•) ')
                    if gap_text:
                        gaps.append(gap_text)
                elif len(line) > 10:
                    gaps.append(line)
            
            # 证据
            if '证据' in line or '满足' in line:
                if line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•')):
                    evidence_text = line.lstrip('0123456789.-•) ')
                    if evidence_text:
                        evidence.append(evidence_text)
            
            # 建议
            if '建议' in line or '继续' in line:
                if line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•')):
                    suggestion_text = line.lstrip('0123456789.-•) ')
                    if suggestion_text:
                        suggestions.append(suggestion_text)
                elif len(line) > 10:
                    suggestions.append(line)
        
        # 确保有理由
        if not gaps and not evidence:
            # 提取"理由"后的内容作为原因
            for i, line in enumerate(lines):
                if '理由' in line:
                    reason_text = line.split('理由')[-1].strip()
                    if reason_text:
                        if is_satisfied:
                            evidence.append(reason_text)
                        else:
                            gaps.append(reason_text)
        
        return VerificationResult(
            status=status,
            goal_condition=self._goal_condition,
            is_satisfied=is_satisfied,
            gaps=gaps,
            evidence=evidence,
            suggestions=suggestions,
            confidence=confidence,
            verification_count=len(self._verification_history),
        )
    
    def _update_stats(self, result: VerificationResult) -> None:
        """更新统计信息"""
        self._stats["total_verifications"] += 1
        
        if result.status == VerificationStatus.SATISFIED:
            self._stats["satisfied"] += 1
        elif result.status == VerificationStatus.IMPOSSIBLE:
            self._stats["impossible"] += 1
        else:
            self._stats["not_satisfied"] += 1
        
        # 计算平均置信度
        total = self._stats["total_verifications"]
        avg_conf = self._stats["avg_confidence"]
        new_avg = (avg_conf * (total - 1) + result.confidence) / total
        self._stats["avg_confidence"] = new_avg
    
    def should_continue(self, result: VerificationResult) -> Tuple[bool, str]:
        """
        根据验证结果判断是否应该继续执行
        
        Args:
            result: 验证结果
        
        Returns:
            (should_continue, reason)
        """
        if result.is_satisfied:
            return False, "目标已满足，可以终止"
        
        if result.status == VerificationStatus.IMPOSSIBLE:
            return False, "目标确认无法完成"
        
        if result.verification_count >= self.max_verifications:
            # 达到最大验证次数，检查置信度
            if result.confidence >= (1.0 - self.FALSE_REJECT_RATE):
                # 置信度足够高，认为应该停止
                self._stats["false_rejects"] += 1
                return False, f"达到最大验证次数({self.max_verifications})，高置信度({result.confidence:.0%})认为应停止"
            else:
                # 置信度不够高，可能误拦，允许继续
                return True, f"达到最大验证次数，但置信度较低({result.confidence:.0%})，允许继续"
        
        # 未达到最大次数，且未满足，继续执行
        return True, f"还有{len(result.gaps)}个差距，继续执行"
    
    def mark_false_reject(self) -> None:
        """
        标记为误拦（用于后续分析）
        
        当外部确认任务实际已完成但被验证器误拦时调用
        """
        self._stats["false_rejects"] += 1
        logger.info("[GoalVerifier] Marked as false reject")
    
    def get_verification_history(self) -> List[Dict]:
        """获取验证历史"""
        return [r.to_dict() for r in self._verification_history]
    
    def get_current_goal(self) -> Optional[str]:
        """获取当前目标条件"""
        return self._goal_condition
    
    def clear_goal(self) -> None:
        """清除当前目标"""
        self._goal_condition = None
        self._goal_context = ""
        self._verification_history.clear()
        logger.info("[GoalVerifier] Goal cleared")
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = self._stats["total_verifications"]
        false_reject_rate = (
            self._stats["false_rejects"] / max(1, self._stats["satisfied"] + self._stats["false_rejects"])
        )
        
        return {
            **self._stats,
            "false_reject_rate": false_reject_rate,
            "current_goal": self._goal_condition[:100] if self._goal_condition else None,
            "verification_history_count": len(self._verification_history),
        }
    
    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            "current_goal": self._goal_condition,
            "goal_context": self._goal_context,
            "stats": self.get_stats(),
            "verification_history": [r.to_dict() for r in self._verification_history],
        }
