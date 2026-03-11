#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Stage-Manager: 项目生命周期管理脚本
功能：标题模糊匹配、ADRS ID、DoD 硬门禁、Backlog 认领、任务智能路由。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

# --- 核心路径配置 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
TEMPLATE_PATH = os.path.join(SKILL_DIR, "references", "stage_template.md")
OVERRIDE_PATH = os.path.join(SKILL_DIR, "SKILL.override.md")

# 运行时路径 (.stages/)
ROOT_DIR = ""
ASSET_ROOT = ""
BACKLOG_FILE = ""
STAGES_INDEX = ""
ADR_INDEX = ""
SESSION_FILE = ""
STAGES_EXEC_DIR = ""
ARCHIVE_EXEC_DIR = ""

# --- 资源池 ---
STRINGS = {
    "stages_index_head": "# Stages Index\n\n> 此文件由 stage-manager 自动维护。所有资产位于 .stages/ 目录下。\n\n---\n\n## 阶段清单\n",
    "adrs_head": "# Architectural Decision Records (ADRS)\n\n---\n\n## 决策目录\n",
    "sessions_head": "# Stage Session Logs (Compressed)\n\n---\n\n## 会话摘要\n",
    "backlogs_head": "# 项目待办清单 (Backlogs)\n\n## [TECH_DEBT] 技术债务\n\n## [ROADMAP] 路线图\n",
    "init_success": "[*] 成功初始化阶段:",
    "archive_success": "[OK] 阶段已结项并归档。",
    "last_sync": "最近同步",
    "user": "用户",
    "stats_total": "总计决策",
    "stats_update": "最近更新",
    "heartbeat_done": "已完成",
    "heartbeat_active": "运行中",
    "heartbeat_backlog": "待办项",
    "heartbeat_adrs": "决策数"
}

def discover_project_root(root_override=None):
    """探测项目根目录。"""
    if root_override: return os.path.abspath(root_override)
    env_root = os.environ.get("STAGE_MANAGER_ROOT")
    if env_root: return os.path.abspath(env_root)
    cwd = os.path.abspath(os.getcwd())
    probe = cwd
    while True:
        if os.path.isdir(os.path.join(probe, ".git")) or os.path.isdir(os.path.join(probe, ".stages")): return probe
        parent = os.path.dirname(probe);
        if parent == probe: return cwd
        probe = parent

def configure_paths(project_root):
    """初始化全局资产路径。"""
    global ROOT_DIR, ASSET_ROOT, BACKLOG_FILE, STAGES_INDEX, ADR_INDEX, SESSION_FILE, STAGES_EXEC_DIR, ARCHIVE_EXEC_DIR
    ROOT_DIR = os.path.abspath(project_root)
    ASSET_ROOT = os.path.join(ROOT_DIR, ".stages")
    BACKLOG_FILE = os.path.join(ASSET_ROOT, "BACKLOGS.md")
    STAGES_INDEX = os.path.join(ASSET_ROOT, "STAGES.md")
    ADR_INDEX = os.path.join(ASSET_ROOT, "ADRS.md")
    SESSION_FILE = os.path.join(ASSET_ROOT, "STAGE_SESSIONS.md")
    STAGES_EXEC_DIR = os.path.join(ASSET_ROOT, "stages")
    ARCHIVE_EXEC_DIR = os.path.join(ASSET_ROOT, "archive", "stages")

def get_git_info():
    """获取 Git Hash。"""
    try:
        devnull = subprocess.DEVNULL
        git_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], stderr=devnull).decode().strip()
        return f"git@{git_hash}"
    except: return "local-env"

def get_sys_user():
    """获取执行用户。"""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

def ensure_structure():
    """确保 .stages/ 资产结构完整。"""
    for d in [ASSET_ROOT, STAGES_EXEC_DIR, ARCHIVE_EXEC_DIR]: os.makedirs(d, exist_ok=True)
    if not os.path.exists(STAGES_INDEX):
        with open(STAGES_INDEX, 'w', encoding='utf-8') as f:
            f.write(STRINGS["stages_index_head"] + "\n---\n\n## 快速状态\n- [HEARTBEAT] Init\n- [LAST_SESSION] 暂无记录\n")
    if not os.path.exists(ADR_INDEX):
        with open(ADR_INDEX, 'w', encoding='utf-8') as f:
            f.write(STRINGS["adrs_head"] + "\n---\n\n## 统计信息\n")
    if not os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, 'w', encoding='utf-8') as f:
            f.write(STRINGS["sessions_head"] + "\n---\n\n## 最近记录\n- 暂无活动记录\n")
    if not os.path.exists(BACKLOG_FILE):
        with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
            f.write(STRINGS["backlogs_head"])

