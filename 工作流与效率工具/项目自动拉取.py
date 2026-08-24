#!/usr/bin/env python3
"""
Git 项目拉取更新工具 (GUI) - 深度优化与多子模块精细化管理版

核心特性：
1. 安全第一：只读远端，只动本地。严格拦截任何 push / remote 修改 / config 等危险指令。
2. 高性能并发：
   - 支持多项目多线程并发拉取（可自定义并发线程数）。
   - 子模块支持 Git 原生 `--jobs <N>` 并行克隆与更新。
   - 子模块分支探测全面多线程并发加速。
3. 冲突与安全防护：
   - Safe 模式变基冲突自动回滚保护（自动 rebase --abort，绝不破坏本地工作区）。
   - 网络类命令智能自动重试（针对 GitHub/GitLab 偶发断流）。
4. 🌟 子模块精细化独立管理与可视化排除：
   - 每个子模块支持独立指定不同分支（如模块 A 用 develop，模块 B 用 main，模块 C 锁定 pinned）。
   - 表格内一键勾选包含/排除，无需手动打字输入路径。
   - 单子模块远端分支多线程并发探测与智能下拉选择。
   - 记录版本 (pinned) / 远端最新 (remote) / 独立分支 (branch) 灵活组合。
5. 现代化交互：
   - 随时安全「中止/停止」正在执行的任务。
   - 实时进度条、状态统计与当前任务展示。
   - 项目搜索与过滤、右键快捷菜单。
   - 彩色高亮执行日志（成功/警告/错误/命令上色）。
"""

import os
import re
import sys
import json
import time
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog

# Windows 下抑制每条命令弹出的控制台黑窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# 配置文件路径
_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".git_pull_tool.json")

# 禁止执行的危险/影响远端的子命令（严格安全拦截）
_FORBIDDEN = {"push", "remote", "config"}

_MODE_LABELS = {"safe": "安全", "stash": "暂存", "force": "强制"}
_MODE_ORDER = ["safe", "stash", "force"]

_SUB_TRACK_LABELS = {
    "default": "跟随全局",
    "pinned": "记录版本",
    "remote": "远端最新",
    "branch": "指定分支",
}
_SUB_TRACK_ORDER = ["pinned", "remote", "branch"]

# 项目配置中允许持久化的字段
_PROJECT_KEYS = (
    "enabled", "mode", "submodule", "sub_track", "sub_branch",
    "sub_overrides", "prune", "shallow", "auto_abort",
)

# 解析 `git submodule status --recursive` 的输出行
_SUB_STATUS_RE = re.compile(r"^[+\-U ]?\s*([0-9a-f]{7,40})\s+(.+?)(?:\s+\([^()]*\))?$")


def _default_project(path: str) -> dict:
    return {
        "path": path,
        "enabled": True,
        "mode": "safe",
        "submodule": True,
        "sub_track": "pinned",
        "sub_branch": "",
        "sub_overrides": {},  # { "rel_path": { "enabled": bool, "strategy": "default"|"pinned"|"remote"|"branch", "branch": str } }
        "prune": False,
        "shallow": False,
        "auto_abort": True,
    }


def _default_global_config() -> dict:
    return {
        "concurrency": 3,
        "submodule_jobs": 4,
        "retry_count": 1,
        "network_timeout": 120,
        "local_timeout": 30,
    }


def _parse_branches(text: str) -> list[str]:
    """把 "main, master" 解析为候选分支列表（按顺序尝试）。"""
    return [b for b in re.split(r"[,;\s]+", (text or "").strip()) if b]


def _submodule_desc(proj: dict) -> str:
    """子模块设置在表格里的简短描述。"""
    if not proj.get("submodule"):
        return "否"
    track = proj.get("sub_track", "pinned")
    overrides = proj.get("sub_overrides", {})
    excluded_count = sum(1 for v in overrides.values() if not v.get("enabled", True))
    custom_count = sum(
        1 for v in overrides.values()
        if v.get("enabled", True) and v.get("strategy") and v.get("strategy") != "default"
    )

    tags = []
    if excluded_count > 0:
        tags.append(f"排除{excluded_count}")
    if custom_count > 0:
        tags.append(f"定制{custom_count}")

    extra = f" ({', '.join(tags)})" if tags else ""

    if track == "branch":
        branches = _parse_branches(proj.get("sub_branch", ""))
        b_name = branches[0] if branches else "未填"
        return f"分支: {b_name}" + ("…" if len(branches) > 1 else "") + extra
    return _SUB_TRACK_LABELS.get(track, track) + extra


# ---------------- Git 只读探测与通用解析工具 ----------------


def _git_probe(cmd: list[str], cwd: str, timeout: int = 30) -> tuple[int, str]:
    """探测用的只读 git 调用：只取 stdout，不写执行日志，失败返回空串。"""
    if cmd and cmd[0] == "git" and len(cmd) > 1 and cmd[1] in _FORBIDDEN:
        return -1, ""
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, creationflags=_NO_WINDOW,
        )
        return r.returncode, (r.stdout or "").strip()
    except Exception:
        return -1, ""


def _submodule_details(repo_path: str) -> list[dict]:
    """
    返回仓库中所有子模块的详细状态列表：
    [{ "rel": "path/to/sub", "abs": "...", "sha": "...", "missing": bool, "head": str }]
    """
    result = []
    if not os.path.isdir(repo_path):
        return result
    rc, out = _git_probe(["git", "submodule", "status", "--recursive"], repo_path)
    if rc != 0:
        return result

    for line in out.splitlines():
        if not line.strip():
            continue
        m = _SUB_STATUS_RE.match(line)
        if not m:
            continue
        sha = m.group(1).strip()
        rel = m.group(2).strip()
        is_missing = line.startswith("-")
        abs_path = os.path.join(repo_path, rel.replace("/", os.sep))

        head_info = "未克隆" if is_missing else "HEAD(游离)"
        if not is_missing and os.path.isdir(abs_path):
            rc_h, br = _git_probe(["git", "rev-parse", "--abbrev-ref", "HEAD"], abs_path)
            if rc_h == 0 and br.strip() and br.strip() != "HEAD":
                head_info = br.strip()
            else:
                head_info = f"HEAD ({sha[:7]})"

        result.append({
            "rel": rel,
            "abs": abs_path,
            "sha": sha[:7],
            "missing": is_missing,
            "head": head_info,
        })
    return result


