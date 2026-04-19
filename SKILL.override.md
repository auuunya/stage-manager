---
name: stage-manager-override
description: stage-manager 当前仓库覆盖约束
---

- 稳定 CLI 入口是 `scripts/stage.py`。
- `scripts/core/*.py` 是内部实现；除非用户明确要求改脚本实现，否则优先聚焦 `.stages/`、阶段文档和交付物。
