# -*- coding: utf-8 -*-
"""
Tree of Thought (ToT) 推理引擎
XuanHub v4.0 Phase 2 — Planning Engine

对复杂问题，不只ReAct单步推理，而是生成多棵推理树择优。
借鉴 Yao et al. (2023) ToT + Besta et al. (2024) GoT。

核心思路：
1. 从问题出发，生成N个候选推理方向（PRO模型发散）
2. 用Flash模型评估每个方向的可行性
3. BFS/DFS搜索最优推理路径
4. 支持回溯和剪枝
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Literal, Callable
from datetime import datetime

logger = logging.getLogger("ToT")


@dataclass
class ThoughtNode:
    """思维节点 — 推理树中的一个思考步骤"""
    id: str = field(default_factory=lambda: f"TH-{uuid.uuid4().hex[:6]}")
    thought: str = ""               # 当前思考内容
    evaluation: Optional[float] = None  # 0.0~1.0 可行性评分
    is_solution: bool = False       # 是否到达最终解答
    depth: int = 0
    parent_id: Optional[str] = None
    children: List["ThoughtNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
    @property
    def best_child(self) -> Optional["ThoughtNode"]:
        """评分最高的子节点"""
        if not self.children:
            return None
        scored = [c for c in self.children if c.evaluation is not None]
        if not scored:
            return self.children[0]
        return max(scored, key=lambda c: c.evaluation)
    
    @property
    def path_to_root(self) -> List[str]:
        """从当前节点向上的思维链"""
        # 需要外部设置parent引用才能回溯，这里返回当前思考
        return [self.thought]
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "thought": self.thought,
            "evaluation": self.evaluation,
            "is_solution": self.is_solution,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "children": [c.to_dict() for c in self.children],
        }


class TreeOfThought:
    """Tree of Thought推理引擎
    
    对复杂问题生成多棵推理树择优，超越Chain-of-Thought的线性推理。
    
    使用方式：
    1. tot = TreeOfThought(strategy_agent, execution_agent)
    2. result = tot.search("如何设计一个可扩展的Agent记忆系统？")
    3. result 包含最优推理路径和最终答案
    """
    
    # 搜索策略
    BFS = "bfs"    # 广度优先：每层展开所有分支再选优
    DFS = "dfs"    # 深度优先：选最优分支深入
    
    def __init__(
        self,
        strategy_chat: Callable = None,     # PRO模型的chat函数
        evaluation_chat: Callable = None,    # Flash模型的chat函数
        branch_factor: int = 3,             # 每步生成几个候选
        max_depth: int = 4,                 # 最大推理深度
        search_strategy: str = "bfs",       # 搜索策略
        evaluation_threshold: float = 0.5,  # 低于此分数的分支被剪枝
    ):
        self.strategy_chat = strategy_chat
        self.evaluation_chat = evaluation_chat
        self.branch_factor = branch_factor
        self.max_depth = max_depth
        self.search_strategy = search_strategy
        self.evaluation_threshold = evaluation_threshold
        
        # 推理树
        self.root: Optional[ThoughtNode] = None
        self._node_index: Dict[str, ThoughtNode] = {}
    
    def search(self, problem: str, context: str = "") -> Dict[str, Any]:
        """搜索最优推理路径
        
        Args:
            problem: 要推理的复杂问题
            context: 问题背景信息
            
        Returns:
            {
                "solution": 最终解答,
                "path": 推理路径(思维链),
                "tree": 完整推理树,
                "best_score": 最优路径评分,
                "branches_explored": 探索的分支数,
            }
        """
        # 创建根节点
        self.root = ThoughtNode(thought=problem, depth=0)
        self._node_index = {self.root.id: self.root}
        
        branches_explored = 0
        
        if self.search_strategy == self.BFS:
            branches_explored = self._bfs_search(self.root, context)
        else:
            branches_explored = self._dfs_search(self.root, context)
        
        # 找最优路径
        best_path, best_score = self._find_best_path()
        
        # 找最终解答
        solution = self._extract_solution()
        
        return {
            "solution": solution,
            "path": best_path,
            "best_score": best_score,
            "branches_explored": branches_explored,
            "tree_size": len(self._node_index),
        }
    
    def _bfs_search(self, root: ThoughtNode, context: str) -> int:
        """广度优先搜索 — 逐层展开"""
        branches_explored = 0
        current_level = [root]
        
        for depth in range(self.max_depth):
            if not current_level:
                break
            
            next_level = []
            
            for node in current_level:
                # 生成候选分支
                branches = self._generate_branches(node, context)
                branches_explored += len(branches)
                
                # 评估每个分支
                for branch_thought in branches:
                    child = ThoughtNode(
                        thought=branch_thought,
                        depth=depth + 1,
                        parent_id=node.id,
                    )
                    
                    # 评估
                    score = self._evaluate_branch(branch_thought, context)
                    child.evaluation = score
                    
                    # 剪枝：低分分支不展开
                    if score >= self.evaluation_threshold:
                        node.children.append(child)
                        self._node_index[child.id] = child
                        next_level.append(child)
                        
                        # 检查是否已得到解答
                        if self._check_solution(branch_thought):
                            child.is_solution = True
            
            current_level = next_level
        
        return branches_explored
    
    def _dfs_search(self, root: ThoughtNode, context: str) -> int:
        """深度优先搜索 — 选最优分支深入"""
        return self._dfs_recursive(root, context, 0)
    
    def _dfs_recursive(self, node: ThoughtNode, context: str, depth: int) -> int:
        """DFS递归"""
        if depth >= self.max_depth:
            return 0
        
        # 生成候选分支
        branches = self._generate_branches(node, context)
        branches_explored = len(branches)
        
        # 评估所有分支
        scored_branches = []
        for branch_thought in branches:
            score = self._evaluate_branch(branch_thought, context)
            scored_branches.append((branch_thought, score))
        
        # 按评分排序，优先深入高分分支
        scored_branches.sort(key=lambda x: -x[1])
        
        # 只深入前branch_factor个
        for thought, score in scored_branches[:self.branch_factor]:
            if score < self.evaluation_threshold:
                continue
            
            child = ThoughtNode(
                thought=thought,
                depth=depth + 1,
                parent_id=node.id,
                evaluation=score,
            )
            node.children.append(child)
            self._node_index[child.id] = child
            
            if self._check_solution(thought):
                child.is_solution = True
                continue  # 找到解答，不再深入
            
            # 递归深入
            branches_explored += self._dfs_recursive(child, context, depth + 1)
        
        return branches_explored
    
    def _generate_branches(self, node: ThoughtNode, context: str) -> List[str]:
        """从当前思维节点生成候选推理方向
        
        用PRO模型（高温度）生成多个发散的推理方向。
        """
        if not self.strategy_chat:
            return self._default_branches(node)
        
        # 构建推理路径
        path = self._get_path_to_node(node)
        path_text = "\n".join(f"步骤{i+1}: {p}" for i, p in enumerate(path))
        
        prompt = f"""从以下推理步骤出发，生成{self.branch_factor}个不同的后续推理方向。
