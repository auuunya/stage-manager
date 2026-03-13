---
name: stage-manager
description: 项目阶段管理与归档专家。用于初始化阶段、同步进度、记录 ADR、认领 backlog、执行完成度检查、保存会话摘要、归档阶段，以及维护符合 references/stage_template.md 的阶段文档。
---

> [重要] 若存在 `SKILL.override.md`，Agent 在执行任何 stage-manager 工作前必须先读取该文件；其约束优先级高于本文件。

## 1. 核心交互指令

> `stage:*` 仅为技能内语义别名；实际执行时，必须映射为：
> `python3 <skill-path>/scripts/stage_manager.py <subcommand>`

> `stage:bootstrap` 用于恢复全局项目上下文，不提供单阶段 `--file` 语义。

| 指令                  | CLI                                                           | 技术用途                                               |
| :-------------------- | :------------------------------------------------------------ | :----------------------------------------------------- |
| `stage:bootstrap`     | `python3 <skill-path>/scripts/stage_manager.py bootstrap`     | [LOAD] 加载会话快照、最近决策、活跃阶段与 Backlog 概览 |
| `stage:summary "<t>"` | `python3 <skill-path>/scripts/stage_manager.py summary "<t>"` | [SAVE] 压缩并保存当前会话快照                          |
| `stage:intake "<k>"`  | `python3 <skill-path>/scripts/stage_manager.py intake "<k>"`  | [INTAKE] 从 Backlog 认领任务并注入阶段                 |
| `stage:init <name>`   | `python3 <skill-path>/scripts/stage_manager.py init <name>`   | 初始化新阶段文档并写入资产索引                         |
| `stage:sync "<msg>"`  | `python3 <skill-path>/scripts/stage_manager.py sync "<msg>"`  | 增量日志记录；`[ADR]` 前缀触发 ADR 索引与存根          |
| `stage:status`        | `python3 <skill-path>/scripts/stage_manager.py status`        | 查看项目健康度、进度、最近决策与会话摘要               |
| `stage:validate`      | `python3 <skill-path>/scripts/stage_manager.py validate`      | 校验当前或指定阶段文档结构                             |
| `stage:done`          | `python3 <skill-path>/scripts/stage_manager.py done`          | 闭环归档（含 DoD 硬门禁检查，默认严禁擅自 `--force`）  |

补充说明：

- 当需要操作非当前活跃阶段时，优先使用 `--file <stage-file>` 指定目标文档。
- 所有元数据更新、日志追加、ADR 记录、会话快照与任务认领，均应优先通过脚本完成，而不是手动维护索引文件。
- 除非用户明确要求修改 stage-manager 技能本身，否则 Agent 只应使用脚本，不应修改 `scripts/` 下代码。

## 2. 阶段文档 schema 语义

阶段文档必须遵循 `references/stage_template.md` 的标准结构，并与 `references/stage_example.md` 的字段写法、粒度和条目组织方式保持一致。

### 2.1 任务字段语义

任务行标准格式：

- [ ] [P0] [TASK-001] 任务名称 | owner=unassigned | executor=agent | skills=[] | task_depends_on=[] | acceptance=[AC-001] | deliverables=[] | evidence=[] | due=YYYY-MM-DD

**字段说明：**

- `owner`：负责人。未知时使用 `unassigned`。
- `executor`：执行主体，仅允许 `agent`、`human`、`sub_agent`。
- `skills`：执行该任务时可引用的技能标签列表。
- `task_depends_on`：任务级依赖，仅填写任务 ID。
- `acceptance`：该任务直接支撑的验收项 ID 列表。
- `deliverables`：该任务的交付物标识，可为逻辑名称，不强制要求为文件路径。
- `evidence`：用于证明任务完成情况的证据路径列表。
- `due`：目标日期；未知时使用 `YYYY-MM-DD` 或 `null`，不得臆造。

### 2.2 验收项字段语义

验收项标准格式：

- [ ] [AC-001] 功能性 | verify_by=task_completion | required_tasks=[TASK-001] | required_checks=[critical_path_test] | evidence=[]

**字段说明：**

- `verify_by`：验收方式，仅允许以下固定值：
  - `task_completion`
  - `evidence_review`
  - `metric_threshold`
  - `artifact_presence`
