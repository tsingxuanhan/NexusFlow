# -*- coding: utf-8 -*-
"""
自适应上下文管理器 (Adaptive Context Manager)
XuanHub v4.0 Phase 7 — 超长程任务上下文管理

受清华 & OpenBMB 论文《Rethinking Hybrid Attention》(arXiv:2606.15378) 启发，
将LLM的注意力机制发现映射到多Agent系统：

核心类比：
- 全注意力层 = 全局记忆池（长程能力承载者）
- 滑动窗口 = Agent本地上下文窗口
- 大窗口懒惰症 = 上下文舒适区陷阱
- 检索头 = 专门化的信息桥接Agent
- NoPE = 强制全局同步（打破信息壁垒）

核心组件：
- LocalContextWindow: 本地上下文窗口（支持recency/relevance/mixed截断策略）
- GlobalMemoryPool: 全局记忆池（语义检索，可选backing_store对接ArchivalMemory）
- ForcedGlobalSync: 强制全局同步（NoPE策略）
- RetrievalHeadAgent: 检索头Agent（不做推理只做精准检索）
- LazinessDetector: 懒惰检测器（4个指标）
- AdaptiveWindowController: 自适应窗口控制
- AdaptiveContextManager: 编排入口

依赖：numpy（向量计算，可选降级）+ 现有LLM调用能力
不依赖：networkx、gradio、额外向量数据库
"""

import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("AdaptiveContextManager")

# numpy可选导入（降级到纯Python实现）
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.info("[AdaptiveContextManager] numpy not available, using pure Python fallback")


# ============================================================================
# 辅助工具
# ============================================================================

def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算两个向量的余弦相似度"""
    if HAS_NUMPY:
        va, vb = np.array(a), np.array(b)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(va, vb) / (norm_a * norm_b))
    else:
        # 纯Python实现
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def _simple_hash_embed(text: str, dim: int = 128) -> List[float]:
    """简单的文本哈希嵌入（无模型的降级方案）
    
    使用字符n-gram的哈希桶来生成固定维度的伪向量。
    不是真正的语义嵌入，但能提供基本的相似度区分能力。
    """
    vec = [0.0] * dim
    
    # 2-gram + 3-gram
    for n in (2, 3):
        for i in range(len(text) - n + 1):
            gram = text[i:i+n]
            h = hash(gram) % dim
            vec[h] += 1.0
    
    # 归一化
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    
    return vec


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class MemoryItem:
    """全局记忆池中的单个条目"""
    content: str
    agent_id: str = ""
    memory_type: str = "conclusion"  # "conclusion" | "hypothesis" | "contradiction" | "evidence"
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: List[float] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "agent_id": self.agent_id,
            "memory_type": self.memory_type,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "importance": self.importance,
        }


@dataclass
class RetrievalQuery:
    """检索头Agent的查询"""
    requester_id: str
    target_description: str
    constraints: Dict[str, Any] = field(default_factory=dict)
    purpose: str = ""
    top_k: int = 5


@dataclass
class RetrievalResult:
    """检索结果"""
    items: List[MemoryItem] = field(default_factory=list)
    total_candidates: int = 0
    retrieval_precision: float = 0.0
    query: Optional[RetrievalQuery] = None


@dataclass
class SyncMessage:
    """全局同步消息"""
    sync_id: int = 0
    global_summary: str = ""
    key_changes: List[str] = field(default_factory=list)
    contradictions_detected: List[str] = field(default_factory=list)
    action_required: str = "re-evaluate your conclusion based on global state"


@dataclass
class SyncResult:
    """同步结果"""
    sync_message: Optional[SyncMessage] = None
    target_agents: List[str] = field(default_factory=list)
    synced: bool = False


@dataclass
class LazinessAlert:
    """懒惰检测结果"""
    agent_id: str
    laziness_score: float = 0.0
    is_lazy: bool = False
    details: Dict[str, float] = field(default_factory=dict)


@dataclass
class InterventionAction:
    """懒惰干预措施"""
    agent_id: str
    forced_query: Optional[str] = None
    contradicting_info: Optional[str] = None
    new_window_size: Optional[int] = None
    rationale: str = ""


# ============================================================================
# LocalContextWindow — 本地上下文窗口
# ============================================================================

class LocalContextWindow:
    """Agent的本地上下文窗口——故意设小
    
    截断不是"丢弃"，而是"降级到全局记忆池"——
    被截断的信息仍然存在于GlobalMemoryPool，
    Agent需要时可以通过Router检索，但默认看不到。
    
    支持三种截断策略：
    - recency: 保留最近的消息
    - relevance: 保留与当前查询最相关的消息
    - mixed: 最近N条 + 相关度最高的M条
    """
    
    def __init__(
        self,
        max_tokens: int = 4096,
        strategy: str = "recency",
        adaptive: bool = True,
        min_window: int = 1024,
        max_window: int = 8192,
        keep_recent: int = 3,
    ):
        """
        Args:
            max_tokens: 硬上限，每个Agent最多看到的token数
            strategy: 截断策略 "recency" | "relevance" | "mixed"
            adaptive: 是否允许动态调整窗口大小
            min_window: 最小窗口大小
            max_window: 最大窗口大小
            keep_recent: mixed策略中保留的最近消息数
        """
        self.max_tokens = max_tokens
        self.strategy = strategy
        self.adaptive = adaptive
        self.min_window = min_window
        self.max_window = max_window
        self.keep_recent = keep_recent
        
        # 统计
        self.total_truncations = 0
        self.total_messages_truncated = 0
    
    def truncate_messages(self, messages: List[Dict[str, str]], query: str = "") -> List[Dict[str, str]]:
        """截断消息列表到窗口大小
        
        Args:
            messages: 原始消息列表
            query: 当前查询（用于relevance/mixed策略的相关性计算）
            
        Returns:
            截断后的消息列表
        """
        # 估算token数（中文约2token/字，英文约1.3token/字）
        total_tokens = self._estimate_tokens(messages)
        
        if total_tokens <= self.max_tokens:
            return messages
        
        self.total_truncations += 1
        
        if self.strategy == "recency":
            return self._keep_recent_messages(messages)
        elif self.strategy == "relevance":
            return self._keep_relevant_messages(messages, query)
        elif self.strategy == "mixed":
            return self._keep_mixed_messages(messages, query)
        else:
            return self._keep_recent_messages(messages)
    
    def _estimate_tokens(self, messages: List[Dict[str, str]]) -> int:
        """粗估token数"""
        import re
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            cn_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
            other_chars = len(content) - cn_chars
            total += cn_chars * 2 + int(other_chars * 1.3)
        return total
    
    def _estimate_msg_tokens(self, msg: Dict[str, str]) -> int:
        """估算单条消息的token数"""
        return self._estimate_tokens([msg])
    
    def _keep_recent_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """保留最近的消息（recency策略）"""
        # 始终保留system消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        # 从最近往前取，直到达到token上限
        kept = []
        current_tokens = self._estimate_tokens(system_msgs)
        
        for msg in reversed(non_system):
            msg_tokens = self._estimate_msg_tokens(msg)
            if current_tokens + msg_tokens > self.max_tokens:
                break
            kept.insert(0, msg)
            current_tokens += msg_tokens
        
        self.total_messages_truncated += len(non_system) - len(kept)
        
        # 添加截断通知
        if len(kept) < len(non_system):
            truncation_notice = {
                "role": "system",
                "content": f"[上下文窗口] 之前{len(non_system) - len(kept)}条消息已截断，"
                           f"可通过全局记忆检索获取。"
            }
            return system_msgs + [truncation_notice] + kept
        
        return system_msgs + kept
    
    def _keep_relevant_messages(
        self,
        messages: List[Dict[str, str]],
        query: str,
    ) -> List[Dict[str, str]]:
        """保留与查询最相关的消息（relevance策略）"""
        if not query:
            return self._keep_recent_messages(messages)
        
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        query_embed = _simple_hash_embed(query)
        
        # 按相关性排序
        scored = []
        for msg in non_system:
            msg_embed = _simple_hash_embed(msg.get("content", ""))
            score = _cosine_similarity(query_embed, msg_embed)
            scored.append((score, msg))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # 取相关性最高的，不超过token上限
        kept = []
        current_tokens = self._estimate_tokens(system_msgs)
        
        for score, msg in scored:
            msg_tokens = self._estimate_msg_tokens(msg)
            if current_tokens + msg_tokens > self.max_tokens:
                break
            kept.append(msg)
            current_tokens += msg_tokens
        
        # 按原始顺序重排
        kept_indices = set(id(m) for m in kept)
        ordered_kept = [m for m in non_system if id(m) in kept_indices]
        
        self.total_messages_truncated += len(non_system) - len(ordered_kept)
        return system_msgs + ordered_kept
    
    def _keep_mixed_messages(
        self,
        messages: List[Dict[str, str]],
        query: str,
    ) -> List[Dict[str, str]]:
        """混合策略：最近N条 + 相关度最高的M条"""
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]
        
        # 保留最近的N条
        recent = non_system[-self.keep_recent:] if len(non_system) > self.keep_recent else non_system[:]
        
        # 剩余消息中取相关度最高的
        remaining = non_system[:-self.keep_recent] if len(non_system) > self.keep_recent else []
        
        if remaining and query:
            query_embed = _simple_hash_embed(query)
            scored = []
            for msg in remaining:
                msg_embed = _simple_hash_embed(msg.get("content", ""))
                score = _cosine_similarity(query_embed, msg_embed)
                scored.append((score, msg))
            scored.sort(key=lambda x: x[0], reverse=True)
            
            # 填充剩余token预算
            current_tokens = self._estimate_tokens(system_msgs + recent)
            for score, msg in scored:
                msg_tokens = self._estimate_msg_tokens(msg)
                if current_tokens + msg_tokens > self.max_tokens:
                    break
                recent.insert(0, msg)
                current_tokens += msg_tokens
        
        self.total_messages_truncated += len(non_system) - len(recent)
        return system_msgs + recent
    
    def resize(self, new_size: int) -> None:
        """动态调整窗口大小"""
        if not self.adaptive:
            return
        self.max_tokens = max(self.min_window, min(self.max_window, new_size))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取窗口统计信息"""
        return {
            "max_tokens": self.max_tokens,
            "strategy": self.strategy,
            "adaptive": self.adaptive,
            "total_truncations": self.total_truncations,
            "total_messages_truncated": self.total_messages_truncated,
        }


