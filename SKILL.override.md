---
priority: critical
enforcement: mandatory
note: 本文件定义当前会话的强制执行标准。优先级高于 SKILL.md。
---

> **Language: [中文]**

## 1. 语言与质量协议

- **思考链与输出**: 全场景强制使用 **[中文]**。
- **ASCII 强制令**: 严禁 Emoji。必须使用 `[OK]`, `[!]`, `[-]`, `[x]`, `[ ]` 等符号或者 `ascii` 码。
- **Git 血缘追踪**: 凡是涉及架构决策的代码提交，Commit Message **必须包含** 对应的 `[ADRS-XXX]` 唯一编号。

## 2. 规范校验义务 (Compliance)

- **Reference 对齐**: Agent 在拆解任务（`init`）或编写日志（`sync`）时，**必须先通过 `read_file` 读取 [references/best_practice.md](references/best_practice.md)**，确保输出符合其中的标准。
- **模板去噪**: 所有新阶段文档必须通过读取 [references/stage_template.md](references/stage_template.md) 进行初始化。Agent 严禁在最终文档中保留任何斜体引导语或模板占位引用块。

## 3. 工程化补丁 (Engineering Patches)

- **DoD 硬门禁**: 执行 `stage:done` 前，Agent 必须核对 `## 5. 验收标准`。若存在未勾选项，**严禁**直接归档。
- **归档决策**: 进度不满 100% 或 DoD 未通过时，Agent 必须先列出 `[Pending Tasks]` 并询问用户授权，严禁擅自使用 `--force`。
- **Proactive ADR**: `sync [ADR]` 后必须立即补全决策背景，严禁留空。

## 4. 约束与禁止行为

- **技能代码保护 [CRITICAL]**: Agent 严禁擅自修改 `.codex/skills/stage-manager/scripts/` 目录下的任何脚本代码。Agent 必须定位为脚本的 **[使用者/执行者]**，而非开发维护者。只有在用户明确下达“优化/修改 stage-manager 技能本身”的指令时，方可变动脚本。
- **Bootstrap Alignment**: 开启会话首动作必须是 `stage:bootstrap`，并简要复述记忆锚点以确认记忆对齐。
- **需求填充**: 在 `init` 之后必须根据需求填充“目标/范围/任务拆解/验收标准/风险”。
- **资产归口**: 严禁在 `.stages/` 目录以外创建管理文件。
- **精准指代**: 严禁在 `sync` 中使用“优化了代码”等模糊词汇，必须指明具体模块或 [ADRS-XXX] ID。
