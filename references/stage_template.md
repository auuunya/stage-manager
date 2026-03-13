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

<!--
任务字段约定：
- executor 仅允许：agent / human / sub_agent
- acceptance 填写该任务支撑的 AC 编号
- deliverables 填写交付物标识，可为逻辑名称
- evidence 填写任务完成证据
- 代码类 evidence 可保持项目原始路径
- 非代码类 evidence 统一放在 .stage/ 下
-->

- [ ] [P0] [TASK-001] 任务名称 | owner=unassigned | executor=agent | skills=[] | task_depends_on=[] | acceptance=[AC-001] | deliverables=[] | evidence=[] | due=YYYY-MM-DD
- [ ] [P0] [TASK-900] 阶段验收 | owner=unassigned | executor=agent | skills=[stage-reviewer] | task_depends_on=[] | acceptance=[AC-001,AC-002,AC-003,AC-004] | deliverables=[stage-review-report] | evidence=[.stage/reports/stage-review.md] | due=YYYY-MM-DD

<!-- @section:dod -->

## 5. 验收标准

<!--
verify_by 仅允许：
- task_completion
- evidence_review
- metric_threshold
- artifact_presence
-->

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

> 进度日志记录时间序列增量，不重复抄写任务列表。

- 暂无

<!-- @section:adrs -->

## 8. 关键决策（ADRs）

- 暂无

<!-- @section:summary -->

## 9. 阶段总结

> 阶段总结只在阶段收尾或里程碑变化时更新。

- 暂无