def count_adrs_from_index():
    """统计 ADRS 数量。"""
    if not os.path.exists(ADR_INDEX): return 0
    with open(ADR_INDEX, 'r', encoding='utf-8') as f:
        return len(re.findall(r'\[ADRS-\d+\]', f.read()))

def update_adr_index(clean_msg, stage_file, is_archive=False):
    """更新 ADRS 中央索引。"""
    ensure_structure()
    with open(ADR_INDEX, 'r', encoding='utf-8') as f: lines = f.readlines()
    current_count = count_adrs_from_index(); adr_id = f"ADRS-{current_count + 1:03d}"
    path_prefix = ".stages/archive/stages/" if is_archive else ".stages/stages/"
    new_entry = f"{current_count + 1}. [{adr_id}] {clean_msg} ({path_prefix}{stage_file})\n"
    insert_idx = -1
    for i, line in enumerate(lines):
        if "决策目录" in line: insert_idx = i + 1; break
    if insert_idx != -1: lines.insert(insert_idx + current_count, new_entry)
    for i, line in enumerate(lines):
        if "总计决策" in line: lines[i] = f"- 总计决策: {current_count + 1}\n"
        if "最近更新" in line: lines[i] = f"- 最近更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    with open(ADR_INDEX, 'w', encoding='utf-8') as f: f.writelines(lines)
    return adr_id

def update_heartbeat():
    """更新看板元数据。"""
    ensure_structure()
    stats = get_project_stats(); last_session = get_last_session_text()
    now = datetime.now().strftime("%Y-%m-%d %H:%M"); user = get_sys_user(); ver = get_git_info()
    with open(STAGES_INDEX, 'r', encoding='utf-8') as f: lines = f.readlines()
    for i, line in enumerate(lines):
        if "[HEARTBEAT]" in line: lines[i] = f"- [HEARTBEAT] {stats}\n"
        if "[LAST_SESSION]" in line: lines[i] = f"- [LAST_SESSION] {last_session}\n"
        if "最近同步" in line: lines[i] = f"- 最近同步: {now} | 用户: {user} | Version: {ver}\n"
    with open(STAGES_INDEX, 'w', encoding='utf-8') as f: f.writelines(lines)

def get_last_session_text():
    """获取最后会话快照。"""
    if not os.path.exists(SESSION_FILE): return "暂无记录"
    with open(SESSION_FILE, 'r', encoding='utf-8') as f:
        match = re.search(r'- \*\*会话快照\*\*: (.*?)\n', f.read())
    return match.group(1).strip() if match else "暂无记录"

def update_session_summary(text):
    """保存会话压缩快照。"""
    ensure_structure()
    clean_text = text.replace("**", "").replace("- ", "").replace("\n", " ").strip()
    active_file, _ = get_latest_stage_info()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(SESSION_FILE, 'r', encoding='utf-8') as f: lines = f.readlines()
    new_entry = f"### [{now}] Stage: {active_file or 'Global'}\n- **会话快照**: {clean_text}\n"
    insert_idx = -1
    for i, line in enumerate(lines):
        if "会话摘要" in line: insert_idx = i + 1; break
    if insert_idx != -1: lines.insert(insert_idx + 1, new_entry + "\n")
    for i, line in enumerate(lines):
        if line.startswith("- 最近记录") or line.startswith("- 暂无记录"):
            lines[i] = f"- 最近记录: [{now}] {clean_text[:60]}...\n"; break
    with open(SESSION_FILE, 'w', encoding='utf-8') as f: f.writelines(lines)
    update_heartbeat()

def get_latest_stage_info():
    """解析看板索引以定位当前的活动阶段文件。支持两位和三位编号。"""
    ensure_structure()
    if not os.path.exists(STAGES_INDEX): return None, "000"
    with open(STAGES_INDEX, 'r', encoding='utf-8') as f: content = f.read()
    active_match = re.search(r'`.stages/stages/(stage-(\d+)-.*?.md)`（当前阶段）', content)
    all_nums = [int(n) for n in re.findall(r'stage-(\d+)-', content)]
    return (active_match.group(1) if active_match else None), f"{max(all_nums) if all_nums else 0:03d}"