def _gitmodules_urls(path: str) -> dict[str, str]:
    """解析 .gitmodules，返回 {子模块路径: url}。"""
    f = os.path.join(path, ".gitmodules")
    if not os.path.isfile(f):
        return {}
    try:
        with open(f, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return {}
    blocks: list[dict] = []
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[submodule"):
            cur = {}
            blocks.append(cur)
        elif cur is not None and "=" in s and not s.startswith("#"):
            k, _, v = s.partition("=")
            cur[k.strip().lower()] = v.strip()
    return {b["path"]: b["url"] for b in blocks if b.get("path") and b.get("url")}


def _resolve_submodule_url(repo: str, url: str) -> str:
    """把 .gitmodules 里的相对 url（./ 或 ../）按父仓库 origin 解析为可用地址。"""
    if not (url.startswith("./") or url.startswith("../")):
        return url
    rc, base = _git_probe(["git", "ls-remote", "--get-url", "origin"], repo)
    base = base.strip()
    if rc != 0 or not base or base == "origin":
        return ""
    base = base.rstrip("/")
    while url.startswith("./") or url.startswith("../"):
        if url.startswith("./"):
            url = url[2:]
        else:
            url = url[3:]
            base = base.rsplit("/", 1)[0] if "/" in base else base
    return f"{base}/{url}" if url else base


def _branches_of(repo: str, from_remote: bool, url: str = "") -> list[str]:
    """列出分支：from_remote=True 走 ls-remote（联网、最新），否则读本地远程追踪分支。"""
    if from_remote or url:
        target = url or "origin"
        rc, out = _git_probe(["git", "ls-remote", "--heads", target], repo, timeout=30)
        if rc != 0:
            return []
        names = []
        for line in out.splitlines():
            if "refs/heads/" in line:
                names.append(line.split("refs/heads/", 1)[1].strip())
        return names
    rc, out = _git_probe(
        ["git", "for-each-ref", "--format=%(refname:lstrip=3)", "refs/remotes/origin"], repo
    )
    if rc != 0:
        return []
    return [b for b in (l.strip() for l in out.splitlines()) if b and b != "HEAD"]


def _probe_single_submodule_branches(repo_path: str, sub_info: dict, from_remote: bool, urls: dict) -> list[str]:
    """探测单个子模块的分支列表。"""
    rel = sub_info["rel"]
    if sub_info["missing"]:
        raw_url = urls.get(rel, "")
        url = _resolve_submodule_url(repo_path, raw_url) if raw_url else ""
        if from_remote and url:
            return _branches_of(repo_path, True, url)
        return []
    return _branches_of(sub_info["abs"], from_remote)


# ---------------- 单子模块独立配置对话框 ----------------


class SubmoduleItemDialog(tk.Toplevel):
    """设置单个子模块的专属更新策略与指定分支。"""

    def __init__(self, parent, rel_path: str, curr_ov: dict, available_branches: list[str], global_track: str, global_branch: str):
        super().__init__(parent)
        self.title(f"定制子模块 - {rel_path}")
        self.geometry("520x330")
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        self.rel_path = rel_path
        self.var_enabled = tk.BooleanVar(value=curr_ov.get("enabled", True))
        self.var_strat = tk.StringVar(value=curr_ov.get("strategy", "default"))
        self.var_branch = tk.StringVar(value=curr_ov.get("branch", ""))

        # 启用 / 排除 开关
        frm_en = ttk.LabelFrame(self, text="包含 / 排除", padding=10)
        frm_en.pack(fill="x", padx=14, pady=(12, 6))
        ttk.Checkbutton(
            frm_en, text=f"包含此子模块（勾选则参与更新，取消勾选则排除跳过）",
            variable=self.var_enabled, command=self._sync_state
        ).pack(anchor="w")

        # 独立策略选择
        self.frm_strat = ttk.LabelFrame(self, text="独立更新策略", padding=10)
        self.frm_strat.pack(fill="x", padx=14, pady=6)

        strat_options = [
            ("default", f"跟随全局默认设置（当前全局: {_SUB_TRACK_LABELS.get(global_track, global_track)}"
                        f"{f' -> {global_branch}' if global_track == 'branch' else ''}）"),
            ("pinned", "🔒 记录版本 (Pinned)：固定检出父仓库记录的 Commit 节点"),
            ("remote", "🌐 远端最新 (Remote)：根据 .gitmodules 配置跟踪最新"),
            ("branch", "🌿 独立指定分支：为此子模块单独选择/输入分支"),
        ]

        self._rbs = []
        for val, txt in strat_options:
            rb = ttk.Radiobutton(
                self.frm_strat, text=txt, variable=self.var_strat, value=val,
                command=self._sync_state
            )
            rb.pack(anchor="w", pady=2)
            self._rbs.append(rb)

        row_b = ttk.Frame(self.frm_strat)
        row_b.pack(fill="x", padx=(20, 0), pady=(4, 2))
        ttk.Label(row_b, text="目标分支:").pack(side="left")
        self.cbo_branch = ttk.Combobox(
            row_b, textvariable=self.var_branch, width=24, height=12,
            values=available_branches
        )
        self.cbo_branch.pack(side="left", padx=(6, 0))
        ttk.Label(row_b, text="(可下拉或直接输入)", foreground="#666666").pack(side="left", padx=4)

        # 按钮
        btns = ttk.Frame(self, padding=(14, 8, 14, 14))
        btns.pack(fill="x", side="bottom")
        ttk.Button(btns, text="确定", command=self._ok).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self._sync_state()

    def _sync_state(self):
        en = self.var_enabled.get()
        strat = self.var_strat.get()
        for rb in self._rbs:
            rb.config(state="normal" if en else "disabled")
        self.cbo_branch.config(state="normal" if (en and strat == "branch") else "disabled")

    def _ok(self):
        strat = self.var_strat.get()
        branch = self.var_branch.get().strip()
        if self.var_enabled.get() and strat == "branch" and not branch:
            messagebox.showwarning("提示", "选择独立指定分支时，请填写或选择分支名", parent=self)
            return

        self.result = {
            "enabled": self.var_enabled.get(),
            "strategy": strat,
            "branch": branch,
        }
        self.destroy()


# ---------------- 全局设置对话框 ----------------


class SettingsDialog(tk.Toplevel):
    """全局设置对话框。"""

    def __init__(self, parent, current_cfg: dict):
        super().__init__(parent)
        self.title("全局偏好设置")
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        self.var_concurrency = tk.IntVar(value=current_cfg.get("concurrency", 3))
        self.var_sub_jobs = tk.IntVar(value=current_cfg.get("submodule_jobs", 4))
        self.var_retry = tk.IntVar(value=current_cfg.get("retry_count", 1))
        self.var_net_timeout = tk.IntVar(value=current_cfg.get("network_timeout", 120))
        self.var_loc_timeout = tk.IntVar(value=current_cfg.get("local_timeout", 30))

        frm = ttk.LabelFrame(self, text="并发与加速", padding=12)
        frm.pack(fill="x", padx=14, pady=(12, 6))

        # 项目并发
        r1 = ttk.Frame(frm)
        r1.pack(fill="x", pady=4)
        ttk.Label(r1, text="项目并发更新线程数 (1~8):", width=26).pack(side="left")
        ttk.Spinbox(r1, from_=1, to=8, textvariable=self.var_concurrency, width=6).pack(side="left")
        ttk.Label(r1, text="（多项目同时拉取，默认 3）", foreground="#666666").pack(side="left", padx=6)

        # 子模块并发
        r2 = ttk.Frame(frm)
        r2.pack(fill="x", pady=4)
        ttk.Label(r2, text="子模块 Git 并行拉取 (-j):", width=26).pack(side="left")
        ttk.Spinbox(r2, from_=1, to=16, textvariable=self.var_sub_jobs, width=6).pack(side="left")
        ttk.Label(r2, text="（加速多子模块同步，默认 4）", foreground="#666666").pack(side="left", padx=6)

        frm_net = ttk.LabelFrame(self, text="网络容错与超时", padding=12)
        frm_net.pack(fill="x", padx=14, pady=6)

        r3 = ttk.Frame(frm_net)
        r3.pack(fill="x", pady=4)
        ttk.Label(r3, text="网络命令失败重试次数 (0~3):", width=26).pack(side="left")
        ttk.Spinbox(r3, from_=0, to=3, textvariable=self.var_retry, width=6).pack(side="left")
        ttk.Label(r3, text="（针对 GitHub/GitLab 偶发断流）", foreground="#666666").pack(side="left", padx=6)

        r4 = ttk.Frame(frm_net)
        r4.pack(fill="x", pady=4)
        ttk.Label(r4, text="网络拉取超时时间 (秒):", width=26).pack(side="left")
        ttk.Spinbox(r4, from_=30, to=600, textvariable=self.var_net_timeout, width=6).pack(side="left")

        r5 = ttk.Frame(frm_net)
        r5.pack(fill="x", pady=4)
        ttk.Label(r5, text="本地命令超时时间 (秒):", width=26).pack(side="left")
        ttk.Spinbox(r5, from_=10, to=120, textvariable=self.var_loc_timeout, width=6).pack(side="left")

        btns = ttk.Frame(self, padding=(14, 8, 14, 14))
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", command=self._ok).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _ok(self):
        self.result = {
            "concurrency": max(1, min(8, self.var_concurrency.get())),
            "submodule_jobs": max(1, min(16, self.var_sub_jobs.get())),
            "retry_count": max(0, min(3, self.var_retry.get())),
            "network_timeout": max(15, self.var_net_timeout.get()),
            "local_timeout": max(5, self.var_loc_timeout.get()),
        }
        self.destroy()


# ---------------- 项目选项编辑与子模块可视化管理对话框 ----------------


class EditDialog(tk.Toplevel):
    """编辑单/多个项目的更新选项与子模块精细化管理。"""

    def __init__(self, parent, init: dict, paths: list[str]):
        super().__init__(parent)
        count = len(paths)
        self.title("编辑更新与子模块配置" + (f"（{count} 个项目）" if count > 1 else ""))
        self.geometry("820x680")
        self.minsize(720, 580)
        self.result = None
        self._paths = list(paths)
        self._probing = False
        self.transient(parent)
        self.grab_set()

        # 项目属性绑定
        self.var_mode = tk.StringVar(value=init.get("mode", "safe"))
        self.var_sub = tk.BooleanVar(value=init.get("submodule", True))
        self.var_track = tk.StringVar(value=init.get("sub_track", "pinned"))
        self.var_branch = tk.StringVar(value=init.get("sub_branch", ""))
        self.var_prune = tk.BooleanVar(value=init.get("prune", False))
        self.var_shallow = tk.BooleanVar(value=init.get("shallow", False))
        self.var_auto_abort = tk.BooleanVar(value=init.get("auto_abort", True))

        # 子模块覆盖字典: { rel_path: { "enabled": bool, "strategy": str, "branch": str } }
        self.sub_overrides = dict(init.get("sub_overrides", {}))

        # 子模块状态与探测缓存: { rel_path: { "branches": [], "head": "", "missing": bool, ... } }
        self.sub_info_map = {}

        self._build_widgets()
        self._sync_state()

        # 加载并渲染子模块
        self._load_submodules_initial()

    def _build_widgets(self):
        # 1. 更新模式
        frm_mode = ttk.LabelFrame(self, text="更新模式", padding=8)
        frm_mode.pack(fill="x", padx=12, pady=(10, 4))
        mode_texts = {
            "safe": "安全更新（autostash + rebase，保留本地修改，冲突自动回滚保护）",
            "stash": "暂存更新（stash → 拉取 → 恢复）",
            "force": "强制更新（丢弃本地修改，与远端强行一致）",
        }
        for value in _MODE_ORDER:
            ttk.Radiobutton(frm_mode, text=mode_texts[value], variable=self.var_mode, value=value).pack(
                anchor="w", pady=1
            )

        # 2. 全局子模块默认策略
        frm_sub_global = ttk.LabelFrame(self, text="子模块全局默认策略", padding=8)
        frm_sub_global.pack(fill="x", padx=12, pady=4)

        self.chk_sub = ttk.Checkbutton(
            frm_sub_global, text="启用子模块更新（总开关）", variable=self.var_sub,
            command=self._sync_state,
        )
        self.chk_sub.pack(anchor="w")

        track_texts = {
            "pinned": "默认记录版本：检出父仓库记录的提交 (Pinned HEAD)",
            "remote": "默认远端最新：根据各子模块 .gitmodules 配置拉取 (--remote)",
            "branch": "默认指定分支：",
        }
        self._track_radios = []
        for value in _SUB_TRACK_ORDER:
            row = ttk.Frame(frm_sub_global)
            row.pack(fill="x", padx=(18, 0), pady=1)
            rb = ttk.Radiobutton(
                row, text=track_texts[value], variable=self.var_track,
                value=value, command=self._sync_state,
            )
            rb.pack(side="left")
            self._track_radios.append(rb)
            if value == "branch":
                self.cbo_global_branch = ttk.Combobox(
                    row, textvariable=self.var_branch, width=20, height=12, values=[]
                )
                self.cbo_global_branch.pack(side="left", padx=(4, 0))
                ttk.Label(row, text="（未单独指定分支的子模块将默认尝试此分支）", foreground="#666666").pack(side="left", padx=4)

        # 3. 子模块精细化管理表格
        frm_sub_table = ttk.LabelFrame(
            self,
            text="子模块精细化定制列表（点击「更新」列一键排除/包含；双击行设置单模块专属分支/策略）",
            padding=8
        )
        frm_sub_table.pack(fill="both", expand=True, padx=12, pady=4)

        # 表格
        table_wrap = ttk.Frame(frm_sub_table)
        table_wrap.pack(fill="both", expand=True)

        cols = ("enabled", "strategy", "head")
        self.tree_subs = ttk.Treeview(
            table_wrap, columns=cols, show="tree headings", height=6, selectmode="extended"
        )
        self.tree_subs.heading("#0", text="子模块路径")
        self.tree_subs.heading("enabled", text="更新/包含")
        self.tree_subs.heading("strategy", text="生效策略 / 目标分支")
        self.tree_subs.heading("head", text="当前本地 HEAD")

        self.tree_subs.column("#0", width=280, anchor="w")
        self.tree_subs.column("enabled", width=80, anchor="center", stretch=False)
        self.tree_subs.column("strategy", width=220, anchor="w")
        self.tree_subs.column("head", width=140, anchor="center", stretch=False)

        self.tree_subs.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree_subs.yview)
        sb.pack(side="left", fill="y")
        self.tree_subs.config(yscrollcommand=sb.set)

        self.tree_subs.bind("<Button-1>", self._on_sub_tree_click)
        self.tree_subs.bind("<Double-1>", self._on_sub_tree_double_click)

        # 子模块表格工具栏
        sub_tool_bar = ttk.Frame(frm_sub_table)
        sub_tool_bar.pack(fill="x", pady=(6, 0))

        self.btn_probe_subs = ttk.Button(
            sub_tool_bar, text="🔍 并发探测所有子模块远端分支",
            command=lambda: self._probe_all_submodules(from_remote=True)
        )
        self.btn_probe_subs.pack(side="left")

        ttk.Button(
            sub_tool_bar, text="✏ 设置选中子模块分支/策略...",
            command=self._on_edit_selected_sub
        ).pack(side="left", padx=6)

        ttk.Separator(sub_tool_bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(
            sub_tool_bar, text="全部包含(更新)",
            command=lambda: self._set_all_subs_enabled(True)
        ).pack(side="left")

        ttk.Button(
            sub_tool_bar, text="全部排除(跳过)",
            command=lambda: self._set_all_subs_enabled(False)
        ).pack(side="left", padx=4)

        ttk.Button(
            sub_tool_bar, text="重置为跟随全局",
            command=self._reset_all_subs_strategy
        ).pack(side="left")

        self.lbl_sub_status = ttk.Label(frm_sub_table, text="", foreground="#336699")
        self.lbl_sub_status.pack(anchor="w", pady=(4, 0))

        # 4. 高级选项
        frm_opt = ttk.LabelFrame(self, text="高级防护与优化选项", padding=8)
        frm_opt.pack(fill="x", padx=12, pady=4)

        ttk.Checkbutton(
            frm_opt, text="安全防护：Safe 模式下发生冲突自动 rebase --abort 并还原工作区（无损防护）",
            variable=self.var_auto_abort
        ).pack(anchor="w", pady=1)

        row_opt2 = ttk.Frame(frm_opt)
        row_opt2.pack(fill="x", pady=1)
        ttk.Checkbutton(
            row_opt2, text="清理无效远程追踪分支 (git fetch --prune)", variable=self.var_prune
        ).pack(side="left")
        ttk.Checkbutton(
            row_opt2, text="浅拉取加速 (git fetch / submodule update --depth 1)", variable=self.var_shallow
        ).pack(side="left", padx=16)

        # 底部按钮
        btns = ttk.Frame(self, padding=(12, 6, 12, 10))
        btns.pack(fill="x")
        ttk.Button(btns, text="确定", command=self._ok).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _sync_state(self):
        sub_on = self.var_sub.get()
        for rb in self._track_radios:
            rb.config(state="normal" if sub_on else "disabled")
        branch_on = sub_on and self.var_track.get() == "branch"
        self.cbo_global_branch.config(state="normal" if branch_on else "disabled")
        self._refresh_sub_tree()

    # ---------------- 子模块表格渲染与交互 ----------------

    def _load_submodules_initial(self):
        """打开界面时快速读取本地子模块信息并填充表格。"""
        all_subs = {}
        for path in self._paths:
            subs = _submodule_details(path)
            for s in subs:
                rel = s["rel"]
                if rel not in all_subs:
                    all_subs[rel] = {
                        "rel": rel,
                        "abs": s["abs"],
                        "head": s["head"],
                        "missing": s["missing"],
                        "branches": [],
                    }
        self.sub_info_map = all_subs
        self._refresh_sub_tree()
        # 初始异步探测本地分支（不联网，秒级完成）
        self._probe_all_submodules(from_remote=False)

    def _refresh_sub_tree(self):
        self.tree_subs.delete(*self.tree_subs.get_children())
        global_track = self.var_track.get()
        global_branch = self.var_branch.get().strip()

        for rel, info in self.sub_info_map.items():
            ov = self.sub_overrides.get(rel, {})
            is_enabled = ov.get("enabled", True)
            strat = ov.get("strategy", "default")
            spec_branch = ov.get("branch", "").strip()

            if not is_enabled:
                strat_desc = "⛔ [已排除] 跳过更新"
            elif strat == "default":
                if global_track == "branch":
                    b_txt = f"分支: {global_branch}" if global_branch else "分支(未填)"
                    strat_desc = f"跟随全局 ({b_txt})"
                else:
                    strat_desc = f"跟随全局 ({_SUB_TRACK_LABELS.get(global_track, global_track)})"
            elif strat == "pinned":
                strat_desc = "🔒 独立: 记录版本 (Pinned)"
            elif strat == "remote":
                strat_desc = "🌐 独立: 远端最新 (Remote)"
            elif strat == "branch":
                strat_desc = f"🌿 独立分支: {spec_branch}" if spec_branch else "🌿 独立分支 (未填写)"
            else:
                strat_desc = strat

            self.tree_subs.insert(
                "", "end", iid=rel, text=rel,
                values=(
                    "☑ 包含" if is_enabled else "☐ 排除",
                    strat_desc,
                    info.get("head", "-"),
                )
            )

        count = len(self.sub_info_map)
        excluded = sum(1 for ov in self.sub_overrides.values() if not ov.get("enabled", True))
        self.lbl_sub_status.config(
            text=f"共发现 {count} 个子模块" + (f"（已排除 {excluded} 个）" if excluded else "")
        )

    def _on_sub_tree_click(self, event):
        region = self.tree_subs.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree_subs.identify_column(event.x)
        row = self.tree_subs.identify_row(event.y)
        if col == "#1" and row:  # #1 是 enabled 列
            rel = row
            ov = self.sub_overrides.setdefault(rel, {"enabled": True, "strategy": "default", "branch": ""})
            ov["enabled"] = not ov.get("enabled", True)
            self._refresh_sub_tree()
            return "break"

    def _on_sub_tree_double_click(self, event):
        row = self.tree_subs.identify_row(event.y)
        if row:
            self._edit_submodule_item(row)
            return "break"

    def _on_edit_selected_sub(self):
        sel = self.tree_subs.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在列表中选中要配置的子模块", parent=self)
            return
        self._edit_submodule_item(sel[0])

    def _edit_submodule_item(self, rel: str):
        info = self.sub_info_map.get(rel, {})
        ov = self.sub_overrides.get(rel, {"enabled": True, "strategy": "default", "branch": ""})
        branches = info.get("branches", [])
        global_track = self.var_track.get()
        global_branch = self.var_branch.get().strip()

        dlg = SubmoduleItemDialog(self, rel, ov, branches, global_track, global_branch)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.sub_overrides[rel] = dlg.result
            self._refresh_sub_tree()

    def _set_all_subs_enabled(self, enabled: bool):
        for rel in self.sub_info_map:
            ov = self.sub_overrides.setdefault(rel, {"enabled": True, "strategy": "default", "branch": ""})
            ov["enabled"] = enabled
        self._refresh_sub_tree()

    def _reset_all_subs_strategy(self):
        for rel in self.sub_info_map:
            ov = self.sub_overrides.setdefault(rel, {"enabled": True, "strategy": "default", "branch": ""})
            ov["strategy"] = "default"
            ov["branch"] = ""
        self._refresh_sub_tree()

    # ---------------- 子模块多线程分支探测 ----------------

    def _probe_all_submodules(self, from_remote: bool):
        if self._probing or not self.sub_info_map:
            return
        self._probing = True
        self.btn_probe_subs.config(state="disabled")
        self.lbl_sub_status.config(
            text="正在多线程并发探测子模块远端分支..." if from_remote else "正在读取本地缓存分支..."
        )

        paths = list(self._paths)

        def work():
            probe_results = {}
            tasks = []
            for path in paths:
                subs = _submodule_details(path)
                urls = _gitmodules_urls(path)
                for s in subs:
                    tasks.append((path, s, from_remote, urls))

            with ThreadPoolExecutor(max_workers=min(12, max(len(tasks), 1))) as pool:
                future_map = {
                    pool.submit(_probe_single_submodule_branches, repo, sub, f_rem, u): sub["rel"]
                    for repo, sub, f_rem, u in tasks
                }
                for fut in as_completed(future_map):
                    rel = future_map[fut]
                    try:
                        branches = fut.result()
                    except Exception:
                        branches = []
                    probe_results.setdefault(rel, set()).update(branches)

            final_map = {k: sorted(list(v), key=lambda x: x.lower()) for k, v in probe_results.items()}
            try:
                self.after(0, self._probe_done, final_map, from_remote)
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=work, daemon=True).start()

    def _probe_done(self, branch_map: dict, from_remote: bool):
        self._probing = False
        if not self.winfo_exists():
            return
        self.btn_probe_subs.config(state="normal")

        all_branches_counter = {}
        for rel, branches in branch_map.items():
            if rel in self.sub_info_map:
                self.sub_info_map[rel]["branches"] = branches
            for b in branches:
                all_branches_counter[b] = all_branches_counter.get(b, 0) + 1

        # 更新全局候选分支下拉框
        sorted_all = sorted(all_branches_counter, key=lambda b: (-all_branches_counter[b], b.lower()))
        self.cbo_global_branch.config(values=sorted_all)

        src = "远端" if from_remote else "本地缓存"
        self.lbl_sub_status.config(
            text=f"子模块分支探测完成（数据源: {src}），双击行即可从专属分支列表中选择"
        )
        self._refresh_sub_tree()

    def _ok(self):
        global_branches = _parse_branches(self.var_branch.get())
        if self.var_sub.get() and self.var_track.get() == "branch" and not global_branches:
            messagebox.showwarning("提示", "全局默认选择“指定分支”时请填写至少一个分支名", parent=self)
            return

        self.result = {
            "mode": self.var_mode.get(),
            "submodule": self.var_sub.get(),
            "sub_track": self.var_track.get(),
            "sub_branch": ", ".join(global_branches),
            "sub_overrides": self.sub_overrides,
            "prune": self.var_prune.get(),
            "shallow": self.var_shallow.get(),
            "auto_abort": self.var_auto_abort.get(),
        }
        self.destroy()


# ---------------- 核心主界面与调度引擎 ----------------


class GitPullTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Git Pull - 项目拉取更新工具 (High-Performance)")
        self.root.geometry("980x720")
        self.root.minsize(840, 620)

        self._running = False
        self._cancel_event = threading.Event()
        self._active_procs_lock = threading.Lock()
        self._active_procs = set()

        self.projects: list[dict] = []
        self.global_cfg = _default_global_config()

        # 状态统计
        self._stats_total = 0
        self._stats_done = 0
        self._stats_ok = 0
        self._stats_fail = 0

        self._build_ui()
        self._load_config()
        self._refresh_tree()

    # ---------------- UI 构建 ----------------

    def _build_ui(self):
        # 顶部工具栏
        top_bar = ttk.Frame(self.root, padding=(10, 8, 10, 4))
        top_bar.pack(fill="x")

        ttk.Label(top_bar, text="🔍 快速搜索:").pack(side="left", padx=(0, 4))
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self._refresh_tree())
        ent_search = ttk.Entry(top_bar, textvariable=self.var_search, width=24)
        ent_search.pack(side="left")

        ttk.Button(top_bar, text="⚙ 全局偏好设置", command=self._on_settings).pack(side="right")
        ttk.Button(top_bar, text="添加项目...", command=self._on_add).pack(side="right", padx=(0, 6))

        # 项目列表 Frame
        frame_proj = ttk.LabelFrame(
            self.root,
            text="项目列表（点击「更新」列切换勾选；双击行编辑配置与子模块；支持右键快捷操作）",
            padding=8
        )
        frame_proj.pack(fill="both", expand=False, padx=10, pady=4)

        tree_row = ttk.Frame(frame_proj)
        tree_row.pack(fill="both", expand=True)

        cols = ("enabled", "mode", "submodule", "prune", "shallow")
        self.tree = ttk.Treeview(
            tree_row, columns=cols, show="tree headings", height=8, selectmode="extended"
        )
        self.tree.heading("#0", text="项目路径")
        self.tree.heading("enabled", text="更新")
        self.tree.heading("mode", text="模式")
        self.tree.heading("submodule", text="子模块定制策略")
        self.tree.heading("prune", text="prune")
        self.tree.heading("shallow", text="浅拉取")

        self.tree.column("#0", width=420, anchor="w")
        self.tree.column("enabled", width=55, anchor="center", stretch=False)
        self.tree.column("mode", width=60, anchor="center", stretch=False)
        self.tree.column("submodule", width=180, anchor="center", stretch=False)
        self.tree.column("prune", width=55, anchor="center", stretch=False)
        self.tree.column("shallow", width=60, anchor="center", stretch=False)
        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(tree_row, orient="vertical", command=self.tree.yview)
        sb.pack(side="left", fill="y")
        self.tree.config(yscrollcommand=sb.set)

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._show_context_menu)
        self.tree.bind("<Delete>", lambda e: self._on_remove())
        self.root.bind("<Control-a>", lambda e: self._set_all_enabled(True))

        # 列表下方快捷按钮
        btn_col = ttk.Frame(frame_proj)
        btn_col.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_col, text="全部勾选", command=lambda: self._set_all_enabled(True)).pack(side="left")
        ttk.Button(btn_col, text="全部取消", command=lambda: self._set_all_enabled(False)).pack(side="left", padx=6)
        ttk.Separator(btn_col, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(btn_col, text="编辑选中（含子模块定制）...", command=self._on_edit).pack(side="left")
        ttk.Button(btn_col, text="移除选中", command=self._on_remove).pack(side="left", padx=6)

        # 进度条与操作按钮区
        frame_action = ttk.Frame(self.root, padding=(10, 6, 10, 4))
        frame_action.pack(fill="x")

        self.btn_run = ttk.Button(frame_action, text="▶ 开始更新（已勾选项目）", command=self._on_run)
        self.btn_run.pack(side="left", padx=(0, 6))

        self.btn_stop = ttk.Button(frame_action, text="🛑 中止执行", command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(0, 10))

        self.btn_status = ttk.Button(frame_action, text="🔍 查看项目状态", command=self._on_status)
        self.btn_status.pack(side="left", padx=(0, 6))

        ttk.Button(frame_action, text="🧹 清空日志", command=self._clear_log).pack(side="right")

        # 进度条与标签
        self.progress_bar = ttk.Progressbar(frame_action, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side="right", fill="x", expand=True, padx=(12, 12))

        self.lbl_progress = ttk.Label(self.root, text="就绪", foreground="#555555")
        self.lbl_progress.pack(anchor="w", padx=12, pady=(0, 2))

        # 执行日志 Frame (带富文本高亮)
        frame_log = ttk.LabelFrame(self.root, text="执行日志", padding=8)
        frame_log.pack(fill="both", expand=True, padx=10, pady=(2, 10))

        self.log_text = scrolledtext.ScrolledText(
            frame_log, wrap="word", height=14, font=("Consolas", 9),
            bg="#ffffff", fg="#222222"
        )
        self.log_text.pack(fill="both", expand=True)

        # 配置日志高亮标签
        self.log_text.tag_config("cmd", foreground="#0277bd", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("success", foreground="#2e7d32", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("warn", foreground="#ef6c00", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("error", foreground="#c62828", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("blocked", foreground="#8e24aa", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("header", foreground="#1565c0", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("info", foreground="#37474f")

        # 右键上下文菜单
        self._build_context_menu()

    def _build_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="⚡ 仅更新此项目", command=self._on_menu_run_single)
        self.context_menu.add_command(label="🔍 查看此项目状态", command=self._on_menu_status_single)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📁 在资源管理器中打开", command=self._on_menu_open_folder)
        self.context_menu.add_command(label="💻 在终端中打开 (PowerShell/CMD)", command=self._on_menu_open_terminal)
        self.context_menu.add_command(label="📋 复制项目路径", command=self._on_menu_copy_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✏ 编辑配置与子模块...", command=self._on_edit)
        self.context_menu.add_command(label="🗑 移除此项目", command=self._on_remove)

    def _show_context_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.context_menu.post(event.x_root, event.y_root)

    # ---------------- 表格渲染 ----------------

    def _refresh_tree(self):
        query = self.var_search.get().strip().lower()
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for i, p in enumerate(self.projects):
            path = p["path"]
            if query and query not in path.lower():
                continue
            iid = str(i)
            self.tree.insert(
                "", "end", iid=iid, text=path,
                values=(
                    "☑" if p["enabled"] else "☐",
                    _MODE_LABELS.get(p["mode"], p["mode"]),
                    _submodule_desc(p),
                    "是" if p["prune"] else "否",
                    "是" if p.get("shallow") else "否",
                ),
            )
            if iid in sel:
                self.tree.selection_add(iid)

    # ---------------- 配置持久化 ----------------

    def _load_config(self):
        loaded = []
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("projects", []):
                if isinstance(item, str):
                    loaded.append(_default_project(item))
                elif isinstance(item, dict) and item.get("path"):
                    d = _default_project(item["path"])
                    d.update({k: item[k] for k in _PROJECT_KEYS if k in item})
                    loaded.append(d)
            if "global_config" in data and isinstance(data["global_config"], dict):
                self.global_cfg.update(data["global_config"])
        except Exception:
            pass

        if not loaded:
            here = os.path.dirname(os.path.abspath(__file__))
            loaded = [_default_project(here)]

        self.projects = loaded

    def _save_config(self):
        try:
            payload = {
                "projects": self.projects,
                "global_config": self.global_cfg,
            }
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------------- 线程安全的 UI 与日志 ----------------

    def _log(self, msg: str):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg: str):
        lines = msg.splitlines()
        for line in lines:
            tag = "info"
            if line.startswith("$ "):
                tag = "cmd"
            elif any(line.startswith(prefix) for prefix in ("[OK]", "[SUCCESS]", "=== [OK]")):
                tag = "success"
            elif any(line.startswith(prefix) for prefix in ("[WARN]", "[WARNING]")):
                tag = "warn"
            elif any(line.startswith(prefix) for prefix in ("[ERROR]", "[FAILED]", "[FAIL]")):
                tag = "error"
            elif line.startswith("[BLOCKED]"):
                tag = "blocked"
            elif line.startswith("===") or line.startswith("###") or line.startswith("---"):
                tag = "header"

            self.log_text.insert("end", line + "\n", tag)
        self.log_text.see("end")

    def _set_running(self, running: bool):
        self.root.after(0, self._apply_running_state, running)

    def _apply_running_state(self, running: bool):
        self._running = running
        state = "disabled" if running else "normal"
        self.btn_run.config(state=state)
        self.btn_status.config(state=state)
        self.btn_stop.config(state="normal" if running else "disabled")

    def _update_progress(self, current: int, total: int, text: str):
        def apply_p():
            self.progress_bar.config(maximum=max(total, 1), value=current)
            self.lbl_progress.config(text=text)
        self.root.after(0, apply_p)

    def _clear_log(self):
        self.log_text.delete("1.0", "end")

    # ---------------- Git 执行引擎（含超时、重试、取消与拦截） ----------------

    def _run_cmd(
        self, cmd: list[str], cwd: str, quiet: bool = False, is_network: bool = False
    ) -> tuple[int, str]:
        if self._cancel_event.is_set():
            return -1, "cancelled"

        if cmd and cmd[0] == "git" and len(cmd) > 1 and cmd[1] in _FORBIDDEN:
            self._log(f"[BLOCKED] 安全防护已拦截影响远端的命令: {' '.join(cmd)}")
            return -1, "blocked"

        timeout = (
            self.global_cfg.get("network_timeout", 120)
            if is_network
            else self.global_cfg.get("local_timeout", 30)
        )
        max_retries = self.global_cfg.get("retry_count", 1) if is_network else 0

        for attempt in range(max_retries + 1):
            if self._cancel_event.is_set():
                return -1, "cancelled"

            if not quiet:
                prefix = f"$ {' '.join(cmd)}"
                if attempt > 0:
                    prefix += f" (第 {attempt + 1} 次重试)"
                self._log(prefix)

            try:
                p = subprocess.Popen(
                    cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace",
                    creationflags=_NO_WINDOW,
                )
                with self._active_procs_lock:
                    self._active_procs.add(p)

                try:
                    stdout, stderr = p.communicate(timeout=timeout)
                finally:
                    with self._active_procs_lock:
                        self._active_procs.discard(p)

                output = (stdout + stderr).strip()
                if output and not quiet:
                    self._log(output)

                if p.returncode == 0 or not is_network or attempt == max_retries:
                    return p.returncode, output

                self._log(f"[WARN] 命令执行失败 (code {p.returncode})，1秒后重试...")
                time.sleep(1.0)
            except FileNotFoundError:
                self._log("[ERROR] 未找到 git 命令，请确认已安装 Git 并加入 PATH 环境变量")
                return -1, "git-not-found"
            except subprocess.TimeoutExpired:
                p.kill()
                self._log(f"[WARN] 命令超时 ({timeout}秒)")
                if attempt == max_retries:
                    return -1, "timeout"
                time.sleep(1.0)
            except Exception as e:
                self._log(f"[ERROR] 执行异常: {e}")
                return -1, str(e)

        return -1, "failed"

    # ---------------- 前置校验 ----------------

    def _preflight(self, path: str) -> bool:
        if not path:
            self._log("[FAILED] 项目路径为空")
            return False
        if not os.path.isdir(path):
            self._log(f"[FAILED] 路径不存在: {path}")
            return False
        rc, _ = self._run_cmd(["git", "--version"], cwd=path, quiet=True)
        if rc != 0:
            return False
        rc, out = self._run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, quiet=True)
        if rc != 0 or out.strip() != "true":
            self._log(f"[FAILED] 该目录不是合法的 git 仓库: {path}")
            return False
        return True

    # ---------------- 批量与单项目更新 ----------------

    def _do_update_all(self, projects: list[dict]):
        total = len(projects)
        self._stats_total = total
        self._stats_done = 0
        self._stats_ok = 0
        self._stats_fail = 0

        self._log("=" * 60)
        self._log(f"批量更新启动 | 共 {total} 个项目 | 并发数: {self.global_cfg.get('concurrency', 3)}")
        self._log("=" * 60)

        results = []
        concurrency = max(1, self.global_cfg.get("concurrency", 3))

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_proj = {
                executor.submit(self._do_update_one_wrapper, proj, i, total): proj
                for i, proj in enumerate(projects, 1)
            }

            for future in as_completed(future_to_proj):
                proj = future_to_proj[future]
                try:
                    ok, msg = future.result()
                except Exception as e:
                    ok = False
                    msg = f"未预期异常: {e}"
                results.append((proj["path"], ok, msg))

                self._stats_done += 1
                if ok:
                    self._stats_ok += 1
                else:
                    self._stats_fail += 1

                self._update_progress(
                    self._stats_done, total,
                    f"进度: {self._stats_done}/{total} | 成功: {self._stats_ok} | 失败: {self._stats_fail}"
                )

        self._log("\n" + "=" * 60)
        if self._cancel_event.is_set():
            self._log("[WARN] 任务已由用户手动中止！完成汇总：")
        else:
            self._log("批量更新全部完成！汇总报告：")

        for path, ok, msg in results:
            tag = "[OK]  " if ok else "[FAIL]"
            detail = f" ({msg})" if msg else ""
            self._log(f"  {tag} {path}{detail}")
        self._log("=" * 60)

    def _do_update_one_wrapper(self, proj: dict, idx: int, total: int) -> tuple[bool, str]:
        path = proj["path"]
        if self._cancel_event.is_set():
            return False, "用户已中止"

        self._log(f"\n[{idx}/{total}] 开始更新: {path}")
        self._log(
            f"    模式={_MODE_LABELS.get(proj['mode'])} | 子模块={_submodule_desc(proj)} | "
            f"prune={'是' if proj['prune'] else '否'} | 浅拉取={'是' if proj.get('shallow') else '否'}"
        )

        ok, msg = self._do_update_one(proj)
        status_str = "成功" if ok else f"失败 ({msg})"
        self._log(f"[{idx}/{total}] {path} -> {status_str}")
        return ok, msg

    def _do_update_one(self, proj: dict) -> tuple[bool, str]:
        path = proj["path"]
        mode = proj["mode"]
        if not self._preflight(path):
            return False, "仓库校验失败"

        if self._cancel_event.is_set():
            return False, "用户已中止"

        # 1. Fetch
        fetch_cmd = ["git", "fetch", "--all", "--tags"]
        if proj["prune"]:
            fetch_cmd.append("--prune")
        if proj.get("shallow"):
            fetch_cmd.extend(["--depth", "1"])

        rc, _ = self._run_cmd(fetch_cmd, cwd=path, is_network=True)
        if rc != 0:
            return False, "git fetch 失败"

        if self._cancel_event.is_set():
            return False, "用户已中止"

        # 2. Update mode
        if mode == "force":
            ok, msg = self._do_force_update(path)
        elif mode == "stash":
            ok, msg = self._do_stash_update(path)
        else:
            ok, msg = self._do_safe_update(path, proj.get("auto_abort", True))

        if not ok:
            return False, msg

        # 3. Submodule update
        if proj.get("submodule"):
            sub_ok, sub_msg = self._do_submodule_update(path, mode, proj)
            if not sub_ok:
                return False, f"主项目成功，但子模块异常: {sub_msg}"

        return True, "完成"

    def _current_upstream(self, path: str) -> str:
        rc, up = self._run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=path, quiet=True,
        )
        if rc == 0 and up.strip():
            return up.strip()
        _, branch = self._run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, quiet=True)
        branch = branch.strip() or "HEAD"
        self._log(f"[INFO] 当前分支无上游跟踪，回退使用 origin/{branch}")
        return f"origin/{branch}"

    # ---------------- 三种更新模式 ----------------

    def _do_safe_update(self, path: str, auto_abort: bool) -> tuple[bool, str]:
        self._log("--- 安全更新：git pull --rebase --autostash ---")
        rc, output = self._run_cmd(["git", "pull", "--rebase", "--autostash"], cwd=path, is_network=True)
        if rc != 0:
            if "conflict" in output.lower() or "error: could not apply" in output.lower():
                self._log("[WARN] pull 发生冲突！")
                if auto_abort:
                    self._log("[INFO] 🛡️ 触发安全回滚防护：自动执行 git rebase --abort 还原工作区...")
                    self._run_cmd(["git", "rebase", "--abort"], cwd=path)
                    return False, "检测到冲突，已自动回滚 rebase，保留现场未修改"
                else:
                    return False, "冲突，需手动解决后执行 git rebase --continue"
            return False, "pull --rebase 失败"
        return True, ""

    def _do_stash_update(self, path: str) -> tuple[bool, str]:
        self._log("--- 暂存更新：stash → pull --rebase → stash pop ---")
        rc, output = self._run_cmd(
            ["git", "stash", "push", "--include-untracked", "-m", "auto-stash before pull"],
            cwd=path,
        )
        has_stash = rc == 0 and "No local changes" not in output
        rc, _ = self._run_cmd(["git", "pull", "--rebase"], cwd=path, is_network=True)
        pull_ok = rc == 0
        if not pull_ok:
            self._log("[WARN] pull 失败")
        if has_stash:
            rc_pop, _ = self._run_cmd(["git", "stash", "pop"], cwd=path)
            if rc_pop != 0:
                self._log("[WARN] stash pop 存在冲突，改动已保留在 stash 中，请手动核对")
                return False, "stash pop 冲突"
        return (True, "") if pull_ok else (False, "pull --rebase 失败")

    def _do_force_update(self, path: str) -> tuple[bool, str]:
        self._log("--- 强制更新：丢弃本地所有未提交修改，硬重置到远端最新 ---")
        upstream = self._current_upstream(path)
        self._run_cmd(["git", "checkout", "--", "."], cwd=path)
        self._run_cmd(["git", "clean", "-fd"], cwd=path)
        rc, _ = self._run_cmd(["git", "reset", "--hard", upstream], cwd=path)
        if rc != 0:
            return False, f"reset --hard {upstream} 失败"
        return True, ""

    # ---------------- 🌟 子模块精细化更新引擎 ----------------

    def _do_submodule_update(self, path: str, mode: str, proj: dict) -> tuple[bool, str]:
        global_track = proj.get("sub_track", "pinned")
        global_branches = _parse_branches(proj.get("sub_branch", ""))
        overrides = proj.get("sub_overrides", {})
        jobs = max(1, self.global_cfg.get("submodule_jobs", 4))

        self._log(f"--- 更新子模块（全局默认: {_SUB_TRACK_LABELS.get(global_track, global_track)} | 并行: {jobs}）---")

        if not os.path.isfile(os.path.join(path, ".gitmodules")):
            self._log("[INFO] 项目未包含 .gitmodules，跳过子模块")
            return True, ""

        if self._cancel_event.is_set():
            return False, "用户已中止"

        # 1. 同步所有子模块 URL
        self._run_cmd(["git", "submodule", "sync", "--recursive"], cwd=path)

        # 2. 强制模式工作区清理
        if mode == "force":
            self._run_cmd(
                ["git", "submodule", "foreach", "--recursive",
                 "git checkout -- . && git clean -fd"],
                cwd=path,
            )

        # 3. 递归初始化所有未初始化的子模块
        init_cmd = ["git", "submodule", "update", "--init", "--recursive", f"--jobs={jobs}"]
        if mode == "force":
            init_cmd.append("--force")
        if proj.get("shallow"):
            init_cmd.extend(["--depth", "1"])
        self._run_cmd(init_cmd, cwd=path, is_network=True)

        # 4. 获取子模块列表，按每个子模块的独立定制策略逐个处理
        subs = _submodule_details(path)
        if not subs:
            return True, ""

        failed_subs = []
        updated_count = 0
        skipped_count = 0

        for s in subs:
            if self._cancel_event.is_set():
                return False, "用户已中止"

            rel = s["rel"]
            sub_dir = s["abs"]
            ov = overrides.get(rel, {})

            # 排除检查
            if not ov.get("enabled", True):
                self._log(f"[INFO] ⏭️ 子模块 [{rel}] 已配置排除，跳过更新")
                skipped_count += 1
                continue

            # 确定该子模块的生效策略与目标分支
            strat = ov.get("strategy", "default")
            if strat == "default":
                strat = global_track

            target_branches = (
                _parse_branches(ov.get("branch", ""))
                if (strat == "branch" and ov.get("strategy") == "branch")
                else global_branches
            )

            self._log(f"\n>>> 子模块 [{rel}] -> 策略: {_SUB_TRACK_LABELS.get(strat, strat)}")

            if not os.path.exists(os.path.join(sub_dir, ".git")):
                self._log("[WARN] 子模块不是合法的 git 工作区，跳过")
                continue

            # A. Pinned 模式
            if strat == "pinned":
                cmd = ["git", "submodule", "update", "--recursive"]
                if mode == "force":
                    cmd.append("--force")
                if proj.get("shallow"):
                    cmd.extend(["--depth", "1"])
                cmd += ["--", rel]
                rc, _ = self._run_cmd(cmd, cwd=path, is_network=True)
                if rc == 0:
                    updated_count += 1
                else:
                    failed_subs.append(rel)

            # B. Remote 模式
            elif strat == "remote":
                cmd = ["git", "submodule", "update", "--remote", "--recursive"]
                if mode == "force":
                    cmd.append("--force")
                if proj.get("shallow"):
                    cmd.extend(["--depth", "1"])
                cmd += ["--", rel]
                rc, _ = self._run_cmd(cmd, cwd=path, is_network=True)
                if rc == 0:
                    updated_count += 1
                else:
                    failed_subs.append(rel)

            # C. Branch 模式（独立或全局指定分支）
            elif strat == "branch":
                if not target_branches:
                    self._log(f"[WARN] 子模块 [{rel}] 选择了指定分支但未配置分支名，保持记录版本")
                    continue

                fetch_cmd = ["git", "fetch", "--all", "--tags"]
                if proj.get("prune"):
                    fetch_cmd.append("--prune")
                if proj.get("shallow"):
                    fetch_cmd.extend(["--depth", "1"])

                rc, _ = self._run_cmd(fetch_cmd, cwd=sub_dir, is_network=True)
                if rc != 0:
                    self._log("[WARN] fetch 失败，跳过该子模块")
                    failed_subs.append(rel)
                    continue

                picked = None
                for b in target_branches:
                    rc_b, _ = self._run_cmd(
                        ["git", "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{b}"],
                        cwd=sub_dir, quiet=True,
                    )
                    if rc_b == 0:
                        picked = b
                        break

                if not picked:
                    self._log(f"[WARN] 远端无匹配分支 {' / '.join(target_branches)}，保持当前版本")
                    continue

                if not self._checkout_branch(sub_dir, picked, mode):
                    failed_subs.append(rel)
                    continue

                if mode == "force":
                    ok_s, _ = self._do_force_update(sub_dir)
                elif mode == "stash":
                    ok_s, _ = self._do_stash_update(sub_dir)
                else:
                    ok_s, _ = self._do_safe_update(sub_dir, proj.get("auto_abort", True))

                if ok_s:
                    updated_count += 1
                else:
                    failed_subs.append(rel)

        self._log(f"\n[INFO] 子模块更新完成：成功更新 {updated_count} 个，排除跳过 {skipped_count} 个")
        if failed_subs:
            return False, f"{len(failed_subs)} 个子模块更新失败 ({', '.join(failed_subs[:3])})"
        return True, ""

    def _checkout_branch(self, repo: str, branch: str, mode: str) -> bool:
        """切换到 branch 并设置追踪 origin/branch。"""
        rc, cur = self._run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, quiet=True
        )
        if rc == 0 and cur.strip() == branch:
            self._log(f"[INFO] 已在分支 {branch}")
        else:
            rc_local, _ = self._run_cmd(
                ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
                cwd=repo, quiet=True,
            )
            if rc_local == 0:
                cmd = ["git", "checkout", branch]
            else:
                cmd = ["git", "checkout", "-b", branch, "--track", f"origin/{branch}"]
            rc, _ = self._run_cmd(cmd, cwd=repo)
            if rc != 0 and mode == "force":
                rc, _ = self._run_cmd(
                    ["git", "checkout", "-f", "-B", branch, f"origin/{branch}"], cwd=repo
                )
            if rc != 0:
                self._log(f"[WARN] 切换分支 {branch} 失败，跳过")
                return False

        self._run_cmd(
            ["git", "branch", f"--set-upstream-to=origin/{branch}", branch], cwd=repo, quiet=True
        )
        return True

    # ---------------- 结构化状态查看 ----------------

    def _do_status_inspection(self, targets: list[dict]):
        self._log("=" * 60)
        self._log(f"项目状态检查看板 | 共 {len(targets)} 个项目")
        self._log("=" * 60)

        for proj in targets:
            path = proj["path"]
            self._log(f"\n📦 项目: {path}")
            if not self._preflight(path):
                continue

            # 1. Branch and Upstream
            _, br = self._run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, quiet=True)
            _, up = self._run_cmd(["git", "rev-parse", "--abbrev-ref", "@{u}"], cwd=path, quiet=True)
            branch_str = br.strip() or "HEAD"
            up_str = up.strip() if up.strip() else "(未设置上游)"

            # 2. Ahead / Behind
            ahead_behind = ""
            if up_str and up_str != "(未设置上游)":
                rc, counts = self._run_cmd(
                    ["git", "rev-list", "--left-right", "--count", f"{branch_str}...{up_str}"],
                    cwd=path, quiet=True
                )
                if rc == 0 and counts.strip():
                    parts = counts.split()
                    if len(parts) == 2:
                        ahead, behind = parts
                        ahead_behind = f" [超前 {ahead} | 落后 {behind}]"

            self._log(f"  当前分支: {branch_str} -> 跟踪: {up_str}{ahead_behind}")

            # 3. Dirty files
            rc, st = self._run_cmd(["git", "status", "--porcelain"], cwd=path, quiet=True)
            if rc == 0:
                dirty_count = len([l for l in st.splitlines() if l.strip()])
                if dirty_count == 0:
                    self._log("  工作区状态: 干净 (Clean)")
                else:
                    self._log(f"  工作区状态: 存在 {dirty_count} 处未提交/未跟踪修改")

            # 4. Submodules
            subs = _submodule_details(path)
            if subs:
                self._log(f"  子模块列表 (共 {len(subs)} 个):")
                for s in subs:
                    rel = s["rel"]
                    ov = proj.get("sub_overrides", {}).get(rel, {})
                    ex_tag = " [已排除]" if not ov.get("enabled", True) else ""
                    self._log(f"    ├─ {rel}: 检出=[{s['head']}] commit=[{s['sha']}]{ex_tag}")

        self._log("\n" + "=" * 60)
        self._log("状态检查完成")
        self._log("=" * 60)

    # ---------------- 交互事件处理 ----------------

    def _selected_indices(self) -> list[int]:
        return sorted(int(iid) for iid in self.tree.selection())

    def _on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if col == "#1" and row != "":
            idx = int(row)
            self.projects[idx]["enabled"] = not self.projects[idx]["enabled"]
            self._save_config()
            self._refresh_tree()
            return "break"

    def _on_tree_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row != "":
            self._edit_indices([int(row)])
            return "break"

    def _on_add(self):
        chosen = filedialog.askdirectory(title="选择 Git 项目目录", initialdir=os.path.expanduser("~"))
        if not chosen:
            return
        chosen = os.path.normpath(chosen)
        if any(os.path.normpath(p["path"]) == chosen for p in self.projects):
            messagebox.showinfo("提示", "该项目已在列表中")
            return
        self.projects.append(_default_project(chosen))
        self._save_config()
        self._refresh_tree()

    def _on_remove(self):
        idxs = self._selected_indices()
        if not idxs:
            messagebox.showinfo("提示", "请先在列表中选中要移除的项目")
            return
        if messagebox.askyesno("确认移除", f"确定从列表中移除选中的 {len(idxs)} 个项目？（不会删除本地文件）"):
            for i in reversed(idxs):
                del self.projects[i]
            self._save_config()
            self._refresh_tree()

    def _on_edit(self):
        idxs = self._selected_indices()
        if not idxs:
            messagebox.showinfo("提示", "请先在列表中选中要编辑的项目")
            return
        self._edit_indices(idxs)

    def _edit_indices(self, idxs: list[int]):
        init = self.projects[idxs[0]]
        dlg = EditDialog(self.root, init, [self.projects[i]["path"] for i in idxs])
        self.root.wait_window(dlg)
        if dlg.result is None:
            return
        for i in idxs:
            self.projects[i].update(dlg.result)
        self._save_config()
        self._refresh_tree()

    def _on_settings(self):
        dlg = SettingsDialog(self.root, self.global_cfg)
        self.root.wait_window(dlg)
        if dlg.result is not None:
            self.global_cfg.update(dlg.result)
            self._save_config()

    def _set_all_enabled(self, value: bool):
        for p in self.projects:
            p["enabled"] = value
        self._save_config()
        self._refresh_tree()

    def _on_run(self):
        if self._running:
            return
        targets = [p for p in self.projects if p["enabled"]]
        if not targets:
            messagebox.showwarning("提示", "没有勾选任何项目（请点击「更新」列勾选）")
            return

        force_list = [p["path"] for p in targets if p["mode"] == "force"]
        if force_list:
            if not messagebox.askyesno(
                "确认强制更新",
                f"以下 {len(force_list)} 个项目处于【强制更新】模式，将丢弃所有本地未提交修改：\n\n"
                + "\n".join(force_list[:10]) + ("\n..." if len(force_list) > 10 else "")
                + "\n\n确定继续执行？",
            ):
                return

        snapshot = [dict(p) for p in targets]
        self._clear_log()
        self._cancel_event.clear()
        self._set_running(True)
        self._update_progress(0, len(snapshot), f"准备更新 {len(snapshot)} 个项目...")

        def task():
            try:
                self._do_update_all(snapshot)
            except Exception as e:
                self._log(f"\n[ERROR] 批量任务发生异常: {e}")
            finally:
                self._set_running(False)

        threading.Thread(target=task, daemon=True).start()

    def _on_stop(self):
        if not self._running:
            return
        if messagebox.askyesno("确认中止", "确定要中止当前的更新任务？正在执行的子进程将被终止。"):
            self._cancel_event.set()
            with self._active_procs_lock:
                for p in list(self._active_procs):
                    try:
                        p.kill()
                    except Exception:
                        pass
            self._log("\n[WARN] 已发送中止信号...")

    def _on_status(self):
        if self._running:
            return
        idxs = self._selected_indices()
        targets = [self.projects[i] for i in idxs] if idxs else list(self.projects)
        if not targets:
            messagebox.showwarning("提示", "列表中没有项目")
            return

        snapshot = [dict(p) for p in targets]
        self._clear_log()
        self._set_running(True)

        def task():
            try:
                self._do_status_inspection(snapshot)
            finally:
                self._set_running(False)

        threading.Thread(target=task, daemon=True).start()

    # ---------------- 右键菜单响应 ----------------

    def _on_menu_run_single(self):
        idxs = self._selected_indices()
        if not idxs or self._running:
            return
        p = dict(self.projects[idxs[0]])
        self._clear_log()
        self._cancel_event.clear()
        self._set_running(True)

        def task():
            try:
                self._do_update_all([p])
            finally:
                self._set_running(False)

        threading.Thread(target=task, daemon=True).start()

    def _on_menu_status_single(self):
        idxs = self._selected_indices()
        if not idxs or self._running:
            return
        p = dict(self.projects[idxs[0]])
        self._clear_log()
        self._set_running(True)

        def task():
            try:
                self._do_status_inspection([p])
            finally:
                self._set_running(False)

        threading.Thread(target=task, daemon=True).start()

    def _on_menu_open_folder(self):
        idxs = self._selected_indices()
        if not idxs:
            return
        path = self.projects[idxs[0]]["path"]
        if os.path.isdir(path):
            os.startfile(path)

    def _on_menu_open_terminal(self):
        idxs = self._selected_indices()
        if not idxs:
            return
        path = self.projects[idxs[0]]["path"]
        if not os.path.isdir(path):
            return
        try:
            subprocess.Popen(["wt", "-d", path])
        except Exception:
            subprocess.Popen(["powershell", "-NoExit", "-Command", f"Set-Location -LiteralPath '{path}'"])

    def _on_menu_copy_path(self):
        idxs = self._selected_indices()
        if not idxs:
            return
        path = self.projects[idxs[0]]["path"]
        self.root.clipboard_clear()
        self.root.clipboard_append(path)


if __name__ == "__main__":
    root = tk.Tk()
    # 启用高 DPI 缩放适配 (Windows)
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = GitPullTool(root)
    root.mainloop()
