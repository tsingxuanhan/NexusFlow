# -*- coding: utf-8 -*-
"""
铉枢·炉守 动态拓扑路由器
Dynamic Cognitive Topology Router — 荣耀赛题核心模块

基于Agent能力图谱和任务特征，实时计算最优协作拓扑。
借鉴TEN Agent的模块化Pipeline思想，但核心算法原创。

核心创新:
- 运行时动态重建Agent协作图（非静态编排）
- 基于认知负载感知的路径选择（非简单最短路径）
- 支持异常时的拓扑自愈（Agent故障→自动重路由）

依赖: networkx (轻量图计算，无C扩展)
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger("DynamicRouter")

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx not installed, dynamic router degraded to simple mode")


# ============ 数据结构 ============

class AgentLoadState(Enum):
    """Agent负载状态"""
    IDLE = "idle"           # 空闲
    BUSY = "busy"           # 正常工作中
    OVERLOADED = "overloaded"  # 过载（需要降载）
    OFFLINE = "offline"     # 离线/故障
    WARMING = "warming"     # 预热中（刚被唤醒）


class TaskComplexity(Enum):
    """任务复杂度等级"""
    TRIVIAL = 1     # 单步可完成
    SIMPLE = 2      # 2-5步
    MODERATE = 3    # 5-20步
    COMPLEX = 4     # 20-50步
    EPIC = 5        # 50+步，超长程


@dataclass
class AgentCapabilityProfile:
    """Agent能力画像 — 路由器视角"""
    agent_id: str
    name: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    domain_expertise: List[str] = field(default_factory=list)
    
    # 运行时状态
    load_state: AgentLoadState = AgentLoadState.IDLE
    current_tasks: int = 0
    max_concurrent: int = 3
    avg_latency_ms: float = 500.0   # 历史平均响应延迟
    success_rate: float = 1.0       # 历史成功率
    tier: str = "cloud"             # edge / fog / cloud
    
    # 认知特征
    reasoning_depth: float = 0.5    # 0=快速直觉, 1=深度推理
    creativity: float = 0.5         # 0=确定性, 1=探索性
    context_window: int = 8192      # 上下文窗口大小
    
    # 协作特征
    can_handoff: bool = True        # 是否支持任务交接
    preferred_partners: List[str] = field(default_factory=list)  # 偏好协作对象
    
    def compute_score(self) -> float:
        """计算综合可用性评分 (0-1)"""
        if self.load_state == AgentLoadState.OFFLINE:
            return 0.0
        
        load_factor = 1.0 - (self.current_tasks / max(self.max_concurrent, 1))
        health_factor = self.success_rate
        latency_factor = 1.0 / (1.0 + self.avg_latency_ms / 1000.0)
        
        if self.load_state == AgentLoadState.OVERLOADED:
            load_factor *= 0.3
        elif self.load_state == AgentLoadState.WARMING:
            load_factor *= 0.5
        
        return round(load_factor * health_factor * latency_factor, 4)


@dataclass
class TaskRequirement:
    """任务需求描述"""
    task_id: str = ""
    description: str = ""
    required_capabilities: List[str] = field(default_factory=list)
    required_domains: List[str] = field(default_factory=list)
    complexity: TaskComplexity = TaskComplexity.MODERATE
    latency_budget_ms: float = 30000.0    # 延迟预算
    privacy_level: int = 0                 # 0=公开, 1=内部, 2=敏感
    preferred_tier: Optional[str] = None   # 优先部署层
    min_reasoning_depth: float = 0.0       # 最低推理深度要求
    is_creative: bool = False              # 是否需要创造性
    # Phase 7: 认知分工字段
    execution_mode: str = "sequential"     # "sequential" | "cognitive_division"
    perspective_count: int = 2             # 视角数量
    decomposition_strategy: Optional[str] = None  # 分解策略


@dataclass
class RoutePlan:
    """路由方案"""
    plan_id: str = ""
    task_id: str = ""
    agent_chain: List[str] = field(default_factory=list)  # Agent执行链
    topology_type: str = "sequential"  # sequential / parallel / hybrid / dynamic / star
    estimated_cost: float = 0.0        # 预估Token成本
    estimated_latency_ms: float = 0.0  # 预估总延迟
    confidence: float = 0.0            # 路由置信度
    fallback_plan: Optional[str] = None  # 备选方案ID
    created_at: float = field(default_factory=time.time)
    
    # 执行状态追踪
    status: str = "planned"  # planned / executing / completed / failed / rerouted
    executed_agents: List[str] = field(default_factory=list)
    actual_latency_ms: float = 0.0
    
    # Phase 7: 认知分工计划
    cdol_enabled: bool = False
    perspective_assignments: List[Dict] = field(default_factory=list)
    # 每个 assignment: {agent_id, perspective_question, context_mask, role_constraint}


# ============ 拓扑路由器核心 ============

class DynamicTopologyRouter:
    """
    动态拓扑路由器
    
    核心能力:
    1. 维护Agent能力图谱（运行时动态更新）
    2. 根据任务需求计算最优协作拓扑
    3. 支持异常时的拓扑自愈
    4. 历史路由经验学习
    
    与A2AProtocol的关系:
    - A2AProtocol负责消息传递（通信层）
    - DynamicTopologyRouter负责路径决策（决策层）
    - Router输出RoutePlan → Protocol执行消息路由
    """
    
    def __init__(self, auto_rebuild_interval: int = 10):
        """
        Args:
            auto_rebuild_interval: 每隔N次路由请求自动重建拓扑图
        """
        self._agents: Dict[str, AgentCapabilityProfile] = {}
        self._topology: Optional[Any] = nx.DiGraph() if HAS_NETWORKX else None
        self._route_history: List[RoutePlan] = []
        self._request_count = 0
        self._auto_rebuild_interval = auto_rebuild_interval
        
        # 经验学习：capability → 成功路由模式
        self._route_patterns: Dict[str, List[RoutePlan]] = defaultdict(list)
        
        logger.info("[DynamicRouter] Initialized" + 
                    (" (networkx available)" if HAS_NETWORKX else " (simple mode)"))
    
    # ============ Agent注册与画像管理 ============
    
    def register_agent(self, profile: AgentCapabilityProfile) -> None:
        """注册Agent到路由器"""
        self._agents[profile.agent_id] = profile
        self._rebuild_topology()
        logger.info(
            f"[DynamicRouter] Registered agent: {profile.name} "
            f"(caps: {profile.capabilities}, tier: {profile.tier}, "
            f"score: {profile.compute_score()})"
        )
    
    def register_from_a2a(self, agent_info) -> None:
        """
        从A2AProtocol的AgentInfo注册
        
        Args:
            agent_info: A2AProtocol.AgentInfo实例
        """
        caps = [c.name for c in agent_info.capabilities]
        domains = agent_info.metadata.get("domains", [])
        tier = agent_info.metadata.get("tier", "cloud")
        
        profile = AgentCapabilityProfile(
            agent_id=agent_info.agent_id,
            name=agent_info.name,
            role=agent_info.role,
            capabilities=caps,
            domain_expertise=domains,
            tier=tier,
            load_state=AgentLoadState.IDLE if agent_info.status == "online" else AgentLoadState.OFFLINE,
        )
        self.register_agent(profile)
    
    def update_agent_state(self, agent_id: str, 
                           load_state: Optional[AgentLoadState] = None,
                           current_tasks: Optional[int] = None,
                           avg_latency_ms: Optional[float] = None,
                           success_rate: Optional[float] = None) -> None:
        """更新Agent运行时状态"""
        if agent_id not in self._agents:
            logger.warning(f"[DynamicRouter] Unknown agent: {agent_id}")
            return
        
        agent = self._agents[agent_id]
        if load_state is not None:
            agent.load_state = load_state
        if current_tasks is not None:
            agent.current_tasks = current_tasks
        if avg_latency_ms is not None:
            # 指数加权移动平均
            agent.avg_latency_ms = 0.7 * agent.avg_latency_ms + 0.3 * avg_latency_ms
        if success_rate is not None:
            agent.success_rate = 0.8 * agent.success_rate + 0.2 * success_rate
        
        self._rebuild_topology()
    
    def unregister_agent(self, agent_id: str) -> None:
        """注销Agent"""
        if agent_id in self._agents:
            name = self._agents[agent_id].name
            del self._agents[agent_id]
            self._rebuild_topology()
            logger.info(f"[DynamicRouter] Unregistered: {name}")
    
    # ============ 拓扑构建 ============
    
    def _rebuild_topology(self) -> None:
        """重建协作拓扑图"""
        if not HAS_NETWORKX:
            return
        
        G = nx.DiGraph()
        
        for agent_id, profile in self._agents.items():
            score = profile.compute_score()
            G.add_node(agent_id, 
                       name=profile.name,
                       role=profile.role,
                       score=score,
                       tier=profile.tier,
                       capabilities=profile.capabilities)
        
        # 建立连接边（权重 = 协作成本）
        for src_id, src in self._agents.items():
            for dst_id, dst in self._agents.items():
                if src_id == dst_id:
                    continue
                if src.load_state == AgentLoadState.OFFLINE or \
                   dst.load_state == AgentLoadState.OFFLINE:
                    continue
                
                weight = self._compute_edge_weight(src, dst)
                if weight < float('inf'):
                    G.add_edge(src_id, dst_id, weight=weight)
        
        self._topology = G
    
    def _compute_edge_weight(self, src: AgentCapabilityProfile, 
                              dst: AgentCapabilityProfile) -> float:
        """
        计算两个Agent之间的协作边权重
        
        权重因素:
        - 能力互补度（输出→输入匹配）
        - 协作偏好（preferred_partners加分）
        - 部署层延迟（跨层通信加惩罚）
        - 负载状态（过载Agent入边权重增大）
        """
        weight = 1.0
        
        # 1. 负载惩罚
        dst_score = dst.compute_score()
        if dst_score < 0.2:
            return float('inf')  # 不可达
        weight *= (1.0 / max(dst_score, 0.1))
        
        # 2. 协作偏好加成
        if dst.agent_id in src.preferred_partners:
            weight *= 0.6  # 偏好伙伴降低40%成本
        if src.agent_id in dst.preferred_partners:
            weight *= 0.8
        
        # 3. 跨层通信惩罚
        tier_penalty = {"edge": 0, "fog": 1, "cloud": 2}
        src_tier = tier_penalty.get(src.tier, 2)
        dst_tier = tier_penalty.get(dst.tier, 2)
        cross_tier = abs(src_tier - dst_tier)
        weight *= (1.0 + cross_tier * 0.5)
        
        # 4. 延迟因子
        weight *= (1.0 + dst.avg_latency_ms / 5000.0)
        
        return weight
    
    # ============ 路由决策 ============
    
    def route(self, task: TaskRequirement) -> RoutePlan:
        """
        核心路由决策：为任务计算最优Agent协作链
        
        算法流程:
        1. 筛选候选Agent（能力匹配 + 状态可用）
        2. 基于拓扑图计算最优路径
        3. 考虑隐私约束（敏感任务限制在edge层）
        4. 生成备选方案
        5. 返回RoutePlan
        
        Args:
            task: 任务需求描述
            
        Returns:
            RoutePlan: 最优路由方案
        """
        self._request_count += 1
        
        # 定期重建
        if self._request_count % self._auto_rebuild_interval == 0:
            self._rebuild_topology()
        
        # Step 1: 筛选候选Agent
        candidates = self._filter_candidates(task)
        if not candidates:
            logger.warning(f"[DynamicRouter] No candidates for task: {task.task_id}")
            return RoutePlan(
                plan_id=str(uuid.uuid4())[:8],
                task_id=task.task_id,
                status="failed",
                confidence=0.0
            )
        
        # Step 2: 计算最优路径
        if HAS_NETWORKX and len(candidates) > 1:
            plan = self._compute_optimal_path(task, candidates)
        else:
            plan = self._compute_simple_path(task, candidates)
        
        # Phase 7: 认知分工模式
        if task.execution_mode == "cognitive_division":
            plan.cdol_enabled = True
            plan.perspective_assignments = self._generate_perspective_assignments(
                task, candidates
            )
            # 认知分工不需要串行agent_chain，而是并行Agent集合
            plan.agent_chain = [a.agent_id for a in candidates[:task.perspective_count]]
            plan.topology_type = "star"  # 星型拓扑：所有Agent连到FusionJudge
            plan.confidence = self._estimate_chain_confidence(plan.agent_chain)
            logger.info(
                f"[DynamicRouter] CDoL mode enabled: {len(plan.perspective_assignments)} perspectives"
            )
        
        # Step 3: 生成备选方案
        plan.fallback_plan = self._generate_fallback(task, candidates, plan)
        
        # Step 4: 记录历史
        self._route_history.append(plan)
        pattern_key = self._extract_pattern_key(task)
        self._route_patterns[pattern_key].append(plan)
        
        # 保持历史窗口
        if len(self._route_history) > 200:
            self._route_history = self._route_history[-200:]
        
        logger.info(
            f"[DynamicRouter] Route plan {plan.plan_id}: "
            f"chain={plan.agent_chain}, topology={plan.topology_type}, "
            f"confidence={plan.confidence:.2f}"
        )
        
        return plan
    
    def _filter_candidates(self, task: TaskRequirement) -> List[AgentCapabilityProfile]:
        """筛选满足任务需求的候选Agent"""
        candidates = []
        
        for agent_id, profile in self._agents.items():
            # 离线过滤
            if profile.load_state == AgentLoadState.OFFLINE:
                continue
            
            # 隐私约束：敏感任务只在指定层
            if task.privacy_level >= 2 and task.preferred_tier and profile.tier != task.preferred_tier:
                continue
            
            # 能力匹配
            cap_match = self._capability_match_score(profile, task)
            if cap_match <= 0:
                continue
            
            candidates.append(profile)
        
        # 按综合评分排序
        candidates.sort(key=lambda p: p.compute_score() * 
                       self._capability_match_score(p, task), reverse=True)
        
        return candidates
    
    def _generate_perspective_assignments(
        self,
        task: TaskRequirement,
        candidates: List[AgentCapabilityProfile],
    ) -> List[Dict]:
        """Phase 7: 基于任务特征生成视角分配
        
        调用PerspectiveDecomposer生成视角分配方案，
        并转换为路由方案格式的字典列表。
        
        Args:
            task: 任务需求
            candidates: 候选Agent列表
            
        Returns:
            视角分配字典列表
        """
        try:
            from cognitive_division_engine import PerspectiveDecomposer
            decomposer = PerspectiveDecomposer()
            plan = decomposer.decompose(
                task.description,
                agents=candidates,
                strategy=task.decomposition_strategy,
                perspective_count=task.perspective_count,
            )
            return [
                {
                    "agent_id": a.agent_id,
                    "perspective_question": a.perspective_question,
                    "context_mask": a.context_mask.to_dict(),
                    "role_constraint": a.role_constraint,
                }
                for a in plan.assignments
            ]
        except ImportError:
            logger.warning("[DynamicRouter] cognitive_division_engine not available, generating simple assignments")
            # 降级：简单分配
            assignments = []
            for i, c in enumerate(candidates[:task.perspective_count]):
                assignments.append({
                    "agent_id": c.agent_id,
                    "perspective_question": f"从第{i+1}个视角分析: {task.description}",
                    "context_mask": {"allowed_evidence": ["all"], "blocked_evidence": [],
                                     "allowed_domains": c.domain_expertise[:2],
                                     "blocked_domains": [], "abstraction_level": "mixed"},
                    "role_constraint": None,
                })
            return assignments
    
    def _capability_match_score(self, profile: AgentCapabilityProfile, 
                                 task: TaskRequirement) -> float:
        """计算Agent能力与任务需求的匹配度 (0-1)"""
        score = 0.0
        factors = 0
        
        # 能力匹配
        if task.required_capabilities:
            matched = sum(1 for cap in task.required_capabilities 
                        if any(cap.lower() in c.lower() for c in profile.capabilities))
            cap_score = matched / len(task.required_capabilities)
            score += cap_score
            factors += 1
        
        # 领域匹配
        if task.required_domains:
            matched = sum(1 for d in task.required_domains 
                        if any(d.lower() in e.lower() for e in profile.domain_expertise))
            domain_score = matched / len(task.required_domains)
            score += domain_score
            factors += 1
        
        # 推理深度匹配
        if task.min_reasoning_depth > 0:
            depth_score = min(1.0, profile.reasoning_depth / task.min_reasoning_depth)
            score += depth_score
            factors += 1
        
        # 创造性匹配
        if task.is_creative:
            creativity_score = profile.creativity
            score += creativity_score
            factors += 1
        
        if factors == 0:
            return 0.5  # 没有明确要求时给基础分
        
        return score / factors
    
    def _compute_optimal_path(self, task: TaskRequirement, 
                               candidates: List[AgentCapabilityProfile]) -> RoutePlan:
        """基于NetworkX计算最优协作路径"""
        plan = RoutePlan(
            plan_id=str(uuid.uuid4())[:8],
            task_id=task.task_id,
        )
        
        # 根据任务复杂度决定拓扑类型
        if task.complexity.value <= 2:
            # 简单任务：选最强单Agent
            best = max(candidates, key=lambda p: p.compute_score())
            plan.agent_chain = [best.agent_id]
            plan.topology_type = "sequential"
            plan.confidence = best.compute_score()
            plan.estimated_latency_ms = best.avg_latency_ms
            
        elif task.complexity.value <= 3:
            # 中等任务：选2-3个互补Agent
            chain = self._find_complementary_chain(task, candidates, max_len=3)
            plan.agent_chain = chain
            plan.topology_type = "sequential" if len(chain) <= 2 else "hybrid"
            plan.confidence = self._estimate_chain_confidence(chain)
            plan.estimated_latency_ms = sum(
                self._agents[aid].avg_latency_ms for aid in chain if aid in self._agents
            )
            
        else:
            # 复杂/超长程任务：动态拓扑
            chain = self._find_complementary_chain(task, candidates, max_len=8)
            
            # 分析是否有可并行的子链
            parallel_groups = self._detect_parallel_opportunities(chain, task)
            if parallel_groups:
                plan.topology_type = "hybrid"
            else:
                plan.topology_type = "dynamic"
            
            plan.agent_chain = chain
            plan.confidence = self._estimate_chain_confidence(chain) * 0.9  # 长链降置信
            plan.estimated_latency_ms = self._estimate_chain_latency(chain, parallel_groups)
        
        # 预估Token成本
        plan.estimated_cost = len(plan.agent_chain) * task.complexity.value * 500
        
        return plan
    
    def _compute_simple_path(self, task: TaskRequirement,
                              candidates: List[AgentCapabilityProfile]) -> RoutePlan:
        """无NetworkX时的简化路由"""
        plan = RoutePlan(
            plan_id=str(uuid.uuid4())[:8],
            task_id=task.task_id,
        )
        
        if task.complexity.value <= 2:
            best = max(candidates, key=lambda p: p.compute_score())
            plan.agent_chain = [best.agent_id]
            plan.topology_type = "sequential"
            plan.confidence = best.compute_score()
        else:
            # 选前N个最佳Agent
            n = min(task.complexity.value, len(candidates))
            plan.agent_chain = [c.agent_id for c in candidates[:n]]
            plan.topology_type = "sequential"
            plan.confidence = 0.6
        
        plan.estimated_latency_ms = sum(
            self._agents[aid].avg_latency_ms for aid in plan.agent_chain if aid in self._agents
        )
        plan.estimated_cost = len(plan.agent_chain) * task.complexity.value * 500
        
        return plan
    
    def _find_complementary_chain(self, task: TaskRequirement,
                                    candidates: List[AgentCapabilityProfile],
                                    max_len: int = 5) -> List[str]:
        """
        寻找能力互补的Agent链
        
        策略: 贪心选择，每步选与已选集合互补度最高的Agent
        """
        if not candidates:
            return []
        
        chain = [candidates[0].agent_id]  # 从最强候选开始
        covered_caps = set(candidates[0].capabilities)
        covered_caps.update(task.required_capabilities)  # 假设第一个满足了部分
        
        for _ in range(max_len - 1):
            best_next = None
            best_complementarity = -1
            
            for c in candidates:
                if c.agent_id in chain:
                    continue
                
                # 计算与已选集合的互补度
                new_caps = set(c.capabilities) - covered_caps
                complementarity = len(new_caps) * c.compute_score()
                
                # 偏好加成
                if any(self._agents.get(prev) and 
                       c.agent_id in self._agents[prev].preferred_partners 
                       for prev in chain if prev in self._agents):
                    complementarity *= 1.3
                
                if complementarity > best_complementarity:
                    best_complementarity = complementarity
                    best_next = c
            
            if best_next and best_complementarity > 0.1:
                chain.append(best_next.agent_id)
                covered_caps.update(best_next.capabilities)
            else:
                break
        
        return chain
    
    def _detect_parallel_opportunities(self, chain: List[str], 
                                         task: TaskRequirement) -> List[List[str]]:
        """检测链中可并行执行的Agent组"""
        if len(chain) <= 2:
            return []
        
        # 简单启发式：无依赖关系的相邻Agent可并行
        groups = []
        i = 1
        while i < len(chain) - 1:
            # 如果前后两个Agent的能力不重叠，可以并行
            caps_a = set(self._agents[chain[i]].capabilities) if chain[i] in self._agents else set()
            caps_b = set(self._agents[chain[i+1]].capabilities) if chain[i+1] in self._agents else set()
            
            if not caps_a.intersection(caps_b):
                groups.append([chain[i], chain[i+1]])
                i += 2
            else:
                i += 1
        
        return groups
    
    def _estimate_chain_confidence(self, chain: List[str]) -> float:
        """估计Agent链的执行置信度"""
        if not chain:
            return 0.0
        
        scores = []
        for aid in chain:
            if aid in self._agents:
                scores.append(self._agents[aid].compute_score())
        
        if not scores:
            return 0.0
        
        # 链的置信度 = 最弱环节 * 链长度惩罚
        min_score = min(scores)
        avg_score = sum(scores) / len(scores)
        length_penalty = 0.95 ** max(0, len(chain) - 2)
        
        return round(min(1.0, (0.6 * min_score + 0.4 * avg_score) * length_penalty), 4)
    
    def _estimate_chain_latency(self, chain: List[str], 
                                  parallel_groups: List[List[str]]) -> float:
        """估计总延迟（考虑并行）"""
        if not chain:
            return 0.0
        
        parallel_agents = set()
        for group in parallel_groups:
            parallel_agents.update(group)
        
        total = 0.0
        for aid in chain:
            if aid in self._agents and aid not in parallel_agents:
                total += self._agents[aid].avg_latency_ms
            elif aid in self._agents:
                # 并行的只算最慢的
                total += self._agents[aid].avg_latency_ms * 0.3
        
        return total
    
    def _generate_fallback(self, task: TaskRequirement,
                            candidates: List[AgentCapabilityProfile],
                            primary: RoutePlan) -> Optional[str]:
        """生成备选方案"""
        if len(candidates) <= len(primary.agent_chain):
            return None
        
        # 备选：用排名靠后的Agent替换最弱环节
        fallback_id = str(uuid.uuid4())[:8]
        logger.debug(f"[DynamicRouter] Fallback plan generated: {fallback_id}")
        return fallback_id
    
    def _extract_pattern_key(self, task: TaskRequirement) -> str:
        """提取路由模式键（用于经验学习）"""
        caps = sorted(task.required_capabilities)[:3]
        return f"{task.complexity.value}|{'|'.join(caps)}"
    
    # ============ 拓扑自愈 ============
    
    def handle_agent_failure(self, failed_agent_id: str, 
                              current_plan: RoutePlan) -> Optional[RoutePlan]:
        """
        Agent故障时的拓扑自愈
        
        策略:
        1. 从当前链中移除故障Agent
        2. 查找替代Agent
        3. 如果无法替代，拆分任务为子链
        4. 返回新的RoutePlan
        
        Args:
            failed_agent_id: 故障Agent ID
            current_plan: 当前路由方案
            
        Returns:
            新的RoutePlan，或None（无法恢复）
        """
        if failed_agent_id not in current_plan.agent_chain:
            return current_plan
        
        logger.warning(f"[DynamicRouter] Agent failure detected: {failed_agent_id}, rerouting...")
        
        # 标记Agent为离线
        if failed_agent_id in self._agents:
            self._agents[failed_agent_id].load_state = AgentLoadState.OFFLINE
        
        # 重建拓扑
        self._rebuild_topology()
        
        # 移除故障Agent后的链
        remaining_chain = [a for a in current_plan.agent_chain if a != failed_agent_id]
        
        # 查找替代
        failed_profile = self._agents.get(failed_agent_id)
        if failed_profile:
            # 创建替代需求
            replacement_task = TaskRequirement(
                required_capabilities=failed_profile.capabilities,
                required_domains=failed_profile.domain_expertise,
            )
            candidates = self._filter_candidates(replacement_task)
            # 排除已在线中的
            candidates = [c for c in candidates if c.agent_id not in remaining_chain]
            
            if candidates:
                replacement = candidates[0]
                # 插入替代Agent到原位置
                idx = current_plan.agent_chain.index(failed_agent_id)
                new_chain = remaining_chain[:idx] + [replacement.agent_id] + remaining_chain[idx:]
                
                new_plan = RoutePlan(
                    plan_id=str(uuid.uuid4())[:8],
                    task_id=current_plan.task_id,
                    agent_chain=new_chain,
                    topology_type=current_plan.topology_type,
                    confidence=self._estimate_chain_confidence(new_chain),
                    status="rerouted",
                )
                logger.info(f"[DynamicRouter] Rerouted: {failed_agent_id} → {replacement.name}")
                return new_plan
        
        # 无法替代，返回缩短的链
        if remaining_chain:
            return RoutePlan(
                plan_id=str(uuid.uuid4())[:8],
                task_id=current_plan.task_id,
                agent_chain=remaining_chain,
                topology_type="sequential",
                confidence=self._estimate_chain_confidence(remaining_chain) * 0.8,
                status="rerouted",
            )
        
        return None
    
    # ============ 查询与统计 ============
    
    def get_topology_summary(self) -> Dict[str, Any]:
        """获取当前拓扑摘要"""
        agent_summaries = []
        for aid, profile in self._agents.items():
            agent_summaries.append({
                "id": aid,
                "name": profile.name,
                "role": profile.role,
                "tier": profile.tier,
                "load_state": profile.load_state.value,
                "score": profile.compute_score(),
                "tasks": profile.current_tasks,
                "capabilities": profile.capabilities,
            })
        
        return {
            "total_agents": len(self._agents),
            "online_agents": sum(1 for a in self._agents.values() 
                                if a.load_state != AgentLoadState.OFFLINE),
            "agents": agent_summaries,
            "total_routes": len(self._route_history),
            "topology_edges": self._topology.number_of_edges() if HAS_NETWORKX and self._topology else 0,
        }
    
    def get_route_history(self, limit: int = 20) -> List[Dict]:
        """获取路由历史"""
        return [
            {
                "plan_id": p.plan_id,
                "task_id": p.task_id,
                "chain": [self._agents[a].name if a in self._agents else a for a in p.agent_chain],
                "topology": p.topology_type,
                "confidence": p.confidence,
                "status": p.status,
                "latency_ms": p.estimated_latency_ms,
            }
            for p in self._route_history[-limit:]
        ]
    
    def get_agent_detail(self, agent_id: str) -> Optional[Dict]:
        """获取Agent详细画像"""
        if agent_id not in self._agents:
            return None
        p = self._agents[agent_id]
        return {
            "id": p.agent_id,
            "name": p.name,
            "role": p.role,
            "tier": p.tier,
            "load_state": p.load_state.value,
            "score": p.compute_score(),
            "capabilities": p.capabilities,
            "domains": p.domain_expertise,
            "current_tasks": p.current_tasks,
            "max_concurrent": p.max_concurrent,
            "avg_latency_ms": round(p.avg_latency_ms, 1),
            "success_rate": round(p.success_rate, 3),
            "reasoning_depth": p.reasoning_depth,
            "creativity": p.creativity,
            "context_window": p.context_window,
        }
    
    def suggest_optimization(self) -> List[str]:
        """基于历史数据给出优化建议"""
        suggestions = []
        
        if not self._route_history:
            return ["No routing history yet"]
        
        # 分析失败率
        failed = sum(1 for p in self._route_history if p.status == "failed")
        total = len(self._route_history)
        if failed / max(total, 1) > 0.2:
            suggestions.append(f"High failure rate ({failed}/{total}). Consider adding more agents.")
        
        # 分析过载Agent
        overloaded = [a for a in self._agents.values() 
                     if a.load_state == AgentLoadState.OVERLOADED]
        if overloaded:
            names = [a.name for a in overloaded]
            suggestions.append(f"Overloaded agents: {', '.join(names)}. Scale up or redistribute.")
        
        # 分析长链
        long_chains = [p for p in self._route_history if len(p.agent_chain) > 5]
        if long_chains:
            suggestions.append(f"{len(long_chains)} routes had chains > 5. Consider splitting tasks.")
        
        if not suggestions:
            suggestions.append("System is running well. No optimization needed.")
        
        return suggestions
