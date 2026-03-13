---
priority: critical
enforcement: mandatory
note: 本文件定义当前会话的强制执行补丁。优先级高于 SKILL.md。
---

> Language: 中文

## 1. 语言与输出约束

- 全场景输出强制使用[Language]。
- 严禁 Emoji。
- 状态与标记优先使用 ASCII 风格符号，如 `[OK]`, `[!]`, `[-]`, `[x]`, `[ ]`。

## 2. 强制流程补丁

- 当 Agent 开始执行项目阶段管理工作时，首个操作必须是 `stage:bootstrap`。
- 在执行 `init`、`sync`、`summary`、人工补全文档前，必须先读取 [references/best_practice.md](references/best_practice.md)。
- 所有新阶段文档必须基于 [references/stage_template.md](references/stage_template.md) 初始化。
- 所有阶段文档输出必须与 [references/stage_example.md](references/stage_example.md) 的字段写法、结构粒度和条目组织方式保持一致。
- 更新已有阶段文档时，只允许增量修改受影响的 section，不得整体重写未变更内容。

## 3. done 前强制检查

执行 `stage:done` 前，Agent 必须显式确认以下条件：

1. [ ] 所有 `[P0]` 任务已完成。
2. [ ] `## 5. 验收标准` 已全部勾选。
3. [ ] `## 3. 非范围` 中的新想法已迁移到 `BACKLOGS.md` 或后续阶段。
4. [ ] 已执行 `stage:summary` 保存最后会话快照，或已确认当前上下文无需额外快照。
5. [ ] `## 9. 阶段总结` 已填写完成，或允许脚本补写最小归档总结。
6. [ ] 若任务包含代码实现，已核对实际变更证据，例如源码 diff、变更文件列表、测试结果、构建结果或可验证产物。

- 若未满足上述条件，必须先列出 `[Pending Tasks]` 并请求用户授权；严禁擅自使用 `--force`。

## 4. ADR 与提交约束

- `sync [ADR]` 仅用于生成 ADR 索引与存根；生成后，Agent 必须继续补全：
  - 背景/动机
  - 可选方案
  - 结论
  - 影响/后果
- 凡是涉及架构决策的代码提交，Commit Message 必须包含对应的 `[ADRS-XXX]` 唯一编号。

## 5. 资产保护补丁

- 严禁擅自修改当前 Skill 目录下 `scripts/` 中的任何脚本代码。
- 严禁使用直接覆写方式手动修改以下索引资产：
  - `.stages/STAGES.md`
  - `.stages/BACKLOGS.md`
  - `.stages/ADRS.md`
  - `.stages/STAGE_SESSIONS.md`
- 所有索引资产更新必须通过 `python3 <skill-path>/scripts/stage_manager.py` 的对应子命令完成。
