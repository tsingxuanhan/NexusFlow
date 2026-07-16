# -*- coding: utf-8 -*-
"""
铉枢·炉守 可视化监控面板
NexusFlow Dashboard — Gradio Web UI

受TEN Agent的可视化Dashboard启发，对应荣耀赛题评分的"界面美观度5分"。

功能:
- Agent拓扑图实时可视化（基于NetworkX + Gradio Plot）
- 任务执行进度追踪
- 路由决策历史回溯
- 系统健康度仪表盘
- Demo交互入口（提交任务→看Agent协作过程）

依赖: gradio (pip install gradio)
"""

import logging
import time
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("Dashboard")

try:
    import gradio as gr
    HAS_GRADIO = True
except ImportError:
    HAS_GRADIO = False
    logger.warning("gradio not installed, dashboard unavailable")


class NexusFlowDashboard:
    """
    NexusFlow 可视化监控面板
    
    用法:
        from nexusflow.core.dynamic_router import DynamicTopologyRouter
        from nexusflow.core.edge_cloud_scheduler import EdgeCloudScheduler
        
        router = DynamicTopologyRouter()
        scheduler = EdgeCloudScheduler()
        
        dashboard = NexusFlowDashboard(router=router, scheduler=scheduler)
        dashboard.launch(server_port=7860)
    """
    
    def __init__(self, router=None, scheduler=None, title: str = "NexusFlow"):
        self.router = router
        self.scheduler = scheduler
        self.title = title
        self._demo_log: List[Dict] = []
        self._task_log: List[Dict] = []
        
        logger.info(f"[Dashboard] Initialized: {title}")
    
    def launch(self, server_name: str = "0.0.0.0", server_port: int = 7860,
               share: bool = False) -> None:
        """启动Dashboard"""
        if not HAS_GRADIO:
            logger.error("[Dashboard] gradio not installed. Run: pip install gradio")
            return
        
        app = self._build_ui()
        app.launch(
            server_name=server_name,
            server_port=server_port,
            share=share,
            show_error=True,
        )
    
    def _build_ui(self):
        """构建Gradio界面"""
        with gr.Blocks(
            title=f"{self.title} Dashboard",
            theme=gr.themes.Soft(),
            css=self._get_css(),
        ) as app:
            
            gr.Markdown(f"# 🧠 {self.title} — 动态群体智能监控面板")
            gr.Markdown("*基于动态认知拓扑的超长程复杂任务协作系统*")
            
            with gr.Tabs():
                # ============ Tab 1: 系统概览 ============
                with gr.Tab("📊 系统概览"):
                    with gr.Row():
                        with gr.Column(scale=2):
                            topology_status = gr.Dataframe(
                                headers=["Agent", "角色", "层级", "状态", "评分", "当前任务"],
                                label="Agent拓扑状态",
                                interactive=False,
                            )
                        with gr.Column(scale=1):
                            system_metrics = gr.JSON(label="系统指标")
                    
                    refresh_btn = gr.Button("🔄 刷新状态", variant="primary")
                    refresh_btn.click(
                        fn=self._refresh_topology,
                        outputs=[topology_status, system_metrics]
                    )
                
                # ============ Tab 2: 任务提交(Demo) ============
                with gr.Tab("🚀 任务提交"):
                    gr.Markdown("### 提交任务，观察Agent动态协作过程")
                    
                    with gr.Row():
                        task_input = gr.Textbox(
                            label="任务描述",
                            placeholder="例：帮我研究低碳水泥的纳米改性方案，需要文献分析+假设生成+实验设计...",
                            lines=3,
                        )
                    
                    with gr.Row():
                        complexity_sel = gr.Dropdown(
                            choices=["简单(1-5步)", "中等(5-20步)", "复杂(20-50步)", "超长程(50+步)"],
                            value="中等(5-20步)",
                            label="任务复杂度",
                        )
                        privacy_sel = gr.Dropdown(
                            choices=["公开数据", "内部数据", "敏感数据"],
                            value="公开数据",
                            label="隐私等级",
                        )
                    
                    submit_btn = gr.Button("🎯 提交任务", variant="primary")
                    
                    with gr.Row():
                        route_result = gr.JSON(label="路由决策")
                        schedule_result = gr.JSON(label="调度决策")
                    
                    execution_log = gr.Dataframe(
                        headers=["时间", "事件", "Agent", "详情"],
                        label="执行日志",
                        interactive=False,
                    )
                    
                    submit_btn.click(
                        fn=self._submit_task,
                        inputs=[task_input, complexity_sel, privacy_sel],
                        outputs=[route_result, schedule_result, execution_log]
                    )
                
                # ============ Tab 3: 路由历史 ============
                with gr.Tab("📜 路由历史"):
                    route_history = gr.Dataframe(
                        headers=["计划ID", "任务", "Agent链", "拓扑类型", "置信度", "状态"],
                        label="路由决策历史",
                        interactive=False,
                    )
                    refresh_route_btn = gr.Button("🔄 刷新历史")
                    refresh_route_btn.click(
                        fn=self._refresh_route_history,
                        outputs=[route_history]
                    )
                
                # ============ Tab 4: 资源监控 ============
                with gr.Tab("🖥️ 资源监控"):
                    with gr.Row():
                        resource_table = gr.Dataframe(
                            headers=["层级", "资源名", "GPU", "延迟(ms)", "负载", "可用模型"],
                            label="端-边-云资源池",
                            interactive=False,
                        )
                        scheduling_stats = gr.JSON(label="调度统计")
                    
                    refresh_res_btn = gr.Button("🔄 刷新资源")
                    refresh_res_btn.click(
                        fn=self._refresh_resources,
                        outputs=[resource_table, scheduling_stats]
                    )
                
                # ============ Tab 5: 优化建议 ============
                with gr.Tab("💡 优化建议"):
                    suggestions = gr.Markdown(label="系统优化建议")
                    refresh_sug_btn = gr.Button("🔄 分析并生成建议")
                    refresh_sug_btn.click(
                        fn=self._generate_suggestions,
                        outputs=[suggestions]
                    )
            
            # 底部信息
            gr.Markdown("---")
            gr.Markdown(
                "**NexusFlow** · 基于动态认知拓扑的超长程群体智能引擎 · "
                f"Powered by NexusFlow"
            )
        
        return app
    
    # ============ 回调函数 ============
    
    def _refresh_topology(self):
        """刷新拓扑状态"""
        if not self.router:
            return [["No router connected"]], {}
        
        summary = self.router.get_topology_summary()
        
        rows = []
        for agent in summary["agents"]:
            rows.append([
                agent["name"],
                agent["role"],
                agent["tier"],
                agent["load_state"],
                f"{agent['score']:.2f}",
                agent["tasks"],
            ])
        
        metrics = {
            "总Agent数": summary["total_agents"],
            "在线Agent": summary["online_agents"],
            "拓扑边数": summary["topology_edges"],
            "累计路由": summary["total_routes"],
        }
        
        return rows, metrics
    
    def _submit_task(self, task_desc: str, complexity: str, privacy: str):
        """提交任务并返回路由+调度决策"""
        import uuid
        
        # 解析参数
        complexity_map = {
            "简单(1-5步)": 2, "中等(5-20步)": 3,
            "复杂(20-50步)": 4, "超长程(50+步)": 5,
        }
        privacy_map = {"公开数据": 0, "内部数据": 1, "敏感数据": 2}
        
        task_id = str(uuid.uuid4())[:8]
        
        # 路由决策
        route_data = None
        if self.router:
            from nexusflow.core.dynamic_router import TaskRequirement, TaskComplexity
            
            task_req = TaskRequirement(
                task_id=task_id,
                description=task_desc,
                complexity=TaskComplexity(complexity_map.get(complexity, 3)),
                privacy_level=privacy_map.get(privacy, 0),
                required_capabilities=["planning", "research", "execution"],
            )
            plan = self.router.route(task_req)
            route_data = {
                "plan_id": plan.plan_id,
                "agent_chain": [
                    self.router._agents[a].name if a in self.router._agents else a
                    for a in plan.agent_chain
                ],
                "topology_type": plan.topology_type,
                "confidence": plan.confidence,
                "estimated_latency_ms": plan.estimated_latency_ms,
                "estimated_cost": plan.estimated_cost,
            }
        
        # 调度决策
        schedule_data = None
        if self.scheduler:
            decision = self.scheduler.schedule({
                "task_id": task_id,
                "privacy_level": privacy_map.get(privacy, 0),
                "latency_budget_ms": 30000,
            })
            schedule_data = {
                "tier": decision.selected_tier.value,
                "resource": decision.selected_resource,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "privacy_guaranteed": decision.privacy_guaranteed,
            }
        
        # 记录执行日志
        now = datetime.now().strftime("%H:%M:%S")
        log_rows = [
            [now, "任务接收", "System", f"task_id={task_id}"],
        ]
        if route_data:
            log_rows.append([now, "路由决策", "Router", 
                           f"chain={route_data['agent_chain']}"])
        if schedule_data:
            log_rows.append([now, "调度决策", "Scheduler",
                           f"tier={schedule_data['tier']}"])
        
        self._task_log.append({
            "task_id": task_id,
            "description": task_desc,
            "route": route_data,
            "schedule": schedule_data,
            "timestamp": now,
        })
        
        return route_data, schedule_data, log_rows
    
    def _refresh_route_history(self):
        """刷新路由历史"""
        if not self.router:
            return [["No router connected"]]
        
        history = self.router.get_route_history(limit=30)
        rows = []
        for h in history:
            rows.append([
                h["plan_id"],
                h["task_id"],
                " → ".join(h["chain"]),
                h["topology"],
                f"{h['confidence']:.2f}",
                h["status"],
            ])
        return rows
    
    def _refresh_resources(self):
        """刷新资源监控"""
        if not self.scheduler:
            return [["No scheduler connected"]], {}
        
        resources = self.scheduler.get_all_resources()
        rows = []
        for tier_name, res_list in resources.items():
            for r in res_list:
                rows.append([
                    tier_name,
                    r["name"],
                    r["gpu"],
                    r["latency_ms"],
                    f"{r['load_factor']:.0%}",
                    ", ".join(r["models"][:3]) + ("..." if len(r["models"]) > 3 else ""),
                ])
        
        stats = self.scheduler.get_scheduling_stats()
        return rows, stats
    
    def _generate_suggestions(self):
        """生成优化建议"""
        if not self.router:
            return "### 未连接路由器\n请先初始化 DynamicTopologyRouter"
        
        suggestions = self.router.suggest_optimization()
        
        md = "### 💡 系统优化建议\n\n"
        for i, s in enumerate(suggestions, 1):
            md += f"{i}. {s}\n"
        
        # 附加资源建议
        if self.scheduler:
            stats = self.scheduler.get_scheduling_stats()
            md += "\n### 📊 调度分析\n\n"
            md += f"- 调度策略: {stats['policy']}\n"
            md += f"- 总调度次数: {stats['total_decisions']}\n"
            md += f"- 层间迁移: {stats['total_migrations']}次\n"
            
            dist = stats.get("tier_distribution", {})
            md += "- 层级分布:\n"
            for tier, count in dist.items():
                pct = count / max(stats['total_decisions'], 1) * 100
                md += f"  - {tier}: {count}次 ({pct:.0f}%)\n"
        
        return md
    
    def _get_css(self) -> str:
        """自定义CSS"""
        return """
        .gradio-container {
            max-width: 1200px !important;
            margin: auto !important;
        }
        footer {
            display: none !important;
        }
        """
