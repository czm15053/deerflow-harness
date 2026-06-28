"""ThreadState: 在 LangGraph AgentState 之上叠加线程运行时字段。

一次对话（thread）的全部运行时状态放在一张 TypedDict 里。
LangGraph 的 AgentState 只负责 messages；本模块扩展出沙箱、线程目录、
产物文件、todo、已上传文件、已查看图片等字段，并为并发写入的字段配好
reducer，避免多个节点同时更新时静默丢数据。
"""

from typing import Annotated, NotRequired, TypedDict

from langchain.agents import AgentState


class SandboxState(TypedDict):
    """沙箱实例标识。"""

    sandbox_id: NotRequired[str | None]


class ThreadDataState(TypedDict):
    """线程目录映射：workspace / uploads / outputs。"""

    workspace_path: NotRequired[str | None]
    uploads_path: NotRequired[str | None]
    outputs_path: NotRequired[str | None]


class ViewedImageData(TypedDict):
    """已查看图片的 base64 数据。"""

    base64: str
    mime_type: str


def merge_sandbox(
    existing: SandboxState | None, new: SandboxState | None
) -> SandboxState | None:
    """SandboxState 的 reducer：只允许幂等写入。

    多个沙箱工具可能在同一步里懒初始化并写入同一个 sandbox_id。
    如果两个写入的 id 不一致，说明隔离/生命周期出现 bug，必须 fail-closed，
    而不是静默覆盖。
    """
    if new is None:
        return existing
    if existing is None:
        return new

    existing_id = existing.get("sandbox_id")
    new_id = new.get("sandbox_id")
    if existing_id == new_id:
        return existing
    raise ValueError(
        f"Conflicting sandbox state updates: {existing_id!r} != {new_id!r}"
    )


SandboxStateField = Annotated[NotRequired[SandboxState | None], merge_sandbox]


def merge_artifacts(
    existing: list[str] | None, new: list[str] | None
) -> list[str]:
    """Artifacts reducer：合并并去重，保留顺序。"""
    if existing is None:
        return new or []
    if new is None:
        return existing
    return list(dict.fromkeys(existing + new))


def merge_viewed_images(
    existing: dict[str, ViewedImageData] | None,
    new: dict[str, ViewedImageData] | None,
) -> dict[str, ViewedImageData]:
    """ViewedImages reducer：合并字典；空字典表示清空。"""
    if existing is None:
        return new or {}
    if new is None:
        return existing
    if len(new) == 0:
        return {}
    return {**existing, **new}


def merge_todos(existing: list | None, new: list | None) -> list | None:
    """Todos reducer：显式更新覆盖，None 表示不更新。"""
    if new is None:
        return existing
    return new


class PromotedTools(TypedDict):
    """MCP 延迟工具晋升状态。"""

    catalog_hash: str
    names: list[str]


def merge_promoted(
    existing: PromotedTools | None, new: PromotedTools | None
) -> PromotedTools | None:
    """Promoted reducer：按 catalog_hash 作用域合并。"""
    if not new:
        return existing
    if existing is None or existing.get("catalog_hash") != new["catalog_hash"]:
        return {
            "catalog_hash": new["catalog_hash"],
            "names": list(dict.fromkeys(new["names"])),
        }
    return {
        "catalog_hash": existing["catalog_hash"],
        "names": list(dict.fromkeys(existing["names"] + new["names"])),
    }


class ThreadState(AgentState):
    """线程状态：AgentState + 运行时扩展字段。

    每个带 Annotated[...] reducer 的字段都在告诉 LangGraph：
    当多个节点并发更新这个字段时，不要简单覆盖，而要按我定义的语义合并。
    """

    sandbox: SandboxStateField
    thread_data: NotRequired[ThreadDataState | None]
    title: NotRequired[str | None]
    artifacts: Annotated[list[str], merge_artifacts]
    todos: Annotated[list | None, merge_todos]
    uploaded_files: NotRequired[list[dict] | None]
    viewed_images: Annotated[
        dict[str, ViewedImageData], merge_viewed_images
    ]
    promoted: Annotated[PromotedTools | None, merge_promoted]
