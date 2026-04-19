#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stage-Manager 应用协调层：装配上下文并暴露稳定入口。"""

import argparse
import sys
from types import SimpleNamespace

from core.cli import build_parser, execute_command
from core.commands import (
    check_item as check_item_impl,
)
from core.commands import (
    check_stage_name_exists as check_stage_name_exists_impl,
)
from core.commands import (
    init_stage as init_stage_impl,
)
from core.commands import (
    intake_backlog as intake_backlog_impl,
)
from core.commands import (
    route_backlog as route_backlog_impl,
)
from core.commands import (
    switch_stage as switch_stage_impl,
)
from core.dashboard import render_dashboard as render_dashboard_impl
from core.doc import (
    FM_KEY_ORDER,
    calculate_progress,
    check_section_items,
    clean_summary_text,
    count_adrs_from_index,
    extract_summary_brief,
    find_section_block,
    get_last_session_text,
    get_latest_stage_info,
    get_pending_tasks,
    get_project_stats,
    get_project_stats_dict,
    infer_stage_type,
    list_md_files,
    normalize_backlog_task_line,
    parse_ac_line,
    parse_frontmatter,
    parse_task_line,
    prepend_to_section_body,
    render_adr_entry,
    render_log_entry,
    render_summary_entry,
    replace_frontmatter,
    replace_section_body,
    resolve_stage_file,
    update_title,
    validate_ac_line,
    validate_task_line,
)
from core.indexes import (
    rewrite_stages_index as rewrite_stages_index_impl,
)
from core.indexes import (
    update_adr_index as update_adr_index_impl,
)
from core.indexes import (
    update_heartbeat as update_heartbeat_impl,
)
from core.indexes import (
    update_session_summary as update_session_summary_impl,
)
from core.ops import (
    append_stage_summary as append_stage_summary_impl,
)
from core.ops import (
    archive_stage as archive_stage_impl,
)
from core.ops import (
    sync_log as sync_log_impl,
)
from core.runtime import (
    ALLOWED_LOG_STATUS,
    ALLOWED_STAGE_STATUS,
    SESSION_MAX_ENTRIES,
    SKILL_DIR,
    TEMPLATE_PATH,
    VERSION,
    _out,
    cfg,
    discover_project_root,
    emit,
    ensure_structure,
    flush_json,
    get_git_info,
    get_sys_user,
    info,
    now_date,
    now_datetime,
    read_text,
    slugify_name,
    write_lock,
    write_text,
)
from core.validate import (
    check_dod_completed as check_dod_completed_impl,
)
from core.validate import (
    check_implementation_evidence as check_implementation_evidence_impl,
)
from core.validate import (
    check_p0_completed as check_p0_completed_impl,
)
from core.validate import (
    has_summary_content as has_summary_content_impl,
)
from core.validate import (
    validate_stage_document as validate_stage_document_impl,
)


def _build_indexes_ctx():
    """构建索引维护函数所需的上下文。"""
    return SimpleNamespace(
        cfg=cfg,
        ensure_structure=ensure_structure,
        read_text=read_text,
        now_datetime=now_datetime,
        get_sys_user=get_sys_user,
        get_git_info=get_git_info,
        list_md_files=list_md_files,
        write_text=write_text,
        get_project_stats=get_project_stats,
        get_last_session_text=get_last_session_text,
        count_adrs_from_index=count_adrs_from_index,
        clean_summary_text=clean_summary_text,
        get_latest_stage_info=get_latest_stage_info,
        session_max_entries=SESSION_MAX_ENTRIES,
    )


def rewrite_stages_index(current_stage: str | None = None):
    """组装索引上下文并委派重写 `STAGES.md`。"""
    return rewrite_stages_index_impl(_build_indexes_ctx(), current_stage)


def update_heartbeat():
    """组装统计上下文并委派刷新 `STAGES.md` heartbeat。"""
    return update_heartbeat_impl(_build_indexes_ctx())


def update_adr_index(clean_msg: str, stage_file: str, is_archive: bool = False) -> str:
    """组装 ADR 索引上下文并委派写入。"""
    return update_adr_index_impl(_build_indexes_ctx(), clean_msg, stage_file, is_archive)


def update_session_summary(text: str):
    """组装会话索引上下文并委派写入快照。"""
    ctx = _build_indexes_ctx()
    ctx.update_heartbeat = update_heartbeat
    return update_session_summary_impl(ctx, text)


