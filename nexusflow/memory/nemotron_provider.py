# -*- coding: utf-8 -*-
"""
Nemotron-3 Embed 神经语义嵌入提供者

三种接入方式：
- local: 本地 SentenceTransformers 推理（默认）
- nim: NVIDIA NIM API (https://integrate.api.nvidia.com/v1/embeddings)
- openrouter: OpenRouter API (nvidia/nemotron-3-embed-1b:free)

用法:
    # 本地推理
    provider = NemotronEmbeddingProvider(mode="local")

    # NIM API
    provider = NemotronEmbeddingProvider(
        mode="nim",
        api_key="nvapi-xxx",
        model_name="nvidia/nemotron-3-embed-1b",
    )

    # OpenRouter（免费）
    provider = NemotronEmbeddingProvider(
        mode="openrouter",
        api_key="sk-or-v1-xxx",
        model_name="nvidia/nemotron-3-embed-1b:free",
    )

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

    # NIM 端点配置
    _NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
    _OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        model_name: str = "nvidia/Nemotron-3-Embed-1B-BF16",
        mode: str = "local",
        dimension: Optional[int] = None,
        device: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """
        Args:
            model_name: 模型名称。local 模式用 HuggingFace ID，
                        NIM 用 "nvidia/nemotron-3-embed-1b"，
                        OpenRouter 用 "nvidia/nemotron-3-embed-1b:free"。
            mode: 推理方式 - "local" / "nim" / "openrouter"
            dimension: 向量维度。None 则首次编码后自动检测。
            device: PyTorch device（仅 local 模式）。
            api_key: API Key（nim/openrouter 模式必填）。
            api_base: 自定义 API 端点（可选，覆盖默认值）。
        """
        if mode not in ("local", "nim", "openrouter"):
            raise ValueError(f"Unknown mode '{mode}'. Use 'local', 'nim', or 'openrouter'.")
        if mode in ("nim", "openrouter") and not api_key:
            raise ValueError(f"mode='{mode}' requires api_key.")

        self.model_name = model_name
        self.mode = mode
        self.dimension = dimension
        self.device = device
        self.api_key = api_key
        self._model = None
        self._loaded = False

        # API 端点
        if api_base:
            self._api_base = api_base
        elif mode == "nim":
            self._api_base = self._NIM_BASE_URL
        elif mode == "openrouter":
            self._api_base = self._OPENROUTER_BASE_URL
        else:
            self._api_base = None

    def _ensure_loaded(self):
        """延迟初始化（local 模式加载模型，API 模式验证连接）"""
        if self._loaded:
            return

        if self.mode == "local":
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.model_name,
                    device=self.device,
                )
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
            # API 模式：发一个测试请求验证连通性
            try:
                test_vec = self._api_encode("test")
                if self.dimension is None:
                    self.dimension = len(test_vec)
                self._loaded = True
                logger.info(
                    f"[NemotronProvider] API mode '{self.mode}' connected, "
                    f"dimension: {self.dimension}"
                )
            except Exception as e:
                logger.error(f"[NemotronProvider] API connection failed: {e}")
                raise

    # ============ 核心接口 ============

    def embed(self, text: str) -> List[float]:
        """兼容接口 — 默认作为 document 编码"""
        return self.embed_document(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量编码（API 模式走批量请求，local 模式逐条）"""
        if self.mode in ("nim", "openrouter"):
            self._ensure_loaded()
            # API 模式：批量添加 passage 前缀
            prefixed = [f"passage: {t}" for t in texts]
            return self._api_encode_batch(prefixed)
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
        return self._api_encode(prefixed_text)

    def _api_encode(self, prefixed_text: str) -> List[float]:
        """通过 API 编码单条文本"""
        import urllib.request
        import json

        url = f"{self._api_base}/embeddings"
        payload = json.dumps({
            "model": self.model_name,
            "input": prefixed_text,
            "encoding_format": "float",
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return data["data"][0]["embedding"]

    def _api_encode_batch(self, prefixed_texts: List[str]) -> List[List[float]]:
        """通过 API 批量编码（NIM 支持 input 为列表）"""
        import urllib.request
        import json

        url = f"{self._api_base}/embeddings"
        payload = json.dumps({
            "model": self.model_name,
            "input": prefixed_texts,
            "encoding_format": "float",
        }).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # API 返回的 data 数组与 input 顺序一致
        return [item["embedding"] for item in data["data"]]

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
            "device": str(self._model.device) if self._model else (
                "api" if self.mode in ("nim", "openrouter") else None
            ),
            "api_base": self._api_base,
        }
