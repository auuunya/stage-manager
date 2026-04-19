import argparse
import contextlib


def build_parser(version: str, allowed_log_status) -> argparse.ArgumentParser:
    """构建完整 CLI 解析树，不执行业务逻辑。"""
    parser = argparse.ArgumentParser(
        description="Stage-Manager: 项目生命周期自动化管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  stage.py init \"feature-auth\"\n"
            "  stage.py sync \"实现登录逻辑\" --task-name \"登录接口\"\n"
            "  stage.py sync \"[ADR] 使用 JWT\"\n"
            "  stage.py check TASK-001\n"
            "  stage.py switch stage-002-api.md\n"
            "  stage.py summary \"会话快照\"\n"
            "  stage.py status --json\n"
            "  stage.py done\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {version}")
    parser.add_argument("--root", help="指定项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    sub = parser.add_subparsers(dest="cmd", title="子命令", required=True)

    p = sub.add_parser("init", help="初始化新阶段")
    p.add_argument("name", help="阶段名称")

    p = sub.add_parser("sync", help="同步进展")
    p.add_argument("message", help="进展描述；[ADR] 前缀触发决策同步")
    p.add_argument("--task-name", help="关联任务名")
    p.add_argument("--status", default="进行中", choices=sorted(allowed_log_status))
    p.add_argument("--next-action", help="后续行动")
    p.add_argument("--blocked-by", help="阻塞依赖 ID")
    p.add_argument("--file", help="指定 stage 文件")

    p = sub.add_parser("summary", help="会话快照或阶段总结")
    p.add_argument("text", nargs="?", help="快照内容")
    p.add_argument("--stage", action="store_true", help="写入阶段总结(section 9)")
    p.add_argument("--name", help="总结名称")
    p.add_argument("--goal", help="里程碑目标")
    p.add_argument("--result", action="append", help="核心成果(可多次)")
    p.add_argument("--audit", help="变更审计")
    p.add_argument("--debt", help="遗留风险/技术债")
    p.add_argument("--file", help="指定 stage 文件")

    p = sub.add_parser("intake", help="从 Backlog 认领任务")
    p.add_argument("keyword", help="匹配关键字")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--file", help="指定 stage 文件")

    sub.add_parser("bootstrap", help="会话启动引导")

    p = sub.add_parser("status", help="健康看板")
    p.add_argument("--file", help="指定 stage 文件")

    p = sub.add_parser("validate", help="校验阶段文档")
    p.add_argument("--file", help="指定 stage 文件")

    p = sub.add_parser("done", help="闭环归档")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--file", help="指定 stage 文件")

    p = sub.add_parser("check", help="勾选/取消勾选任务或验收项")
    p.add_argument("item_id", help="目标 ID（如 TASK-001、AC-002）")
    p.add_argument("--uncheck", action="store_true", help="取消勾选")
    p.add_argument("--file", help="指定 stage 文件")

    p = sub.add_parser("switch", help="切换当前活跃阶段")
    p.add_argument("target", help="目标阶段文件名")

    return parser


def determine_lock_target(args) -> str | None:
    """根据命令参数生成写锁标签，便于并发冲突时定位占用命令。"""
    write_cmds = {"init", "sync", "summary", "intake", "done", "check", "switch"}
    if args.cmd not in write_cmds:
        return None
    if args.cmd == "summary":
        return "summary --stage" if args.stage else "summary"
    if args.cmd == "done":
        suffix = []
        if args.dry_run:
            suffix.append("--dry-run")
        if args.force:
            suffix.append("--force")
        return " ".join(["done"] + suffix).strip()
    return args.cmd


def execute_command(args, ctx) -> bool:
    """根据解析结果分发命令；写命令执行期间持有单写者锁。"""
    ok = True
    lock_target = determine_lock_target(args)
    lock_ctx = ctx.write_lock(lock_target) if lock_target else contextlib.nullcontext()

    try:
        with lock_ctx:
            if args.cmd == "init":
                ok = ctx.init_stage(args.name)

            elif args.cmd == "sync":
                ok = ctx.sync_log(args.message, args.task_name, args.status, args.next_action, args.blocked_by, args.file)

            elif args.cmd == "summary":
                if args.stage:
                    if not all([args.name, args.goal, args.audit, args.debt]):
                        ctx.info("[!] --stage 模式下必须提供 --name --goal --audit --debt")
                        return False
                    ok = ctx.append_stage_summary(args.name, args.goal, args.result or [], args.audit, args.debt, args.file)
                else:
                    if not args.text:
                        ctx.info("[!] 非 --stage 模式下必须提供 text")
                        return False
                    ctx.update_session_summary(args.text)

            elif args.cmd == "intake":
                ok = ctx.intake_backlog(args.keyword, dry_run=args.dry_run, file_target=args.file)

            elif args.cmd == "bootstrap":
                ctx.render_dashboard("full")

            elif args.cmd == "status":
                ctx.render_dashboard("brief", file_target=getattr(args, "file", None))

            elif args.cmd == "validate":
                filename, filepath = ctx.resolve_stage_file(getattr(args, "file", None))
                if not filename or not filepath:
                    ctx.info("[!] 当前没有可操作的阶段文件。")
                    return False
                errors, warns = ctx.validate_stage_document(filepath)
                ctx.emit("validate", {"file": filename, "errors": errors, "warnings": warns})
                if not errors and not warns:
                    ctx.info(f"[OK] 校验通过: {filename}")
                else:
                    ctx.info(f"[CHECK] {filename}")
                    for err in errors:
                        ctx.info(f"  [ERROR] {err}")
                    for warn in warns:
                        ctx.info(f"  [WARN]  {warn}")
                    if errors:
                        ok = False

            elif args.cmd == "done":
                ok = ctx.archive_stage(force=args.force, dry_run=args.dry_run, file_target=getattr(args, "file", None))

            elif args.cmd == "check":
                ok = ctx.check_item(args.item_id, uncheck=args.uncheck, file_target=getattr(args, "file", None))

            elif args.cmd == "switch":
                ok = ctx.switch_stage(args.target)
    except RuntimeError as exc:
        ctx.info(str(exc))
        ok = False

    return ok
