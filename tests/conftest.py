# -*- coding: utf-8 -*-
"""
NexusFlow 单元测试 conftest
配置测试路径，确保能正确 import 仓库根目录下的模块。
"""
import sys
import os

# 将仓库根目录加入 sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
