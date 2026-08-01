"""
Topology Optimizer
===================
Learns from execution history to improve routing decisions.
Uses multi-armed bandit (MAB) to balance exploration vs exploitation.
"""

import time
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import random
import math

logger = logging.getLogger("lhab_nf.optimizer")


@dataclass
class ExecutionOutcome:
    """执行结果"""
    plan_id: str
    success: bool
    actual_latency_ms: float
    actual_cost: float
    tokens_used: int
    errors: List[str] = field(default_factory=list)
    task_completion_rate: float = 1.0
    perturbation_recovery_rate: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class RoutePattern:
    """路由模式（用于学习）"""
    task_pattern: str              # e.g., "data_analysis:complex"
    agent_chain: Tuple[str, ...]   # Agent 序列
    topology_type: str
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    avg_cost: float = 0.0
    last_used: float = 0.0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / max(1, total)
    
    @property
    def total_count(self) -> int:
        return self.success_count + self.failure_count


class TopologyOptimizer:
    """
    拓扑优化器
    
    通过记录执行结果，学习最优路由模式。
    使用 UCB1 (Upper Confidence Bound) 算法平衡探索与利用。
    """
    
    def __init__(self, exploration_factor: float = 1.0):
        """
        Args:
            exploration_factor: 探索系数（越大越倾向探索新方案）
        """
        self.exploration_factor = exploration_factor
        self.patterns: Dict[str, List[RoutePattern]] = defaultdict(list)
        self.executions: Dict[str, ExecutionOutcome] = {}
        self.requests: Dict[str, Dict[str, Any]] = {}  # plan_id -> request info
        
        # 默认权重（当没有历史数据时使用）
        self.default_weights = {
            "capability_match": 0.35,
            "load_state": 0.25,
            "cross_tier": 0.15,
            "preference": 0.15,
            "latency": 0.10,
        }
        
        # 学习到的权重（按任务模式）
        self.learned_weights: Dict[str, Dict[str, float]] = {}
        
        logger.info(f"[Optimizer] Initialized (exploration={exploration_factor})")
    
    def record_request(self, task: Any, plan: Any) -> None:
        """
        记录路由请求（在执行前调用）
        
        Args:
            task: TaskRequirement
            plan: RoutePlan
        """
        task_pattern = self._extract_task_pattern(task)
        
        self.requests[plan.plan_id] = {
            "task_pattern": task_pattern,
            "task_id": task.task_id if hasattr(task, 'task_id') else "unknown",
            "agent_chain": tuple(plan.agent_chain),
            "topology_type": plan.topology_type,
            "timestamp": time.time(),
        }
        
        logger.debug(f"[Optimizer] Recorded request: {plan.plan_id} ({task_pattern})")
    
    def record_execution(self, plan_id: str, outcome: ExecutionOutcome) -> None:
        """
        记录执行结果（在执行完成后调用）
        
        Args:
            plan_id: 路由方案 ID
            outcome: 执行结果
        """
        if plan_id not in self.requests:
            logger.warning(f"[Optimizer] Unknown plan_id: {plan_id}")
            return
        
        self.executions[plan_id] = outcome
        request_info = self.requests[plan_id]
        task_pattern = request_info["task_pattern"]
        agent_chain = request_info["agent_chain"]
        topology_type = request_info["topology_type"]
        
        # 更新或创建模式记录
        patterns = self.patterns[task_pattern]
        pattern = None
        for p in patterns:
            if p.agent_chain == agent_chain and p.topology_type == topology_type:
                pattern = p
                break
        
        if pattern is None:
            # 新创建模式
            pattern = RoutePattern(
                task_pattern=task_pattern,
                agent_chain=agent_chain,
                topology_type=topology_type,
            )
            patterns.append(pattern)
        
        # 更新统计
        if outcome.success:
            pattern.success_count += 1
        else:
            pattern.failure_count += 1
        
        # 更新平均值（指数加权）
        alpha = 0.3
        pattern.avg_latency_ms = (1 - alpha) * pattern.avg_latency_ms + alpha * outcome.actual_latency_ms
        pattern.avg_cost = (1 - alpha) * pattern.avg_cost + alpha * outcome.actual_cost
        pattern.last_used = time.time()
        
        # 清理旧数据
        self._cleanup_old_data()
        
        logger.info(
            f"[Optimizer] Recorded execution: {plan_id} "
            f"(success={outcome.success}, latency={outcome.actual_latency_ms:.0f}ms, "
            f"pattern={task_pattern}, chain={agent_chain})"
        )
    
    def get_optimal_pattern(self, task_pattern: str) -> Optional[RoutePattern]:
        """
        获取给定任务模式的最优路由模式（使用 UCB1）
        
        Args:
            task_pattern: 任务模式标识
        
        Returns:
            最优 RoutePattern，如果没有历史数据则返回 None
        """
        patterns = self.patterns.get(task_pattern, [])
        
        if not patterns:
            return None
        
        # 如果所有模式都只试过 1 次，随机选一个（探索）
        if all(p.total_count <= 1 for p in patterns):
            return random.choice(patterns)
        
        # UCB1: 平衡探索与利用
        total_trials = sum(p.total_count for p in patterns)
        
        def ucb_score(pattern: RoutePattern) -> float:
            if pattern.total_count == 0:
                return float('inf')  # 优先探索未尝试的
            
            # 利用：成功率 + 低延迟
            reward = pattern.success_rate * 0.7 + (1.0 / (1.0 + pattern.avg_latency_ms / 10000.0)) * 0.3
            
            # 探索：不确定性（越少尝试越倾向探索）
            exploration = math.sqrt(2.0 * math.log(total_trials) / pattern.total_count)
            
            return reward + self.exploration_factor * exploration
        
        best_pattern = max(patterns, key=ucb_score)
        return best_pattern
    
    def get_learned_weights(self, task_pattern: str) -> Dict[str, float]:
        """
        获取针对特定任务模式学习到的权重
        
        Args:
            task_pattern: 任务模式标识
        
        Returns:
            权重字典
        """
        if task_pattern in self.learned_weights:
            return self.learned_weights[task_pattern]
        
        # 如果没有学习到的权重，返回默认值
        return self.default_weights.copy()
    
    def learn_weights(self, task_pattern: str) -> None:
        """
        基于历史数据学习最优权重
        
        Args:
            task_pattern: 任务模式标识
        """
        patterns = self.patterns.get(task_pattern, [])
        
        if len(patterns) < 3:
            # 数据不足，无法学习
            return
        
        # 分析成功模式与失败模式的差异
        successful = [p for p in patterns if p.success_rate > 0.7]
        failed = [p for p in patterns if p.success_rate < 0.5]
        
        if not successful:
            return
        
        # 简化版：根据成功模式的特征调整权重
        # 实际应该做更复杂的特征分析
        
        # 这里只做示例：如果低延迟模式成功率高，增加 latency 权重
        avg_latency = sum(p.avg_latency_ms for p in successful) / len(successful)
        
        weights = self.default_weights.copy()
        
        if avg_latency < 10000:  # 10s 内
            weights["latency"] = 0.20  # 增加延迟权重
            weights["capability_match"] = 0.25  # 相应减少其他
        else:
            weights["latency"] = 0.05
            weights["capability_match"] = 0.40
        
        self.learned_weights[task_pattern] = weights
        logger.info(f"[Optimizer] Learned weights for {task_pattern}: {weights}")
    
    def recommend_improvements(self, plan: Any) -> List[str]:
        """
        分析当前方案，给出改进建议
        
        Args:
            plan: RoutePlan
        
        Returns:
            改进建议列表
        """
        recommendations = []
        
        task_pattern = self._extract_task_pattern_from_plan(plan)
        optimal = self.get_optimal_pattern(task_pattern)
        
        if optimal and optimal.agent_chain != tuple(plan.agent_chain):
            recommendations.append(
                f"历史数据显示，模式 '{task_pattern}' 的最优路由为 "
                f"{' → '.join(optimal.agent_chain)}（成功率 {optimal.success_rate:.1%}），"
                f"当前方案可能不是最优"
            )
        
        if plan.estimated_latency_ms > 30000:
            recommendations.append(
                f"预估延迟 {plan.estimated_latency_ms/1000:.1f}s 较长，"
                f"考虑减少 Agent 数量或使用并行拓扑"
            )
        
        if len(plan.agent_chain) > 5:
            recommendations.append(
                f"Agent 链过长（{len(plan.agent_chain)} 个），"
                f"可能增加协调开销和失败风险"
            )
        
        if not recommendations:
            recommendations.append("当前方案结构合理，无明显改进空间")
        
        return recommendations
    
    def _extract_task_pattern(self, task: Any) -> str:
        """提取任务模式标识"""
        # 基于任务的能力需求和复杂度
        caps = getattr(task, 'required_capabilities', [])
        complexity = getattr(task, 'complexity', None)
        
        if caps:
            cap_str = "+".join(sorted(caps)[:3])  # 取前 3 个能力
        else:
            cap_str = "general"
        
        if complexity:
            complexity_str = complexity.name if hasattr(complexity, 'name') else str(complexity)
        else:
            complexity_str = "moderate"
        
        return f"{cap_str}:{complexity_str}"
    
    def _extract_task_pattern_from_plan(self, plan: Any) -> str:
        """从 plan 中提取任务模式（简化版）"""
        # 实际应该从 request info 中获取
        if plan.plan_id in self.requests:
            return self.requests[plan.plan_id]["task_pattern"]
        return "unknown:unknown"
    
    def _cleanup_old_data(self) -> None:
        """清理旧数据，防止内存膨胀"""
        cutoff = time.time() - 7 * 24 * 3600  # 7 天前
        
        # 清理旧请求
        old_plans = [pid for pid, info in self.requests.items() if info["timestamp"] < cutoff]
        for pid in old_plans:
            del self.requests[pid]
            if pid in self.executions:
                del self.executions[pid]
        
        # 清理低使用率的模式
        for task_pattern in list(self.patterns.keys()):
            patterns = self.patterns[task_pattern]
            self.patterns[task_pattern] = [
                p for p in patterns 
                if p.last_used > cutoff or p.total_count >= 3
            ]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取优化器统计信息"""
        total_patterns = sum(len(patterns) for patterns in self.patterns.values())
        total_executions = len(self.executions)
        successful = sum(1 for o in self.executions.values() if o.success)
        
        return {
            "total_patterns": total_patterns,
            "total_executions": total_executions,
            "success_rate": successful / max(1, total_executions),
            "learned_weight_count": len(self.learned_weights),
        }
    
    def export_data(self) -> Dict[str, Any]:
        """导出数据用于分析"""
        return {
            "patterns": {
                pattern: [
                    {
                        "agent_chain": list(p.agent_chain),
                        "topology_type": p.topology_type,
                        "success_rate": p.success_rate,
                        "avg_latency_ms": p.avg_latency_ms,
                        "avg_cost": p.avg_cost,
                        "total_count": p.total_count,
                    }
                    for p in patterns
                ]
                for pattern, patterns in self.patterns.items()
            },
            "learned_weights": self.learned_weights,
            "stats": self.get_stats(),
        }
