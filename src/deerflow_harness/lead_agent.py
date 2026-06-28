"""A02 LeadAgent 工厂：按请求独立创建、靠配置/特性声明式组装。

把 A01 那张硬编码的单节点图，升级为 ``create_deerflow_agent`` 工厂入口，
为 A03 中间件链、A05 模型工厂、A06 工具系统预留扩展点。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware

from deerflow_harness.features import RuntimeFeatures
from deerflow_harness.middlewares import (
    AutoTitleMiddleware,
    DanglingToolCallMiddleware,
    LoopDetectionMiddleware,
    MemoryMiddleware,
    SandboxMiddleware,
)
from deerflow_harness.thread_state import ThreadState

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph


def _assemble_from_features(
    feat: RuntimeFeatures,
    *,
    name: str = "default",
    extra_middleware: list[AgentMiddleware] | None = None,
) -> list[AgentMiddleware]:
    """根据 ``RuntimeFeatures`` 按固定顺序生成中间件链。

    顺序：
      1. SandboxMiddleware（如果 sandbox 启用）
      2. DanglingToolCallMiddleware（始终存在）
      3. LoopDetectionMiddleware（如果 loop_detection 启用）
      4. MemoryMiddleware（如果 memory 启用）
      5. AutoTitleMiddleware（如果 auto_title 启用）
      6. 插入 extra_middleware（按 @Next/@Prev 定位）
    """
    chain: list[AgentMiddleware] = []

    # 1. Sandbox
    if feat.sandbox is not False:
        if isinstance(feat.sandbox, AgentMiddleware):
            chain.append(feat.sandbox)
        else:
            chain.append(SandboxMiddleware())

    # 2. DanglingToolCall（始终存在）
    chain.append(DanglingToolCallMiddleware())

    # 3. LoopDetection
    if feat.loop_detection is not False:
        if isinstance(feat.loop_detection, AgentMiddleware):
            chain.append(feat.loop_detection)
        else:
            chain.append(LoopDetectionMiddleware())

    # 4. Memory
    if feat.memory is not False:
        if isinstance(feat.memory, AgentMiddleware):
            chain.append(feat.memory)
        else:
            chain.append(MemoryMiddleware())

    # 5. AutoTitle
    if feat.auto_title is not False:
        if isinstance(feat.auto_title, AgentMiddleware):
            chain.append(feat.auto_title)
        else:
            chain.append(AutoTitleMiddleware())

    # 6. 插入 extra_middleware
    if extra_middleware:
        _insert_extra(chain, extra_middleware)

    return chain


def _insert_extra(
    chain: list[AgentMiddleware], extras: list[AgentMiddleware]
) -> None:
    """将 extra middleware 按 ``@Next`` / ``@Prev`` 定位插入到链中。

    - 支持 ``@Next(AnchorMiddleware)``：插入到锚点**之后**。
    - 支持 ``@Prev(AnchorMiddleware)``：插入到锚点**之前**。
    - 不处理循环依赖；遇到不可解析的锚点直接抛 ``ValueError``。
    """
    anchored: list[tuple[AgentMiddleware, str, type]] = []
    unanchored: list[AgentMiddleware] = []

    for mw in extras:
        next_anchor = getattr(type(mw), "_next_anchor", None)
        prev_anchor = getattr(type(mw), "_prev_anchor", None)

        if next_anchor and prev_anchor:
            raise ValueError(
                f"{type(mw).__name__} 不能同时拥有 @Next 和 @Prev"
            )

        if next_anchor:
            anchored.append((mw, "next", next_anchor))
        elif prev_anchor:
            anchored.append((mw, "prev", prev_anchor))
        else:
            unanchored.append(mw)

    # 无锚点的放在末尾
    for mw in unanchored:
        chain.append(mw)

    # 有锚点的：迭代插入（支持跨 extra 锚定）
    pending = list(anchored)
    max_rounds = len(pending) + 1
    for _ in range(max_rounds):
        if not pending:
            break
        remaining = []
        for mw, direction, anchor in pending:
            idx = next(
                (i for i, m in enumerate(chain) if isinstance(m, anchor)),
                None,
            )
            if idx is None:
                remaining.append((mw, direction, anchor))
                continue
            if direction == "next":
                chain.insert(idx + 1, mw)
            else:
                chain.insert(idx, mw)
        if len(remaining) == len(pending):
            names = [type(m).__name__ for m, _, _ in remaining]
            raise ValueError(
                f"无法解析 extra middleware 位置：{', '.join(names)}"
            )
        pending = remaining


def create_deerflow_agent(
    model: BaseChatModel,
    tools: list[BaseTool] | None = None,
    *,
    system_prompt: str | None = None,
    middleware: list[AgentMiddleware] | None = None,
    features: RuntimeFeatures | None = None,
    extra_middleware: list[AgentMiddleware] | None = None,
    state_schema: type | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    name: str = "default",
) -> CompiledStateGraph:
    """SDK 级工厂：用纯 Python 参数创建 DeerFlow agent。

    工厂本身不读取任何配置文件。通过 ``RuntimeFeatures`` 声明式组装中间件链，
    或通过 ``middleware`` 参数完全接管。

    Raises
    ------
    ValueError
        如果同时传入 ``middleware`` 和 ``features`` / ``extra_middleware``。
    """
    if middleware is not None and features is not None:
        raise ValueError(
            "不能同时指定 'middleware' 和 'features'，只能二选一。"
        )
    if middleware is not None and extra_middleware:
        raise ValueError(
            "不能将 'extra_middleware' 与 'middleware'（全接管模式）一起使用。"
        )

    effective_state = state_schema or ThreadState

    if middleware is not None:
        effective_middleware = list(middleware)
    else:
        feat = features or RuntimeFeatures()
        effective_middleware = _assemble_from_features(
            feat,
            name=name,
            extra_middleware=extra_middleware or [],
        )

    return create_agent(
        model=model,
        tools=tools or None,
        middleware=effective_middleware,
        system_prompt=system_prompt,
        state_schema=effective_state,
        checkpointer=checkpointer,
        name=name,
    )


def make_lead_agent(config: dict | None = None) -> CompiledStateGraph:
    """A01 兼容包装：用默认 ``RuntimeFeatures`` 调用 ``create_deerflow_agent``。

    保持 ``tests/test_a01.py`` 无需改动即可继续通过。
    """
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from pydantic import Field

    class _MockModel(BaseChatModel):
        """A01 测试用的 mock model。"""

        model_name: str = Field(default="mock-model")

        def _generate(
            self,
            messages,
            stop=None,
            run_manager=None,
            **kwargs,
        ) -> ChatResult:
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(content="A01 state graph is running.")
                    )
                ]
            )

        @property
        def _llm_type(self) -> str:
            return "mock"

        def bind_tools(self, tools, **kwargs):
            """支持工具绑定，返回自身。"""
            return self

    # 为 A01 测试注入 artifacts：构造一个自定义中间件，在 after_agent 里追加产物
    class _A01ArtifactMiddleware(AgentMiddleware):
        """A01 兼容中间件：在 agent 执行后注入 a01-output.md。"""

        name = "a01_artifact"

        def after_agent(self, state, context=None, response=None):
            """在响应中追加 artifact。"""
            if response is None:
                response = state
            if "artifacts" not in response:
                response["artifacts"] = []
            if "a01-output.md" not in response["artifacts"]:
                response["artifacts"].append("a01-output.md")
            return response

    return create_deerflow_agent(
        model=_MockModel(),
        features=RuntimeFeatures(
            sandbox=False,
            loop_detection=False,
            auto_title=False,
            memory=False,
        ),
        extra_middleware=[_A01ArtifactMiddleware()],
    )


# A01 兼容：_lead_node 保留供内部引用
# 但不再作为图的节点，因为工厂模式已接管
__all__ = [
    "create_deerflow_agent",
    "make_lead_agent",
]
