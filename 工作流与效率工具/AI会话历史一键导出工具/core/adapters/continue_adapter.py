"""
Continue 插件适配器
解析 ~/.continue/sessions/*.json 下的开源 AI 编程助手会话
"""

import os
import glob
import json
from datetime import datetime
from typing import List, Optional

try:
    from core.adapters.base_adapter import BaseAdapter
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact
except (ImportError, ValueError):
    from .base_adapter import BaseAdapter
    from ..models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact


class ContinueAdapter(BaseAdapter):
    tool_id = "continue"
    tool_name = "Continue"
    icon = "⏩"
    description = "开源 AI 编程插件 Continue 的本地对话历史"

    def get_sessions_dir(self) -> str:
        return os.path.join(self.home, ".continue", "sessions")

    def detect(self) -> bool:
        sdir = self.get_sessions_dir()
        return os.path.exists(sdir) and bool(os.listdir(sdir))

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        sdir = self.get_sessions_dir()
        if not os.path.exists(sdir):
            return sessions

        for fname in os.listdir(sdir):
            if not fname.endswith(".json"):
                continue

            fpath = os.path.join(sdir, fname)
            session_id = fname[:-5]
            title = f"Continue 会话 {session_id[:8]}"
            workspace_path = ""

            try:
                mtime = os.path.getmtime(fpath)
                updated_at = datetime.fromtimestamp(mtime)
                created_at = datetime.fromtimestamp(os.path.getctime(fpath))
            except Exception:
                created_at = datetime.now()
                updated_at = created_at

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        if data.get("title"):
                            title = data.get("title")
                        if data.get("workspaceDirectory"):
                            workspace_path = data.get("workspaceDirectory")
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
                raw_source_path=fpath
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
                data = json.load(f)

            history = data.get("history") or data.get("messages") or []
            if isinstance(history, list):
                for item in history:
                    if not isinstance(item, dict):
                        continue
                    m = item.get("message", item)
                    role = m.get("role", "user")
                    content = m.get("content") or m.get("text") or ""
                    if isinstance(content, list):
                        parts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
                        content = "\n".join(parts)
                    messages.append(UnifiedMessage(
                        role="user" if role in ("user", "human") else "assistant",
                        content=str(content)
                    ))
        except Exception:
            pass

        session.messages = messages
        return session
