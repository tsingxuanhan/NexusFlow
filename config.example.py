# -*- coding: utf-8 -*-
"""
xuanshu-agents 配置文件模板
复制此文件为 config.py 并填入真实值
cp config.example.py config.py
"""

import os

# DeepSeek API配置 — 从环境变量读取
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-your-key-here")
DEEPSEEK_ENDPOINT = os.environ.get("DEEPSEEK_ENDPOINT", "http://127.0.0.1:XXXX/v1/chat/completions")

# 模型配置
MODELS = {
    "pro": "deepseek-v4-pro",      # 推理用，强模型（贵但准）
    "flash": "deepseek-v4-flash"   # 验证/轻量任务（便宜快）
}

# 模型默认参数
DEFAULT_PARAMS = {
    "pro": {
        "temperature": 1.0,
        "top_p": 1.0,
        "max_tokens": 4096,
        "frequency_penalty": 0,
        "presence_penalty": 0
    },
    "flash": {
        "temperature": 1.0,
        "top_p": 1.0,
        "max_tokens": 2048,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }
}

# API请求配置
REQUEST_TIMEOUT = 120  # 秒
MAX_RETRIES = 3        # 最大重试次数
RETRY_DELAY = 5        # 重试延迟（秒），429时使用指数退避

# 对话历史配置
MAX_HISTORY_LENGTH = 50  # 保留的最大历史消息数

# ============================================================================
# v4.0 新增配置
# ============================================================================

# 领域注册表 — 可用领域列表
DOMAIN_REGISTRY = {
    "materials": {
        "display_name": "低碳建筑材料",
        "description": "SSC/MBCMs/LC3/纳米改性/混凝土耐久性",
        "default_model": "flash",
    },
    "ai_ml": {
        "display_name": "AI与机器学习",
        "description": "深度学习/NLP/LLM/Agent框架/RAG",
        "default_model": "flash",
    },
    "general": {
        "display_name": "通用",
        "description": "通用知识问答与任务执行",
        "default_model": "flash",
    },
}

# Letta三层记忆配置
MEMORY_CONFIG = {
    "core": {
        "max_tokens": 4000,          # Core Memory容量限制
        "auto_update": True,         # 自动从对话更新
        "persist": True,             # 持久化到文件
        "file": "data/core_memory.json",
    },
    "archival": {
        "index_type": "ngram_tfidf", # 索引类型（chromadb装不上）
        "chunk_size": 500,           # 文档分块大小
        "overlap": 50,               # 分块重叠
        "top_k": 5,                  # 检索返回数
        "persist": True,
        "file": "data/archival_memory.json",
    },
    "recall": {
        "max_episodes": 1000,        # 最大事件数
        "decay_rate": 0.01,          # D-MEM衰减率
        "dopamine_threshold": 0.3,   # 低于此值开始遗忘
        "persist": True,
        "file": "data/recall_memory.json",
    },
}

# ContextCompactor配置
COMPACTOR_CONFIG = {
    "threshold": 8000,    # token阈值
    "keep_recent": 4,     # 保留最近N轮
    "model": "flash",     # 压缩用模型
}

