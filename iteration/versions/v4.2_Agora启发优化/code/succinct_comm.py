# -*- coding: utf-8 -*-
"""
铉枢·炉守 Succinct Communication — 通信极简化模块
XuanHub Succinct Communication v4.2

基于 Agora (ICML 2026) Succinct Memory & Communication 设计。

核心功能：
1. 两层信封设计：CoreEnvelope(≤500token) + DetailEnvelope(按需获取)
2. CoreEnvelope 包含：task_id, role, goal_summary, key_findings, status
3. DetailEnvelope 包含：完整上下文，通过 reference_id 按需拉取
4. 兼容现有 A2A 协议（backward compatible）
5. 预期 Token 消耗降低 30-50%

消息类型：
- TASK_BRIEF: 最小化任务描述
- RESULT_SUMMARY: 压缩结果
- ERROR_REPORT: 紧凑错误信息
- KNOWLEDGE_REF: 引用知识条目
- HYPOTHESIS_REF: 引用假说
- CONTEXT_REQUEST: 请求详细上下文
- CONTEXT_RESPONSE: 详细上下文（按需）
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SuccinctComm")


# ============================================================================
# 枚举与数据结构
# ============================================================================

class MessageType(Enum):
    """Compressed message types for inter-agent communication"""
    TASK_BRIEF = "task_brief"
    RESULT_SUMMARY = "result_summary"
    ERROR_REPORT = "error_report"
    KNOWLEDGE_REF = "knowledge_ref"
    HYPOTHESIS_REF = "hypothesis_ref"
    CONTEXT_REQUEST = "context_request"
    CONTEXT_RESPONSE = "context_response"


@dataclass
class CommunicationEnvelope:
    """
    Two-layer communication envelope.

    Layer 1 (Core): Always transmitted — compact summary (~200-500 tokens)
    Layer 2 (Detail): On-demand reference — agent can request full context

    This design reduces average token consumption by 30-50% because
    most inter-agent messages only need the core layer.
    """
    envelope_id: str = ""
    message_type: MessageType = MessageType.TASK_BRIEF
    sender: str = ""
    receiver: str = ""

    # Layer 1: Core context (always transmitted)
    core_summary: str = ""
    key_entities: List[str] = field(default_factory=list)
    action_required: str = ""

    # Layer 2: Detail references (on-demand)
    detail_refs: List[Dict] = field(default_factory=list)
    # Each ref: {"type": "hypothesis|knowledge|file|checkpoint", "id": "...", "summary": "..."}

    # Metadata
    estimated_core_tokens: int = 0
    estimated_full_tokens: int = 0
    compression_ratio: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_core_prompt(self) -> str:
        """Generate the core prompt (Layer 1 only)"""
        parts = [f"## [{self.message_type.value}] From: {self.sender}\n"]
        parts.append(self.core_summary)

        if self.action_required:
            parts.append(f"\n**Required Action**: {self.action_required}")

        if self.key_entities:
            parts.append(f"\n**Key Entities**: {', '.join(self.key_entities)}")

        if self.detail_refs:
            ref_summary = "\n".join(
                f"  - [{r['type']}] {r['id']}: {r.get('summary', '')}"
                for r in self.detail_refs
            )
            parts.append(f"\n**Detail References** (request if needed):\n{ref_summary}")

        return '\n'.join(parts)

    def to_dict(self) -> Dict:
        """Serialize envelope to dictionary"""
        return {
            "envelope_id": self.envelope_id,
            "message_type": self.message_type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "core_summary": self.core_summary,
            "key_entities": self.key_entities,
            "action_required": self.action_required,
            "detail_refs": self.detail_refs,
            "estimated_core_tokens": self.estimated_core_tokens,
            "estimated_full_tokens": self.estimated_full_tokens,
            "compression_ratio": self.compression_ratio,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CommunicationEnvelope":
        """Deserialize envelope from dictionary"""
        return cls(
            envelope_id=data.get("envelope_id", ""),
            message_type=MessageType(data.get("message_type", "task_brief")),
            sender=data.get("sender", ""),
            receiver=data.get("receiver", ""),
            core_summary=data.get("core_summary", ""),
            key_entities=data.get("key_entities", []),
            action_required=data.get("action_required", ""),
            detail_refs=data.get("detail_refs", []),
            estimated_core_tokens=data.get("estimated_core_tokens", 0),
            estimated_full_tokens=data.get("estimated_full_tokens", 0),
            compression_ratio=data.get("compression_ratio", 0.0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )

    def resolve_detail(self, ref_type: str, ref_id: str, resolver_fn=None) -> str:
        """Resolve a detail reference (Layer 2 on-demand)"""
        if resolver_fn:
            return resolver_fn(ref_type, ref_id)
        return f"[Detail for {ref_type}:{ref_id} - not resolved]"


# ============================================================================
# SuccinctCommunicationManager 主类
# ============================================================================

class SuccinctCommunicationManager:
    """
    Manages inter-agent communication with compression.

    Integration with existing A2A Protocol:
    - Wraps A2AMessage creation with CommunicationEnvelope
    - Before sending, extracts core summary and creates detail refs
    - Receiver can request details on demand

    Compatibility:
    - Existing A2A messages still work (backward compatible)
    - New messages use CommunicationEnvelope format
    - Gradual migration: agents can use either format
    """

    def __init__(
        self,
        knowledge_library: Any = None,
        hypothesis_engine: Any = None,
        token_budget: int = 500,
    ):
        self.knowledge_library = knowledge_library
        self.hypothesis_engine = hypothesis_engine
        self.token_budget = token_budget

        # Detail store for on-demand resolution
        self._detail_store: Dict[str, Dict[str, Any]] = {}

        self._stats: Dict[str, Any] = {
            "messages_compressed": 0,
            "total_core_tokens": 0,
            "total_full_tokens": 0,
            "detail_requests": 0,
        }

    # ============ Core API ============

    def wrap_message(
        self,
        content: str,
        sender: str,
        receiver: str,
        message_type: MessageType = MessageType.TASK_BRIEF,
        action_required: str = "",
        related_entities: Optional[List[Dict]] = None,
    ) -> CommunicationEnvelope:
        """
        Wrap a full message into a CommunicationEnvelope.

        Primary API per spec: wrap_message()
        """
        envelope = CommunicationEnvelope(
            envelope_id=f"env_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._stats['messages_compressed']}",
            message_type=message_type,
            sender=sender,
            receiver=receiver,
            core_summary=self._summarize(content),
            action_required=action_required,
        )

        if related_entities:
            for entity in related_entities:
                envelope.detail_refs.append(entity)
                envelope.key_entities.append(entity.get("id", ""))

        # Estimate compression
        full_tokens = len(content) * 2  # rough estimate for mixed CN/EN
        core_tokens = len(envelope.core_summary) * 2
        envelope.estimated_full_tokens = full_tokens
        envelope.estimated_core_tokens = core_tokens
        envelope.compression_ratio = core_tokens / max(1, full_tokens)

        # Store full content for on-demand resolution
        self._detail_store[envelope.envelope_id] = {
            "full_content": content,
            "sender": sender,
            "timestamp": envelope.timestamp,
        }

        self._stats["messages_compressed"] += 1
        self._stats["total_core_tokens"] += core_tokens
        self._stats["total_full_tokens"] += full_tokens

        return envelope

    def unwrap_message(self, envelope: CommunicationEnvelope) -> str:
        """
        Unwrap a CommunicationEnvelope to get the core prompt.

        Primary API per spec: unwrap_message()
        """
        return envelope.to_core_prompt()

    def request_detail(
        self,
        envelope: CommunicationEnvelope,
        ref_type: str = "",
        ref_id: str = "",
    ) -> str:
        """
        Request detailed content from an envelope.

        Primary API per spec: request_detail()
        """
        self._stats["detail_requests"] += 1

        # Try resolving from envelope's detail refs
        if ref_type and ref_id:
            return self.resolve_detail_request(envelope, ref_type, ref_id)

        # Fall back to full content from detail store
        if envelope.envelope_id in self._detail_store:
            return self._detail_store[envelope.envelope_id]["full_content"]

        return "[Detail not available]"

    def create_task_brief(
        self,
        task_description: str,
        sender: str,
        receiver: str,
        related_hypotheses: List[str] = None,
        related_knowledge: List[str] = None,
        related_files: List[str] = None,
    ) -> CommunicationEnvelope:
        """
        Create a compressed task brief.

        Instead of sending full context, sends:
        - Core: Task description + key constraints
        - Refs: Hypothesis IDs, Knowledge IDs, file paths
        """
        envelope = CommunicationEnvelope(
            message_type=MessageType.TASK_BRIEF,
            sender=sender,
            receiver=receiver,
            core_summary=self._summarize(task_description),
            action_required="Execute the described task",
        )

        if related_hypotheses:
            for h_id in related_hypotheses:
                envelope.detail_refs.append({
                    "type": "hypothesis",
                    "id": h_id,
                    "summary": self._get_hypothesis_summary(h_id),
                })
                envelope.key_entities.append(h_id)

        if related_knowledge:
            for k_id in related_knowledge:
                envelope.detail_refs.append({
                    "type": "knowledge",
                    "id": k_id,
                    "summary": self._get_knowledge_summary(k_id),
                })
                envelope.key_entities.append(k_id)

        if related_files:
            for f_path in related_files:
                envelope.detail_refs.append({
                    "type": "file",
                    "id": f_path,
                    "summary": f"File: {f_path}",
                })

        full_tokens = len(task_description) * 2
        core_tokens = len(envelope.core_summary) * 2
        envelope.estimated_full_tokens = full_tokens
        envelope.estimated_core_tokens = core_tokens
        envelope.compression_ratio = core_tokens / max(1, full_tokens)

        self._stats["messages_compressed"] += 1
        self._stats["total_core_tokens"] += core_tokens
        self._stats["total_full_tokens"] += full_tokens

        return envelope

    def create_result_summary(
        self,
        result_text: str,
        sender: str,
        receiver: str,
        hypothesis_updates: List[Dict] = None,
    ) -> CommunicationEnvelope:
        """Create a compressed result summary"""
        envelope = CommunicationEnvelope(
            message_type=MessageType.RESULT_SUMMARY,
            sender=sender,
            receiver=receiver,
            core_summary=self._summarize(result_text),
            action_required="Review result and decide next steps",
        )

        if hypothesis_updates:
            for update in hypothesis_updates:
                envelope.detail_refs.append({
                    "type": "hypothesis_update",
                    "id": update.get("hypothesis_id", ""),
                    "summary": (
                        f"Status: {update.get('status', 'unknown')}, "
                        f"Confidence: {update.get('confidence', 0):.2f}"
                    ),
                })

        return envelope

    def wrap_a2a_message(self, a2a_message: Any) -> CommunicationEnvelope:
        """
        Wrap an existing A2A message in CommunicationEnvelope.
        Backward compatibility: existing A2AMessage objects
        can be wrapped without modification.
        """
        content = str(getattr(a2a_message, 'content', ''))

        envelope = CommunicationEnvelope(
            envelope_id=getattr(a2a_message, 'message_id', ''),
            message_type=MessageType.TASK_BRIEF,
            sender=getattr(a2a_message, 'sender_name', ''),
            receiver=getattr(a2a_message, 'receiver_id', ''),
            core_summary=self._summarize(content),
            action_required=getattr(a2a_message, 'action', ''),
        )

        return envelope

    def resolve_detail_request(
        self,
        envelope: CommunicationEnvelope,
        ref_type: str,
        ref_id: str,
    ) -> str:
        """
        Resolve a detail request from a receiver agent.
        """
        self._stats["detail_requests"] += 1

        if ref_type == "hypothesis" and self.hypothesis_engine:
            hypotheses = self.hypothesis_engine._hypotheses
            if ref_id in hypotheses:
                return hypotheses[ref_id].to_four_tuple_str()

        elif ref_type == "knowledge" and self.knowledge_library:
            if ref_id in self.knowledge_library._entries:
                entry = self.knowledge_library._entries[ref_id]
                return f"[{entry.title}] {entry.description}"

        return f"[Detail not available for {ref_type}:{ref_id}]"

    # ============ Internal Methods ============

    def _summarize(self, text: str, max_tokens: Optional[int] = None) -> str:
        """
        Summarize text to fit within token budget.
        Simple strategy: extract key sentences.
        For production, could use LLM-based summarization.
        """
        budget = max_tokens or self.token_budget
        max_chars = budget * 2  # rough char estimate for mixed CN/EN

        if len(text) <= max_chars:
            return text

        # Extract first paragraph + key sentences
        paragraphs = text.split('\n\n')
        result = paragraphs[0] if paragraphs else text[:max_chars]

        if len(result) > max_chars:
            result = result[:max_chars] + "..."

        return result

    def _get_hypothesis_summary(self, h_id: str) -> str:
        """Get compact hypothesis summary"""
        if self.hypothesis_engine and h_id in self.hypothesis_engine._hypotheses:
            h = self.hypothesis_engine._hypotheses[h_id]
            return f"{h.title} [{h.status.value}, conf={h.confidence:.2f}]"
        return f"Hypothesis {h_id}"

    def _get_knowledge_summary(self, k_id: str) -> str:
        """Get compact knowledge summary"""
        if self.knowledge_library and k_id in self.knowledge_library._entries:
            entry = self.knowledge_library._entries[k_id]
            return f"{entry.title} [{entry.knowledge_type.value}]"
        return f"Knowledge {k_id}"

    def get_stats(self) -> Dict:
        """Return stats including estimated savings"""
        savings = 0
        if self._stats["total_full_tokens"] > 0:
            savings = 1 - (self._stats["total_core_tokens"] / self._stats["total_full_tokens"])
        return {
            **self._stats,
            "estimated_savings_ratio": f"{savings:.1%}",
        }
