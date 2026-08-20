#!/usr/bin/env python3
"""
Git 项目拉取更新工具 (GUI)

特性：
- 只读远端，只动本地。禁止任何 push / force-push / 修改远端的操作。
- 支持管理多个项目，每个项目独立配置更新选项（是否更新 / 模式 / 子模块 / prune）。
- 三种更新模式：安全 / 暂存 / 强制。
- 自动同步并更新所有子模块（递归），子模块版本可选：
  记录版本（父仓库 pin 的提交）/ 远端最新（--remote）/ 指定分支（支持多个候选）。
- 线程安全的日志与 UI 刷新（通过 root.after 调度回主线程）。
"""

import os
import re
import json
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from threading import Thread

# Windows 下抑制每条命令弹出的控制台黑窗
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# 记忆项目列表
_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".git_pull_tool.json")

# 禁止执行的危险/影响远端的子命令（安全兜底）
_FORBIDDEN = {"push", "remote", "config"}

_MODE_LABELS = {"safe": "安全", "stash": "暂存", "force": "强制"}
_MODE_ORDER = ["safe", "stash", "force"]

# 子模块版本策略
_SUB_TRACK_LABELS = {"pinned": "记录版本", "remote": "远端最新", "branch": "指定分支"}
_SUB_TRACK_ORDER = ["pinned", "remote", "branch"]

# 项目配置中允许持久化的字段
_PROJECT_KEYS = ("enabled", "mode", "submodule", "sub_track", "sub_branch", "prune")

# 解析 `git submodule status --recursive` 的输出行
#   " <sha> <path> (<describe>)"，行首可能是 ' ' / '+' / '-' / 'U'
_SUB_STATUS_RE = re.compile(r"^[+\-U ]?\s*[0-9a-f]{7,40}\s+(.+?)(?:\s+\([^()]*\))?$")


def _default_project(path: str) -> dict:
    return {
        "path": path,
        "enabled": True,
        "mode": "safe",
        "submodule": True,
        "sub_track": "pinned",
        "sub_branch": "",
        "prune": False,
    }


def _parse_branches(text: str) -> list[str]:
    """把 "main, master" 解析为候选分支列表（按顺序尝试）。"""
    return [b for b in re.split(r"[,;\s]+", (text or "").strip()) if b]


def _submodule_desc(proj: dict) -> str:
    """子模块设置在表格里的简短描述。"""
    if not proj.get("submodule"):
        return "否"
    track = proj.get("sub_track", "pinned")
    if track == "branch":
        branches = _parse_branches(proj.get("sub_branch", ""))
        if not branches:
            return "分支(未填)"
        return "分支: " + branches[0] + ("…" if len(branches) > 1 else "")
    return _SUB_TRACK_LABELS.get(track, track)


# ---------------- 子模块分支探测（只读，供编辑对话框使用） ----------------


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


def _submodule_dirs(path: str) -> tuple[list[tuple[str, str]], list[str]]:
    """返回 ([(相对路径, 绝对路径)] 已克隆, [相对路径] 未克隆)。"""
    ready: list[tuple[str, str]] = []
    missing: list[str] = []
    rc, out = _git_probe(["git", "submodule", "status", "--recursive"], path)
    if rc != 0:
        return ready, missing
    for line in out.splitlines():
        if not line.strip():
            continue
        m = _SUB_STATUS_RE.match(line)
        if not m:
            continue
        rel = m.group(1).strip()
        if line.startswith("-"):
            missing.append(rel)
        else:
            ready.append((rel, os.path.join(path, rel.replace("/", os.sep))))
    return ready, missing


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
        rc, out = _git_probe(["git", "ls-remote", "--heads", target], repo, timeout=60)
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


