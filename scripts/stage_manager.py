#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stage-Manager: 项目生命周期管理脚本

功能：阶段初始化、进度同步、ADR 编号与注入、DoD 硬门禁、Backlog 认领、
会话摘要、阶段总结、归档与索引维护、schema 校验。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

# -------------------------------------------------------------------
# 常量 & 配置
# -------------------------------------------------------------------

SESSION_MAX_ENTRIES = 20
VERSION = "1.1.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATE_PATH = os.path.join(SKILL_DIR, "references", "stage_template.md")

ALLOWED_STAGE_STATUS = {"PLANNING", "IN_PROGRESS", "TESTING", "COMPLETED", "ARCHIVED"}
ALLOWED_LOG_STATUS = {"已完成", "进行中", "阻塞"}
ALLOWED_EXECUTOR = {"human", "agent", "sub_agent"}
ALLOWED_VERIFY_BY = {"task_completion", "evidence_review", "metric_threshold", "artifact_presence"}

# @section 锚点 → 章节编号映射
_SECTION_ANCHORS = {
    1: "goals", 2: "scope", 3: "out_of_scope", 4: "tasks",
    5: "dod", 6: "risks", 7: "log", 8: "adrs", 9: "summary",
}
_ANCHOR_TO_NUM = {v: k for k, v in _SECTION_ANCHORS.items()}

STRINGS = {
    "stages_index_head": (
        "# Stages Index\n\n"
        "> 此文件由 stage-manager 自动维护。所有资产位于 .stages/ 目录下。\n\n"
        "---\n\n## 阶段清单\n"
    ),
    "adrs_head": "# Architectural Decision Records (ADRS)\n\n---\n\n## 决策目录\n",
    "sessions_head": "# Stage Session Logs (Compressed)\n\n---\n\n## 会话摘要\n",
    "backlogs_head": "# 项目待办清单 (Backlogs)\n\n## [TECH_DEBT] 技术债务\n\n## [ROADMAP] 路线图\n",
}


@dataclass
class _PathConfig:
    root_dir: str = ""
    asset_root: str = ""
    backlog_file: str = ""
    stages_index: str = ""
    adr_index: str = ""
    session_file: str = ""
    stages_exec_dir: str = ""
    archive_exec_dir: str = ""

    def configure(self, project_root: str):
        self.root_dir = os.path.abspath(project_root)
        self.asset_root = os.path.join(self.root_dir, ".stages")
        self.backlog_file = os.path.join(self.asset_root, "BACKLOGS.md")
        self.stages_index = os.path.join(self.asset_root, "STAGES.md")
        self.adr_index = os.path.join(self.asset_root, "ADRS.md")
        self.session_file = os.path.join(self.asset_root, "STAGE_SESSIONS.md")
        self.stages_exec_dir = os.path.join(self.asset_root, "stages")
        self.archive_exec_dir = os.path.join(self.asset_root, "archive", "stages")


cfg = _PathConfig()

# -------------------------------------------------------------------
# JSON 输出支持
# -------------------------------------------------------------------

@dataclass
class _OutputCtx:
    json_mode: bool = False
    data: Dict[str, Any] = field(default_factory=dict)

_out = _OutputCtx()


def emit(key: str, value: Any):
    """累积 JSON 输出字段，仅在 json_mode 下生效。"""
    if _out.json_mode:
        _out.data[key] = value


def info(msg: str):
    """标准信息输出。json_mode 下静默，累积到 messages。"""
    if _out.json_mode:
        _out.data.setdefault("messages", []).append(msg)
    else:
        print(msg)


def flush_json():
    """在 json_mode 下输出累积的 JSON 并退出。"""
    if _out.json_mode:
        print(json.dumps(_out.data, ensure_ascii=False, indent=2))


# -------------------------------------------------------------------
# 基础工具
# -------------------------------------------------------------------

def now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_datetime() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, content: str):
    """原子写入：写到临时文件再 rename，防止中断导致数据损坏。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


def discover_project_root(root_override: Optional[str] = None) -> str:
    if root_override:
        return os.path.abspath(root_override)
    env_root = os.environ.get("STAGE_MANAGER_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    probe = os.path.abspath(os.getcwd())
    while True:
        if os.path.isdir(os.path.join(probe, ".git")) or os.path.isdir(os.path.join(probe, ".stages")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return os.path.abspath(os.getcwd())
        probe = parent


def get_git_info() -> str:
    try:
        h = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        return f"git@{h}"
    except Exception:
        return "local-env"


def get_sys_user() -> str:
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def slugify_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9\-_.]+", "-", re.sub(r"\s+", "-", name.strip().lower()))
    return re.sub(r"-{2,}", "-", s).strip("-") or "unnamed-stage"


def ensure_structure():
    for d in [cfg.asset_root, cfg.stages_exec_dir, cfg.archive_exec_dir]:
        os.makedirs(d, exist_ok=True)

    defaults = [
        (cfg.stages_index, lambda: (
            STRINGS["stages_index_head"] + "\n---\n\n## 快速状态\n"
            f"- [HEARTBEAT] Init\n- [LAST_SESSION] 暂无记录\n"
            f"- 最近同步: {now_datetime()} | 用户: {get_sys_user()} | Version: {get_git_info()}\n"
        )),
        (cfg.adr_index, lambda: (
            STRINGS["adrs_head"] + f"\n---\n\n## 统计信息\n- 总计决策: 0\n- 最近更新: {now_datetime()}\n"
        )),
        (cfg.session_file, lambda: (
            STRINGS["sessions_head"] + "\n---\n\n## 最近记录\n- 暂无活动记录\n"
        )),
        (cfg.backlog_file, lambda: STRINGS["backlogs_head"]),
    ]
    for path, content_fn in defaults:
        if not os.path.exists(path):
            write_text(path, content_fn())


# -------------------------------------------------------------------
# frontmatter / markdown
# -------------------------------------------------------------------

_FM_KEY_ORDER = ["stage_id", "name", "status", "start_date", "end_date", "depends_on", "milestone"]


def parse_frontmatter(content: str) -> Tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.S)
    if not m:
        return {}, content
    data: Dict[str, object] = {}
    for line in m.group(1).splitlines():
        line = re.sub(r"\s+#.*$", "", line.strip())
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        val = v.strip()
        if val == "null":
            data[k.strip()] = None
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            data[k.strip()] = [x.strip().strip('"') for x in inner.split(",") if x.strip()] if inner else []
        elif val.startswith('"') and val.endswith('"'):
            data[k.strip()] = val[1:-1]
        else:
            data[k.strip()] = val
    return data, m.group(2)


def dump_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _FM_KEY_ORDER:
        v = data.get(key)
        if v is None:
            lines.append(f"{key}: null")
        elif isinstance(v, list):
            joined = ", ".join(f'"{x}"' if " " in str(x) else str(x) for x in v) if v else ""
            lines.append(f"{key}: [{joined}]")
        else:
            lines.append(f'{key}: "{v}"')
    lines.append("---")
    return "\n".join(lines)


def replace_frontmatter(content: str, updates: dict) -> str:
    cur, body = parse_frontmatter(content)
    cur.update(updates)
    return dump_frontmatter(cur) + "\n" + body.lstrip("\n")


def update_title(content: str, stage_id: str, name: str) -> str:
    new_title = f"# {stage_id}: {name}"
    return re.sub(r"^# .*?$", new_title, content, count=1, flags=re.M) if re.search(r"^# ", content, re.M) else new_title + "\n\n" + content


def find_section_block(content: str, section_no: int) -> Optional[Tuple[int, int, str, str]]:
    """优先通过 @section 锚点定位，回退到 ## N. 正则。"""
    anchor_name = _SECTION_ANCHORS.get(section_no)
    if anchor_name:
        anchor_pat = rf"<!--\s*@section:{re.escape(anchor_name)}\s*-->\s*\n"
        anchor_m = re.search(anchor_pat, content)
        if anchor_m:
            after = content[anchor_m.end():]
            header_m = re.match(r"(\s*^## \d+\..*?$)(.*?)(?=^## \d+\.|\Z)", after, re.M | re.S)
            if header_m:
                abs_start = anchor_m.start()
                abs_end = anchor_m.end() + header_m.end()
                return (abs_start, abs_end, header_m.group(1).strip(), header_m.group(2))

    # 回退：按章节编号匹配
    m = re.search(rf"(^## {section_no}\..*?$)(.*?)(?=^## \d+\.|\Z)", content, re.M | re.S)
    return (m.start(), m.end(), m.group(1), m.group(2)) if m else None


