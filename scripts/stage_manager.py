#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stage-Manager: 项目生命周期管理脚本

功能：
- 阶段初始化
- 进度同步（支持结构化日志）
- ADR 自动编号与注入
- DoD 硬门禁
- Backlog 认领（支持任务结构化归一）
- 会话摘要
- 阶段总结写入
- 归档与索引维护
- schema 校验（ERROR / WARN）
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# -------------------------------------------------------------------
# 核心路径配置
# -------------------------------------------------------------------

SESSION_MAX_ENTRIES = 20
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATE_PATH = os.path.join(SKILL_DIR, "references", "stage_template.md")

ALLOWED_STAGE_STATUS = {"PLANNING", "IN_PROGRESS", "TESTING", "COMPLETED", "ARCHIVED"}
ALLOWED_LOG_STATUS = {"已完成", "进行中", "阻塞"}
ALLOWED_EXECUTOR = {"human", "agent", "sub_agent"}


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
        """
        根据项目根目录计算并填充所有资产路径。
        Args:
            project_root: 项目根目录（可为相对或绝对路径）。
        Side Effects:
            更新实例上的路径字段。
        """
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
# 常量资源
# -------------------------------------------------------------------

STRINGS = {
    "stages_index_head": (
        "# Stages Index\n\n"
        "> 此文件由 stage-manager 自动维护。所有资产位于 .stages/ 目录下。\n\n"
        "---\n\n"
        "## 阶段清单\n"
    ),
    "adrs_head": (
        "# Architectural Decision Records (ADRS)\n\n"
        "---\n\n"
        "## 决策目录\n"
    ),
    "sessions_head": (
        "# Stage Session Logs (Compressed)\n\n"
        "---\n\n"
        "## 会话摘要\n"
    ),
    "backlogs_head": (
        "# 项目待办清单 (Backlogs)\n\n"
        "## [TECH_DEBT] 技术债务\n\n"
        "## [ROADMAP] 路线图\n"
    ),
}


# -------------------------------------------------------------------
# 基础工具
# -------------------------------------------------------------------

def now_date() -> str:
    """
    返回当前本地日期字符串。
    Returns:
        str: YYYY-MM-DD 格式日期。
    """
    return datetime.now().strftime("%Y-%m-%d")


def now_datetime() -> str:
    """
    返回当前本地日期时间字符串。
    Returns:
        str: YYYY-MM-DD HH:MM 格式时间。
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_text(path: str) -> str:
    """
    读取 UTF-8 文本文件内容。
    Args:
        path: 文件路径。
    Returns:
        str: 文件全文内容。
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, content: str):
    """
    以 UTF-8 覆盖写入文本文件。
    Args:
        path: 文件路径。
        content: 写入内容。
    Side Effects:
        覆盖目标文件内容。
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def discover_project_root(root_override=None):
    """
    推断项目根目录。
    Args:
        root_override: 手动指定根目录（可为空）。
    Returns:
        str: 解析后的绝对路径。
    Notes:
        优先级：root_override > STAGE_MANAGER_ROOT > 向上探测 .git/.stages。
    """
    if root_override:
        return os.path.abspath(root_override)

    env_root = os.environ.get("STAGE_MANAGER_ROOT")
    if env_root:
        return os.path.abspath(env_root)

    cwd = os.path.abspath(os.getcwd())
    probe = cwd
    while True:
        if os.path.isdir(os.path.join(probe, ".git")) or os.path.isdir(os.path.join(probe, ".stages")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return cwd
        probe = parent


def get_git_info():
    """
    获取当前 Git 短哈希标识。
    Returns:
        str: 形如 git@<hash> 的标识；若失败则返回 local-env。
    """
    try:
        devnull = subprocess.DEVNULL
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=devnull,
        ).decode().strip()
        return f"git@{git_hash}"
    except Exception:
        return "local-env"


def get_sys_user():
    """
    读取系统用户名。
    Returns:
        str: USER/USERNAME 环境变量值，缺省为 unknown。
    """
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def slugify_name(name: str) -> str:
    """
    将名称归一化为文件安全的 slug。
    Args:
        name: 原始名称。
    Returns:
        str: 仅含小写字母、数字、-、_、. 的 slug。
    """
    s = name.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-_.]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "unnamed-stage"


def infer_stage_display_name(raw_name: str) -> str:
    """
    生成阶段展示名。
    Args:
        raw_name: 原始输入名称。
    Returns:
        str: 去除首尾空白后的名称，空值时返回 TBD。
    """
    return raw_name.strip() if raw_name.strip() else "TBD"


def ensure_structure():
    """
    确保 .stages 目录结构与索引文件存在。
    Side Effects:
        创建目录及缺失的索引文件并写入默认内容。
    """
    for d in [cfg.asset_root, cfg.stages_exec_dir, cfg.archive_exec_dir]:
        os.makedirs(d, exist_ok=True)

    if not os.path.exists(cfg.stages_index):
        write_text(
            cfg.stages_index,
            STRINGS["stages_index_head"]
            + "\n---\n\n"
            + "## 快速状态\n"
            + "- [HEARTBEAT] Init\n"
            + "- [LAST_SESSION] 暂无记录\n"
            + f"- 最近同步: {now_datetime()} | 用户: {get_sys_user()} | Version: {get_git_info()}\n"
        )

    if not os.path.exists(cfg.adr_index):
        write_text(
            cfg.adr_index,
            STRINGS["adrs_head"]
            + "\n---\n\n"
            + "## 统计信息\n"
            + "- 总计决策: 0\n"
            + f"- 最近更新: {now_datetime()}\n"
        )

    if not os.path.exists(cfg.session_file):
        write_text(
            cfg.session_file,
            STRINGS["sessions_head"]
            + "\n---\n\n"
            + "## 最近记录\n"
            + "- 暂无活动记录\n"
        )

    if not os.path.exists(cfg.backlog_file):
        write_text(cfg.backlog_file, STRINGS["backlogs_head"])


# -------------------------------------------------------------------
# frontmatter / markdown
# -------------------------------------------------------------------

def parse_frontmatter(content: str):
    """
    解析 frontmatter 并拆分正文。
    Args:
        content: 完整 Markdown 文本。
    Returns:
        Tuple[dict, str]: frontmatter 字典与正文内容。
    Notes:
        解析规则为简化键值/列表语法，并非完整 YAML。
    """
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.S)
    if not m:
        return {}, content

    raw = m.group(1)
    body = m.group(2)
    data = {}

    for line in raw.splitlines():
        if not line.strip():
            continue
        line_no_comment = re.sub(r"\s+#.*$", "", line)
        if ":" not in line_no_comment:
            continue
        k, v = line_no_comment.split(":", 1)
        key = k.strip()
        val = v.strip()

        if val == "null":
            data[key] = None
        elif val == "[]":
            data[key] = []
        elif val.startswith('"') and val.endswith('"'):
            data[key] = val[1:-1]
        elif val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                data[key] = []
            else:
                parts = [x.strip().strip('"') for x in inner.split(",") if x.strip()]
                data[key] = parts
        else:
            data[key] = val

    return data, body


def dump_frontmatter(data: dict) -> str:
    """
    按固定字段顺序序列化 frontmatter。
    Args:
        data: frontmatter 字典。
    Returns:
        str: 序列化后的 frontmatter 文本（包含 --- 包围）。
    """
    ordered_keys = [
        "stage_id",
        "name",
        "status",
        "start_date",
        "end_date",
        "depends_on",
        "milestone",
    ]

    lines = ["---"]
    for key in ordered_keys:
        value = data.get(key)
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, list):
            if value:
                joined = ", ".join(f'"{x}"' if " " in str(x) else str(x) for x in value)
                lines.append(f"{key}: [{joined}]")
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f'{key}: "{value}"')
    lines.append("---")
    return "\n".join(lines)


def replace_frontmatter(content: str, updates: dict) -> str:
    """
    合并更新并替换 frontmatter。
    Args:
        content: 原始文档内容。
        updates: 需要更新的字段。
    Returns:
        str: 更新后的完整文档内容。
    """
    current, body = parse_frontmatter(content)
    current.update(updates)
    return dump_frontmatter(current) + "\n" + body.lstrip("\n")


def update_title(content: str, stage_id: str, name: str) -> str:
    """
    更新文档一级标题为阶段标题。
    Args:
        content: 原始文档内容。
        stage_id: 阶段 ID。
        name: 阶段名称。
    Returns:
        str: 更新后的内容。
    """
    new_title = f"# {stage_id}: {name}"
    if re.search(r"^# .*?$", content, re.M):
        return re.sub(r"^# .*?$", new_title, content, count=1, flags=re.M)
    return new_title + "\n\n" + content


def find_section_block(content: str, section_no: int):
    """
    按编号查找 section 块。
    Args:
        content: 文档内容。
        section_no: section 编号（例如 4 表示 "## 4."）。
    Returns:
        Optional[Tuple[int, int, str, str]]: (start, end, header, body) 或 None。
    """
    pattern = rf"(^## {section_no}\..*?$)(.*?)(?=^## \d+\.|\Z)"
    m = re.search(pattern, content, re.M | re.S)
    if not m:
        return None
    return (m.start(), m.end(), m.group(1), m.group(2))


def replace_section_body(content: str, section_no: int, new_body: str) -> str:
    """
    替换指定 section 的正文内容。
    Args:
        content: 文档内容。
        section_no: section 编号。
        new_body: 新的正文文本。
    Returns:
        str: 更新后的内容；若未找到 section 则返回原文。
    """
    block = find_section_block(content, section_no)
    if not block:
        return content

    start, end, header, _old_body = block
    replacement = header + "\n\n" + new_body.strip("\n") + "\n"
    return content[:start] + replacement + content[end:]


def prepend_to_section_body(content: str, section_no: int, block_text: str, remove_placeholder_tbd=False) -> str:
    """
    向 section 正文前插入内容块。
    Args:
        content: 文档内容。
        section_no: section 编号。
        block_text: 待插入文本块。
        remove_placeholder_tbd: 是否移除“暂无”占位。
    Returns:
        str: 更新后的内容。
    """
    section = find_section_block(content, section_no)
    if not section:
        return content

    start, end, header, body = section
    body_text = body.strip("\n")

    if remove_placeholder_tbd:
        body_text = re.sub(r"^\s*-\s*暂无\s*$", "", body_text, flags=re.M).strip("\n")

    parts = []
    if block_text.strip():
        parts.append(block_text.strip("\n"))
    if body_text.strip():
        parts.append(body_text.strip("\n"))

    new_body = "\n\n".join(parts) if parts else "- 暂无"
    replacement = header + "\n\n" + new_body + "\n"
    return content[:start] + replacement + content[end:]


# -------------------------------------------------------------------
# 路径解析
# -------------------------------------------------------------------

def get_latest_stage_info():
  """
  从 STAGES.md 中定位唯一当前阶段。
  返回 (active_filename_or_none, max_stage_num_str)
  """
  ensure_structure()

  active_files = []
  if os.path.exists(cfg.stages_exec_dir):
      active_files = [f for f in os.listdir(cfg.stages_exec_dir) if f.endswith(".md")]

  max_num = f"{max((_extract_stage_num(f) for f in active_files), default=0):03d}"

  if not os.path.exists(cfg.stages_index):
      return None, max_num

  content = read_text(cfg.stages_index)
  active_match = re.search(r"`\.stages/stages/(stage-\d+-.*?\.md)`（当前阶段）", content)

  return (active_match.group(1) if active_match else None), max_num


def resolve_stage_file(target: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    解析阶段文件位置。
    Args:
        target: None 表示当前活跃阶段；也可传文件名或相对/绝对路径。
    Returns:
        Tuple[Optional[str], Optional[str]]: (filename, absolute_path)。
    """
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


