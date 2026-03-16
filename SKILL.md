---
name: stage-manager
description: 项目阶段管理与归档专家。用于初始化阶段、同步进度、记录 ADR、认领 backlog、执行完成度检查、保存会话摘要、归档阶段，以及维护符合 references/stage_template.md 的阶段文档。
---

> [MANDATORY] 若存在 `SKILL.override.md`，Agent 必须先读取该文件；其约束优先级高于本文件。

## 1. 核心交互指令

> `stage:*` 仅为技能内语义别名；实际执行时映射为：
> `python3 <skill-path>/scripts/stage_manager.py <subcommand>`

| 指令                  | CLI 子命令           | 用途                                               |
| :-------------------- | :------------------- | :------------------------------------------------- |
| `stage:bootstrap`     | `bootstrap`          | [LOAD] 加载会话快照、最近决策、活跃阶段与 Backlog  |
| `stage:init <name>`   | `init <name>`        | 初始化新阶段文档并写入资产索引                     |
| `stage:sync "<msg>"`  | `sync "<msg>"`       | 增量日志；`[ADR]` 前缀触发 ADR 索引与存根          |
| `stage:summary "<t>"` | `summary "<t>"`      | [SAVE] 压缩并保存当前会话快照                      |
| `stage:intake "<k>"`  | `intake "<k>"`       | 从 Backlog 认领任务并注入阶段                      |
| `stage:status`        | `status`             | 查看项目健康度、进度、最近决策与会话摘要           |
| `stage:validate`      | `validate`           | 校验阶段文档结构                                   |
| `stage:check <ID>`    | `check <ID>`         | 勾选任务/验收项（`--uncheck` 反向）                 |
| `stage:switch <file>` | `switch <file>`      | 切换当前活跃阶段                                   |
| `stage:done`          | `done`               | 闭环归档（含 DoD 硬门禁，严禁擅自 `--force`）      |

- 操作非活跃阶段时使用 `--file <stage-file>`。`bootstrap` 无 `--file` 语义。
- 所有元数据、日志、ADR、快照与任务认领均通过脚本完成，不得手动修改索引。
- 严禁擅自修改 `scripts/` 下的代码，除非用户明确要求。
- 严禁直接覆写 `.stages/STAGES.md`、`BACKLOGS.md`、`ADRS.md`、`STAGE_SESSIONS.md`。

## 2. 阶段文档 schema

阶段文档遵循 `references/stage_template.md`（唯一 schema 来源）；`references/stage_example.md` 仅作参考示例，非强制对齐。

**任务行格式：**

```
- [ ] [P0] [TASK-001] 名称 | owner=unassigned | executor=agent | skills=[] | task_depends_on=[] | acceptance=[AC-001] | deliverables=[] | evidence=[] | due=YYYY-MM-DD
```

- `executor` 仅允许 `agent` / `human` / `sub_agent`
- `due` 未知时填 `YYYY-MM-DD` 或 `null`，不得臆造

**验收项格式：**

```
- [ ] [AC-001] 功能性 | verify_by=task_completion | required_tasks=[TASK-001] | required_checks=[critical_path_test] | evidence=[]
```

- `verify_by` 仅允许：`task_completion` / `evidence_review` / `metric_threshold` / `artifact_presence`

**evidence 约定**（详见 `references/best_practice.md`）：代码类保持原始路径；非代码类统一放 `.stage/`（`reports/`、`docs/`、`logs/`、`snapshots/`）。

## 3. 工程化机制

### 3.1 DoD 硬门禁

执行 `stage:done` 前，Agent 必须显式确认：

1. [ ] 所有 `[P0]` 任务已完成
2. [ ] `## 5. 验收标准` 已全部勾选
3. [ ] `## 3. 非范围` 新想法已迁移至 Backlog 或后续阶段
4. [ ] 已执行 `stage:summary` 或确认无需额外快照
5. [ ] `## 9. 阶段总结` 已填写，或允许脚本补写最小归档总结
6. [ ] 实施型阶段已核对变更证据（源码 diff、测试结果、构建产物等）

未满足时列出 `[Pending Tasks]` 并请求用户授权；严禁擅自 `--force`。

### 3.2 Backlog 认领

- 从 `BACKLOGS.md` 按关键字认领，注入 `## 4. 任务拆解`，归一为结构化格式。

### 3.3 ADR 同步

- `stage:sync "[ADR] <title>"` 自动生成 ADRS 编号、更新索引、写入存根。
- Agent 必须补全：背景/动机、可选方案、结论、影响/后果，不得停留 TBD。
- 涉及架构决策的 Commit Message 必须包含 `[ADRS-XXX]` 编号。

### 3.4 文档结构约束

- 所有 `@section:*` 锚点、章节编号和顺序必须保留。
- 更新时只增量修改受影响 section，不得整体重写。
- `- 暂无` 占位在新增首条时必须替换，不得并列保留。

## 4. 标准生命周期

1. **探测** — 首个操作必须是 `stage:bootstrap`；随后读取 `references/best_practice.md`。
2. **认领** — 存在遗留或 Backlog 命中项时执行 `stage:intake`。
3. **初始化** — 新建阶段执行 `stage:init`；补全目标、范围、任务、验收与风险。
4. **执行** — 任务拆解遵循 INVEST 原则，使用结构化格式。
5. **同步** — 变更后 `stage:sync`；架构决策用 `[ADR]` 前缀。
6. **校验** — 交付或归档前 `stage:validate`。
7. **闭环** — 验收通过后 `stage:done`。

## 5. 输出原则

- 未知信息用 `TBD` / `null` / `[]`，不得臆造。
- 日志必须指向具体模块、接口、风险项或 ADR，禁止模糊表述。
- **规划型阶段**（design/audit/review/planning/analysis）：文档与方案可为主要交付物。
- **实施型阶段**（implement/refactor/fix/integrate/migrate/replace）：必须产生实际代码/配置/测试变更。
