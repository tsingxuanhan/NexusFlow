# -*- coding: utf-8 -*-
"""
试金 (Assayer) — 知识交叉验证Agent
XuanHub Assayer Agent for Knowledge Verification
"""

from base_agent import BaseAgent
from typing import List, Dict

# 试金系统提示词
ASSAYER_SYSTEM_PROMPT = """你是"试金"，铉枢项目中的知识验证专家。

## 核心职责
对知识库中的条目进行多角度交叉验证，确保信息准确性，标记冲突与不确定性。

## 专业领域知识
- 低碳建筑材料（SSC/MBCMs/LC3/纳米改性混凝土）
- 水泥化学与水化动力学
- 混凝土耐久性评估
- 材料表征方法

## 验证原则
1. **多源验证**: 每个知识点从至少2个角度验证
2. **宁可标⚠️不可标错✅**: 不确定时必须标记警告
3. **可追溯**: 标注信息来源与验证依据
4. **不妥协**: 发现冲突必须明确指出

## 输出格式
验证报告必须包含：
1. 条目ID/名称
2. 验证结果: ✅通过 / ⚠️存疑 / ❌冲突
3. 验证依据 (来源1、来源2...)
4. 冲突说明 (如有)
5. 建议处理方式

## 冲突处理
- 发现冲突时，列出所有来源及各自说法
- 不强求统一，允许标注"有争议"
- 提供最佳实践建议"""



class AssayerAgent(BaseAgent):
    """试金 - 知识验证专家"""
    
    def __init__(self, **kwargs):
        super().__init__(
            name="Assayer",
            model="flash",
            system_prompt=ASSAYER_SYSTEM_PROMPT,
            **kwargs
        )
    
    def verify_entry(self, entry: str, entry_id: str = "N/A") -> str:
        """验证单个知识条目
        
        Args:
            entry: 要验证的知识条目内容
            entry_id: 条目ID
            
        Returns:
            验证报告
        """
        prompt = f"""请验证以下知识条目的准确性：

**条目ID**: {entry_id}
**待验证内容**: {entry}

验证要求：
1. 从多个角度进行交叉验证（至少2个角度）
2. 检查数据是否合理（数值范围、单位、逻辑关系）
3. 与领域知识进行对比
4. 标注不确定或可能有误的部分

输出格式：
```
## 验证报告

### 验证结果: ✅/⚠️/❌

### 验证依据
- 角度1: [分析]
- 角度2: [分析]

### 发现的问题 (如有)
- [问题描述]

### 建议处理
[建议]
```"""
        
        return self.chat(prompt)
    
    def batch_verify(self, entries: List[Dict], report_id: str = "batch001") -> str:
        """批量验证知识条目
        
        Args:
            entries: 知识条目列表 [{"id": "...", "content": "..."}, ...]
            report_id: 报告ID
            
        Returns:
            批量验证报告
        """
        entries_text = "\n".join([
            f"{i+1}. **[{e.get('id', f'ID-{i}')}]** {e.get('content', '')}"
            for i, e in enumerate(entries)
        ])
        
        prompt = f"""请批量验证以下知识条目：

---
{entries_text}
---

验证要求：
1. 对每个条目进行快速验证
2. 从多个角度交叉验证
3. 发现问题立即标注
4. 批量输出验证结果表

输出格式：
1. Markdown表格（ID / 验证结果 / 问题摘要）
2. 详细问题说明（仅有问题的条目）
3. 整体质量评估"""
        
        return self.chat(prompt)
    
    def check_consistency(self, statements: List[str], topic: str) -> str:
        """检查一组陈述的一致性
        
        Args:
            statements: 陈述列表
            topic: 主题
            
        Returns:
            一致性检查报告
        """
        stmts_text = "\n".join([f"- {s}" for s in statements])
        
        prompt = f"""请检查以下关于 "{topic}" 的陈述是否相互一致：

{stmts_text}

检查维度：
1. 数值一致性（数据是否矛盾）
2. 逻辑一致性（推理是否矛盾）
3. 结论一致性（观点是否矛盾）
4. 上下文一致性（前提假设是否一致）

输出格式：
- 一致性矩阵
- 发现的不一致之处
- 可能的解释
- 建议的统一表述"""
        
        return self.chat(prompt)
    
    def verify_claim(self, claim: str, expected_range: str = None) -> str:
        """验证某个具体说法或数值
        
        Args:
            claim: 要验证的说法
            expected_range: 预期合理范围（可选）
            
        Returns:
            验证结果
        """
        range_info = f"\n预期合理范围: {expected_range}" if expected_range else ""
        
        prompt = f"""请验证以下说法的准确性：

**待验证说法**: {claim}
{range_info}

验证要点：
1. 数据是否在合理范围内
2. 是否有文献支持
3. 是否与公认事实一致
4. 单位是否正确

输出：简短验证结果 + 依据"""
        
        return self.chat(prompt)
    
    def verify_composition(self, material: str, composition: str) -> str:
        """验证材料配方的合理性
        
        Args:
            material: 材料名称
            composition: 配方描述
            
        Returns:
            配方验证报告
        """
        prompt = f"""请验证以下材料配方的合理性：

**材料**: {material}
**配方**: {composition}

验证维度：
1. 热力学可行性（各组分是否能反应）
2. 配比合理性（各组分比例是否合理）
3. 工程可行性（是否可制备、可施工）
4. 性能预期（是否符合该类材料的典型性能）

输出格式：
- ✅合理的部分
- ⚠️需要注意的部分
- ❌不合理或错误的部分
- 改进建议"""
        
        return self.chat(prompt)
