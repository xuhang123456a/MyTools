"""
Claude Code / CLI 适配器
深度解析 ~/.claude/projects/ 下的项目会话与 Agent 对话流
"""

import os
import glob
import json
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    from core.adapters.base_adapter import BaseAdapter
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact
except (ImportError, ValueError):
    from .base_adapter import BaseAdapter
    from ..models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact


class ClaudeCodeAdapter(BaseAdapter):
    tool_id = "claude_code"
    tool_name = "Claude Code / CLI"
    icon = "🧠"
    description = "Anthropic Claude Code CLI 命令行助手与 Agent 历史"

    def get_claude_dir(self) -> str:
        return os.path.join(self.home, ".claude")

    def detect(self) -> bool:
        cdir = self.get_claude_dir()
        if not os.path.exists(cdir):
            return False
        pdir = os.path.join(cdir, "projects")
        return os.path.exists(pdir) and bool(glob.glob(os.path.join(pdir, "*", "*.jsonl")))

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        cdir = self.get_claude_dir()
        pdir = os.path.join(cdir, "projects")
        if not os.path.exists(pdir):
            return sessions

        # 扫描 projects/<project_name>/<session_uuid>.jsonl
        for proj_folder in os.listdir(pdir):
            proj_path = os.path.join(pdir, proj_folder)
            if not os.path.isdir(proj_path):
                continue

            for fname in os.listdir(proj_path):
                if not fname.endswith(".jsonl"):
                    continue
                # 跳过 subagents 内部的辅助任务
                if "subagents" in fname or fname.startswith("."):
                    continue

                fpath = os.path.join(proj_path, fname)
                session_id = fname[:-6]

                try:
                    mtime = os.path.getmtime(fpath)
                    updated_at = datetime.fromtimestamp(mtime)
                    created_at = datetime.fromtimestamp(os.path.getctime(fpath))
                except Exception:
                    created_at = datetime.now()
                    updated_at = datetime.now()

                title = f"Claude 会话 {session_id[:8]}"
                workspace_path = ""
                msg_count_est = 0

                # 快速预读取标题与工作区
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        for idx in range(30):
                            line = f.readline()
                            if not line:
                                break
                            try:
                                obj = json.loads(line)
                                if obj.get("type") in ("user", "assistant"):
                                    msg_count_est += 1
                                if obj.get("cwd") and not workspace_path:
                                    workspace_path = obj.get("cwd")
                                if obj.get("type") == "ai-title" and obj.get("aiTitle"):
                                    title = obj.get("aiTitle")
                                elif obj.get("type") == "user" and title.startswith("Claude 会话"):
                                    m = obj.get("message", {})
                                    c = m.get("content") if isinstance(m, dict) else obj.get("content")
                                    if isinstance(c, str):
                                        c_clean = re.sub(r"<.*?>.*?</.*?>", "", c, flags=re.DOTALL).strip()
                                        if c_clean:
                                            title = c_clean.split("\n")[0][:60]
                                    elif isinstance(c, list):
                                        for it in c:
                                            if isinstance(it, dict) and it.get("text"):
                                                it_clean = re.sub(r"<.*?>.*?</.*?>", "", it["text"], flags=re.DOTALL).strip()
                                                if it_clean:
                                                    title = it_clean.split("\n")[0][:60]
                                                    break
                            except Exception:
                                continue
                except Exception:
                    pass

                session = UnifiedSession(
                    session_id=session_id,
                    source_tool=self.tool_name,
                    tool_id=self.tool_id,
                    title=title,
                    workspace_path=workspace_path,
                    created_at=created_at,
                    updated_at=updated_at,
                    raw_source_path=fpath,
                    estimated_msg_count=max(msg_count_est, 1),
                    metadata={"project_name": proj_folder}
                )
                sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        fpath = session.raw_source_path
        if not os.path.exists(fpath):
            return session

        messages: List[UnifiedMessage] = []

        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue

                    entry_type = obj.get("type")
                    msg_obj = obj.get("message", {})

                    if obj.get("cwd") and not session.workspace_path:
                        session.workspace_path = obj.get("cwd")

                    if entry_type == "ai-title" and obj.get("aiTitle"):
                        session.title = obj.get("aiTitle")

                    elif entry_type == "user" or (isinstance(msg_obj, dict) and msg_obj.get("role") == "user"):
                        raw_c = msg_obj.get("content") if isinstance(msg_obj, dict) else obj.get("content")
                        text_parts = []
                        if isinstance(raw_c, str):
                            text_parts.append(raw_c)
                        elif isinstance(raw_c, list):
                            for item in raw_c:
                                if isinstance(item, str):
                                    text_parts.append(item)
                                elif isinstance(item, dict) and item.get("text"):
                                    text_parts.append(item["text"])

                        clean_text = "\n".join(text_parts).strip()
                        clean_text = re.sub(r"<ide_opened_file>.*?</ide_opened_file>", "", clean_text, flags=re.DOTALL).strip()
                        if clean_text:
                            messages.append(UnifiedMessage(
                                role="user",
                                content=clean_text,
                                timestamp=session.created_at
                            ))

                    elif entry_type == "assistant" or (isinstance(msg_obj, dict) and msg_obj.get("role") == "assistant"):
                        raw_c = msg_obj.get("content") if isinstance(msg_obj, dict) else obj.get("content")
                        text_parts = []
                        thinking_parts = []
                        tool_calls = []

                        if isinstance(raw_c, str):
                            text_parts.append(raw_c)
                        elif isinstance(raw_c, list):
                            for item in raw_c:
                                if isinstance(item, str):
                                    text_parts.append(item)
                                elif isinstance(item, dict):
                                    itype = item.get("type")
                                    if itype == "text" and item.get("text"):
                                        text_parts.append(item["text"])
                                    elif itype == "thinking" and item.get("thinking"):
                                        thinking_parts.append(item["thinking"])
                                    elif itype == "tool_use":
                                        tool_calls.append(UnifiedToolCall(
                                            tool_name=item.get("name", "tool"),
                                            tool_summary=f"调用工具: {item.get('name')}",
                                            arguments=item.get("input", {}) if isinstance(item.get("input"), dict) else {"raw": item.get("input")}
                                        ))

                        final_text = "\n".join(text_parts).strip()
                        final_thinking = "\n\n".join(thinking_parts).strip()

                        if final_text or final_thinking or tool_calls:
                            messages.append(UnifiedMessage(
                                role="assistant",
                                content=final_text,
                                thinking=final_thinking,
                                tool_calls=tool_calls,
                                timestamp=session.updated_at
                            ))
        except Exception:
            pass

        session.messages = messages
        return session