def _build_validate_ctx():
    """构建阶段文档校验所需的上下文。"""
    return SimpleNamespace(
        read_text=read_text,
        parse_frontmatter=parse_frontmatter,
        fm_key_order=FM_KEY_ORDER,
        allowed_stage_status=ALLOWED_STAGE_STATUS,
        find_section_block=find_section_block,
        parse_task_line=parse_task_line,
        validate_task_line=validate_task_line,
        parse_ac_line=parse_ac_line,
        validate_ac_line=validate_ac_line,
        infer_stage_type=infer_stage_type,
        check_implementation_evidence=check_implementation_evidence,
        check_section_items=check_section_items,
    )


def check_p0_completed(filepath: str):
    """组装校验依赖并委派 P0 完成性检查。"""
    ctx = SimpleNamespace(parse_task_line=parse_task_line, check_section_items=check_section_items)
    return check_p0_completed_impl(ctx, filepath)


def check_dod_completed(filepath: str):
    """组装校验依赖并委派 DoD 完成性检查。"""
    return check_dod_completed_impl(SimpleNamespace(check_section_items=check_section_items), filepath)


def has_summary_content(filepath: str) -> bool:
    """判断阶段总结 section 是否已有真实内容。"""
    ctx = SimpleNamespace(read_text=read_text, find_section_block=find_section_block)
    return has_summary_content_impl(ctx, filepath)


def check_implementation_evidence(filepath: str):
    """检查实施型阶段是否引用了真实 evidence。"""
    ctx = SimpleNamespace(
        read_text=read_text,
        infer_stage_type=infer_stage_type,
        parse_task_line=parse_task_line,
        parse_ac_line=parse_ac_line,
        find_section_block=find_section_block,
    )
    return check_implementation_evidence_impl(ctx, filepath)


def validate_stage_document(filepath: str):
    """组装校验上下文并委派阶段文档完整校验。"""
    return validate_stage_document_impl(_build_validate_ctx(), filepath)


def _build_dashboard_ctx():
    """构建 dashboard 展示所需的上下文。"""
    return SimpleNamespace(
        cfg=cfg,
        resolve_stage_file=resolve_stage_file,
        get_project_stats_dict=get_project_stats_dict,
        get_project_stats=get_project_stats,
        calculate_progress=calculate_progress,
        get_pending_tasks=get_pending_tasks,
        read_text=read_text,
        skill_path=SKILL_DIR,
        json_mode=_out.json_mode,
        emit=emit,
        info=info,
        update_heartbeat=update_heartbeat,
    )


def render_dashboard(mode: str = "full", file_target: str | None = None) -> bool:
    """统一委派 dashboard 渲染，并保留刷新 heartbeat 的语义。"""
    return render_dashboard_impl(_build_dashboard_ctx(), mode, file_target)


def _build_commands_ctx():
    """构建独立命令实现所需的上下文。"""
    return SimpleNamespace(
        cfg=cfg,
        template_path=TEMPLATE_PATH,
        get_latest_stage_info=get_latest_stage_info,
        slugify_name=slugify_name,
        check_stage_name_exists=check_stage_name_exists,
        read_text=read_text,
        replace_frontmatter=replace_frontmatter,
        update_title=update_title,
        write_text=write_text,
        rewrite_stages_index=rewrite_stages_index,
        update_heartbeat=update_heartbeat,
        resolve_stage_file=resolve_stage_file,
        find_section_block=find_section_block,
        prepend_to_section_body=prepend_to_section_body,
        normalize_backlog_task_line=normalize_backlog_task_line,
        emit=emit,
        info=info,
        now_date=now_date,
    )


def init_stage(name: str) -> bool:
    """组装初始化上下文并委派创建新阶段。"""
    return init_stage_impl(_build_commands_ctx(), name)


def check_stage_name_exists(slug: str):
    """组装命令上下文并检查阶段名是否已存在。"""
    return check_stage_name_exists_impl(_build_commands_ctx(), slug)


def check_item(item_id: str, uncheck: bool = False, file_target: str | None = None) -> bool:
    """组装命令上下文并切换 TASK 或 AC 的勾选状态。"""
    return check_item_impl(_build_commands_ctx(), item_id, uncheck, file_target)


def switch_stage(target: str) -> bool:
    """组装命令上下文并切换当前活跃阶段。"""
    return switch_stage_impl(_build_commands_ctx(), target)


