# -*- coding: utf-8 -*-
"""
铉枢·炉守 可观测性模块
XuanHub Observability - Tracing and Metrics
"""

import logging
import time
import uuid
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("AgentTracer")


@dataclass
class Span:
    """调用链路span"""
    span_id: str
    trace_id: str
    parent_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "running"  # running, ok, error
    error_message: Optional[str] = None


@dataclass
class TokenUsage:
    """Token使用统计"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class AgentTracer:
    """
    Agent链路追踪器
    
    功能:
    - 生成trace_id和span_id
    - 记录调用链路
    - 统计Token使用
    - 错误追踪
    """
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.trace_id: Optional[str] = None
        self.spans: List[Span] = []
        self.token_usage = TokenUsage()
        self._current_span: Optional[Span] = None
        
        logger.info(f"[{agent_name}] Tracer initialized")
    
    def start_trace(self) -> str:
        """开始新的trace"""
        self.trace_id = str(uuid.uuid4())[:8]
        self.spans.clear()
        self.token_usage = TokenUsage()
        logger.debug(f"[{self.agent_name}] Trace started: {self.trace_id}")
        return self.trace_id
    
    @contextmanager
    def span(self, name: str, attributes: Dict[str, Any] = None):
        """
        创建span上下文管理器
        
        用法:
            with tracer.span("api_call", {"model": "gpt-4"}):
                response = call_api()
        """
        parent_id = self._current_span.span_id if self._current_span else None
        
        span = Span(
            span_id=str(uuid.uuid4())[:8],
            trace_id=self.trace_id or "no-trace",
            parent_id=parent_id,
            name=name,
            start_time=time.time(),
            attributes=attributes or {}
        )
        
        previous_span = self._current_span
        self._current_span = span
        
        try:
            yield span
            span.end_time = time.time()
            span.status = "ok"
            self.spans.append(span)
        except Exception as e:
            span.end_time = time.time()
            span.status = "error"
            span.error_message = str(e)
            self.spans.append(span)
            raise
        finally:
            self._current_span = previous_span
    
    def record_token_usage(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0
    ) -> None:
        """记录Token使用"""
        self.token_usage.input_tokens += input_tokens
        self.token_usage.output_tokens += output_tokens
        self.token_usage.total_tokens += input_tokens + output_tokens
        self.token_usage.cached_tokens += cached_tokens
    
    def record_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """记录错误"""
        logger.error(
            f"[{self.agent_name}] Error in trace {self.trace_id}: {error}",
            extra={"context": context}
        )
        
        if self._current_span:
            self._current_span.status = "error"
            self._current_span.error_message = str(error)
            if context:
                self._current_span.attributes.update(context)
    
    def get_summary(self) -> Dict[str, Any]:
        """获取追踪摘要"""
        total_duration = 0
        if self.spans:
            first_span = min(self.spans, key=lambda s: s.start_time)
            last_span = max(self.spans, key=lambda s: s.start_time if s.end_time else s.start_time)
            total_duration = (last_span.end_time or last_span.start_time) - first_span.start_time
        
        error_count = sum(1 for s in self.spans if s.status == "error")
        
        return {
            "trace_id": self.trace_id,
            "agent_name": self.agent_name,
            "spans_count": len(self.spans),
            "error_count": error_count,
            "total_duration_ms": round(total_duration * 1000, 2),
            "token_usage": self.token_usage.to_dict()
        }
    
    def export(self) -> Dict[str, Any]:
        """导出完整追踪数据"""
        return {
            "summary": self.get_summary(),
            "spans": [
                {
                    "span_id": s.span_id,
                    "parent_id": s.parent_id,
                    "name": s.name,
                    "duration_ms": round((s.end_time - s.start_time) * 1000, 2) if s.end_time else None,
                    "status": s.status,
                    "error": s.error_message,
                    "attributes": s.attributes
                }
                for s in self.spans
            ]
        }
    
    def log_summary(self) -> None:
        """打印追踪摘要"""
        summary = self.get_summary()
        logger.info(
            f"[{self.agent_name}] Trace {summary['trace_id']} | "
            f"Spans: {summary['spans_count']} | "
            f"Errors: {summary['error_count']} | "
            f"Duration: {summary['total_duration_ms']}ms | "
            f"Tokens: {summary['token_usage']['total_tokens']}"
        )


class MetricsCollector:
    """
    指标收集器
    
    收集和聚合Agent运行指标
    """
    
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {}
    
    def record(self, name: str, value: float) -> None:
        """记录指标值"""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)
        
        # 保持最近1000条
        if len(self.metrics[name]) > 1000:
            self.metrics[name] = self.metrics[name][-1000:]
    
    def increment(self, name: str, delta: int = 1) -> None:
        """增加计数器"""
        self.counters[name] = self.counters.get(name, 0) + delta
    
    def get_stats(self, name: str) -> Optional[Dict[str, float]]:
        """获取指标统计"""
        if name not in self.metrics or not self.metrics[name]:
            return None
        
        values = self.metrics[name]
        sorted_values = sorted(values)
        
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "p50": sorted_values[len(sorted_values) // 2],
            "p95": sorted_values[int(len(sorted_values) * 0.95)],
            "p99": sorted_values[int(len(sorted_values) * 0.99)]
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有统计"""
        return {
            "metrics": {name: self.get_stats(name) for name in self.metrics},
            "counters": self.counters.copy()
        }


# ============ OpenTelemetry兼容导出 ============

class OTelExporter:
    """
    OpenTelemetry格式导出器
    
    将追踪数据导出为OTLP兼容格式
    参考: OpenTelemetry Collector + Microsoft Agent Framework
    """
    
    def __init__(self, service_name: str = "xuanshu-agents"):
        self.service_name = service_name
        self._traces: List[Dict] = []
    
    def export_span(
        self,
        tracer: AgentTracer,
        span: Span,
        resource_attrs: Optional[Dict[str, str]] = None
    ) -> Dict:
        """将Span导出为OpenTelemetry格式"""
        resource = {
            "service.name": self.service_name,
            "service.version": "1.0.0",
            "telemetry.sdk.language": "python",
        }
        if resource_attrs:
            resource.update(resource_attrs)
        
        span_data = {
            "traceId": span.trace_id,
            "spanId": span.span_id,
            "parentSpanId": span.parent_id or "",
            "name": span.name,
            "startTimeUnixNano": int(span.start_time * 1e9),
            "endTimeUnixNano": int(span.end_time * 1e9) if span.end_time else 0,
            "attributes": [
                {"key": k, "value": {"stringValue": str(v)}} for k, v in (span.attributes or {}).items()
            ],
            "status": {
                "code": 1 if span.status == "ok" else 2 if span.status == "error" else 0,
            },
            "resource": [
                {"key": k, "value": {"stringValue": v}} for k, v in resource.items()
            ]
        }
        
        self._traces.append(span_data)
        return span_data
    
    def export_trace(self, tracer: AgentTracer) -> Dict:
        """导出完整Trace为OTLP格式"""
        resource = {
            "service.name": self.service_name,
            "service.version": "1.0.0",
            "agent.name": tracer.agent_name
        }
        
        spans = [self.export_span(tracer, span) for span in tracer.spans]
        
        return {
            "resourceSpans": [{
                "resource": {
                    "attributes": [
                        {"key": k, "value": {"stringValue": v}} for k, v in resource.items()
                    ]
                },
                "scopeSpans": [{"spans": spans}]
            }]
        }
    
    def to_json(self, tracer: AgentTracer) -> str:
        """导出为JSON字符串"""
        import json
        return json.dumps(self.export_trace(tracer), indent=2, ensure_ascii=False)