def _get_anchor_prefix(content_slice: str, section_no: int) -> str:
    """从内容片段中提取 @section 锚点注释，用于写回时保留。"""
    anchor_name = _SECTION_ANCHORS.get(section_no)
    if anchor_name:
        m = re.search(rf"(<!--\s*@section:{re.escape(anchor_name)}\s*-->\s*\n)", content_slice)
        if m:
            return m.group(1)
    return ""


def replace_section_body(content: str, section_no: int, new_body: str) -> str:
    block = find_section_block(content, section_no)
    if not block:
        return content
    start, end, header, _ = block
    prefix = _get_anchor_prefix(content[start:end], section_no)
    return content[:start] + prefix + header + "\n\n" + new_body.strip("\n") + "\n" + content[end:]


def prepend_to_section_body(content: str, section_no: int, block_text: str, remove_placeholder_tbd: bool = False) -> str:
    section = find_section_block(content, section_no)
    if not section:
        return content
    start, end, header, body = section
    body_text = body.strip("\n")
    if remove_placeholder_tbd:
        body_text = re.sub(r"^\s*-\s*暂无\s*$", "", body_text, flags=re.M).strip("\n")
    parts = [p for p in [block_text.strip("\n"), body_text.strip("\n")] if p.strip()]
    new_body = "\n\n".join(parts) if parts else "- 暂无"
    prefix = _get_anchor_prefix(content[start:end], section_no)
    return content[:start] + prefix + header + "\n\n" + new_body + "\n" + content[end:]


# -------------------------------------------------------------------
# 路径解析 / 索引
# -------------------------------------------------------------------

def _extract_stage_num(filename: str) -> int:
    m = re.search(r"stage-(\d+)-", filename)
    return int(m.group(1)) if m else 999999


def _list_md_files(directory: str) -> List[str]:
    if not os.path.exists(directory):
        return []
    return sorted([f for f in os.listdir(directory) if f.endswith(".md")], key=_extract_stage_num)


def get_latest_stage_info() -> Tuple[Optional[str], str]:
    ensure_structure()
    active_files = _list_md_files(cfg.stages_exec_dir)
    max_num = f"{max((_extract_stage_num(f) for f in active_files), default=0):03d}"
    content = read_text(cfg.stages_index)
    if not content:
        return None, max_num
    m = re.search(r"`\.stages/stages/(stage-\d+-.*?\.md)`（当前阶段）", content)
    return (m.group(1) if m else None), max_num


