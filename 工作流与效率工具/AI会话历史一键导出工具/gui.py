"""
图形化用户界面 (GUI Interface)
基于 Tkinter 的现代桌面 AI 会话历史管理与一键导出工具
支持完整对话与极简 Token 优化双模式预览、一键剪贴板复制、多格式导出
"""

import os
import sys
import json
import threading
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Set

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# 路径自适应
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from core.scanner import SessionScanner
    from core.models import UnifiedSession
    from exporters import MarkdownExporter, HTMLExporter, JSONExporter, IndexExporter, CleanTextExporter
except (ImportError, ValueError):
    from .core.scanner import SessionScanner
    from .core.models import UnifiedSession
    from .exporters import MarkdownExporter, HTMLExporter, JSONExporter, IndexExporter, CleanTextExporter


class ExporterGUI(tk.Tk):
    """AI 会话导出工具主界面"""

    def __init__(self):
        super().__init__()

        self.title("🧰 AI 会话历史一键导出工具")
        self.geometry("1260x800")
        self.minsize(1020, 640)

        # 核心扫描与数据
        self.scanner = SessionScanner()
        self.clean_exporter = CleanTextExporter()
        self.all_sessions: List[UnifiedSession] = []
        self.displayed_sessions: List[UnifiedSession] = []
        self.selected_session_ids: Set[str] = set()
        self.row_to_session: Dict[str, UnifiedSession] = {}
        self.combo_to_tool_id: Dict[str, Optional[str]] = {}
        self.current_loaded_session: Optional[UnifiedSession] = None

        # 导出配置
        default_export_dir = os.path.abspath(os.path.join(current_dir, "exported_ai_sessions"))
        self.export_dir_var = tk.StringVar(value=default_export_dir)
        self.fmt_md_var = tk.BooleanVar(value=True)
        self.fmt_html_var = tk.BooleanVar(value=True)
        self.fmt_json_var = tk.BooleanVar(value=False)
        self.fmt_clean_md_var = tk.BooleanVar(value=True)
        self.fmt_clean_txt_var = tk.BooleanVar(value=False)

        self.search_var = tk.StringVar()
        self.tool_filter_var = tk.StringVar(value="全部 AI 工具")

        self._setup_styles()
        self._build_ui()
        self.refresh_scan()

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), padding=5)
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#666666")
        style.configure("Success.TLabel", font=("Segoe UI", 9, "bold"), foreground="#16a34a")
        style.configure("TNotebook.Tab", font=("Segoe UI", 9, "bold"), padding=[12, 4])

    def _build_ui(self):
        # 1. 顶部 Header
        header_frame = ttk.Frame(self, padding="16 12 16 8")
        header_frame.pack(fill=tk.X)

        title_lbl = ttk.Label(header_frame, text="🧰 AI 会话历史一键导出工具", style="Header.TLabel")
        title_lbl.pack(side=tk.LEFT)

        self.status_header_lbl = ttk.Label(header_frame, text="正在初始化...", style="SubHeader.TLabel")
        self.status_header_lbl.pack(side=tk.RIGHT, padx=8)

        # 2. 搜索与工具过滤工具栏
        toolbar_frame = ttk.Frame(self, padding="16 6 16 6")
        toolbar_frame.pack(fill=tk.X)

        ttk.Label(toolbar_frame, text="🔍 搜索:").pack(side=tk.LEFT, padx=(0, 4))
        search_entry = ttk.Entry(toolbar_frame, textvariable=self.search_var, width=22)
        search_entry.pack(side=tk.LEFT, padx=(0, 12))
        search_entry.bind("<KeyRelease>", lambda e: self.apply_filter())

        ttk.Label(toolbar_frame, text="🤖 筛选工具:").pack(side=tk.LEFT, padx=(0, 4))
        self.tool_combo = ttk.Combobox(toolbar_frame, textvariable=self.tool_filter_var, state="readonly", width=28)
        self.tool_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.tool_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_filter())

        btn_refresh = ttk.Button(toolbar_frame, text="🔄 刷新扫描", command=self.refresh_scan)
        btn_refresh.pack(side=tk.LEFT, padx=4)

        btn_select_all = ttk.Button(toolbar_frame, text="全选", command=self.select_all)
        btn_select_all.pack(side=tk.LEFT, padx=4)

        btn_deselect = ttk.Button(toolbar_frame, text="取消全选", command=self.deselect_all)
        btn_deselect.pack(side=tk.LEFT, padx=4)

        self.count_badge_lbl = ttk.Label(toolbar_frame, text="", foreground="#0284c7", font=("Segoe UI", 9, "bold"))
        self.count_badge_lbl.pack(side=tk.RIGHT, padx=8)

        # 3. 中间主体区 (左侧会话表格 + 右侧双模预览窗口)
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # 左侧表格 Frame
        left_frame = ttk.Frame(main_paned)
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        main_paned.add(left_frame, weight=3)

        columns = ("selected", "tool", "title", "time", "count", "workspace")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("selected", text="[勾选]")
        self.tree.heading("tool", text="AI 工具")
        self.tree.heading("title", text="会话标题")
        self.tree.heading("time", text="创建时间")
        self.tree.heading("count", text="消息数")
        self.tree.heading("workspace", text="关联项目 / 工作区")

        self.tree.column("selected", width=55, minwidth=45, anchor="center")
        self.tree.column("tool", width=120, minwidth=90, anchor="w")
        self.tree.column("title", width=220, minwidth=140, anchor="w")
        self.tree.column("time", width=130, minwidth=110, anchor="center")
        self.tree.column("count", width=65, minwidth=50, anchor="center")
        self.tree.column("workspace", width=180, minwidth=100, anchor="w")

        tree_scroll_y = tk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview, width=15)
        tree_scroll_x = tk.Scrollbar(left_frame, orient=tk.HORIZONTAL, command=self.tree.xview, width=15)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-1>", self._on_tree_click)

        # 右侧预览 Frame (Notebook 双标签页：完整预览 / 极简 Token 优化预览)
        right_frame = ttk.Frame(main_paned, padding=6)
        right_frame.grid_rowconfigure(2, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        main_paned.add(right_frame, weight=3)

        # 预览顶部控制条
        preview_header = ttk.Frame(right_frame)
        preview_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.preview_title_lbl = ttk.Label(preview_header, text="💬 会话内容实时预览", font=("Segoe UI", 11, "bold"))
        self.preview_title_lbl.pack(side=tk.LEFT, anchor="w")

        btn_copy_preview = ttk.Button(preview_header, text="📋 复制当前预览文本", command=self.copy_current_preview)
        btn_copy_preview.pack(side=tk.RIGHT, padx=(4, 0))

        self.preview_meta_lbl = ttk.Label(right_frame, text="请从左侧列表选择会话以查看详情", font=("Segoe UI", 8), foreground="#666666")
        self.preview_meta_lbl.grid(row=1, column=0, sticky="w", pady=(0, 4))

        # Notebook 选项卡
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.grid(row=2, column=0, sticky="nsew")

        # Tab 1: 完整原始对话预览
        tab_full = ttk.Frame(self.notebook)
        tab_full.grid_rowconfigure(0, weight=1)
        tab_full.grid_columnconfigure(0, weight=1)
        self.notebook.add(tab_full, text="💬 完整原始对话 (含思考与工具)")

        self.preview_full_text = tk.Text(tab_full, wrap=tk.WORD, font=("Consolas", 9), relief=tk.SOLID, borderwidth=1)
        scroll_full = tk.Scrollbar(tab_full, orient=tk.VERTICAL, command=self.preview_full_text.yview, width=15)
        self.preview_full_text.configure(yscrollcommand=scroll_full.set)

        self.preview_full_text.grid(row=0, column=0, sticky="nsew")
        scroll_full.grid(row=0, column=1, sticky="ns")

        # Tab 2: ✨ 极简 Token 优化预览
        tab_clean = ttk.Frame(self.notebook)
        tab_clean.grid_rowconfigure(0, weight=1)
        tab_clean.grid_columnconfigure(0, weight=1)
        self.notebook.add(tab_clean, text="✨ 极简 Token 优化 (核心问答/低消耗)")

        self.preview_clean_text = tk.Text(tab_clean, wrap=tk.WORD, font=("Segoe UI", 9), relief=tk.SOLID, borderwidth=1)
        scroll_clean = tk.Scrollbar(tab_clean, orient=tk.VERTICAL, command=self.preview_clean_text.yview, width=15)
        self.preview_clean_text.configure(yscrollcommand=scroll_clean.set)

        self.preview_clean_text.grid(row=0, column=0, sticky="nsew")
        scroll_clean.grid(row=0, column=1, sticky="ns")

        # 文本标签样式
        for pt in (self.preview_full_text, self.preview_clean_text):
            pt.tag_configure("role_user", foreground="#0369a1", font=("Segoe UI", 9, "bold"))
            pt.tag_configure("role_assistant", foreground="#15803d", font=("Segoe UI", 9, "bold"))
            pt.tag_configure("role_system", foreground="#9333ea", font=("Segoe UI", 9, "bold"))
            pt.tag_configure("thinking", foreground="#6b7280", font=("Consolas", 8, "italic"))
            pt.tag_configure("tools", foreground="#b45309", font=("Consolas", 8))
            pt.tag_configure("notice", foreground="#dc2626", font=("Segoe UI", 9, "bold"))

        # 4. 底部导出配置与操作栏
        bottom_frame = ttk.Frame(self, padding="16 10 16 14")
        bottom_frame.pack(fill=tk.X)

        path_row = ttk.Frame(bottom_frame)
        path_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(path_row, text="📁 导出目标目录:").pack(side=tk.LEFT, padx=(0, 6))
        path_entry = ttk.Entry(path_row, textvariable=self.export_dir_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_browse = ttk.Button(path_row, text="浏览...", command=self.browse_export_dir)
        btn_browse.pack(side=tk.LEFT)

        action_row = ttk.Frame(bottom_frame)
        action_row.pack(fill=tk.X)

        fmt_group = ttk.Frame(action_row)
        fmt_group.pack(side=tk.LEFT)

        ttk.Label(fmt_group, text="导出格式:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(fmt_group, text="Markdown (.md)", variable=self.fmt_md_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(fmt_group, text="独立网页 (.html)", variable=self.fmt_html_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(fmt_group, text="标准 JSON (.json)", variable=self.fmt_json_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(fmt_group, text="✨ 极简 Markdown (.clean.md)", variable=self.fmt_clean_md_var).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(fmt_group, text="📝 极简纯文本 (.clean.txt)", variable=self.fmt_clean_txt_var).pack(side=tk.LEFT, padx=4)

        btn_open_dir = ttk.Button(action_row, text="📂 打开导出目录", command=self.open_export_dir)
        btn_open_dir.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_export = ttk.Button(action_row, text="🚀 一键导出选中会话", style="Primary.TButton", command=self.start_export)
        self.btn_export.pack(side=tk.RIGHT, padx=6)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(bottom_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(8, 0))

    def _extract_selected_tool_id(self) -> Optional[str]:
        val = self.tool_filter_var.get().strip()
        return self.combo_to_tool_id.get(val, None)

    def refresh_scan(self):
        current_tool_id = self._extract_selected_tool_id()
        filter_label = current_tool_id or "全部工具"
        self.status_header_lbl.config(text=f"正在刷新扫描 ({filter_label})...")

        def _do_scan():
            sessions = self.scanner.scan_all()
            detected_tools = self.scanner.get_detected_tools()

            self.after(0, lambda: self._on_scan_finished(sessions, detected_tools, current_tool_id))

        threading.Thread(target=_do_scan, daemon=True).start()

    def _on_scan_finished(self, sessions: List[UnifiedSession], detected_tools: List[Dict[str, str]], prev_tool_id: Optional[str]):
        self.all_sessions = sessions
        self.selected_session_ids = {s.session_id for s in sessions if s.message_count > 0 or s.title}

        tool_counts = {}
        for s in sessions:
            tool_counts[s.tool_id] = tool_counts.get(s.tool_id, 0) + 1

        self.combo_to_tool_id.clear()
        all_label = f"全部 AI 工具 ({len(sessions)} 条)"
        self.combo_to_tool_id[all_label] = None
        tool_options = [all_label]
        selected_index = 0

        for idx, t in enumerate(detected_tools, 1):
            cnt = tool_counts.get(t['tool_id'], 0)
            opt_str = f"{t['icon']} {t['tool_name']} ({cnt} 条)"
            tool_options.append(opt_str)
            self.combo_to_tool_id[opt_str] = t['tool_id']
            if prev_tool_id and t['tool_id'] == prev_tool_id:
                selected_index = idx

        self.tool_combo["values"] = tool_options
        self.tool_combo.current(selected_index)

        self.status_header_lbl.config(
            text=f"已发现 {len(detected_tools)} 个 AI 平台，共 {len(sessions)} 条历史记录"
        )
        self.apply_filter()

    def apply_filter(self):
        kw = self.search_var.get().strip()
        tool_id = self._extract_selected_tool_id() or ""

        self.displayed_sessions = self.scanner.filter_sessions(
            self.all_sessions,
            keyword=kw,
            tool_id=tool_id
        )

        self.tree.delete(*self.tree.get_children())
        self.row_to_session.clear()

        for idx, s in enumerate(self.displayed_sessions, 1):
            chk = "☑" if s.session_id in self.selected_session_ids else "☐"
            row_iid = f"row_{idx}_{s.tool_id}_{s.session_id}"
            self.row_to_session[row_iid] = s

            self.tree.insert(
                "",
                tk.END,
                iid=row_iid,
                values=(
                    chk,
                    f"{s.source_tool}",
                    s.title,
                    s.formatted_created_at,
                    s.message_count if s.message_count > 0 else "-",
                    s.workspace_path or "-"
                )
            )

        selected_count = sum(1 for s in self.displayed_sessions if s.session_id in self.selected_session_ids)
        self.count_badge_lbl.config(text=f"显示: {len(self.displayed_sessions)} 条 / 已选: {selected_count} 条")

        if not self.displayed_sessions:
            self.preview_title_lbl.config(text="💬 无匹配会话")
            self.preview_meta_lbl.config(text="")
            for pt in (self.preview_full_text, self.preview_clean_text):
                pt.delete("1.0", tk.END)
                pt.insert(
                    tk.END,
                    "ℹ️ 当前筛选条件下未找到任何历史会话记录。\n\n"
                    "可能原因：\n"
                    "1. 该工具尚未在本机生成本地历史数据；\n"
                    "2. 搜索关键词未匹配到标题或工作区；\n"
                    "3. 聊天记录存储在其他路径或未开启本地会话存储功能。\n",
                    "notice"
                )

    def _on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            row_iid = self.tree.identify_row(event.y)
            if column == "#1" and row_iid and row_iid in self.row_to_session:
                session = self.row_to_session[row_iid]
                sid = session.session_id
                if sid in self.selected_session_ids:
                    self.selected_session_ids.remove(sid)
                else:
                    self.selected_session_ids.add(sid)

                chk = "☑" if sid in self.selected_session_ids else "☐"
                vals = list(self.tree.item(row_iid, "values"))
                vals[0] = chk
                self.tree.item(row_iid, values=vals)

                selected_count = sum(1 for s in self.displayed_sessions if s.session_id in self.selected_session_ids)
                self.count_badge_lbl.config(text=f"显示: {len(self.displayed_sessions)} 条 / 已选: {selected_count} 条")

    def _on_tree_select(self, event):
        selected_items = self.tree.selection()
        if not selected_items:
            return
        row_iid = selected_items[0]
        session = self.row_to_session.get(row_iid)
        if session:
            self._load_and_preview_session(session)

    def _load_and_preview_session(self, session: UnifiedSession):
        self.preview_title_lbl.config(text=f"💬 {session.title[:50]}")
        self.preview_meta_lbl.config(
            text=f"平台: {session.source_tool}  |  时间: {session.formatted_created_at}  |  工作区: {session.workspace_path or '无'}"
        )

        def _do_load():
            full = self.scanner.load_detail(session)
            self.current_loaded_session = full
            self.after(0, lambda: self._render_both_previews(full))

        threading.Thread(target=_do_load, daemon=True).start()

    def _render_both_previews(self, session: UnifiedSession):
        # 1. 渲染完整预览 (Tab 1)
        self.preview_full_text.delete("1.0", tk.END)
        if not session.messages:
            self.preview_full_text.insert(tk.END, "(该会话暂无消息记录或为元数据占位)\n", "thinking")
        else:
            for idx, msg in enumerate(session.messages, 1):
                if msg.role == "user":
                    self.preview_full_text.insert(tk.END, f"👤 User #{idx}:\n", "role_user")
                    self.preview_full_text.insert(tk.END, f"{msg.content}\n\n")
                elif msg.role == "assistant":
                    self.preview_full_text.insert(tk.END, f"🤖 Assistant #{idx}:\n", "role_assistant")
                    if msg.thinking:
                        self.preview_full_text.insert(tk.END, f"🧠 思考过程:\n{msg.thinking.strip()}\n\n", "thinking")
                    if msg.content:
                        self.preview_full_text.insert(tk.END, f"{msg.content}\n\n")
                    if msg.tool_calls:
                        self.preview_full_text.insert(tk.END, f"🛠️ 工具调用 ({len(msg.tool_calls)} 项):\n", "tools")
                        for tc in msg.tool_calls:
                            summary_str = tc.tool_summary or "执行工具"
                            self.preview_full_text.insert(tk.END, f"  - {tc.tool_name}: {summary_str}\n", "tools")
                        self.preview_full_text.insert(tk.END, "\n")
                elif msg.role == "system":
                    self.preview_full_text.insert(tk.END, f"⚙️ System #{idx}:\n", "role_system")
                    self.preview_full_text.insert(tk.END, f"{msg.content[:300]}...\n\n", "thinking")

        # 2. 渲染极简 Token 优化预览 (Tab 2)
        self.preview_clean_text.delete("1.0", tk.END)
        clean_text = self.clean_exporter.generate_clean_markdown(session)
        if not clean_text or not session.messages:
            self.preview_clean_text.insert(tk.END, "(该会话暂无可提炼的问答内容)\n", "thinking")
        else:
            self.preview_clean_text.insert(tk.END, clean_text)

    def copy_current_preview(self):
        """一键将当前激活选项卡的预览内容复制到系统剪贴板（静默无弹窗干扰）"""
        current_tab_idx = self.notebook.index(self.notebook.select())
        if current_tab_idx == 0:
            content = self.preview_full_text.get("1.0", tk.END).strip()
            mode_name = "完整原始对话"
        else:
            content = self.preview_clean_text.get("1.0", tk.END).strip()
            mode_name = "极简 Token 优化文本"

        if not content:
            self.status_header_lbl.config(text="⚠️ 当前没有可复制的文本内容")
            return

        self.clipboard_clear()
        self.clipboard_append(content)
        self.status_header_lbl.config(text=f"✅ 已复制【{mode_name}】到剪贴板，可直接粘贴！")

    def select_all(self):
        for s in self.displayed_sessions:
            self.selected_session_ids.add(s.session_id)
        self.apply_filter()

    def deselect_all(self):
        for s in self.displayed_sessions:
            self.selected_session_ids.discard(s.session_id)
        self.apply_filter()

    def browse_export_dir(self):
        dir_selected = filedialog.askdirectory(initialdir=self.export_dir_var.get())
        if dir_selected:
            self.export_dir_var.set(dir_selected)

    def open_export_dir(self):
        out_dir = self.export_dir_var.get()
        if os.path.exists(out_dir):
            if sys.platform == "win32":
                os.startfile(out_dir)
            else:
                subprocess.Popen(["xdg-open", out_dir])
        else:
            messagebox.showinfo("提示", "导出目录尚未创建，请先执行导出。")

    def start_export(self):
        target_sessions = [s for s in self.all_sessions if s.session_id in self.selected_session_ids]
        if not target_sessions:
            messagebox.showwarning("提示", "请至少勾选一个会话后再执行导出。")
            return

        formats = []
        if self.fmt_md_var.get(): formats.append("md")
        if self.fmt_html_var.get(): formats.append("html")
        if self.fmt_json_var.get(): formats.append("json")
        if self.fmt_clean_md_var.get(): formats.append("clean_md")
        if self.fmt_clean_txt_var.get(): formats.append("clean_txt")

        if not formats:
            messagebox.showwarning("提示", "请至少选择一种导出格式（如极简 Markdown、HTML 等）。")
            return

        out_dir = os.path.abspath(self.export_dir_var.get())
        self.btn_export.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_header_lbl.config(text=f"正在导出 {len(target_sessions)} 条会话...")

        def _do_export():
            md_exp = MarkdownExporter() if "md" in formats else None
            html_exp = HTMLExporter() if "html" in formats else None
            json_exp = JSONExporter() if "json" in formats else None
            clean_exp = CleanTextExporter() if ("clean_md" in formats or "clean_txt" in formats) else None
            index_exp = IndexExporter()

            exported_records = []
            total = len(target_sessions)

            for i, s in enumerate(target_sessions, 1):
                full_s = self.scanner.load_detail(s)
                rec = {"session": full_s}
                sub_dir = os.path.join(out_dir, full_s.tool_id)

                if md_exp:
                    mp = md_exp.export(full_s, sub_dir)
                    rec["md_path"] = os.path.relpath(mp, out_dir)
                if html_exp:
                    hp = html_exp.export(full_s, sub_dir)
                    rec["html_path"] = os.path.relpath(hp, out_dir)
                if json_exp:
                    jp = json_exp.export(full_s, sub_dir)
                    rec["json_path"] = os.path.relpath(jp, out_dir)
                if clean_exp and "clean_md" in formats:
                    cmp = clean_exp.export_clean_markdown(full_s, sub_dir)
                    rec["clean_md_path"] = os.path.relpath(cmp, out_dir)
                if clean_exp and "clean_txt" in formats:
                    ctp = clean_exp.export_clean_text(full_s, sub_dir)
                    rec["clean_txt_path"] = os.path.relpath(ctp, out_dir)

                exported_records.append(rec)
                pct = (i / total) * 100
                self.after(0, lambda p=pct: self.progress_var.set(p))

            index_exp.export(exported_records, out_dir)

            self.after(0, lambda: self._on_export_complete(len(exported_records), out_dir))

        threading.Thread(target=_do_export, daemon=True).start()

    def _on_export_complete(self, count: int, out_dir: str):
        """导出完成：静默刷新状态栏与进度条，无弹窗打扰用户"""
        self.btn_export.config(state=tk.NORMAL)
        self.progress_var.set(100)
        self.status_header_lbl.config(
            text=f"🎉 导出完成！已成功导出 {count} 条会话至目标目录"
        )


def run_gui():
    app = ExporterGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
