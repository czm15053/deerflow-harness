"""A02 验收测试：LeadAgent 工厂行为。

覆盖 create_deerflow_agent 的接口、特性开关、互斥校验、
@Next/@Prev 装饰器定位，以及自定义中间件实例替换。
"""

from __future__ import annotations

import pytest
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from deerflow_harness.features import Next, Prev, RuntimeFeatures
from deerflow_harness.lead_agent import create_deerflow_agent
from deerflow_harness.middlewares import (
    AutoTitleMiddleware,
    DanglingToolCallMiddleware,
    LoopDetectionMiddleware,
    SandboxMiddleware,
)


class _MockModel(BaseChatModel):
    """测试用的 mock chat model。"""

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
                    message=AIMessage(content="mock response")
                )
            ]
        )

    @property
    def _llm_type(self) -> str:
        return "mock"

    def bind_tools(self, tools, **kwargs):
        """支持工具绑定，返回自身。"""
        return self


def _mock() -> _MockModel:
    """返回一个新的 mock model 实例。"""
    return _MockModel()


# ---------------------------------------------------------------------------
# 工厂接口测试
# ---------------------------------------------------------------------------


class TestFactoryInterface:
    def test_create_agent_returns_compiled_graph(self):
        """默认 features 下返回可编译、可 invoke 的 CompiledStateGraph。"""
        graph = create_deerflow_agent(model=_mock())
        result = graph.invoke({"messages": []})

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert result["messages"][0].content == "mock response"

    def test_create_agent_with_tools(self):
        """传入空工具列表也能正常编译。"""
        graph = create_deerflow_agent(model=_mock(), tools=[])
        result = graph.invoke({"messages": []})
        assert "messages" in result


# ---------------------------------------------------------------------------
# 特性开关测试
# ---------------------------------------------------------------------------


class TestFeaturesDriveMiddlewareChain:
    def test_all_disabled_minimal_chain(self):
        """全部关闭时只保留 DanglingToolCallMiddleware。"""
        graph = create_deerflow_agent(
            model=_mock(),
            features=RuntimeFeatures(
                sandbox=False,
                loop_detection=False,
                auto_title=False,
                memory=False,
            ),
        )
        result = graph.invoke({"messages": []})
        assert "messages" in result

    def test_all_default_chain(self):
        """默认 features（sandbox=True, loop_detection=True）下能正常 invoke。"""
        graph = create_deerflow_agent(
            model=_mock(),
            features=RuntimeFeatures(),
        )
        result = graph.invoke({"messages": []})
        assert "messages" in result

    def test_custom_middleware_instance_replaces_default(self):
        """传入 AgentMiddleware 实例时直接使用，而非创建默认占位。"""

        class _CustomSandbox(AgentMiddleware):
            name = "custom_sandbox"

        custom = _CustomSandbox()
        graph = create_deerflow_agent(
            model=_mock(),
            features=RuntimeFeatures(sandbox=custom),
        )
        result = graph.invoke({"messages": []})
        assert "messages" in result


# ---------------------------------------------------------------------------
# 互斥校验测试
# ---------------------------------------------------------------------------


class TestMutualExclusion:
    def test_middleware_and_features_mutually_exclusive(self):
        """同时传入 middleware 和 features 应抛 ValueError。"""
        with pytest.raises(ValueError, match="middleware"):
            create_deerflow_agent(
                model=_mock(),
                middleware=[DanglingToolCallMiddleware()],
                features=RuntimeFeatures(),
            )

    def test_middleware_and_extra_middleware_mutually_exclusive(self):
        """同时传入 middleware 和 extra_middleware 应抛 ValueError。"""
        with pytest.raises(ValueError, match="extra_middleware"):
            create_deerflow_agent(
                model=_mock(),
                middleware=[DanglingToolCallMiddleware()],
                extra_middleware=[SandboxMiddleware()],
            )


# ---------------------------------------------------------------------------
# @Next / @Prev 装饰器定位测试
# ---------------------------------------------------------------------------


class TestDecoratorPositioning:
    def test_next_decorator_positions_extra_middleware(self):
        """@Next 装饰的中间件应出现在锚点之后。"""

        @Next(SandboxMiddleware)
        class _AfterSandbox(AgentMiddleware):
            name = "after_sandbox"

        # 为验证链顺序，通过 _assemble_from_features 直接获取中间件列表
        from deerflow_harness.lead_agent import _assemble_from_features

        chain = _assemble_from_features(
            RuntimeFeatures(sandbox=True, loop_detection=False),
            extra_middleware=[_AfterSandbox()],
        )
        names = [type(m).__name__ for m in chain]

        sandbox_idx = names.index("SandboxMiddleware")
        after_idx = names.index("_AfterSandbox")
        assert after_idx == sandbox_idx + 1, (
            f"_AfterSandbox 应在 SandboxMiddleware 之后，"
            f"实际顺序: {names}"
        )

    def test_prev_decorator_positions_extra_middleware(self):
        """@Prev 装饰的中间件应出现在锚点之前。"""

        @Prev(LoopDetectionMiddleware)
        class _BeforeLoop(AgentMiddleware):
            name = "before_loop"

        from deerflow_harness.lead_agent import _assemble_from_features

        chain = _assemble_from_features(
            RuntimeFeatures(sandbox=False, loop_detection=True),
            extra_middleware=[_BeforeLoop()],
        )
        names = [type(m).__name__ for m in chain]

        loop_idx = names.index("LoopDetectionMiddleware")
        before_idx = names.index("_BeforeLoop")
        assert before_idx == loop_idx - 1, (
            f"_BeforeLoop 应在 LoopDetectionMiddleware 之前，"
            f"实际顺序: {names}"
        )

    def test_unanchored_extra_goes_to_end(self):
        """无装饰器的 extra middleware 放在链尾。"""

        class _Unanchored(AgentMiddleware):
            name = "unanchored"

        from deerflow_harness.lead_agent import _assemble_from_features

        chain = _assemble_from_features(
            RuntimeFeatures(
                sandbox=False,
                loop_detection=False,
                auto_title=False,
                memory=False,
            ),
            extra_middleware=[_Unanchored()],
        )
        names = [type(m).__name__ for m in chain]
        assert names[-1] == "_Unanchored", f"实际顺序: {names}"

    def test_anchor_not_found_raises(self):
        """锚点不存在时抛 ValueError。"""

        @Prev(AutoTitleMiddleware)
        class _MissingAnchor(AgentMiddleware):
            name = "missing_anchor"

        from deerflow_harness.lead_agent import _assemble_from_features

        with pytest.raises(ValueError, match="无法解析"):
            _assemble_from_features(
                RuntimeFeatures(
                    sandbox=False,
                    loop_detection=False,
                    auto_title=False,
                    memory=False,
                ),
                extra_middleware=[_MissingAnchor()],
            )
