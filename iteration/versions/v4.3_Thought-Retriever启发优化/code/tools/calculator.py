# -*- coding: utf-8 -*-
"""
铉枢·炉守 计算器工具
XuanHub Calculator Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 calculate()
支持数学/统计/线性代数运算，底层用numpy
"""

import math
import logging
from typing import Any, Dict, List, Optional, Union
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("Calculator")


# ============ 安全数学环境 ============

SAFE_MATH_NAMESPACE = {
    # 基础数学
    "abs": abs, "round": round, "min": min, "max": max,
    "sum": sum, "len": len, "sorted": sorted,
    "pow": pow, "divmod": divmod,
    # math模块
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10,
    "log2": math.log2, "exp": math.exp, "pow": math.pow,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "pi": math.pi, "e": math.e,
    "ceil": math.ceil, "floor": math.floor,
    "factorial": math.factorial, "gcd": math.gcd,
    "degrees": math.degrees, "radians": math.radians,
    # 统计辅助
    "mean": lambda x: sum(x) / len(x) if x else 0,
    "median": lambda x: sorted(x)[len(x) // 2] if x else 0,
    "stdev": lambda x: (sum((i - sum(x)/len(x))**2 for i in x) / len(x))**0.5 if len(x) > 1 else 0,
    # numpy（如果可用）
    "np": None,  # 延迟导入
}


def _get_numpy():
    """延迟导入numpy"""
    if SAFE_MATH_NAMESPACE["np"] is None:
        try:
            import numpy as _np
            SAFE_MATH_NAMESPACE["np"] = _np
        except ImportError:
            return None
    return SAFE_MATH_NAMESPACE["np"]


# ============ CodeAct全局函数 ============

def calculate(expression: str, variables: Optional[Dict[str, Any]] = None) -> Any:
    """
    数学/统计计算 — CodeAct全局函数
    
    Args:
        expression: 数学表达式或计算代码
        variables: 额外变量字典
    
    Returns:
        计算结果
    
    CodeAct用法:
        result = calculate("sqrt(144) + log10(1000)")
        # 12.0 + 3.0 = 15.0
        
        result = calculate("mean([1, 2, 3, 4, 5])")
        # 3.0
        
        result = calculate("np.array([1,2,3]).dot(np.array([4,5,6]))")
        # 32
    """
    # 安全检查
    forbidden = ["import", "__", "exec", "eval", "compile", "open", "os.", "subprocess"]
    for word in forbidden:
        if word in expression:
            raise ValueError(f"Forbidden pattern in expression: {word}")
    
    # 构建命名空间
    namespace = SAFE_MATH_NAMESPACE.copy()
    if variables:
        namespace.update(variables)
    
    # 尝试导入numpy
    _get_numpy()
    
    try:
        result = eval(expression, {"__builtins__": {}}, namespace)
        return result
    except Exception as e:
        raise ValueError(f"Calculation error: {e}")


def linear_regression(x: List[float], y: List[float]) -> Dict[str, float]:
    """
    简单线性回归 — CodeAct全局函数
    
    Args:
        x: 自变量列表
        y: 因变量列表
    
    Returns:
        {"slope": ..., "intercept": ..., "r_squared": ...}
    """
    n = len(x)
    if n != len(y) or n < 2:
        raise ValueError("x and y must have same length >= 2")
    
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    ss_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    ss_xx = sum((xi - mean_x) ** 2 for xi in x)
    ss_yy = sum((yi - mean_y) ** 2 for yi in y)
    
    slope = ss_xy / ss_xx if ss_xx != 0 else 0
    intercept = mean_y - slope * mean_x
    r_squared = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_xx * ss_yy != 0 else 0
    
    return {"slope": slope, "intercept": intercept, "r_squared": r_squared}


# ============ BaseTool兼容 ============

class CalculatorTool(BaseTool):
    """计算器工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform mathematical and statistical calculations. Supports basic math, trigonometry, statistics, and numpy operations.",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression (e.g., 'sqrt(144) + log10(1000)')"
                    },
                    "variables": {
                        "type": "object",
                        "description": "Additional variables for the expression"
                    }
                },
                "required": ["expression"]
            }
        )
    
    def execute(self, expression: str, variables: Optional[Dict] = None, **kwargs) -> ToolResult:
        try:
            result = calculate(expression, variables=variables)
            return ToolResult(
                success=True,
                output=result,
                metadata={"expression": expression}
            )
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
