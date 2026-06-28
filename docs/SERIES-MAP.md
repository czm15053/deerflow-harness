# 系列地图

本仓库配套 16 篇中文文章，从零搭一个最小但可生长的 **LangGraph agent harness**。  
每篇文章固定六段体例：

1. 这层在做什么
2. 不这样会坏什么（failure-first）
3. 关键概念
4. 怎么最小实现（本仓库代码走读）
5. 验收（可运行的测试）
6. 踩过的坑 + 进阶

文章灵感来自「dacong001 — deerflow 源码解析」18 集字幕的 failure-first 讲法；落地代码完全重写，是独立的教学项目。

---

## 文章与代码对照

| 篇号 | 主题 | 参考字幕 | 本仓库落点 | 核心设计思想 |
| --- | --- | --- | --- | --- |
| 00 | 设计理念与架构总览 | P1 | `docs/00-overview.md` | 为什么不用 while 循环 |
| 01 | LangGraph 核心 + ThreadState | P2、P3 | `src/deerflow_harness/thread_state.py` | reducer 解决并发写入冲突 |
| 02 | LeadAgent 工厂模式 | P4 | `src/deerflow_harness/lead_agent.py` | 每请求独立 agent + 配置驱动 |
| 03 | 中间件链详解 | P5 | `src/deerflow_harness/middlewares/` | 横切关注点独立、可组合 |
| 04 | 配置系统 | P10 | `src/deerflow_harness/config.py` | Pydantic 校验 + mtime 热重载 |
| 05 | 模型工厂 | P11 | `src/deerflow_harness/models/factory.py` | 反射加载 + thinking/stream_usage 默认 |
| 06 | 工具系统 | P6 | `src/deerflow_harness/tools.py` | 反射加载 + 工具组过滤 |
| 07 | 沙箱执行系统 | P7 | `src/deerflow_harness/sandbox/` | 线程隔离 + 虚拟路径翻译 |
| 08 | 子智能体系统 | P8 | `src/deerflow_harness/subagents/` | 双线程池 + 并发限制 |
| 09 | 记忆系统 | P9 | `src/deerflow_harness/memory/` | 异步防抖 + 置信度过滤 |
| 10 | Skills 技能系统 | P13 | `src/deerflow_harness/skills/` | SKILL.md + 白名单工具 |
| 11 | MCP 协议集成 | P12 | `src/deerflow_harness/mcp/` | 懒加载 + 多 server 管理 |
| 12 | Gateway API | P14 | `src/deerflow_harness/gateway/` | SSE 流式 + RunManager |
| 13 | 测试 + 可观测性 | P16 | `tests/` 与 tracing | 边界测试 + tracing root |
| 14 | 前端架构 | P15 | `frontend/`（可选） | EventSource 消费 SSE |
| 15 | 部署与运维 | P17 | `docker/`（可选） | nginx + docker-compose |
| 16 | 实战练习 | P18 | `docs/16-hands-on.md` | 综合练习 |

---

## 阅读建议

- **按顺序读**：后一篇的代码依赖前一篇的抽象。
- **边看边跑**：每篇都有 `tests/test_a0x.py`，读完立即 `uv run pytest -q` 验证。
- **不急着追全功能**：每篇只解决一个真实坏点，把「为什么」吃透再往下。

---

## 状态

- ✅ 00 导论已就位
- ⏳ 01–16 逐步推进中
