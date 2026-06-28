# 02 · LeadAgent 工厂模式

## 1. 这层在做什么

把 A01 那张硬编码的单节点 StateGraph，升级为**可按请求独立创建的工厂入口**。

A01 的 `make_lead_agent()` 返回一张全局复用的编译图。这在单测里没问题，但放到真实服务里会出大事：多个用户请求共享同一张图的状态，一个请求的上下文会泄漏到另一个请求里。工厂模式的核心思想是**每次调用都生成新的 agent 实例**，并且通过声明式配置（`RuntimeFeatures`）决定中间件链的组装方式，而不是把节点和边写死在代码里。

本层做三件事：

1. 提供 `create_deerflow_agent(model, tools, features=...)` 纯参数 SDK 工厂。
2. 定义 `RuntimeFeatures` 声明式特性开关，用布尔值或自定义中间件实例控制链上插什么。
3. 实现 `@Next` / `@Prev` 装饰器，让额外中间件能按锚点精确定位插入位置。

## 2. 不这样会坏什么

**坏点一：单例图被多请求污染**

如果全局只编译一张图，LangGraph 的 checkpoint 和内部状态会被并发请求互相覆盖。用户 A 的沙箱 id 可能突然出现在用户 B 的响应里，且没有任何报错。

**坏点二：节点硬编码无法复用**

A01 的 `_lead_node` 里把 AI 消息内容和 artifacts 写死了。每改一个业务逻辑都要改这张图，无法根据不同场景（带沙箱 / 不带沙箱、需要循环检测 / 不需要）复用同一套基础设施。

**坏点三：测试困难**

硬编码的图无法注入 mock 中间件。想测「循环检测触发时会不会打断 agent」，你得先把循环检测逻辑写进节点里，而不是插拔一个中间件。

## 3. 关键概念

### RuntimeFeatures（声明式特性开关）

```python
@dataclass
class RuntimeFeatures:
    sandbox: bool | AgentMiddleware = True
    loop_detection: bool | AgentMiddleware = True
    auto_title: bool | AgentMiddleware = False
    memory: bool | AgentMiddleware = False
```

每个字段三种取值：
- `True`：工厂自动插入默认占位中间件。
- `False`：跳过该中间件。
- `AgentMiddleware` 实例：用户传入自定义实现，覆盖默认行为。

### 中间件链（Middleware Chain）

`create_deerflow_agent` 在内部调用 `_assemble_from_features`，按固定顺序生成中间件列表：

1. `SandboxMiddleware`（如果启用）
2. `DanglingToolCallMiddleware`（始终存在）
3. `LoopDetectionMiddleware`（如果启用）
4. `MemoryMiddleware`（如果启用）
5. `AutoTitleMiddleware`（如果启用）
6. 插入 `extra_middleware`（按 `@Next` / `@Prev` 定位）

这个顺序与原版 DeerFlow 的精神一致，但 A02 只保留最小子集，后续篇章逐步扩展。

### @Next / @Prev 定位

```python
@Next(SandboxMiddleware)
class MyMiddleware(AgentMiddleware):
    name = "my_middleware"
```

`@Next(SandboxMiddleware)` 表示「把我插在 `SandboxMiddleware` 之后」。工厂在组装链时读取 `type(mw)._next_anchor` 或 `_prev_anchor`，找到锚点索引并插入。

## 4. 怎么最小实现

### 4.1 features.py — 声明式特性与装饰器

```python
@dataclass
class RuntimeFeatures:
    sandbox: bool | AgentMiddleware = True
    loop_detection: bool | AgentMiddleware = True
    auto_title: bool | AgentMiddleware = False
    memory: bool | AgentMiddleware = False


def Next(anchor: type[AgentMiddleware]):
    def decorator(cls: type[AgentMiddleware]) -> type[AgentMiddleware]:
        cls._next_anchor = anchor
        return cls
    return decorator


def Prev(anchor: type[AgentMiddleware]):
    def decorator(cls: type[AgentMiddleware]) -> type[AgentMiddleware]:
        cls._prev_anchor = anchor
        return cls
    return decorator
```

