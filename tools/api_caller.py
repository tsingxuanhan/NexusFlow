# -*- coding: utf-8 -*-
"""
铉枢·炉守 HTTP API调用工具
XuanHub API Caller Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 http_get/http_post()
"""

import json
import logging
from typing import Any, Dict, Optional
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("APICaller")


# ============ CodeAct全局函数 ============

def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    HTTP GET请求 — CodeAct全局函数
    
    Args:
        url: 请求URL
        headers: 请求头
        params: 查询参数
        timeout: 超时秒数
    
    Returns:
        {"status": 200, "data": ..., "headers": ...}
    
    CodeAct用法:
        resp = http_get("https://api.example.com/papers",
                       params={"query": "SSC cement", "limit": 5})
        papers = resp["data"]
    """
    try:
        import requests
        
        logger.info(f"[APICaller] GET {url}")
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        
        # 尝试解析JSON
        try:
            data = resp.json()
        except Exception:
            data = resp.text[:5000]  # 非JSON截断
        
        return {
            "status": resp.status_code,
            "data": data,
            "headers": dict(resp.headers),
        }
    except Exception as e:
        logger.error(f"[APICaller] GET error: {e}")
        return {"status": 0, "error": str(e)}


def http_post(
    url: str,
    json_data: Optional[Dict] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    HTTP POST请求 — CodeAct全局函数
    
    Args:
        url: 请求URL
        json_data: JSON请求体
        headers: 请求头
        timeout: 超时秒数
    
    Returns:
        {"status": 200, "data": ..., "headers": ...}
    
    CodeAct用法:
        resp = http_post("https://api.example.com/analyze",
                        json_data={"text": "SSC cement properties"})
        result = resp["data"]
    """
    try:
        import requests
        
        logger.info(f"[APICaller] POST {url}")
        resp = requests.post(url, json=json_data, headers=headers, timeout=timeout)
        
        try:
            data = resp.json()
        except Exception:
            data = resp.text[:5000]
        
        return {
            "status": resp.status_code,
            "data": data,
            "headers": dict(resp.headers),
        }
    except Exception as e:
        logger.error(f"[APICaller] POST error: {e}")
        return {"status": 0, "error": str(e)}


# ============ BaseTool兼容 ============

class APICallerTool(BaseTool):
    """HTTP API调用工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="api_caller",
            description="Make HTTP GET or POST requests to external APIs.",
            parameters={
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "description": "HTTP method",
                        "default": "GET"
                    },
                    "url": {
                        "type": "string",
                        "description": "Request URL"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Request headers"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters (GET only)"
                    },
                    "json_data": {
                        "type": "object",
                        "description": "JSON body (POST only)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 30
                    }
                },
                "required": ["method", "url"]
            }
        )
    
    def execute(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict] = None,
        timeout: int = 30,
        **kwargs
    ) -> ToolResult:
        try:
            if method.upper() == "GET":
                result = http_get(url, headers=headers, params=params, timeout=timeout)
            elif method.upper() == "POST":
                result = http_post(url, json_data=json_data, headers=headers, timeout=timeout)
            else:
                return ToolResult(success=False, error=f"Unsupported method: {method}")
            
            success = 200 <= result.get("status", 0) < 300
            return ToolResult(
                success=success,
                output=result.get("data"),
                error=result.get("error"),
                metadata={"status": result.get("status"), "url": url}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
