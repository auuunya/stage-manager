---
name: stage-manager
description: 项目阶段管理与归档。用于 stage:init、stage:sync、stage:status、stage:done、stage:done --force，以及创建维护 STAGES.md、BACKLOG.md、stages/、archive/stages/。凡是阶段拆解、进度同步、完成度检查、归档、未完成任务迁移都应触发本技能。
---

## 1. 核心交互指令

| 指令                  | CLI                                                               | 用途                   |
| --------------------- | ----------------------------------------------------------------- | ---------------------- |
| `stage:init <name>`   | `python3 <skill-path>/scripts/stage_manager.py init <name>`       | 创建阶段文档并更新索引 |
| `stage:sync "<msg>"`  | `python3 <skill-path>/scripts/stage_manager.py sync "<msg>"`      | 记录进展并刷新最近同步 |
| `stage:status`        | `python3 <skill-path>/scripts/stage_manager.py status`            | 查看活跃阶段与完成度   |
| `stage:done`          | `python3 <skill-path>/scripts/stage_manager.py done`              | 完成度 100% 时归档     |
| `stage:done --force`  | `python3 <skill-path>/scripts/stage_manager.py done --force`      | 未达 100% 强制归档     |
| `stage:status --root` | `python3 <skill-path>/scripts/stage_manager.py status --root <p>` | 指定项目根目录         |

## 2. 运行环境与规则

1. `STAGES.md` 仅作索引；规则以本文件为准。
2. 阶段详情写入项目根目录 `stages/stage-XX-<name>.md`。
3. 技术决策变更后执行 `stage:sync`，并更新 `## 8. 关键决策`。
4. 会话开始先执行 `stage:status`；进度 100% 时提示 `stage:done`。
5. 阶段文档必须遵循 [references/stage_template.md](references/stage_template.md)。
6. 输出质量遵循 [references/best_practice.md](references/best_practice.md)。
7. 所有产物默认生成于项目根目录，不写入 skill 目录。

## 3. 阶段管理工作流

### 3.1 查询与定位

- 执行前读取项目根目录 `STAGES.md`，定位 `（当前阶段）`。
- 读取对应 `stages/stage-XX-<name>.md` 获取上下文。

### 3.2 自动化流转

- **初始化**：若无活跃阶段且用户提出新需求，引导执行 `stage:init`。
- **更新**：代码运行成功或文档更新后，自动调用 `stage:sync`。
- **闭环**：验收项完成后执行 `stage:done`；仅在用户明确要求下使用 `stage:done --force`。

## 4. 规范约束

- **命名规范**：文件必须符合 `stage-XX-<short-name>.md`（全小写，连字符）。
- **内容质量**：任务拆解遵循 **INVEST 原则**（见 `references/best_practice.md`）。
- **禁止蔓延**：非本阶段范围（Out of Scope）的任务必须记录在案，严禁在当前阶段偷跑。
- **归档策略**：执行 `done` 时，未完成任务迁移至 `BACKLOG.md`，原始文件移至 `archive/stages/`。
- **逻辑触发点**：
  1. 任何代码修改完成后，必须立即检查当前活跃阶段文档并同步。
  2. 严禁手动修改 `STAGES.md` 的列表结构，必须由脚本生成。
  3. `init/sync/done` 执行后，必须刷新 `STAGES.md` 中的“最近同步”时间。

## 5. 自动化工具接入

_以下命令可由 Agent 或用户执行。_

```bash
python3 <skill-path>/scripts/stage_manager.py init "feature-auth"
python3 <skill-path>/scripts/stage_manager.py sync "feat: Login API finished"
python3 <skill-path>/scripts/stage_manager.py done --force
```

## 6. 归档与清理策略

归档与清理规则已在第 4 节“归档策略/逻辑触发点”定义，执行 `stage:done` 时按其自动迁移并同步索引。

## 7. 禁止行为

- **严禁**直接编辑 `STAGES.md` 中的列表项（由脚本维护）。
- **严禁**在没有活跃阶段的情况下开始大规模代码重构。
- **严禁**绕过脚本逻辑手动在 `stages/` 目录下创建文件。
