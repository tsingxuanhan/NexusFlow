# AI与机器学习核心概念

## 深度学习基础
- **反向传播**: 通过链式法则计算损失函数对权重的梯度，是训练神经网络的核心算法
- **梯度消失/爆炸**: 深层网络中梯度逐层衰减或放大，解决方案：BatchNorm、残差连接、梯度裁剪
- **注意力机制**: Q-K-V计算注意力权重，允许模型关注输入的不同部分，Transformer的核心
- **Transformer架构**: Self-Attention + FFN + LayerNorm，并行化优于RNN，GPT/BERT的基础
- **位置编码**: Transformer无位置感知，需注入位置信息（正弦编码/RoPE/ALiBi）

## 大语言模型(LLM)
- **预训练**: 大规模语料上的自监督学习（下一词预测/掩码语言建模）
- **微调**: SFT(Supervised Fine-Tuning) → RLHF → DPO → GRPO
- **推理能力**: Chain-of-Thought、Tree-of-Thought、自我反思提升推理
- **长上下文**: RoPE扩展、滑动窗口、稀疏注意力支持128K-1M tokens
- **多模态**: 视觉-语言模型(VLM)，统一架构处理文本+图像+音频

## RAG技术
- **基础RAG**: 检索-增强-生成三阶段
- **语义检索**: 向量相似度搜索，embedding模型将文本映射到向量空间
- **混合检索**: 向量+关键词(BM25)融合检索，RRF(Reciprocal Rank Fusion)排序
- **多跳RAG**: Agentic RAG，自动追踪引用链，Google验证比单跳高30%准确率
- **Chunk策略**: 固定大小/语义分块/递归分块，overlap防止信息断裂

## Agent框架
- **ReAct**: 推理+行动交替循环，LLM生成思考→执行工具→观察结果
- **CodeAct**: Agent通过写代码而非JSON调用工具，SWE-Bench上高15-20%
- **MCP(Model Context Protocol)**: 标准化工具接入协议，2026-07版本无状态化
- **A2A(Agent-to-Agent)**: 跨框架Agent协作协议，Google提出v1.0
- **Sleeptime Agent**: Agent空闲时整理记忆提取规则，成本用Flash模型

## 评估基准
- **SWE-Bench**: 软件工程任务，衡量代码修复能力
- **MMLU**: 多学科知识，57个领域
- **HumanEval**: 代码生成，164个Python编程题
- **GAIA**: 通用AI助手，3个难度级别