# -------------------------------------------------------------------
# 统计
# -------------------------------------------------------------------
def list_active_stage_files() -> List[str]:
    """列出所有活跃阶段文件名，按阶段编号排序。"""
    if not os.path.exists(cfg.stages_exec_dir):
        return []
    files = [f for f in os.listdir(cfg.stages_exec_dir) if f.endswith(".md")]
    return sorted(files, key=_extract_stage_num)

def _extract_stage_num(filename: str) -> int:
    """从文件名中提取阶段编号，若无匹配返回最大值 999999。"""
    m = re.search(r"stage-(\d+)-", filename)
    return int(m.group(1)) if m else 999999

def rewrite_stages_index(current_stage: Optional[str] = None):
    """
    重建 STAGES.md 的阶段清单，保证：
    - archive/stages 下的文件标记为 （已归档）
    - stages 下的文件若为 current_stage，则标记为 （当前阶段）
    - stages 下的其余文件标记为 （活跃阶段）
    - 任意时刻只允许一个 （当前阶段）
    """
    ensure_structure()

    # 读取现有文件，保留“快速状态”区域
    existing = read_text(cfg.stages_index) if os.path.exists(cfg.stages_index) else ""
    quick_status_match = re.search(
        r"(^---\n\n## 快速状态.*$)",
        existing,
        re.M | re.S,
    )

    quick_status_block = quick_status_match.group(1) if quick_status_match else (
        "---\n\n"
        "## 快速状态\n"
        "- [HEARTBEAT] Init\n"
        "- [LAST_SESSION] 暂无记录\n"
        f"- 最近同步: {now_datetime()} | 用户: {get_sys_user()} | Version: {get_git_info()}\n"
    )

    active_files = []
    archived_files = []

    if os.path.exists(cfg.stages_exec_dir):
        active_files = [
            f for f in os.listdir(cfg.stages_exec_dir)
            if f.endswith(".md")
        ]

    if os.path.exists(cfg.archive_exec_dir):
        archived_files = [
            f for f in os.listdir(cfg.archive_exec_dir)
            if f.endswith(".md")
        ]

    active_files = sorted(active_files, key=_extract_stage_num)
    archived_files = sorted(archived_files, key=_extract_stage_num)

    # 若未显式传 current_stage，则尝试沿用旧索引中的当前阶段
    if not current_stage:
        old_current_match = re.search(
            r"`\.stages/stages/(stage-\d+-.*?\.md)`（当前阶段）",
            existing,
        )
        if old_current_match and old_current_match.group(1) in active_files:
            current_stage = old_current_match.group(1)

    # 如果仍为空，但存在未归档阶段，则默认第一个阶段为当前阶段
    if not current_stage and active_files:
        current_stage = active_files[0]

    lines = []
    lines.append("# Stages Index\n\n")
    lines.append("> 此文件由 stage-manager 自动维护。所有资产位于 .stages/ 目录下。\n\n")
    lines.append("---\n\n")
    lines.append("## 阶段清单\n")

    index = 1

    # 未归档阶段：当前阶段排前，其余活跃阶段随后
    if active_files:
        ordered_active = []
        if current_stage and current_stage in active_files:
            ordered_active.append(current_stage)
        ordered_active.extend([f for f in active_files if f != current_stage])

        for f in ordered_active:
            status = "当前阶段" if f == current_stage else "活跃阶段"
            lines.append(f"{index}. `.stages/stages/{f}`（{status}）\n")
            index += 1

    # 已归档阶段
    for f in archived_files:
        lines.append(f"{index}. `.stages/archive/stages/{f}`（已归档）\n")
        index += 1

    lines.append("\n")
    lines.append(quick_status_block.strip("\n") + "\n")

    write_text(cfg.stages_index, "".join(lines))