每个方向应该是独立且有洞察力的，不要重复。

{f"背景: {context}" if context else ""}

已有推理步骤:
{path_text if path_text else "（这是第一步）"}

当前步骤: {node.thought}

请生成{self.branch_factor}个后续推理方向，每个方向用编号标注:
1. [方向1]
2. [方向2]
3. [方向3]"""

        try:
            response = self.strategy_chat(prompt)
            branches = self._parse_branches(response)
            return branches if branches else self._default_branches(node)
        except Exception as e:
            logger.warning(f"ToT生成分支失败: {e}")
            return self._default_branches(node)
    
    def _evaluate_branch(self, thought: str, context: str) -> float:
        """评估分支可行性
        
        用Flash模型快速评估，返回0.0~1.0的分数。
        """
        if not self.evaluation_chat:
            return 0.5  # 默认中等分数
        
        prompt = f"""评估以下推理方向的可行性，只返回0到1之间的数字。
1.0表示非常可行，0.0表示完全不可行。

{f"背景: {context}" if context else ""}

推理方向: {thought}

可行性评分(0-1):"""

        try:
            response = self.evaluation_chat(prompt).strip()
            # 提取数字
            import re
            match = re.search(r'(\d+\.?\d*)', response)
            if match:
                score = float(match.group(1))
                return min(1.0, max(0.0, score))
            return 0.5
        except Exception as e:
            logger.warning(f"ToT评估分支失败: {e}")
            return 0.5
    
    def _check_solution(self, thought: str) -> bool:
        """检查是否已到达最终解答"""
        # 简单启发式：如果思维中包含结论性标记
        solution_markers = ["因此", "所以", "结论是", "答案是", "最终方案", "综上所述", "最终"]
        return any(marker in thought for marker in solution_markers)
    
    def _get_path_to_node(self, node: ThoughtNode) -> List[str]:
        """获取从根到当前节点的路径"""
        path = []
        current_id = node.parent_id
        visited = set()
        
        while current_id and current_id not in visited:
            visited.add(current_id)
            parent = self._node_index.get(current_id)
            if parent:
                path.append(parent.thought)
                current_id = parent.parent_id
            else:
                break
        
        return list(reversed(path))
    
    def _find_best_path(self) -> tuple:
        """找到评分最高的推理路径"""
        if not self.root:
            return [], 0.0
        
        # 找所有解节点或叶子节点
        candidates = []
        for node in self._node_index.values():
            if node.is_solution or (node.is_leaf and node.evaluation is not None):
                candidates.append(node)
        
        if not candidates:
            # 没有评分节点，返回根
            return [self.root.thought], 0.0
        
        # 找最高分的
        best = max(candidates, key=lambda n: n.evaluation or 0)
        
        # 回溯路径
        path = self._get_path_to_node(best)
        path.append(best.thought)
        
        return path, best.evaluation or 0.0
    
    def _extract_solution(self) -> str:
        """提取最终解答"""
        # 优先找is_solution的节点
        for node in self._node_index.values():
            if node.is_solution:
                return node.thought
        
        # 没有明确的解节点，取评分最高的叶子
        leaves = [n for n in self._node_index.values() if n.is_leaf and n.evaluation is not None]
        if leaves:
            best = max(leaves, key=lambda n: n.evaluation or 0)
            return best.thought
        
        return "未找到明确解答"
    
    def _parse_branches(self, response: str) -> List[str]:
        """从模型回复中解析分支"""
        import re
        branches = []
        
        for line in response.split("\n"):
            # 匹配 "1." "1)" 等编号行
            match = re.match(r'^\d+[\.\)、]\s*(.+)', line.strip())
            if match:
                branches.append(match.group(1).strip())
        
        return branches[:self.branch_factor]
    
    def _default_branches(self, node: ThoughtNode) -> List[str]:
        """默认分支生成（无API时的fallback）"""
        return [
            f"从不同角度分析: {node.thought}",
            f"验证当前假设: {node.thought}",
            f"探索替代方案: {node.thought}",
        ]
    
    def to_prompt(self) -> str:
        """将推理树序列化为可注入prompt的文本"""
        if not self.root:
            return ""
        
        lines = ["## 推理树 (Tree of Thought)"]
        self._render_node(self.root, lines, 0)
        return "\n".join(lines)
    
    def _render_node(self, node: ThoughtNode, lines: List[str], indent: int) -> None:
        prefix = "  " * indent
        score_str = f" (评分: {node.evaluation:.1f})" if node.evaluation is not None else ""
        sol_str = " ★解答" if node.is_solution else ""
        lines.append(f"{prefix}→ {node.thought[:80]}{score_str}{sol_str}")
        for child in node.children:
            self._render_node(child, lines, indent + 1)


# ============================================================================
# Graph of Thought (GoT) — 图结构推理（ToT的扩展）
# ============================================================================

class GraphOfThought:
    """Graph of Thought推理 — 允许思维节点之间有更复杂的关系
    
    与ToT的区别：
    - ToT: 严格的树结构，节点只有一个父节点
    - GoT: 图结构，节点可以合并、引用其他分支的结论
    
    适用场景：
    - 需要综合多个推理路径的结论
    - 不同分支之间有交叉引用
    """
    
    def __init__(
        self,
        strategy_chat: Callable = None,
        evaluation_chat: Callable = None,
        max_nodes: int = 20,
    ):
        self.strategy_chat = strategy_chat
        self.evaluation_chat = evaluation_chat
        self.max_nodes = max_nodes
        
        self.nodes: Dict[str, ThoughtNode] = {}
        self.edges: List[Dict] = []  # {from, to, type: "derive"|"merge"|"refine"}
    
    def think(self, problem: str, context: str = "") -> Dict[str, Any]:
        """图推理"""
        # 创建起始节点
        start = ThoughtNode(thought=problem, depth=0)
        self.nodes[start.id] = start
        
        # 第一轮：发散
        branches = self._diverge(start, context)
        
        # 第二轮：评估
        for branch in branches:
            score = self._evaluate(branch.thought, context)
            branch.evaluation = score
        
        # 第三轮：合并高分分支
        if len(branches) >= 2:
            top_branches = sorted(branches, key=lambda b: b.evaluation or 0, reverse=True)[:2]
            merged = self._merge(top_branches, context)
            if merged:
                return {
                    "solution": merged.thought,
                    "nodes_explored": len(self.nodes),
                    "top_branches": [b.thought[:80] for b in top_branches],
                }
        
        # 返回最佳分支
        if branches:
            best = max(branches, key=lambda b: b.evaluation or 0)
            return {
                "solution": best.thought,
                "nodes_explored": len(self.nodes),
                "top_branches": [b.thought[:80] for b in branches[:3]],
            }
        
        return {"solution": "推理未得出结果", "nodes_explored": 0}
    
    def _diverge(self, node: ThoughtNode, context: str) -> List[ThoughtNode]:
        """发散：从一个节点生成多个后续"""
        if not self.strategy_chat:
            return []
        
        prompt = f"""对以下问题，给出3个不同角度的推理方向：

