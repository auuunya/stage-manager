#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stage-Manager: 项目生命周期管理脚本
功能：自动化处理阶段初始化、状态精准同步、进度统计及归档。
"""
import os
import re
import shutil
import sys
import argparse
from datetime import datetime

# --- 核心配置：自适应路径 ---
# 脚本位于 stage-manager/scripts/
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 核心 Skill 根目录: stage-manager/
SKILL_DIR = os.path.dirname(SCRIPT_DIR)

TEMPLATE_PATH = os.path.join(SKILL_DIR, "references", "stage_template.md")

# 运行时路径（根据目标项目根目录动态计算）
ROOT_DIR = ""
BACKLOG_FILE = ""
STAGES_INDEX = ""
STAGES_EXEC_DIR = ""
ARCHIVE_EXEC_DIR = ""


def discover_project_root(root_override=None):
    """优先使用 --root 或环境变量；否则基于当前目录自动推断项目根目录。"""
    if root_override:
        return os.path.abspath(root_override)

    env_root = os.environ.get("STAGE_MANAGER_ROOT")
    if env_root:
        return os.path.abspath(env_root)

    cwd = os.path.abspath(os.getcwd())
    probe = cwd
    while True:
        if os.path.isdir(os.path.join(probe, ".git")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return cwd
        probe = parent


def configure_paths(project_root):
    """基于项目根目录配置运行时路径。"""
    global ROOT_DIR, BACKLOG_FILE, STAGES_INDEX, STAGES_EXEC_DIR, ARCHIVE_EXEC_DIR

    ROOT_DIR = os.path.abspath(project_root)
    BACKLOG_FILE = os.path.join(ROOT_DIR, "BACKLOG.md")
    STAGES_INDEX = os.path.join(ROOT_DIR, "STAGES.md")
    STAGES_EXEC_DIR = os.path.join(ROOT_DIR, "stages")
    ARCHIVE_EXEC_DIR = os.path.join(ROOT_DIR, "archive", "stages")

def ensure_structure():
    """初始化基础环境与看板骨架"""
    for d in [STAGES_EXEC_DIR, ARCHIVE_EXEC_DIR]:
        os.makedirs(d, exist_ok=True)

    # 如果 STAGES.md 不存在，生成标准开源看板模板
    if not os.path.exists(STAGES_INDEX):
        with open(STAGES_INDEX, 'w', encoding='utf-8') as f:
            f.write("# Stages Index\n\n")
            f.write("> 当前项目生命周期概览。此文件由 `stage-manager` 自动维护。\n\n")
            f.write("--- \n\n")
            f.write("## 阶段清单 (Stage Index)\n") # 关键锚点：新阶段将插入在此行下方
            f.write("\n--- \n\n")
            f.write("## 快速状态\n")
            f.write(f"- **最近同步**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    if not os.path.exists(BACKLOG_FILE):
        with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
            f.write("# 项目待办清单 (Backlog)\n\n")
            f.write("## 溢出任务池\n\n")
            f.write("_从已完成阶段自动迁移过来的任务会出现在这里。_\n")


def update_recent_sync():
    """更新 STAGES.md 的最近同步时间。"""
    ensure_structure()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(STAGES_INDEX, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    updated = False
    for idx, line in enumerate(lines):
        if line.startswith("- **最近同步**:"):
            lines[idx] = f"- **最近同步**: {now}\n"
            updated = True
            break

    if not updated:
        if lines and lines[-1].strip() != "":
            lines.append("\n")
        lines.append("## 快速状态\n")
        lines.append(f"- **最近同步**: {now}\n")

    with open(STAGES_INDEX, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def get_latest_stage_info():
    """解析 STAGES.md 获取当前活跃阶段"""
    ensure_structure()
    with open(STAGES_INDEX, 'r', encoding='utf-8') as f:
        content = f.read()

    active_match = re.search(r'`stages/(stage-(\d+)-.*?.md)`（当前阶段）', content)
    all_nums = [int(n) for n in re.findall(r'stage-(\d+)-', content)]
    max_num_val = max(all_nums) if all_nums else 0

    return (active_match.group(1) if active_match else None), f"{max_num_val:02d}"

def calculate_progress(filepath):
    """通过解析 Markdown 任务列表计算完成度"""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    tasks = re.findall(r'- \[( |x|X)\]', content)
    if not tasks: return 0
    done = sum(1 for t in tasks if t.lower() == 'x')
    return int((done / len(tasks)) * 100)

def init_stage(name):
    """初始化新阶段并在看板锚点位置精准插入"""
    ensure_structure()
    active_file, max_num = get_latest_stage_info()

    if active_file:
        print(f"错误：阶段 '{active_file}' 尚未完成，请先执行 done。")
        return False

    next_num = f"{int(max_num) + 1:02d}"
    filename = f"stage-{next_num}-{name}.md"
    filepath = os.path.join(STAGES_EXEC_DIR, filename)

    # 1. 填充模板并创建文档
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            content = f.read().replace("XX", next_num).replace("<阶段简短名称>", name).replace("YYYY-MM-DD", datetime.now().strftime("%Y-%m-%d"))
    else:
        content = f"# Stage-{next_num}: {name}\n\n开始日期: {datetime.now().strftime('%Y-%m-%d')}\n"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    # 2. 精准更新 STAGES.md 看板
    with open(STAGES_INDEX, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_line = f"{int(next_num)}. `stages/{filename}`（当前阶段）\n"

    # 查找插入点：在 "## 阶段清单" 标题之后寻找最后一个已有列表项或紧随其后的位置
    insert_idx = -1
    for i, line in enumerate(lines):
        if "## 阶段清单" in line:
            insert_idx = i + 1
            break

    if insert_idx != -1:
        # 如果标题下已经有列表，跳转到列表末尾插入，保持序号递增
        while insert_idx < len(lines) and (re.match(r'^\d+\.', lines[insert_idx].strip()) or lines[insert_idx].strip() == ""):
            if re.match(r'^\d+\.', lines[insert_idx].strip()):
                insert_idx += 1
            else:
                # 如果是空行且后面还有列表，继续向下，否则停止
                if insert_idx + 1 < len(lines) and re.match(r'^\d+\.', lines[insert_idx+1].strip()):
                    insert_idx += 1
                else:
                    break
        lines.insert(insert_idx, new_line)
    else:
        lines.append(new_line) # 防御性处理：找不到标题则追加到末尾

    with open(STAGES_INDEX, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    update_recent_sync()
    print(f"✨ 成功初始化阶段: {filename}")
    return True

def sync_log(message):
    """向活跃阶段追加进度日志"""
    active_file, _ = get_latest_stage_info()
    if not active_file:
        print("错误：没有活跃阶段可以同步日志。")
        return False

    filepath = os.path.join(STAGES_EXEC_DIR, active_file)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_entry = f"\n### [{now}] 自动同步更新\n- {message}\n"

    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(log_entry)
    update_recent_sync()
    print(f"📝 已向 {active_file} 追加进度记录。")
    return True

def archive_stage(force=False):
    """归档阶段，精准更新看板状态并迁移 Backlog"""
    active_file, _ = get_latest_stage_info()
    if not active_file:
        print("没有活跃阶段需要归档。")
        return False

    src = os.path.join(STAGES_EXEC_DIR, active_file)
    dst = os.path.join(ARCHIVE_EXEC_DIR, active_file)
    progress = calculate_progress(src)

    if progress < 100 and not force:
        print(f"错误：当前阶段完成度为 {progress}%，未达到 100%，拒绝归档。")
        print("如需强制归档，请使用: done --force")
        return False

    # 1. 迁移未完成任务
    with open(src, 'r', encoding='utf-8') as f:
        content = f.read()
    unfinished = re.findall(r'- \[ \].*', content)
    if unfinished:
        with open(BACKLOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n### 来自 {active_file} 的溢出任务 ({datetime.now().strftime('%Y-%m-%d')})\n" + "\n".join(unfinished) + "\n")
        print(f"发现未完成任务，已迁移至 BACKLOG.md")

    # 2. 物理归档
    shutil.move(src, dst)

    # 3. 精准更新 STAGES.md 中的路径和状态标记
    with open(STAGES_INDEX, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    with open(STAGES_INDEX, 'w', encoding='utf-8') as f:
        for line in lines:
            if f"stages/{active_file}" in line:
                line = line.replace(f"stages/{active_file}", f"archive/stages/{active_file}")
                line = line.replace("（当前阶段）", "（已归档）")
            f.write(line)

    update_recent_sync()
    print(f"阶段 {active_file} 已成功归档至 archive/stages/。")
    return True

def show_status():
    """显示当前活跃阶段与进度。"""
    active, _ = get_latest_stage_info()
    if active:
        progress = calculate_progress(os.path.join(STAGES_EXEC_DIR, active))
        bar = "█" * (progress // 5) + "░" * (20 - (progress // 5))
        print(f"当前阶段: {active}")
        print(f"进度: [{bar}] {progress}%")
        return True

    print("当前项目没有活跃阶段。")
    return True


def parse_args(argv):
    """解析命令行参数。"""
    root_override = None
    normalized_argv = []
    i = 0
    while i < len(argv):
        if argv[i] == "--root":
            if i + 1 >= len(argv):
                raise SystemExit("错误：--root 需要提供目录参数。")
            root_override = argv[i + 1]
            i += 2
            continue
        normalized_argv.append(argv[i])
        i += 1

    parser = argparse.ArgumentParser(
        description="Stage-Manager: 项目阶段生命周期自动化管理工具",
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    init_parser = subparsers.add_parser("init", help="初始化新阶段")
    init_parser.add_argument("name", nargs="?", default="new-stage", help="阶段名称")

    sync_parser = subparsers.add_parser("sync", help="同步阶段日志")
    sync_parser.add_argument("message", nargs="?", default="执行自动化任务", help="同步内容")

    done_parser = subparsers.add_parser("done", help="归档当前阶段")
    done_parser.add_argument("--force", action="store_true", help="完成度未达 100% 时强制归档")

    subparsers.add_parser("status", help="查看阶段状态")
    args = parser.parse_args(normalized_argv)
    args.root = root_override
    return args


def main():
    args = parse_args(sys.argv[1:])
    configure_paths(discover_project_root(args.root))

    if args.cmd == "init":
        success = init_stage(args.name)
    elif args.cmd == "sync":
        success = sync_log(args.message)
    elif args.cmd == "done":
        success = archive_stage(force=args.force)
    else:
        success = show_status()

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