def count_adrs_from_index():
    """
    统计 ADR 索引中的条目数量。
    Returns:
        int: ADR 数量。
    """
    if not os.path.exists(cfg.adr_index):
        return 0
    return len(re.findall(r"\[ADRS-\d+\]", read_text(cfg.adr_index)))


def get_last_session_text():
    """
    读取最近会话快照文本。
    Returns:
        str: 最近会话摘要，缺失时返回“暂无记录”。
    """
    if not os.path.exists(cfg.session_file):
        return "暂无记录"
    content = read_text(cfg.session_file)
    match = re.search(r"- \*\*会话快照\*\*: (.*?)\n", content)
    return match.group(1).strip() if match else "暂无记录"


def calculate_progress(filepath):
    """
    计算阶段文件任务完成度。
    Args:
        filepath: 阶段文件路径。
    Returns:
        int: 完成度百分比（0-100）。
    Notes:
        仅统计 section 4/5 中的 checklist。
    """
    if not os.path.exists(filepath):
        return 0

    content = read_text(filepath)
    sections = re.findall(r"^## [45]\..*?(?=^## \d+\.|\Z)", content, re.M | re.S)

    all_marks = []
    for s in sections:
        all_marks.extend(re.findall(r"^\s*(?:-\s*|\d+\.\s*)\[( |x|X)\]", s, re.M))

    if not all_marks:
        return 0

    done = sum(1 for t in all_marks if t.lower() == "x")
    return int((done / len(all_marks)) * 100)


def get_project_stats():
    """
    汇总项目统计数据并拼接为状态字符串。
    Returns:
        str: 阶段/任务/ADR 统计摘要。
    Side Effects:
        确保目录结构存在。
    """
    ensure_structure()

    done_stages = len([f for f in os.listdir(cfg.archive_exec_dir) if f.endswith(".md")]) if os.path.exists(cfg.archive_exec_dir) else 0
    active_stages = len([f for f in os.listdir(cfg.stages_exec_dir) if f.endswith(".md")]) if os.path.exists(cfg.stages_exec_dir) else 0

    total_done_tasks = 0
    total_pending_tasks = 0

    if os.path.exists(cfg.backlog_file):
        backlog_content = read_text(cfg.backlog_file)
        total_pending_tasks += len(re.findall(r"^\s*-\s*\[ \]", backlog_content, re.M))

    active_file, active_path = resolve_stage_file(None)
    if active_file and active_path and os.path.exists(active_path):
        content = read_text(active_path)
        sections = re.findall(r"^## [45]\..*?(?=^## \d+\.|\Z)", content, re.M | re.S)
        for s in sections:
            total_done_tasks += len(re.findall(r"^\s*(?:-\s*|\d+\.\s*)\[(x|X)\]", s, re.M))
            total_pending_tasks += len(re.findall(r"^\s*(?:-\s*|\d+\.\s*)\[ \]", s, re.M))

    adr_c = count_adrs_from_index()
    return f"阶段(归档/活跃): {done_stages}/{active_stages} | 任务(完成/待办): {total_done_tasks}/{total_pending_tasks} | 决策: {adr_c}"


