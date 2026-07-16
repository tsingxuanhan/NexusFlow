# -*- coding: utf-8 -*-
"""
铉枢·炉守 端-边-云调度器
Edge-Fog-Cloud Scheduler — 受TEN Agent架构启发

三层部署架构:
  Edge(端侧) → 本地设备，低延迟，隐私安全
  Fog(边缘)  → 区域服务器，中等算力
  Cloud(云端) → 大型集群，强算力，高延迟

核心设计:
- 任务根据复杂度、隐私需求、延迟约束自动选择执行层
- 隐私敏感任务优先在Edge层处理（数据不出设备）
- 支持层间任务迁移（Edge处理不了→上抛到Fog/Cloud）
- 参考TEN的pipeline模块化设计，但调度逻辑原创

与DynamicTopologyRouter的关系:
- Router负责"谁来执行"（Agent选择）
- Scheduler负责"在哪执行"（部署层选择）
- Router调用Scheduler获取部署建议
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("EdgeCloudScheduler")


class DeployTier(Enum):
    """部署层"""
    EDGE = "edge"     # 端侧：本地设备（笔记本、手机）
    FOG = "fog"       # 边缘：区域服务器/校园服务器
    CLOUD = "cloud"   # 云端：大型GPU集群


class SchedulingPolicy(Enum):
    """调度策略"""
    LATENCY_FIRST = "latency_first"       # 延迟优先（实时交互场景）
    PRIVACY_FIRST = "privacy_first"       # 隐私优先（敏感数据场景）
    COST_FIRST = "cost_first"             # 成本优先（省钱模式）
    BALANCED = "balanced"                 # 均衡
    EDGE_PREFERRED = "edge_preferred"     # 端侧优先（离线优先）


@dataclass
class TierResource:
    """部署层资源描述"""
    tier: DeployTier
    name: str                     # 资源名称，如 "local-rtx3080", "campus-a100"
    endpoint: str = ""            # API端点
    
    # 资源规格
    cpu_cores: int = 4
    gpu_count: int = 0
    gpu_memory_gb: float = 0.0
    ram_gb: float = 16.0
    storage_gb: float = 100.0
    
    # 运行时状态
    available: bool = True
    load_factor: float = 0.0     # 0-1, 当前负载率
    latency_to_user_ms: float = 10.0  # 到用户的网络延迟
    
    # 模型能力
    supported_models: List[str] = field(default_factory=list)
    max_context_window: int = 8192
    
    # 成本
    cost_per_token: float = 0.0   # 每token成本(元)
    
    def compute_fitness(self, task_requirements: Dict) -> float:
        """
        计算该层资源对任务的适配度 (0-1)
        
        Args:
            task_requirements: 任务需求字典
        """
        score = 1.0
        
        # GPU需求
        if task_requirements.get("needs_gpu", False):
            if self.gpu_count == 0:
                return 0.0
            score *= min(1.0, self.gpu_memory_gb / task_requirements.get("min_gpu_memory_gb", 8))
        
        # 上下文窗口需求
        needed_ctx = task_requirements.get("context_window", 4096)
        if self.max_context_window < needed_ctx:
            score *= (self.max_context_window / needed_ctx)
        
        # 负载惩罚
        score *= (1.0 - self.load_factor * 0.5)
        
        # 可用性
        if not self.available:
            return 0.0
        
        return round(max(0.0, min(1.0, score)), 4)


@dataclass
class SchedulingDecision:
    """调度决策"""
    decision_id: str = ""
    task_id: str = ""
    selected_tier: DeployTier = DeployTier.CLOUD
    selected_resource: str = ""
    reason: str = ""
    confidence: float = 0.0
    fallback_tier: Optional[DeployTier] = None
    estimated_latency_ms: float = 0.0
    estimated_cost: float = 0.0
    privacy_guaranteed: bool = False


# ============ 端-边-云调度器 ============

class EdgeCloudScheduler:
    """
    端-边-云三级调度器
    
    职责:
    - 管理三层资源池
    - 根据任务特征和调度策略选择执行层
    - 支持层间任务迁移
    - 隐私合规保障
    
    用法:
        scheduler = EdgeCloudScheduler(policy=SchedulingPolicy.BALANCED)
        
        # 注册资源
        scheduler.register_tier(TierResource(
            tier=DeployTier.EDGE,
            name="local-rtx3080",
            gpu_count=1, gpu_memory_gb=16.0,
            supported_models=["qwen-7b", "deepseek-v4-flash"],
            latency_to_user_ms=5,
        ))
        
        # 调度
        decision = scheduler.schedule(task_requirements={
            "needs_gpu": True,
            "privacy_level": 2,
            "context_window": 8192,
            "latency_budget_ms": 5000,
        })
    """
    
    def __init__(self, policy: SchedulingPolicy = SchedulingPolicy.BALANCED):
        self._tiers: Dict[DeployTier, List[TierResource]] = {
            DeployTier.EDGE: [],
            DeployTier.FOG: [],
            DeployTier.CLOUD: [],
        }
        self._policy = policy
        self._decisions: List[SchedulingDecision] = []
        self._migration_log: List[Dict] = []
        
        logger.info(f"[EdgeCloudScheduler] Initialized, policy={policy.value}")
    
    # ============ 资源管理 ============
    
    def register_tier(self, resource: TierResource) -> None:
        """注册一层资源"""
        self._tiers[resource.tier].append(resource)
        logger.info(
            f"[EdgeCloudScheduler] Registered {resource.tier.value}: "
            f"{resource.name} (GPU:{resource.gpu_count}, "
            f"RAM:{resource.ram_gb}GB, latency:{resource.latency_to_user_ms}ms)"
        )
    
    def update_resource_state(self, tier: DeployTier, name: str,
                               load_factor: Optional[float] = None,
                               available: Optional[bool] = None) -> None:
        """更新资源状态"""
        for r in self._tiers.get(tier, []):
            if r.name == name:
                if load_factor is not None:
                    r.load_factor = load_factor
                if available is not None:
                    r.available = available
                break
    
    def get_all_resources(self) -> Dict[str, List[Dict]]:
        """获取所有资源状态"""
        result = {}
        for tier, resources in self._tiers.items():
            result[tier.value] = [
                {
                    "name": r.name,
                    "endpoint": r.endpoint,
                    "available": r.available,
                    "load_factor": r.load_factor,
                    "gpu": r.gpu_count,
                    "ram_gb": r.ram_gb,
                    "latency_ms": r.latency_to_user_ms,
                    "models": r.supported_models,
                }
                for r in resources
            ]
        return result
    
    # ============ 调度决策 ============
    
    def schedule(self, task_requirements: Dict) -> SchedulingDecision:
        """
        核心调度决策
        
        Args:
            task_requirements: 任务需求
                - needs_gpu: bool — 是否需要GPU
                - min_gpu_memory_gb: float — 最低显存需求
                - privacy_level: int — 0=公开, 1=内部, 2=敏感
                - context_window: int — 需要的上下文窗口
                - latency_budget_ms: float — 延迟预算
                - model_name: str — 指定模型
                - cost_budget: float — 成本预算
                - offline_ok: bool — 是否接受离线处理
                
        Returns:
            SchedulingDecision
        """
        decision = SchedulingDecision(
            decision_id=str(uuid.uuid4())[:8],
            task_id=task_requirements.get("task_id", ""),
        )
        
        # 根据策略选择调度逻辑
        if self._policy == SchedulingPolicy.PRIVACY_FIRST:
            self._schedule_privacy_first(task_requirements, decision)
        elif self._policy == SchedulingPolicy.LATENCY_FIRST:
            self._schedule_latency_first(task_requirements, decision)
        elif self._policy == SchedulingPolicy.EDGE_PREFERRED:
            self._schedule_edge_preferred(task_requirements, decision)
        elif self._policy == SchedulingPolicy.COST_FIRST:
            self._schedule_cost_first(task_requirements, decision)
        else:
            self._schedule_balanced(task_requirements, decision)
        
        self._decisions.append(decision)
        if len(self._decisions) > 500:
            self._decisions = self._decisions[-500:]
        
        logger.info(
            f"[EdgeCloudScheduler] Decision: tier={decision.selected_tier.value}, "
            f"resource={decision.selected_resource}, reason={decision.reason}"
        )
        
        return decision
    
    def _schedule_privacy_first(self, req: Dict, dec: SchedulingDecision) -> None:
        """隐私优先策略：敏感任务强制端侧"""
        privacy = req.get("privacy_level", 0)
        
        if privacy >= 2:
            # 敏感数据：强制Edge层
            edge = self._find_best_resource(DeployTier.EDGE, req)
            if edge:
                dec.selected_tier = DeployTier.EDGE
                dec.selected_resource = edge.name
                dec.reason = "Privacy-sensitive: forced to edge tier"
                dec.privacy_guaranteed = True
                dec.confidence = edge.compute_fitness(req)
                dec.estimated_latency_ms = edge.latency_to_user_ms
                return
            else:
                dec.reason = "WARNING: Privacy-sensitive but no edge resource available!"
                dec.confidence = 0.3
        
        # 非敏感：正常调度
        self._schedule_balanced(req, dec)
    
    def _schedule_latency_first(self, req: Dict, dec: SchedulingDecision) -> None:
        """延迟优先策略"""
        budget = req.get("latency_budget_ms", 30000)
        
        # 先尝试Edge
        edge = self._find_best_resource(DeployTier.EDGE, req)
        if edge and edge.latency_to_user_ms <= budget * 0.5:
            dec.selected_tier = DeployTier.EDGE
            dec.selected_resource = edge.name
            dec.reason = f"Low latency: {edge.latency_to_user_ms}ms < budget {budget}ms"
            dec.confidence = edge.compute_fitness(req)
            dec.estimated_latency_ms = edge.latency_to_user_ms
            return
        
        # 再尝试Fog
        fog = self._find_best_resource(DeployTier.FOG, req)
        if fog and fog.latency_to_user_ms <= budget:
            dec.selected_tier = DeployTier.FOG
            dec.selected_resource = fog.name
            dec.reason = f"Fog latency acceptable: {fog.latency_to_user_ms}ms"
            dec.confidence = fog.compute_fitness(req)
            dec.estimated_latency_ms = fog.latency_to_user_ms
            return
        
        # 兜底Cloud
        cloud = self._find_best_resource(DeployTier.CLOUD, req)
        if cloud:
            dec.selected_tier = DeployTier.CLOUD
            dec.selected_resource = cloud.name
            dec.reason = "No edge/fog meets latency, fallback to cloud"
            dec.confidence = cloud.compute_fitness(req) * 0.8
            dec.estimated_latency_ms = cloud.latency_to_user_ms
        else:
            dec.reason = "No resource available"
            dec.confidence = 0.0
    
    def _schedule_edge_preferred(self, req: Dict, dec: SchedulingDecision) -> None:
        """端侧优先策略"""
        for tier in [DeployTier.EDGE, DeployTier.FOG, DeployTier.CLOUD]:
            resource = self._find_best_resource(tier, req)
            if resource:
                dec.selected_tier = tier
                dec.selected_resource = resource.name
                dec.reason = f"Edge preferred: selected from {tier.value}"
                dec.confidence = resource.compute_fitness(req)
                dec.estimated_latency_ms = resource.latency_to_user_ms
                if tier == DeployTier.EDGE:
                    dec.privacy_guaranteed = True
                return
        
        dec.reason = "No resource available at any tier"
        dec.confidence = 0.0
    
    def _schedule_cost_first(self, req: Dict, dec: SchedulingDecision) -> None:
        """成本优先策略"""
        best_cost = float('inf')
        best_resource = None
        best_tier = DeployTier.CLOUD
        
        for tier in [DeployTier.EDGE, DeployTier.FOG, DeployTier.CLOUD]:
            for r in self._tiers[tier]:
                if not r.available:
                    continue
                fitness = r.compute_fitness(req)
                if fitness <= 0:
                    continue
                effective_cost = r.cost_per_token / max(fitness, 0.1)
                if effective_cost < best_cost:
                    best_cost = effective_cost
                    best_resource = r
                    best_tier = tier
        
        if best_resource:
            dec.selected_tier = best_tier
            dec.selected_resource = best_resource.name
            dec.reason = f"Lowest cost: {best_cost:.6f}/token at {best_tier.value}"
            dec.confidence = best_resource.compute_fitness(req)
            dec.estimated_cost = best_cost
            dec.estimated_latency_ms = best_resource.latency_to_user_ms
        else:
            dec.reason = "No affordable resource"
            dec.confidence = 0.0
    
    def _schedule_balanced(self, req: Dict, dec: SchedulingDecision) -> None:
        """均衡策略：综合考量延迟、成本、适配度"""
        candidates = []
        
        for tier in [DeployTier.EDGE, DeployTier.FOG, DeployTier.CLOUD]:
            for r in self._tiers[tier]:
                if not r.available:
                    continue
                fitness = r.compute_fitness(req)
                if fitness <= 0:
                    continue
                
                # 综合评分 = 适配度 * 0.5 + (1-延迟归一化) * 0.3 + (1-成本归一化) * 0.2
                latency_score = 1.0 / (1.0 + r.latency_to_user_ms / 1000.0)
                cost_score = 1.0 / (1.0 + r.cost_per_token * 1000)
                
                total_score = fitness * 0.5 + latency_score * 0.3 + cost_score * 0.2
                candidates.append((total_score, tier, r))
        
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_tier, best_resource = candidates[0]
            
            dec.selected_tier = best_tier
            dec.selected_resource = best_resource.name
            dec.reason = f"Balanced selection: score={best_score:.3f} at {best_tier.value}"
            dec.confidence = best_score
            dec.estimated_latency_ms = best_resource.latency_to_user_ms
            dec.estimated_cost = best_resource.cost_per_token
            
            # 备选层
            if len(candidates) > 1:
                dec.fallback_tier = candidates[1][1]
        else:
            dec.reason = "No suitable resource at any tier"
            dec.confidence = 0.0
    
    def _find_best_resource(self, tier: DeployTier, req: Dict) -> Optional[TierResource]:
        """在某一层中找最适配的资源"""
        best = None
        best_fitness = -1
        
        for r in self._tiers.get(tier, []):
            if not r.available:
                continue
            
            # 检查模型支持
            needed_model = req.get("model_name")
            if needed_model and needed_model not in r.supported_models:
                continue
            
            fitness = r.compute_fitness(req)
            if fitness > best_fitness:
                best_fitness = fitness
                best = r
        
        return best if best_fitness > 0 else None
    
    # ============ 层间迁移 ============
    
    def migrate(self, task_id: str, from_tier: DeployTier, 
                to_tier: DeployTier, reason: str = "") -> bool:
        """
        任务层间迁移
        
        场景:
        - Edge处理不了（算力不够）→ 上抛到Fog/Cloud
        - Cloud处理完，结果下发到Edge做展示
        - 隐私检查发现数据敏感 → 从Cloud迁移到Edge
        
        Args:
            task_id: 任务ID
            from_tier: 源层
            to_tier: 目标层
            reason: 迁移原因
            
        Returns:
            bool: 迁移是否成功
        """
        # 检查目标层是否有资源
        if not self._tiers.get(to_tier):
            logger.warning(f"[EdgeCloudScheduler] No resources at {to_tier.value}")
            return False
        
        available = [r for r in self._tiers[to_tier] if r.available]
        if not available:
            logger.warning(f"[EdgeCloudScheduler] No available resources at {to_tier.value}")
            return False
        
        migration = {
            "task_id": task_id,
            "from": from_tier.value,
            "to": to_tier.value,
            "reason": reason,
            "timestamp": time.time(),
            "status": "migrated",
        }
        self._migration_log.append(migration)
        
        logger.info(
            f"[EdgeCloudScheduler] Task {task_id} migrated: "
            f"{from_tier.value} → {to_tier.value} ({reason})"
        )
        
        return True
    
    # ============ 默认配置 ============
    
    def setup_default_tiers(self, local_gpu: bool = False) -> None:
        """
        设置默认三层配置
        
        Args:
            local_gpu: 本地是否有GPU
        """
        # Edge: 本地设备
        edge = TierResource(
            tier=DeployTier.EDGE,
            name="local-device",
            gpu_count=1 if local_gpu else 0,
            gpu_memory_gb=16.0 if local_gpu else 0,
            ram_gb=32.0,
            supported_models=["qwen-7b", "qwen-14b", "deepseek-v4-flash"] if local_gpu else ["qwen-7b"],
            max_context_window=8192 if local_gpu else 4096,
            latency_to_user_ms=5.0,
            cost_per_token=0.0,  # 本地免费
        )
        self.register_tier(edge)
        
        # Fog: 区域服务器（示例）
        fog = TierResource(
            tier=DeployTier.FOG,
            name="campus-server",
            endpoint="http://campus-server:8080",
            gpu_count=2,
            gpu_memory_gb=24.0,
            ram_gb=64.0,
            supported_models=["qwen-14b", "qwen-72b", "deepseek-v4-flash", "deepseek-v4-pro"],
            max_context_window=32768,
            latency_to_user_ms=50.0,
            cost_per_token=0.0001,
        )
        self.register_tier(fog)
        
        # Cloud: 云端API
        cloud = TierResource(
            tier=DeployTier.CLOUD,
            name="cloud-api",
            endpoint="https://api.dashscope.aliyuncs.com",
            gpu_count=0,  # 云端API不暴露GPU数
            ram_gb=0,
            supported_models=["qwen-max", "qwen-plus", "deepseek-v4-pro", "deepseek-r1"],
            max_context_window=131072,
            latency_to_user_ms=200.0,
            cost_per_token=0.0005,
        )
        self.register_tier(cloud)
    
    # ============ 统计 ============
    
    def get_scheduling_stats(self) -> Dict[str, Any]:
        """获取调度统计"""
        tier_counts = {t.value: 0 for t in DeployTier}
        for d in self._decisions:
            tier_counts[d.selected_tier.value] += 1
        
        return {
            "policy": self._policy.value,
            "total_decisions": len(self._decisions),
            "tier_distribution": tier_counts,
            "total_migrations": len(self._migration_log),
            "resources": {
                tier.value: len(resources) 
                for tier, resources in self._tiers.items()
            },
        }
