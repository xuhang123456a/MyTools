"""
Chatbox 客户端适配器
解析 AppData/Roaming/xyz.chatboxapp.app 下的会话备份与数据库
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


class ChatboxAdapter(BaseAdapter):
    tool_id = "chatbox"
    tool_name = "Chatbox"
    icon = "💬"
    description = "开源 AI 对话客户端 Chatbox 的本地备份与历史会话"

    def get_cb_dir(self) -> str:
        return os.path.join(self.appdata, "xyz.chatboxapp.app")

    def detect(self) -> bool:
        cb_dir = self.get_cb_dir()
        if not os.path.exists(cb_dir):
            return False
        backups = glob.glob(os.path.join(cb_dir, "config-backup-*.json"))
        for b in backups:
            try:
                with open(b, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                    threads = data.get("threads") or data.get("sessions") or data.get("conversations")
                    if threads:
                        return True
            except Exception:
                pass
        return False

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        cb_dir = self.get_cb_dir()
        if not os.path.exists(cb_dir):
            return sessions

        backups = sorted(glob.glob(os.path.join(cb_dir, "config-backup-*.json")), reverse=True)
        if not backups:
            return sessions

        for backup_path in backups:
            try:
                with open(backup_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)

                threads = data.get("threads") or data.get("sessions") or data.get("conversations") or []
                if isinstance(threads, dict):
                    threads = list(threads.values())

                if not threads:
                    continue

                for t in threads:
                    if not isinstance(t, dict):
                        continue
                    tid = t.get("id") or t.get("uuid") or f"thread_{len(sessions)}"
                    title = t.get("name") or t.get("title") or f"Chatbox 对话 {str(tid)[:8]}"

                    session = UnifiedSession(
                        session_id=str(tid),
                        source_tool=self.tool_name,
                        tool_id=self.tool_id,
                        title=title,
                        workspace_path="",
                        created_at=datetime.fromtimestamp(os.path.getmtime(backup_path)),
                        updated_at=datetime.fromtimestamp(os.path.getmtime(backup_path)),
                        raw_source_path=backup_path,
                        metadata={"thread_id": str(tid)}
                    )
                    sessions.append(session)
                if sessions:
                    break
            except Exception:
                pass

        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        fpath = session.raw_source_path
        tid = session.metadata.get("thread_id")
        if not os.path.exists(fpath) or not tid:
            return session

        messages: List[UnifiedMessage] = []
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            threads = data.get("threads") or data.get("sessions") or data.get("conversations") or []
            if isinstance(threads, dict):
                threads = list(threads.values())

            for t in threads:
                if str(t.get("id") or t.get("uuid")) == tid:
                    raw_msgs = t.get("messages") or []
                    for m in raw_msgs:
                        if isinstance(m, dict):
                            role = m.get("role", "user")
                            content = m.get("content") or m.get("text") or ""
                            messages.append(UnifiedMessage(
                                role="user" if role in ("user", "human") else "assistant",
                                content=str(content)
                            ))
                    break
        except Exception:
            pass

        session.messages = messages
        session.message_count = len(messages)
        return session