# ============================================================================
# GlobalMemoryPool — 全局记忆池
# ============================================================================

class GlobalMemoryPool:
    """全局记忆池——全注意力层的Agent系统实现
    
    存储所有Agent的推理产物（结论、假设、矛盾），支持语义检索。
    
    关键设计：
    - 不存储原始对话（那是Agent的本地上下文）
    - 只存储结构化的推理产物
    - 支持按语义检索（模拟Retrieval Head的精准定位）
    - 可选backing_store对接ArchivalMemory持久化
    """
    
    def __init__(self, backing_store: Optional[Any] = None, embedding_dim: int = 128):
        """
        Args:
            backing_store: 持久化后端（如ArchivalMemory实例）
            embedding_dim: 嵌入向量维度
        """
        self.backing_store = backing_store
        self.embedding_dim = embedding_dim
        
        # 分类存储
        self.conclusions: List[MemoryItem] = []
        self.hypotheses: List[MemoryItem] = []
        self.contradictions: List[MemoryItem] = []
        self.evidence: List[MemoryItem] = []
        
        # 全部条目索引
        self._all_items: List[MemoryItem] = []
        
        # 统计
        self.total_adds = 0
        self.total_searches = 0
    
    def add(
        self,
        memory_type: str,
        agent_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5,
    ) -> MemoryItem:
        """添加通用记忆条目
        
        Args:
            memory_type: "conclusion" | "hypothesis" | "contradiction" | "evidence"
            agent_id: 来源Agent ID
            content: 内容
            metadata: 元数据
            importance: 重要性评分
            
        Returns:
            创建的MemoryItem
        """
        item = MemoryItem(
            content=content,
            agent_id=agent_id,
            memory_type=memory_type,
            metadata=metadata or {},
            embedding=_simple_hash_embed(content, self.embedding_dim),
            timestamp=time.time(),
            importance=importance,
        )
        
        # 分类存储
        if memory_type == "conclusion":
            self.conclusions.append(item)
        elif memory_type == "hypothesis":
            self.hypotheses.append(item)
        elif memory_type == "contradiction":
            self.contradictions.append(item)
        elif memory_type == "evidence":
            self.evidence.append(item)
        else:
            self.evidence.append(item)  # 默认归入evidence
        
        self._all_items.append(item)
        self.total_adds += 1
        
        # 同步到持久化后端
        if self.backing_store:
            try:
                self.backing_store.store(
                    content=content,
                    source=f"global_pool:{agent_id}",
                    domain="global_memory",
                    importance=importance,
                )
            except Exception as e:
                logger.warning(f"[GlobalMemoryPool] backing_store写入失败: {e}")
        
        return item
    
    def add_conclusion(self, agent_id: str, conclusion: Any) -> MemoryItem:
        """添加推理结论
        
        Args:
            agent_id: Agent ID
            conclusion: IntermediateConclusion对象或字符串
        """
        if hasattr(conclusion, 'conclusion'):
            content = conclusion.conclusion
            metadata = {
                "confidence": getattr(conclusion, 'confidence', 0.5),
                "active_hypotheses": getattr(conclusion, 'active_hypotheses', []),
                "eliminated_hypotheses": getattr(conclusion, 'eliminated_hypotheses', []),
            }
            importance = getattr(conclusion, 'confidence', 0.5)
        else:
            content = str(conclusion)
            metadata = {}
            importance = 0.5
        
        return self.add("conclusion", agent_id, content, metadata, importance)
    
    def add_hypothesis(self, agent_id: str, hypothesis: str, importance: float = 0.5) -> MemoryItem:
        """添加假设"""
        return self.add("hypothesis", agent_id, hypothesis, importance=importance)
    
    def add_contradiction(self, agent_id: str, contradiction: str, importance: float = 0.7) -> MemoryItem:
        """添加矛盾记录"""
        return self.add("contradiction", agent_id, contradiction, importance=importance)
    
    def semantic_search(self, query: str, top_k: int = 10) -> List[MemoryItem]:
        """语义检索——Retrieval Head Agent的核心依赖
        
        使用余弦相似度进行检索。
        
        Args:
            query: 查询文本
            top_k: 返回数量
            
        Returns:
            按相似度排序的MemoryItem列表
        """
        self.total_searches += 1
        query_embedding = _simple_hash_embed(query, self.embedding_dim)
        
        # 计算所有条目的相似度
        scored = []
        for item in self._all_items:
            score = _cosine_similarity(query_embedding, item.embedding)
            # 加入重要性加权和时间衰减
            time_decay = math.exp(-0.001 * (time.time() - item.timestamp))
            final_score = score * 0.7 + item.importance * 0.2 + time_decay * 0.1
            scored.append((final_score, item))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        
        return [item for _, item in scored[:top_k]]
    
    def get_all_items(self, memory_type: Optional[str] = None) -> List[MemoryItem]:
        """获取所有条目（可选按类型过滤）"""
        if memory_type:
            return [item for item in self._all_items if item.memory_type == memory_type]
        return list(self._all_items)
    
    def get_agent_items(self, agent_id: str) -> List[MemoryItem]:
        """获取指定Agent的所有条目"""
        return [item for item in self._all_items if item.agent_id == agent_id]
    
    def snapshot(self) -> Dict[str, Any]:
        """获取当前状态快照（用于同步）"""
        return {
            "total_items": len(self._all_items),
            "conclusions": len(self.conclusions),
            "hypotheses": len(self.hypotheses),
            "contradictions": len(self.contradictions),
            "evidence": len(self.evidence),
            "agent_ids": list(set(item.agent_id for item in self._all_items)),
            "timestamp": time.time(),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_items": len(self._all_items),
            "conclusions": len(self.conclusions),
            "hypotheses": len(self.hypotheses),
            "contradictions": len(self.contradictions),
            "evidence": len(self.evidence),
            "total_adds": self.total_adds,
            "total_searches": self.total_searches,
            "backing_store": self.backing_store is not None,
        }


