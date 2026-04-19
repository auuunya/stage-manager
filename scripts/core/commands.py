#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stage-Manager 剩余命令实现：init、check、switch 与 backlog 认领。"""

import os
import re
from typing import List, Optional


def init_stage(ctx, name: str) -> bool:
    """初始化新阶段文档，并将其注册为当前阶段。"""
    _, max_num = ctx.get_latest_stage_info()
    next_num = f"{int(max_num) + 1:03d}"
    slug = ctx.slugify_name(name)
    existing = ctx.check_stage_name_exists(slug)
    if existing:
        ctx.info(f"[!] 已存在同名阶段: {existing}")
        return False

    filename = f"stage-{next_num}-{slug}.md"
    filepath = os.path.join(ctx.cfg.stages_exec_dir, filename)
    if not os.path.exists(ctx.template_path):
        ctx.info(f"[!] 模板不存在: {ctx.template_path}")
        return False

    template = ctx.read_text(ctx.template_path)
    stage_id = f"STAGE-{next_num}"
    display = name.strip() or "TBD"
    content = ctx.replace_frontmatter(
        template,
        {
            "stage_id": stage_id,
            "name": display,
            "status": "PLANNING",
            "start_date": ctx.now_date(),
            "end_date": None,
            "depends_on": [],
            "milestone": None,
        },
    )
    content = ctx.update_title(content, stage_id, display)
    ctx.write_text(filepath, content)
    ctx.rewrite_stages_index(current_stage=filename)
    ctx.update_heartbeat()
    ctx.info(f"[*] 初始化阶段: {filename}")
    return True


def check_stage_name_exists(ctx, slug: str) -> Optional[str]:
    """检查给定 slug 是否已存在于未归档或归档阶段文件中。"""
    pattern = re.compile(rf"^stage-\d+-{re.escape(slug)}\.md$")
    for directory in [ctx.cfg.stages_exec_dir, ctx.cfg.archive_exec_dir]:
        if not os.path.exists(directory):
            continue
        for filename in os.listdir(directory):
            if pattern.match(filename):
                return filename
    return None


def check_item(ctx, item_id: str, uncheck: bool = False, file_target: Optional[str] = None) -> bool:
    """切换 TASK 或 AC 条目的勾选状态，并刷新 heartbeat。"""
    filename, filepath = ctx.resolve_stage_file(file_target)
    if not filename or not filepath:
        ctx.info("[!] 当前没有可操作的阶段文件。")
        return False

    content = ctx.read_text(filepath)
    if item_id.startswith("TASK-"):
        section_no = 4
    elif item_id.startswith("AC-"):
        section_no = 5
    else:
        ctx.info(f"[!] 无法识别 ID 类型: {item_id}（支持 TASK-XXX 或 AC-XXX）")
        return False

    new_mark = "[ ]" if uncheck else "[x]"
    pattern = re.compile(rf"^(\s*-\s*)\[{'[xX]' if uncheck else ' '}\](\s+.*\[{re.escape(item_id)}\].*)$", re.M)

    section = ctx.find_section_block(content, section_no)
    if not section:
        ctx.info(f"[!] 未找到 section {section_no}。")
        return False

    match = pattern.search(content)
    if not match:
        ctx.info(f"[!] 未找到匹配的条目 {item_id}（当前状态可能已是目标状态）。")
        return False

    new_line = f"{match.group(1)}{new_mark}{match.group(2)}"
    content = content[:match.start()] + new_line + content[match.end():]
    ctx.write_text(filepath, content)
    ctx.update_heartbeat()

    action = "取消勾选" if uncheck else "勾选"
    ctx.info(f"[OK] 已{action}: {item_id}")
    ctx.emit("checked", {"id": item_id, "new_state": "unchecked" if uncheck else "checked"})
    return True


def switch_stage(ctx, target: str) -> bool:
    """切换当前活跃阶段，并同步更新索引与 heartbeat。"""
    filename, filepath = ctx.resolve_stage_file(target)
    if not filename or not filepath:
        ctx.info(f"[!] 未找到阶段文件: {target}")
        return False
    if not filepath.startswith(os.path.abspath(ctx.cfg.stages_exec_dir)):
        ctx.info(f"[!] 只能切换到活跃阶段（非归档）: {filename}")
        return False
    ctx.rewrite_stages_index(current_stage=filename)
    ctx.update_heartbeat()
    ctx.info(f"[OK] 当前阶段已切换为: {filename}")
    ctx.emit("switched", {"current_stage": filename})
    return True


def intake_backlog(ctx, keyword: str, dry_run: bool = False, file_target: Optional[str] = None) -> bool:
    """按关键字从 backlog 认领任务；非 dry-run 时同时修改 backlog 与阶段文件。"""
    filename, filepath = ctx.resolve_stage_file(file_target)
    if not filename or not filepath:
        ctx.info("[!] 错误：当前没有可操作的阶段文件。")
        return False

    lines = ctx.read_text(ctx.cfg.backlog_file).splitlines(True)
    extracted, remaining = [], []
    for line in lines:
        if line.strip().startswith("- [ ]") and keyword.lower() in line.lower():
            extracted.append(line.strip())
        else:
            remaining.append(line)

    if not extracted:
        ctx.info(f"[!] 未在 BACKLOGS.md 中找到匹配 '{keyword}' 的任务。")
        return False

    content = ctx.read_text(filepath)
    existing_nums = [int(match.group(1)) for match in re.finditer(r"\[TASK-(\d{3})\]", content) if int(match.group(1)) < 900]
    next_num = max(existing_nums, default=0) + 1

    normalized = []
    for raw in extracted:
        new_id = f"TASK-{next_num:03d}"
        normalized.append(ctx.normalize_backlog_task_line(raw, new_id))
        next_num += 1

    if dry_run:
        ctx.info(f"[DRY-RUN] 将从 Backlog 认领 {len(normalized)} 个任务至 {filename}:")
        for task in normalized:
            ctx.info(f"  {task}")
        return True

    full = "".join(remaining)
    full = re.sub(r"### 来自 .*? \(\d{4}-\d{2}-\d{2}\)\n\s*(?=###|##|$)", "", full, flags=re.S)
    ctx.write_text(ctx.cfg.backlog_file, full)

    content = ctx.prepend_to_section_body(content, 4, "\n".join(normalized), remove_placeholder_tbd=True)
    ctx.write_text(filepath, content)

    ctx.update_heartbeat()
    ctx.info(f"[OK] 已从 Backlog 认领 {len(normalized)} 个任务并载入 {filename}。")
    return True


def route_backlog(ctx, tasks: List[str], stage_file: str, category_marker: str):
    """将任务或非范围条目回流到 backlog 指定分区。"""
    if not tasks:
        return
    lines = ctx.read_text(ctx.cfg.backlog_file).splitlines(True)
    source_label = "非范围条目" if category_marker == "[ROADMAP]" else "溢出与未完成任务"
    header = f"### 来自 {stage_file} 的{source_label} ({ctx.now_date()})\n"

    insert_idx = next((index + 1 for index, line in enumerate(lines) if category_marker in line), -1)
    if insert_idx == -1:
        ctx.info(f"[!] 警告: BACKLOGS.md 中未找到 '{category_marker}' 标记，任务分流跳过。")
        return

    new_content = [header] + [f"{task}\n" if not task.endswith("\n") else task for task in tasks] + ["\n"]
    for item in reversed(new_content):
        lines.insert(insert_idx, item)
    ctx.write_text(ctx.cfg.backlog_file, "".join(lines))
