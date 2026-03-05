---
name: stage-manager
description: 项目阶段生命周期管理专家，负责规划、执行与自动化归档。
version: 1.0.0
tools:
  - scripts/stage_manager.py
---

## 1. 核心交互指令 (Command Aliases)

_`Agent`必须通过以下指令来维护项目状态，以确保 `STAGES.md` 索引的精准插入_

| 指令 (Alias)        | 映射脚本指令 (CLI)                                           | 触发场景与 Agent 职责                                                                |
| ------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `stage:init <name>` | `python stage-manager/scripts/stage_manager.py init <name>`  | **初始化**：准备开始新功能，Agent 必须调用此脚本生成文档，填充目标、范围和分级任务。 |
| `stage:sync`        | `python stage-manager/scripts/stage_manager.py sync "<msg>"` | **打卡**：完成 Checkbox 任务或代码提交后，Agent 必须同步进度日志。                   |
| `stage:done`        | `python stage-manager/scripts/stage_manager.py done`         | **结算**：验收标准 100% 达成时，Agent 执行此指令触发自动化归档。                     |
| `stage:status`      | `python stage-manager/scripts/stage_manager.py status`       | **审计**：对话开始前，Agent 应先执行此指令感知项目当前上下文。                       |

---

## 2. 运行环境与规则 (Context & Rules)

1. **零污染原则**：根目录 `STAGES.md` 仅作为索引。所有规则定义由本文件（`stage-manager.md`）承载。
2. **执行详情**：所有具体任务、日志、风险均位于 `stages/stage-XX-<name>.md`。
3. **ADR 自动补全**：若决定改变技术方案，必须执行 `stage:sync` 并写入阶段文档的 `## 8. 关键决策`。
4. **进度感知**：对话开始前执行 `stage:status`。若进度 100%，主动询问是否执行 `stage:done`。
5. **模版一致性**：创建新阶段文档时，必须完整继承 `references/stage_template.md` 的结构，严禁随意删减核心元数据字段。
6. **最佳实践对齐**：所有阶段的输出质量必须符合 `references/best_practice.md` 定义的标准。在任务执行过程中，若遇到规范冲突，以最佳实践手册为准。

---

## 3. 阶段管理工作流 (Strict Workflow)

### 3.1 查询与定位

在执行任何代码修改或任务前，**Agent 必须**：

- 读取 `STAGES.md` 确定当前处于 `（当前阶段）` 的文件。
- 读取该 `stages/stage-XX.md` 确认任务上下文。

### 3.2 自动化流转 (Agent Logic)

- **初始化**：若无活跃阶段且用户提出新需求，引导执行 `stage:init`。
- **更新**：代码运行成功或文档更新后，自动调用 `stage:sync`。
- **闭环**：验收标准全部勾选后，提示执行 `stage:done` 进行自动归档。

---

## 4. 规范约束 (Output Constraints)

- **命名规范**：文件必须符合 `stage-XX-<short-name>.md`（全小写，连字符）。
- **内容质量**：任务拆解遵循 **INVEST 原则**（见 `references/best_practice.md`）。
- **禁止蔓延**：非本阶段范围（Out of Scope）的任务必须记录在案，严禁在当前阶段偷跑。
- **归档策略**：执行 `done` 时，未完成任务自动迁移至 `BACKLOG.md`，原始文件移至 `archive/`。
- **逻辑触发点**：
  1. 任何代码修改完成后，必须立即检查当前活跃阶段文档并同步。
  2. 严禁手动修改 `STAGES.md` 的列表结构，必须由脚本生成。

---

## 5. 自动化工具接入 (Scripts)

_Agent 可调用以下逻辑（或由用户在终端执行）_：

```bash
# 初始化示例
python stage-manager/scripts/stage_manager.py init "feature-auth"
# 同步日志示例
python stage-manager/scripts/stage_manager.py sync "完成了登录页面的接口对接"
# 完成归档
python stage-manager/scripts/stage_manager.py done
```

## 6. 归档与清理策略 (Lifecycle Management)

本项目的 `stages/` 目录仅存放 `**活跃阶段**`。当阶段状态变更为 `done` 后：

1. **归档路径**：阶段文档将自动移动至 `archive/stages/` 目录。
2. **根目录清理**：`stages/` 下的对应文件必须被删除，防止项目根目录膨胀。
3. **全局索引维护**：`STAGES.md` 中的链接需自动从 `stages/` 更新为 `archive/` 路径。

_Agent 职责_：在执行 `stage:done` 指令时，必须自动触发上述迁移逻辑，并确保所有关联索引同步更新。

## 7. 禁止行为 (Forbidden)

- **严禁**直接编辑 `STAGES.md` 中的列表项（由脚本维护）。
- **严禁**在没有活跃阶段的情况下开始大规模代码重构。
- **严禁**绕过脚本逻辑手动在 `stages/` 目录下创建文件。