def _collect_submodule_branches(paths: list[str], from_remote: bool) -> dict:
    """
    汇总所有项目的子模块分支。
    返回 {branches: 按公共度排序的分支名, common: 所有子模块都有的分支,
          subs: 参与统计的子模块数, failed: 未能读取的子模块路径}
    """
    counter: dict[str, int] = {}
    subs = 0
    failed: list[str] = []
    for path in paths:
        if not os.path.isdir(path):
            continue
        ready, missing = _submodule_dirs(path)
        urls = _gitmodules_urls(path) if missing else {}
        for rel, sub_dir in ready:
            subs += 1
            names = _branches_of(sub_dir, from_remote)
            if not names:
                failed.append(rel)
                continue
            for b in set(names):
                counter[b] = counter.get(b, 0) + 1
        for rel in missing:
            subs += 1
            # 未克隆的子模块本地没有任何 ref，只能靠 ls-remote；
            # 因此仅在明确要求读远端时才联网，避免打开对话框就发起网络请求
            url = _resolve_submodule_url(path, urls.get(rel, "")) if urls.get(rel) else ""
            names = _branches_of(path, True, url) if (from_remote and url) else []
            if not names:
                failed.append(rel + "(未克隆)")
                continue
            for b in set(names):
                counter[b] = counter.get(b, 0) + 1
    ordered = sorted(counter, key=lambda b: (-counter[b], b.lower()))
    common = [b for b in ordered if subs and counter[b] == subs]
    return {"branches": ordered, "common": common, "subs": subs, "failed": failed}