- `required_tasks`：该验收项依赖的任务 ID 列表。
- `required_checks`：该验收项必须满足的检查点列表。
- `evidence`：用于证明该验收项通过的证据路径列表。

### 2.3 evidence 约定

- 代码类 evidence 可保持项目原始路径，如 `src/...`、`tests/...`、`configs/...`。
- 非代码类 evidence 必须统一放在 `.stage/` 下。
- 推荐目录：
  - `.stage/reports/`：验收报告、性能报告、安全报告、阶段审查报告
  - `.stage/docs/`：设计文档、ADR、补充说明
  - `.stage/logs/`：进度日志、变更日志、审计日志
  - `.stage/snapshots/`：指标快照、状态快照、测试结果汇总
- 每个 [P0] 实施任务建议至少提供一份可读摘要 evidence，便于 Agent 验收。
- 每个阶段建议包含一个“阶段验收”任务，产出 `.stage/reports/stage-review.md`。

## 3. 工程化核心机制

### 3.1 DoD 验收硬门禁

- `stage:done` 前必须检查 `## 5. 验收标准`。
- 若存在未勾选项，归档默认拒绝执行。
- `--force` 仅在用户明确授权时允许使用。
- 当进度未达到 100% 或 DoD 未通过时，必须先列出 `[Pending Tasks]`，不得擅自强行收尾。

### 3.2 Backlog 认领机制

- 支持从 `BACKLOGS.md` 中按关键字认领任务。
- 认领后的任务应注入当前或指定阶段的 `## 4. 任务拆解`。
- 普通任务行应尽量归一为结构化任务格式。

### 3.3 ADR 决策同步机制

- 当 `stage:sync` 的消息以 `[ADR]` 前缀开头时，脚本负责：
  - 生成唯一 ADRS 编号
  - 更新 `ADRS.md` 索引
  - 在阶段文档的 `## 8. 关键决策（ADRs）` 中写入 ADR 存根
- Agent 必须继续补全 ADR 内容，不得停留在 TBD。
- ADR 至少补全以下字段：
  - 背景/动机
  - 可选方案
  - 结论 -
  - 影响/后果

### 3.4 阶段文档强结构约束

- 所有 `@section:\*` 锚点、章节编号和章节顺序必须保留。
- 更新已有阶段文档时，优先增量修改受影响 section，不得整体重写未变更内容。
- 若 section 当前为 `- 暂无` 且需要新增首条记录，必须替换该占位，而不是并列保留。

## 4. 核心参考规范

Agent 在执行过程中必须参考以下文件：

- `references/stage_template.md`：阶段文档的唯一 schema 来源。
- `references/stage_example.md`：阶段文档的标准实例化样例。
- `references/best_practice.md`：任务拆解、验收标准、风险记录与日志规范。

## 5. 标准阶段生命周期

1. 探测：进入阶段管理场景后，首个操作必须是 `stage:bootstrap`；随后读取 `references/best_practice.md`。
2. 认领：若存在遗留任务或 Backlog 命中项，执行 `stage:intake`。
3. 初始化：若需新建阶段，执行 `stage:init <name>`；然后补全目标、范围、任务、验收标准与风险。
4. 执行：定位活跃阶段开展工作，任务拆解应符合 **INVEST** 原则，优先使用结构化任务格式。
5. 同步：发生代码、文档或决策变更后执行 `stage:sync`；架构决策使用 [ADR] 前缀触发 ADR 流程。
6. 校验：在关键交付或归档前执行 `stage:validate` 检查结构与字段完整性。
7. 闭环：满足验收标准后执行 `stage:done`，完成任务迁移、阶段总结与归档。

## 6. 输出与维护原则

- 未知信息使用 `TBD`、`null` 或空数组表示，不得臆造日期、依赖、负责人或里程碑。
- 日志必须描述具体模块、接口、脚本、风险项或 ADR，不得使用模糊表述。
- 若为规划型阶段，可接受以文档、方案、任务拆解作为主要交付物。
- 若为实施型阶段，必须产生实际代码、配置、测试或脚本变更，不得仅以任务清单、建议或总结作为完成依据。
- 归档前应确认：
  - 所有 `[P0]` 任务已完成
  - `## 5. 验收标准` 已全部通过
  - `## 3. 非范围` 中的新想法已迁移
  - `## 9. 阶段总结` 已补充，或允许脚本生成最小归档总结
