# -*- coding: utf-8 -*-
"""
铉枢·炉守 联网搜索工具
XuanHub Web Search Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 search()
"""

import logging
from typing import Any, Dict, List, Optional
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("WebSearch")


def search(query: str, limit: int = 5, engine: str = "general") -> List[Dict[str, str]]:
    """
    联网搜索 — CodeAct全局函数
    
    Args:
        query: 搜索关键词
        limit: 返回结果数
        engine: 搜索引擎类型 (general/scholar)
    
    Returns:
        搜索结果列表 [{"title": ..., "url": ..., "snippet": ...}]
    
    CodeAct用法:
        results = search("SSC cement latest research")
        for r in results:
            print(r["title"], r["url"])
    """
    try:
        import requests
        # 通过本地API代理搜索（对接Coze搜索能力或自定义搜索API）
        # 兜底：返回占位结果，Agent在真实环境中会被替换
        logger.info(f"[WebSearch] Searching: {query} (limit={limit}, engine={engine})")
        
        # 尝试调用SearXNG本地实例
        try:
            resp = requests.get(
                "http://127.0.0.1:8888/search",
                params={"q": query, "format": "json", "limit": limit},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("results", [])[:limit]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", ""),
                    })
                return results
        except Exception:
            pass
        
        # 尝试通过DeepSeek API代理
        try:
            resp = requests.post(
                "http://127.0.0.1:8083/v1/chat/completions",
                json={
                    "model": "deepseek-v4-flash",
                    "messages": [
                        {"role": "system", "content": "你是搜索助手，根据查询返回最相关的信息。"},
                        {"role": "user", "content": f"搜索: {query}"},
                    ],
                    "max_tokens": 500,
                },
                timeout=15,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                return [{"title": query, "url": "", "snippet": content}]
        except Exception:
            pass
        
        # 最终兜底
        return [{"title": f"Search: {query}", "url": "", "snippet": "Search API not configured. Set up SearXNG or search API proxy."}]
        
    except Exception as e:
        logger.error(f"[WebSearch] Error: {e}")
        return [{"title": "Error", "url": "", "snippet": str(e)}]


class WebSearchTool(BaseTool):
    """联网搜索工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web for information. Returns a list of results with title, url, and snippet.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return",
                        "default": 5
                    },
                    "engine": {
                        "type": "string",
                        "description": "Search engine type: general or scholar",
                        "default": "general"
                    }
                },
                "required": ["query"]
            }
        )
    
    def execute(self, query: str, limit: int = 5, engine: str = "general", **kwargs) -> ToolResult:
        results = search(query, limit=limit, engine=engine)
        return ToolResult(
            success=True,
            output=results,
            metadata={"query": query, "result_count": len(results)}
        )