class EditDialog(tk.Toplevel):
    """编辑单/多个项目的更新选项。"""

    def __init__(self, parent, init: dict, paths: list[str]):
        super().__init__(parent)
        count = len(paths)
        self.title("编辑更新选项" + (f"（{count} 个项目）" if count > 1 else ""))
        self.resizable(False, False)
        self.result = None
        self._paths = list(paths)
        self._probing = False
        self.transient(parent)
        self.grab_set()

        self.var_mode = tk.StringVar(value=init.get("mode", "safe"))
        self.var_sub = tk.BooleanVar(value=init.get("submodule", True))
        self.var_track = tk.StringVar(value=init.get("sub_track", "pinned"))
        self.var_branch = tk.StringVar(value=init.get("sub_branch", ""))
        self.var_prune = tk.BooleanVar(value=init.get("prune", False))

        frm = ttk.LabelFrame(self, text="更新模式", padding=8)
        frm.pack(fill="x", padx=12, pady=(12, 6))
        mode_texts = {
            "safe": "安全更新（autostash + rebase，保留本地修改）",
            "stash": "暂存更新（stash → 拉取 → 恢复）",
            "force": "强制更新（丢弃本地修改，与远端一致）",
        }
        for value in _MODE_ORDER:
            ttk.Radiobutton(frm, text=mode_texts[value], variable=self.var_mode, value=value).pack(
                anchor="w", pady=2
            )

        frm_sub = ttk.LabelFrame(self, text="子模块", padding=8)
        frm_sub.pack(fill="x", padx=12, pady=6)
        self.chk_sub = ttk.Checkbutton(
            frm_sub, text="同步更新所有子模块（递归）", variable=self.var_sub,
            command=self._sync_state,
        )
        self.chk_sub.pack(anchor="w")

        track_texts = {
            "pinned": "记录版本：检出父仓库记录的提交（默认，游离头指针）",
            "remote": "远端最新：--remote，分支取自 .gitmodules 配置",
            "branch": "指定分支：",
        }
        self._track_radios = []
        for value in _SUB_TRACK_ORDER:
            row = ttk.Frame(frm_sub)
            row.pack(fill="x", padx=(18, 0), pady=1)
            rb = ttk.Radiobutton(
                row, text=track_texts[value], variable=self.var_track,
                value=value, command=self._sync_state,
            )
            rb.pack(side="left")
            self._track_radios.append(rb)
            if value == "branch":
                self.cbo_branch = ttk.Combobox(
                    row, textvariable=self.var_branch, width=24, height=14, values=[]
                )
                self.cbo_branch.pack(side="left", padx=(4, 0))
                self.btn_probe = ttk.Button(
                    row, text="读取远端分支", width=13,
                    command=lambda: self._probe(from_remote=True),
                )
                self.btn_probe.pack(side="left", padx=(6, 0))

        self.lbl_branches = ttk.Label(frm_sub, text="", foreground="#336699", justify="left")
        self.lbl_branches.pack(anchor="w", padx=(18, 0), pady=(4, 0))
        self.lbl_hint = ttk.Label(
            frm_sub,
            text="下拉可选子模块的分支；也可手动输入，多个候选用逗号分隔（如 main, master），\n"
                 "按顺序取远端第一个存在的分支，都不存在时保留该子模块当前版本。",
            foreground="#666666", justify="left",
        )
        self.lbl_hint.pack(anchor="w", padx=(18, 0), pady=(2, 0))

        frm2 = ttk.LabelFrame(self, text="选项", padding=8)
        frm2.pack(fill="x", padx=12, pady=6)
        ttk.Checkbutton(
            frm2, text="清理无效的远程追踪分支 (fetch --prune)", variable=self.var_prune
        ).pack(anchor="w")

        btns = ttk.Frame(self, padding=(12, 6, 12, 12))
        btns.pack(fill="x")
        ttk.Button(btns, text="确定", command=self._ok).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        self._sync_state()
        # 打开时先用本地远程追踪分支填充下拉（不联网，很快）
        self._probe(from_remote=False)

    def _sync_state(self):
        """子模块开关 / 版本策略联动，禁用不可用控件。"""
        sub_on = self.var_sub.get()
        for rb in self._track_radios:
            rb.config(state="normal" if sub_on else "disabled")
        branch_on = sub_on and self.var_track.get() == "branch"
        self.cbo_branch.config(state="normal" if branch_on else "disabled")
        if not self._probing:
            self.btn_probe.config(state="normal" if branch_on else "disabled")

    # ---------------- 分支探测 ----------------

    def _probe(self, from_remote: bool):
        """后台读取子模块分支列表并填充下拉框。"""
        if self._probing or not self._paths:
            return
        self._probing = True
        self.btn_probe.config(state="disabled")
        self.lbl_branches.config(
            text="正在读取远端分支…" if from_remote else "正在读取本地已知分支…"
        )

        paths = list(self._paths)

        def work():
            try:
                data = _collect_submodule_branches(paths, from_remote)
            except Exception as e:  # 探测失败不影响手动输入
                data = {"branches": [], "common": [], "subs": 0, "failed": [str(e)]}
            try:
                self.after(0, self._probe_done, data, from_remote)
            except (tk.TclError, RuntimeError):
                pass  # 对话框已关闭 / 主循环已退出

        Thread(target=work, daemon=True).start()

    def _probe_done(self, data: dict, from_remote: bool):
        self._probing = False
        if not self.winfo_exists():
            return
        branches = data["branches"]
        self.cbo_branch.config(values=branches)

        src = "远端" if from_remote else "本地缓存"
        if not data["subs"]:
            text = "未发现子模块（可手动输入分支名）"
        elif not branches:
            text = f"未从{src}读取到分支（{data['subs']} 个子模块）"
            if not from_remote:
                text += "，可点击“读取远端分支”"
        else:
            text = f"{src}：{len(branches)} 个分支 / {data['subs']} 个子模块"
            if data["common"] and len(data["common"]) < len(branches):
                text += "；全部子模块共有：" + ", ".join(data["common"][:4])
            if data["failed"]:
                text += f"；{len(data['failed'])} 个未读到"
        self.lbl_branches.config(text=text)
        self._sync_state()

    def _ok(self):
        branches = _parse_branches(self.var_branch.get())
        if self.var_sub.get() and self.var_track.get() == "branch" and not branches:
            messagebox.showwarning("提示", "选择“指定分支”时请填写至少一个分支名", parent=self)
            return
        self.result = {
            "mode": self.var_mode.get(),
            "submodule": self.var_sub.get(),
            "sub_track": self.var_track.get(),
            "sub_branch": ", ".join(branches),
            "prune": self.var_prune.get(),
        }
        self.destroy()


class GitPullTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Git Pull - 项目拉取更新工具")
        self.root.geometry("880x680")
        self.root.minsize(780, 600)

        self._running = False
        self._active_dir = None
        self.projects: list[dict] = []

        self._build_ui()
        self._load_config()
        self._refresh_tree()

    # ---------------- UI ----------------

    def _build_ui(self):
        frame_proj = ttk.LabelFrame(
            self.root, text="项目列表（点击“更新”列勾选/取消；双击行编辑选项）", padding=8
        )
        frame_proj.pack(fill="both", expand=False, padx=10, pady=(10, 5))

        tree_row = ttk.Frame(frame_proj)
        tree_row.pack(fill="both", expand=True)

        cols = ("enabled", "mode", "submodule", "prune")
        self.tree = ttk.Treeview(tree_row, columns=cols, show="tree headings", height=7,
                                 selectmode="extended")
        self.tree.heading("#0", text="项目路径")
        self.tree.heading("enabled", text="更新")
        self.tree.heading("mode", text="模式")
        self.tree.heading("submodule", text="子模块")
        self.tree.heading("prune", text="prune")
        self.tree.column("#0", width=390, anchor="w")
        self.tree.column("enabled", width=55, anchor="center", stretch=False)
        self.tree.column("mode", width=60, anchor="center", stretch=False)
        self.tree.column("submodule", width=120, anchor="center", stretch=False)
        self.tree.column("prune", width=60, anchor="center", stretch=False)
        self.tree.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(tree_row, orient="vertical", command=self.tree.yview)
        sb.pack(side="left", fill="y")
        self.tree.config(yscrollcommand=sb.set)

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        btn_col = ttk.Frame(frame_proj)
        btn_col.pack(fill="x", pady=(6, 0))
        ttk.Button(btn_col, text="添加项目...", command=self._on_add).pack(side="left")
        ttk.Button(btn_col, text="移除选中", command=self._on_remove).pack(side="left", padx=6)
        ttk.Button(btn_col, text="编辑选中...", command=self._on_edit).pack(side="left")
        ttk.Separator(btn_col, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(btn_col, text="全部勾选", command=lambda: self._set_all_enabled(True)).pack(side="left")
        ttk.Button(btn_col, text="全部取消", command=lambda: self._set_all_enabled(False)).pack(side="left", padx=6)

        frame_btn = ttk.Frame(self.root, padding=8)
        frame_btn.pack(fill="x", padx=10)
        self.btn_run = ttk.Button(frame_btn, text="开始更新（已勾选项目）", command=self._on_run)
        self.btn_run.pack(side="left", padx=(0, 10))
        self.btn_status = ttk.Button(frame_btn, text="查看状态", command=self._on_status)
        self.btn_status.pack(side="left")

        frame_log = ttk.LabelFrame(self.root, text="执行日志", padding=8)
        frame_log.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.log_text = scrolledtext.ScrolledText(
            frame_log, wrap="word", height=14, font=("Consolas", 9)
        )
        self.log_text.pack(fill="both", expand=True)

    # ---------------- 表格渲染 ----------------

    def _refresh_tree(self):
        sel = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for i, p in enumerate(self.projects):
            iid = str(i)
            self.tree.insert(
                "", "end", iid=iid, text=p["path"],
                values=(
                    "☑" if p["enabled"] else "☐",
                    _MODE_LABELS.get(p["mode"], p["mode"]),
                    _submodule_desc(p),
                    "是" if p["prune"] else "否",
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
            legacy = data.get("last_path")
            if legacy and not any(p["path"] == legacy for p in loaded):
                loaded.append(_default_project(legacy))
        except Exception:
            pass

        if not loaded:
            here = os.path.dirname(os.path.abspath(__file__))
            loaded = [_default_project(here)]

        self.projects = loaded

    def _save_config(self):
        try:
            with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"projects": self.projects}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ---------------- 线程安全的 UI 调度 ----------------

    def _log(self, msg: str):
        self.root.after(0, self._append_log, msg)

    def _append_log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def _set_running(self, running: bool):
        self.root.after(0, self._apply_running_state, running)

    def _apply_running_state(self, running: bool):
        self._running = running
        state = "disabled" if running else "normal"
        self.btn_run.config(state=state)
        self.btn_status.config(state=state)

    def _clear_log(self):
        self.log_text.delete("1.0", "end")

    # ---------------- git 执行 ----------------

    def _run_cmd(self, cmd: list[str], cwd: str = None, quiet: bool = False) -> tuple[int, str]:
        """执行命令。quiet=True 时不打印命令与输出（用于探测类只读命令）。"""
        if cmd and cmd[0] == "git" and len(cmd) > 1 and cmd[1] in _FORBIDDEN:
            self._log(f"[BLOCKED] 已拦截可能影响远端/配置的命令: {' '.join(cmd)}")
            return -1, "blocked"

        work_dir = cwd or self._active_dir
        if not quiet:
            self._log(f"$ {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, cwd=work_dir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600, creationflags=_NO_WINDOW,
            )
            output = (result.stdout + result.stderr).strip()
            if output and not quiet:
                self._log(output)
            return result.returncode, output
        except FileNotFoundError:
            self._log("[ERROR] 未找到 git，请确认已安装并加入 PATH")
            return -1, "git-not-found"
        except subprocess.TimeoutExpired:
            self._log("[ERROR] 命令超时（600秒）")
            return -1, "timeout"
        except Exception as e:
            self._log(f"[ERROR] {e}")
            return -1, str(e)

    # ---------------- 前置校验 ----------------

    def _preflight(self, path: str) -> bool:
        if not path:
            self._log("[FAILED] 项目路径为空")
            return False
        if not os.path.isdir(path):
            self._log(f"[FAILED] 路径不存在: {path}")
            return False
        rc, _ = self._run_cmd(["git", "--version"], cwd=path)
        if rc != 0:
            return False
        rc, out = self._run_cmd(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
        if rc != 0 or out.strip() != "true":
            self._log(f"[FAILED] 该目录不是 git 仓库: {path}")
            return False
        return True

    # ---------------- 批量更新 ----------------

    def _do_update_all(self, projects: list[dict]):
        total = len(projects)
        self._log("#" * 56)
        self._log(f"批量更新 | 共 {total} 个项目")
        self._log("#" * 56)

        results = []
        for i, proj in enumerate(projects, 1):
            path = proj["path"]
            self._active_dir = path
            self._log(f"\n{'='*56}")
            self._log(f"[{i}/{total}] {path}")
            self._log(f"    模式={_MODE_LABELS.get(proj['mode'])} 子模块={_submodule_desc(proj)} "
                      f"prune={'是' if proj['prune'] else '否'}")
            self._log("=" * 56)
            try:
                ok = self._do_update_one(proj)
            except Exception as e:
                self._log(f"[ERROR] 未预期异常: {e}")
                ok = False
            results.append((path, ok))

        self._active_dir = None
        self._log("\n" + "#" * 56)
        self._log("批量更新完成，汇总：")
        for path, ok in results:
            self._log(f"  {'[OK]  ' if ok else '[FAIL]'} {path}")
        self._log("#" * 56)

    def _do_update_one(self, proj: dict) -> bool:
        path = proj["path"]
        mode = proj["mode"]
        if not self._preflight(path):
            return False

        fetch_cmd = ["git", "fetch", "--all", "--tags"]
        if proj["prune"]:
            fetch_cmd.append("--prune")
        rc, _ = self._run_cmd(fetch_cmd, cwd=path)
        if rc != 0:
            self._log("[FAILED] fetch 失败，请检查网络或远端地址")
            return False

        if mode == "force":
            ok = self._do_force_update(path)
        elif mode == "stash":
            ok = self._do_stash_update(path)
        else:
            ok = self._do_safe_update(path)

        if ok and proj["submodule"]:
            self._do_submodule_update(path, mode, proj)
        return ok

    def _current_upstream(self, path: str) -> str:
        rc, up = self._run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=path
        )
        if rc == 0 and up.strip():
            return up.strip()
        _, branch = self._run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path)
        branch = branch.strip() or "HEAD"
        self._log(f"[INFO] 当前分支无上游，回退使用 origin/{branch}")
        return f"origin/{branch}"

    # ---------------- 三种更新模式 ----------------

    def _do_safe_update(self, path: str) -> bool:
        self._log("--- 安全更新：git pull --rebase --autostash ---")
        rc, output = self._run_cmd(["git", "pull", "--rebase", "--autostash"], cwd=path)
        if rc != 0:
            if "conflict" in output.lower():
                self._log("[WARN] 存在冲突，请手动解决后执行: git rebase --continue")
            else:
                self._log("[WARN] pull 失败，请查看日志手动处理")
            return False
        return True

    def _do_stash_update(self, path: str) -> bool:
        self._log("--- 暂存更新：stash → pull --rebase → stash pop ---")
        rc, output = self._run_cmd(
            ["git", "stash", "push", "--include-untracked", "-m", "auto-stash before pull"],
            cwd=path,
        )
        has_stash = rc == 0 and "No local changes" not in output
        rc, _ = self._run_cmd(["git", "pull", "--rebase"], cwd=path)
        pull_ok = rc == 0
        if not pull_ok:
            self._log("[WARN] pull 失败")
        if has_stash:
            rc, output = self._run_cmd(["git", "stash", "pop"], cwd=path)
            if rc != 0:
                self._log("[WARN] stash pop 有冲突，请手动解决（改动仍保留在 stash 中，未丢失）")
                return False
        return pull_ok

    def _do_force_update(self, path: str) -> bool:
        self._log("--- 强制更新：丢弃本地所有修改，硬重置到远端 ---")
        upstream = self._current_upstream(path)
        self._run_cmd(["git", "checkout", "--", "."], cwd=path)
        self._run_cmd(["git", "clean", "-fd"], cwd=path)
        rc, _ = self._run_cmd(["git", "reset", "--hard", upstream], cwd=path)
        if rc != 0:
            self._log("[WARN] reset --hard 失败")
            return False
        return True

    def _do_submodule_update(self, path: str, mode: str, proj: dict):
        track = proj.get("sub_track", "pinned")
        self._log(f"--- 更新子模块（{_SUB_TRACK_LABELS.get(track, track)}）---")

        if not os.path.isfile(os.path.join(path, ".gitmodules")):
            self._log("[INFO] 未找到 .gitmodules，跳过子模块")
            return

        self._run_cmd(["git", "submodule", "sync", "--recursive"], cwd=path)

        if mode == "force":
            self._run_cmd(
                ["git", "submodule", "foreach", "--recursive",
                 "git checkout -- . && git clean -fd"],
                cwd=path,
            )

        if track == "branch":
            # 指定分支时只补齐未克隆的子模块，避免整体 update 把已在分支上的
            # 子模块又拉回游离头指针（记录版本）
            self._init_missing_submodules(path, mode)
            self._do_submodule_branch(path, mode, proj)
            return

        update_cmd = ["git", "submodule", "update", "--init", "--recursive"]
        if mode == "force":
            update_cmd.append("--force")
        if track == "remote":
            update_cmd.append("--remote")
            self._log("[INFO] 使用 --remote：分支取自 .gitmodules 的 submodule.<name>.branch，"
                      "未配置时 git 默认使用 master")
        self._run_cmd(update_cmd, cwd=path)

    def _init_missing_submodules(self, path: str, mode: str):
        """只初始化尚未克隆的子模块（status 中以 '-' 开头的条目）。"""
        rc, out = self._run_cmd(
            ["git", "submodule", "status", "--recursive"], cwd=path, quiet=True
        )
        if rc != 0:
            return
        missing = []
        for line in out.splitlines():
            if line.startswith("-"):
                m = _SUB_STATUS_RE.match(line)
                if m:
                    missing.append(m.group(1).strip())
        if not missing:
            return
        self._log(f"[INFO] 初始化未克隆的子模块: {', '.join(missing)}")
        for rel in missing:
            parent_rel, _, leaf = rel.rpartition("/")
            repo = os.path.join(path, parent_rel.replace("/", os.sep)) if parent_rel else path
            cmd = ["git", "submodule", "update", "--init", "--recursive"]
            if mode == "force":
                cmd.append("--force")
            cmd += ["--", leaf]
            self._run_cmd(cmd, cwd=repo)

    def _list_submodules(self, path: str) -> list[str]:
        """返回所有（递归）子模块相对顶层仓库的路径。"""
        rc, out = self._run_cmd(
            ["git", "submodule", "status", "--recursive"], cwd=path, quiet=True
        )
        if rc != 0:
            return []
        subs = []
        for line in out.splitlines():
            if not line.strip():
                continue
            if line.startswith("-"):
                self._log(f"[WARN] 子模块未初始化，跳过: {line.strip()}")
                continue
            m = _SUB_STATUS_RE.match(line)
            if m:
                subs.append(m.group(1).strip())
        return subs

    def _do_submodule_branch(self, path: str, mode: str, proj: dict):
        """把每个子模块切到指定分支（多个候选按顺序取远端第一个存在的），并拉取最新。"""
        branches = _parse_branches(proj.get("sub_branch", ""))
        if not branches:
            self._log("[WARN] 选择了“指定分支”但未填写分支名，保持记录版本")
            return

        subs = self._list_submodules(path)
        if not subs:
            self._log("[INFO] 未发现已初始化的子模块，跳过分支切换")
            return

        self._log(f"[INFO] 目标分支（按顺序尝试）: {' / '.join(branches)}")
        switched = 0
        for rel in subs:
            sub_dir = os.path.join(path, rel.replace("/", os.sep))
            self._log(f"\n>>> 子模块: {rel}")
            if not os.path.exists(os.path.join(sub_dir, ".git")):
                self._log("[WARN] 该子模块目录不是 git 工作区，跳过")
                continue

            fetch_cmd = ["git", "fetch", "--all", "--tags"]
            if proj.get("prune"):
                fetch_cmd.append("--prune")
            rc, _ = self._run_cmd(fetch_cmd, cwd=sub_dir)
            if rc != 0:
                self._log("[WARN] fetch 失败，保持当前版本")
                continue

            picked = None
            for b in branches:
                rc, _ = self._run_cmd(
                    ["git", "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{b}"],
                    cwd=sub_dir, quiet=True,
                )
                if rc == 0:
                    picked = b
                    break
            if not picked:
                self._log(f"[WARN] 远端不存在分支 {' / '.join(branches)}，保持当前版本")
                continue

            if not self._checkout_branch(sub_dir, picked, mode):
                continue

            if mode == "force":
                self._do_force_update(sub_dir)
            elif mode == "stash":
                self._do_stash_update(sub_dir)
            else:
                self._do_safe_update(sub_dir)
            switched += 1

        if switched:
            self._log(f"\n[INFO] {switched}/{len(subs)} 个子模块已切到指定分支并拉取最新；"
                      "父仓库中子模块指针可能显示为已修改，属正常现象（本工具不会提交或推送）")
        else:
            self._log("\n[WARN] 没有子模块被切换到指定分支")

    def _checkout_branch(self, repo: str, branch: str, mode: str) -> bool:
        """在仓库 repo 中切换到 branch（不存在则基于 origin/branch 创建并跟踪）。"""
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
                self._log("[INFO] 常规切换失败，强制模式改用 checkout -f -B")
                rc, _ = self._run_cmd(
                    ["git", "checkout", "-f", "-B", branch, f"origin/{branch}"], cwd=repo
                )
            if rc != 0:
                self._log(f"[WARN] 切换到分支 {branch} 失败（可能存在本地修改或冲突），跳过该子模块")
                return False

        # 确保有上游，后续 pull --rebase 才有明确目标
        rc, _ = self._run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=repo, quiet=True,
        )
        if rc != 0:
            self._run_cmd(
                ["git", "branch", f"--set-upstream-to=origin/{branch}", branch], cwd=repo
            )
        return True

    # ---------------- 列表 / 选择操作 ----------------

    def _selected_indices(self) -> list[int]:
        return sorted(int(iid) for iid in self.tree.selection())

    def _on_tree_click(self, event):
        # 点击“更新”列切换勾选
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if col == "#1" and row != "":  # #1 = enabled 列
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
        chosen = filedialog.askdirectory(title="选择 git 项目目录", initialdir=os.path.expanduser("~"))
        if not chosen:
            return
        if any(p["path"] == chosen for p in self.projects):
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

    def _set_all_enabled(self, value: bool):
        for p in self.projects:
            p["enabled"] = value
        self._save_config()
        self._refresh_tree()

    # ---------------- 执行回调 ----------------

    def _on_run(self):
        if self._running:
            return
        targets = [p for p in self.projects if p["enabled"]]
        if not targets:
            messagebox.showwarning("提示", "没有勾选任何项目（点击“更新”列勾选）")
            return

        force_list = [p["path"] for p in targets if p["mode"] == "force"]
        if force_list:
            if not messagebox.askyesno(
                "确认强制更新",
                f"以下 {len(force_list)} 个项目将强制更新，丢弃所有本地修改"
                "（含未跟踪文件与子模块改动），无法恢复：\n\n"
                + "\n".join(force_list) + "\n\n确定继续？",
            ):
                return

        # 拷贝一份快照，避免执行期间列表被改动
        snapshot = [dict(p) for p in targets]
        self._clear_log()
        self._set_running(True)

        def task():
            try:
                self._do_update_all(snapshot)
            except Exception as e:
                self._log(f"\n[ERROR] 未预期的异常: {e}")
            finally:
                self._set_running(False)

        Thread(target=task, daemon=True).start()

    def _on_status(self):
        if self._running:
            return
        idxs = self._selected_indices()
        targets = [self.projects[i] for i in idxs] if idxs else list(self.projects)
        if not targets:
            messagebox.showwarning("提示", "请先添加项目")
            return

        snapshot = [dict(p) for p in targets]
        self._clear_log()
        self._set_running(True)

        def task():
            try:
                for proj in snapshot:
                    path = proj["path"]
                    self._active_dir = path
                    self._log(f"\n{'='*56}")
                    self._log(f"项目: {path}")
                    self._log("=" * 56)
                    if not self._preflight(path):
                        continue
                    self._log("--- git status ---")
                    self._run_cmd(["git", "status"], cwd=path)
                    self._log("\n--- git submodule status ---")
                    self._run_cmd(["git", "submodule", "status", "--recursive"], cwd=path)
                    subs = self._list_submodules(path)
                    if subs:
                        self._log("\n--- 子模块当前分支 ---")
                        for rel in subs:
                            sub_dir = os.path.join(path, rel.replace("/", os.sep))
                            rc, br = self._run_cmd(
                                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                cwd=sub_dir, quiet=True,
                            )
                            name = br.strip() if rc == 0 else "?"
                            if name == "HEAD":
                                name = "HEAD（游离，跟随父仓库记录版本）"
                            self._log(f"  {rel}: {name}")
                self._active_dir = None
            finally:
                self._set_running(False)

        Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = GitPullTool(root)
    root.mainloop()