def resolve_stage_file(target: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    if not target:
        active_file, _ = get_latest_stage_info()
        if not active_file:
            return None, None
        return active_file, os.path.join(cfg.stages_exec_dir, active_file)
    if os.path.isabs(target) and os.path.exists(target):
        return os.path.basename(target), target
    if os.path.exists(target):
        return os.path.basename(target), os.path.abspath(target)
    for base in [cfg.stages_exec_dir, cfg.archive_exec_dir]:
        candidate = os.path.join(base, target)
        if os.path.exists(candidate):
            return os.path.basename(candidate), candidate
    return None, None


def rewrite_stages_index(current_stage: Optional[str] = None):
    ensure_structure()
    existing = read_text(cfg.stages_index)

    qs_match = re.search(r"(^---\n\n## 快速状态.*$)", existing, re.M | re.S)
    quick_status = qs_match.group(1) if qs_match else (
        f"---\n\n## 快速状态\n- [HEARTBEAT] Init\n- [LAST_SESSION] 暂无记录\n"
        f"- 最近同步: {now_datetime()} | 用户: {get_sys_user()} | Version: {get_git_info()}\n"
    )

    active_files = _list_md_files(cfg.stages_exec_dir)
    archived_files = _list_md_files(cfg.archive_exec_dir)

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
        for f in ordered:
            tag = "当前阶段" if f == current_stage else "活跃阶段"
            lines.append(f"{idx}. `.stages/stages/{f}`（{tag}）\n")
            idx += 1
    for f in archived_files:
        lines.append(f"{idx}. `.stages/archive/stages/{f}`（已归档）\n")
        idx += 1

    lines.append("\n" + quick_status.strip("\n") + "\n")
    write_text(cfg.stages_index, "".join(lines))


# -------------------------------------------------------------------
# 通用 ID / 解析 / 校验
# -------------------------------------------------------------------

def _next_id(filepath: str, prefix: str, *, max_below: Optional[int] = None) -> str:
    """统一的递增 ID 生成器。max_below 用于排除保留编号(如 TASK-900)。"""
    nums = []
    for m in re.finditer(rf"\[{prefix}(\d{{3}})\]", read_text(filepath)):
        n = int(m.group(1))
        if max_below is None or n < max_below:
            nums.append(n)
    return f"{prefix}{max(nums, default=0) + 1:03d}"


def count_adrs_from_index() -> int:
    return len(re.findall(r"\[ADRS-\d+\]", read_text(cfg.adr_index)))


def get_last_session_text() -> str:
    m = re.search(r"- \*\*会话快照\*\*: (.*?)\n", read_text(cfg.session_file))
    return m.group(1).strip() if m else "暂无记录"


def parse_bracket_list(text: str) -> List[str]:
    text = text.strip()
    if not text.startswith("[") or not text.endswith("]"):
        return []
    inner = text[1:-1].strip()
    return [x.strip().strip('"') for x in inner.split(",") if x.strip()] if inner else []


def _parse_kv_tail(tail: str) -> Tuple[str, Dict[str, str]]:
    """解析 'name | k1=v1 | k2=v2' 格式的尾部。"""
    parts = [p.strip() for p in tail.split("|")]
    name = parts[0].strip().replace("**", "") if parts else ""
    fields: Dict[str, str] = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            fields[k.strip()] = v.strip()
    return name, fields


def parse_task_line(task_line: str) -> Optional[Dict[str, object]]:
    m = re.match(r"^\-\s*\[([ xX])\]\s+\[(P\d+)\]\s+\[(TASK-\d{3}|TASK-TBD)\]\s+(.*)$", task_line.strip())
    if not m:
        return None
    name, fields = _parse_kv_tail(m.group(4))
    return {
        "checked": m.group(1).lower() == "x",
        "priority": m.group(2),
        "task_id": m.group(3),
        "name": name,
        "owner": fields.get("owner", ""),
        "executor": fields.get("executor", ""),
        "skills": parse_bracket_list(fields.get("skills", "[]")),
        "task_depends_on": parse_bracket_list(fields.get("task_depends_on", "[]")),
        "acceptance": parse_bracket_list(fields.get("acceptance", "[]")),
        "deliverables": parse_bracket_list(fields.get("deliverables", "[]")),
        "evidence": parse_bracket_list(fields.get("evidence", "[]")),
        "due": fields.get("due", ""),
    }


def parse_ac_line(ac_line: str) -> Optional[Dict[str, object]]:
    m = re.match(r"^\-\s*\[([ xX])\]\s+\[(AC-\d{3})\]\s+(.*)$", ac_line.strip())
    if not m:
        return None
    name, fields = _parse_kv_tail(m.group(3))
    return {
        "checked": m.group(1).lower() == "x",
        "ac_id": m.group(2),
        "name": name,
        "verify_by": fields.get("verify_by", ""),
        "required_tasks": parse_bracket_list(fields.get("required_tasks", "[]")),
        "required_checks": parse_bracket_list(fields.get("required_checks", "[]")),
        "evidence": parse_bracket_list(fields.get("evidence", "[]")),
    }


def _validate_id_list(items: List[str], pattern: str, label: str, owner_id: str) -> List[str]:
    return [f"{owner_id} {label} 非法: {x}" for x in items if not re.fullmatch(pattern, x)]


def validate_task_line(task_line: str) -> List[str]:
    parsed = parse_task_line(task_line)
    if not parsed:
        return [f"任务格式非法: {task_line}"]
    errs: List[str] = []
    tid = str(parsed["task_id"])
    if parsed["executor"] not in ALLOWED_EXECUTOR:
        errs.append(f"{tid} executor 非法: {parsed['executor']}")
    due = str(parsed.get("due", "")).strip()
    if due and due not in {"YYYY-MM-DD", "null"} and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
        errs.append(f"{tid} due 日期格式非法: {due}")
    errs.extend(_validate_id_list(parsed["task_depends_on"], r"TASK-\d{3}|TASK-TBD", "task_depends_on", tid))
    errs.extend(_validate_id_list(parsed["acceptance"], r"AC-\d{3}", "acceptance", tid))
    return errs


def validate_ac_line(ac_line: str) -> List[str]:
    parsed = parse_ac_line(ac_line)
    if not parsed:
        return [f"验收项格式非法: {ac_line}"]
    errs: List[str] = []
    aid = str(parsed["ac_id"])
    if str(parsed["verify_by"]) not in ALLOWED_VERIFY_BY:
        errs.append(f"{aid} verify_by 非法: {parsed['verify_by']}")
    errs.extend(_validate_id_list(parsed["required_tasks"], r"TASK-\d{3}|TASK-TBD", "required_tasks", aid))
    return errs


def normalize_backlog_task_line(task_line: str, new_task_id: str) -> str:
    raw = task_line.strip()
    if parse_task_line(raw):
        return raw if raw.startswith("- [ ]") else f"- [ ] {raw}"
    raw = re.sub(r"^\-\s*\[[ xX]\]\s*", "", raw).strip()
    # 优先从 [PX] 括号前缀取优先级
    m = re.match(r"^\[(P\d+)\]\s+(.*)$", raw)
    if m:
        prio, rest = m.group(1), m.group(2).strip()
    else:
        # 回退：从管道字段 priority=PX 取优先级
        prio_m = re.search(r"\bpriority=(P\d+)\b", raw)
        prio = prio_m.group(1) if prio_m else "P1"
        rest = raw
    # 提取名称部分（管道分隔前的第一段）
    name = rest.split("|")[0].strip()
    return (
        f"- [ ] [{prio}] [{new_task_id}] {name} | owner=unassigned | executor=agent | "
        f"skills=[] | task_depends_on=[] | acceptance=[] | deliverables=[] | evidence=[] | due=YYYY-MM-DD"
    )


# -------------------------------------------------------------------
# 统计 / 推断
# -------------------------------------------------------------------

def calculate_progress(filepath: str) -> int:
    content = read_text(filepath)
    if not content:
        return 0
    marks = []
    for sec_no in (4, 5):
        sec = find_section_block(content, sec_no)
        if sec:
            marks.extend(re.findall(r"^\s*(?:-\s*|\d+\.\s*)\[( |x|X)\]", sec[3], re.M))
    return int((sum(1 for t in marks if t.lower() == "x") / len(marks)) * 100) if marks else 0


def get_project_stats_dict() -> Dict[str, Any]:
    ensure_structure()
    done = len(_list_md_files(cfg.archive_exec_dir))
    active = len(_list_md_files(cfg.stages_exec_dir))
    total_done, total_pending = 0, 0
    total_pending += len(re.findall(r"^\s*-\s*\[ \]", read_text(cfg.backlog_file), re.M))
    _, active_path = resolve_stage_file(None)
    if active_path:
        content = read_text(active_path)
        for sec_no in (4, 5):
            sec = find_section_block(content, sec_no)
            if not sec:
                continue
            body = sec[3]
            total_done += len(re.findall(r"^\s*(?:-\s*|\d+\.\s*)\[(x|X)\]", body, re.M))
            total_pending += len(re.findall(r"^\s*(?:-\s*|\d+\.\s*)\[ \]", body, re.M))
    return {
        "archived_stages": done, "active_stages": active,
        "tasks_done": total_done, "tasks_pending": total_pending,
        "adrs": count_adrs_from_index(),
    }


def get_project_stats() -> str:
    d = get_project_stats_dict()
    return (f"阶段(归档/活跃): {d['archived_stages']}/{d['active_stages']} | "
            f"任务(完成/待办): {d['tasks_done']}/{d['tasks_pending']} | 决策: {d['adrs']}")


def update_heartbeat():
    ensure_structure()
    stats, session, now, user, ver = get_project_stats(), get_last_session_text(), now_datetime(), get_sys_user(), get_git_info()
    lines = read_text(cfg.stages_index).splitlines(True)
    found_sync = False
    for i, line in enumerate(lines):
        if "[HEARTBEAT]" in line:
            lines[i] = f"- [HEARTBEAT] {stats}\n"
        elif "[LAST_SESSION]" in line:
            lines[i] = f"- [LAST_SESSION] {session}\n"
        elif "最近同步" in line:
            lines[i] = f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n"
            found_sync = True
    if not found_sync:
        lines.append(f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n")
    write_text(cfg.stages_index, "".join(lines))


def infer_stage_type(content: str) -> str:
    text = content.lower()
    impl = ["implement", "refactor", "fix", "integrate", "migrate", "replace", "实现", "改造", "重构", "修复", "接入", "替换", "迁移"]
    return "implementation" if any(k in text for k in impl) else "planning"


def _check_section_items(
    filepath: str, section_no: int, filter_fn: Callable[[str], bool]
) -> Tuple[bool, List[str]]:
    if not os.path.exists(filepath):
        return True, []
    sec = find_section_block(read_text(filepath), section_no)
    if not sec:
        return True, []
    pending = [line.strip() for line in re.findall(r"^\s*-\s*\[[ xX]\].*$", sec[3], re.M) if filter_fn(line)]
    return len(pending) == 0, pending


def check_p0_completed(filepath: str) -> Tuple[bool, List[str]]:
    def _is_unchecked_p0(line: str) -> bool:
        p = parse_task_line(line)
        return p is not None and p["priority"] == "P0" and not p["checked"]
    return _check_section_items(filepath, 4, _is_unchecked_p0)


def check_dod_completed(filepath: str) -> Tuple[bool, List[str]]:
    return _check_section_items(filepath, 5, lambda line: re.match(r"^\s*-\s*\[ \]", line) is not None)


def has_summary_content(filepath: str) -> bool:
    if not os.path.exists(filepath):
        return False
    sec = find_section_block(read_text(filepath), 9)
    return sec is not None and not re.fullmatch(r"\s*-\s*暂无\s*", sec[3].strip())


def check_implementation_evidence(filepath: str) -> Tuple[bool, List[str]]:
    if not os.path.exists(filepath):
        return False, []
    content = read_text(filepath)
    if infer_stage_type(content) != "implementation":
        return True, []

    evidence_paths: List[str] = []
    for sec_no, parser in [(4, parse_task_line), (5, parse_ac_line)]:
        sec = find_section_block(content, sec_no)
        if not sec:
            continue
        for line in re.findall(r"^\s*-\s*\[[ xX]\].*$", sec[3], re.M):
            parsed = parser(line)
            if parsed:
                evidence_paths.extend(parsed["evidence"])

    real = [p for p in dict.fromkeys(evidence_paths) if p and not p.startswith(".stage/")]
    return len(real) > 0, real


def get_pending_tasks(filepath: str) -> List[str]:
    if not os.path.exists(filepath):
        return []
    sec = find_section_block(read_text(filepath), 4)
    if not sec:
        return []
    tasks = re.findall(r"^\s*-\s*\[ \]\s+(.*)$", sec[3], re.M)
    return sorted(tasks, key=lambda t: int(m.group(1)) if (m := re.search(r"\[P(\d+)\]", t)) else 999)


def clean_summary_text(text: str) -> str:
    if not text:
        return "N/A"
    c = re.sub(r"\s+", " ", re.sub(r"^\s*-\s*(?:###\s*|\[x\]\s*|\[ \]\s*)?", "", text.replace("**", ""), flags=re.M | re.I))
    return c.strip() or "N/A"


def extract_summary_brief(content: str) -> str:
    sec = find_section_block(content, 9)
    if not sec:
        return "N/A"
    block = sec[2] + sec[3]  # header + body
    title = re.search(r"^- ### \[SUMMARY-\d+\] \| \[\d{4}-\d{2}-\d{2}\] \| \[(.*?)\]", block, re.M)
    goal = re.search(r"^\s*- \*\*里程碑目标\*\*: (.*)$", block, re.M)
    results = re.findall(r"^\s*-\s*\[x\]\s+(.*)$", block, re.M)
    audit = re.search(r"^\s*- \*\*变更审计\*\*: (.*)$", block, re.M)

    parts = []
    if title: parts.append(title.group(1).strip())
    if goal: parts.append(f"目标：{goal.group(1).strip()}")
    if results: parts.append("成果：" + "；".join(r.strip() for r in results[:2]))
    if audit: parts.append(f"变更：{audit.group(1).strip()}")
    if parts:
        return " | ".join(parts)[:240]

    raw = " ".join(l.strip() for l in block.splitlines() if l.strip() and not l.strip().startswith(("## ", ">")))
    return clean_summary_text(raw)[:240] or "N/A"


# -------------------------------------------------------------------
# 校验
# -------------------------------------------------------------------

def validate_stage_document(filepath: str) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warns: List[str] = []

    if not os.path.exists(filepath):
        return [f"文件不存在: {filepath}"], []

    content = read_text(filepath)
    fm, _ = parse_frontmatter(content)

    for key in _FM_KEY_ORDER:
        if key not in fm:
            errors.append(f"frontmatter 缺少字段: {key}")
    if "status" in fm and fm["status"] not in ALLOWED_STAGE_STATUS:
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
        if not find_section_block(content, sec):
            errors.append(f"缺少 section: ## {sec}.")

    task_ids, ac_ids = [], []
    task_to_ac: Dict[str, List[str]] = {}
    ac_to_task: Dict[str, List[str]] = {}

    for sec_no, parser, validator, id_key, ref_key in [
        (4, parse_task_line, validate_task_line, "task_id", "acceptance"),
        (5, parse_ac_line, validate_ac_line, "ac_id", "required_tasks"),
    ]:
        sec = find_section_block(content, sec_no)
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
    for tid, refs in task_to_ac.items():
        for ac in refs:
            if ac not in ac_set:
                errors.append(f"{tid} 引用了不存在的验收项: {ac}")
    for aid, refs in ac_to_task.items():
        for tid in refs:
            if tid not in task_set:
                errors.append(f"{aid} 引用了不存在的任务: {tid}")

    if "TASK-900" not in task_set:
        warns.append("建议增加 TASK-900 阶段验收任务")

    for sec_no, label in [(7, "进度日志"), (9, "阶段总结")]:
        sec = find_section_block(content, sec_no)
        if sec and re.fullmatch(r"\s*-\s*暂无\s*", sec[3].strip()):
            warns.append(f"{label}为空")

    if infer_stage_type(content) == "implementation":
        ok, _ = check_implementation_evidence(filepath)
        if not ok:
            warns.append("实施型阶段尚未发现实际代码/测试/配置 evidence")

    return errors, warns


# -------------------------------------------------------------------
# ADR / session
# -------------------------------------------------------------------

def update_adr_index(clean_msg: str, stage_file: str, is_archive: bool = False) -> str:
    ensure_structure()
    lines = read_text(cfg.adr_index).splitlines(True)
    count = count_adrs_from_index()
    adr_id = f"ADRS-{count + 1:03d}"
    prefix = ".stages/archive/stages/" if is_archive else ".stages/stages/"
    entry = f"{count + 1}. [{adr_id}] {clean_msg} ({prefix}{stage_file})\n"

    insert_idx = next((i + 1 for i, l in enumerate(lines) if "决策目录" in l), -1)
    if insert_idx != -1:
        lines.insert(insert_idx + count, entry)
    else:
        lines.append("\n" + entry)

    for i, line in enumerate(lines):
        if "总计决策" in line:
            lines[i] = f"- 总计决策: {count + 1}\n"
        elif "最近更新" in line:
            lines[i] = f"- 最近更新: {now_datetime()}\n"

    write_text(cfg.adr_index, "".join(lines))
    return adr_id


def update_session_summary(text: str):
    ensure_structure()
    clean = clean_summary_text(text)
    active_file, _ = get_latest_stage_info()
    now = now_datetime()

    lines = read_text(cfg.session_file).splitlines(True)
    entry = f"### [{now}] Stage: {active_file or 'Global'}\n- **会话快照**: {clean}\n\n"

    insert_idx = next((i + 1 for i, l in enumerate(lines) if "会话摘要" in l), -1)
    if insert_idx != -1:
        lines.insert(insert_idx + 1, entry)
    else:
        lines.append(entry)

    for i, line in enumerate(lines):
        if line.startswith("- 最近记录") or line.startswith("- 暂无活动记录"):
            lines[i] = f"- 最近记录: [{now}] {clean[:60]}...\n"
            break

    indices = [i for i, l in enumerate(lines) if l.startswith("### [")]
    if len(indices) > SESSION_MAX_ENTRIES:
        lines = lines[:indices[SESSION_MAX_ENTRIES]]

    write_text(cfg.session_file, "".join(lines))
    update_heartbeat()


# -------------------------------------------------------------------
# 渲染器
# -------------------------------------------------------------------

def render_log_entry(filepath: str, message: str, task_name: Optional[str] = None,
                     status: str = "进行中", next_action: Optional[str] = None,
                     blocked_by: Optional[str] = None) -> str:
    log_id = _next_id(filepath, "LOG-")
    status_text = f"阻塞 (Blocked by: {blocked_by})" if status == "阻塞" and blocked_by else status
    return (
        f"- ### [{log_id}] | [{now_date()}] | [{task_name or 'SYNC'}] | [{get_sys_user()}] | [Ver:{get_git_info()}]\n"
        f"  - **状态**: {status_text}\n"
        f"  - **关键进展**: {message}\n"
        f"  - **后续行动**: {next_action or 'TBD'}\n"
    )


def render_adr_entry(adr_id: str, title: str) -> str:
    return (
        f"- ### [{adr_id}] | [{now_date()}] | [{title}]\n"
        f"  - **背景/动机**: TBD\n  - **可选方案**: TBD\n  - **结论**: TBD\n  - **影响/后果**: TBD\n"
    )


def render_summary_entry(filepath: str, name: str, milestone_goal: str,
                         core_results: List[str], change_audit: str, tech_debt: str) -> str:
    sid = _next_id(filepath, "SUMMARY-")
    result_lines = "\n".join(f"    - [x] {item}" for item in core_results) if core_results else "    - [x] TBD"
    return (
        f"- ### [{sid}] | [{now_date()}] | [{name}] | [Ver:{get_git_info()}]\n"
        f"  - **里程碑目标**: {milestone_goal}\n"
        f"  - **核心成果**:\n{result_lines}\n"
        f"  - **变更审计**: {change_audit}\n"
        f"  - **遗留风险/技术债**: {tech_debt}\n"
    )


# -------------------------------------------------------------------
# 展示（统一 dashboard）
# -------------------------------------------------------------------

def _dashboard_data(mode: str, file_target: Optional[str] = None) -> Dict[str, Any]:
    """收集 dashboard 所需的全部数据，不做任何输出。"""
    filename, filepath = resolve_stage_file(file_target)
    data: Dict[str, Any] = {
        "stats": get_project_stats_dict(),
        "stats_str": get_project_stats(),
        "mode": mode,
    }
    if filename and filepath:
        data["current_stage"] = filename
        data["progress"] = calculate_progress(filepath)
        data["pending_tasks"] = get_pending_tasks(filepath)
    data["recent_sessions"] = re.findall(r"- \*\*会话快照\*\*: (.*?)\n", read_text(cfg.session_file))[:3]
    data["recent_adrs"] = re.findall(r"^\d+\. (\[ADRS-\d+\].*?)$", read_text(cfg.adr_index), re.M)[-3:]
    if mode == "full":
        data["backlog_count"] = len(re.findall(r"^\s*-\s*\[ \]", read_text(cfg.backlog_file), re.M))
        data["skill_path"] = SKILL_DIR
        data["asset_root"] = cfg.asset_root
    return data


def _render_dashboard_json(data: Dict[str, Any]):
    """JSON 模式渲染。"""
    out = {"stats": data["stats"]}
    for key in ("current_stage", "progress", "recent_sessions", "recent_adrs",
                "backlog_count", "skill_path", "asset_root"):
        if key in data:
            out[key] = data[key]
    if "pending_tasks" in data:
        out["pending_tasks"] = data["pending_tasks"][:5]
    emit("dashboard", out)


def _render_dashboard_text(data: Dict[str, Any]):
    """文本模式渲染。"""
    mode = data["mode"]
    stats_str = data["stats_str"]

    info("\n" + "=" * 50)
    info(" [BOOTSTRAP] 会话上下文恢复中..." if mode == "full" else f" [项目健康度] {stats_str}")
    info("=" * 50)

    if mode == "full":
        info(f"\n [项目概览] {stats_str}")

    if "current_stage" in data:
        p = data["progress"]
        bar = "#" * int(p / 5) + "-" * (20 - int(p / 5))
        info(f" [{'活跃阶段' if mode == 'full' else '阶段文件'}] {data['current_stage']}")
        info(f" [完成进度] [{bar}] {p}%")
        pending = data.get("pending_tasks", [])
        if pending:
            limit = 3 if mode == "full" else 5
            plabel = "下一步待办" if mode == "full" else "未完成任务"
            info(f"\n [{plabel}] (前{limit}条):")
            for t in pending[:limit]:
                info(f"  [ ] {t.strip()}")
    elif mode == "full":
        info(" [活跃阶段] 无活跃阶段")

    sessions = data.get("recent_sessions", [])
    if sessions:
        info(f"\n [{'记忆锚点' if mode == 'full' else '最近会话'}] {'最近会话快照' if mode == 'full' else '(最近3条)'}:")
        trunc = 100 if mode == "full" else 80
        for s in sessions[:3]:
            info(f"  > {s[:trunc]}{'...' if len(s) > trunc else ''}")
    elif mode == "full":
        info("\n [记忆锚点] 暂无历史快照。")

    adrs = data.get("recent_adrs", [])
    if adrs:
        info("\n [最近决策] (最近3条):" if mode == "brief" else "\n [最近决策]:")
        for a in adrs[-3:]:
            info(f"  * {a.strip()}")

    if mode == "full":
        bc = data.get("backlog_count", 0)
        if bc > 0:
            info(f"\n [Backlog] {bc} 个待认领任务")
        info(f"\n [Skill 路径] {SKILL_DIR}")
        info(f" [资产目录] {cfg.asset_root}")

    info("\n" + "=" * 50)
    if mode == "full":
        info(" [OK] Bootstrap 完成。")
    info("=" * 50 + "\n")


def _render_dashboard(mode: str = "full", file_target: Optional[str] = None) -> bool:
    data = _dashboard_data(mode, file_target)
    if _out.json_mode:
        _render_dashboard_json(data)
    else:
        _render_dashboard_text(data)
    update_heartbeat()
    return True


# -------------------------------------------------------------------
# check 命令
# -------------------------------------------------------------------

def check_item(item_id: str, uncheck: bool = False, file_target: Optional[str] = None) -> bool:
    """切换 TASK-XXX 或 AC-XXX 的勾选状态。"""
    filename, filepath = resolve_stage_file(file_target)
    if not filename or not filepath:
        info("[!] 当前没有可操作的阶段文件。")
        return False

    content = read_text(filepath)

    # 确定目标 section
    if item_id.startswith("TASK-"):
        sec_no = 4
    elif item_id.startswith("AC-"):
        sec_no = 5
    else:
        info(f"[!] 无法识别 ID 类型: {item_id}（支持 TASK-XXX 或 AC-XXX）")
        return False

    old_mark = "[x]" if uncheck else "[ ]"
    new_mark = "[ ]" if uncheck else "[x]"
    pattern = re.compile(rf"^(\s*-\s*)\[{'[xX]' if uncheck else ' '}\](\s+.*\[{re.escape(item_id)}\].*)$", re.M)

    sec = find_section_block(content, sec_no)
    if not sec:
        info(f"[!] 未找到 section {sec_no}。")
        return False

    match = pattern.search(content)
    if not match:
        info(f"[!] 未找到匹配的条目 {item_id}（当前状态可能已是目标状态）。")
        return False

    new_line = f"{match.group(1)}{new_mark}{match.group(2)}"
    content = content[:match.start()] + new_line + content[match.end():]
    write_text(filepath, content)
    update_heartbeat()

    action = "取消勾选" if uncheck else "勾选"
    info(f"[OK] 已{action}: {item_id}")
    emit("checked", {"id": item_id, "new_state": "unchecked" if uncheck else "checked"})
    return True


# -------------------------------------------------------------------
# switch 命令
# -------------------------------------------------------------------

def switch_stage(target: str) -> bool:
    """切换当前活跃阶段。"""
    filename, filepath = resolve_stage_file(target)
    if not filename or not filepath:
        info(f"[!] 未找到阶段文件: {target}")
        return False
    if not filepath.startswith(os.path.abspath(cfg.stages_exec_dir)):
        info(f"[!] 只能切换到活跃阶段（非归档）: {filename}")
        return False
    rewrite_stages_index(current_stage=filename)
    update_heartbeat()
    info(f"[OK] 当前阶段已切换为: {filename}")
    emit("switched", {"current_stage": filename})
    return True


# -------------------------------------------------------------------
# backlog
# -------------------------------------------------------------------

def intake_backlog(keyword: str, dry_run: bool = False, file_target: Optional[str] = None) -> bool:
    filename, filepath = resolve_stage_file(file_target)
    if not filename or not filepath:
        info("[!] 错误：当前没有可操作的阶段文件。")
        return False

    lines = read_text(cfg.backlog_file).splitlines(True)
    extracted, remaining = [], []
    for line in lines:
        if line.strip().startswith("- [ ]") and keyword.lower() in line.lower():
            extracted.append(line.strip())
        else:
            remaining.append(line)

    if not extracted:
        info(f"[!] 未在 BACKLOGS.md 中找到匹配 '{keyword}' 的任务。")
        return False

    content = read_text(filepath)
    existing_nums = [int(m.group(1)) for m in re.finditer(r"\[TASK-(\d{3})\]", content) if int(m.group(1)) < 900]
    next_num = max(existing_nums, default=0) + 1

    normalized = []
    for raw in extracted:
        new_id = f"TASK-{next_num:03d}"
        normalized.append(normalize_backlog_task_line(raw, new_id))
        next_num += 1

    if dry_run:
        info(f"[DRY-RUN] 将从 Backlog 认领 {len(normalized)} 个任务至 {filename}:")
        for t in normalized:
            info(f"  {t}")
        return True

    full = "".join(remaining)
    full = re.sub(r"### 来自 .*? \(\d{4}-\d{2}-\d{2}\)\n\s*(?=###|##|$)", "", full, flags=re.S)
    write_text(cfg.backlog_file, full)

    content = prepend_to_section_body(content, 4, "\n".join(normalized), remove_placeholder_tbd=True)
    write_text(filepath, content)

    update_heartbeat()
    info(f"[OK] 已从 Backlog 认领 {len(normalized)} 个任务并载入 {filename}。")
    return True


def route_backlog(tasks: List[str], stage_file: str, category_marker: str):
    if not tasks:
        return
    lines = read_text(cfg.backlog_file).splitlines(True)
    source_label = "非范围条目" if category_marker == "[ROADMAP]" else "溢出与未完成任务"
    header = f"### 来自 {stage_file} 的{source_label} ({now_date()})\n"

    insert_idx = next((i + 1 for i, l in enumerate(lines) if category_marker in l), -1)
    if insert_idx == -1:
        info(f"[!] 警告: BACKLOGS.md 中未找到 '{category_marker}' 标记，任务分流跳过。")
        return

    new_content = [header] + [f"{t}\n" if not t.endswith("\n") else t for t in tasks] + ["\n"]
    for item in reversed(new_content):
        lines.insert(insert_idx, item)
    write_text(cfg.backlog_file, "".join(lines))


# -------------------------------------------------------------------
# 初始化 / 日志 / 总结 / 归档
# -------------------------------------------------------------------

def check_stage_name_exists(slug: str) -> Optional[str]:
    pattern = re.compile(rf"^stage-\d+-{re.escape(slug)}\.md$")
    for d in [cfg.stages_exec_dir, cfg.archive_exec_dir]:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            if pattern.match(f):
                return f
    return None


def sync_log(message: str, task_name: Optional[str] = None, status: str = "进行中",
             next_action: Optional[str] = None, blocked_by: Optional[str] = None,
             file_target: Optional[str] = None) -> bool:
    filename, filepath = resolve_stage_file(file_target)
    if not filename or not filepath:
        info("[!] 当前没有可操作的阶段文件。")
        return False
    if status not in ALLOWED_LOG_STATUS:
        info(f"[!] 非法日志状态: {status}，允许值: {', '.join(sorted(ALLOWED_LOG_STATUS))}")
        return False

    content = read_text(filepath)

    if message.startswith("[ADR]"):
        clean_msg = message[5:].strip() or "TBD"
        adr_id = update_adr_index(clean_msg, filename, is_archive=("archive" in filepath))
        content = prepend_to_section_body(content, 8, render_adr_entry(adr_id, clean_msg), remove_placeholder_tbd=True)
        info(f"[OK] 已创建 ADR 存根: {adr_id}")

    content = prepend_to_section_body(
        content, 7,
        render_log_entry(filepath, message, task_name, status, next_action, blocked_by),
        remove_placeholder_tbd=True,
    )

    fm, _ = parse_frontmatter(content)
    cur_status = str(fm.get("status"))
    new_status = "IN_PROGRESS" if cur_status == "PLANNING" else cur_status
    if new_status != fm.get("status"):
        content = replace_frontmatter(content, {"status": new_status})

    write_text(filepath, content)
    update_heartbeat()
    info(f"[OK] 已同步到 {filename}")
    return True


def append_stage_summary(name: str, milestone_goal: str, core_results: List[str],
                         change_audit: str, tech_debt: str, file_target: Optional[str] = None) -> bool:
    filename, filepath = resolve_stage_file(file_target)
    if not filename or not filepath:
        info("[!] 当前没有可操作的阶段文件。")
        return False
    content = read_text(filepath)
    entry = render_summary_entry(filepath, name, milestone_goal, core_results, change_audit, tech_debt)
    content = prepend_to_section_body(content, 9, entry, remove_placeholder_tbd=True)
    write_text(filepath, content)
    update_heartbeat()
    info(f"[OK] 已写入阶段总结: {filename}")
    return True


def archive_stage(force: bool = False, dry_run: bool = False, file_target: Optional[str] = None) -> bool:
    filename, src = resolve_stage_file(file_target)
    if not filename or not src:
        info("[!] 当前没有可操作的阶段文件。")
        return False
    if src.startswith(os.path.abspath(cfg.archive_exec_dir)):
        info("[!] 该阶段已经位于 archive 目录。")
        return False

    errors, warns = validate_stage_document(src)
    if errors and not force:
        info("[!] 归档前校验失败：")
        for e in errors: info(f"  [ERROR] {e}")
        for w in warns: info(f"  [WARN]  {w}")
        info("[?] 请先修复上述 ERROR。需要强制继续时使用: done --force")
        return False

    gates = [
        (check_p0_completed, "仍存在未完成的 [P0] 任务", "请先完成上述 P0 任务"),
        (check_dod_completed, "## 5. 验收标准 (DoD) 未能全量通过", "请先完成上述验收项"),
    ]
    for checker, fail_msg, fix_msg in gates:
        ok, pending = checker(src)
        if not ok and not force:
            info(f"\n[!] 归档拒绝：{fail_msg}。")
            for item in pending: info(f"  {item}")
            info(f"\n[?] {fix_msg}。需要强制继续时使用: done --force")
            return False

    if not has_summary_content(src) and not force:
        info("\n[!] 归档拒绝：## 9. 阶段总结 仍为空。")
        info("[?] 请先补充阶段总结。需要强制继续时使用: done --force")
        return False

    impl_ok, _ = check_implementation_evidence(src)
    if not impl_ok and not force:
        info("\n[!] 归档拒绝：实施型阶段尚未发现实际代码/测试/配置 evidence。")
        info("[?] 请先补充可验证 evidence。需要强制继续时使用: done --force")
        return False

    if dry_run:
        info(f"[DRY-RUN] 将归档阶段: {filename}")
        for w in warns: info(f"[DRY-RUN][WARN] {w}")
        return True

    content = read_text(src)

    oos = find_section_block(content, 3)
    if oos:
        items = re.findall(r"^\s*-\s+\[OUT-SCOPE-\d+\].*$", oos[3], re.M)
        if items: route_backlog(items, filename, "[ROADMAP]")

    tasks = find_section_block(content, 4)
    if tasks:
        unfinished = re.findall(r"^\s*-\s*\[ \].*$", tasks[3], re.M)
        if unfinished: route_backlog(unfinished, filename, "[TECH_DEBT]")

    summary = extract_summary_brief(content)
    content = replace_frontmatter(content, {"status": "COMPLETED", "end_date": now_date()})

    if not has_summary_content(src):
        content = replace_section_body(content, 9, render_summary_entry(
            src, "Archive Summary", "阶段归档。",
            ["阶段已完成归档流程。"], "归档时自动补写状态与结束日期。", "已按规则分流至 Backlog。",
        ))

    write_text(src, content)

    # 安全归档：copy → 验证 → 删除
    dst = os.path.join(cfg.archive_exec_dir, filename)
    shutil.copy2(src, dst)
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
        info("[!] 归档复制验证失败，保留源文件。")
        return False
    os.remove(src)

    remaining = _list_md_files(cfg.stages_exec_dir)
    rewrite_stages_index(current_stage=remaining[0] if remaining else None)
    update_session_summary(f"[归档自动化] 阶段 {filename} 已结项: {summary}")
    info("[OK] 归档完成。")
    return True


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def main():
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--root", help="指定项目根目录")
    base_parser.add_argument("--json", action="store_true", help="输出 JSON 格式（适用于 bootstrap/status/validate/check）")
    temp_args, _ = base_parser.parse_known_args()
    cfg.configure(discover_project_root(temp_args.root))
    _out.json_mode = temp_args.json

    parser = argparse.ArgumentParser(
        description="Stage-Manager: 项目生命周期自动化管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  stage_manager.py init \"feature-auth\"\n"
            "  stage_manager.py sync \"实现登录逻辑\" --task-name \"登录接口\"\n"
            "  stage_manager.py sync \"[ADR] 使用 JWT\"\n"
            "  stage_manager.py check TASK-001\n"
            "  stage_manager.py switch stage-002-api.md\n"
            "  stage_manager.py summary \"会话快照\"\n"
            "  stage_manager.py status --json\n"
            "  stage_manager.py done\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--root", help="指定项目根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    sub = parser.add_subparsers(dest="cmd", title="子命令", required=True)

    p = sub.add_parser("init", help="初始化新阶段")
    p.add_argument("name", help="阶段名称")

    p = sub.add_parser("sync", help="同步进展")
    p.add_argument("message", help="进展描述；[ADR] 前缀触发决策同步")
    p.add_argument("--task-name", help="关联任务名")
    p.add_argument("--status", default="进行中", choices=sorted(ALLOWED_LOG_STATUS))
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

    args = parser.parse_args()
    if args.json:
        _out.json_mode = True
    ensure_structure()

    ok = True

    if args.cmd == "init":
        _, max_num = get_latest_stage_info()
        next_num = f"{int(max_num) + 1:03d}"
        slug = slugify_name(args.name)
        existing = check_stage_name_exists(slug)
        if existing:
            info(f"[!] 已存在同名阶段: {existing}")
            flush_json()
            sys.exit(1)

        filename = f"stage-{next_num}-{slug}.md"
        filepath = os.path.join(cfg.stages_exec_dir, filename)
        if not os.path.exists(TEMPLATE_PATH):
            info(f"[!] 模板不存在: {TEMPLATE_PATH}")
            flush_json()
            sys.exit(1)

        template = read_text(TEMPLATE_PATH)
        stage_id = f"STAGE-{next_num}"
        display = args.name.strip() or "TBD"
        content = replace_frontmatter(template, {
            "stage_id": stage_id, "name": display, "status": "PLANNING",
            "start_date": now_date(), "end_date": None, "depends_on": [], "milestone": None,
        })
        content = update_title(content, stage_id, display)
        write_text(filepath, content)
        rewrite_stages_index(current_stage=filename)
        update_heartbeat()
        info(f"[*] 初始化阶段: {filename}")

    elif args.cmd == "sync":
        ok = sync_log(args.message, args.task_name, args.status, args.next_action, args.blocked_by, args.file)

    elif args.cmd == "summary":
        if args.stage:
            if not all([args.name, args.goal, args.audit, args.debt]):
                info("[!] --stage 模式下必须提供 --name --goal --audit --debt")
                flush_json()
                sys.exit(1)
            ok = append_stage_summary(args.name, args.goal, args.result or [], args.audit, args.debt, args.file)
        else:
            if not args.text:
                info("[!] 非 --stage 模式下必须提供 text")
                flush_json()
                sys.exit(1)
            update_session_summary(args.text)

    elif args.cmd == "intake":
        ok = intake_backlog(args.keyword, dry_run=args.dry_run, file_target=args.file)

    elif args.cmd == "bootstrap":
        _render_dashboard("full")

    elif args.cmd == "status":
        _render_dashboard("brief", file_target=getattr(args, "file", None))

    elif args.cmd == "validate":
        filename, filepath = resolve_stage_file(getattr(args, "file", None))
        if not filename or not filepath:
            info("[!] 当前没有可操作的阶段文件。")
            flush_json()
            sys.exit(1)
        errors, warns = validate_stage_document(filepath)
        emit("validate", {"file": filename, "errors": errors, "warnings": warns})
        if not errors and not warns:
            info(f"[OK] 校验通过: {filename}")
        else:
            info(f"[CHECK] {filename}")
            for e in errors: info(f"  [ERROR] {e}")
            for w in warns: info(f"  [WARN]  {w}")
            if errors:
                ok = False

    elif args.cmd == "done":
        ok = archive_stage(force=args.force, dry_run=args.dry_run, file_target=getattr(args, "file", None))

    elif args.cmd == "check":
        ok = check_item(args.item_id, uncheck=args.uncheck, file_target=getattr(args, "file", None))

    elif args.cmd == "switch":
        ok = switch_stage(args.target)

    flush_json()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
