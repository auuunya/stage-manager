import os
import re
import shutil


def sync_log(ctx, message: str, task_name=None, status: str = "进行中",
             next_action=None, blocked_by=None, file_target=None) -> bool:
    """向阶段文档追加日志；遇到 `[ADR]` 前缀时同步写入 ADR 存根和索引。"""
    filename, filepath = ctx.resolve_stage_file(file_target)
    if not filename or not filepath:
        ctx.info("[!] 当前没有可操作的阶段文件。")
        return False
    if status not in ctx.allowed_log_status:
        ctx.info(f"[!] 非法日志状态: {status}，允许值: {', '.join(sorted(ctx.allowed_log_status))}")
        return False

    content = ctx.read_text(filepath)

    if message.startswith("[ADR]"):
        clean_msg = message[5:].strip() or "TBD"
        adr_id = ctx.update_adr_index(clean_msg, filename, is_archive=("archive" in filepath))
        content = ctx.prepend_to_section_body(
            content,
            8,
            ctx.render_adr_entry(adr_id, clean_msg),
            remove_placeholder_tbd=True,
        )
        ctx.info(f"[OK] 已创建 ADR 存根: {adr_id}")

    content = ctx.prepend_to_section_body(
        content,
        7,
        ctx.render_log_entry(filepath, message, task_name, status, next_action, blocked_by),
        remove_placeholder_tbd=True,
    )

    fm, _ = ctx.parse_frontmatter(content)
    cur_status = str(fm.get("status"))
    new_status = "IN_PROGRESS" if cur_status == "PLANNING" else cur_status
    if new_status != fm.get("status"):
        content = ctx.replace_frontmatter(content, {"status": new_status})

    ctx.write_text(filepath, content)
    ctx.update_heartbeat()
    ctx.info(f"[OK] 已同步到 {filename}")
    return True


def append_stage_summary(ctx, name: str, milestone_goal: str, core_results,
                         change_audit: str, tech_debt: str, file_target=None) -> bool:
    """向阶段文档 section 9 追加总结记录，并刷新 heartbeat。"""
    filename, filepath = ctx.resolve_stage_file(file_target)
    if not filename or not filepath:
        ctx.info("[!] 当前没有可操作的阶段文件。")
        return False
    content = ctx.read_text(filepath)
    entry = ctx.render_summary_entry(filepath, name, milestone_goal, core_results, change_audit, tech_debt)
    content = ctx.prepend_to_section_body(content, 9, entry, remove_placeholder_tbd=True)
    ctx.write_text(filepath, content)
    ctx.update_heartbeat()
    ctx.info(f"[OK] 已写入阶段总结: {filename}")
    return True


def archive_stage(ctx, force: bool = False, dry_run: bool = False, file_target=None) -> bool:
    """完成归档闭环：校验门禁、回流 backlog、迁移文件并写入会话摘要。"""
    filename, src = ctx.resolve_stage_file(file_target)
    if not filename or not src:
        ctx.info("[!] 当前没有可操作的阶段文件。")
        return False
    if src.startswith(os.path.abspath(ctx.cfg.archive_exec_dir)):
        ctx.info("[!] 该阶段已经位于 archive 目录。")
        return False

    errors, warns = ctx.validate_stage_document(src)
    if errors and not force:
        ctx.info("[!] 归档前校验失败：")
        for err in errors:
            ctx.info(f"  [ERROR] {err}")
        for warn in warns:
            ctx.info(f"  [WARN]  {warn}")
        ctx.info("[?] 请先修复上述 ERROR。需要强制继续时使用: done --force")
        return False

    gates = [
        (ctx.check_p0_completed, "仍存在未完成的 [P0] 任务", "请先完成上述 P0 任务"),
        (ctx.check_dod_completed, "## 5. 验收标准 (DoD) 未能全量通过", "请先完成上述验收项"),
    ]
    for checker, fail_msg, fix_msg in gates:
        ok, pending = checker(src)
        if not ok and not force:
            ctx.info(f"\n[!] 归档拒绝：{fail_msg}。")
            for item in pending:
                ctx.info(f"  {item}")
            ctx.info(f"\n[?] {fix_msg}。需要强制继续时使用: done --force")
            return False

    if not ctx.has_summary_content(src) and not force:
        ctx.info("\n[!] 归档拒绝：## 9. 阶段总结 仍为空。")
        ctx.info("[?] 请先补充阶段总结。需要强制继续时使用: done --force")
        return False

    impl_ok, _ = ctx.check_implementation_evidence(src)
    if not impl_ok and not force:
        ctx.info("\n[!] 归档拒绝：实施型阶段尚未发现实际代码/测试/配置 evidence。")
        ctx.info("[?] 请先补充可验证 evidence。需要强制继续时使用: done --force")
        return False

    if dry_run:
        ctx.info(f"[DRY-RUN] 将归档阶段: {filename}")
        for warn in warns:
            ctx.info(f"[DRY-RUN][WARN] {warn}")
        return True

    content = ctx.read_text(src)

    oos = ctx.find_section_block(content, 3)
    if oos:
        items = re.findall(r"^\s*-\s+\[OUT-SCOPE-\d+\].*$", oos[3], re.M)
        if items:
            ctx.route_backlog(items, filename, "[ROADMAP]")

    tasks = ctx.find_section_block(content, 4)
    if tasks:
        unfinished = re.findall(r"^\s*-\s*\[ \].*$", tasks[3], re.M)
        if unfinished:
            ctx.route_backlog(unfinished, filename, "[TECH_DEBT]")

    summary = ctx.extract_summary_brief(content)
    content = ctx.replace_frontmatter(content, {"status": "COMPLETED", "end_date": ctx.now_date()})

    if not ctx.has_summary_content(src):
        content = ctx.replace_section_body(content, 9, ctx.render_summary_entry(
            src,
            "Archive Summary",
            "阶段归档。",
            ["阶段已完成归档流程。"],
            "归档时自动补写状态与结束日期。",
            "已按规则分流至 Backlog。",
        ))

    ctx.write_text(src, content)

    dst = os.path.join(ctx.cfg.archive_exec_dir, filename)
    shutil.copy2(src, dst)
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
        ctx.info("[!] 归档复制验证失败，保留源文件。")
        return False
    os.remove(src)

    remaining = ctx.list_md_files(ctx.cfg.stages_exec_dir)
    ctx.rewrite_stages_index(current_stage=remaining[0] if remaining else None)
    ctx.update_session_summary(f"[归档自动化] 阶段 {filename} 已结项: {summary}")
    ctx.info("[OK] 归档完成。")
    return True
