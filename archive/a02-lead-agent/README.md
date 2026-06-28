# A02 · LeadAgent 工厂模式 — 归档快照

这是系列文章 **第 02 篇（LeadAgent 工厂）** 结束时的独立项目快照。

## 说明

- 包含 A02 结束时完整的 `src/`、`tests/`、`docs/` 与项目配置。
- 如需查看最新开发版本，请回到根目录 `deerflow-harness/`。

## 运行

请回到仓库根目录 `deerflow-harness/` 执行（共享根目录的 `.venv`）：

```bash
PYTHONPATH=archive/a02-lead-agent/src uv run pytest archive/a02-lead-agent/tests -q
```

预期：`20 passed`

## 与根目录的关系

- `archive/a02-lead-agent/`：A02 结束时的状态（LeadAgent 工厂 + features + middlewares）
- `deerflow-harness/`（根目录）：最新开发版本，继续承载 A03+ 的代码
