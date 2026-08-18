"""最小 chromadb 桩：仅满足 AI-Novel-Forge 测试期的 import 与模块级构造需求。
不实现任何真实向量检索（测试中对 RAG 调用处已 mock）。
"""
from unittest.mock import MagicMock


def PersistentClient(*args, **kwargs):
    """返回一个 MagicMock 客户端；其 collection 方法调用均为桩。"""
    return MagicMock()
