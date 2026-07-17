#!/usr/bin/env python3
"""
Git 项目拉取更新工具 (GUI)

特性：
- 只读远端，只动本地。禁止任何 push / force-push / 修改远端的操作。
- 支持管理多个项目，每个项目独立配置更新选项（是否更新 / 模式 / 子模块 / prune）。
- 三种更新模式：安全 / 暂存 / 强制。
- 自动同步并更新所有子模块（递归）。
- 线程安全的日志与 UI 刷新（通过 root.after 调度回主线程）。
"""

import os
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


def _default_project(path: str) -> dict:
    return {"path": path, "enabled": True, "mode": "safe", "submodule": True, "prune": False}


class EditDialog(tk.Toplevel):
    """编辑单/多个项目的更新选项。"""

    def __init__(self, parent, init: dict, count: int):
        super().__init__(parent)
        self.title("编辑更新选项" + (f"（{count} 个项目）" if count > 1 else ""))
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()

        self.var_mode = tk.StringVar(value=init.get("mode", "safe"))
        self.var_sub = tk.BooleanVar(value=init.get("submodule", True))
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

        frm2 = ttk.LabelFrame(self, text="选项", padding=8)
        frm2.pack(fill="x", padx=12, pady=6)
        ttk.Checkbutton(frm2, text="同步更新所有子模块", variable=self.var_sub).pack(anchor="w")
        ttk.Checkbutton(
            frm2, text="清理无效的远程追踪分支 (fetch --prune)", variable=self.var_prune
        ).pack(anchor="w")

        btns = ttk.Frame(self, padding=(12, 6, 12, 12))
        btns.pack(fill="x")
        ttk.Button(btns, text="确定", command=self._ok).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    def _ok(self):
        self.result = {
            "mode": self.var_mode.get(),
            "submodule": self.var_sub.get(),
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
        self.tree.column("#0", width=440, anchor="w")
        self.tree.column("enabled", width=55, anchor="center", stretch=False)
        self.tree.column("mode", width=70, anchor="center", stretch=False)
        self.tree.column("submodule", width=70, anchor="center", stretch=False)
        self.tree.column("prune", width=70, anchor="center", stretch=False)
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
                    "是" if p["submodule"] else "否",
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
                    d.update({k: item[k] for k in ("enabled", "mode", "submodule", "prune") if k in item})
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

    def _run_cmd(self, cmd: list[str], cwd: str = None) -> tuple[int, str]:
        if cmd and cmd[0] == "git" and len(cmd) > 1 and cmd[1] in _FORBIDDEN:
            self._log(f"[BLOCKED] 已拦截可能影响远端/配置的命令: {' '.join(cmd)}")
            return -1, "blocked"

        work_dir = cwd or self._active_dir
        self._log(f"$ {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, cwd=work_dir, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600, creationflags=_NO_WINDOW,
            )
            output = (result.stdout + result.stderr).strip()
            if output:
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
            self._log(f"    模式={_MODE_LABELS.get(proj['mode'])} 子模块={'是' if proj['submodule'] else '否'} "
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
            self._do_submodule_update(path, mode)
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

    def _do_submodule_update(self, path: str, mode: str):
        self._log("--- 更新子模块 ---")
        self._run_cmd(["git", "submodule", "sync", "--recursive"], cwd=path)
        if mode == "force":
            self._run_cmd(
                ["git", "submodule", "foreach", "--recursive",
                 "git checkout -- . && git clean -fd"],
                cwd=path,
            )
            self._run_cmd(
                ["git", "submodule", "update", "--init", "--recursive", "--force"], cwd=path
            )
        else:
            self._run_cmd(["git", "submodule", "update", "--init", "--recursive"], cwd=path)

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
        dlg = EditDialog(self.root, init, len(idxs))
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
                self._active_dir = None
            finally:
                self._set_running(False)

        Thread(target=task, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = GitPullTool(root)
    root.mainloop()