def calculate_progress(filepath):
    """计算 4/5 章节进度。"""
    if not os.path.exists(filepath): return 0
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
    sections = re.findall(r'## [45]\..*?(?=##|$)', content, re.S)
    all_tasks = []
    for s in sections: all_tasks.extend(re.findall(r'- \[( |x|X)\]', s))
    return int((sum(1 for t in all_tasks if t.lower() == 'x') / len(all_tasks)) * 100) if all_tasks else 0

def check_dod_completed(filepath):
    """
    DoD 验收硬门禁：检查 ## 5. 验收标准 章节的所有任务是否已勾选。
    """
    if not os.path.exists(filepath): return True
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
    dod_section = re.search(r'## 5\..*?(?=##|$)', content, re.S)
    if not dod_section: return True # 无验收标准章节则跳过
    pending_dod = re.findall(r'- \[ \].*', dod_section.group())
    return len(pending_dod) == 0, pending_dod

def intake_backlog(keyword):
    """
    Backlog 认领机制：从 BACKLOGS.md 中提取含关键字的任务并载入活跃阶段。
    """
    active_file, _ = get_latest_stage_info()
    if not active_file: print("[!] 错误：当前没有活跃阶段可以认领任务。"); return False

    with open(BACKLOG_FILE, 'r', encoding='utf-8') as f: lines = f.readlines()

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

    # 回写 BACKLOGS.md 之前清理空标题
    full_content = "".join(remaining_lines)
    # 正则逻辑：匹配 ### 标题，如果其下方直接跟随另一个标题或文件末尾（忽略空白），则视为冗余
    full_content = re.sub(r'### 来自 .*? \(\d{4}-\d{2}-\d{2}\)\n\s*(?=###|##|$)', '', full_content, flags=re.S)
    
    with open(BACKLOG_FILE, 'w', encoding='utf-8') as f:
        f.write(full_content)

    # 注入活跃阶段文档的 ## 4. 任务拆解
    filepath = os.path.join(STAGES_EXEC_DIR, active_file)
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read()

    new_task_block = "\n".join(extracted_tasks) + "\n"
    content = re.sub(r'(## 4\..*?\n)', r'\1' + new_task_block, content, 1)

    with open(filepath, 'w', encoding='utf-8') as f: f.write(content)
    print(f"[OK] 已从 Backlog 认领 {len(extracted_tasks)} 个任务并载入 {active_file}。")
    return True

def route_backlog(tasks, stage_file, category_marker):
    """任务分流逻辑。"""
    if not tasks: return
    with open(BACKLOG_FILE, 'r', encoding='utf-8') as f: lines = f.readlines()
    now = datetime.now().strftime("%Y-%m-%d")
    source_label = "非范围条目" if category_marker == "[ROADMAP]" else "溢出与未完成任务"
    header = f"### 来自 {stage_file} 的{source_label} ({now})\n"
    insert_idx = -1
    for i, line in enumerate(lines):
        if category_marker in line: insert_idx = i + 1; break
    if insert_idx != -1:
        new_content = [header] + [f"{t}\n" for t in tasks] + ["\n"]
        for item in reversed(new_content): lines.insert(insert_idx, item)
    with open(BACKLOG_FILE, 'w', encoding='utf-8') as f: f.writelines(lines)

def sync_log(message):
    """同步进展。"""
    active_file, _ = get_latest_stage_info()
    if not active_file: return False
    filepath = os.path.join(STAGES_EXEC_DIR, active_file); now = datetime.now().strftime("%Y-%m-%d %H:%M")
    user = get_sys_user(); ver = get_git_info()
    with open(filepath, 'r', encoding='utf-8') as f: content = f.read()
    if message.startswith("[ADR]"):
        clean_msg = message[5:].strip(); adr_id = update_adr_index(clean_msg, active_file)
        adr_entry = f"\n- **决策点**: [{adr_id}] {clean_msg}\n- **背景/动机**: (请立即补全)\n- **结论**: (请立即补全)\n"
        content = re.sub(r'(## 8\..*?\n)', r'\1' + adr_entry, content, 1)
        print(f"[!] {adr_id} 存根已创建，请立即完善背景。")
    log_entry = f"\n### [{now}] 自动同步更新 | 用户: {user} | Ver: {ver}\n- {message}\n"
    content = re.sub(r'(## 7\..*?\n)', r'\1' + log_entry, content, 1) if re.search(r'## 7\.', content) else content + log_entry
    with open(filepath, 'w', encoding='utf-8') as f: f.write(content)
    update_heartbeat(); return True