# ============================================================================
# ForcedGlobalSync — 强制全局同步
# ============================================================================

class ForcedGlobalSync:
    """强制全局同步——NoPE的Agent系统实现
    
    设计意图：
    - 不是Agent主动查询全局状态（那是"大窗口"行为）
    - 是系统定期强制注入全局信息（打破局部依赖）
    - 每次同步后，Agent必须重新评估自己的结论是否仍然成立
    
    类比论文：对全注意力层应用NoPE（去掉位置编码）→ 打破位置依赖
    """
    
    def __init__(
        self,
        sync_interval: int = 10,
        llm_chat: Optional[Callable] = None,
    ):
        """
        Args:
            sync_interval: 每N步触发一次同步
            llm_chat: LLM调用函数（用于生成摘要）
        """
        self.sync_interval = sync_interval
        self.llm_chat = llm_chat
        self.step_counter = 0
        self.sync_count = 0
        self._last_sync_snapshot: Optional[Dict[str, Any]] = None
        self._sync_history: List[Dict[str, Any]] = []
    
    def maybe_sync(
        self,
        global_memory: GlobalMemoryPool,
        agents: Optional[List[Any]] = None,
    ) -> Optional[SyncResult]:
        """检查是否需要同步，如果需要则执行
        
        Args:
            global_memory: 全局记忆池
            agents: 需要同步的Agent列表
            
        Returns:
            SyncResult（如果触发了同步），否则None
        """
        self.step_counter += 1
        
        if self.step_counter % self.sync_interval != 0:
            return None
        
        self.sync_count += 1
        
        # 1. 生成全局摘要
        global_summary = self._generate_summary(global_memory)
        
        # 2. 检测关键变化
        changes = self._detect_changes(global_memory)
        
        # 3. 检测跨Agent矛盾
        contradictions = self._detect_cross_agent_contradictions(global_memory)
        
        # 4. 构建同步消息
        sync_message = SyncMessage(
            sync_id=self.sync_count,
            global_summary=global_summary,
            key_changes=changes,
            contradictions_detected=contradictions,
            action_required="re-evaluate your conclusion based on global state",
        )
        
        # 5. 更新快照
        self._last_sync_snapshot = global_memory.snapshot()
        
        # 6. 记录历史
        self._sync_history.append({
            "sync_id": self.sync_count,
            "timestamp": time.time(),
            "summary_length": len(global_summary),
            "changes_count": len(changes),
            "contradictions_count": len(contradictions),
        })
        
        target_agents = []
        if agents:
            target_agents = [getattr(a, 'name', getattr(a, 'agent_id', str(a))) for a in agents]
        
        result = SyncResult(
            sync_message=sync_message,
            target_agents=target_agents,
            synced=True,
        )
        
        logger.info(
            f"[ForcedGlobalSync] 同步 #{self.sync_count} 完成: "
            f"changes={len(changes)}, contradictions={len(contradictions)}"
        )
        
        return result
    
    def get_latest_summary(self, global_memory: GlobalMemoryPool) -> str:
        """获取最新的全局摘要（供Agent回调使用）"""
        return self._generate_summary(global_memory)
    
    def _generate_summary(self, memory: GlobalMemoryPool) -> str:
        """生成全局摘要
        
        关键：摘要是"无位置编码"的——不包含"谁先说、谁后说"的时序信息，
        只包含"当前状态是什么、关键矛盾是什么、待解决的是什么"。
        """
        snapshot = memory.snapshot()
        
        # 收集最新结论
        recent_conclusions = memory.conclusions[-5:] if memory.conclusions else []
        recent_contradictions = memory.contradictions[-3:] if memory.contradictions else []
        
        parts = [f"## 全局推理状态 (同步#{self.sync_count})"]
        
        if recent_conclusions:
            parts.append("\n### 已确认的结论")
            for item in recent_conclusions:
                parts.append(f"- [{item.agent_id}] {item.content[:100]}")
        
        if memory.hypotheses:
            parts.append("\n### 活跃假设")
            for item in memory.hypotheses[-3:]:
                parts.append(f"- [{item.agent_id}] {item.content[:100]}")
        
        if recent_contradictions:
            parts.append("\n### 未解决的矛盾")
            for item in recent_contradictions:
                parts.append(f"- {item.content[:100]}")
        
        # 统计摘要
        parts.append(f"\n### 统计")
        parts.append(f"- 总结论数: {snapshot.get('conclusions', 0)}")
        parts.append(f"- 活跃假设: {snapshot.get('hypotheses', 0)}")
        parts.append(f"- 未解决矛盾: {snapshot.get('contradictions', 0)}")
        parts.append(f"- 参与Agent: {', '.join(snapshot.get('agent_ids', []))}")
        
        # 如果有LLM，生成更精炼的摘要
        if self.llm_chat:
            try:
                raw_summary = "\n".join(parts)
                prompt = f"""请将以下全局推理状态压缩为简洁的摘要（200字以内），
重点突出：1.最关键的分歧点 2.最可能被推翻的结论 3.下一步最应该探索的方向

注意：不要按时间顺序叙述，按重要性排列。

{raw_summary}"""
                refined = self.llm_chat(prompt)
                if refined:
                    return refined
            except Exception as e:
                logger.warning(f"[ForcedGlobalSync] LLM摘要生成失败: {e}")
        
        return "\n".join(parts)
    
    def _detect_changes(self, memory: GlobalMemoryPool) -> List[str]:
        """检测自上次同步以来的关键变化"""
        if not self._last_sync_snapshot:
            return ["首次同步，无历史对比"]
        
        changes = []
        current = memory.snapshot()
        previous = self._last_sync_snapshot
        
        # 新增结论数
        new_conclusions = current.get("conclusions", 0) - previous.get("conclusions", 0)
        if new_conclusions > 0:
            changes.append(f"新增{new_conclusions}个结论")
        
        # 新增矛盾数
        new_contradictions = current.get("contradictions", 0) - previous.get("contradictions", 0)
        if new_contradictions > 0:
            changes.append(f"新增{new_contradictions}个矛盾")
        
        # 新参与Agent
        new_agents = set(current.get("agent_ids", [])) - set(previous.get("agent_ids", []))
        if new_agents:
            changes.append(f"新参与Agent: {', '.join(new_agents)}")
        
        return changes
    
    def _detect_cross_agent_contradictions(self, memory: GlobalMemoryPool) -> List[str]:
        """检测跨Agent矛盾"""
        contradictions = []
        
        # 检查矛盾记录
        for item in memory.contradictions:
            contradictions.append(item.content[:100])
        
        # 简单检查：不同Agent的结论是否矛盾
        agent_conclusions = defaultdict(list)
        for item in memory.conclusions:
            agent_conclusions[item.agent_id].append(item.content[:80])
        
        if len(agent_conclusions) >= 2:
            agent_ids = list(agent_conclusions.keys())
            # 简单对比：如果两个Agent的结论完全不同
            for i in range(len(agent_ids)):
                for j in range(i + 1, len(agent_ids)):
                    c1 = agent_conclusions[agent_ids[i]]
                    c2 = agent_conclusions[agent_ids[j]]
                    if c1 and c2:
                        # 简单的词汇重叠检测
                        words1 = set(c1[-1].lower().split())
                        words2 = set(c2[-1].lower().split())
                        overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                        if overlap < 0.2:
                            contradictions.append(
                                f"Agent {agent_ids[i]} 和 {agent_ids[j]} 的结论可能存在矛盾"
                            )
        
        return contradictions
    
    def get_stats(self) -> Dict[str, Any]:
        """获取同步统计"""
        return {
            "sync_interval": self.sync_interval,
            "step_counter": self.step_counter,
            "sync_count": self.sync_count,
            "history": self._sync_history[-10:],
        }


