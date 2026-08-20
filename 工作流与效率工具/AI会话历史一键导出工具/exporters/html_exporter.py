"""
HTML 独立网页导出器 (HTML Exporter)
生成零外部依赖、自包含 CSS/JS 的现代化单文件暗黑/亮色 AI 聊天对话页面
"""

import os
import re
import json
import html
from typing import Optional

try:
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall
except (ImportError, ValueError):
    from ..core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall


class HTMLExporter:
    """HTML 导出器"""

    @staticmethod
    def sanitize_filename(name: str, max_len: int = 40) -> str:
        clean = re.sub(r'[\\/*?:"<>|\r\n\t]', "_", name).strip()
        clean = re.sub(r'_+', '_', clean)
        clean = clean.strip("._ ")
        if not clean:
            clean = "untitled"
        return clean[:max_len]

    @staticmethod
    def format_text(text: str) -> str:
        """轻量级 Markdown 格式化为安全 HTML"""
        if not text:
            return ""
        escaped = html.escape(text)

        # 代码块 ```lang ... ```
        def code_block_sub(match):
            lang = match.group(1) or ""
            code_body = match.group(2)
            return (
                f'<div class="code-container">'
                f'<div class="code-header"><span>{lang or "code"}</span>'
                f'<button class="copy-btn" onclick="copyCode(this)">复制</button></div>'
                f'<pre><code>{code_body}</code></pre></div>'
            )

        escaped = re.sub(r'```([a-zA-Z0-9_-]*)\r?\n(.*?)```', code_block_sub, escaped, flags=re.DOTALL)

        # 行内代码 `...`
        escaped = re.sub(r'`([^`]+)`', r'<code>\1</code>', escaped)

        # 粗体 **...**
        escaped = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', escaped)

        # 换行处理（非代码块内部）
        paragraphs = escaped.split("\n\n")
        formatted_paragraphs = []
        for p in paragraphs:
            if "<div class=\"code-container\"" in p:
                formatted_paragraphs.append(p)
            else:
                formatted_paragraphs.append(f"<p>{p.replace(chr(10), '<br>')}</p>")

        return "".join(formatted_paragraphs)

    def export(self, session: UnifiedSession, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)

        date_prefix = session.created_at.strftime("%Y%m%d_%H%M") if session.created_at else "nodate"
        safe_title = self.sanitize_filename(session.title)
        sid_short = session.session_id[:8]
        filename = f"{date_prefix}_{session.tool_id}_{sid_short}_{safe_title}.html"
        filepath = os.path.join(output_dir, filename)

        messages_html = []
        for idx, msg in enumerate(session.messages, 1):
            is_user = (msg.role == "user")
            is_system = (msg.role == "system")
            role_class = "user-msg" if is_user else ("system-msg" if is_system else "assistant-msg")
            role_name = "👤 用户" if is_user else ("⚙️ 系统" if is_system else f"🤖 {session.source_tool}")

            msg_body = []

            # 思考链 / Reasoning
            if msg.thinking:
                msg_body.append(
                    f'<details class="thinking-box">'
                    f'<summary>🧠 思考过程 (Reasoning) · 点击展开</summary>'
                    f'<div class="thinking-content">{html.escape(msg.thinking)}</div>'
                    f'</details>'
                )

            # 正文内容
            if msg.content:
                msg_body.append(f'<div class="msg-text">{self.format_text(msg.content)}</div>')

            # 工具调用
            if msg.tool_calls:
                tools_html = []
                for tidx, tool in enumerate(msg.tool_calls, 1):
                    args_json = json.dumps(tool.arguments, ensure_ascii=False, indent=2)
                    output_text = tool.output[:1500] + ("\n...(截断)..." if len(tool.output) > 1500 else "")
                    tools_html.append(
                        f'<div class="tool-item">'
                        f'<div class="tool-name">⚡ <b>{html.escape(tool.tool_name)}</b>: {html.escape(tool.tool_summary or "")}</div>'
                        f'<pre class="tool-args"><code>{html.escape(args_json)}</code></pre>'
                        + (f'<pre class="tool-output"><code>{html.escape(output_text)}</code></pre>' if output_text else '')
                        + f'</div>'
                    )
                msg_body.append(
                    f'<details class="tools-box">'
                    f'<summary>🛠️ 工具调用记录 ({len(msg.tool_calls)} 项操作) · 点击展开</summary>'
                    f'<div class="tools-content">{"".join(tools_html)}</div>'
                    f'</details>'
                )

            messages_html.append(
                f'<div class="message-card {role_class}">'
                f'<div class="msg-header">'
                f'<span class="role-badge">{role_name}</span>'
                f'<span class="msg-index">#{idx}</span>'
                f'</div>'
                f'<div class="msg-content">{"".join(msg_body)}</div>'
                f'</div>'
            )

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(session.title)} - AI 会话导出</title>
<style>
:root {{
  --bg-color: #0f172a;
  --card-bg: #1e293b;
  --user-bg: #1e3a8a;
  --assistant-bg: #1e293b;
  --system-bg: #334155;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --border-color: #334155;
  --accent-color: #38bdf8;
  --code-bg: #0f172a;
  --thinking-bg: #1e1e38;
  --tool-bg: #182234;
}}
[data-theme="light"] {{
  --bg-color: #f1f5f9;
  --card-bg: #ffffff;
  --user-bg: #e0e7ff;
  --assistant-bg: #ffffff;
  --system-bg: #f8fafc;
  --text-primary: #0f172a;
  --text-secondary: #64748b;
  --border-color: #cbd5e1;
  --accent-color: #2563eb;
  --code-bg: #f8fafc;
  --thinking-bg: #f5f3ff;
  --tool-bg: #f0fdf4;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background-color: var(--bg-color);
  color: var(--text-primary);
  line-height: 1.6;
  padding-bottom: 60px;
  transition: background-color 0.2s;
}}
.container {{
  max-width: 960px;
  margin: 0 auto;
  padding: 20px 16px;
}}
.top-header {{
  position: sticky;
  top: 0;
  background: var(--bg-color);
  border-bottom: 1px solid var(--border-color);
  padding: 16px 0;
  z-index: 100;
  margin-bottom: 24px;
}}
.header-content {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}}
.title-area h1 {{
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--accent-color);
  margin-bottom: 6px;
}}
.meta-badges {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 0.85rem;
}}
.badge {{
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  padding: 3px 10px;
  border-radius: 999px;
  color: var(--text-secondary);
}}
.btn {{
  background: var(--card-bg);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}}
