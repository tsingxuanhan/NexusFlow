# -*- coding: utf-8 -*-
"""
Nemotron-3 Embed 神经语义嵌入提供者

三种接入方式：
- local: 本地 SentenceTransformers 推理（默认）
- nim: NVIDIA NIM API (https://integrate.api.nvidia.com/v1/embeddings)
- openrouter: OpenRouter API (nvidia/nemotron-3-embed-1b:free)

用法:
    provider = NemotronEmbeddingProvider()
    vec = provider.embed_query("纳米SiO2对混凝土的影响")
    doc_vec = provider.embed_document("SSC水泥的早期强度特性...")
"""

import logging
from typing import List, Optional

from nexusflow.memory.vector_memory import EmbeddingProvider

logger = logging.getLogger("NemotronProvider")


class NemotronEmbeddingProvider(EmbeddingProvider):
    """
    Nemotron-3 Embed 神经语义嵌入提供者

    实现 EmbeddingProvider 抽象接口，无缝替换现有 Provider。
    自动添加 query/passage 前缀以满足 Nemotron 的推理要求。

    模型版本:
    - 8B-BF16: 云端高精度（RTEB #1, 78.5%）
    - 1B-BF16: 边缘低延迟（RTEB 72.4%, ~2.3GB VRAM）
    - 1B-NVFP4: Blackwell 高吞吐（仅 Blackwell 架构有加速）
    """

    def __init__(
        self,
        model_name: str = "nvidia/Nemotron-3-Embed-1B-BF16",
        mode: str = "local",
        dimension: Optional[int] = None,
        device: Optional[str] = None,
    ):
        """
        Args:
            model_name: HuggingFace 模型名称
            mode: 推理方式 - "local" / "nim" / "openrouter"
            dimension: 向量维度。None 则首次编码后自动检测。
            device: PyTorch device。None 则自动选择（有 GPU 用 GPU）。
        """
        self.model_name = model_name
        self.mode = mode
        self.dimension = dimension
        self.device = device
        self._model = None
        self._loaded = False

    def _ensure_loaded(self):
        """延迟加载模型（避免 import 时占显存）"""
        if self._loaded:
            return

        if self.mode == "local":
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                )
                # 自动检测维度
                if self.dimension is None:
                    test_vec = self._model.encode("test", normalize_embeddings=True)
                    self.dimension = len(test_vec)
                    logger.info(f"[NemotronProvider] Auto-detected dimension: {self.dimension}")
                self._loaded = True
                logger.info(
                    f"[NemotronProvider] Loaded {self.model_name} on "
                    f"{self._model.device}"
                )
            except Exception as e:
                logger.error(f"[NemotronProvider] Failed to load model: {e}")
                raise
        else:
            # nim / openrouter 模式留作扩展
            raise NotImplementedError(
                f"Mode '{self.mode}' not yet implemented. Use mode='local'."
            )

    # ============ 核心接口 ============

    def embed(self, text: str) -> List[float]:
        """兼容接口 — 默认作为 document 编码"""
        return self.embed_document(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量编码（全部作为 document）"""
        return [self.embed_document(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        """编码查询文本 — 添加 'query: ' 前缀"""
        self._ensure_loaded()
        return self._encode(f"query: {text}")

    def embed_document(self, text: str) -> List[float]:
        """编码文档文本 — 添加 'passage: ' 前缀"""
        self._ensure_loaded()
        return self._encode(f"passage: {text}")

    # ============ 内部方法 ============

    def _encode(self, prefixed_text: str) -> List[float]:
        """编码已添加前缀的文本"""
        if self.mode == "local":
            embedding = self._model.encode(
                prefixed_text, normalize_embeddings=True
            )
            return embedding.tolist()
        raise NotImplementedError

    # ============ 工具方法 ============

    def is_loaded(self) -> bool:
        """模型是否已加载"""
        return self._loaded

    def get_model_info(self) -> dict:
        """返回模型信息"""
        return {
            "model_name": self.model_name,
            "mode": self.mode,
            "dimension": self.dimension,
            "loaded": self._loaded,
            "device": str(self._model.device) if self._model else None,
        }