# ============================================================================
# RetrievalHeadAgent — 检索头Agent
# ============================================================================

class RetrievalHeadAgent:
    """检索头Agent——专门化的信息桥接
    
    与普通Agent的区别：
    - 普通Agent：接收信息 → 推理 → 产出结论
    - 检索头Agent：接收查询 → 检索全局记忆 → 返回精准信息片段
    
    不推理，不判断，只检索。
    
    灵感来源：论文中的Retrieval Head——
    低注意力熵（精准的远程定位），而不是高注意力熵（广泛的局部关注）。
    """
    
    def __init__(self, agent_id: str, global_memory: GlobalMemoryPool):
        """
        Args:
            agent_id: 检索头Agent的ID
            global_memory: 全局记忆池
        """
        self.agent_id = agent_id
        self.global_memory = global_memory
        self.retrieval_log: List[Dict[str, Any]] = []
        self.total_retrievals = 0
    
    def retrieve(self, query: RetrievalQuery) -> RetrievalResult:
        """精准检索——模拟Retrieval Head的低熵注意力模式
        
        Args:
            query: 检索查询
            
        Returns:
            RetrievalResult: 检索结果
        """
        self.total_retrievals += 1
        
        # 1. 语义检索：从全局记忆中找相关内容
        candidates = self.global_memory.semantic_search(
            query.target_description,
            top_k=20,
        )
        
        # 2. 约束过滤
        filtered = self._apply_constraints(candidates, query.constraints)
        
        # 3. 精准排序：根据用途评估相关性
        ranked = self._rank_by_utility(filtered, query.purpose)
        
        # 4. 返回top-K
        result_items = ranked[:query.top_k]
        
        # 计算检索精度
        precision = self._compute_precision(result_items, query)
        
        result = RetrievalResult(
            items=result_items,
            total_candidates=len(candidates),
            retrieval_precision=precision,
            query=query,
        )
        
        # 记录检索日志
        self.retrieval_log.append({
            "timestamp": time.time(),
            "requester": query.requester_id,
            "target": query.target_description[:50],
            "candidates": len(candidates),
            "returned": len(result_items),
            "precision": precision,
        })
        
        return result
    
    def _apply_constraints(
        self,
        items: List[MemoryItem],
        constraints: Dict[str, Any],
    ) -> List[MemoryItem]:
        """应用约束过滤"""
        filtered = items
        
        # 按agent_id过滤
        if "agent_id" in constraints:
            target_id = constraints["agent_id"]
            filtered = [item for item in filtered if item.agent_id == target_id]
        
        # 按memory_type过滤
        if "memory_type" in constraints:
            target_type = constraints["memory_type"]
            filtered = [item for item in filtered if item.memory_type == target_type]
        
        # 按时间范围过滤
        if "after_timestamp" in constraints:
            ts = constraints["after_timestamp"]
            filtered = [item for item in filtered if item.timestamp >= ts]
        
        # 按最低重要性过滤
        if "min_importance" in constraints:
            min_imp = constraints["min_importance"]
            filtered = [item for item in filtered if item.importance >= min_imp]
        
        return filtered
    
    def _rank_by_utility(
        self,
        items: List[MemoryItem],
        purpose: str,
    ) -> List[MemoryItem]:
        """根据用途评估相关性排序
        
        不是简单的相似度排序，而是"这条信息对当前推理有什么用"。
        """
        if not purpose:
            return items
        
        purpose_embed = _simple_hash_embed(purpose)
        
        scored = []
        for item in items:
            # 综合评分：语义相关性 + 重要性 + 时效性
            content_embed = item.embedding
            semantic_score = _cosine_similarity(purpose_embed, content_embed)
            time_decay = math.exp(-0.001 * (time.time() - item.timestamp))
            
            final_score = (
                semantic_score * 0.5 +
                item.importance * 0.3 +
                time_decay * 0.2
            )
            scored.append((final_score, item))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored]
    
    def _compute_precision(
        self,
        items: List[MemoryItem],
        query: RetrievalQuery,
    ) -> float:
        """计算检索精度（简化版）"""
        if not items:
            return 0.0
        
        # 基于语义相关性的精度估计
        query_embed = _simple_hash_embed(query.target_description)
        total_score = 0.0
        for item in items:
            total_score += _cosine_similarity(query_embed, item.embedding)
        
        return total_score / len(items) if items else 0.0
    
    def get_stats(self) -> Dict[str, Any]:
        """获取检索头统计"""
        avg_precision = 0.0
        if self.retrieval_log:
            avg_precision = sum(r.get("precision", 0) for r in self.retrieval_log) / len(self.retrieval_log)
        
        return {
            "agent_id": self.agent_id,
            "total_retrievals": self.total_retrievals,
            "average_precision": round(avg_precision, 3),
            "recent_retrievals": self.retrieval_log[-5:],
        }


