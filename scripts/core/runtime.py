#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Stage-Manager 运行时能力：路径、IO、输出、环境探测与写锁。"""

import contextlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


SESSION_MAX_ENTRIES = 20
VERSION = "1.1.0"
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR = os.path.dirname(PACKAGE_DIR)
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATE_PATH = os.path.join(SKILL_DIR, "references", "stage_template.md")
LOCK_FILENAME = ".stage-manager.lock"

ALLOWED_STAGE_STATUS = {"PLANNING", "IN_PROGRESS", "TESTING", "COMPLETED", "ARCHIVED"}
ALLOWED_LOG_STATUS = {"已完成", "进行中", "阻塞"}
ALLOWED_EXECUTOR = {"human", "agent", "sub_agent"}
ALLOWED_VERIFY_BY = {"task_completion", "evidence_review", "metric_threshold", "artifact_presence"}

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
class PathConfig:
    """保存 stage-manager 运行期涉及的所有派生路径。"""

    root_dir: str = ""
    asset_root: str = ""
    backlog_file: str = ""
    stages_index: str = ""
    adr_index: str = ""
    session_file: str = ""
    stages_exec_dir: str = ""
    archive_exec_dir: str = ""

    def configure(self, project_root: str):
        """根据项目根目录刷新运行期路径配置，不执行文件读写。"""
        self.root_dir = os.path.abspath(project_root)
        self.asset_root = os.path.join(self.root_dir, ".stages")
        self.backlog_file = os.path.join(self.asset_root, "BACKLOGS.md")
        self.stages_index = os.path.join(self.asset_root, "STAGES.md")
        self.adr_index = os.path.join(self.asset_root, "ADRS.md")
        self.session_file = os.path.join(self.asset_root, "STAGE_SESSIONS.md")
        self.stages_exec_dir = os.path.join(self.asset_root, "stages")
        self.archive_exec_dir = os.path.join(self.asset_root, "archive", "stages")


@dataclass
class OutputCtx:
    """保存 JSON 输出模式及其累积载荷。"""

    json_mode: bool = False
    data: Dict[str, Any] = field(default_factory=dict)


cfg = PathConfig()
_out = OutputCtx()


def emit(key: str, value: Any):
    """在 JSON 模式下累积一个输出字段，不直接打印。"""
    if _out.json_mode:
        _out.data[key] = value


def info(msg: str):
    """输出用户消息；JSON 模式下改为追加到 `messages`。"""
    if _out.json_mode:
        _out.data.setdefault("messages", []).append(msg)
    else:
        print(msg)


def flush_json():
    """将 JSON 模式下累积的结果一次性打印出来。"""
    if _out.json_mode:
        print(json.dumps(_out.data, ensure_ascii=False, indent=2))


def now_date() -> str:
    """返回当前日期，格式为 YYYY-MM-DD。"""
    return datetime.now().strftime("%Y-%m-%d")


def now_datetime() -> str:
    """返回当前时间，格式为 YYYY-MM-DD HH:MM。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def read_text(path: str) -> str:
    """读取 UTF-8 文本文件；文件不存在时返回空串。"""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path: str, content: str):
    """以临时文件替换方式写入文本，避免半写入损坏目标文件。"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(tmp, path)


def _lock_path() -> str:
    """返回当前项目的 stage 写锁文件路径。"""
    return os.path.join(cfg.asset_root, LOCK_FILENAME)


def _lock_payload(command: str) -> Dict[str, Any]:
    """生成写锁元数据，供冲突提示和僵尸锁清理复用。"""
    return {
        "pid": os.getpid(),
        "user": get_sys_user(),
        "command": command,
        "cwd": os.getcwd(),
        "started_at": now_datetime(),
    }


def _read_lock_payload(path: str) -> Dict[str, Any]:
    """读取写锁元数据；解析失败时返回空字典。"""
    try:
        raw = read_text(path).strip()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def _pid_is_alive(pid: Any) -> bool:
    """判断给定 PID 是否仍然存活。"""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _format_lock_holder(meta: Dict[str, Any]) -> str:
    """将锁元数据格式化为用户可读文本。"""
    parts = []
    if meta.get("user"):
        parts.append(f"user={meta['user']}")
    if meta.get("pid"):
        parts.append(f"pid={meta['pid']}")
    if meta.get("command"):
        parts.append(f"cmd={meta['command']}")
    if meta.get("started_at"):
        parts.append(f"started={meta['started_at']}")
    return ", ".join(parts) if parts else "unknown holder"


@contextlib.contextmanager
def write_lock(command: str):
    """获取单写者锁，保证同一时刻仅有一个 stage 写命令运行。"""
    ensure_structure()
    path = _lock_path()
    meta = _lock_payload(command)
    payload = json.dumps(meta, ensure_ascii=False, indent=2)
    acquired = False

    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            acquired = True
            break
        except FileExistsError:
            existing = _read_lock_payload(path)
            if existing.get("pid") == os.getpid():
                acquired = True
                break
            if not _pid_is_alive(existing.get("pid")):
                try:
                    os.remove(path)
                    continue
                except FileNotFoundError:
                    continue
            holder = _format_lock_holder(existing)
            raise RuntimeError(
                f"[BUSY] 检测到另一个 stage 写命令正在运行：{holder}。"
                " 请等待其完成，或确认异常退出后重试。"
            )

    if not acquired:
        raise RuntimeError("[BUSY] stage 写锁获取失败，请稍后重试。")

    try:
        yield
    finally:
        current = _read_lock_payload(path)
        if current.get("pid") == os.getpid():
            try:
                os.remove(path)
            except FileNotFoundError:
                pass


def discover_project_root(root_override: str | None = None) -> str:
    """探测项目根目录，优先使用显式参数，再回退环境变量与向上搜索。"""
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
    """返回当前 Git 短提交号，失败时回退到 local-env。"""
    try:
        short_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return f"git@{short_hash}"
    except Exception:
        return "local-env"


def get_sys_user() -> str:
    """返回当前系统用户名。"""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def slugify_name(name: str) -> str:
    """将阶段名称转换为可用于文件名的 slug。"""
    slug = re.sub(r"[^a-z0-9\-_.]+", "-", re.sub(r"\s+", "-", name.strip().lower()))
    return re.sub(r"-{2,}", "-", slug).strip("-") or "unnamed-stage"


def ensure_structure():
    """确保 `.stages` 目录树和基础索引文件存在，缺失时自动补齐。"""
    for directory in [cfg.asset_root, cfg.stages_exec_dir, cfg.archive_exec_dir]:
        os.makedirs(directory, exist_ok=True)

    defaults = [
        (
            cfg.stages_index,
            lambda: (
                STRINGS["stages_index_head"] + "\n---\n\n## 快速状态\n"
                f"- [HEARTBEAT] Init\n- [LAST_SESSION] 暂无记录\n"
                f"- 最近同步: {now_datetime()} | 用户: {get_sys_user()} | Version: {get_git_info()}\n"
            ),
        ),
        (
            cfg.adr_index,
            lambda: STRINGS["adrs_head"] + f"\n---\n\n## 统计信息\n- 总计决策: 0\n- 最近更新: {now_datetime()}\n",
        ),
        (
            cfg.session_file,
            lambda: STRINGS["sessions_head"] + "\n---\n\n## 最近记录\n- 暂无活动记录\n",
        ),
        (cfg.backlog_file, lambda: STRINGS["backlogs_head"]),
    ]
    for path, content_fn in defaults:
        if not os.path.exists(path):
            write_text(path, content_fn())
