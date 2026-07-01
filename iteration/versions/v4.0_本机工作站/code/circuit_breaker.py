# -*- coding: utf-8 -*-
"""
铉枢·炉守 熔断器模式
XuanHub Circuit Breaker Pattern
参考: OpenClaw + LangGraph 错误处理
"""

import time
import logging
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock

logger = logging.getLogger("CircuitBreaker")


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态，熔断器关闭
    OPEN = "open"         # 熔断状态，请求被拒绝
    HALF_OPEN = "half_open"  # 半开状态，尝试放行部分请求


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5       # 失败次数阈值，超过后打开熔断器
    success_threshold: int = 2       # 半开状态下成功次数，达到后关闭熔断器
    timeout: float = 30.0           # 熔断超时时间(秒)，超时后进入半开状态
    excluded_errors: tuple = ()     # 不计入失败的错误类型
    
    # Jitter配置 (防止雷鸣羊群效应)
    jitter: bool = True
    jitter_range: float = 0.5       # ±0.5秒随机偏移


@dataclass
class CircuitBreakerStats:
    """熔断器统计"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    
    # 时间窗口统计
    window_start: float = field(default_factory=time.time)
    recent_failures: list = field(default_factory=list)
    
    def add_failure(self, error_type: str) -> None:
        """记录失败"""
        self.failed_calls += 1
        self.recent_failures.append(time.time())
        
        # 保持最近1分钟的失败记录
        cutoff = time.time() - 60
        self.recent_failures = [t for t in self.recent_failures if t > cutoff]
    
    def add_success(self) -> None:
        """记录成功"""
        self.successful_calls += 1
    
    def add_rejection(self) -> None:
        """记录拒绝"""
        self.rejected_calls += 1
    
    def recent_failure_count(self) -> int:
        """最近失败次数"""
        cutoff = time.time() - 60
        return sum(1 for t in self.recent_failures if t > cutoff)
    
    def reset(self) -> None:
        """重置统计"""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rejected_calls = 0
        self.window_start = time.time()
        self.recent_failures.clear()
    
    def to_dict(self) -> Dict:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "success_rate": self.successful_calls / self.total_calls if self.total_calls > 0 else 0,
            "recent_failures_1min": self.recent_failure_count()
        }


class CircuitBreaker:
    """
    熔断器
    
    防止级联故障，在服务持续失败时快速失败而不是持续重试
    
    工作原理:
    - CLOSED: 正常状态，所有请求通过
    - OPEN: 熔断状态，所有请求被拒绝，立即返回
    - HALF_OPEN: 半开状态，放行部分请求测试服务是否恢复
    
    用法:
        cb = CircuitBreaker("ollama_api", failure_threshold=5)
        
        with cb:
            result = call_ollama_api()
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        on_open: Optional[Callable] = None,
        on_close: Optional[Callable] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # 回调函数
        self.on_open = on_open
        self.on_close = on_close
        
        # 状态
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._stats = CircuitBreakerStats()
        
        # 线程安全
        self._lock = Lock()
        
        logger.info(f"[CircuitBreaker] '{name}' initialized (threshold={self.config.failure_threshold}, timeout={self.config.timeout}s)")
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        with self._lock:
            return self._get_state_unlocked()
    
    def _get_state_unlocked(self) -> CircuitState:
        """非线程安全的状态检查（需要持有锁）"""
        if self._state == CircuitState.OPEN:
            # 检查超时
            if self._last_failure_time and \
               time.time() - self._last_failure_time >= self.config.timeout:
                self._transition_to(CircuitState.HALF_OPEN)
        return self._state
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """状态转换"""
        if self._state == new_state:
            return
        
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1
        
        # 重置计数器
        if new_state == CircuitState.HALF_OPEN:
            self._success_count = 0
            logger.warning(f"[CircuitBreaker] '{self.name}' transitioned: {old_state.value} -> {new_state.value} (testing recovery)")
        else:
            self._failure_count = 0
            self._success_count = 0
            logger.warning(f"[CircuitBreaker] '{self.name}' transitioned: {old_state.value} -> {new_state.value}")
        
        # 触发回调
        if new_state == CircuitState.OPEN and self.on_open:
            try:
                self.on_open(self.name)
            except Exception as e:
                logger.error(f"[CircuitBreaker] on_open callback failed: {e}")
        elif new_state == CircuitState.CLOSED and self.on_close:
            try:
                self.on_close(self.name)
            except Exception as e:
                logger.error(f"[CircuitBreaker] on_close callback failed: {e}")
    
    def record_success(self) -> None:
        """记录成功"""
        with self._lock:
            self._stats.add_success()
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
    
    def record_failure(self, error: Exception) -> None:
        """记录失败"""
        with self._lock:
            error_type = type(error).__name__
            
            # 排除不计入的错误
            if error_type in self.config.excluded_errors:
                logger.debug(f"[CircuitBreaker] '{self.name}' excluded error: {error_type}")
                return
            
            self._stats.add_failure(error_type)
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下任何失败都重新打开
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        return self.state != CircuitState.OPEN
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        通过熔断器执行函数
        
        用法:
            cb = CircuitBreaker("api")
            result = cb.call(requests.get, "https://...")
        """
        with self._lock:
            state = self._get_state_unlocked()
            self._stats.total_calls += 1
            
            if state == CircuitState.OPEN:
                self._stats.add_rejection()
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Call rejected to prevent cascading failure."
                )
            
            if state == CircuitState.HALF_OPEN:
                # 半开状态，记录但不阻止
                pass
        
        # 执行函数
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise
    
    def __enter__(self) -> 'CircuitBreaker':
        """上下文管理器入口"""
        with self._lock:
            state = self._get_state_unlocked()
            self._stats.total_calls += 1
            
            if state == CircuitState.OPEN:
                self._stats.add_rejection()
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN."
                )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """上下文管理器出口"""
        if exc_type is not None:
            # 发生异常
            self.record_failure(exc_val)
            return False  # 不吞没异常
        else:
            # 正常返回
            self.record_success()
            return True
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure": self._last_failure_time,
                "stats": self._stats.to_dict()
            }
    
    def reset(self) -> None:
        """重置熔断器"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._stats.reset()
            logger.info(f"[CircuitBreaker] '{self.name}' reset to CLOSED")


class CircuitBreakerOpenError(Exception):
    """熔断器打开错误"""
    pass


class CircuitBreakerRegistry:
    """
    熔断器注册表
    
    管理多个熔断器，支持按名称访问
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._breakers = {}
            cls._instance._lock = Lock()
        return cls._instance
    
    def register(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """注册熔断器"""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
            return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """获取熔断器"""
        with self._lock:
            return self._breakers.get(name)
    
    def get_all(self) -> Dict[str, CircuitBreaker]:
        """获取所有熔断器"""
        with self._lock:
            return self._breakers.copy()
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """获取所有统计"""
        with self._lock:
            return {name: cb.get_stats() for name, cb in self._breakers.items()}
    
    def reset_all(self) -> None:
        """重置所有熔断器"""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()


# 便捷函数
def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """获取全局熔断器"""
    registry = CircuitBreakerRegistry()
    return registry.register(name, config)
