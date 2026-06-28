"""A01 的最小 LeadAgent：一张单节点 StateGraph。

这里先用裸 StateGraph 把 ThreadState 和 reducer 跑起来；
从 A02 开始再把它换成 langchain.agents.create_agent + 工厂模式。
"""

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from deerflow_harness.thread_state import ThreadState


def _lead_node(state: ThreadState) -> dict:
    """最小节点：追加一条 AI 消息，并声明产出一个 artifact。"""
    return {
        "messages": [AIMessage(content="A01 state graph is running.")],
        "artifacts": ["a01-output.md"],
    }


def make_lead_agent(config: dict | None = None) -> StateGraph:
    """LangGraph 图工厂：返回一张已编译的最小状态图。"""
    builder = StateGraph(ThreadState)
    builder.add_node("lead", _lead_node)
    builder.set_entry_point("lead")
    builder.add_edge("lead", END)
    return builder.compile()
