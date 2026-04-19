import os
import re


def check_p0_completed(ctx, filepath):
    """返回阶段文档中 P0 任务是否已全部完成，以及未完成条目。"""
    def _is_unchecked_p0(line: str) -> bool:
        """判断任务行是否表示一个尚未勾选的 P0 任务。"""
        parsed = ctx.parse_task_line(line)
        return parsed is not None and parsed["priority"] == "P0" and not parsed["checked"]

    return ctx.check_section_items(filepath, 4, _is_unchecked_p0)


def check_dod_completed(ctx, filepath):
    """返回验收标准是否已全部勾选，以及未完成条目。"""
    return ctx.check_section_items(filepath, 5, lambda line: re.match(r"^\s*-\s*\[ \]", line) is not None)


def has_summary_content(ctx, filepath):
    """判断阶段总结 section 是否已包含非占位内容。"""
    if not os.path.exists(filepath):
        return False
    sec = ctx.find_section_block(ctx.read_text(filepath), 9)
    return sec is not None and not re.fullmatch(r"\s*-\s*暂无\s*", sec[3].strip())


def check_implementation_evidence(ctx, filepath):
    """检查实施型阶段是否引用了真实代码、测试或配置 evidence。"""
    if not os.path.exists(filepath):
        return False, []
    content = ctx.read_text(filepath)
    if ctx.infer_stage_type(content) != "implementation":
        return True, []

    evidence_paths = []
    for sec_no, parser in [(4, ctx.parse_task_line), (5, ctx.parse_ac_line)]:
        sec = ctx.find_section_block(content, sec_no)
        if not sec:
            continue
        for line in re.findall(r"^\s*-\s*\[[ xX]\].*$", sec[3], re.M):
            parsed = parser(line)
            if parsed:
                evidence_paths.extend(parsed["evidence"])

    real = [path for path in dict.fromkeys(evidence_paths) if path and not path.startswith(".stage/")]
    return len(real) > 0, real


def validate_stage_document(ctx, filepath):
    """汇总阶段文档的 schema、一致性和 evidence 校验结果。"""
    errors = []
    warns = []

    if not os.path.exists(filepath):
        return [f"文件不存在: {filepath}"], []

    content = ctx.read_text(filepath)
    fm, _ = ctx.parse_frontmatter(content)

    for key in ctx.fm_key_order:
        if key not in fm:
            errors.append(f"frontmatter 缺少字段: {key}")
    if "status" in fm and fm["status"] not in ctx.allowed_stage_status:
        errors.append(f"stage status 非法: {fm['status']}")

    for date_key in ("start_date", "end_date"):
        if date_key in fm and fm[date_key] not in (None, "null"):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fm[date_key])):
                errors.append(f"{date_key} 日期格式非法: {fm[date_key]}")

    if fm.get("status") in {"COMPLETED", "ARCHIVED"} and not fm.get("end_date"):
        errors.append("状态为 COMPLETED/ARCHIVED 时，end_date 不得为 null")
    if fm.get("status") in {"PLANNING", "IN_PROGRESS", "TESTING"} and fm.get("end_date"):
        warns.append("未归档阶段通常不应填写 end_date")

    for sec in range(1, 10):
        if not ctx.find_section_block(content, sec):
            errors.append(f"缺少 section: ## {sec}.")

    task_ids, ac_ids = [], []
    task_to_ac = {}
    ac_to_task = {}

    for sec_no, parser, validator, id_key, ref_key in [
        (4, ctx.parse_task_line, ctx.validate_task_line, "task_id", "acceptance"),
        (5, ctx.parse_ac_line, ctx.validate_ac_line, "ac_id", "required_tasks"),
    ]:
        sec = ctx.find_section_block(content, sec_no)
        if not sec:
            continue
        lines = re.findall(r"^\s*-\s*\[[ xX]\].*$", sec[3], re.M)
        if not lines:
            warns.append(f"{'任务拆解' if sec_no == 4 else '验收标准'} section 中暂无 checklist")
        for line in lines:
            errors.extend(validator(line))
            parsed = parser(line)
            if not parsed:
                continue
            item_id = str(parsed[id_key])
            if sec_no == 4:
                task_ids.append(item_id)
                task_to_ac[item_id] = list(parsed[ref_key])
                if parsed["priority"] == "P0" and not parsed["evidence"]:
                    warns.append(f"{item_id} 为 P0 任务但 evidence 为空")
            else:
                ac_ids.append(item_id)
                ac_to_task[item_id] = list(parsed[ref_key])
                if parsed["verify_by"] == "artifact_presence" and not parsed["evidence"]:
                    errors.append(f"{item_id} verify_by=artifact_presence 时 evidence 不得为空")
                elif not parsed["evidence"]:
                    warns.append(f"{item_id} evidence 为空")

    if len(task_ids) != len(set(task_ids)):
        errors.append("任务 ID 存在重复")
    if len(ac_ids) != len(set(ac_ids)):
        errors.append("验收项 ID 存在重复")

    ac_set, task_set = set(ac_ids), set(task_ids)
    for task_id, refs in task_to_ac.items():
        for ac in refs:
            if ac not in ac_set:
                errors.append(f"{task_id} 引用了不存在的验收项: {ac}")
    for ac_id, refs in ac_to_task.items():
        for task_id in refs:
            if task_id not in task_set:
                errors.append(f"{ac_id} 引用了不存在的任务: {task_id}")

    if "TASK-900" not in task_set:
        warns.append("建议增加 TASK-900 阶段验收任务")

    for sec_no, label in [(7, "进度日志"), (9, "阶段总结")]:
        sec = ctx.find_section_block(content, sec_no)
        if sec and re.fullmatch(r"\s*-\s*暂无\s*", sec[3].strip()):
            warns.append(f"{label}为空")

    if ctx.infer_stage_type(content) == "implementation":
        ok, _ = ctx.check_implementation_evidence(filepath)
        if not ok:
            warns.append("实施型阶段尚未发现实际代码/测试/配置 evidence")

    return errors, warns