{context if context else ""}

问题: {node.thought}

请分别给出3个推理方向，每个用编号标注。"""
        
        try:
            response = self.strategy_chat(prompt)
            import re
            branches = []
            for line in response.split("\n"):
                match = re.match(r'^\d+[\.\)、]\s*(.+)', line.strip())
                if match:
                    child = ThoughtNode(
                        thought=match.group(1).strip(),
                        depth=node.depth + 1,
                        parent_id=node.id,
                    )
                    self.nodes[child.id] = child
                    self.edges.append({"from": node.id, "to": child.id, "type": "derive"})
                    node.children.append(child)
                    branches.append(child)
            return branches
        except Exception as e:
            logger.warning(f"GoT发散失败: {e}")
            return []
    
    def _evaluate(self, thought: str, context: str) -> float:
        """评估思维节点"""
        if not self.evaluation_chat:
            return 0.5
        
        prompt = f"评估以下推理方向的可行性(0-1):\n{thought}\n评分:"
        try:
            response = self.evaluation_chat(prompt).strip()
            import re
            match = re.search(r'(\d+\.?\d*)', response)
            if match:
                return min(1.0, max(0.0, float(match.group(1))))
        except Exception:
            pass
        return 0.5
    
    def _merge(self, branches: List[ThoughtNode], context: str) -> Optional[ThoughtNode]:
        """合并多个分支的结论"""
        if not self.strategy_chat:
            return None
        
        branch_texts = "\n\n".join([
            f"方向{i+1}: {b.thought}" for i, b in enumerate(branches)
        ])
        
        prompt = f"""综合以下推理方向的结论，给出一个统一的分析：

{branch_texts}

要求：取各方向的长处，避免短处，形成更完整的结论。"""
        
        try:
            response = self.strategy_chat(prompt)
            merged = ThoughtNode(
                thought=response,
                depth=max(b.depth for b in branches) + 1,
            )
            self.nodes[merged.id] = merged
            for b in branches:
                self.edges.append({"from": b.id, "to": merged.id, "type": "merge"})
            return merged
        except Exception as e:
            logger.warning(f"GoT合并失败: {e}")
            return None
