"""声明式特性开关与中间件定位装饰器。

纯数据类与装饰器——无 I/O、无副作用。
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain.agents.middleware import AgentMiddleware


@dataclass
class RuntimeFeatures:
    """声明式特性开关，用于 ``create_deerflow_agent``。

    每个字段支持三种取值：
    - ``True``：使用工厂内置的占位中间件。
    - ``False``：不插入对应中间件。
    - ``AgentMiddleware`` 实例：用户传入自定义实现。
    """

    sandbox: bool | AgentMiddleware = True
    loop_detection: bool | AgentMiddleware = True
    auto_title: bool | AgentMiddleware = False
    memory: bool | AgentMiddleware = False


# ---------------------------------------------------------------------------
# 中间件定位装饰器
# ---------------------------------------------------------------------------


def Next(anchor: type[AgentMiddleware]):
    """声明该中间件应插入到 *anchor* 之后。"""
    if not (isinstance(anchor, type) and issubclass(anchor, AgentMiddleware)):
        raise TypeError(
            f"@Next 期望一个 AgentMiddleware 子类，得到 {anchor!r}"
        )

    def decorator(cls: type[AgentMiddleware]) -> type[AgentMiddleware]:
        cls._next_anchor = anchor  # type: ignore[attr-defined]
        return cls

    return decorator


def Prev(anchor: type[AgentMiddleware]):
    """声明该中间件应插入到 *anchor* 之前。"""
    if not (isinstance(anchor, type) and issubclass(anchor, AgentMiddleware)):
        raise TypeError(
            f"@Prev 期望一个 AgentMiddleware 子类，得到 {anchor!r}"
        )

    def decorator(cls: type[AgentMiddleware]) -> type[AgentMiddleware]:
        cls._prev_anchor = anchor  # type: ignore[attr-defined]
        return cls

    return decorator
