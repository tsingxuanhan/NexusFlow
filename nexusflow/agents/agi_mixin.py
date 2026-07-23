# -*- coding: utf-8 -*-
"""
AGI能力Mixin — 自主目标、元认知、跨领域迁移、持续学习
AGIMixin extracted from base_agent.py
"""

import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("BaseAgent")


class AGIMixin:
    """AGI核心能力方法：init_agi / autonomous / assess_confidence / identify_gaps / cross_domain_analogy / learn_from_interaction / periodic_learn / verify_goal / dream_cycle / distill / append_checkpoint_note / update_checkpoint / agi_status / start_agentos"""

    def init_agi(
        self,
        strategy_chat: Optional[Any] = None,
        execution_chat: Optional[Any] = None,
    ) -> None:
        """
        初始化Phase 5 AGI核心能力模块

        包括：自主目标分解、元认知、跨领域迁移、持续学习管道
        """
        from nexusflow.cognition.autonomous import AutonomousGoalHandler
        from nexusflow.cognition.meta_cognition import MetaCognition
        from nexusflow.cognition.cross_domain import CrossDomainTransfer
        from nexusflow.cognition.continuous_learning import ContinuousLearningPipelineV41 as ContinuousLearningPipeline

        # 确保记忆系统已初始化
        if not hasattr(self, '_memory'):
            self.init_memory()

        # 获取chat函数引用
        _strategy = strategy_chat or self.chat
        _execution = execution_chat or self.chat

        # 1. 自主目标处理器
        self._autonomous = AutonomousGoalHandler(
            strategy_chat=_strategy,
            execution_chat=_execution,
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            sleeptime_engine=self._sleeptime if hasattr(self, '_sleeptime') else None,
            api_endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # 2. 元认知
        self._meta_cognition = MetaCognition(
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            api_endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # 3. 跨领域迁移
        self._cross_domain = CrossDomainTransfer(
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            api_endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # 4. 持续学习管道
        self._continuous_learning = ContinuousLearningPipeline(
            memory_manager=self._memory if hasattr(self, '_memory') else None,
            sleeptime_engine=self._sleeptime if hasattr(self, '_sleeptime') else None,
            meta_cognition=self._meta_cognition,
            api_endpoint=self.endpoint,
            api_key=self.api_key,
        )

        # v4.1 新增：5. Checkpoint Writer（异步检查点写入器）
        try:
            from .checkpoint_writer import CheckpointWriter
            self._checkpoint_writer = CheckpointWriter(
                agent_name=self.name,
                storage_dir=f"./data/checkpoints/{self.name}",
                model="flash",
                auto_start=True,
            )
        except ImportError:
            self._checkpoint_writer = None
            logger.warning(f"[{self.name}] CheckpointWriter not available")

        # v4.1 新增：6. Goal Verifier（独立目标验证器）
        try:
            from nexusflow.core.goal_verifier import GoalVerifier
            self._goal_verifier = GoalVerifier(
                model="flash",
                api_endpoint=self.endpoint,
                api_key=self.api_key,
                max_verifications=3,
            )
        except ImportError:
            self._goal_verifier = None
            logger.warning(f"[{self.name}] GoalVerifier not available")

        logger.info(f"[{self.name}] AGI capabilities initialized: autonomous + meta_cognition + cross_domain + continuous_learning + checkpoint_writer + goal_verifier")

    def autonomous(self, goal: str, context: str = "", stop_condition: str = "") -> Dict:
        """
        自主执行目标 — 从模糊意图到完整结果

        Args:
            goal: 用户的高层目标
            context: 额外上下文
            stop_condition: 停止条件（自然语言），用于GoalVerifier验证
        """
        if not hasattr(self, '_autonomous'):
            self.init_agi()

        # v4.1: 如果提供了停止条件，定义给GoalVerifier
        if stop_condition and self._goal_verifier:
            self._goal_verifier.define_goal(stop_condition, context=context)

        result = self._autonomous.handle(goal, context=context)

        # v4.1: 自主执行后自动验证目标
        if stop_condition and self._goal_verifier:
            verification = self._goal_verifier.verify(
                conversation_history=self.messages if hasattr(self, 'messages') else [],
                task_output=result.get("result", "") if isinstance(result, dict) else str(result),
            )
            result["verification"] = verification.to_dict()

            # 检查是否应该继续
            should_continue, reason = self._goal_verifier.should_continue(verification)
            result["should_continue"] = should_continue
            result["verification_reason"] = reason

            if not should_continue:
                logger.info(f"[{self.name}] Autonomous task complete: {reason}")

        return result.to_dict() if hasattr(result, 'to_dict') else result

    def assess_confidence(self, query: str) -> Dict:
        """
        元认知置信度评估 — 知道自己"知道什么"和"不知道什么"

        Args:
            query: 要评估的问题
        """
        if not hasattr(self, '_meta_cognition'):
            self.init_agi()
        assessment = self._meta_cognition.assess_confidence(query)
        return assessment.to_dict()

    def identify_gaps(self, domain: Optional[str] = None) -> List[Dict]:
        """
        识别知识盲区

        Args:
            domain: 限定领域（None=全领域扫描）
        """
        if not hasattr(self, '_meta_cognition'):
            self.init_agi()
        gaps = self._meta_cognition.identify_knowledge_gaps(domain=domain)
        return [g.to_dict() for g in gaps]

    def cross_domain_analogy(self, source: str, target: str, concept: Optional[str] = None) -> List[Dict]:
        """
        跨领域类比发现

        Args:
            source: 源领域
            target: 目标领域
            concept: 限定概念（可选）
        """
        if not hasattr(self, '_cross_domain'):
            self.init_agi()
        analogies = self._cross_domain.find_analogy(source, target, concept)
        return [a.to_dict() for a in analogies]

    def learn_from_interaction(
        self,
        query: str,
        response: str,
        outcome: str = "neutral",
        feedback: str = "",
        domain: str = "general",
    ) -> Dict:
        """
        从交互中学习

        Args:
            query: 用户问题
            response: Agent回答
            outcome: "positive"/"negative"/"neutral"/"corrected"
            feedback: 用户反馈
            domain: 领域
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()

        from nexusflow.cognition.continuous_learning import InteractionOutcome
        outcome_map = {
            "positive": InteractionOutcome.POSITIVE,
            "negative": InteractionOutcome.NEGATIVE,
            "neutral": InteractionOutcome.NEUTRAL,
            "corrected": InteractionOutcome.CORRECTED,
        }
        outcome_enum = outcome_map.get(outcome, InteractionOutcome.NEUTRAL)

        result = self._continuous_learning.on_interaction(
            query=query,
            response=response,
            outcome=outcome_enum,
            feedback=feedback,
            domain=domain,
        )
        return result.to_dict()

    def periodic_learn(self, force: bool = False) -> Dict:
        """
        触发定期深度学习（Sleeptime整合）

        Args:
            force: 是否强制执行
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()
        result = self._continuous_learning.on_periodic(force=force)
        return result.to_dict()

    # ============ v4.1: 新增公开方法 ============

    def verify_goal(self, goal_condition: str) -> Dict:
        """
        验证目标是否完成（手动触发GoalVerifier）

        Args:
            goal_condition: 自然语言描述的停止条件

        Returns:
            验证结果
        """
        if not hasattr(self, '_goal_verifier'):
            self.init_agi()

        if not self._goal_verifier:
            return {"error": "GoalVerifier not available"}

        # 定义目标
        self._goal_verifier.define_goal(goal_condition)

        # 执行验证
        result = self._goal_verifier.verify(
            conversation_history=self.messages if hasattr(self, 'messages') else [],
        )

        return result.to_dict()

    def dream_cycle(self, force: bool = False) -> Dict:
        """
        触发7天周期深度整合（Dream Cycle）

        区别于on_periodic（按小时执行），dream_cycle是深度整合：
        - 路径有效性验证
        - 去重压缩
        - 重要性衰减加速

        Args:
            force: 是否强制执行

        Returns:
            DreamCycleResult
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()

        if hasattr(self._continuous_learning, 'dream_cycle'):
            result = self._continuous_learning.dream_cycle(force=force)
            return result.to_dict()
        else:
            return {"error": "dream_cycle not available in this version"}

    def distill(self, force: bool = False) -> Dict:
        """
        触发30天经验沉淀（Distill）

        识别重复工作模式，固化成可复用的skill/规则/SOP。

        Args:
            force: 是否强制执行

        Returns:
            DistillResult
        """
        if not hasattr(self, '_continuous_learning'):
            self.init_agi()

        if hasattr(self._continuous_learning, 'distill'):
            result = self._continuous_learning.distill(force=force)
            return result.to_dict()
        else:
            return {"error": "distill not available in this version"}

    def append_checkpoint_note(self, category: str, content: str) -> None:
        """
        追加笔记到checkpoint（主Agent调用）

        Args:
            category: 分类（intent/next/constraint/task/work/file/discovery/error/runtime/decision/note）
            content: 笔记内容
        """
        if not hasattr(self, '_checkpoint_writer'):
            self.init_agi()

        if self._checkpoint_writer:
            self._checkpoint_writer.append_note(category, content)

    def update_checkpoint(self, **kwargs) -> None:
        """
        更新检查点状态（异步写入）

        Args:
            current_intent: 当前意图
            next_action: 下一步动作
            working_constraints: 工作约束列表
            task_tree: 任务树字典
            current_work: 当前工作描述
            involved_files: 涉及文件列表
            cross_task_discoveries: 跨任务发现列表
            errors_and_fixes: 错误修复列表
            runtime_state: 运行时状态字典
            design_decisions: 设计决策列表
            misc_notes: 杂项笔记列表
        """
        if not hasattr(self, '_checkpoint_writer'):
            self.init_agi()

        if self._checkpoint_writer:
            self._checkpoint_writer.update_state(**kwargs)

    def agi_status(self) -> Dict:
        """获取AGI核心能力状态"""
        initialized = hasattr(self, '_autonomous')

        result = {
            "initialized": initialized,
            "modules": {
                "autonomous": hasattr(self, '_autonomous'),
                "meta_cognition": hasattr(self, '_meta_cognition'),
                "cross_domain": hasattr(self, '_cross_domain'),
                "continuous_learning": hasattr(self, '_continuous_learning'),
                "agentos": hasattr(self, '_agentos'),
                # v4.1 新增
                "checkpoint_writer": hasattr(self, '_checkpoint_writer') and self._checkpoint_writer is not None,
                "goal_verifier": hasattr(self, '_goal_verifier') and self._goal_verifier is not None,
            },
        }

        if hasattr(self, '_autonomous'):
            result["autonomous_stats"] = self._autonomous.get_stats()
        if hasattr(self, '_meta_cognition'):
            result["meta_stats"] = self._meta_cognition.get_stats()
        if hasattr(self, '_cross_domain'):
            result["cross_domain_stats"] = self._cross_domain.get_stats()
        if hasattr(self, '_continuous_learning'):
            result["learning_stats"] = self._continuous_learning.get_stats()
        # v4.1 新增模块统计
        if hasattr(self, '_checkpoint_writer') and self._checkpoint_writer:
            result["checkpoint_writer_stats"] = self._checkpoint_writer.get_stats()
        if hasattr(self, '_goal_verifier') and self._goal_verifier:
            result["goal_verifier_stats"] = self._goal_verifier.get_stats()

        return result

    def start_agentos(self, host: str = "127.0.0.1", port: int = 9090, mode: str = "http") -> None:
        """
        启动AgentOS运行时

        Args:
            host: 监听地址
            port: 监听端口
            mode: "http" 或 "stdio"
        """
        from server.agentos import AgentOS

        if not hasattr(self, '_agentos'):
            self._agentos = AgentOS(
                agent=self,
                memory_manager=self._memory if hasattr(self, '_memory') else None,
                sleeptime_engine=self._sleeptime if hasattr(self, '_sleeptime') else None,
                meta_cognition=self._meta_cognition if hasattr(self, '_meta_cognition') else None,
                continuous_learning=self._continuous_learning if hasattr(self, '_continuous_learning') else None,
                autonomous_handler=self._autonomous if hasattr(self, '_autonomous') else None,
                cross_domain=self._cross_domain if hasattr(self, '_cross_domain') else None,
                host=host,
                port=port,
            )

        # 非阻塞启动（在后台线程中运行）
        import threading
        server_thread = threading.Thread(
            target=self._agentos.run,
            kwargs={"host": host, "port": port, "mode": mode},
            daemon=True,
        )
        server_thread.start()
        logger.info(f"[{self.name}] AgentOS started on {host}:{port} ({mode})")
