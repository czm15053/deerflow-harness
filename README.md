# deerflow-harness

从零搭一个 **LangGraph + LangChain**（Python 3.12+）的 AI agent harness，配套 **16 篇中文系列文章**。

每一层都是：**一篇讲「为什么」的文章 + 一段最小可跑代码 + 一组测试**，三者一体，可独立运行验证。

## 这是什么

不是又一个 ReAct demo，而是把「一个 agent 从骨架到能上生产」要长出来的每一层，一层一篇拆开讲。每篇固定六段：

1. 这层在做什么
2. 不这样会坏什么（先讲 failure，再讲 solution）
3. 关键概念
4. 怎么最小实现（本仓库代码）
5. 验收（如何证明它真的工作）
6. 踩过的坑 + 进阶（原领域实践是怎么做得更深）

## 文章目录

见 [`docs/`](./docs)，第 00 篇为导论。  
完整学习路线与代码对照请看 [`docs/SERIES-MAP.md`](./docs/SERIES-MAP.md)。

## 运行

```bash
uv sync
uv run pytest -q
```

## 版本与归档

本仓库采用**双版本**机制：

- **根目录**（`deerflow-harness/`）：最新开发版本，继续承载 A03+ 的代码演进。
- **`archive/` 目录**：每篇文章结束时的**独立可运行快照**，完整保存该篇的代码、测试与文档。

### 当前归档

| 归档 | 主题 | 测试数 | 运行方式（从仓库根目录执行） |
|------|------|--------|------------------------------|
| `archive/a00-overview/` | 导论（无代码） | 1 passed | `PYTHONPATH=archive/a00-overview/src uv run pytest archive/a00-overview/tests -q` |
| `archive/a01-state-graph/` | ThreadState + 最小图 | 9 passed | `PYTHONPATH=archive/a01-state-graph/src uv run pytest archive/a01-state-graph/tests -q` |
| `archive/a02-lead-agent/` | LeadAgent 工厂 | 20 passed | `PYTHONPATH=archive/a02-lead-agent/src uv run pytest archive/a02-lead-agent/tests -q` |

每个归档都是**结构独立**的项目（有自己的 `pyproject.toml`、`src/`、`tests/`、`docs/`），但为了节省空间，所有归档共享根目录的 `.venv`，通过 `PYTHONPATH` 指向对应归档的 `src/` 来运行测试。

## 状态

- 系列：第 00–02 篇已就位，A03+ 逐步推进中。
- 代码：随每篇逐层加入。