def route_backlog(tasks, stage_file: str, category_marker: str):
    """组装命令上下文并回流 backlog 条目。"""
    return route_backlog_impl(_build_commands_ctx(), tasks, stage_file, category_marker)


def intake_backlog(keyword: str, dry_run: bool = False, file_target: str | None = None) -> bool:
    """组装命令上下文并执行 backlog 认领。"""
    return intake_backlog_impl(_build_commands_ctx(), keyword, dry_run, file_target)


def _build_ops_ctx():
    """构建日志、总结与归档流程所需的上下文。"""
    return SimpleNamespace(
        cfg=cfg,
        allowed_log_status=ALLOWED_LOG_STATUS,
        resolve_stage_file=resolve_stage_file,
        info=info,
        read_text=read_text,
        update_adr_index=update_adr_index,
        prepend_to_section_body=prepend_to_section_body,
        render_adr_entry=render_adr_entry,
        render_log_entry=render_log_entry,
        parse_frontmatter=parse_frontmatter,
        replace_frontmatter=replace_frontmatter,
        write_text=write_text,
        update_heartbeat=update_heartbeat,
        render_summary_entry=render_summary_entry,
        validate_stage_document=validate_stage_document,
        check_p0_completed=check_p0_completed,
        check_dod_completed=check_dod_completed,
        has_summary_content=has_summary_content,
        check_implementation_evidence=check_implementation_evidence,
        find_section_block=find_section_block,
        route_backlog=route_backlog,
        extract_summary_brief=extract_summary_brief,
        now_date=now_date,
        replace_section_body=replace_section_body,
        list_md_files=list_md_files,
        rewrite_stages_index=rewrite_stages_index,
        update_session_summary=update_session_summary,
    )


def sync_log(
    message: str,
    task_name: str | None = None,
    status: str = "进行中",
    next_action: str | None = None,
    blocked_by: str | None = None,
    file_target: str | None = None,
) -> bool:
    """组装日志上下文并委派写入阶段日志与 ADR 存根。"""
    return sync_log_impl(_build_ops_ctx(), message, task_name, status, next_action, blocked_by, file_target)


def append_stage_summary(
    name: str, milestone_goal: str, core_results, change_audit: str, tech_debt: str, file_target: str | None = None
) -> bool:
    """组装总结上下文并委派写入阶段总结。"""
    return append_stage_summary_impl(
        _build_ops_ctx(), name, milestone_goal, core_results, change_audit, tech_debt, file_target
    )


def archive_stage(force: bool = False, dry_run: bool = False, file_target: str | None = None) -> bool:
    """组装归档上下文并委派执行归档流程。"""
    return archive_stage_impl(_build_ops_ctx(), force, dry_run, file_target)


def _build_cli_ctx():
    """构建 CLI 分发器所需的顶层上下文。"""
    return SimpleNamespace(
        cfg=cfg,
        template_path=TEMPLATE_PATH,
        write_lock=write_lock,
        get_latest_stage_info=get_latest_stage_info,
        slugify_name=slugify_name,
        check_stage_name_exists=check_stage_name_exists,
        init_stage=init_stage,
        read_text=read_text,
        replace_frontmatter=replace_frontmatter,
        update_title=update_title,
        write_text=write_text,
        rewrite_stages_index=rewrite_stages_index,
        update_heartbeat=update_heartbeat,
        sync_log=sync_log,
        append_stage_summary=append_stage_summary,
        update_session_summary=update_session_summary,
        intake_backlog=intake_backlog,
        render_dashboard=render_dashboard,
        resolve_stage_file=resolve_stage_file,
        validate_stage_document=validate_stage_document,
        archive_stage=archive_stage,
        check_item=check_item,
        switch_stage=switch_stage,
        emit=emit,
        info=info,
        now_date=now_date,
    )


def main():
    """初始化运行期上下文、解析 CLI，并执行对应命令。"""
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--root", help="指定项目根目录")
    base_parser.add_argument(
        "--json", action="store_true", help="输出 JSON 格式（适用于 bootstrap/status/validate/check）"
    )
    temp_args, _ = base_parser.parse_known_args()

    cfg.configure(discover_project_root(temp_args.root))
    _out.json_mode = temp_args.json

    parser = build_parser(VERSION, ALLOWED_LOG_STATUS)
    args = parser.parse_args()
    if args.json:
        _out.json_mode = True

    ensure_structure()
    ok = execute_command(args, _build_cli_ctx())

    flush_json()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
