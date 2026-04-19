---
name: stage-manager
description: 阶段规划、任务拆解、进度同步、ADR 记录、backlog 认领、会话摘要与归档门禁 skill。
---

> [MANDATORY] 若存在 `SKILL.override.md`，必须先读取；其约束优先级高于本文件。
>
> [MANDATORY] 所有会写入 `.stages/` 或阶段文档的操作必须串行执行。禁止并发运行 `stage:init`、`stage:sync`、`stage:summary`、`stage:intake`、`stage:check`、`stage:switch`、`stage:done`；`sub_agent` 默认只读。

## 0. 硬规则

- `stage:*` 的实际入口是：

```text
python3 <skill-path>/scripts/stage.py <subcommand>
```

- 当前稳定 CLI 入口是 `scripts/stage.py`；`scripts/core/*.py` 是内部实现，除非用户明确要求改脚本实现，否则不要进入 `core/`。
- `.stages/` 是系统运行资产目录，`.stage/` 是交付证据目录；不要混用。
- 不要手动改 `.stages/STAGES.md`、`ADRS.md`、`BACKLOGS.md`、`STAGE_SESSIONS.md`。
- 未知信息写 `TBD` / `null` / `[]`，不要臆造。
- 操作其他阶段时使用 `--file <stage-file>`；`bootstrap` 无 `--file` 语义。

## 1. 三条最短路径

| 场景 | 动作序列 |
| :--- | :--- |
| 新项目，无当前阶段 | `stage:bootstrap` -> 读 `references/best_practice.md` -> `stage:init <name>` -> 补全 `## 1-6` -> `stage:validate` |
| 继续推进当前阶段 | `stage:bootstrap` -> `stage:status` -> `stage:sync` / `stage:check` / `stage:intake` |
| 准备归档 | `stage:validate` -> `stage:summary --stage ...` -> 核对 DoD -> `stage:done` |

新建阶段时，“先 `bootstrap`，再读 `references/best_practice.md`，再 `init`”是硬顺序，不是建议。
若回答里缺少“读取 `references/best_practice.md`”这一步，应视为流程不完整；不要把它折叠进“按模板补全文档”或“参考最佳实践”这类模糊表述。

## 2. 命令映射

| 语义指令 | CLI 子命令 | 用途 |
| :--- | :--- | :--- |
| `stage:bootstrap` | `bootstrap` | 加载会话快照、最近决策、当前阶段与 backlog |
| `stage:init <name>` | `init <name>` | 初始化新阶段并写入索引 |
| `stage:sync "<msg>"` | `sync "<msg>"` | 增量日志；`[ADR]` 前缀触发 ADR 存根与索引 |
| `stage:summary "<text>"` | `summary "<text>"` | 保存会话快照 |
| `stage:summary --stage ...` | `summary --stage ...` | 写入 `## 9. 阶段总结` |
| `stage:intake "<keyword>"` | `intake "<keyword>"` | 从 backlog 认领任务 |
| `stage:status` | `status` | 查看健康度、进度、最近决策与会话摘要 |
| `stage:validate` | `validate` | 校验阶段文档 |
| `stage:check <ID>` | `check <ID>` | 勾选或反勾选任务/验收项 |
| `stage:switch <file>` | `switch <file>` | 切换当前阶段指针 |
| `stage:done` | `done` | 闭环归档；严禁擅自 `--force` |

## 3. 文档与流程规则

- 规范模板：`references/stage_template.md`
- 最佳实践：`references/best_practice.md`

### 3.1 文档结构

- 保留所有 `@section:*` 锚点、章节编号和顺序。
- 只增量修改受影响 section，不要整体重写。
- 新增首条内容时，替换 `- 暂无` 占位，不要并列保留。

### 3.2 Schema 关键约束

- 任务行与验收项格式以 `references/stage_template.md` 为唯一准绳。
- `executor` 仅允许：`agent` / `human` / `sub_agent`
- `verify_by` 仅允许：`task_completion` / `evidence_review` / `metric_threshold` / `artifact_presence`
- `due` 未知时填 `YYYY-MM-DD` 或 `null`

### 3.3 Evidence

- 代码和测试 evidence 保持原始路径。
- 报告、文档、日志、快照等非代码 evidence 统一放 `.stage/`。
- `evidence` 必须优先引用已存在或已确认会产出的对象；拿不准就写 `TBD`。
- 实施型阶段必须产出实际代码、配置或测试变更；只有日志、总结、ADR 不算完成。

### 3.4 ADR

- 用 `stage:sync "[ADR] <title>"` 创建 ADR 存根与索引。
- 只允许增量补全目标阶段文档 `## 8. 关键决策（ADRs）` 的四字段：背景/动机、可选方案、结论、影响/后果。
- 不要手动改 `.stages/ADRS.md`。
- 信息不足时保留 `TBD` 并向用户索取，不要臆造。

### 3.5 Done 门禁

执行 `stage:done` 前，必须确认：

1. 所有 `[P0]` 任务已完成
2. `## 5. 验收标准` 已全部勾选
3. `## 3. 非范围` 的新想法已迁移到 backlog 或后续阶段
4. 会话快照与阶段总结已补齐，或用户明确允许最小归档总结
5. 实施型阶段已具备真实 evidence

不满足时，原样展示缺失项；未经用户授权，不得使用 `--force`。

## 4. 输出要求

- 日志必须指向具体模块、接口、文件、风险或 ADR，避免“已优化”“已处理”。
- 会话快照与阶段总结不是同一动作：
  - 会话快照：`stage:summary "<text>"`
  - 阶段总结：`stage:summary --stage --name ... --goal ... --result ... --audit ... --debt ...`
- 规划型阶段可主要产出文档、方案、审计结果。
- 实施型阶段必须落到代码、配置、测试或构建产物。

### 模块级进展日志最小模板

```text
<模块/接口/文件> | change=<本次变更或当前状态> | evidence=<测试/文档/路径/ADR，未知写 TBD> | next=<下一个明确动作> | risk=<无 / 具体风险>
```

- 一条日志只描述一个模块主题；跨模块请拆开。
- `next` 必须是紧邻的可执行动作。
- `risk` 没有就写 `无`。

## 5. 评估与恢复

- dry-run 评估至少覆盖：新建阶段、推进当前阶段并记录 ADR、归档门禁、单写者约束。

常见恢复动作：

- `bootstrap` 后无当前阶段：`stage:init <name>`
- 需要操作其他阶段：在写命令后追加 `--file <stage-file>`
- `validate` 只有 WARN：继续推进，但在 `done` 前补齐
- `done` 被拒绝：先修文档或 evidence，再重试；未经授权不得 `--force`
