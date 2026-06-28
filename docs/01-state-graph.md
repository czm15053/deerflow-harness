# 01 · LangGraph 核心 + ThreadState 状态管理

## 1. 这层在做什么

让 agent 的多次 LLM 调用之间**有状态**。

LLM API 本身是无状态的：你每次调用都要把历史消息全拼进去。agent 不一样，它要remember 上一步调了什么工具、用户有没有上传文件、当前对话是不是已经创建了沙箱。这些跨调用的信息需要一个持续存在的对象来承载。

本层做两件事：

1. 定义一张 `ThreadState`，在 LangGraph 的 `AgentState` 基础上扩展线程运行时字段。
2. 给会并发写入的字段配上 **reducer**，让 LangGraph 知道多个节点同时更新同一个字段时该怎么合并，而不是后一个覆盖前一个。

## 2. 不这样会坏什么

最朴素的 agent 长这样：

```python
messages = []
while True:
    reply = llm.invoke(messages)
    if not reply.tool_calls:
        break
    for call in reply.tool_calls:
        messages.append(run_tool(call))
```

它会在三个地方坏掉。

**坏点一：并发写入静默丢数据**

假设 agent 同时派了两个子任务，子任务 A 搜索出结果，子任务 B 执行了代码，两者都想把结果追加到 messages 或某个产物列表里。如果它们直接操作同一个 Python list，最终后写入的会覆盖先写入的——没有报错，没有警告，但数据就是少了。

**坏点二：没有 schema，无法持久化**

一个普通 `dict` 里可以塞任何东西，包括不可序列化的对象。等到你想把状态存进 SQLite、下次对话恢复时，根本不知道哪些字段该存、类型是什么。代码升级后，旧状态怎么迁移也毫无章法。

**坏点三：业务规则被淹没在赋值逻辑里**

比如「同一个输出文件只能出现一次」，如果你每次都用 `state["artifacts"] = new_list` 赋值，去重逻辑必须散落在每个节点里。节点一多，规则就被复制得到处都是，改一处漏一处。

## 3. 关键概念

### State 是一个 TypedDict

LangGraph 用 `TypedDict` 声明状态 schema：字段名、类型、哪些是可选的，全部写死。这带来三个好处：

- 可被序列化，checkpoint 能存能取。
- 静态类型检查能在写代码阶段发现字段名拼错。
- 字典语法访问，使用摩擦小。

### Reducer 是并发写入的合并函数

`Annotated[field_type, reducer_function]` 告诉 LangGraph：节点返回的更新不是最终值，而是「增量」；框架会把多个节点的增量按 reducer 定义的语义合并到现有状态上。

LangGraph 内置了 `add_messages` 用于 messages：追加，且按消息 id 替换同 id 消息（流式输出就靠这个）。我们自己的字段需要自己写 reducer。

### ThreadState 是业务状态的载体

除了 messages，agent 还需要：

- `sandbox`：当前线程的沙箱 id。
- `thread_data`：workspace / uploads / outputs 的物理路径映射。
- `artifacts`：要展示给用户的产物文件列表。
- `viewed_images`：已经被 `view_image` 读取过的图片，注入后清空。
- `todos`：plan 模式下的任务列表。
- `promoted`：延迟加载的 MCP 工具晋升名单。

这些字段里，凡是可能被多个节点并发写的，都要加 reducer。

## 4. 怎么最小实现

本仓库的落点：

- `src/deerflow_harness/thread_state.py`：定义 `ThreadState` 和所有 reducer。
- `src/deerflow_harness/lead_agent.py`：一张单节点 `StateGraph`，用来验证 ThreadState 能跑通。

### 4.1 继承 AgentState