.btn:hover {{ border-color: var(--accent-color); }}
.search-input {{
  background: var(--card-bg);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  width: 200px;
}}
.message-card {{
  border-radius: 12px;
  border: 1px solid var(--border-color);
  margin-bottom: 20px;
  padding: 16px 20px;
  background: var(--card-bg);
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}}
.user-msg {{
  background: var(--user-bg);
  border-left: 4px solid var(--accent-color);
}}
.assistant-msg {{
  background: var(--assistant-bg);
}}
.system-msg {{
  background: var(--system-bg);
  opacity: 0.85;
}}
.msg-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}}
.role-badge {{
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--accent-color);
}}
.msg-index {{
  font-size: 0.8rem;
  color: var(--text-secondary);
}}
.msg-text p {{ margin-bottom: 12px; }}
.code-container {{
  background: var(--code-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin: 12px 0;
  overflow: hidden;
}}
.code-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: rgba(0,0,0,0.2);
  border-bottom: 1px solid var(--border-color);
  font-size: 0.8rem;
  color: var(--text-secondary);
}}
.copy-btn {{
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.75rem;
}}
.copy-btn:hover {{ color: var(--accent-color); border-color: var(--accent-color); }}
pre {{
  padding: 12px;
  overflow-x: auto;
  font-family: Consolas, Monaco, "Courier New", monospace;
  font-size: 0.9rem;
}}
code {{
  font-family: Consolas, Monaco, "Courier New", monospace;
  background: rgba(125,125,125,0.15);
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 0.88em;
}}
details {{
  background: rgba(0,0,0,0.1);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin: 12px 0;
  padding: 10px 14px;
}}
summary {{
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--accent-color);
}}
.thinking-box {{ background: var(--thinking-bg); }}
.thinking-content {{
  margin-top: 10px;
  white-space: pre-wrap;
  font-size: 0.88rem;
  color: var(--text-secondary);
}}
.tools-box {{ background: var(--tool-bg); }}
.tool-item {{
  margin: 10px 0;
  padding: 10px;
  border-left: 3px solid var(--accent-color);
  background: rgba(0,0,0,0.1);
}}
.tool-name {{ font-size: 0.85rem; margin-bottom: 6px; }}
.tool-args, .tool-output {{ margin: 6px 0; max-height: 200px; overflow-y: auto; }}
</style>
</head>
<body>
<div class="top-header">
  <div class="container header-content">
    <div class="title-area">
      <h1>💬 {html.escape(session.title)}</h1>
      <div class="meta-badges">
        <span class="badge">🤖 {html.escape(session.source_tool)}</span>
        <span class="badge">📅 {session.formatted_created_at}</span>
        {f'<span class="badge">📁 {html.escape(session.workspace_path)}</span>' if session.workspace_path else ''}
        <span class="badge">🔢 共 {session.message_count} 条记录</span>
      </div>
    </div>
    <div style="display: flex; gap: 8px; align-items: center;">
      <input type="text" class="search-input" placeholder="在会话中搜索..." oninput="filterChat(this.value)">
      <button class="btn" onclick="toggleTheme()">🌓 切换主题</button>
    </div>
  </div>
</div>

<div class="container" id="chatContainer">
{"".join(messages_html)}
</div>

<script>
function toggleTheme() {{
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('ai_export_theme', next);
}}
if (localStorage.getItem('ai_export_theme') === 'light') {{
  document.documentElement.setAttribute('data-theme', 'light');
}}
function copyCode(btn) {{
  const pre = btn.parentElement.nextElementSibling;
  navigator.clipboard.writeText(pre.innerText).then(() => {{
    const original = btn.innerText;
    btn.innerText = '✓ 已复制';
    setTimeout(() => btn.innerText = original, 1500);
  }});
}}
function filterChat(query) {{
  const q = query.toLowerCase().trim();
  document.querySelectorAll('.message-card').forEach(card => {{
    if (!q || card.innerText.toLowerCase().includes(q)) {{
      card.style.display = 'block';
    }} else {{
      card.style.display = 'none';
    }}
  }});
}}
</script>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)

        return filepath