def update_heartbeat():
    """
    刷新 STAGES.md 的心跳、最近会话与同步时间。
    Side Effects:
        覆盖写入 STAGES.md。
    """
    ensure_structure()
    stats = get_project_stats()
    last_session = get_last_session_text()
    now = now_datetime()
    user = get_sys_user()
    ver = get_git_info()

    lines = read_text(cfg.stages_index).splitlines(True)
    found_sync = False

    for i, line in enumerate(lines):
        if "[HEARTBEAT]" in line:
            lines[i] = f"- [HEARTBEAT] {stats}\n"
        elif "[LAST_SESSION]" in line:
            lines[i] = f"- [LAST_SESSION] {last_session}\n"
        elif "最近同步" in line:
            lines[i] = f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n"
            found_sync = True

    if not found_sync:
        lines.append(f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n")

    write_text(cfg.stages_index, "".join(lines))


# -------------------------------------------------------------------
# 任务解析与归一化
# -------------------------------------------------------------------
def clean_summary_text(text: str) -> str:
    """
    清洗摘要文本为单行纯文本。
    Args:
        text: 原始 Markdown/列表文本。
    Returns:
        str: 去除格式后的摘要文本，空值时返回 N/A。
    """
    if not text:
        return "N/A"

    cleaned = text

    # 去掉 markdown 粗体
    cleaned = cleaned.replace("**", "")

    # 去掉 summary/log 头部标记
    cleaned = re.sub(r"^- ###\s*", "", cleaned, flags=re.M)

    # 去掉 checklist 标记
    cleaned = re.sub(r"^\s*-\s*\[x\]\s*", "", cleaned, flags=re.M | re.I)
    cleaned = re.sub(r"^\s*-\s*\[ \]\s*", "", cleaned, flags=re.M)

    # 去掉普通 bullet
    cleaned = re.sub(r"^\s*-\s*", "", cleaned, flags=re.M)

    # 合并空白
    cleaned = re.sub(r"\s+", " ", cleaned)

    return cleaned.strip() or "N/A"


def extract_summary_brief(content: str) -> str:
    """
    从阶段总结区块提取简短摘要。
    Args:
        content: 阶段文档全文。
    Returns:
        str: 适合写入索引/会话的摘要（<=240 字符）。
    Notes:
        优先使用 SUMMARY/里程碑/成果/变更审计；否则降级清洗。
    """
    section = re.search(r"^## 9\..*?(?=^## \d+\.|\Z)", content, re.M | re.S)
    if not section:
        return "N/A"

    block = section.group(0)

    title_match = re.search(
        r"^- ### \[SUMMARY-\d+\] \| \[\d{4}-\d{2}-\d{2}\] \| \[(.*?)\] \| \[Ver:.*?\]",
        block,
        re.M,
    )
    goal_match = re.search(r"^\s*- \*\*里程碑目标\*\*: (.*)$", block, re.M)
    result_matches = re.findall(r"^\s*-\s*\[x\]\s+(.*)$", block, re.M)
    audit_match = re.search(r"^\s*- \*\*变更审计\*\*: (.*)$", block, re.M)

    parts = []

    if title_match:
        parts.append(title_match.group(1).strip())

    if goal_match:
        parts.append(f"目标：{goal_match.group(1).strip()}")

    if result_matches:
        parts.append("成果：" + "；".join(r.strip() for r in result_matches[:2]))

    if audit_match:
        parts.append(f"变更：{audit_match.group(1).strip()}")

    if not parts:
        # 兜底：把 section 内容做一次清洗后截断
        raw_lines = []
        for line in block.splitlines():
            s = line.strip()
            if not s or s.startswith("## ") or s.startswith(">"):
                continue
            raw_lines.append(s)
        return clean_summary_text(" ".join(raw_lines))[:240] or "N/A"

    return " | ".join(parts)[:240]

def parse_task_line(task_line: str) -> Optional[Dict[str, str]]:
    """
    解析结构化任务行。
    Args:
        task_line: 任务行文本。
    Returns:
        Optional[Dict[str, str]]: 解析结果字段字典，格式非法返回 None。
    """
    raw = task_line.strip()
    raw = re.sub(r"^\-\s*\[[ xX]\]\s*", "", raw)

    parts = [p.strip() for p in raw.split("|")]
    if not parts:
        return None

    first = parts[0]
    prio_match = re.match(r"^\[(P\d+)\]\s+(.*)$", first)
    if not prio_match:
        return None

    result = {
        "priority": prio_match.group(1),
        "name": prio_match.group(2).strip(),
        "owner": "",
        "executor": "",
        "skills": "",
        "task_depends_on": "",
        "due": "",
    }

    for part in parts[1:]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        result[k.strip()] = v.strip()

    return result


def validate_task_line(task_line: str) -> List[str]:
    """
    校验任务行字段合法性。
    Args:
        task_line: 任务行文本。
    Returns:
        List[str]: 错误信息列表；为空表示通过。
    """
    errs = []
    parsed = parse_task_line(task_line)
    if not parsed:
        errs.append(f"任务格式非法: {task_line}")
        return errs

    if parsed.get("executor") and parsed["executor"] not in ALLOWED_EXECUTOR:
        errs.append(f"executor 非法: {parsed['executor']}")

    due = parsed.get("due", "")
    if due and due != "YYYY-MM-DD" and due != "null":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            errs.append(f"due 日期格式非法: {due}")

    return errs


def normalize_backlog_task_line(task_line: str) -> str:
    """
    将 Backlog 任务归一为结构化格式。
    Args:
        task_line: 任务行文本。
    Returns:
        str: 规范化后的任务行。
    Notes:
        若缺少优先级会默认 P1 并补充占位字段。
    """
    raw = task_line.strip()

    if parse_task_line(raw):
        return raw if raw.startswith("- [ ]") else f"- [ ] {raw}"

    raw = re.sub(r"^\-\s*\[[ xX]\]\s*", "", raw).strip()

    prio = "P1"
    m = re.match(r"^\[(P\d+)\]\s+(.*)$", raw)
    if m:
        prio = m.group(1)
        name = m.group(2).strip()
    else:
        name = raw

    return (
        f"- [ ] [{prio}] {name} | owner=unassigned | executor=agent | "
        f"skills=[] | task_depends_on=[] | due=YYYY-MM-DD"
    )


def get_pending_tasks(filepath):
    """
    提取未完成任务并按优先级排序。
    Args:
        filepath: 阶段文件路径。
    Returns:
        List[str]: 未完成任务列表。
    """
    if not os.path.exists(filepath):
        return []

    content = read_text(filepath)
    breakdown_match = re.search(r"^## 4\..*?(?=^## \d+\.|\Z)", content, re.M | re.S)
    if not breakdown_match:
        return []

    tasks = re.findall(r"^\s*-\s*\[ \]\s+(.*)$", breakdown_match.group(0), re.M)

    def p_score(t):
        m = re.search(r"\[P(\d+)\]", t)
        return int(m.group(1)) if m else 999

    return sorted(tasks, key=p_score)


# -------------------------------------------------------------------
# 校验
# -------------------------------------------------------------------

def check_dod_completed(filepath):
    """
    检查 DoD 区块是否全部完成。
    Args:
        filepath: 阶段文件路径。
    Returns:
        Tuple[bool, List[str]]: (是否完成, 未完成条目)。
    """
    if not os.path.exists(filepath):
        return True, []

    content = read_text(filepath)
    dod_section = re.search(r"^## 5\..*?(?=^## \d+\.|\Z)", content, re.M | re.S)
    if not dod_section:
        return True, []

    pending_dod = re.findall(r"^\s*(?:-\s*|\d+\.\s*)\[ \].*$", dod_section.group(0), re.M)
    return len(pending_dod) == 0, pending_dod


def validate_stage_document(filepath: str) -> Tuple[List[str], List[str]]:
    """
    校验阶段文档结构与字段规范。
    Args:
        filepath: 阶段文件路径。
    Returns:
        Tuple[List[str], List[str]]: (errors, warns)。
    Notes:
        同时检查 frontmatter、section 完整性与任务格式。
    """
    errors: List[str] = []
    warns: List[str] = []

    if not os.path.exists(filepath):
        return [f"文件不存在: {filepath}"], []

    content = read_text(filepath)
    fm, _body = parse_frontmatter(content)

    required_frontmatter = ["stage_id", "name", "status", "start_date", "end_date", "depends_on", "milestone"]
    for key in required_frontmatter:
        if key not in fm:
            errors.append(f"frontmatter 缺少字段: {key}")

    if "status" in fm and fm["status"] not in ALLOWED_STAGE_STATUS:
        errors.append(f"stage status 非法: {fm['status']}")

    if "start_date" in fm and fm["start_date"] not in (None, "null"):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fm["start_date"])):
            errors.append(f"start_date 日期格式非法: {fm['start_date']}")

    if "end_date" in fm and fm["end_date"] not in (None, "null"):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(fm["end_date"])):
            errors.append(f"end_date 日期格式非法: {fm['end_date']}")

    if fm.get("status") in {"COMPLETED", "ARCHIVED"} and not fm.get("end_date"):
        errors.append("状态为 COMPLETED/ARCHIVED 时，end_date 不得为 null")

    if fm.get("status") in {"PLANNING", "IN_PROGRESS", "TESTING"} and fm.get("end_date"):
        warns.append("未归档阶段通常不应填写 end_date")

    for sec in range(1, 10):
        if not find_section_block(content, sec):
            errors.append(f"缺少 section: ## {sec}.")

    task_section = find_section_block(content, 4)
    if task_section:
        _s, _e, _h, body = task_section
        task_lines = re.findall(r"^\s*-\s*\[[ xX]\].*$", body, re.M)
        for t in task_lines:
            errors.extend(validate_task_line(t))
        if not task_lines:
            warns.append("任务拆解 section 中暂无 checklist 任务")

    log_section = find_section_block(content, 7)
    if log_section:
        _s, _e, _h, body = log_section
        if re.fullmatch(r"\s*-\s*暂无\s*", body.strip()):
            warns.append("进度日志为空")

    summary_section = find_section_block(content, 9)
    if summary_section:
        _s, _e, _h, body = summary_section
        if re.fullmatch(r"\s*-\s*暂无\s*", body.strip()):
            warns.append("阶段总结为空")

    return errors, warns


# -------------------------------------------------------------------
# ADR / session
# -------------------------------------------------------------------

def update_adr_index(clean_msg, stage_file, is_archive=False):
    """
    追加 ADR 索引条目并更新统计。
    Args:
        clean_msg: ADR 标题内容。
        stage_file: 关联阶段文件名。
        is_archive: 是否归档阶段。
    Returns:
        str: 新生成的 ADR ID。
    Side Effects:
        覆盖写入 ADRS.md。
    """
    ensure_structure()

    lines = read_text(cfg.adr_index).splitlines(True)
    current_count = count_adrs_from_index()
    adr_id = f"ADRS-{current_count + 1:03d}"
    path_prefix = ".stages/archive/stages/" if is_archive else ".stages/stages/"
    new_entry = f"{current_count + 1}. [{adr_id}] {clean_msg} ({path_prefix}{stage_file})\n"

    insert_idx = -1
    for i, line in enumerate(lines):
        if "决策目录" in line:
            insert_idx = i + 1
            break

    if insert_idx != -1:
        lines.insert(insert_idx + current_count, new_entry)
    else:
        lines.append("\n" + new_entry)

    found_total = False
    found_update = False
    for i, line in enumerate(lines):
        if "总计决策" in line:
            lines[i] = f"- 总计决策: {current_count + 1}\n"
            found_total = True
        elif "最近更新" in line:
            lines[i] = f"- 最近更新: {now_datetime()}\n"
            found_update = True

    if not found_total:
        lines.append(f"- 总计决策: {current_count + 1}\n")
    if not found_update:
        lines.append(f"- 最近更新: {now_datetime()}\n")

    write_text(cfg.adr_index, "".join(lines))
    return adr_id


