---
stage_id: "STAGE-XXX"
name: "TBD"
status: "PLANNING"
start_date: null
end_date: null
depends_on: []
milestone: null
---

# STAGE-XXX: TBD

---

<!--
约定：
- `.stages/` 由脚本维护
- `.stage/` 用于 evidence
- stage 写命令同一时刻只允许一个 Agent 执行
-->

<!-- @section:goals -->

## 1. 阶段目标

- [ ] [TARGET-001]: TBD
- [ ] [TARGET-002]: TBD

<!-- @section:scope -->

## 2. 范围

- [SCOPE-001] TBD

<!-- @section:out_of_scope -->

## 3. 非范围

- [OUT-SCOPE-001] TBD

<!-- @section:tasks -->

## 4. 任务拆解

<!-- `executor`: agent / human / sub_agent -->
<!-- 代码类 evidence 保持原始路径；非代码类放 `.stage/` -->
<!-- 下列 `skills`、`deliverables`、`evidence`、`due` 只是 schema 占位示例；除非用户或项目上下文已明确给出，否则回答时不要把这些默认值当成真实事实直接写入。 -->

- [ ] [P0] [TASK-001] 任务名称 | owner=unassigned | executor=agent | skills=[] | task_depends_on=[] | acceptance=[AC-001] | deliverables=[] | evidence=[] | due=YYYY-MM-DD
- [ ] [P0] [TASK-900] 阶段验收 | owner=unassigned | executor=agent | skills=[stage-reviewer] | task_depends_on=[] | acceptance=[AC-001,AC-002,AC-003,AC-004] | deliverables=[stage-review-report] | evidence=[.stage/reports/stage-review.md] | due=YYYY-MM-DD

<!-- @section:dod -->

## 5. 验收标准

<!-- `verify_by`: task_completion / evidence_review / metric_threshold / artifact_presence -->

- [ ] [AC-001] 功能性 | verify_by=task_completion | required_tasks=[TASK-001] | required_checks=[critical_path_test] | evidence=[]
- [ ] [AC-002] 安全性 | verify_by=evidence_review | required_tasks=[TASK-001] | required_checks=[permission_check,isolation_check] | evidence=[]
- [ ] [AC-003] 稳定性 | verify_by=metric_threshold | required_tasks=[] | required_checks=[metrics_target_met] | evidence=[.stage/reports/perf.md]
- [ ] [AC-004] 变更可追踪 | verify_by=artifact_presence | required_tasks=[TASK-001] | required_checks=[log_updated,adr_updated,summary_updated] | evidence=[.stage/logs/progress-log.md,.stage/docs/adr-001.md]

<!-- @section:risks -->

## 6. 风险与应对

| 风险描述 | 严重程度 | 触发信号 | 应对措施 | 回滚/降级方案 |
| :------- | :------- | :------- | :------- | :------------ |

<!-- @section:log -->

## 7. 进度日志

<!--
- ### [LOG-XXX] | [YYYY-MM-DD] | [主题] | [owner] | [Ver:git@commit-or-TBD]
  - **状态**: 进行中 / 已完成 / 阻塞 (Blocked by: XXX)
  - **关键进展**: 1 句增量描述
  - **模块级记录**: <模块/接口/文件> | change=<...> | evidence=<...> | next=<...> | risk=<...>
  - **后续行动**: 紧邻的下一步
-->

- 暂无

<!-- @section:adrs -->

## 8. 关键决策（ADRs）

- 暂无

<!-- @section:summary -->

## 9. 阶段总结

- 暂无
