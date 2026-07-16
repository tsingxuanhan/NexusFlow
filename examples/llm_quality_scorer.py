# -*- coding: utf-8 -*-
"""
LLM Quality Scorer for Ablation Experiments
============================================
使用 DeepSeek 对 CDoL 输出进行多维度质量评分，替代 hardcoded 公式。

评分维度（5维）：
1. Completeness (完整性): 是否覆盖任务要求的所有方面
2. Depth (深度): 推理链的深度，是否有层次递进
3. Consistency (一致性): 结论内部是否自洽，有无矛盾
4. Novelty (创新性): 是否有超越常识的独到见解
5. Actionability (可操作性): 结论是否具体可执行

输出：每维度 0-10 分，加权合成 0-1 总分
"""

import json
import logging
import urllib.request
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger("LLMQualityScorer")

# ============================================================
# 配置
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

# 评分维度权重（可根据实验需求调整）
DIMENSION_WEIGHTS = {
    "completeness": 0.25,
    "depth": 0.25,
    "consistency": 0.20,
    "novelty": 0.15,
    "actionability": 0.15,
}

# ============================================================
# 评分 Prompt
# ============================================================
SCORER_SYSTEM_PROMPT = """你是一个严格的学术评审专家，负责对AI系统生成的分析结果进行质量评分。
你必须只输出JSON格式，不要输出任何其他内容。

评分维度（每个0-10分，整数）：
1. completeness: 是否覆盖任务要求的所有方面？10=完全覆盖所有要点，0=严重遗漏
2. depth: 推理链的深度如何？10=多层递进、有因果链条，0=只有表面描述
3. consistency: 结论是否内部自洽？10=完全无矛盾、逻辑严密，0=自相矛盾
4. novelty: 是否有独到见解？10=有超越常识的原创洞察，0=全是陈词滥调
5. actionability: 结论是否可操作？10=具体可执行、有明确步骤，0=空泛无物

=== 评分锚定示例（参考这些标杆校准你的评分） ===

【8-9分标杆】：
- completeness: 8 — 覆盖了任务要求的所有4个维度，每个维度有3+具体论据
- depth: 8 — 呈现"数据→模式→原因→影响"多层因果链，不是单层罗列
- consistency: 9 — 结论间有明确逻辑关联，前因后果自洽
- novelty: 8 — 提出了"参数规模边际递减+MoE效率拐点"等超越常识的洞察
- actionability: 7 — 给出了具体时间节点和布局建议

【5-6分标杆】：
- completeness: 6 — 覆盖了主要维度但某个方面较薄（如只提了2个维度）
- depth: 5 — 有分析但停留在现象描述层，缺少深层原因
- consistency: 6 — 基本自洽但有个别跳跃
- novelty: 5 — 观点较常规，多为业界共识
- actionability: 5 — 有方向但缺乏具体步骤

【2-3分标杆】：
- completeness: 3 — 只回答了任务的一小部分
- depth: 2 — 纯表面描述，没有分析
- consistency: 3 — 前后有矛盾
- novelty: 2 — 完全是陈词滥调
- actionability: 2 — 空泛无物

注意：
- 评分要严格，大部分AI输出的综合分在4-7分区间。
- 根据内容本身的质量判断，不要因为"还行"就给高分。
- 只输出JSON，格式如下：
{
  "completeness": 7,
  "depth": 6,
  "consistency": 8,
  "novelty": 5,
  "actionability": 6,
  "brief_reason": "一句话说明评分理由"
}"""


def _call_scorer(prompt: str) -> str:
    """调用 DeepSeek 评分（独立于 demo_full_system 的 deepseek_chat，避免循环依赖）"""
    messages = [
        {"role": "system", "content": SCORER_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    payload = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.1,  # 低温度，评分一致性更高
    }).encode("utf-8")

    req = urllib.request.Request(
        DEEPSEEK_URL, data=payload,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Scorer API error: {e}")
        return ""


def _parse_scores(raw: str) -> Optional[Dict[str, int]]:
    """从 LLM 返回中提取 JSON 评分"""
    if not raw:
        return None
    # 尝试直接解析
    try:
        data = json.loads(raw)
        return data
    except json.JSONDecodeError:
        pass
    # 尝试从 markdown code block 中提取
    for start_marker in ["```json", "```"]:
        if start_marker in raw:
            start = raw.index(start_marker) + len(start_marker)
            end = raw.find("```", start)
            if end > start:
                try:
                    return json.loads(raw[start:end].strip())
                except json.JSONDecodeError:
                    pass
    # 尝试找到第一个 { 和最后一个 }
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return None


def score_output(
    task_description: str,
    output_text: str,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    对单次实验输出进行 LLM 质量评分。
    
    Args:
        task_description: 原始任务描述（评分的参照标准）
        output_text: 系统生成的输出文本
        weights: 维度权重，默认使用 DIMENSION_WEIGHTS
    
    Returns:
        {
            "scores": {"completeness": 7, "depth": 6, ...},
            "composite": 0.65,  # 加权合成 0-1
            "reason": "评分理由",
            "raw_response": "LLM原始返回"
        }
    """
    if not output_text or len(output_text.strip()) < 20:
        logger.warning("Output too short to score, returning default")
        return {
            "scores": {k: 5 for k in DIMENSION_WEIGHTS},
            "composite": 0.5,
            "reason": "输出过短，无法评分",
            "raw_response": "",
        }
    
    w = weights or DIMENSION_WEIGHTS
    
    # 截断过长输出（评分不需要全文，保留头尾）
    truncated = output_text
    if len(output_text) > 3000:
        truncated = output_text[:2000] + "\n...\n" + output_text[-1000:]
    
    prompt = f"""请对以下AI系统的输出进行质量评分。

## 任务要求
{task_description}

## 系统输出
{truncated}

请严格按JSON格式输出5个维度的评分（0-10整数）。"""

    raw_response = _call_scorer(prompt)
    scores = _parse_scores(raw_response)
    
    if scores is None:
        logger.warning(f"Failed to parse scorer response: {raw_response[:200]}")
        return {
            "scores": {k: 5 for k in DIMENSION_WEIGHTS},
            "composite": 0.5,
            "reason": "评分解析失败",
            "raw_response": raw_response,
        }
    
    # 验证并夹紧分数
    valid_scores = {}
    for dim in DIMENSION_WEIGHTS:
        val = scores.get(dim, 5)
        if isinstance(val, (int, float)):
            valid_scores[dim] = max(0, min(10, int(val)))
        else:
            valid_scores[dim] = 5
    
    # 加权合成（0-1）
    composite = sum(
        valid_scores[dim] * w.get(dim, 0.0) for dim in DIMENSION_WEIGHTS
    ) / 10.0
    
    return {
        "scores": valid_scores,
        "composite": round(composite, 3),
        "reason": scores.get("brief_reason", ""),
        "raw_response": raw_response,
    }


def score_batch(
    task_description: str,
    outputs: List[str],
    weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """批量评分多个输出（用于同一任务的不同实验条件对比）"""
    results = []
    for i, output in enumerate(outputs):
        logger.info(f"Scoring output {i+1}/{len(outputs)}...")
        result = score_output(task_description, output, weights)
        results.append(result)
    return results
