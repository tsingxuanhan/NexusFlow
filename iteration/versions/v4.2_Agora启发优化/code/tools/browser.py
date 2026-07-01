# -*- coding: utf-8 -*-
"""
铉枢·炉守 浏览器自动化工具
XuanHub Browser Control Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 browse()
对接agent-browser skill或Playwright
"""

import logging
from typing import Any, Dict, Optional
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("BrowserControl")


def browse(url: str, action: str = "visit", selector: str = "", text: str = "", 
           wait: int = 3, screenshot: bool = False) -> Dict[str, Any]:
    """
    浏览器自动化操作 — CodeAct全局函数
    
    Args:
        url: 目标URL
        action: 操作类型 (visit/click/type/scroll/screenshot/extract)
        selector: CSS选择器(click/type时)
        text: 输入文本(type时)
        wait: 等待秒数
        screenshot: 是否截图
    
    Returns:
        {"success": bool, "content": str, "url": str}
    
    CodeAct用法:
        result = browse("https://example.com")
        result = browse("https://example.com", action="click", selector="#search-btn")
        result = browse("https://example.com", action="type", selector="#search", text="SSC cement")
    """
    try:
        import requests
        
        # 简单模式：用requests获取页面内容
        if action == "visit":
            resp = requests.get(url, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (XuanHub Agent)"
            })
            # 简单提取文本
            content = resp.text[:20000]
            return {
                "success": True,
                "content": content,
                "url": url,
                "status": resp.status_code,
            }
        
        elif action == "extract":
            resp = requests.get(url, timeout=15)
            # 简单提取：去HTML标签
            import re
            text = re.sub(r'<[^>]+>', ' ', resp.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return {
                "success": True,
                "content": text[:10000],
                "url": url,
            }
        
        else:
            # 复杂操作需要Playwright/MCP浏览器
            return {
                "success": False,
                "content": f"Action '{action}' requires Playwright/MCP browser. Simple mode only supports visit/extract.",
                "url": url,
            }
    
    except Exception as e:
        logger.error(f"[BrowserControl] Error: {e}")
        return {"success": False, "content": "", "url": url, "error": str(e)}


class BrowserControlTool(BaseTool):
    """浏览器自动化工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="browser_control",
            description="Control a web browser: visit URLs, click elements, type text, extract content. Simple mode uses requests; advanced mode requires Playwright.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Target URL"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["visit", "click", "type", "scroll", "screenshot", "extract"],
                        "description": "Browser action",
                        "default": "visit"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for click/type actions"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    },
                    "wait": {
                        "type": "integer",
                        "description": "Wait time in seconds",
                        "default": 3
                    }
                },
                "required": ["url"]
            }
        )
    
    def execute(self, url: str, action: str = "visit", selector: str = "",
                text: str = "", wait: int = 3, **kwargs) -> ToolResult:
        result = browse(url, action=action, selector=selector, text=text, wait=wait)
        return ToolResult(
            success=result.get("success", False),
            output=result.get("content", ""),
            error=result.get("error"),
            metadata={"url": url, "action": action}
        )