def _prune_session_entries(lines):
    """
    按最大条数裁剪会话摘要区块。
    Args:
        lines: 会话文件行列表。
    Returns:
        List[str]: 裁剪后的行列表。
    """
    entry_indices = [i for i, line in enumerate(lines) if line.startswith("### [")]
    if len(entry_indices) <= SESSION_MAX_ENTRIES:
        return lines
    cutoff = entry_indices[SESSION_MAX_ENTRIES]
    return lines[:cutoff]


def update_session_summary(text):
    """
    写入会话摘要并刷新心跳。
    Args:
        text: 摘要文本。
    Side Effects:
        更新 STAGE_SESSIONS.md 与 STAGES.md。
    """
    ensure_structure()

    clean_text = clean_summary_text(text)
    active_file, _ = get_latest_stage_info()
    now = now_datetime()

    lines = read_text(cfg.session_file).splitlines(True)
    new_entry = f"### [{now}] Stage: {active_file or 'Global'}\n- **会话快照**: {clean_text}\n\n"

    insert_idx = -1
    for i, line in enumerate(lines):
        if "会话摘要" in line:
            insert_idx = i + 1
            break

    if insert_idx != -1:
        lines.insert(insert_idx + 1, new_entry)
    else:
        lines.append(new_entry)

    for i, line in enumerate(lines):
        if line.startswith("- 最近记录") or line.startswith("- 暂无活动记录"):
            lines[i] = f"- 最近记录: [{now}] {clean_text[:60]}...\n"
            break

    lines = _prune_session_entries(lines)
    write_text(cfg.session_file, "".join(lines))
    update_heartbeat()


# -------------------------------------------------------------------
# 渲染器
# -------------------------------------------------------------------

def next_log_id(filepath: str) -> str:
    """
    生成下一个日志编号。
    Args:
        filepath: 阶段文件路径。
    Returns:
        str: 形如 LOG-001 的编号。
    """
    if not os.path.exists(filepath):
        return "LOG-001"
    content = read_text(filepath)
    count = len(re.findall(r"\[LOG-\d+\]", content))
    return f"LOG-{count + 1:03d}"


def next_summary_id(filepath: str) -> str:
    """
    生成下一个总结编号。
    Args:
        filepath: 阶段文件路径。
    Returns:
        str: 形如 SUMMARY-001 的编号。
    """
    if not os.path.exists(filepath):
        return "SUMMARY-001"
    content = read_text(filepath)
    count = len(re.findall(r"\[SUMMARY-\d+\]", content))
    return f"SUMMARY-{count + 1:03d}"


def render_log_entry(
    filepath: str,
    message: str,
    task_name: Optional[str] = None,
    status: str = "进行中",
    next_action: Optional[str] = None,
    blocked_by: Optional[str] = None,
) -> str:
    """
    渲染进度日志条目。
    Args:
        filepath: 阶段文件路径。
        message: 进展描述。
        task_name: 关联任务名。
        status: 日志状态。
        next_action: 后续行动。
        blocked_by: 阻塞依赖。
    Returns:
        str: Markdown 日志条目文本。
    """
    log_id = next_log_id(filepath)
    date_str = now_date()
    user = get_sys_user()
    ver = get_git_info()

    log_task_name = task_name or "SYNC"

    if status == "阻塞" and blocked_by:
        status_text = f"阻塞 (Blocked by: {blocked_by})"
    else:
        status_text = status

    return (
        f"- ### [{log_id}] | [{date_str}] | [{log_task_name}] | [{user}] | [Ver:{ver}]\n"
        f"  - **状态**: {status_text}\n"
        f"  - **关键进展**: {message}\n"
        f"  - **后续行动**: {next_action or 'TBD'}\n"
    )


def render_adr_entry(adr_id: str, title: str) -> str:
    """
    渲染 ADR 条目模板。
    Args:
        adr_id: ADR 编号。
        title: ADR 标题。
    Returns:
        str: Markdown ADR 条目文本。
    """
    date_str = now_date()
    return (
        f"- ### [{adr_id}] | [{date_str}] | [{title}]\n"
        f"  - **背景/动机**: TBD\n"
        f"  - **可选方案**: TBD\n"
        f"  - **结论**: TBD\n"
        f"  - **影响/后果**: TBD\n"
    )


def render_summary_entry(
    filepath: str,
    name: str,
    milestone_goal: str,
    core_results: List[str],
    change_audit: str,
    tech_debt: str,
) -> str:
    """
    渲染阶段总结条目。
    Args:
        filepath: 阶段文件路径。
        name: 总结名称。
        milestone_goal: 里程碑目标。
        core_results: 核心成果列表。
        change_audit: 变更审计。
        tech_debt: 遗留风险/技术债。
    Returns:
        str: Markdown 总结条目文本。
    """
    summary_id = next_summary_id(filepath)
    date_str = now_date()
    ver = get_git_info()

    result_lines = "\n".join([f"    - [x] {item}" for item in core_results]) if core_results else "    - [x] TBD"

    return (
        f"- ### [{summary_id}] | [{date_str}] | [{name}] | [Ver:{ver}]\n"
        f"  - **里程碑目标**: {milestone_goal}\n"
        f"  - **核心成果**:\n"
        f"{result_lines}\n"
        f"  - **变更审计**: {change_audit}\n"
        f"  - **遗留风险/技术债**: {tech_debt}\n"
    )


# -------------------------------------------------------------------
# heartbeat / 展示
# -------------------------------------------------------------------