def get_project_stats():
    """获取统计指标。"""
    ensure_structure()
    done_c = len([f for f in os.listdir(ARCHIVE_EXEC_DIR) if f.endswith(".md")]) if os.path.exists(ARCHIVE_EXEC_DIR) else 0
    active_c = len([f for f in os.listdir(STAGES_EXEC_DIR) if f.endswith(".md")]) if os.path.exists(STAGES_EXEC_DIR) else 0
    backlog_c = sum(1 for l in open(BACKLOG_FILE, 'r', encoding='utf-8').readlines() if l.strip().startswith("- [ ]")) if os.path.exists(BACKLOG_FILE) else 0
    adr_c = count_adrs_from_index()
    return f"已完成: {done_c} | 活跃: {active_c} | 待办: {backlog_c} | 决策: {adr_c}"

def show_status():
    """展示看板。"""
    active, _ = get_latest_stage_info()
    print("\n" + "="*50 + f"\n [项目健康度] {get_project_stats()}\n" + "="*50)
    if active:
        p = calculate_progress(os.path.join(STAGES_EXEC_DIR, active))
        bar = "#" * int(p/5) + "-" * (20 - int(p/5))
        print(f" [活跃阶段] {active}\n [完成进度] [{bar}] {p}%")
    if os.path.exists(ADR_INDEX):
        print("\n [最近决策] (最近3条):")
        with open(ADR_INDEX, 'r', encoding='utf-8') as f:
            adrs = re.findall(r'^\d+\. (\[ADRS-\d+\].*?)$', f.read(), re.M)
            for a in adrs[-3:]: print(f"  * {a.strip()}")
    if os.path.exists(SESSION_FILE):
        print("\n [最近会话] (最近3条):")
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            sessions = re.findall(r'- \*\*会话快照\*\*: (.*?)\n', f.read())
            for s in sessions[:3]: print(f"  > {s[:80]}...")
    print("="*50 + "\n"); update_heartbeat(); return True

def archive_stage(force=False):
    """闭环归档（含 DoD 硬门禁）。"""
    active_file, _ = get_latest_stage_info()
    if not active_file: return False
    src = os.path.join(STAGES_EXEC_DIR, active_file); progress = calculate_progress(src)

    # DoD 硬门禁检查
    dod_ok, pending_dod = check_dod_completed(src)
    if not dod_ok and not force:
        print(f"\n[!] 归档拒绝：## 5. 验收标准 (DoD) 未能全量通过。")
        for dod in pending_dod: print(f"  {dod.strip()}")
        print("\n[?] 请先完成上述验收项。若需强制归档，请询问用户后使用: done --force")
        return False

    if progress < 100 and not force:
        print(f"\n[!] 进度 {progress}% 未达标。强制归档请使用: done --force")
        return False

    with open(src, 'r', encoding='utf-8') as f: content = f.read()
    oos_match = re.search(r'## 3\..*?(?=##|$)', content, re.S)
    if oos_match: route_backlog(re.findall(r'- \[ \].*', oos_match.group()), active_file, "[ROADMAP]")
    breakdown_match = re.search(r'## 4\..*?(?=##|$)', content, re.S)
    if breakdown_match: route_backlog(re.findall(r'- \[ \].*', breakdown_match.group()), active_file, "[TECH_DEBT]")
    summary_match = re.search(r'## 9\..*?\n(.*?)(?=##|$)', content, re.S)
    summary = " ".join([l.strip() for l in summary_match.group(1).split('\n') if l.strip() and not l.strip().startswith('>')][:100]) if summary_match else "N/A"

    status_tag = "[DONE] | [ARCHIVED]" if progress >= 100 else "[IN_PROGRESS] | [ARCHIVED]"
    content = re.sub(r'- 阶段状态: .*', f'- 阶段状态: {status_tag}', content)
    with open(src, 'w', encoding='utf-8') as f: f.write(content)
    shutil.move(src, os.path.join(ARCHIVE_EXEC_DIR, active_file))
    with open(STAGES_INDEX, 'r', encoding='utf-8') as f: lines = f.readlines()
    with open(STAGES_INDEX, 'w', encoding='utf-8') as f:
        for line in lines:
            if active_file in line:
                line = line.replace(".stages/stages/", ".stages/archive/stages/").replace("（当前阶段）", f"（已归档）\n   > {summary}\n")
            f.write(line)
    update_session_summary(f"[归档自动化] 阶段 {active_file} 已结项: {summary}")
    print("[OK] 归档完成。"); return True

