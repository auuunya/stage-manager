# Stage-Manager

> 一个为 AI Agent 工作流设计的自动化阶段计划管理系统。

`stage-manager` 是一套轻量级、标准化的项目生命周期管理 Skill。它通过“一阶段一文档”的隔离原则，结合自动化脚本，确保项目进度、决策记录（ADR）和任务溢出（Backlog）被结构化地记录，同时保持根目录的清爽。

## 🌟 核心特性

- **状态机管理**：严格控制项目的 `Planning` -> `In Progress` -> `Done` 流转。
- **自动化归档**：一键将完成的阶段移入 `archive/`，防止项目文档膨胀。
- **任务溢出处理**：自动捕获未完成任务并同步至 `BACKLOG.md`。
- **Agent 友好**：预设的指令集（CLI）让 Cursor, Windsurf, AutoGPT 等 AI 工具能无缝接管项目管理。

## 📁 目录结构

```text
stage-manager/               # 核心封装
├── stage-manager.md         # 规则说明书
├── STAGES.md                # 当前阶段的看板
├── BACKLOG.md               # 任务溢出池
├── scripts/                 # 自动化脚本
│   └── stage_manager.py     # 核心管理器
├── references/              # 规范定义
│   ├── stage_template.md    # 阶段文档模板
│   └── best_practice.md     # 任务拆解准则
└── examples/                # 示例
    ├── BACKLOG.md
    ├── stage-01-foundation.md
    └── stage-02-auth-system.md
```
