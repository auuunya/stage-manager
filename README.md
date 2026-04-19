# Stage-Manager

> 为 AI Agent 工作流设计的工业级自动化阶段计划管理系统。

`stage-manager` 是一套轻量级、标准化的项目生命周期管理 Skill。它基于“一阶段一文档”的隔离原则，结合自动化脚本、标准化模板和参考规范，确保项目进度、架构决策记录（ADRS）和会话摘要（STAGE_SESSIONS）被结构化地记录。所有运行期资产统一归口于 `.stages/` 目录，保持项目根目录清爽、可审计、可恢复。

## CLI 入口

- 当前稳定入口是 `scripts/stage.py`
- 技能内的 `stage:*` 语义别名，实际都映射到：

```bash
python3 <skill-path>/scripts/stage.py <subcommand>
```

- 常见示例：

```bash
python3 scripts/stage.py bootstrap
python3 scripts/stage.py init "feature-auth"
python3 scripts/stage.py sync "[ADR] 使用 Redis 作为缓存层"
python3 scripts/stage.py status --file stage-002-payment-fix.md
```

## 核心特性

- **中央资产归口**  
  所有管理文件（看板、决策、日志、任务池）统一存放在 `.stages/` 目录下。
- **标准化阶段文档**  
  每个阶段文档均遵循统一 schema，包含目标、范围、任务拆解、验收标准、风险、日志、ADRs 与阶段总结。
- **架构决策 ID 化**  
  自动为架构决策生成唯一 ID（如 `[ADRS-001]`），支持跨文档精准引用。
- **会话状态压缩 (Save/Load)**  
  通过 `summary` 和 `bootstrap` 机制，缓解长对话场景下的记忆丢失与上下文膨胀问题。
- **DoD 硬门禁**  
  归档前自动检查 `## 5. 验收标准`，避免“任务完成但验收未完成”的伪闭环。
- **Backlog 认领与任务分流**  
  支持从 `BACKLOGS.md` 按关键字认领任务；归档时自动将未完成任务和非范围条目分别分流至 `[TECH_DEBT]` 与 `[ROADMAP]`。
- **多阶段操作支持**  
  支持通过 `--file` 显式指定其他阶段文件，而不只依赖当前阶段。
- **单写者保护**  
  所有会修改 `.stages/` 或阶段文档的命令都会走脚本级单写者锁，避免并发写入造成索引冲突。

## 运行期资产目录

```text
.stages/                           # 自动生成的运行期资产目录（位于项目根目录）
├── STAGES.md                      # 阶段看板（含统计、当前阶段、其他阶段、最近快照）
├── ADRS.md                        # 架构决策中央索引（含标准 ID）
├── STAGE_SESSIONS.md              # 会话压缩日志（滑动窗口）
├── BACKLOGS.md                    # 跨阶段任务池
├── stages/                        # 所有未归档阶段文档；其中只有一个会被标记为“当前阶段”
└── archive/
    └── stages/                    # 已归档阶段文档
```

## 脚本结构

```text
scripts/
├── stage.py                       # 对外 CLI 入口
└── core/                          # 内部实现模块
    ├── cli.py                     # 参数解析与命令分发
    ├── runtime.py                 # 路径、IO、输出、写锁
    ├── doc.py                     # frontmatter、section、解析、渲染、统计
    ├── commands.py                # init/check/switch/intake 等命令
    ├── ops.py                     # sync/summary/done 等写操作
    ├── indexes.py                 # STAGES/ADRS/session 索引维护
    ├── validate.py                # P0/DoD/evidence/schema 校验
    └── dashboard.py               # bootstrap/status 展示
```

- `scripts/stage.py` 负责稳定入口契约，便于技能、测试和外部调用保持不变。
- `scripts/core/*.py` 是内部实现；若只是在使用 skill，不需要直接操作这些模块。

## 阶段状态语义

- `STAGES.md` 中的 `当前阶段` 是唯一指针，表示默认读写目标。
- `其他阶段` 表示仍位于 `.stages/stages/` 下、但当前未被选中的未归档阶段。
- `已归档阶段` 表示阶段文件已迁入 `.stages/archive/stages/`。
- 需要操作其他阶段时，优先使用 `--file <stage-file>`，不要为了临时补写而切换当前阶段。

## 写入约束

- `init`、`sync`、`summary`、`intake`、`check`、`switch`、`done` 都属于写命令，应串行执行。
- 若两个写命令并发运行，脚本会返回 `[BUSY]`，要求等待前一个命令完成后再重试。
- `.stages/STAGES.md`、`.stages/ADRS.md`、`.stages/BACKLOGS.md`、`.stages/STAGE_SESSIONS.md` 只允许通过 `scripts/stage.py` 维护，不建议手动改索引。
