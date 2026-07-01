# -*- coding: utf-8 -*-
"""
铉枢·炉守 PDF读取工具
XuanHub PDF Reader Tool — Phase 3

双重接口: BaseTool JSON调用 + CodeAct全局函数 read_pdf()
支持文本提取和简单表格识别
"""

import os
import logging
from typing import Any, Dict, List, Optional
from .base_tool import BaseTool, ToolResult

logger = logging.getLogger("PDFReader")


def read_pdf(path: str, max_pages: int = 50, extract_tables: bool = False) -> Dict[str, Any]:
    """
    读取PDF文件 — CodeAct全局函数
    
    Args:
        path: PDF文件路径
        max_pages: 最大读取页数
        extract_tables: 是否提取表格
    
    Returns:
        {"pages": int, "text": str, "tables": [...]}
    
    CodeAct用法:
        result = read_pdf("knowledge/papers/review.pdf")
        print(f"Pages: {result['pages']}")
        print(result['text'][:500])
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"PDF not found: {path}")
    
    text_content = []
    tables = []
    page_count = 0
    
    # 尝试PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        page_count = len(reader.pages)
        
        for i, page in enumerate(reader.pages[:max_pages]):
            text = page.extract_text()
            if text:
                text_content.append(f"--- Page {i+1} ---\n{text}")
        
        logger.info(f"[PDFReader] PyPDF2: {page_count} pages from {path}")
    
    except ImportError:
        # 尝试pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                page_count = len(pdf.pages)
                for i, page in enumerate(pdf.pages[:max_pages]):
                    text = page.extract_text()
                    if text:
                        text_content.append(f"--- Page {i+1} ---\n{text}")
                    
                    if extract_tables:
                        page_tables = page.extract_tables()
                        if page_tables:
                            tables.extend(page_tables)
            
            logger.info(f"[PDFReader] pdfplumber: {page_count} pages from {path}")
        
        except ImportError:
            # 最后兜底：用pdftotext命令
            import subprocess
            try:
                result = subprocess.run(
                    ["pdftotext", path, "-"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    text_content.append(result.stdout)
                    page_count = -1  # 未知页数
                else:
                    raise RuntimeError("No PDF library available (PyPDF2, pdfplumber, pdftotext)")
            except FileNotFoundError:
                raise RuntimeError("No PDF library available. Install PyPDF2: pip install PyPDF2")
    
    return {
        "pages": page_count,
        "text": "\n\n".join(text_content)[:50000],  # 截断超长文本
        "tables": tables,
    }


class PDFReaderTool(BaseTool):
    """PDF读取工具 — BaseTool JSON兼容"""
    
    def __init__(self):
        super().__init__(
            name="pdf_reader",
            description="Extract text and tables from PDF files. Supports PyPDF2, pdfplumber, and pdftotext.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the PDF file"
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Maximum pages to read",
                        "default": 50
                    },
                    "extract_tables": {
                        "type": "boolean",
                        "description": "Whether to extract tables",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        )
    
    def execute(self, path: str, max_pages: int = 50, extract_tables: bool = False, **kwargs) -> ToolResult:
        try:
            result = read_pdf(path, max_pages=max_pages, extract_tables=extract_tables)
            return ToolResult(
                success=True,
                output=result,
                metadata={"path": path, "pages": result["pages"]}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
