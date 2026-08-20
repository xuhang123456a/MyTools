"""
汇总索引生成器 (Index Exporter)
生成全局会话导航主页 INDEX.md 与 index.html，方便按工具/时间检索与快速跳转
"""

import os
import html
from datetime import datetime
from typing import List, Dict, Any

try:
    from core.models import UnifiedSession
except (ImportError, ValueError):
    from ..core.models import UnifiedSession


class IndexExporter:
    """汇总索引生成器"""

    def export(self, exported_items: List[Dict[str, Any]], output_dir: str):
        """
        exported_items 每个元素格式:
        {
            "session": UnifiedSession,
            "md_path": str (相对路径),
            "html_path": str (相对路径),
            "json_path": str (相对路径),
            "clean_md_path": str (相对路径),
            "clean_txt_path": str (相对路径),
        }
        """
        os.makedirs(output_dir, exist_ok=True)
        self._export_markdown_index(exported_items, output_dir)
        self._export_html_index(exported_items, output_dir)

    def _export_markdown_index(self, items: List[Dict[str, Any]], output_dir: str):
        filepath = os.path.join(output_dir, "INDEX.md")
        lines = []

        lines.append("# 🧰 本地 AI 会话历史归档总览")
        lines.append("")
        lines.append(f"> 📅 **导出时间**: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}` | 🔢 **会话总数**: `{len(items)}` 个")
        lines.append("")

        # 统计各工具分布
        tool_counts: Dict[str, int] = {}
        for it in items:
            tname = it["session"].source_tool
            tool_counts[tname] = tool_counts.get(tname, 0) + 1

        lines.append("### 📊 工具统计")
        lines.append("")
        for tname, cnt in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{tname}**: `{cnt}` 条会话")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("### 📑 会话归档清单")
        lines.append("")
        lines.append("| 序号 | AI 工具 | 会话标题 | 创建时间 | 消息数 | 工作区 / 项目 | 导出文件 |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for idx, it in enumerate(items, 1):
            s: UnifiedSession = it["session"]
            link_parts = []
            if it.get("md_path"):
                link_parts.append(f"[Markdown]({it['md_path'].replace(chr(92), '/')})")
            if it.get("html_path"):
                link_parts.append(f"[HTML]({it['html_path'].replace(chr(92), '/')})")
            if it.get("clean_md_path"):
                link_parts.append(f"[精简版]({it['clean_md_path'].replace(chr(92), '/')})")
            if it.get("json_path"):
                link_parts.append(f"[JSON]({it['json_path'].replace(chr(92), '/')})")

            links = " / ".join(link_parts)
            safe_title = s.title.replace("|", "-")
            ws_show = f"`{s.workspace_path}`" if s.workspace_path else "-"
            lines.append(f"| {idx} | `{s.source_tool}` | **{safe_title}** | `{s.formatted_created_at}` | `{s.message_count}` | {ws_show} | {links} |")

        lines.append("")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _export_html_index(self, items: List[Dict[str, Any]], output_dir: str):
        filepath = os.path.join(output_dir, "index.html")

        tool_counts: Dict[str, int] = {}
        for it in items:
            tname = it["session"].source_tool
            tool_counts[tname] = tool_counts.get(tname, 0) + 1

        rows_html = []
        for idx, it in enumerate(items, 1):
            s: UnifiedSession = it["session"]
            md_rel = it.get("md_path", "").replace("\\", "/")
            html_rel = it.get("html_path", "").replace("\\", "/")
            clean_md_rel = it.get("clean_md_path", "").replace("\\", "/")
            json_rel = it.get("json_path", "").replace("\\", "/")

            links_html = []
            if html_rel:
                links_html.append(f'<a href="{html_rel}" class="btn-link" target="_blank">🌐 网页</a>')
            if md_rel:
                links_html.append(f'<a href="{md_rel}" class="btn-link" target="_blank">📄 Markdown</a>')
            if clean_md_rel:
                links_html.append(f'<a href="{clean_md_rel}" class="btn-link clean-btn" target="_blank">✨ 精简版</a>')
            if json_rel:
                links_html.append(f'<a href="{json_rel}" class="btn-link" target="_blank">📦 JSON</a>')

            rows_html.append(f"""
            <tr data-tool="{html.escape(s.tool_id)}" data-title="{html.escape(s.title.lower())}">
              <td>{idx}</td>
              <td><span class="badge">{html.escape(s.source_tool)}</span></td>
              <td class="session-title"><b>{html.escape(s.title)}</b></td>
              <td>{s.formatted_created_at}</td>
              <td><span class="msg-badge">{s.message_count}</span></td>
              <td class="ws-path">{html.escape(s.workspace_path or '-')}</td>
              <td><div class="action-links">{"".join(links_html)}</div></td>
            </tr>
            """)

        tool_filter_btns = ['<button class="filter-btn active" onclick="filterByTool(\'all\', this)">全部 (' + str(len(items)) + ')</button>']
        for it in items:
            t_id = it["session"].tool_id
            t_name = it["session"].source_tool
            btn_html = f'<button class="filter-btn" onclick="filterByTool(\'{t_id}\', this)">{html.escape(t_name)} ({tool_counts[t_name]})</button>'
            if btn_html not in tool_filter_btns:
                tool_filter_btns.append(btn_html)

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>本地 AI 会话历史归档导航</title>
<style>
:root {{
  --bg-color: #0f172a;
  --card-bg: #1e293b;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --border-color: #334155;
  --accent-color: #38bdf8;
  --clean-color: #10b981;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: var(--bg-color);
  color: var(--text-primary);
  line-height: 1.6;
  padding: 24px 16px 80px 16px;
}}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 16px;
}}
h1 {{ font-size: 1.6rem; color: var(--accent-color); }}
.search-bar {{
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}}
.search-input {{
  background: var(--card-bg);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 0.9rem;
  width: 280px;
}}
.filter-btn {{
  background: var(--card-bg);
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 0.85rem;
}}
.filter-btn.active, .filter-btn:hover {{
  color: var(--accent-color);
  border-color: var(--accent-color);
  background: rgba(56,189,248,0.1);
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: var(--card-bg);
  border-radius: 12px;
  overflow: hidden;
}}
th, td {{
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.9rem;
}}
th {{ background: rgba(0,0,0,0.2); color: var(--text-secondary); font-weight: 600; }}
tr:hover {{ background: rgba(255,255,255,0.03); }}
.badge {{
  background: rgba(56,189,248,0.15);
  color: var(--accent-color);
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.8rem;
}}
.msg-badge {{
  background: rgba(255,255,255,0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.8rem;
}}
.session-title {{ max-width: 320px; }}
.ws-path {{ max-width: 200px; font-family: monospace; font-size: 0.8rem; color: var(--text-secondary); word-break: break-all; }}
.action-links {{ display: flex; gap: 6px; flex-wrap: wrap; }}
.btn-link {{
  text-decoration: none;
  background: rgba(255,255,255,0.08);
  color: var(--text-primary);
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.75rem;
}}
.btn-link:hover {{ background: var(--accent-color); color: #000; }}
.clean-btn {{ border: 1px solid var(--clean-color); color: var(--clean-color); }}
.clean-btn:hover {{ background: var(--clean-color); color: #000; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>🧰 本地 AI 会话历史归档导航</h1>
      <p style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 4px;">共收录 {len(items)} 条已导出会话记录</p>
    </div>
  </div>

  <div class="search-bar">
    <input type="text" class="search-input" placeholder="🔍 搜索会话标题或项目路径..." oninput="filterTable(this.value)">
    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
      {"".join(tool_filter_btns)}
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th width="40">#</th>
        <th width="140">AI 工具</th>
        <th>会话标题</th>
        <th width="140">创建时间</th>
        <th width="70">消息数</th>
        <th width="200">关联项目</th>
        <th width="200">导出文件</th>
      </tr>
    </thead>
    <tbody id="tableBody">
      {"".join(rows_html)}
    </tbody>
  </table>
</div>

<script>
let currentTool = 'all';
let currentQuery = '';

function filterByTool(toolId, btn) {{
  currentTool = toolId;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}}

function filterTable(query) {{
  currentQuery = query.toLowerCase().trim();
  applyFilters();
}}

function applyFilters() {{
  document.querySelectorAll('#tableBody tr').forEach(row => {{
    const rowTool = row.getAttribute('data-tool');
    const rowTitle = row.innerText.toLowerCase();
    const matchTool = (currentTool === 'all' || rowTool === currentTool);
    const matchQuery = (!currentQuery || rowTitle.includes(currentQuery));
    row.style.display = (matchTool && matchQuery) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