def update_heartbeat():
    """
    刷新 STAGES.md 的心跳、最近会话与同步时间。
    Side Effects:
        覆盖写入 STAGES.md。
    """
    ensure_structure()
    stats = get_project_stats()
    last_session = get_last_session_text()
    now = now_datetime()
    user = get_sys_user()
    ver = get_git_info()

    lines = read_text(cfg.stages_index).splitlines(True)
    found_sync = False

    for i, line in enumerate(lines):
        if "[HEARTBEAT]" in line:
            lines[i] = f"- [HEARTBEAT] {stats}\n"
        elif "[LAST_SESSION]" in line:
            lines[i] = f"- [LAST_SESSION] {last_session}\n"
        elif "最近同步" in line:
            lines[i] = f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n"
            found_sync = True

    if not found_sync:
        lines.append(f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n")

    write_text(cfg.stages_index, "".join(lines))


def show_status(file_target: Optional[str] = None):
    """
    输出项目健康度与近期摘要信息。
    Args:
        file_target: 指定阶段文件或 None。
    Returns:
        bool: 执行成功返回 True。
    Side Effects:
        打印到 stdout，并刷新心跳。
    """
    filename, filepath = resolve_stage_file(file_target)

    print("\n" + "=" * 50)
    print(f" [项目健康度] {get_project_stats()}")
    print("=" * 50)

    if filename and filepath:
        p = calculate_progress(filepath)
        bar = "#" * int(p / 5) + "-" * (20 - int(p / 5))
        print(f" [阶段文件] {filename}")
        print(f" [完成进度] [{bar}] {p}%")

        pending = get_pending_tasks(filepath)
        if pending:
            print("\n [未完成任务] (前5条):")
            for t in pending[:5]:
                print(f"  [ ] {t.strip()}")

    if os.path.exists(cfg.adr_index):
        print("\n [最近决策] (最近3条):")
        adrs = re.findall(r"^\d+\. (\[ADRS-\d+\].*?)$", read_text(cfg.adr_index), re.M)
        for a in adrs[-3:]:
            print(f"  * {a.strip()}")

    if os.path.exists(cfg.session_file):
        print("\n [最近会话] (最近3条):")
        sessions = re.findall(r"- \*\*会话快照\*\*: (.*?)\n", read_text(cfg.session_file))
        for s in sessions[:3]:
            print(f"  > {s[:80]}...")

    print("=" * 50 + "\n")
    update_heartbeat()
    return True


def bootstrap():
    """
    会话启动引导，输出概览与记忆锚点。
    Returns:
        bool: 执行成功返回 True。
    Side Effects:
        打印到 stdout。
    """
    ensure_structure()

    print("\n" + "=" * 50)
    print(" [BOOTSTRAP] 会话上下文恢复中...")
    print("=" * 50)

    print(f"\n [项目概览] {get_project_stats()}")

    active_file, active_path = resolve_stage_file(None)
    if active_file and active_path:
        progress = calculate_progress(active_path)
        bar = "#" * int(progress / 5) + "-" * (20 - int(progress / 5))
        print(f" [活跃阶段] {active_file}")
        print(f" [完成进度] [{bar}] {progress}%")
        pending = get_pending_tasks(active_path)
        if pending:
            print("\n [下一步待办] (按优先级前3条):")
            for t in pending[:3]:
                print(f"  [ ] {t.strip()}")
    else:
        print(" [活跃阶段] 无活跃阶段")

    if os.path.exists(cfg.session_file):
        sessions = re.findall(r"- \*\*会话快照\*\*: (.*?)\n", read_text(cfg.session_file))
        if sessions:
            print("\n [记忆锚点] 最近会话快照:")
            for s in sessions[:3]:
                print(f"  > {s[:100]}")
        else:
            print("\n [记忆锚点] 暂无历史快照。")
    else:
        print("\n [记忆锚点] 暂无历史快照。")

    if os.path.exists(cfg.adr_index):
        adrs = re.findall(r"^\d+\. (\[ADRS-\d+\].*?)$", read_text(cfg.adr_index), re.M)
        if adrs:
            print("\n [最近决策]:")
            for a in adrs[-3:]:
                print(f"  * {a.strip()}")

    if os.path.exists(cfg.backlog_file):
        backlog_count = len(re.findall(r"^\s*-\s*\[ \]", read_text(cfg.backlog_file), re.M))
        if backlog_count > 0:
            print(f"\n [Backlog] {backlog_count} 个待认领任务")

    print(f"\n [Skill 路径] {SKILL_DIR}")
    print(f" [资产目录] {cfg.asset_root}")

    print("\n" + "=" * 50)
    print(" [OK] Bootstrap 完成。")
    print("=" * 50 + "\n")
    return True


# -------------------------------------------------------------------
# backlog
# -------------------------------------------------------------------

def intake_backlog(keyword, dry_run=False, file_target: Optional[str] = None):
    """
    从 Backlog 认领任务并写入阶段文件。
    Args:
        keyword: 匹配关键字。
        dry_run: 是否仅预览。
        file_target: 指定阶段文件或 None。
    Returns:
        bool: 是否成功。
    Side Effects:
        修改 BACKLOGS.md 与阶段文件。
    """
    filename, filepath = resolve_stage_file(file_target)
    if not filename or not filepath:
        print("[!] 错误：当前没有可操作的阶段文件。")
        return False

    lines = read_text(cfg.backlog_file).splitlines(True)

    extracted_tasks = []
    remaining_lines = []

    for line in lines:
        if line.strip().startswith("- [ ]") and keyword.lower() in line.lower():
            extracted_tasks.append(line.strip())
        else:
            remaining_lines.append(line)

    if not extracted_tasks:
        print(f"[!] 未在 BACKLOGS.md 中找到匹配 '{keyword}' 的任务。")
        return False

    normalized_tasks = [normalize_backlog_task_line(t) for t in extracted_tasks]

    if dry_run:
        print(f"[DRY-RUN] 将从 Backlog 认领 {len(normalized_tasks)} 个任务至 {filename}:")
        for t in normalized_tasks:
            print(f"  {t}")
        return True

    full_content = "".join(remaining_lines)
    full_content = re.sub(
        r"### 来自 .*? \(\d{4}-\d{2}-\d{2}\)\n\s*(?=###|##|$)",
        "",
        full_content,
        flags=re.S,
    )
    write_text(cfg.backlog_file, full_content)

    content = read_text(filepath)
    new_task_block = "\n".join(normalized_tasks)
    content = prepend_to_section_body(content, 4, new_task_block, remove_placeholder_tbd=True)
    write_text(filepath, content)

    update_heartbeat()
    print(f"[OK] 已从 Backlog 认领 {len(normalized_tasks)} 个任务并载入 {filename}。")
    return True


def route_backlog(tasks, stage_file, category_marker):
    """
    将任务分流写回 BACKLOGS.md。
    Args:
        tasks: 任务行列表。
        stage_file: 来源阶段文件名。
        category_marker: 分类标记（如 [TECH_DEBT]）。
    Side Effects:
        更新 BACKLOGS.md。
    """
    if not tasks:
        return

    lines = read_text(cfg.backlog_file).splitlines(True)
    today = now_date()
    source_label = "非范围条目" if category_marker == "[ROADMAP]" else "溢出与未完成任务"
    header = f"### 来自 {stage_file} 的{source_label} ({today})\n"

    insert_idx = -1
    for i, line in enumerate(lines):
        if category_marker in line:
            insert_idx = i + 1
            break

    if insert_idx == -1:
        print(f"[!] 警告: BACKLOGS.md 中未找到 '{category_marker}' 标记，任务分流跳过。")
        return

    new_content = [header] + [f"{t}\n" if not t.endswith("\n") else t for t in tasks] + ["\n"]
    for item in reversed(new_content):
        lines.insert(insert_idx, item)

    write_text(cfg.backlog_file, "".join(lines))


# -------------------------------------------------------------------
# 初始化 / 日志 / 总结 / 归档
# -------------------------------------------------------------------

def check_stage_name_exists(name):
    """
    检查阶段名称是否已存在。
    Args:
        name: 需要检查的 slug/名称片段。
    Returns:
        Optional[str]: 匹配的文件名，未命中返回 None。
    """
    for d in [cfg.stages_exec_dir, cfg.archive_exec_dir]:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".md") and name in f:
                return f
    return None


def seed_stage_body(content: str) -> str:
    """
    用默认占位内容替换模板中的示例。
    Args:
        content: 模板内容。
    Returns:
        str: 替换后的内容。
    Notes:
        主要更新任务拆解与风险表格两部分。
    """
    task_seed = (
        "- [ ] [P0] 定义本阶段关键交付物 | owner=unassigned | executor=agent | "
        "skills=[] | task_depends_on=[] | due=YYYY-MM-DD\n"
        "- [ ] [P1] 补充阶段风险与边界 | owner=unassigned | executor=agent | "
        "skills=[] | task_depends_on=[] | due=YYYY-MM-DD"
    )

    risk_seed = (
        "| 风险描述 | 严重程度 | 触发信号 | 应对措施 | 回滚/降级方案 |\n"
        "| :------- | :------- | :------- | :------- | :------------ |\n"
    )

    content = replace_section_body(content, 4, task_seed)
    content = replace_section_body(content, 6, risk_seed)
    return content


def initialize_stage_content(template: str, next_num: str, stage_name: str) -> str:
    """
    基于模板生成新阶段文件内容。
    Args:
        template: 模板全文。
        next_num: 阶段编号字符串。
        stage_name: 原始阶段名称。
    Returns:
        str: 初始化后的阶段文档内容。
    """
    stage_id = f"STAGE-{next_num}"
    display_name = infer_stage_display_name(stage_name)

    content = replace_frontmatter(
        template,
        {
            "stage_id": stage_id,
            "name": display_name,
            "status": "PLANNING",
            "start_date": now_date(),
            "end_date": None,
            "depends_on": [],
            "milestone": None,
        },
    )

    content = update_title(content, stage_id, display_name)
    content = content.replace("<STAGE_NAME>", display_name)
    content = re.sub(r"\| 示例风险.*?\n", "", content)
    content = seed_stage_body(content)
    return content


