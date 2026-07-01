# 铉枢 · 云电脑模拟本机 — 环境状态

## 部署时间
2026-05-22 18:30~18:50

## 硬件限制
- CPU: 2 cores
- RAM: 3.8GB (无swap)
- GPU: 无 → Ollama CPU-only模式
- 存储: 云端临时

## 服务清单

| 服务 | 端口 | 状态 | 说明 |
|------|------|------|------|
| Ollama API | :11434 | ✅ | CPU模式，已装qwen2.5:0.5b |
| Open WebUI | :3000 | ✅ | v0.9.5，接Ollama |
| DeepSeek代理 | :8083 | ✅ | → api.deepseek.com, RPM=30 |
| MiMo 700M代理 | :8084 | ✅ | → token-plan-cn.xiaomimimo.com, RPM=20 |
| MiMo 200M代理 | :8085 | ✅ | → token-plan-cn.xiaomimimo.com, RPM=15 |
| 控制面板 | :8766 | ✅ | 含LiquidGlass Demo |
| Draw.io | :8080 | ✅ | |
| Portainer | :19443 | ✅ | 端口从9443改为19443(避免冲突) |

## 已验证功能

1. ✅ Ollama CPU推理 (qwen2.5:0.5b)
2. ✅ DeepSeek API代理转发 (chat/completions)
3. ✅ Open WebUI + Ollama 联通
4. ✅ Agent管线: Miner → Assayer → Foundry (3/3 success)
5. ✅ 编排器DAG依赖执行
6. ✅ Checkpoint/Handoff机制
7. ✅ 控制面板可访问

## 本机vs云电脑差异

| | 本机 | 云电脑 |
|---|---|---|
| GPU | RTX 3080 Ti 16GB | 无 |
| Ollama模型 | 7B/9B全功能 | 0.5B仅测试 |
| ComfyUI | ✅ | ❌ (需GPU) |
| JupyterLab | ✅ | ⚠️ (RAM紧张) |
| Stirling PDF | ✅ | ⚠️ (3.3GB镜像, RAM紧张) |
| 数据持久性 | ✅ 本地盘 | ⚠️ 临时环境 |

## 修复记录

1. Docker安装: Ubuntu docker.io + compose v2 plugin (v5.1.4)
2. Docker Hub镜像: 配置了3个国内mirror
3. base_agent.py: 添加 `from dataclasses import dataclass, field`
4. base_agent.py: chat()添加 `**kwargs` 接收编排器注入的上游结果
5. Portainer端口: 9443→19443 (9000被系统占用)
6. API代理: 纯Python实现，替代Docker部署(省RAM)

## 启动命令
```bash
bash /root/ai-workstation/scripts/start-cloud-sim.sh
```