def main():
    """CLI 入口点，解析命令并执行相应逻辑。"""
    # 提前解析 --root 以配置路径环境
    base_parser = argparse.ArgumentParser(add_help=False)
    base_parser.add_argument("--root", help="指定项目根目录")
    temp_args, _ = base_parser.parse_known_args()
    configure_paths(discover_project_root(temp_args.root))

    # 主解析器定义
    parser = argparse.ArgumentParser(
        description="Stage-Manager: 工业级项目生命周期自动化管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例用法:
  python3 stage_manager.py init "feature-auth"       # 开启新阶段
  python3 stage_manager.py sync "实现登录逻辑"       # 同步进展
  python3 stage_manager.py sync "[ADR] 使用 JWT"     # 同步决策并生成 ID
  python3 stage_manager.py intake "api"              # 从 Backlog 认领含 'api' 的任务
  python3 stage_manager.py summary "会话阶段性总结"  # 存档记忆快照
  python3 stage_manager.py bootstrap                 # 恢复会话上下文
  python3 stage_manager.py status                    # 查看全局看板
  python3 stage_manager.py done                      # 结项归档 (DoD 检查)
        """
    )
    parser.add_argument("--root", help="指定项目根目录")
    subparsers = parser.add_subparsers(dest="cmd", title="子命令清单", required=True)

    # init 子命令
    init_p = subparsers.add_parser("init", help="初始化新阶段文档并更新看板")
    init_p.add_argument("name", help="阶段简短名称 (例如: user-auth)")

    # sync 子命令
    sync_p = subparsers.add_parser("sync", help="向当前阶段同步进展记录")
    sync_p.add_argument("message", help="进展描述文字；使用 [ADR] 前缀可自动同步至决策索引")

    # summary 子命令
    sum_p = subparsers.add_parser("summary", help="保存本次会话的高密度压缩快照")
    sum_p.add_argument("text", help="会话快照内容")

    # intake 子命令
    int_p = subparsers.add_parser("intake", help="从 BACKLOGS.md 中认领任务至当前阶段")
    int_p.add_argument("keyword", help="用于匹配 Backlog 任务的关键字")

    # bootstrap 子命令
    subparsers.add_parser("bootstrap", help="会话启动引导，加载最近快照以恢复记忆锚点")

    # status 子命令
    subparsers.add_parser("status", help="输出可视化健康看板，含最近决策、快照及项目指标")

    # done 子命令
    done_p = subparsers.add_parser("done", help="闭环归档当前阶段 (触发任务分流与 DoD 检查)")
    done_p.add_argument("--force", action="store_true", help="忽略未完成任务，强制执行归档操作")

    args = parser.parse_args()

    if args.cmd == "init":
        _, max_num = get_latest_stage_info(); next_num = f"{int(max_num) + 1:03d}"
        filename = f"stage-{next_num}-{args.name}.md"; filepath = os.path.join(STAGES_EXEC_DIR, filename)
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            c = f.read().replace("XXX", next_num).replace("<阶段简短名称>", args.name).replace("YYYY-MM-DD", datetime.now().strftime("%Y-%m-%d"))
        with open(filepath, 'w', encoding='utf-8') as f: f.write(c)
        with open(STAGES_INDEX, 'r', encoding='utf-8') as f: lines = f.readlines()
        for i, line in enumerate(lines):
            if "阶段清单" in line: lines.insert(i + 1, f"1. `.stages/stages/{filename}`（当前阶段）\n"); break
        with open(STAGES_INDEX, 'w', encoding='utf-8') as f: f.writelines(lines)
        update_heartbeat(); print(f"[*] 初始化阶段: {filename}")
    elif args.cmd == "sync": sync_log(args.message)
    elif args.cmd == "summary": update_session_summary(args.text)
    elif args.cmd == "intake": intake_backlog(args.keyword)
    elif args.cmd == "bootstrap": bootstrap()
    elif args.cmd == "done": archive_stage(args.force)
    elif args.cmd == "status": show_status()
    sys.exit(0)

if __name__ == "__main__": main()