def next_stage_status_on_sync(current_status: Optional[str], log_status: str) -> str:
    """
    根据当前状态和日志状态推导新阶段状态。
    Args:
        current_status: 当前阶段状态。
        log_status: 日志状态。
    Returns:
        str: 推导后的阶段状态。
    """
    if current_status == "PLANNING":
        return "IN_PROGRESS"
    if current_status == "IN_PROGRESS" and log_status == "已完成":
        return "IN_PROGRESS"
    return current_status or "IN_PROGRESS"


def sync_log(
    message: str,
    task_name: Optional[str] = None,
    status: str = "进行中",
    next_action: Optional[str] = None,
    blocked_by: Optional[str] = None,
    file_target: Optional[str] = None,
):
    """
    同步进展日志到阶段文件。
    Args:
        message: 日志内容。
        task_name: 关联任务名。
        status: 日志状态。
        next_action: 后续行动。
        blocked_by: 阻塞依赖。
        file_target: 指定阶段文件或 None。
    Returns:
        bool: 是否成功。
    Side Effects:
        更新阶段文件、ADR 索引与心跳信息。
    """
    filename, filepath = resolve_stage_file(file_target)
    if not filename or not filepath:
        print("[!] 当前没有可操作的阶段文件。")
        return False

    if status not in ALLOWED_LOG_STATUS:
        print(f"[!] 非法日志状态: {status}，允许值: {', '.join(sorted(ALLOWED_LOG_STATUS))}")
        return False

    content = read_text(filepath)

    if message.startswith("[ADR]"):
        clean_msg = message[5:].strip() or "TBD"
        adr_id = update_adr_index(clean_msg, filename, is_archive=("archive" in filepath))
        adr_entry = render_adr_entry(adr_id, clean_msg)
        content = prepend_to_section_body(content, 8, adr_entry, remove_placeholder_tbd=True)
        print(f"[OK] 已创建 ADR 存根: {adr_id}")

    log_entry = render_log_entry(
        filepath=filepath,
        message=message,
        task_name=task_name,
        status=status,
        next_action=next_action,
        blocked_by=blocked_by,
    )
    content = prepend_to_section_body(content, 7, log_entry, remove_placeholder_tbd=True)

    fm, _ = parse_frontmatter(content)
    new_status = next_stage_status_on_sync(fm.get("status"), status)
    if new_status != fm.get("status"):
        content = replace_frontmatter(content, {"status": new_status})

    write_text(filepath, content)
    update_heartbeat()
    print(f"[OK] 已同步到 {filename}")
    return True


def append_stage_summary(
    name: str,
    milestone_goal: str,
    core_results: List[str],
    change_audit: str,
    tech_debt: str,
    file_target: Optional[str] = None,
):
    """
    向阶段文档追加总结条目。
    Args:
        name: 总结名称。
        milestone_goal: 里程碑目标。
        core_results: 核心成果列表。
        change_audit: 变更审计。
        tech_debt: 遗留风险/技术债。
        file_target: 指定阶段文件或 None。
    Returns:
        bool: 是否成功。
    Side Effects:
        更新阶段文件与心跳。
    """
    filename, filepath = resolve_stage_file(file_target)
    if not filename or not filepath:
        print("[!] 当前没有可操作的阶段文件。")
        return False

    content = read_text(filepath)

    entry = render_summary_entry(
        filepath=filepath,
        name=name,
        milestone_goal=milestone_goal,
        core_results=core_results,
        change_audit=change_audit,
        tech_debt=tech_debt,
    )

    content = prepend_to_section_body(content, 9, entry, remove_placeholder_tbd=True)
    write_text(filepath, content)
    update_heartbeat()
    print(f"[OK] 已写入阶段总结: {filename}")
    return True


def archive_stage(force=False, dry_run=False, file_target: Optional[str] = None):
    """
    归档阶段文件并更新索引。
    Args:
        force: 是否强制归档。
        dry_run: 是否仅预览。
        file_target: 指定阶段文件或 None。
    Returns:
        bool: 是否成功。
    Side Effects:
        分流任务、写入归档、更新索引/会话并删除原文件。
    """
    filename, src = resolve_stage_file(file_target)
    if not filename or not src:
        print("[!] 当前没有可操作的阶段文件。")
        return False

    if src.startswith(os.path.abspath(cfg.archive_exec_dir)):
        print("[!] 该阶段已经位于 archive 目录。")
        return False

    progress = calculate_progress(src)
    errors, warns = validate_stage_document(src)

    if errors and not force:
        print("[!] 归档前校验失败：")
        for e in errors:
            print(f"  [ERROR] {e}")
        for w in warns:
            print(f"  [WARN]  {w}")
        print("[?] 请先修复上述 ERROR。需要强制继续时使用: done --force")
        return False

    dod_ok, pending_dod = check_dod_completed(src)
    if not dod_ok and not force:
        print("\n[!] 归档拒绝：## 5. 验收标准 (DoD) 未能全量通过。")
        for dod in pending_dod:
            print(f"  {dod.strip()}")
        print("\n[?] 请先完成上述验收项。需要强制继续时使用: done --force")
        return False

    if progress < 100 and not force:
        print(f"\n[!] 进度 {progress}% 未达标。强制归档请使用: done --force")
        return False

    if dry_run:
        print(f"[DRY-RUN] 将归档阶段: {filename} (进度: {progress}%)")
        for w in warns:
            print(f"[DRY-RUN][WARN] {w}")
        return True

    content = read_text(src)

    oos_match = re.search(r"^## 3\..*?(?=^## \d+\.|\Z)", content, re.M | re.S)
    if oos_match:
        oos_tasks = re.findall(r"^\s*-\s+\S.*$", oos_match.group(0), re.M)
        if oos_tasks:
            route_backlog(oos_tasks, filename, "[ROADMAP]")

    breakdown_match = re.search(r"^## 4\..*?(?=^## \d+\.|\Z)", content, re.M | re.S)
    if breakdown_match:
        unfinished = re.findall(r"^\s*-\s*\[ \].*$", breakdown_match.group(0), re.M)
        if unfinished:
            route_backlog(unfinished, filename, "[TECH_DEBT]")

    summary = extract_summary_brief(content)

    fm, _ = parse_frontmatter(content)
    current_status = fm.get("status")
    if current_status == "ARCHIVED":
        print("[!] 当前阶段已经是 ARCHIVED。")
        return False

    final_status = "ARCHIVED" if force and progress < 100 else "COMPLETED"
    content = replace_frontmatter(
        content,
        {
            "status": final_status,
            "end_date": now_date(),
        },
    )

    summary_section = find_section_block(content, 9)
    if summary_section:
        _s, _e, _h, body = summary_section
        if re.fullmatch(r"\s*-\s*暂无\s*", body.strip()):
            summary_entry = render_summary_entry(
                filepath=src,
                name="Archive Summary",
                milestone_goal="阶段归档。",
                core_results=["阶段已完成归档流程。"],
                change_audit="归档时自动补写状态与结束日期。",
                tech_debt="已按规则分流至 Backlog。",
            )
            content = replace_section_body(content, 9, summary_entry)

    write_text(src, content)

    dst = os.path.join(cfg.archive_exec_dir, filename)
    shutil.copy2(src, dst)
    os.remove(src)
    # lines = read_text(cfg.stages_index).splitlines(True)
    # new_lines = []
    # for line in lines:
    #     if filename in line and "（当前阶段）" in line:
    #         line = line.replace(".stages/stages/", ".stages/archive/stages/")
    #         line = line.replace("（当前阶段）", "（已归档）")
    #         new_lines.append(line)
    #         new_lines.append(f"   > {summary}\n")
    #     else:
    #         new_lines.append(line)
    # write_text(cfg.stages_index, "".join(new_lines))
    # 重建索引
    remaining_active = []
    if os.path.exists(cfg.stages_exec_dir):
        remaining_active = [
            f for f in os.listdir(cfg.stages_exec_dir)
            if f.endswith(".md")
        ]
    remaining_active = sorted(remaining_active, key=_extract_stage_num)
    next_current = remaining_active[0] if remaining_active else None
    rewrite_stages_index(current_stage=next_current)
    update_session_summary(f"[归档自动化] 阶段 {filename} 已结项: {summary}")
    # os.remove(src)
    print("[OK] 归档完成。")
    return True


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------