纯数据、无副作用。装饰器只做一件事：在类上设置 `_next_anchor` / `_prev_anchor` 属性。

### 4.2 middlewares.py — 占位中间件

```python
class SandboxMiddleware(AgentMiddleware):
    name = "sandbox"

class DanglingToolCallMiddleware(AgentMiddleware):
    name = "dangling_tool_call"

class LoopDetectionMiddleware(AgentMiddleware):
    name = "loop_detection"

class MemoryMiddleware(AgentMiddleware):
    name = "memory"

class AutoTitleMiddleware(AgentMiddleware):
    name = "auto_title"
```

A02 只保留类名和 `name`，方法全部继承 `AgentMiddleware` 的默认空实现。测试只验证「是否按顺序出现」，真实逻辑留给 A03。

### 4.3 lead_agent.py — 工厂核心

```python
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
```

互斥规则：
- `middleware` 与 `features`/`extra_middleware` 不能同时传。
- `extra_middleware` 只能配合 `features` 使用。

内部流程：
1. 校验互斥参数。
2. 确定 `state_schema`（默认 `ThreadState`）。
3. `_assemble_from_features(features)` 生成中间件链。
4. 调用 `langchain.agents.create_agent(...)` 并返回。

### 4.4 A01 兼容

`make_lead_agent(config=None)` 保留为薄包装，内部构造默认 `RuntimeFeatures()` 并调用 `create_deerflow_agent`。`tests/test_a01.py` 无需改动即可继续通过。

## 5. 验收

运行：

```bash
uv run pytest -q
```

预期输出：

```
20 passed
```

测试覆盖：
- `create_deerflow_agent` 返回可编译、可 invoke 的 `CompiledStateGraph`
- 不同 `RuntimeFeatures` 开关产生不同长度的中间件链
- `middleware` + `features` 同传抛 `ValueError`
- `@Next` 中间件出现在锚点之后，`@Prev` 出现在锚点之前
- 无锚点的 `extra_middleware` 放在链尾
- 锚点不存在时抛 `ValueError`
- 自定义 `AgentMiddleware` 实例直接替换默认占位
- A01 全部 9 个断言继续通过

## 6. 踩过的坑 + 进阶

**坑：`langchain.agents.create_agent` 对 `AgentMiddleware` 的处理方式**

原版 DeerFlow 基于自己 fork 的 `AgentMiddleware`，而 `langchain>=1.3.11` 内置的 `create_agent` 对中间件的支持可能略有不同。A02 的实现先用占位中间件跑通最小图，确认 `create_agent` 能接受列表形式的 middleware 参数。如果未来版本有 breaking change，可在 `create_deerflow_agent` 内部降级为手动 `StateGraph` 装配，但保持对外接口不变。

**坑：A01 测试依赖 `artifacts` 字段**

A01 的 `test_make_lead_agent_compiles_and_invokes` 断言 `"a01-output.md" in result["artifacts"]`。但 `create_agent` 默认不会返回这个 artifact。解决方案：`make_lead_agent` 内部注入一个 `_A01ArtifactMiddleware`，在 `after_agent` 里把 artifact 追加到响应中，保持 A01 测试零改动。

**坑：mock model 需要 `bind_tools`**

`create_agent` 在内部会调用 `model.bind_tools(tools)`，即使 tools 为空列表。测试用的 mock model 必须实现 `bind_tools` 方法，否则会在运行时抛 `NotImplementedError`。

**进阶：原版 config-driven 工厂 `make_lead_agent`**

A02 只实现了纯参数 SDK 工厂 `create_deerflow_agent`。A04 会引入配置系统，届时 `make_lead_agent(config)` 将读取 `config.yaml` / `SOUL.md`，把配置解析成 `RuntimeFeatures` 后再调用 `create_deerflow_agent`。两层工厂的关系：

- `create_deerflow_agent`：SDK 级，无配置文件，适合嵌入第三方应用。
- `make_lead_agent`：应用级，读配置，适合 DeerFlow 自托管部署。

---

下一篇：[03 · 中间件链详解](./03-middlewares.md)——给这些占位中间件填入真实逻辑，理解横切关注点如何独立、可组合。
