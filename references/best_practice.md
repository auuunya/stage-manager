# references/best_practice.md

> 仅补充最佳实践；字段 schema 与占位格式以 `stage_template.md` 为唯一准绳。

## 1. 基本原则

- 隔离：Stage N 的失败不应拖垮全局，必要时补回滚或降级方案。
- 文档即代码：像维护代码一样维护 `stage-XXX.md`。
- 增量更新：优先只改受影响 section，不整体重写。
- 单写者：同一时刻只允许一个 Agent 执行 `stage:*` 写命令。
- 阶段状态术语统一使用：`当前阶段`、`其他阶段`、`已归档阶段`。

## 2. 任务拆解

按 INVEST 拆任务：

- Independent：避免循环依赖
- Valuable：每个任务都要有可感知产出
- Estimatable：最好不超过 1 到 2 天
- Small：便于勾选和回滚
- Testable：必须能被验收

补充要求：

- 拆不完或估不准，就继续拆。
- `acceptance` 指向 AC，`deliverables` 与 `evidence` 不混用。
- `TASK-900` 作为阶段验收任务保留。

## 3. Evidence

- 代码类：保持项目原始路径，如 `src/...`、`tests/...`
- 非代码类：统一放 `.stage/`，如 `reports/`、`docs/`、`logs/`、`snapshots/`
- 每个 P0 任务至少一份可读 evidence
- 每个 AC 至少一条可核验 evidence
- 实施型阶段若没有代码、测试或配置 evidence，不算完成

## 4. 验收标准

- 优先写“动作 + 结果”，不要写“符合预期”“基本完成”
- `required_checks` 写可验证检查点，如 `login_api_returns_token`
- 可追踪类 AC 应覆盖日志、ADR、总结三者之一或其组合

## 5. 多 Agent 协作

- 多个 Agent 可以并行产出代码、报告或分析
- 只有一个 Agent 可以执行 `stage:init`、`stage:sync`、`stage:summary`、`stage:intake`、`stage:check`、`stage:switch`、`stage:done`
- `sub_agent` 默认只读；需要回写时，先把产物交给主 Agent
- “创建 ADR 存根”和“补阶段总结”这类写操作必须排队

## 6. 日志质量

日志记录增量与决策，不写泛化周报。

推荐模板：

```text
<模块/接口/文件> | change=<本次变更或当前状态> | evidence=<测试/文档/路径/ADR，未知写 TBD> | next=<下一个明确动作> | risk=<无 / 具体风险>
```

要求：

- `模块/接口/文件` 至少落到模块、API、任务文件或配置文件层级
- `change` 只写本次新增、修复、迁移或阻塞状态
- `evidence` 优先复用当前阶段任务、验收项或 `.stage/` 中已存在对象；拿不准写 `TBD`
- `next` 必须是紧邻的可执行动作
- `risk` 没有就写 `无`
- 一条日志只描述一个模块主题；跨模块请拆开

反例：

- `完成登录优化`
- `处理了一些问题`
- `继续推进`

## 7. ADR

最小四字段：

- 背景/动机
- 可选方案
- 结论
- 影响/后果

推荐骨架：

```md
- ### [ADRS-XXX] | [YYYY-MM-DD] | [标题]
  - **背景/动机**: ...
  - **可选方案**: 方案A vs 方案B
  - **结论**: ...
  - **影响/后果**: ...
```

若涉及架构决策，Commit Message 应包含 ADRS 编号。
