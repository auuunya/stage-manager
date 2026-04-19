import re


def rewrite_stages_index(ctx, current_stage=None):
    """重建 STAGES.md 阶段列表，并重算当前/其他/归档标签。"""
    ctx.ensure_structure()
    existing = ctx.read_text(ctx.cfg.stages_index)

    qs_match = re.search(r"(^---\n\n## 快速状态.*$)", existing, re.M | re.S)
    quick_status = qs_match.group(1) if qs_match else (
        f"---\n\n## 快速状态\n- [HEARTBEAT] Init\n- [LAST_SESSION] 暂无记录\n"
        f"- 最近同步: {ctx.now_datetime()} | 用户: {ctx.get_sys_user()} | Version: {ctx.get_git_info()}\n"
    )

    active_files = ctx.list_md_files(ctx.cfg.stages_exec_dir)
    archived_files = ctx.list_md_files(ctx.cfg.archive_exec_dir)

    if not current_stage:
        old = re.search(r"`\.stages/stages/(stage-\d+-.*?\.md)`（当前阶段）", existing)
        if old and old.group(1) in active_files:
            current_stage = old.group(1)
    if not current_stage and active_files:
        current_stage = active_files[0]

    lines = [
        "# Stages Index\n\n> 此文件由 stage-manager 自动维护。所有资产位于 .stages/ 目录下。\n\n---\n\n## 阶段清单\n"
    ]
    idx = 1
    if active_files:
        ordered = [current_stage] + [f for f in active_files if f != current_stage] if current_stage else active_files
        for filename in ordered:
            tag = "当前阶段" if filename == current_stage else "其他阶段"
            lines.append(f"{idx}. `.stages/stages/{filename}`（{tag}）\n")
            idx += 1
    for filename in archived_files:
        lines.append(f"{idx}. `.stages/archive/stages/{filename}`（已归档）\n")
        idx += 1

    lines.append("\n" + quick_status.strip("\n") + "\n")
    ctx.write_text(ctx.cfg.stages_index, "".join(lines))


def update_heartbeat(ctx):
    """仅刷新 STAGES.md 的统计、最近会话和最近同步元数据。"""
    ctx.ensure_structure()
    stats = ctx.get_project_stats()
    session = ctx.get_last_session_text()
    now = ctx.now_datetime()
    user = ctx.get_sys_user()
    ver = ctx.get_git_info()

    lines = ctx.read_text(ctx.cfg.stages_index).splitlines(True)
    found_sync = False
    for index, line in enumerate(lines):
        if "[HEARTBEAT]" in line:
            lines[index] = f"- [HEARTBEAT] {stats}\n"
        elif "[LAST_SESSION]" in line:
            lines[index] = f"- [LAST_SESSION] {session}\n"
        elif "最近同步" in line:
            lines[index] = f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n"
            found_sync = True
    if not found_sync:
        lines.append(f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n")
    ctx.write_text(ctx.cfg.stages_index, "".join(lines))


def update_adr_index(ctx, clean_msg: str, stage_file: str, is_archive: bool = False) -> str:
    """向 ADRS.md 追加决策目录项，同时更新总数和最近更新时间。"""
    ctx.ensure_structure()
    lines = ctx.read_text(ctx.cfg.adr_index).splitlines(True)
    count = ctx.count_adrs_from_index()
    adr_id = f"ADRS-{count + 1:03d}"
    prefix = ".stages/archive/stages/" if is_archive else ".stages/stages/"
    entry = f"{count + 1}. [{adr_id}] {clean_msg} ({prefix}{stage_file})\n"

    insert_idx = next((i + 1 for i, line in enumerate(lines) if "决策目录" in line), -1)
    if insert_idx != -1:
        lines.insert(insert_idx + count, entry)
    else:
        lines.append("\n" + entry)

    for index, line in enumerate(lines):
        if "总计决策" in line:
            lines[index] = f"- 总计决策: {count + 1}\n"
        elif "最近更新" in line:
            lines[index] = f"- 最近更新: {ctx.now_datetime()}\n"

    ctx.write_text(ctx.cfg.adr_index, "".join(lines))
    return adr_id


def update_session_summary(ctx, text: str):
    """向 STAGE_SESSIONS.md 头部写入会话快照，并裁剪历史上限。"""
    ctx.ensure_structure()
    clean = ctx.clean_summary_text(text)
    active_file, _ = ctx.get_latest_stage_info()
    now = ctx.now_datetime()

    lines = ctx.read_text(ctx.cfg.session_file).splitlines(True)
    entry = f"### [{now}] Stage: {active_file or 'Global'}\n- **会话快照**: {clean}\n\n"

    insert_idx = next((i + 1 for i, line in enumerate(lines) if "会话摘要" in line), -1)
    if insert_idx != -1:
        lines.insert(insert_idx + 1, entry)
    else:
        lines.append(entry)

    for index, line in enumerate(lines):
        if line.startswith("- 最近记录") or line.startswith("- 暂无活动记录"):
            lines[index] = f"- 最近记录: [{now}] {clean[:60]}...\n"
            break

    indices = [i for i, line in enumerate(lines) if line.startswith("### [")]
    if len(indices) > ctx.session_max_entries:
        lines = lines[:indices[ctx.session_max_entries]]

    ctx.write_text(ctx.cfg.session_file, "".join(lines))
    ctx.update_heartbeat()