# ============================================================================
# LazinessDetector — 懒惰检测器
# ============================================================================

class LazinessDetector:
    """上下文舒适区检测器
    
    检测Agent是否处于"上下文舒适区"——拥有足够多本地信息，
    不再主动通过Router获取其他Agent的信息。
    
    四个检测指标：
    1. 检索频率下降：Agent长时间不向Global Memory发起检索请求
    2. 修正率下降：Agent在Global Sync后几乎不修正自己的结论
    3. 置信度膨胀：Agent的置信度持续上升但不被外部信息挑战
    4. 信息源多样性下降：Agent的推理链中引用的信息源越来越单一
    """
    
    # 懒惰阈值
    LAZINESS_THRESHOLD = 0.7
    WINDOW_SIZE = 20
    
    def __init__(self, window_size: int = 20):
        """
        Args:
            window_size: 滑动窗口大小（最近N个step）
        """
        self.window_size = window_size
        self.metrics_history: Dict[str, List[Dict[str, float]]] = defaultdict(list)
    
    def check(self, agent_id: str, agent_state: Optional[Dict[str, Any]] = None) -> LazinessAlert:
        """检查单个Agent是否处于舒适区
        
        Args:
            agent_id: Agent ID
            agent_state: Agent当前状态（可选）
            
        Returns:
            LazinessAlert: 懒惰检测结果
        """
        history = self.metrics_history[agent_id]
        
        # 如果agent_state提供了，记录当前指标
        if agent_state:
            self._record_metrics(agent_id, agent_state)
            history = self.metrics_history[agent_id]
        
        # 如果没有足够历史数据，返回低懒惰分数
        if len(history) < 3:
            return LazinessAlert(
                agent_id=agent_id,
                laziness_score=0.0,
                is_lazy=False,
                details={"reason": "insufficient_history"},
            )
        
        # 取最近window_size个step的指标
        recent = history[-self.window_size:]
        
        # 指标1：检索频率（最近的检索请求比例）
        retrieval_rate = self._compute_retrieval_rate(recent)
        
        # 指标2：Sync后修正率
        revision_rate = self._compute_revision_rate(recent)
        
        # 指标3：置信度变化趋势
        confidence_trend = self._compute_confidence_trend(recent)
        
        # 指标4：信息源多样性
        source_diversity = self._compute_source_diversity(recent)
        
        # 综合懒惰分数
        laziness_score = self._compute_laziness_score(
            retrieval_rate, revision_rate, confidence_trend, source_diversity
        )
        
        alert = LazinessAlert(
            agent_id=agent_id,
            laziness_score=laziness_score,
            is_lazy=laziness_score > self.LAZINESS_THRESHOLD,
            details={
                "retrieval_rate": retrieval_rate,
                "revision_rate": revision_rate,
                "confidence_trend": confidence_trend,
                "source_diversity": source_diversity,
            },
        )
        
        if alert.is_lazy:
            logger.warning(
                f"[LazinessDetector] Agent {agent_id} 处于舒适区! "
                f"laziness_score={laziness_score:.2f}"
            )
        
        return alert
    
    def intervention(self, alert: LazinessAlert) -> Optional[InterventionAction]:
        """对"懒惰"Agent的干预措施
        
        类比论文中的干预：
        - 论文：对全注意力层应用NoPE → 打破位置依赖
        - Agent系统：强制注入"意外信息" → 打破认知舒适区
        
        Args:
            alert: 懒惰检测结果
            
        Returns:
            InterventionAction或None（不懒惰时）
        """
        if not alert.is_lazy:
            return None
        
        actions = []
        
        # 干预策略1：强制检索任务
        forced_query = f"请检索全局记忆中与当前任务相关但尚未使用的信息"
        
        # 干预策略2：注入矛盾信息
        contradicting_info = (
            f"注意：全局记忆池中存在与你的当前结论可能矛盾的信息。"
            f"请重新评估你的推理过程。"
        )
        
        # 干预策略3：缩小上下文窗口
        # 如果懒惰分数很高，大幅缩小窗口
        if alert.laziness_score > 0.85:
            new_window = 1024
        elif alert.laziness_score > 0.7:
            new_window = 2048
        else:
            new_window = None  # 不调整
        
        return InterventionAction(
            agent_id=alert.agent_id,
            forced_query=forced_query,
            contradicting_info=contradicting_info,
            new_window_size=new_window,
            rationale=(
                f"Agent处于上下文舒适区(laziness={alert.laziness_score:.2f})，"
                f"需要打破局部依赖"
            ),
        )
    
    def _record_metrics(self, agent_id: str, agent_state: Dict[str, Any]) -> None:
        """记录Agent当前step的指标"""
        metrics = {
            "timestamp": time.time(),
            "retrieval_count": float(agent_state.get("retrieval_count", 0)),
            "revision_count": float(agent_state.get("revision_count", 0)),
            "confidence": float(agent_state.get("confidence", 0.5)),
            "source_count": float(agent_state.get("source_count", 1)),
            "sync_participated": float(agent_state.get("sync_participated", 0)),
        }
        self.metrics_history[agent_id].append(metrics)
        
        # 保持窗口大小
        if len(self.metrics_history[agent_id]) > self.window_size * 2:
            self.metrics_history[agent_id] = self.metrics_history[agent_id][-self.window_size:]
    
    def _compute_retrieval_rate(self, history: List[Dict[str, float]]) -> float:
        """计算检索频率（最近step中有检索行为的比例）"""
        if not history:
            return 0.0
        retrieval_steps = sum(1 for m in history if m.get("retrieval_count", 0) > 0)
        return retrieval_steps / len(history)
    
    def _compute_revision_rate(self, history: List[Dict[str, float]]) -> float:
        """计算Sync后修正率"""
        sync_steps = [m for m in history if m.get("sync_participated", 0) > 0]
        if not sync_steps:
            return 0.5  # 没有sync数据时返回中间值
        revision_steps = sum(1 for m in sync_steps if m.get("revision_count", 0) > 0)
        return revision_steps / len(sync_steps)
    
    def _compute_confidence_trend(self, history: List[Dict[str, float]]) -> float:
        """计算置信度变化趋势
        
        返回值 > 0.5 表示置信度持续上升（可能的懒惰信号）
        返回值 < 0.5 表示置信度稳定或下降（正常）
        """
        if len(history) < 2:
            return 0.5
        
        confidences = [m.get("confidence", 0.5) for m in history]
        
        # 计算线性趋势斜率
        n = len(confidences)
        x_mean = (n - 1) / 2.0
        y_mean = sum(confidences) / n
        
        numerator = sum((i - x_mean) * (c - y_mean) for i, c in enumerate(confidences))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0.5
        
        slope = numerator / denominator
        
        # 将斜率映射到0-1范围（斜率0→0.5，正斜率→>0.5，负斜率→<0.5）
        return max(0.0, min(1.0, 0.5 + slope * 2))
    
    def _compute_source_diversity(self, history: List[Dict[str, float]]) -> float:
        """计算信息源多样性
        
        返回 0-1，值越低表示信息源越单一（懒惰信号）
        """
        if not history:
            return 0.5
        
        source_counts = [m.get("source_count", 1) for m in history]
        avg_sources = sum(source_counts) / len(source_counts)
        
        # 归一化到0-1（假设10个信息源为满分）
        return min(1.0, avg_sources / 10.0)
    
    def _compute_laziness_score(
        self,
        retrieval_rate: float,
        revision_rate: float,
        confidence_trend: float,
        source_diversity: float,
    ) -> float:
        """综合懒惰分数计算
        
        懒惰的特征：
        - 检索频率低 → 高懒惰分
        - 修正率低 → 高懒惰分
        - 置信度持续上升 → 高懒惰分
        - 信息源单一 → 高懒惰分
        """
        # 各指标的懒惰贡献
        lazy_retrieval = 1.0 - retrieval_rate      # 检索越少越懒
        lazy_revision = 1.0 - revision_rate         # 修正越少越懒
        lazy_confidence = confidence_trend           # 置信度越上升越懒
        lazy_diversity = 1.0 - source_diversity      # 信息源越单一越懒
        
        # 加权综合
        score = (
            lazy_retrieval * 0.3 +
            lazy_revision * 0.25 +
            lazy_confidence * 0.25 +
            lazy_diversity * 0.2
        )
        
        return round(max(0.0, min(1.0, score)), 3)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取检测器统计"""
        return {
            "window_size": self.window_size,
            "tracked_agents": len(self.metrics_history),
            "lazy_agents": [
                aid for aid, history in self.metrics_history.items()
                if history and self._compute_laziness_score(
                    self._compute_retrieval_rate(history[-self.window_size:]),
                    self._compute_revision_rate(history[-self.window_size:]),
                    self._compute_confidence_trend(history[-self.window_size:]),
                    self._compute_source_diversity(history[-self.window_size:]),
                ) > self.LAZINESS_THRESHOLD
            ],
        }


# ============================================================================
# AdaptiveWindowController — 自适应窗口控制器
# ============================================================================

class AdaptiveWindowController:
    """自适应窗口控制器
    
    核心思想：窗口大小不是固定的，而是根据任务阶段动态调整。
    
    策略（类比论文）：
    - 任务初期：较大窗口（8K），允许Agent快速建立局部理解
    - 任务中期：缩小窗口（4K），迫使Agent开始检索远程信息
    - 任务后期：最小窗口（2K）+ 频繁Sync，聚焦最终决策
    
    论文发现：小窗口+NoPE组合最优
    """
    
    def __init__(self, initial_window: int = 8192):
        """
        Args:
            initial_window: 初始窗口大小
        """
        self.initial_window = initial_window
        self.current_window = initial_window
        self.phase = "exploration"  # "exploration" | "refinement" | "decision"
        self._history: List[Dict[str, Any]] = []
    
    def adjust(self, task_progress: float, laziness_score: float) -> int:
        """根据任务进度和懒惰程度调整窗口
        
        Args:
            task_progress: 0-1，任务完成进度
            laziness_score: 0-1，懒惰检测分数
            
        Returns:
            新的窗口大小（token数）
        """
        if task_progress < 0.3:
            # 探索阶段：保持较大窗口
            self.phase = "exploration"
            target_window = max(4096, self.initial_window)
            
        elif task_progress < 0.7:
            # 精炼阶段：缩小窗口，迫使检索
            self.phase = "refinement"
            target_window = 4096
            
            # 如果懒惰分数高，进一步缩小
            if laziness_score > 0.5:
                target_window = 2048
                
        else:
            # 决策阶段：最小窗口 + 高频Sync
            self.phase = "decision"
            target_window = 2048
            
            if laziness_score > 0.3:
                target_window = 1024
        
        # 平滑过渡（不跳变）
        new_window = int(0.7 * self.current_window + 0.3 * target_window)
        
        # 确保在合理范围内
        new_window = max(1024, min(self.initial_window, new_window))
        
        self.current_window = new_window
        
        self._history.append({
            "timestamp": time.time(),
            "task_progress": task_progress,
            "laziness_score": laziness_score,
            "phase": self.phase,
            "window_size": new_window,
        })
        
        return new_window
    
    def get_sync_interval(self) -> int:
        """根据阶段调整Sync频率"""
        if self.phase == "exploration":
            return 20  # 每20步同步一次
        elif self.phase == "refinement":
            return 10  # 每10步同步一次
        else:
            return 5   # 每5步同步一次
    
    def get_phase(self) -> str:
        """获取当前阶段"""
        return self.phase
    
    def get_stats(self) -> Dict[str, Any]:
        """获取控制器统计"""
        return {
            "initial_window": self.initial_window,
            "current_window": self.current_window,
            "phase": self.phase,
            "adjustment_history": self._history[-10:],
        }


# ============================================================================
# AdaptiveContextManager — 编排入口
# ============================================================================

class AdaptiveContextManager:
    """自适应上下文管理器 — 编排入口
    
    在CDoL Engine执行过程中被调用：
    - 控制每个Agent的本地窗口大小
    - 定期触发全局同步
    - 检测懒惰并干预
    """
    
    def __init__(
        self,
        global_memory: Optional[GlobalMemoryPool] = None,
        initial_window: int = 8192,
        sync_interval: int = 10,
        llm_chat: Optional[Callable] = None,
        information_policy: Optional[Any] = None,
    ):
        """
        Args:
            global_memory: 全局记忆池（None时自动创建）
            initial_window: 初始窗口大小
            sync_interval: 同步间隔
            llm_chat: LLM调用函数
            information_policy: AgentInformationPolicy实例（可选，用于三层信息架构）
        """
        self.global_memory = global_memory or GlobalMemoryPool()
        self.window_controller = AdaptiveWindowController(initial_window=initial_window)
        self.laziness_detector = LazinessDetector()
        self.sync_engine = ForcedGlobalSync(
            sync_interval=sync_interval,
            llm_chat=llm_chat,
        )
        self.retrieval_head = RetrievalHeadAgent(
            agent_id="retrieval-head",
            global_memory=self.global_memory,
        )
        
        # Phase 7: 信息策略（三层信息架构）
        self.information_policy = information_policy
        
        # Agent上下文窗口映射
        self._agent_windows: Dict[str, LocalContextWindow] = {}
        
        logger.info(
            f"[AdaptiveContextManager] 初始化完成: "
            f"window={initial_window}, sync_interval={sync_interval}, "
            f"information_policy={'enabled' if information_policy else 'disabled'}"
        )
    
    def prepare_agent(
        self,
        agent: Any,
        task_progress: float = 0.0,
    ) -> LocalContextWindow:
        """在Agent执行前准备上下文环境
        
        Args:
            agent: Agent对象（需有name或agent_id属性）
            task_progress: 当前任务进度 0-1
            
        Returns:
            为该Agent配置的LocalContextWindow
        """
        agent_id = getattr(agent, 'name', getattr(agent, 'agent_id', str(agent)))
        
        # 检查懒惰
        laziness = self.laziness_detector.check(agent_id)
        
        # 自适应窗口
        window_size = self.window_controller.adjust(task_progress, laziness.laziness_score)
        
        # 获取或创建Agent的本地窗口
        if agent_id not in self._agent_windows:
            self._agent_windows[agent_id] = LocalContextWindow(
                max_tokens=window_size,
                strategy="mixed",
                adaptive=True,
            )
        
        window = self._agent_windows[agent_id]
        window.resize(window_size)
        
        # 如果Agent支持上下文窗口设置
        if hasattr(agent, 'set_context_window'):
            agent.set_context_window(window)
        
        # 设置全局同步回调
        if hasattr(agent, 'set_global_sync_callback'):
            agent.set_global_sync_callback(
                lambda: self.sync_engine.get_latest_summary(self.global_memory)
            )
        
        # 懒惰干预
        if laziness.is_lazy:
            intervention = self.laziness_detector.intervention(laziness)
            if intervention and intervention.new_window_size:
                window.resize(intervention.new_window_size)
                logger.info(
                    f"[AdaptiveContextManager] 对Agent {agent_id} 实施干预: "
                    f"窗口缩小到{intervention.new_window_size}"
                )
        
        return window
    
    def on_step_complete(
        self,
        agent_id: str,
        conclusion: Optional[Any] = None,
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[SyncResult]:
        """每步完成后：更新全局记忆 + 检查同步
        
        Args:
            agent_id: Agent ID
            conclusion: Agent的中间结论（如果有）
            agent_state: Agent状态（用于懒惰检测）
            
        Returns:
            SyncResult（如果触发了同步），否则None
        """
        # 将Agent的中间结论写入全局记忆
        if conclusion:
            self.global_memory.add_conclusion(agent_id, conclusion)
        
        # 更新懒惰检测指标
        if agent_state:
            self.laziness_detector.check(agent_id, agent_state)
        
        # 检查是否触发全局同步
        sync_result = self.sync_engine.maybe_sync(self.global_memory)
        
        return sync_result
    
    def retrieve(self, query: str, requester_id: str = "", top_k: int = 5) -> RetrievalResult:
        """通过检索头Agent检索全局记忆
        
        Args:
            query: 查询文本
            requester_id: 请求者ID
            top_k: 返回数量
            
        Returns:
            RetrievalResult
        """
        retrieval_query = RetrievalQuery(
            requester_id=requester_id,
            target_description=query,
            top_k=top_k,
        )
        return self.retrieval_head.retrieve(retrieval_query)
    
    def get_global_summary(self) -> str:
        """获取当前全局摘要"""
        return self.sync_engine.get_latest_summary(self.global_memory)
    
    def get_filtered_context_for_agent(
        self,
        agent_id: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """根据三层信息架构，为指定Agent过滤可访问的全局记忆
        
        三层架构：
        - 全局视野层 (Coordinator, Planner): 可访问所有记忆
        - CDoL参与层 (Researcher, Executor等): 只能访问自己的结论 + 全局同步内容
        - 旁观记录层 (Archivist): 只访问中间结论（不含原始上下文）
        
        Args:
            agent_id: Agent ID
            top_k: 最大返回数量
            
        Returns:
            过滤后的记忆条目列表
        """
        # 如果没有信息策略，返回所有记忆（向后兼容）
        if not self.information_policy:
            items = self.global_memory._all_items[-top_k:]
            return [item.to_dict() for item in items]
        
        try:
            tier = self.information_policy.get_tier(agent_id)
        except (ValueError, KeyError):
            # 未知Agent，降级为旁观层权限（只读结论）
            tier = self.information_policy.AgentTier.OBSERVER if hasattr(self.information_policy, 'AgentTier') else None
            if tier is None:
                items = self.global_memory._all_items[-top_k:]
                return [item.to_dict() for item in items]
        
        # 根据层级过滤
        tier_value = tier.value if hasattr(tier, 'value') else str(tier)
        
        if tier_value == "global":
            # 全局视野层：可访问所有
            items = self.global_memory._all_items[-top_k:]
        elif tier_value == "observer":
            # 旁观记录层：只看中间结论
            items = [
                item for item in self.global_memory._all_items
                if item.memory_type == "conclusion"
            ][-top_k:]
        else:
            # CDoL参与层：自己的结论 + 最近的全局结论
            own_items = [
                item for item in self.global_memory._all_items
                if item.agent_id == agent_id
            ]
            recent_global = self.global_memory.conclusions[-(top_k // 2):]
            # 合并去重
            seen = set()
            merged = []
            for item in own_items + recent_global:
                if id(item) not in seen:
                    seen.add(id(item))
                    merged.append(item)
            items = merged[-top_k:]
        
        return [item.to_dict() for item in items]
    
    def notify_archivist(
        self,
        conclusion: Any,
        agent_id: str = "",
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryItem]:
        """通知Archivist对中间结论进行蒸馏归档
        
        Args:
            conclusion: Agent产出的中间结论
            agent_id: 产出结论的Agent ID
            task_context: 任务上下文（可选）
            
        Returns:
            归档的MemoryItem，如果Archivist不可用则返回None
        """
        if not conclusion:
            return None
        
        # 将结论标记为中间结论，写入全局记忆池
        content = str(conclusion)
        if hasattr(conclusion, 'conclusion'):
            content = conclusion.conclusion
        
        metadata = {
            "source_agent": agent_id,
            "task_context": task_context or {},
            "tier": "intermediate_conclusion",
        }
        
        item = self.global_memory.add(
            memory_type="conclusion",
            agent_id=agent_id,
            content=content,
            metadata=metadata,
            importance=0.6,  # 中间结论中等重要性
        )
        
        logger.info(
            f"[AdaptiveContextManager] 通知Archivist: "
            f"agent={agent_id}, content_len={len(content)}"
        )
        
        return item
    
    def get_stats(self) -> Dict[str, Any]:
        """获取完整统计信息"""
        return {
            "global_memory": self.global_memory.get_stats(),
            "window_controller": self.window_controller.get_stats(),
            "laziness_detector": self.laziness_detector.get_stats(),
            "sync_engine": self.sync_engine.get_stats(),
            "retrieval_head": self.retrieval_head.get_stats(),
            "agent_windows": {
                aid: w.get_stats() for aid, w in self._agent_windows.items()
            },
        }


# ============================================================================
# 便捷函数
# ============================================================================

def create_context_manager(
    backing_store: Optional[Any] = None,
    initial_window: int = 8192,
    sync_interval: int = 10,
    llm_chat: Optional[Callable] = None,
    information_policy: Optional[Any] = None,
) -> AdaptiveContextManager:
    """创建自适应上下文管理器的工厂函数
    
    Args:
        backing_store: 持久化后端
        initial_window: 初始窗口大小
        sync_interval: 同步间隔
        llm_chat: LLM调用函数
        information_policy: AgentInformationPolicy实例（可选）
    """
    global_memory = GlobalMemoryPool(backing_store=backing_store)
    return AdaptiveContextManager(
        global_memory=global_memory,
        initial_window=initial_window,
        sync_interval=sync_interval,
        llm_chat=llm_chat,
        information_policy=information_policy,
    )
