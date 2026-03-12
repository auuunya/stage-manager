---
name: stage-manager
description: 项目阶段管理与归档技术规格书。定义资产归口结构（.stages/）、阶段文档标准结构、核心指令集、及参考规范（references/）。用于处理计划制定、阶段拆解、进度同步、会话恢复、完成度检查、ADR 决策记录、Backlog 认领、归档与未完成任务迁移等场景。
---

> [重要] 约束优先级说明：
> 若存在 `SKILL.override.md`，Agent 在执行任何 stage-manager 工作前必须先读取该文件；一旦读取成功，其约束优先级高于本文件其余说明。

## 1. 核心交互指令

> `stage:*` 仅为技能内语义别名；实际执行时，必须映射为 `python3 <skill-path>/scripts/stage_manager.py <subcommand>`。

> `stage:bootstrap` 用于恢复全局项目上下文，不提供单阶段 `--file` 语义。

| 指令                 | CLI                                                           | 技术用途                                               |
| :------------------- | :------------------------------------------------------------ | :----------------------------------------------------- |
| `stage:bootstrap`    | `python3 <skill-path>/scripts/stage_manager.py bootstrap`     | [LOAD] 加载会话快照、最近决策、活跃阶段与 Backlog 概览 |
| `stage:summary`      | `python3 <skill-path>/scripts/stage_manager.py summary "<t>"` | [SAVE] 压缩并保存当前会话快照                          |
| `stage:intake "<k>"` | `python3 <skill-path>/scripts/stage_manager.py intake "<k>"`  | [INTAKE] 从 Backlog 认领任务并注入阶段                 |
| `stage:init <name>`  | `python3 <skill-path>/scripts/stage_manager.py init <name>`   | 初始化新阶段文档并写入资产索引                         |
| `stage:sync "<msg>"` | `python3 <skill-path>/scripts/stage_manager.py sync "<msg>"`  | 增量日志记录；`[ADR]` 前缀触发 ADR 索引与存根          |
| `stage:status`       | `python3 <skill-path>/scripts/stage_manager.py status`        | 查看项目健康度、进度、最近决策与会话摘要               |
| `stage:validate`     | `python3 <skill-path>/scripts/stage_manager.py validate`      | 校验当前或指定阶段文档结构                             |
| `stage:done`         | `python3 <skill-path>/scripts/stage_manager.py done`          | 闭环归档（含 DoD 硬门禁检查，默认严禁擅自 `--force`）  |

补充说明：

- 当需要操作非当前活跃阶段时，优先使用 `--file <stage-file>` 指定目标文档。
- 所有元数据更新、日志追加、ADR 记录、会话快照与任务认领，均应优先通过脚本完成，而不是手动维护索引文件。

## 2. 工程化核心机制

### 2.1 DoD (Definition of Done) 验收硬门禁

- 归档时自动扫描 `## 5. 验收标准`。
- 若存在任何未完成项，归档默认拒绝执行。
- `--force` 仅在用户明确授权时允许使用。

### 2.2 Backlog 认领机制 (`stage:intake`)

- 支持从 `BACKLOGS.md` 中按关键字认领任务。
- 认领后的任务应注入当前或指定阶段的 `## 4. 任务拆解`。
- 普通任务行应尽量归一为结构化任务格式。

### 2.3 ADR 决策同步机制

- 当 `stage:sync` 的消息以 `[ADR]` 前缀开头时，脚本负责：
  - 生成唯一 ADRS 编号
  - 更新 `ADRS.md` 索引
  - 在阶段文档的 `## 8. 关键决策（ADRs）` 中写入 ADR 存根
- Agent 负责继续补全 ADR 的内容，不得停留在 TBD。

### 2.4 阶段文档强结构约束

- 阶段文档必须遵循 `references/stage_template.md` 的标准 schema。
- 所有 `@section:*` 锚点、章节编号和章节顺序必须保留。
- 更新已有阶段文档时，优先增量修改受影响 section，不得整体重写未变更内容。

## 3. 核心参考规范 (References)

Agent 在执行过程中必须严格参考以下文件，以确保输出一致性：

- `references/stage_template.md`: [强制] 阶段文档的标准 schema 结构。
- `references/stage_example.md`: [强制] 阶段文档的标准示例，用于对齐风格、粒度和字段写法。
- `references/best_practice.md`: [强制] 任务拆解（INVEST）、验收标准编写、风险记录与日志规范。

## 4. 标准阶段生命周期

1. **探测**：当进入项目阶段管理场景时，先执行 `stage:bootstrap`；随后读取 `references/best_practice.md` 以对齐任务拆解、日志与验收标准。
2. **认领**：若存在遗留任务或 Backlog 命中项，执行 `stage:intake` 进行捞取。
3. **初始化**：若需新建阶段，执行 `stage:init`；随后根据当前需求填充目标、范围、任务拆解、验收标准和风险。
4. **执行**：定位活跃阶段开展工作，任务拆解必须符合 INVEST 原则，且优先使用结构化任务格式。
5. **同步**：发生代码、文档或决策变更后执行 `stage:sync`；架构变更或策略分歧使用 `[ADR]` 前缀触发决策记录。
6. **校验**：在归档或关键交付前执行 `stage:validate` 检查文档结构和字段完整性。
7. **闭环**：验收标准全量通过后执行 `stage:done`，完成未完成任务迁移、阶段总结与归档。

## 5. 输出与维护原则

- 未知信息使用 `TBD`、`null` 或空数组表示，不得臆造日期、依赖、负责人或里程碑。
- 日志必须描述具体模块、具体动作或具体 ADR，不得使用"优化了代码""处理了一些问题"等模糊表述。
- 若 section 暂无内容，保留其结构；新增首条内容时，应替换 `- 暂无` 占位，而不是并列保留。
- 归档前应确认：
  - 所有 P0 任务已完成
  - `## 5. 验收标准` 全量通过
  - `## 3. 非范围` 的新想法已迁移
  - `## 9. 阶段总结` 已补充，或允许脚本生成最小归档总结
- 状态语义说明：
  - `COMPLETED`：阶段目标与 DoD 已完整满足，并已完成归档。
  - `ARCHIVED`：阶段已关闭并归档，但可能通过强制收尾或非完整闭环方式结束。
