"""
Markdown 导出器 (Markdown Exporter)
将 UnifiedSession 导出为排版优美、支持折叠思考过程和工具调用的标准 Markdown 文档
"""

import os
import re
import json
from typing import Optional

try:
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall
except (ImportError, ValueError):
    from ..core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall


class MarkdownExporter:
    """Markdown 导出器"""

    @staticmethod
    def sanitize_filename(name: str, max_len: int = 40) -> str:
        clean = re.sub(r'[\\/*?:"<>|\r\n\t]', "_", name).strip()
        clean = re.sub(r'_+', '_', clean)
        clean = clean.strip("._ ")
        if not clean:
            clean = "untitled"
        return clean[:max_len]

    def export(self, session: UnifiedSession, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)

        date_prefix = session.created_at.strftime("%Y%m%d_%H%M") if session.created_at else "nodate"
        safe_title = self.sanitize_filename(session.title)
        sid_short = session.session_id[:8]
        filename = f"{date_prefix}_{session.tool_id}_{sid_short}_{safe_title}.md"
        filepath = os.path.join(output_dir, filename)

        md_lines = []

        # 1. YAML Frontmatter
        md_lines.append("---")
        md_lines.append(f'title: "{session.title.replace(chr(34), chr(39))}"')
        md_lines.append(f'tool: "{session.source_tool}"')
        md_lines.append(f'tool_id: "{session.tool_id}"')
        md_lines.append(f'session_id: "{session.session_id}"')
        md_lines.append(f'created_at: "{session.formatted_created_at}"')
        if session.workspace_path:
            md_lines.append(f'workspace: "{session.workspace_path.replace(chr(92), "/")}"')
        md_lines.append(f'message_count: {session.message_count}')
        md_lines.append("---")
        md_lines.append("")

        # 2. 会话大标题与元信息徽章
        md_lines.append(f"# 💬 {session.title}")
        md_lines.append("")
        badges = [
            f"🤖 **工具**: `{session.source_tool}`",
            f"📅 **时间**: `{session.formatted_created_at}`",
        ]
        if session.workspace_path:
            badges.append(f"📁 **工作区**: `{session.workspace_path}`")
        badges.append(f"🔢 **消息数**: `{session.message_count}`")

        md_lines.append("> " + " | ".join(badges))
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

        # 3. 对话正文
        if not session.messages:
            md_lines.append("*（该会话暂无文本消息记录）*")
            md_lines.append("")

        for idx, msg in enumerate(session.messages, 1):
            if msg.role == "user":
                md_lines.append(f"## 👤 User #{idx}")
                md_lines.append("")
                md_lines.append(msg.content.strip() if msg.content else "*（空消息）*")
                md_lines.append("")
                md_lines.append("---")
                md_lines.append("")

            elif msg.role == "assistant":
                md_lines.append(f"## 🤖 Assistant #{idx}")
                md_lines.append("")

                # 折叠展示思考过程 / Reasoning
                if msg.thinking:
                    md_lines.append("<details>")
                    md_lines.append("<summary>🧠 <b>思考过程 (Thinking / Reasoning)</b> - 点击展开</summary>")
                    md_lines.append("")
                    md_lines.append("> " + msg.thinking.strip().replace("\n", "\n> "))
                    md_lines.append("")
                    md_lines.append("</details>")
                    md_lines.append("")

                # 助手核心回复
                if msg.content:
                    md_lines.append(msg.content.strip())
                    md_lines.append("")

                # 折叠展示工具调用详情
                if msg.tool_calls:
                    md_lines.append("<details>")
                    md_lines.append(f"<summary>🛠️ <b>工具调用记录 ({len(msg.tool_calls)} 项操作)</b> - 点击展开</summary>")
                    md_lines.append("")
                    for tidx, tool in enumerate(msg.tool_calls, 1):
                        md_lines.append(f"#### `{tidx}.` `{tool.tool_name}`: {tool.tool_summary or '执行操作'}")
                        if tool.arguments:
                            md_lines.append("```json")
                            md_lines.append(json.dumps(tool.arguments, ensure_ascii=False, indent=2))
                            md_lines.append("```")
                        if tool.output:
                            md_lines.append("**输出结果:**")
                            md_lines.append("```text")
                            md_lines.append(tool.output[:1500] + ("\n...(截断)..." if len(tool.output) > 1500 else ""))
                            md_lines.append("```")
                        md_lines.append("")
                    md_lines.append("</details>")
                    md_lines.append("")

                md_lines.append("---")
                md_lines.append("")

            elif msg.role == "system":
                md_lines.append(f"## ⚙️ System Prompt #{idx}")
                md_lines.append("")
                md_lines.append("<details>")
                md_lines.append("<summary>系统上下文提示词 - 点击展开</summary>")
                md_lines.append("")
                md_lines.append(msg.content.strip())
                md_lines.append("")
                md_lines.append("</details>")
                md_lines.append("")
                md_lines.append("---")
                md_lines.append("")

        # 4. 产物列表 (Artifacts)
        if session.artifacts:
            md_lines.append("## 📦 会话生成产物与文件 (Artifacts)")
            md_lines.append("")
            for art in session.artifacts:
                md_lines.append(f"### 📄 `{art.title}`")
                if art.content:
                    ext = art.title.split(".")[-1] if "." in art.title else "text"
                    md_lines.append(f"```{ext}")
                    md_lines.append(art.content[:3000] + ("\n...(截断)..." if len(art.content) > 3000 else ""))
                    md_lines.append("```")
                md_lines.append("")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        return filepath
