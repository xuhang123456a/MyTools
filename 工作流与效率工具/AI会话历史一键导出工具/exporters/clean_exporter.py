"""
精简优化文本导出器 (Clean / Concise Text Exporter)
提炼高信噪比对话内容，剔除思维链、工具调用与系统冗余噪音，专供人眼快速阅读与 AI 二次分析 (RAG / 知识库 / Prompt 注入)
极致 Token 优化策略：剥离问候客套、系统注入标记、中间操作占位，仅保留关键问答骨架
"""

import os
import re
from typing import Optional

try:
    from core.models import UnifiedSession, UnifiedMessage
except (ImportError, ValueError):
    from ..core.models import UnifiedSession, UnifiedMessage


class CleanTextExporter:
    """精简对话文本生成器与导出器 (极简 Token 优化版)"""

    @staticmethod
    def sanitize_filename(name: str, max_len: int = 40) -> str:
        clean = re.sub(r'[\\/*?:"<>|\r\n\t]', "_", name).strip()
        clean = re.sub(r'_+', '_', clean)
        clean = clean.strip("._ ")
        if not clean:
            clean = "untitled"
        return clean[:max_len]

    @classmethod
    def clean_message_content(cls, content: str, role: str) -> str:
        """深度清洗消息内容中的系统注入噪音、目录转储与多余标记"""
        if not content:
            return ""

        text = content

        # 1. 剔除各种 AI 平台注入的 XML 与系统提示词标记
        text = re.sub(r"<system-reminder.*?>.*?</system-reminder>", "", text, flags=re.DOTALL)
        text = re.sub(r"<user_info.*?>.*?</user_info>", "", text, flags=re.DOTALL)
        text = re.sub(r"<identity_context.*?>.*?</identity_context>", "", text, flags=re.DOTALL)
        text = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", text, flags=re.DOTALL)
        text = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", text, flags=re.DOTALL)
        text = re.sub(r"<ide_opened_file>.*?</ide_opened_file>", "", text, flags=re.DOTALL)
        text = re.sub(r"<USER_REQUEST>(.*?)</USER_REQUEST>", r"\1", text, flags=re.DOTALL)

        # 2. 剔除 Antigravity / Agent 底层输出的目录转储与时间标记
        text = re.sub(r"Created At:.*?\nCompleted At:.*?\n", "", text)
        text = re.sub(r'\{"name":.*?"isDir":.*?\}\n?', "", text)
        text = re.sub(r"Summary: This directory contains.*?\n?", "", text)

        # 3. 剔除 Kiro / Claude 中间工具执行的占位提示
        text = re.sub(r"⚡ \*\*Kiro Agent 自动化任务处理\*\*.*?\n>", "", text)
        text = re.sub(r"✅ \*\*Kiro Agent 任务执行完成\*\*.*?\n>", "", text)
        text = re.sub(r"> 🤖 Kiro Agent 已自动分析工作区.*?\n?", "", text)
        text = re.sub(r"> 🆔 任务执行编号:.*?\n?", "", text)
        text = re.sub(r"\*（AI 执行了相关工具操作.*?）\*", "", text)

        # 4. 剥离无意义的开场白与结尾客套话（节省大量 Token）
        text = re.sub(
            r"^(好的[，！~]?|收到[！~]?|没问题[，！~]?|当然可以[，！~]?|理解了[，！~]?|下面是.*?：|这是.*?：)\s*",
            "",
            text.strip()
        )
        text = re.sub(
            r"\s*(希望(以上|这些|这个|此回答).*?(帮助|参考|满意).*?|如有(任何)?(疑问|问题|需要).*?$|如果你还有其他.*?$|有需要随时叫我.*?$)\s*$",
            "",
            text.strip()
        )

        # 5. 压缩多余空行与行尾空格
        lines = [line.rstrip() for line in text.split("\n")]
        cleaned_lines = []
        consecutive_empty = 0
        for line in lines:
            if not line:
                consecutive_empty += 1
                if consecutive_empty <= 1:
                    cleaned_lines.append("")
            else:
                consecutive_empty = 0
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    @classmethod
    def generate_clean_markdown(cls, session: UnifiedSession) -> str:
        """生成极简高信噪比 Markdown（专供 LLM 上下文注入与极速人眼阅读）"""
        md_lines = []

        # 极简单行头部（仅占用约 10~15 tokens）
        date_str = session.created_at.strftime("%Y-%m-%d") if session.created_at else ""
        md_lines.append(f"# {session.title} ({session.source_tool} · {date_str})")
        md_lines.append("")

        q_idx = 1
        for msg in session.messages:
            clean_text = cls.clean_message_content(msg.content, msg.role)

            if msg.role == "user":
                # 跳过单纯表示继续的无意义交互
                if not clean_text or clean_text in ("继续", "continue", "go on", "好", "好的", "ok", "OK", "再试一次"):
                    continue
                md_lines.append(f"**Q{q_idx}**: {clean_text}")
                md_lines.append("")
                q_idx += 1

            elif msg.role == "assistant":
                # 过滤完全无实质文本回复的消息
                if not clean_text or clean_text in ("On it.", "On it"):
                    continue
                a_idx = q_idx - 1 if q_idx > 1 else 1
                md_lines.append(f"**A{a_idx}**: {clean_text}")
                md_lines.append("")

        return "\n".join(md_lines).strip()

    @classmethod
    def generate_clean_text(cls, session: UnifiedSession) -> str:
        """生成极简纯文本格式 (纯 Q&A 键值对，Token 消耗降到最低)"""
        txt_lines = []
        date_str = session.created_at.strftime("%Y-%m-%d") if session.created_at else ""
        txt_lines.append(f"【会话】{session.title} ({session.source_tool} {date_str})")
        txt_lines.append("-" * 40)

        q_idx = 1
        for msg in session.messages:
            clean_text = cls.clean_message_content(msg.content, msg.role)

            if msg.role == "user":
                if not clean_text or clean_text in ("继续", "continue", "go on", "好", "好的", "ok", "OK"):
                    continue
                txt_lines.append(f"[Q{q_idx}]: {clean_text}")
                txt_lines.append("")
                q_idx += 1

            elif msg.role == "assistant":
                if not clean_text or clean_text in ("On it.", "On it"):
                    continue
                a_idx = q_idx - 1 if q_idx > 1 else 1
                txt_lines.append(f"[A{a_idx}]: {clean_text}")
                txt_lines.append("")

        return "\n".join(txt_lines).strip()

    def export_clean_markdown(self, session: UnifiedSession, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        date_prefix = session.created_at.strftime("%Y%m%d_%H%M") if session.created_at else "nodate"
        safe_title = self.sanitize_filename(session.title)
        sid_short = session.session_id[:8]
        filename = f"{date_prefix}_{session.tool_id}_{sid_short}_{safe_title}.clean.md"
        filepath = os.path.join(output_dir, filename)

        content = self.generate_clean_markdown(session)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def export_clean_text(self, session: UnifiedSession, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        date_prefix = session.created_at.strftime("%Y%m%d_%H%M") if session.created_at else "nodate"
        safe_title = self.sanitize_filename(session.title)
        sid_short = session.session_id[:8]
        filename = f"{date_prefix}_{session.tool_id}_{sid_short}_{safe_title}.clean.txt"
        filepath = os.path.join(output_dir, filename)

        content = self.generate_clean_text(session)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath
