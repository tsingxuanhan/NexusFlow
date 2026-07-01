"""
100步科研任务场景定义模块

定义新型低碳水泥配方研发的完整100步任务分解，
包含5大阶段、关键决策点标记、阶段信息等。
"""

import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum


class Phase(Enum):
    """任务阶段枚举"""
    PHASE1_LITERATURE = "Phase 1: 文献调研与可行性分析"
    PHASE2_MECHANISM = "Phase 2: 机理研究与假设生成"
    PHASE3_EXPERIMENT = "Phase 3: 实验设计与数据采集"
    PHASE4_ANALYSIS = "Phase 4: 数据分析与配方优化"
    PHASE5_VALIDATION = "Phase 5: 验证与工程化落地"


@dataclass
class DecisionPoint:
    """关键决策点定义"""
    id: str                    # 决策点ID (D1, D2, D3...)
    step: int                  # 步数位置
    name: str                  # 决策点名称
    description: str           # 决策点描述
    agents: List[str]          # 参与的Agent
    importance: str            # 重要性: 高/中/极高
    context_summary: str       # 当前上下文摘要
    
    def __repr__(self):
        return f"D{self.id}(S{self.step}): {self.name}"


@dataclass
class TaskStep:
    """单步任务定义"""
    step_num: int              # 步数编号 (1-100)
    name: str                  # 步骤名称
    description: str           # 详细描述
    phase: Phase               # 所属阶段
    is_decision_point: bool    # 是否为决策点
    decision_id: Optional[str] = None  # 决策点ID (如果是决策点)
    cognitive_value: str = ""  # 认知分工价值
    
    def get_phase_name(self) -> str:
        """获取阶段简称"""
        phase_map = {
            Phase.PHASE1_LITERATURE: "P1-文献",
            Phase.PHASE2_MECHANISM: "P2-机理",
            Phase.PHASE3_EXPERIMENT: "P3-实验",
            Phase.PHASE4_ANALYSIS: "P4-分析",
            Phase.PHASE5_VALIDATION: "P5-验证",
        }
        return phase_map.get(self.phase, "Unknown")
    
    def get_step_tag(self) -> str:
        """获取步骤标签"""
        if self.is_decision_point:
            return f"🔴 {self.decision_id}"
        return f"S{self.step_num}"


class TaskScenario100Steps:
    """
    100步科研任务场景配置
    
    任务: 新型低碳水泥配方研发 (纳米偏高岭土NM + 石灰石粉LS 复掺优化)
    总步数: 100步 (5阶段 × 20步)
    关键决策点: 3个 (D1-S15, D2-S66, D3-S75)
    """
    
    def __init__(self):
        self.steps: List[TaskStep] = []
        self.decision_points: Dict[str, DecisionPoint] = {}
        self._build_steps()
        self._build_decision_points()
    
    def _build_steps(self):
        """构建100步任务列表"""
        
        # ========== Phase 1: 文献调研与可行性分析 (Step 1-20) ==========
        phase1 = Phase.PHASE1_LITERATURE
        
        phase1_steps = [
            (1, "检索低碳水泥SCI论文", "检索近10年'low carbon cement'相关SCI论文", ""),
            (2, "检索SCM相关专利", "检索'supplementary cementitious material'相关专利", ""),
            (3, "筛选高被引论文", "筛选IF>5的高被引论文", ""),
            (4, "整理CO2排放基准", "整理OPC基准排放数据(940kg CO2/吨)", ""),
            (5, "分析低碳技术路线", "分析现有低碳水泥技术路线", ""),
            (6, "梳理NM研究进展", "聚焦分析纳米偏高岭土(NM)研究进展", ""),
            (7, "梳理LS研究进展", "聚焦分析石灰石粉(LS)研究进展", ""),
            (8, "对比NM vs LS特性", "对比NM与LS技术特性", "关键对比"),
            (9, "调研NM市场供应", "调研纳米偏高岭土市场价格与供应", ""),
            (10, "调研LS市场供应", "调研石灰石粉市场价格与供应", ""),
            (11, "分析供应链风险", "分析原材料供应链风险", ""),
            (12, "梳理政策导向", "梳理国内水泥行业政策导向", ""),
            (13, "对标国际认证标准", "对标国际低碳水泥认证标准", ""),
            (14, "识别核心技术壁垒", "识别NM+LS复配核心技术壁垒", "关键识别"),
            (15, "确定研发方向", "初步确定NM+LS复掺研发方向", "🔴 决策点D1"),
            (16, "撰写文献综述初稿", "撰写文献综述报告初稿", ""),
            (17, "补充遗漏文献", "补充遗漏文献(被引追踪)", ""),
            (18, "完善文献综述", "完善文献综述报告", ""),
            (19, "内部同行评审", "内部同行评审模拟", ""),
            (20, "输出Phase1结题报告", "输出Phase1结题报告", ""),
        ]
        
        for step_num, name, desc, cog_val in phase1_steps:
            is_dp = cog_val.startswith("🔴")
            dp_id = "D1" if is_dp else None
            self.steps.append(TaskStep(
                step_num=step_num,
                name=name,
                description=desc,
                phase=phase1,
                is_decision_point=is_dp,
                decision_id=dp_id,
                cognitive_value=cog_val
            ))
        
        # ========== Phase 2: 机理研究与假设生成 (Step 21-40) ==========
        phase2 = Phase.PHASE2_MECHANISM
        
        phase2_steps = [
            (21, "研究NM火山灰反应", "研究纳米偏高岭土火山灰反应机理", ""),
            (22, "研究LS碳化硬化", "研究石灰石粉碳化硬化机理", ""),
            (23, "分析NM+LS协同效应", "分析NM+LS复配协同效应可能性", "协同预判"),
            (24, "构建火山灰动力学模型", "构建火山灰反应动力学模型", ""),
            (25, "构建碳化硬化模型", "构建碳化硬化理论模型", ""),
            (26, "建立反应速率常数库", "建立反应速率常数数据库", ""),
            (27, "设计正交实验方案", "设计正交实验方案(因素选择)", ""),
            (28, "确定实验因素水平", "确定实验因素水平(掺量/温度/时间)", ""),
            (29, "计算所需样本量", "计算所需样本量(统计功效分析)", ""),
            (30, "设计实验记录表", "设计实验记录表", ""),
            (31, "撰写H1假设", "撰写假设H1: NM提升强度", ""),
            (32, "撰写H2假设", "撰写假设H2: LS降低成本", ""),
            (33, "撰写H3假设", "撰写假设H3: 复掺产生协同效应", "🔴 决策点D2预备"),
            (34, "设计假设验证路线", "设计假设验证路线图", ""),
            (35, "预判假设失败原因", "预判假设可能失败的原因", ""),
            (36, "准备备选假设", "准备备选假设(H1'/H2'/H3')", ""),
            (37, "撰写Phase2技术报告", "撰写Phase2技术报告", ""),
            (38, "内部技术评审", "内部技术评审", ""),
            (39, "根据评审修订", "根据评审意见修订报告", ""),
            (40, "输出Phase2结题报告", "输出Phase2结题报告", ""),
        ]
        
        for step_num, name, desc, cog_val in phase2_steps:
            is_dp = cog_val.startswith("🔴")
            dp_id = "D2_prep" if is_dp else None
            self.steps.append(TaskStep(
                step_num=step_num,
                name=name,
                description=desc,
                phase=phase2,
                is_decision_point=is_dp,
                decision_id=dp_id,
                cognitive_value=cog_val
            ))
        
        # ========== Phase 3: 实验设计与数据采集 (Step 41-60) ==========
        phase3 = Phase.PHASE3_EXPERIMENT
        
        phase3_steps = [
            (41, "采购NM实验样品", "采购NM实验样品(粒径<5μm)", ""),
            (42, "采购LS实验样品", "采购LS实验样品(CaCO3>90%)", ""),
            (43, "标定基准水泥", "标定基准水泥(PO 42.5)", ""),
            (44, "制定实验SOP", "制定实验操作规程(SOP)", ""),
            (45, "预实验摸索条件", "预实验(3组配方摸索条件)", ""),
            (46, "调整实验参数", "根据预实验调整参数", "数据驱动"),
            (47, "正式实验-单掺NM", "正式实验第1批(单掺NM系列)", ""),
            (48, "正式实验-单掺LS", "正式实验第2批(单掺LS系列)", ""),
            (49, "正式实验-复配", "正式实验第3批(复掺NM+LS系列)", ""),
            (50, "3d强度测试", "3d抗压强度测试", ""),
            (51, "7d强度测试", "7d抗压强度测试", ""),
            (52, "14d强度测试", "14d抗压强度测试", ""),
            (53, "28d强度测试", "28d抗压强度测试", ""),
            (54, "56d强度测试", "56d抗压强度测试(部分样品)", ""),
            (55, "SEM微观分析", "SEM微观结构分析", ""),
            (56, "XRD物相分析", "XRD物相分析", ""),
            (57, "MIP孔结构分析", "MIP孔结构分析", ""),
            (58, "TG-DSC热重分析", "TG-DSC热重分析", ""),
            (59, "数据清洗处理", "数据清洗与异常值处理", "🔴 决策点D2预备"),
            (60, "实验数据汇总", "实验数据汇总与可视化", ""),
        ]
        
        for step_num, name, desc, cog_val in phase3_steps:
            is_dp = cog_val.startswith("🔴")
            dp_id = "D2_prep2" if is_dp else None
            self.steps.append(TaskStep(
                step_num=step_num,
                name=name,
                description=desc,
                phase=phase3,
                is_decision_point=is_dp,
                decision_id=dp_id,
                cognitive_value=cog_val
            ))
        
        # ========== Phase 4: 数据分析与配方优化 (Step 61-80) ==========
        phase4 = Phase.PHASE4_ANALYSIS
        
        phase4_steps = [
            (61, "ANOVA方差分析", "统计分析(ANOVA方差分析)", ""),
            (62, "回归分析建模", "回归分析(建立预测模型)", ""),
            (63, "响应面分析优化", "响应面分析(RSM优化)", ""),
            (64, "敏感性分析", "敏感性分析(因素重要性)", ""),
            (65, "强度预测模型验证", "强度预测模型验证", ""),
            (66, "最优配方初选", "🔴 关键决策: 最优配方初选", "🔴 决策点D2"),
            (67, "经济性分析", "经济性分析(成本核算)", ""),
            (68, "生命周期LCA评估", "生命周期评估(LCA)", ""),
            (69, "综合评价TOPSIS", "综合评价(TOPSIS法)", ""),
            (70, "配方敏感性测试", "配方敏感性测试", ""),
            (71, "小批量试生产", "小批量试生产", ""),
            (72, "试产品性能复测", "试产品性能复测", ""),
            (73, "预测vs实测对比", "对比分析(预测 vs 实测)", ""),
            (74, "模型修正迭代", "模型修正与迭代", ""),
            (75, "配方定型决策", "🔴 关键决策: 配方定型", "🔴 决策点D3"),
            (76, "编写技术说明书", "编写产品技术说明书", ""),
            (77, "撰写专利权利要求", "专利申请文件撰写(权利要求)", ""),
            (78, "撰写专利说明书", "专利申请文件撰写(说明书)", ""),
            (79, "专利布局规划", "查重与专利布局规划", ""),
            (80, "输出Phase4结题报告", "输出Phase4结题报告", ""),
        ]
        
        for step_num, name, desc, cog_val in phase4_steps:
            is_dp = cog_val.startswith("🔴")
            dp_id = None
            if "D2" in cog_val:
                dp_id = "D2"
            elif "D3" in cog_val:
                dp_id = "D3"
            self.steps.append(TaskStep(
                step_num=step_num,
                name=name,
                description=desc,
                phase=phase4,
                is_decision_point=is_dp,
                decision_id=dp_id,
                cognitive_value=cog_val
            ))
        
        # ========== Phase 5: 验证与工程化落地 (Step 81-100) ==========
        phase5 = Phase.PHASE5_VALIDATION
        
        phase5_steps = [
            (81, "中试生产线设计", "中试生产线设计与改造", ""),
            (82, "原材料预处理工艺", "中试原材料预处理工艺", ""),
            (83, "配料系统调试", "中试配料系统调试", ""),
            (84, "中试试生产-1", "中试试生产第1批", ""),
            (85, "中试试生产-2", "中试试生产第2批", ""),
            (86, "中试产品检测", "中试产品性能检测", ""),
            (87, "工程应用示范", "工程应用示范(预拌混凝土)", ""),
            (88, "应用效果追踪", "工程应用效果追踪(3个月)", ""),
            (89, "用户反馈收集", "用户反馈收集与分析", ""),
            (90, "产品质量改进", "产品质量改进迭代", ""),
            (91, "编制企业标准", "标准规范编制(企业标准)", ""),
            (92, "行业专家评审", "标准规范评审(行业专家)", ""),
            (93, "标准报批备案", "标准报批与备案", ""),
            (94, "市场推广方案", "市场推广方案制定", ""),
            (95, "商业计划书撰写", "商业计划书撰写(投资人版)", ""),
            (96, "知识产权完善", "知识产权组合完善", ""),
            (97, "技术秘密保护", "技术秘密保护措施", ""),
            (98, "项目总结报告", "项目总结报告撰写", ""),
            (99, "成果鉴定查新", "成果鉴定与科技查新", ""),
            (100, "结题汇报材料", "项目结题汇报材料制作", ""),
        ]
        
        for step_num, name, desc, cog_val in phase5_steps:
            self.steps.append(TaskStep(
                step_num=step_num,
                name=name,
                description=desc,
                phase=phase5,
                is_decision_point=False,
                decision_id=None,
                cognitive_value=cog_val
            ))
    
    def _build_decision_points(self):
        """构建关键决策点配置"""
        
        self.decision_points = {
            "D1": DecisionPoint(
                id="D1",
                step=15,
                name="研发方向确定",
                description="确定以NM+LS复掺作为主要研发方向",
                agents=["Miner", "Assayer", "Evaluator"],
                importance="高",
                context_summary="已完成文献调研，需综合技术/经济/政策因素确定方向"
            ),
            "D2": DecisionPoint(
                id="D2",
                step=66,
                name="最优配方初选",
                description="基于实验数据选择最优NM+LS配比方案",
                agents=["Miner", "Assayer", "Evaluator"],
                importance="极高",
                context_summary="已完成100步中的60步实验，需在多约束下做出核心配方决策"
            ),
            "D3": DecisionPoint(
                id="D3",
                step=75,
                name="配方定型决策",
                description="在初选配方基础上确定最终可量产方案",
                agents=["Miner", "Assayer"],
                importance="高",
                context_summary="需综合考虑工程化、成本、市场等因素"
            ),
        }
    
    def get_step(self, step_num: int) -> Optional[TaskStep]:
        """获取指定步数的任务"""
        for step in self.steps:
            if step.step_num == step_num:
                return step
        return None
    
    def get_decision_point(self, dp_id: str) -> Optional[DecisionPoint]:
        """获取指定决策点"""
        return self.decision_points.get(dp_id)
    
    def get_phase_steps(self, phase: Phase) -> List[TaskStep]:
        """获取指定阶段的所有步骤"""
        return [s for s in self.steps if s.phase == phase]
    
    def get_steps_up_to(self, step_num: int) -> List[TaskStep]:
        """获取到指定步数为止的所有步骤"""
        return [s for s in self.steps if s.step_num <= step_num]
    
    def get_context_for_decision(self, dp_id: str) -> Dict:
        """获取决策点的上下文摘要"""
        dp = self.decision_points.get(dp_id)
        if not dp:
            return {}
        
        steps_before = self.get_steps_up_to(dp.step)
        
        return {
            "decision_point": dp,
            "total_steps_completed": len(steps_before),
            "phases_completed": list(set(s.phase for s in steps_before)),
            "key_findings": self._extract_key_findings(steps_before, dp_id)
        }
    
    def _extract_key_findings(self, steps: List[TaskStep], dp_id: str) -> List[str]:
        """从已完成步骤中提取关键发现"""
        findings_map = {
            "D1": [
                "NM: 早期强度优异，火山灰活性高",
                "LS: 成本低，CaCO3含量>90%",
                "政策: 国家鼓励低碳建材发展",
                "市场: NM价格波动较大，LS供应稳定"
            ],
            "D2": [
                "实验数据: 15%NM+5%LS的28d强度最优(48MPa)",
                "理论模型: LS长期耐久性优于NM",
                "经济性: LS成本仅为NM的1/3",
                "环保性: 全生命周期NM减排效果更显著"
            ],
            "D3": [
                "小试结果: 配方稳定性良好",
                "中试条件: 具备量产能力",
                "成本分析: 单吨成本降低12%",
                "专利布局: 核心配方已申请专利"
            ]
        }
        return findings_map.get(dp_id, [])
    
    def print_overview(self):
        """打印任务总览"""
        print("\n" + "=" * 70)
        print("       100步科研任务总览 — 新型低碳水泥配方研发")
        print("=" * 70)
        print()
        
        phases_summary = {
            Phase.PHASE1_LITERATURE: ("文献调研与可行性分析", 1, 20),
            Phase.PHASE2_MECHANISM: ("机理研究与假设生成", 21, 40),
            Phase.PHASE3_EXPERIMENT: ("实验设计与数据采集", 41, 60),
            Phase.PHASE4_ANALYSIS: ("数据分析与配方优化", 61, 80),
            Phase.PHASE5_VALIDATION: ("验证与工程化落地", 81, 100),
        }
        
        for phase, (name, start, end) in phases_summary.items():
            print(f"  {name}: Step {start:3d}-{end:3d}")
        
        print()
        print("  关键决策点:")
        for dp_id, dp in self.decision_points.items():
            print(f"    {dp_id} (S{dp.step}): {dp.name} [{dp.importance}]")
        
        print()
        print("=" * 70)


# 全局任务场景实例
TASK_SCENARIO = TaskScenario100Steps()


def get_scenario() -> TaskScenario100Steps:
    """获取任务场景实例"""
    return TASK_SCENARIO


if __name__ == "__main__":
    # 测试: 打印任务总览
    scenario = TaskScenario100Steps()
    scenario.print_overview()
    
    # 测试: 获取特定决策点信息
    print("\n决策点D2详情:")
    dp = scenario.get_decision_point("D2")
    print(f"  名称: {dp.name}")
    print(f"  描述: {dp.description}")
    print(f"  参与Agent: {', '.join(dp.agents)}")
    print(f"  重要性: {dp.importance}")
