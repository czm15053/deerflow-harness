"""A02 占位中间件——A03 会逐步填入真实逻辑。

当前仅保留类名与 ``name`` 属性，方法全部继承默认空实现。
测试只验证「是否按预期顺序出现在中间件链中」。
"""

from __future__ import annotations

from langchain.agents.middleware import AgentMiddleware


class SandboxMiddleware(AgentMiddleware):
    """沙箱中间件占位。"""

    name = "sandbox"


class DanglingToolCallMiddleware(AgentMiddleware):
    """悬空工具调用中间件占位。"""

    name = "dangling_tool_call"


class LoopDetectionMiddleware(AgentMiddleware):
    """循环检测中间件占位。"""

    name = "loop_detection"


class MemoryMiddleware(AgentMiddleware):
    """记忆中间件占位。"""

    name = "memory"


class AutoTitleMiddleware(AgentMiddleware):
    """自动标题中间件占位。"""

    name = "auto_title"
