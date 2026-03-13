---
stage_id: "STAGE-001"
name: "User Authentication"
status: "IN_PROGRESS"
start_date: "2026-03-12"
end_date: null
depends_on: []
milestone: "MVP-AUTH"
---

# STAGE-001: User Authentication

---

<!-- @section:goals -->

## 1. 阶段目标

- [x] [TARGET-001]: 完成基础用户登录流程
- [ ] [TARGET-002]: 实现 Token 刷新机制

<!-- @section:scope -->

## 2. 范围

- [SCOPE-001] 登录 API
- [SCOPE-002] Token 签发
- [SCOPE-003] Token 校验中间件

<!-- @section:out_of_scope -->

## 3. 非范围

- [OUT-SCOPE-001] OAuth 第三方登录
- [OUT-SCOPE-002] 多因素认证

<!-- @section:tasks -->

## 4. 任务拆解

- [x] [P0] [TASK-001] 设计认证流程 | owner=alice | executor=agent | skills=[system-design] | task_depends_on=[] | acceptance=[AC-001,AC-004] | deliverables=[auth-design] | evidence=[.stage/docs/auth-design.md,.stage/reports/task-001-check.md] | due=2026-03-12
- [x] [P0] [TASK-002] 实现登录 API | owner=gemini | executor=human | skills=[backend-api] | task_depends_on=[TASK-001] | acceptance=[AC-001] | deliverables=[login-api,login-test] | evidence=[src/api/login.ts,tests/login.test.ts,.stage/reports/task-002-check.md] | due=2026-03-13
- [ ] [P0] [TASK-003] 实现 Token 校验中间件 | owner=bob | executor=agent | skills=[backend-security] | task_depends_on=[TASK-001] | acceptance=[AC-002] | deliverables=[auth-middleware,authz-test] | evidence=[src/middleware/auth.ts,tests/authz.test.ts,.stage/reports/task-003-check.md] | due=2026-03-14
- [ ] [P1] [TASK-004] 实现 Token 刷新接口 | owner=codex | executor=sub_agent | skills=[backend-api] | task_depends_on=[TASK-001] | acceptance=[AC-003] | deliverables=[refresh-api,load-test-report] | evidence=[src/api/refresh.ts,.stage/reports/task-004-check.md] | due=2026-03-15
- [ ] [P0] [TASK-900] 阶段验收 | owner=alice | executor=agent | skills=[stage-reviewer] | task_depends_on=[TASK-001,TASK-002,TASK-003,TASK-004] | acceptance=[AC-001,AC-002,AC-003,AC-004] | deliverables=[stage-review-report] | evidence=[.stage/reports/stage-review.md] | due=2026-03-16

<!-- @section:dod -->

## 5. 验收标准

- [x] [AC-001] 功能性 | verify_by=task_completion | required_tasks=[TASK-001,TASK-002] | required_checks=[login_api_returns_token,basic_login_test_passed] | evidence=[tests/login.test.ts,.stage/reports/ac-001-functional-check.md]
- [ ] [AC-002] 安全性 | verify_by=evidence_review | required_tasks=[TASK-003] | required_checks=[permission_check,isolation_check] | evidence=[tests/authz.test.ts,.stage/reports/ac-002-security-check.md]
- [ ] [AC-003] 稳定性 | verify_by=metric_threshold | required_tasks=[TASK-004] | required_checks=[metrics_target_met,100_rps_no_error] | evidence=[.stage/reports/ac-003-load-test.md,.stage/snapshots/load-test-metrics.json]
- [x] [AC-004] 变更可追踪 | verify_by=artifact_presence | required_tasks=[TASK-001,TASK-002] | required_checks=[log_updated,adr_updated,summary_updated] | evidence=[.stage/logs/progress-log.md,.stage/docs/adr-001.md,.stage/reports/ac-004-traceability-check.md]

<!-- @section:risks -->

## 6. 风险与应对

| 风险描述     | 严重程度 | 触发信号     | 应对措施          | 回滚/降级方案 |
| :----------- | :------- | :----------- | :---------------- | :------------ |
| JWT key 泄露 | 高       | token 被伪造 | 使用 key rotation | 回滚至旧 key  |

<!-- @section:log -->

## 7. 进度日志

> 进度日志记录时间序列增量，不重复抄写任务列表。

- ### [LOG-001] | [2026-03-12] | [认证流程设计] | [alice] | [Ver:git@1a2b3c]
  - **状态**: 已完成
  - **关键进展**: 完成 JWT + refresh token 架构设计，并输出认证流程设计文档。
  - **后续行动**: 实现登录 API。

- ### [LOG-002] | [2026-03-13] | [登录 API] | [bob] | [Ver:git@2b3c4d]
  - **状态**: 已完成
  - **关键进展**: `/api/login` 实现并完成基本测试，已补充任务级检查报告。
  - **后续行动**: 实现 Token 校验 middleware。

<!-- @section:adrs -->

## 8. 关键决策（ADRs）

- ### [ADRS-001] | [2026-03-12] | [认证方案选择]
  - **背景/动机**: 系统需要无状态认证方案，以支持 API 服务横向扩展。
  - **可选方案**: Session vs JWT。
  - **结论**: 使用 JWT。
  - **影响/后果**: API 服务保持无状态，扩展性更好；需要额外关注 token 生命周期和密钥轮换策略。

<!-- @section:summary -->

## 9. 阶段总结

> 阶段总结只在阶段收尾或里程碑变化时更新。

- ### [SUMMARY-001] | [2026-03-13] | [认证阶段中期总结] | [Ver:git@2b3c4d]
  - **里程碑目标**: 实现基础认证能力。
  - **核心成果**:
    - [x] JWT 认证架构设计完成
    - [x] 登录 API 实现
  - **变更审计**: 新增 `/api/login` 接口及登录测试，补充阶段证据与任务检查报告。
  - **遗留风险/技术债**: refresh token 机制尚未完成；Token 校验中间件仍待补齐权限测试。
