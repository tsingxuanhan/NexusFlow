# -*- coding: utf-8 -*-
"""
匠人 (Artisan) — 建材领域问答Agent
XuanHub Artisan Agent for Building Materials Q&A
"""

from nexusflow.agents.base_agent import BaseAgent
from nexusflow.memory.vector_memory import get_vector_memory
from typing import List, Dict

# 匠人系统提示词
ARTISAN_SYSTEM_PROMPT = """你是"匠人"，铉枢项目中的建材领域专家。

## 核心职责
为低碳建筑材料研究提供专业知识问答，辅助科研工作。

## 专业领域
- 水泥化学 (Cement Chemistry)
- 水化动力学 (Hydration Kinetics)
- 超硫铁矿渣水泥 (SSC)
- 磷酸镁水泥 (MBCMs)
- 石灰石煅烧粘土水泥 (LC3)
- 纳米改性混凝土
- 混凝土耐久性 (Durability)

## 回答规范
1. **标注来源**: 必须标注信息来源（论文/教科书/标准）
2. **数据诚实**: 无法确认的数据标注"需要查证"，绝不编造
3. **热力学可行**: 配方建议必须符合热力学原理
4. **简洁专业**: 不废话，直接回答

## 来源标注格式
- 📚 教科书/专著: [书名, 作者, 年份]
- 📄 期刊论文: [期刊, 作者, 年份] 或 DOI
- 📋 标准: [标准号, 名称]
- 🌐 网络来源: [URL, 年份]
- ⚠️ 需要查证: 标注为"无明确来源，需要查证"

## 知识边界
- 专注于建筑材料领域
- 不确定时明确说"不确定"或"需要查证"
- 超出领域的问题礼貌拒绝"""



class ArtisanAgent(BaseAgent):
    """匠人 - 建材领域专家"""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="Artisan",
            model="flash",
            system_prompt=ARTISAN_SYSTEM_PROMPT,
            **kwargs
        )
        # ============ 新增: 向量记忆支持 ============
        self.memory = get_vector_memory()
        
        # ============ 新增: A2A能力注册 ============
        if self.a2a:
            # 注册action映射
            self.register_a2a_action("ask", self.ask)
            self.register_a2a_action("explain_concept", self.explain_concept)
            self.register_a2a_action("suggest_formula", self.suggest_formula)
            self.register_a2a_action("analyze_property", self.analyze_property)
            
            # 注册能力
            self.register_a2a_capability(
                name="ask",
                description="专业问答",
                keywords=["问题", "question", "问", "答"]
            )
            self.register_a2a_capability(
                name="explain_concept",
                description="解释专业概念",
                keywords=["概念", "concept", "解释"]
            )
            self.register_a2a_capability(
                name="suggest_formula",
                description="材料配方建议",
                keywords=["配方", "formula", "配比"]
            )
    
    def ask(self, question: str, context: str = None) -> str:
        """专业问答
        
        Args:
            question: 问题
            context: 上下文（可选）
            
        Returns:
            回答
        """
        # 获取相关问答记忆
        memory_context = self.memory.get_context_for_llm(question, max_tokens=500)
        memory_section = f"\n\n## 相关问答历史\n{memory_context}" if memory_context else ""
        
        context_section = f"\n\n## 背景上下文\n{context}" if context else ""
        
        prompt = f"""{context_section}{memory_section}

## 问题
{question}

请用简洁专业的语言回答，标注信息来源。"""
        
        result = self.chat(prompt)
        
        # 保存问答记忆
        self.memory.add(f"Q:{question} A:{result[:200]}", importance=0.7)
        
        return result
    
    def explain_concept(self, concept: str, level: str = "intermediate") -> str:
        """解释专业概念
        
        Args:
            concept: 概念名称
            level: 解释深度 (basic/intermediate/advanced)
            
        Returns:
            概念解释
        """
        level_instruction = {
            "basic": "用通俗易懂的语言解释，适合初学者",
            "intermediate": "平衡专业性和可理解性",
            "advanced": "深入技术细节，适合研究人员"
        }.get(level, "中等深度")
        
        prompt = f"""请解释 "{concept}" 这个概念。

解释要求：{level_instruction}

请包含：
1. 基本定义
2. 核心原理
3. 应用场景
4. 相关的重要参数或指标
5. 与其他概念的联系（如果有）

格式：Markdown，包含层级结构"""
        
        return self.chat(prompt)
    
    def suggest_formula(self, material_type: str, target_property: str = None) -> str:
        """配方建议
        
        Args:
            material_type: 材料类型 (SSC/LC3/MBCMs等)
            target_property: 目标性能（可选）
            
        Returns:
            配方建议
        """
        property_section = f"\n目标性能: {target_property}" if target_property else ""
        
        prompt = f"""请为 {material_type} 提供配方建议。{property_section}

建议要求：
1. 符合热力学可行性
2. 考虑工程实用性
3. 标注各组分的大致比例范围
4. 指出关键控制参数
5. 说明性能预期

⚠️ 注意：以下信息必须标注来源，无法确认的标注"需要查证" """
        
        return self.chat(prompt)
    
    def analyze_property(self, property_name: str, material: str = None) -> str:
        """分析材料性能
        
        Args:
            property_name: 性能名称（抗压强度、耐碱性等）
            material: 材料（可选，指定则分析特定材料）
            
        Returns:
            性能分析
        """
        material_section = f"，特别是 {material}" if material else ""
        
        prompt = f"""请分析{property_name}这一性能指标{material_section}。

请涵盖：
1. 定义与测试方法
2. 影响因素
3. 典型数值范围
4. 改善方法（如果适用）
5. 相关标准

请标注信息来源。"""
        
        return self.chat(prompt)
    
    def compare_materials(self, material1: str, material2: str, aspects: List[str] = None) -> str:
        """对比两种材料
        
        Args:
            material1: 材料1
            material2: 材料2
            aspects: 对比维度（可选）
            
        Returns:
            对比分析
        """
        aspects_text = "\n".join([f"- {a}" for a in aspects]) if aspects else "综合对比"
        
        prompt = f"""请对比 {material1} 和 {material2}。

对比维度：
{aspects_text}

请输出：
1. 简要对比表格
2. 详细分析（每个维度）
3. 各自的优势与局限
4. 应用场景建议"""
        
        return self.chat(prompt)
    
    def explain_standard(self, standard_code: str) -> str:
        """解释标准规范
        
        Args:
            standard_code: 标准号
            
        Returns:
            标准解读
        """
        prompt = f"""请解读标准 {standard_code}。

请涵盖：
1. 标准基本信息（名称、发布时间、适用范围）
2. 核心要求
3. 测试方法要点
4. 重要参数限值
5. 与相关标准的关系

请标注标准的官方来源。"""
        
        return self.chat(prompt)