def main():
    """
    CLI 入口，解析参数并分发子命令。
    Side Effects:
        可能创建/修改 .stages 资产并输出日志。
    """
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--root", help="指定项目根目录")
    temp_args, _ = base_parser.parse_known_args()
    cfg.configure(discover_project_root(temp_args.root))

    parser = argparse.ArgumentParser(
        description="Stage-Manager: 工业级项目生命周期自动化管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例用法:
  python3 stage_manager.py init "feature-auth"
  python3 stage_manager.py sync "实现登录逻辑"
  python3 stage_manager.py sync "实现登录逻辑" --task-name "登录接口" --status "进行中" --next-action "补充单元测试"
  python3 stage_manager.py sync "[ADR] 使用 JWT" --task-name "认证方案"
  python3 stage_manager.py sync "修复边界条件" --file stage-001-feature-auth.md
  python3 stage_manager.py summary "会话阶段性总结"
  python3 stage_manager.py summary --stage --name "阶段小结" --goal "完成认证链路" --result "登录接口完成" --result "权限校验上线" --audit "更新 API 协议" --debt "刷新 token 仍待补全"
  python3 stage_manager.py intake "api"
  python3 stage_manager.py validate
  python3 stage_manager.py validate --file stage-001-feature-auth.md
  python3 stage_manager.py done
        """,
    )
    parser.add_argument("--root", help="指定项目根目录")
    subparsers = parser.add_subparsers(dest="cmd", title="子命令清单", required=True)

    init_p = subparsers.add_parser("init", help="初始化新阶段文档并更新看板")
    init_p.add_argument("name", help="阶段简短名称 (例如: user-auth)")

    sync_p = subparsers.add_parser("sync", help="向阶段同步进展记录")
    sync_p.add_argument("message", help="进展描述文字；使用 [ADR] 前缀可自动同步至决策索引")
    sync_p.add_argument("--task-name", help="日志关联任务名")
    sync_p.add_argument("--status", default="进行中", choices=sorted(ALLOWED_LOG_STATUS), help="日志状态")
    sync_p.add_argument("--next-action", help="后续行动")
    sync_p.add_argument("--blocked-by", help="阻塞依赖 ID，仅在 status=阻塞 时建议填写")
    sync_p.add_argument("--file", help="指定 stage 文件")

    sum_p = subparsers.add_parser("summary", help="保存会话快照，或写入阶段总结")
    sum_p.add_argument("text", nargs="?", help="会话快照内容")
    sum_p.add_argument("--stage", action="store_true", help="将 summary 作为阶段总结写入 section 9")
    sum_p.add_argument("--name", help="阶段总结名称")
    sum_p.add_argument("--goal", help="里程碑目标")
    sum_p.add_argument("--result", action="append", help="核心成果，可重复传入多次")
    sum_p.add_argument("--audit", help="变更审计")
    sum_p.add_argument("--debt", help="遗留风险/技术债")
    sum_p.add_argument("--file", help="指定 stage 文件")

    int_p = subparsers.add_parser("intake", help="从 BACKLOGS.md 中认领任务至阶段")
    int_p.add_argument("keyword", help="用于匹配 Backlog 任务的关键字")
    int_p.add_argument("--dry-run", action="store_true", help="预览认领结果，不执行实际操作")
    int_p.add_argument("--file", help="指定 stage 文件")

    subparsers.add_parser("bootstrap", help="会话启动引导，加载最近快照以恢复记忆锚点")

    status_p = subparsers.add_parser("status", help="输出可视化健康看板，含最近决策、快照及项目指标")
    status_p.add_argument("--file", help="指定 stage 文件")

    validate_p = subparsers.add_parser("validate", help="校验阶段文档结构")
    validate_p.add_argument("--file", help="指定 stage 文件")

    done_p = subparsers.add_parser("done", help="闭环归档阶段 (触发任务分流与 DoD 检查)")
    done_p.add_argument("--force", action="store_true", help="忽略未完成任务，强制执行归档操作")
    done_p.add_argument("--dry-run", action="store_true", help="预览归档操作，不执行实际变更")
    done_p.add_argument("--file", help="指定 stage 文件")

    args = parser.parse_args()
    ensure_structure()

    if args.cmd == "init":
        _, max_num = get_latest_stage_info()
        next_num = f"{int(max_num) + 1:03d}"

        slug = slugify_name(args.name)
        existing = check_stage_name_exists(slug)
        if existing:
            print(f"[!] 警告: 已存在包含 '{slug}' 的阶段: {existing}")
            print("[?] 若确认创建，请使用不同名称。")
            sys.exit(1)

        filename = f"stage-{next_num}-{slug}.md"
        filepath = os.path.join(cfg.stages_exec_dir, filename)

        if not os.path.exists(TEMPLATE_PATH):
            print(f"[!] 模板不存在: {TEMPLATE_PATH}")
            sys.exit(1)

        template = read_text(TEMPLATE_PATH)
        content = initialize_stage_content(template, next_num, args.name)
        write_text(filepath, content)

        # 新建阶段后，重建索引，并将新阶段设为唯一当前阶段
        rewrite_stages_index(current_stage=filename)

        update_heartbeat()
        print(f"[*] 初始化阶段: {filename}")

    elif args.cmd == "sync":
        sync_log(
            message=args.message,
            task_name=args.task_name,
            status=args.status,
            next_action=args.next_action,
            blocked_by=args.blocked_by,
            file_target=args.file,
        )

    elif args.cmd == "summary":
        if args.stage:
            if not args.name or not args.goal or not args.audit or not args.debt:
                print("[!] --stage 模式下必须同时提供 --name --goal --audit --debt")
                sys.exit(1)
            append_stage_summary(
                name=args.name,
                milestone_goal=args.goal,
                core_results=args.result or [],
                change_audit=args.audit,
                tech_debt=args.debt,
                file_target=args.file,
            )
        else:
            if not args.text:
                print("[!] 非 --stage 模式下必须提供 text")
                sys.exit(1)
            update_session_summary(args.text)

    elif args.cmd == "intake":
        intake_backlog(args.keyword, dry_run=args.dry_run, file_target=args.file)

    elif args.cmd == "bootstrap":
        bootstrap()

    elif args.cmd == "status":
        show_status(file_target=args.file)

    elif args.cmd == "validate":
        filename, filepath = resolve_stage_file(args.file)
        if not filename or not filepath:
            print("[!] 当前没有可操作的阶段文件。")
            sys.exit(1)
        errors, warns = validate_stage_document(filepath)
        if not errors and not warns:
            print(f"[OK] 校验通过: {filename}")
        else:
            print(f"[CHECK] {filename}")
            for e in errors:
                print(f"  [ERROR] {e}")
            for w in warns:
                print(f"  [WARN]  {w}")
            if errors:
                sys.exit(1)

    elif args.cmd == "done":
        archive_stage(force=args.force, dry_run=args.dry_run, file_target=args.file)

    sys.exit(0)


if __name__ == "__main__":
    main()
