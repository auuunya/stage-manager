# Stage-Manager

> 一个为 AI Agent 工作流设计的自动化阶段计划管理系统。

`stage-manager` 是一套轻量级、标准化的项目生命周期管理 Skill。它通过“一阶段一文档”的隔离原则，结合自动化脚本，确保项目进度、决策记录（ADR）和任务溢出（Backlog）被结构化地记录，同时保持根目录的清爽。

## 🌟 核心特性

- **阶段流程管理**：按阶段推进 `Planning`/`In Progress`/`Done`，并在归档时进行完成度门禁。
- **自动化归档**：一键将完成的阶段移入 `archive/`，防止项目文档膨胀。
- **任务溢出处理**：自动捕获未完成任务并同步至 `BACKLOG.md`。
- **Agent 友好**：预设的指令集（CLI）让 Cursor, Windsurf, AutoGPT 等 AI 工具能无缝接管项目管理。

## 📁 目录结构

```text
stage-manager/               # 核心封装
├── SKILL.md                 # 技能规则说明书
├── scripts/                 # 自动化脚本
│   └── stage_manager.py     # 核心管理器
├── references/              # 规范定义
│   ├── stage_template.md    # 阶段文档模板
│   └── best_practice.md     # 任务拆解准则
├── assets/                  # 静态资源
└── templates/               # 示例
    ├── BACKLOG.md
    ├── stage-01-foundation.md
    └── stage-02-auth-system.md
```

> 运行脚本后生成的 `STAGES.md`、`BACKLOG.md`、`stages/`、`archive/stages/` 位于目标项目根目录，而非 skill 目录。