```python
from langchain.agents import AgentState

class ThreadState(AgentState):
    sandbox: Annotated[NotRequired[SandboxState | None], merge_sandbox]
    thread_data: NotRequired[ThreadDataState | None]
    title: NotRequired[str | None]
    artifacts: Annotated[list[str], merge_artifacts]
    todos: Annotated[list | None, merge_todos]
    uploaded_files: NotRequired[list[dict] | None]
    viewed_images: Annotated[dict[str, ViewedImageData], merge_viewed_images]
    promoted: Annotated[PromotedTools | None, merge_promoted]
```

`AgentState` 已经带了 `messages: Annotated[list[AnyMessage], add_messages]`，我们只需要叠加自己的字段。

### 4.2 三个典型 reducer

**merge_artifacts：有序去重**

```python
def merge_artifacts(existing, new):
    if existing is None:
        return new or []
    if new is None:
        return existing
    return list(dict.fromkeys(existing + new))
```

用 `dict.fromkeys` 去重同时保留顺序。业务规则「同名文件不重复」被直接表达在数据结构里。

**merge_sandbox：id 冲突抛错**

```python
def merge_sandbox(existing, new):
    if new is None:
        return existing
    if existing is None:
        return new
    if existing.get("sandbox_id") == new.get("sandbox_id"):
        return existing
    raise ValueError("Conflicting sandbox state updates")
```

沙箱 id 不一致说明生命周期出了 bug，必须失败，而不是悄悄选一个。

**merge_viewed_images：空字典清空**

```python
def merge_viewed_images(existing, new):
    if new is None:
        return existing
    if len(new) == 0:
        return {}
    return {**existing, **new}
```

`view_image` 注入图片后，middleware 返回 `{}` 清空已查看图片，避免下一轮重复注入撑爆上下文。

### 4.3 最小图

```python
from langgraph.graph import END, StateGraph

def _lead_node(state: ThreadState):
    return {
        "messages": [AIMessage(content="A01 state graph is running.")],
        "artifacts": ["a01-output.md"],
    }

def make_lead_agent(config=None):
    builder = StateGraph(ThreadState)
    builder.add_node("lead", _lead_node)
    builder.set_entry_point("lead")
    builder.add_edge("lead", END)
    return builder.compile()
```

这张图只有一个节点，但已经能让 LangGraph 走完整的状态更新流程：节点返回更新 → reducer 合并 → 得到最终状态。

## 5. 验收

运行：

```bash
uv run pytest -q
```

应该看到：

```
9 passed
```

测试覆盖：

- `merge_artifacts` 去重与 None 处理
- `merge_sandbox` 允许幂等写入、拒绝冲突 id
- `merge_viewed_images` 合并与清空语义
- `merge_promoted` 按 catalog_hash 切换作用域
- `make_lead_agent` 编译后 `invoke` 返回正确的 messages 和 artifacts
- `ThreadState` 能接受自定义字段

## 6. 踩过的坑 + 进阶

**坑：reducer 只对节点返回的更新生效**

如果你在图外直接 `state["artifacts"].append(...)`，LangGraph 根本不知道，也不会调用 reducer。reducer 是框架在应用节点返回值时使用的，不是 Python 列表的魔法方法。

**坑：NotRequired 字段在图中首次出现为 None**

很多 reducer 要处理 `existing is None` 的情况，否则第一次运行就会抛错。

**进阶：checkpoint 与状态持久化**

本层只做了状态定义。要让对话断线后能恢复，需要给图配上 `checkpointer`（如 `SqliteSaver`）。LangGraph 会在每个节点执行后自动把 `ThreadState` 写进 checkpoint，下次从 `thread_id` 恢复。A12 Gateway 层会再展开。

**进阶：reducer 是业务规则的固化**

「同名文件不重复」「沙箱 id 不一致要报错」「 viewed_images 注入后清空」——这些不是注释，而是可执行的 reducer。把业务规则写进状态合并逻辑，比散落在各个节点里可靠得多。

---

下一篇：[02 · LeadAgent 工厂模式](./02-lead-agent.md)——把这张裸图变成一个能按请求动态组装的 agent。
