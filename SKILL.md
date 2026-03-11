---
name: stage-manager
description: 项目阶段管理与归档技术规格书。定义资产归口结构（.stages/）、核心指令集、及参考规范（references/）。触发词：计划、阶段拆解、进度同步、完成度检查、归档、未完成任务迁移。
---

## 1. 核心交互指令

| 指令                 | CLI                                                           | 技术用途                          |
| :------------------- | :------------------------------------------------------------ | :-------------------------------- |
| `stage:bootstrap`    | `python3 <skill-path>/scripts/stage_manager.py bootstrap`     | **[LOAD]** 加载会话快照与依赖感知 |
| `stage:summary`      | `python3 <skill-path>/scripts/stage_manager.py summary "<t>"` | **[SAVE]** 压缩并保存当前会话快照 |
| `stage:intake "<k>"` | `python3 <skill-path>/scripts/stage_manager.py intake "<k>"`  | **[INTAKE]** 从 Backlog 认领任务  |
| `stage:init`         | `python3 <skill-path>/scripts/stage_manager.py init <name>`   | 初始化资产骨架并填充开启新阶段    |
| `stage:sync`         | `python3 <skill-path>/scripts/stage_manager.py sync "<msg>"`  | 增量日志记录；[ADR] 触发索引同步  |
| `stage:status`       | `python3 <skill-path>/scripts/stage_manager.py status`        | 查看看板、进度及最近详情下钻      |
| `stage:done`         | `python3 <skill-path>/scripts/stage_manager.py done`          | 闭环归档 (含 DoD 硬门禁检查)      |

## 2. 工程化核心机制

### 2.1 DoD (Definition of Done) 验收硬门禁

- **逻辑**：在归档时自动扫描 `## 5. 验收标准` 章节。
- **红线**：若存在任何未完成项，归档将被拒绝，确保功能实现与质量验收不脱节。

### 2.2 Backlog 认领机制 (stage:intake)

- **逻辑**：支持从 `BACKLOGS.md` 中按关键字认领任务并自动注入当前活跃阶段。

## 3. 核心参考规范 (References)

Agent 执行过程中必须严格参考以下文件以确保输出一致性：

- `references/stage_template.md`: **[强制]** 阶段文档的标准 Schema 结构。
- `references/best_practice.md`: **[强制]** 任务拆解（INVEST）、验收标准编写及日志规范。

## 4. 标准阶段生命周期

1. **探测**: 会话开启必执行 `bootstrap` 并对齐 `best_practice.md`。
2. **认领**: 若存在遗留任务，执行 `intake` 进行捞取。
3. **执行**: 定位活跃阶段开展工作，任务拆解必须符合 **INVEST** 原则。
4. **同步**: 变更代码后执行 `sync`；架构变更触发 ADRS 同步。
5. **闭环**: 验收标准全量通过后执行 `done`。
