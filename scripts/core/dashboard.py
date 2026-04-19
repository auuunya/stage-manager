import re


def collect_dashboard_data(ctx, mode: str, file_target=None):
    """收集 dashboard 所需数据，不直接输出也不刷新索引。"""
    filename, filepath = ctx.resolve_stage_file(file_target)
    data = {
        "stats": ctx.get_project_stats_dict(),
        "stats_str": ctx.get_project_stats(),
        "mode": mode,
    }
    if filename and filepath:
        data["current_stage"] = filename
        data["progress"] = ctx.calculate_progress(filepath)
        data["pending_tasks"] = ctx.get_pending_tasks(filepath)
    data["recent_sessions"] = re.findall(r"- \*\*会话快照\*\*: (.*?)\n", ctx.read_text(ctx.cfg.session_file))[:3]
    data["recent_adrs"] = re.findall(r"^\d+\. (\[ADRS-\d+\].*?)$", ctx.read_text(ctx.cfg.adr_index), re.M)[-3:]
    if mode == "full":
        data["backlog_count"] = len(re.findall(r"^\s*-\s*\[ \]", ctx.read_text(ctx.cfg.backlog_file), re.M))
        data["skill_path"] = ctx.skill_path
        data["asset_root"] = ctx.cfg.asset_root
    return data


def render_dashboard_json(ctx, data):
    """将 dashboard 数据整理为 JSON 输出载荷。"""
    out = {"stats": data["stats"]}
    for key in ("current_stage", "progress", "recent_sessions", "recent_adrs",
                "backlog_count", "skill_path", "asset_root"):
        if key in data:
            out[key] = data[key]
    if "pending_tasks" in data:
        out["pending_tasks"] = data["pending_tasks"][:5]
    ctx.emit("dashboard", out)


def render_dashboard_text(ctx, data):
    """将 dashboard 数据格式化为控制台文本。"""
    mode = data["mode"]
    stats_str = data["stats_str"]

    ctx.info("\n" + "=" * 50)
    ctx.info(" [BOOTSTRAP] 会话上下文恢复中..." if mode == "full" else f" [项目健康度] {stats_str}")
    ctx.info("=" * 50)

    if mode == "full":
        ctx.info(f"\n [项目概览] {stats_str}")

    if "current_stage" in data:
        progress = data["progress"]
        bar = "#" * int(progress / 5) + "-" * (20 - int(progress / 5))
        ctx.info(f" [{'活跃阶段' if mode == 'full' else '阶段文件'}] {data['current_stage']}")
        ctx.info(f" [完成进度] [{bar}] {progress}%")
        pending = data.get("pending_tasks", [])
        if pending:
            limit = 3 if mode == "full" else 5
            plabel = "下一步待办" if mode == "full" else "未完成任务"
            ctx.info(f"\n [{plabel}] (前{limit}条):")
            for task in pending[:limit]:
                ctx.info(f"  [ ] {task.strip()}")
    elif mode == "full":
        ctx.info(" [活跃阶段] 无活跃阶段")

    sessions = data.get("recent_sessions", [])
    if sessions:
        ctx.info(f"\n [{'记忆锚点' if mode == 'full' else '最近会话'}] {'最近会话快照' if mode == 'full' else '(最近3条)'}:")
        trunc = 100 if mode == "full" else 80
        for session in sessions[:3]:
            ctx.info(f"  > {session[:trunc]}{'...' if len(session) > trunc else ''}")
    elif mode == "full":
        ctx.info("\n [记忆锚点] 暂无历史快照。")

    adrs = data.get("recent_adrs", [])
    if adrs:
        ctx.info("\n [最近决策] (最近3条):" if mode == "brief" else "\n [最近决策]:")
        for adr in adrs[-3:]:
            ctx.info(f"  * {adr.strip()}")

    if mode == "full":
        backlog_count = data.get("backlog_count", 0)
        if backlog_count > 0:
            ctx.info(f"\n [Backlog] {backlog_count} 个待认领任务")
        ctx.info(f"\n [Skill 路径] {ctx.skill_path}")
        ctx.info(f" [资产目录] {ctx.cfg.asset_root}")

    ctx.info("\n" + "=" * 50)
    if mode == "full":
        ctx.info(" [OK] Bootstrap 完成。")
    ctx.info("=" * 50 + "\n")


def render_dashboard(ctx, mode: str = "full", file_target=None) -> bool:
    """统一渲染 dashboard，并在结束后刷新 heartbeat。"""
    data = collect_dashboard_data(ctx, mode, file_target)
    if ctx.json_mode:
        render_dashboard_json(ctx, data)
    else:
        render_dashboard_text(ctx, data)
    ctx.update_heartbeat()
    return True
