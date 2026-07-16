# -*- coding: utf-8 -*-
"""
矿工 (Miner) — 文献深度挖掘Agent
XuanHub Miner Agent for Literature Mining
"""

from nexusflow.agents.base_agent import BaseAgent
from nexusflow.memory.vector_memory import get_vector_memory

# 矿工系统提示词
MINER_SYSTEM_PROMPT = """你是"矿工"，铉枢项目中的文献挖掘专家。

## 核心职责
专注于低碳建筑材料领域的学术论文检索与深度挖掘，提取结构化知识。

## 专业领域
- SSC (Supersulfated Cements，超硫铁矿渣水泥)
- MBCMs (Magnesium Phosphate Cement-based Materials，磷酸镁水泥基材料)
- LC3 (Limestone Calcined Clay Cement，石灰石煅烧粘土水泥)
- 纳米改性混凝土
- 混凝土耐久性

## 输出规范
每篇论文必须提取以下字段：
1. 标题 (Title)
2. 作者 (Authors)
3. 期刊/会议 (Journal/Conference)
4. 年份 (Year)
5. DOI/URL
6. 核心发现 (Key Findings)
7. 研究方法 (Methods)
8. 关键数据 (Key Data)
9. 验证状态: ✅已验证 或 ⚠️待验证

## 格式要求
- 主要使用Markdown表格展示论文列表
- 每个条目用结构化文本详细说明
- 不确定的信息必须标注⚠️
- 绝对不编造论文，找不到就明确说找不到
- 提供可追溯的来源链接

## 回答风格
- 学术严谨，数据准确
- 表格简洁，重点突出
- 附带简短的分析总结"""



class MinerAgent(BaseAgent):
    """矿工 - 文献挖掘专家"""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="Miner",
            model="pro",
            system_prompt=MINER_SYSTEM_PROMPT,
            **kwargs
        )
        # ============ 新增: 向量记忆支持 ============
        self.memory = get_vector_memory()
        
        # ============ 新增: A2A能力注册 ============
        if self.a2a:
            # 注册action映射
            self.register_a2a_action("search_papers", self.search_papers)
            self.register_a2a_action("extract_paper", self.extract_paper)
            self.register_a2a_action("compare_papers", self.compare_papers)
            self.register_a2a_action("summarize_field", self.summarize_field)
            
            # 注册能力
            self.register_a2a_capability(
                name="search_papers",
                description="搜索学术论文",
                keywords=["论文", "研究", "paper", "search", "检索"]
            )
            self.register_a2a_capability(
                name="extract_paper",
                description="从论文文本提取结构化信息",
                keywords=["提取", "extract", "分析"]
            )
            self.register_a2a_capability(
                name="summarize_field",
                description="总结研究领域",
                keywords=["综述", "总结", "领域", "survey"]
            )
    
    def search_papers(self, keywords: str, max_results: int = 10) -> str:
        """搜索论文
        
        Args:
            keywords: 搜索关键词
            max_results: 最大结果数
            
        Returns:
            结构化的论文列表
        """
        # 获取相关记忆上下文
        context = self.memory.get_context_for_llm(keywords, max_tokens=500)
        context_section = f"\n\n## 相关历史搜索记录\n{context}" if context else ""
        
        prompt = f"""请帮我检索关于 "{keywords}" 的最新学术论文。

要求：
1. 优先检索近5年的高质量论文（SCI期刊优先）
2. 每篇论文提取完整信息（标题、作者、期刊、年份、DOI）
3. 简要说明每篇论文的核心贡献
4. 返回格式：Markdown表格 + 详细说明
5. 最多返回 {max_results} 篇
{context_section}

如果没有找到相关论文，请明确告知。"""
        
        result = self.chat(prompt)
        
        # 保存搜索记忆
        self.memory.add(f"Q:{keywords} A:{result[:200]}", importance=0.6)
        
        return result
    
    def extract_paper(self, paper_text: str) -> str:
        """从论文文本中提取结构化信息
        
        Args:
            paper_text: 论文的文本内容（摘要或全文）
            
        Returns:
            结构化的论文信息
        """
        prompt = f"""请从以下论文内容中提取结构化信息：

---
{paper_text}
---

请提取：
1. 标题、作者、期刊、年份
2. 研究目的与背景
3. 核心发现（用bullet points）
4. 研究方法
5. 关键数据（性能指标、化学成分配比等）
6. 创新点

格式：Markdown表格 + 详细文本说明"""
        
        return self.chat(prompt)
    
    def compare_papers(self, topic: str, papers: list) -> str:
        """对比多篇论文
        
        Args:
            topic: 对比主题
            papers: 论文列表（可以是标题列表或摘要）
            
        Returns:
            对比分析报告
        """
        papers_text = "\n\n".join([f"[{i+1}] {p}" for i, p in enumerate(papers)])
        
        prompt = f"""请对比分析以下关于 "{topic}" 的论文：

{papers_text}

请从以下维度进行对比：
1. 研究方法的异同
2. 关键结论的异同
3. 数据与性能指标的对比
4. 各自的局限性
5. 综合评价与推荐

输出格式：
- 对比表格
- 详细分析
- 总结与建议"""
        
        return self.chat(prompt)
    
    def summarize_field(self, field_name: str) -> str:
        """总结某个研究领域
        
        Args:
            field_name: 研究领域名称
            
        Returns:
            领域综述报告
        """
        prompt = f"""请为我撰写关于 "{field_name}" 的研究综述。

要求：
1. 概述该领域的研究现状与发展历程
2. 主要研究方向与代表成果
3. 关键技术路线与核心问题
4. 未来发展趋势与挑战
5. 推荐阅读的经典论文（5-10篇）

请用Markdown格式输出，包含适当的层级结构。"""
        
        return self.chat(prompt)
    
    def extract_knowledge_from_pdf(self, pdf_path: str) -> str:
        """从PDF提取知识（需要先读取PDF内容）
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            提取的结构化知识
        """
        # 先加载PDF内容
        content = self.load_knowledge(pdf_path)
        
        if not content:
            return f"⚠️ 无法加载PDF文件: {pdf_path}"
        
        return self.extract_paper(content)
