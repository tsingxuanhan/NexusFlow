# -*- coding: utf-8 -*-
"""
铉枢·炉守 数据查询工具
XuanHub Data Query Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 query_data()
支持CSV/JSON/内存数据集的过滤、聚合、统计
"""

import os
import json
import csv
import logging
from typing import Any, Dict, List, Optional, Callable
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("DataQuery")


# ============ 内存数据集存储 ============

class DataSetRegistry:
    """内存数据集注册中心 — 全局单例"""
    
    _instance = None
    _datasets: Dict[str, List[Dict]] = {}
    
    @classmethod
    def get_instance(cls) -> 'DataSetRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(self, name: str, data: List[Dict]) -> None:
        self._datasets[name] = data
        logger.info(f"[DataSetRegistry] Registered dataset: {name} ({len(data)} rows)")
    
    def get(self, name: str) -> Optional[List[Dict]]:
        return self._datasets.get(name)
    
    def list_datasets(self) -> List[str]:
        return list(self._datasets.keys())
    
    def remove(self, name: str) -> bool:
        if name in self._datasets:
            del self._datasets[name]
            return True
        return False


# ============ CodeAct全局函数 ============

def query_data(
    source: str,
    filter_expr: Optional[str] = None,
    select: Optional[List[str]] = None,
    limit: int = 100,
    sort_by: Optional[str] = None,
    ascending: bool = True,
) -> List[Dict]:
    """
    查询结构化数据 — CodeAct全局函数
    
    Args:
        source: 数据源(CSV/JSON文件路径 或 注册的数据集名)
        filter_expr: 过滤表达式(Python表达式，变量名为r)
        select: 选择字段列表
        limit: 最大返回行数
        sort_by: 排序字段
        ascending: 升序/降序
    
    Returns:
        匹配的记录列表
    
    CodeAct用法:
        results = query_data("knowledge/materials/papers.csv",
                            filter_expr="r['year'] > 2023",
                            select=["title", "year", "citations"],
                            sort_by="citations",
                            ascending=False,
                            limit=10)
    """
    # 1. 获取数据
    data = _load_data(source)
    if data is None:
        raise ValueError(f"Data source not found: {source}")
    
    # 2. 过滤
    if filter_expr:
        filtered = []
        for r in data:
            try:
                if eval(filter_expr, {"r": r, "__builtins__": {}}):
                    filtered.append(r)
            except Exception:
                continue
        data = filtered
    
    # 3. 选择字段
    if select:
        data = [{k: r.get(k) for k in select if k in r} for r in data]
    
    # 4. 排序
    if sort_by:
        try:
            data.sort(key=lambda r: r.get(sort_by, 0), reverse=not ascending)
        except Exception:
            pass
    
    # 5. 限制数量
    return data[:limit]


def _load_data(source: str) -> Optional[List[Dict]]:
    """加载数据源"""
    registry = DataSetRegistry.get_instance()
    
    # 先检查内存数据集
    data = registry.get(source)
    if data is not None:
        return data
    
    # 尝试加载文件
    if not os.path.exists(source):
        return None
    
    ext = os.path.splitext(source)[1].lower()
    
    if ext == ".json":
        with open(source, 'r', encoding='utf-8') as f:
            content = json.load(f)
            if isinstance(content, list):
                return content
            elif isinstance(content, dict):
                return [content]
            return None
    
    elif ext == ".csv":
        with open(source, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    
    elif ext in (".jsonl", ".ndjson"):
        results = []
        with open(source, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        return results
    
    return None


def register_dataset(name: str, data: List[Dict]) -> str:
    """
    注册内存数据集 — CodeAct全局函数
    
    Args:
        name: 数据集名称
        data: 数据列表
    
    Returns:
        注册结果描述
    """
    registry = DataSetRegistry.get_instance()
    registry.register(name, data)
    return f"Registered dataset '{name}' with {len(data)} rows"


# ============ BaseTool兼容 ============

class DataQueryTool(BaseTool):
    """数据查询工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="data_query",
            description="Query structured data from CSV, JSON files or in-memory datasets. Supports filtering, selection, sorting, and limiting.",
            parameters={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Data source: file path or registered dataset name"
                    },
                    "filter_expr": {
                        "type": "string",
                        "description": "Python filter expression using 'r' as row variable (e.g., \"r['year'] > 2023\")"
                    },
                    "select": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to select"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows to return",
                        "default": 100
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Field to sort by"
                    }
                },
                "required": ["source"]
            }
        )
    
    def execute(
        self,
        source: str,
        filter_expr: Optional[str] = None,
        select: Optional[List[str]] = None,
        limit: int = 100,
        sort_by: Optional[str] = None,
        ascending: bool = True,
        **kwargs
    ) -> ToolResult:
        try:
            results = query_data(source, filter_expr=filter_expr,
                               select=select, limit=limit,
                               sort_by=sort_by, ascending=ascending)
            return ToolResult(
                success=True,
                output=results,
                metadata={"source": source, "result_count": len(results)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