# Plan/Execute/Reflect模式配置
MODE_CONFIG = {
    "plan": {
        "model": "pro",
        "temperature": 1.0,
        "max_tokens": 4096,
    },
    "execute": {
        "model": "flash",
        "temperature": 0.3,
        "max_tokens": 4096,
    },
    "reflect": {
        "model": "pro",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
}

# ============================================================================
# v4.0 Phase 2: 规划引擎配置
# ============================================================================

# TaskTree配置
TASKTREE_CONFIG = {
    "auto_propagate": True,         # 自动传播完成状态
    "max_depth": 4,                 # 最大任务分解深度
    "default_model": {
        "plan": "pro",              # 规划类任务用PRO
        "execute": "flash",         # 执行类任务用Flash
        "research": "flash",        # 研究类任务用Flash
        "review": "flash",          # 审查类任务用Flash
        "codeact": "flash",         # CodeAct用Flash（Phase 3加沙箱）
    },
}

# Tree of Thought配置
TOT_CONFIG = {
    "branch_factor": 3,             # 每步生成几个候选分支
    "max_depth": 4,                 # 最大推理深度
    "search_strategy": "bfs",       # 搜索策略: bfs/dfs
    "evaluation_threshold": 0.5,    # 低于此分数的分支被剪枝
    "strategy_model": "pro",        # 生成分支用PRO（发散推理）
    "evaluation_model": "flash",    # 评估分支用Flash（快速评估）
}

# ReflectionLoop配置
REFLECTION_CONFIG = {
    "replan_threshold": 0.4,        # 达成度低于此值触发全局重规划
    "local_replan_threshold": 0.6,  # 达成度低于此值触发局部重规划
    "max_iterations": 3,            # 迭代反思最大次数
    "experience_confidence_init": 0.6,  # 新规则初始置信度
    "auto_extract_rules": True,     # 自动提取经验规则
}

# TeLLAgent双Agent分离配置
TELLAGENT_CONFIG = {
    "strategy_model": "pro",        # StrategyAgent用PRO
    "execution_model": "flash",     # ExecutionAgent用Flash
    "auto_evaluate": True,          # 自动评估执行结果
    "auto_replan": True,            # 失败时自动重规划
    "max_replan_attempts": 2,       # 最大重规划次数
}

# 铉枢项目信息
PROJECT_INFO = {
    "name": "铉枢·炉守",
    "full_name": "XuanHub - 面向低碳建筑材料研究的便携式AI工作站框架",
    "version": "4.0",
    "github_repo": "https://github.com/tsingxuanhan/xuan-hub",
    "lab": "济南大学绿色与智能建筑材料重点实验室",
    "advisor": "侯鹏坤",
    "directions": ["SSC", "MBCMs", "LC3", "纳米改性混凝土", "混凝土耐久性"],
}

# 输出配置
OUTPUT_DIR = "./output"
KNOWLEDGE_DIR = "./knowledge"

# ============================================================================
# v4.0 Phase 3: 工具生态配置
# ============================================================================

# CodeAct执行器配置
CODEACT_CONFIG = {
    "timeout": 15,              # 执行超时（秒）
    "max_output_length": 10000, # 最大输出长度
    "enable_guardrails": True,  # 安全检查
    "persist_locals": True,     # 保持局部变量跨执行
}

# 工具注册中心配置
TOOLREGISTRY_CONFIG = {
    "enable_guardrails": True,  # 工具执行Guardrail
    "auto_discover_mcp": False, # 自动发现MCP服务器
    "mcp_registry_url": "https://registry.modelcontextprotocol.io",
}

# 内置工具配置
TOOLS_CONFIG = {
    "web_search": {
        "enabled": True,
        "default_engine": "general",  # general/scholar
        "default_limit": 5,
        "timeout": 10,
    },
    "file_ops": {
        "enabled": True,
        "max_read_lines": 1000,
        "max_write_size": 10485760,  # 10MB
        "allowed_roots": ["/app/data", "./output", "./knowledge", "./data", "./reports"],
    },
    "data_query": {
        "enabled": True,
        "default_limit": 100,
        "max_dataset_size": 100000,
    },
    "api_caller": {
        "enabled": True,
        "default_timeout": 30,
        "max_retries": 2,
    },
    "calculator": {
        "enabled": True,
        "numpy_available": True,
    },
    "git_ops": {
        "enabled": True,
        "allowed_commands": ["status", "log", "diff", "add", "commit", "push", "pull", "fetch",
                            "branch", "tag", "checkout", "merge", "remote", "show"],
    },
    "pdf_reader": {
        "enabled": True,
        "max_pages": 50,
        "extract_tables": False,
    },
    "browser": {
        "enabled": True,
        "default_wait": 3,
        "simple_mode": True,  # True=requests, False=Playwright
    },
    "scheduler": {
        "enabled": True,
        "max_tasks": 50,
    },
}

# MCP V2配置
MCP_V2_CONFIG = {
    "protocol_version": "2026-07-01",
    "registry_url": "https://registry.modelcontextprotocol.io",
    "discover_on_start": False,
    "servers": {},  # {name: {command: ..., args: [...]}} — 在运行时填充
}

# MCP Server配置
MCP_SERVER_CONFIG = {
    "enabled": False,   # 默认不启动Server模式
    "host": "127.0.0.1",
    "port": 9090,
    "mode": "stdio",    # stdio / http
}

# A2A Gateway配置
A2A_GATEWAY_CONFIG = {
    "enabled": True,
    "self_agent_id": "xuanshu-agents",
    "discover_on_start": False,
    "known_agents": {},  # {agent_id: {url, capabilities}} — 在运行时填充
}

# ============================================================================
# v4.0 Phase 4: 知识记忆配置 — Letta三层架构
# ============================================================================

# Memory Manager全局配置
MEMORY_MANAGER_CONFIG = {
    "data_dir": "data",
    "core_max_tokens": 4000,
    "archival_chunk_size": 500,
    "archival_chunk_overlap": 50,
    "recall_max_episodes": 1000,
    "recall_decay_rate": 0.01,
    "recall_dopamine_threshold": 0.3,
    "auto_save": True,
}

# Sleeptime Engine配置
SLEEPTIME_CONFIG = {
    "dream_interval": 3600,          # 每小时做梦一次
    "dopamine_threshold": 0.3,       # 低于此值可遗忘
    "decay_rate": 0.01,              # 衰减率
    "pattern_min_frequency": 2,      # 模式最少出现次数
    "rule_min_confidence": 0.5,      # 规则最低置信度
    "model": "flash",                # 用Flash模型执行（省钱）
}

# Multi-Hop RAG配置
MULTIHOP_RAG_CONFIG = {
    "max_hops": 3,                   # 最大跳数
    "top_k_per_hop": 5,              # 每跳返回数
    "sufficient_threshold": 0.7,     # 充分性阈值
    "llm_query_generation": True,    # 是否用LLM生成下一跳查询
}

# 知识库领域配置
KNOWLEDGE_DOMAINS = {
    "materials": {
        "display_name": "材料科学",
        "priority": "P0",
        "target_docs": 15,
        "knowledge_dir": "knowledge",
    },
    "ai_ml": {
        "display_name": "AI与机器学习",
        "priority": "P0",
        "target_docs": 20,
        "knowledge_dir": "knowledge/ai_ml",
    },
    "computer_science": {
        "display_name": "计算机科学",
        "priority": "P0",
        "target_docs": 15,
        "knowledge_dir": "knowledge/cs",
    },
    "math_stats": {
        "display_name": "数学与统计",
        "priority": "P1",
        "target_docs": 10,
        "knowledge_dir": "knowledge/math",
    },
    "physics": {
        "display_name": "物理学",
        "priority": "P1",
        "target_docs": 10,
        "knowledge_dir": "knowledge/physics",
    },
    "biology": {
        "display_name": "生物学",
        "priority": "P2",
        "target_docs": 8,
        "knowledge_dir": "knowledge/biology",
    },
    "economics": {
        "display_name": "经济学",
        "priority": "P2",
        "target_docs": 8,
        "knowledge_dir": "knowledge/economics",
    },
    "law": {
        "display_name": "法律",
        "priority": "P2",
        "target_docs": 5,
        "knowledge_dir": "knowledge/law",
    },
    "psychology": {
        "display_name": "心理学",
        "priority": "P2",
        "target_docs": 5,
        "knowledge_dir": "knowledge/psychology",
    },
    "history_philosophy": {
        "display_name": "历史与哲学",
        "priority": "P2",
        "target_docs": 5,
        "knowledge_dir": "knowledge/history",
    },
}


# ============================================================================
# v4.0 Phase 5: AGI核心能力配置
# ============================================================================

# 自主目标处理器配置
AUTONOMOUS_CONFIG = {
    "max_decomposition_depth": 3,      # 最大分解深度
    "max_execution_steps": 20,         # 最大执行步数
    "confidence_threshold": 0.6,       # 完成置信度阈值
    "strategy_model": "pro",           # 策略推理用PRO
    "execution_model": "flash",        # 执行用Flash
    "auto_record_to_memory": True,     # 自动记录到记忆系统
}

# 元认知配置
META_COGNITION_CONFIG = {
    "confidence_threshold_high": 0.8,  # 高置信阈值
    "confidence_threshold_low": 0.4,   # 低置信阈值
    "auto_gap_scan": True,             # 自动扫描知识盲区
    "auto_self_improve": False,        # 自动自我改进（需要确认）
    "gap_scan_interval": 86400,        # 盲区扫描间隔（秒，默认1天）
}

# 跨领域迁移配置
CROSS_DOMAIN_CONFIG = {
    "similarity_threshold": 0.5,       # 类比相似度阈值
    "max_analogies": 5,                # 最大类比数
    "auto_transfer": False,            # 不自动迁移（需确认）
    "store_transfer_patterns": True,   # 记录迁移模式
    "validation_threshold": 0.5,       # 迁移验证阈值
}

# 持续学习管道配置
CONTINUOUS_LEARNING_CONFIG = {
    "core_update_threshold": 0.7,      # Core更新重要性阈值
    "consolidation_interval": 3600,    # 整理间隔（秒，默认1小时）
    "batch_buffer_size": 10,           # 批量学习缓冲区大小
    "auto_evaluate_outcome": True,     # 自动判断交互效果
    "auto_fill_p0_gaps": True,         # 自动填补P0级别盲区
}

# AgentOS运行时配置
AGENTOS_CONFIG = {
    "host": "127.0.0.1",
    "port": 9090,
    "mode": "http",                    # http / stdio
    "cors_enabled": True,              # 启用CORS
    "api_key_required": False,         # API Key认证（生产环境建议开启）
    "max_concurrent_tasks": 10,        # 最大并发任务数
}


# ============================================================
# Phase 7: 认知分工 & 自适应上下文
# ============================================================

# 认知分工引擎配置
CDOL_ENABLED = True
CDOL_MAX_ROUNDS = 2              # 最大通信轮次
CDOL_MIN_BRIDGEABILITY = 0.3     # 最低桥接度阈值
CDOL_FALSE_CONSENSUS_THRESHOLD = 0.7  # 虚假一致检测阈值

# 自适应上下文管理
CONTEXT_WINDOW_DEFAULT = 4096    # 默认上下文窗口大小
CONTEXT_WINDOW_MIN = 512         # 最小窗口
CONTEXT_WINDOW_MAX = 32768       # 最大窗口
LAZINESS_CHECK_INTERVAL = 5      # 每N步检查一次懒惰
GLOBAL_SYNC_INTERVAL = 10        # 每N步强制全局同步