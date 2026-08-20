"""
Cursor / Windsurf / Trae AI 编辑器适配器
解析 AppData/Roaming/Cursor, Windsurf, Trae 下的 SQLite (state.vscdb) 会话
"""

import os
import glob
import json
import sqlite3
import urllib.parse
from datetime import datetime
from typing import List, Optional

try:
    from core.adapters.base_adapter import BaseAdapter
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact
except (ImportError, ValueError):
    from .base_adapter import BaseAdapter
    from ..models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact


class CursorWindsurfAdapter(BaseAdapter):
    tool_id = "cursor_windsurf"
    tool_name = "Cursor / Windsurf / Trae"
    icon = "✨"
    description = "Cursor、Windsurf 与 Trae 等新一代 AI IDE 会话历史"

    def get_supported_apps(self) -> List[tuple]:
        apps = [
            ("Cursor", os.path.join(self.appdata, "Cursor", "User", "workspaceStorage"), os.path.join(self.appdata, "Cursor", "User", "globalStorage")),
            ("Windsurf", os.path.join(self.appdata, "Windsurf", "User", "workspaceStorage"), os.path.join(self.appdata, "Windsurf", "User", "globalStorage")),
            ("Trae", os.path.join(self.appdata, "Trae", "User", "workspaceStorage"), os.path.join(self.appdata, "Trae", "User", "globalStorage")),
        ]
        return [(name, ws, g) for name, ws, g in apps if os.path.exists(ws) or os.path.exists(g)]

    def detect(self) -> bool:
        return len(self.get_supported_apps()) > 0

    @staticmethod
    def resolve_ws_path(ws_dir: str) -> str:
        ws_json = os.path.join(ws_dir, "workspace.json")
        if os.path.exists(ws_json):
            try:
                with open(ws_json, "r", encoding="utf-8", errors="ignore") as f:
                    d = json.load(f)
                    uri = d.get("folder") or d.get("workspace") or ""
                    if uri.startswith("file:///"):
                        return urllib.parse.unquote(uri[8:]).replace("/", "\\")
                    elif uri.startswith("file://"):
                        return urllib.parse.unquote(uri[7:]).replace("/", "\\")
            except Exception:
                pass
        return ""

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        for app_name, ws_root, g_root in self.get_supported_apps():
            if os.path.exists(ws_root):
                for ws_hash in os.listdir(ws_root):
                    ws_dir = os.path.join(ws_root, ws_hash)
                    vscdb = os.path.join(ws_dir, "state.vscdb")
                    if not os.path.exists(vscdb):
                        continue

                    ws_path = self.resolve_ws_path(ws_dir)
                    try:
                        conn = sqlite3.connect(vscdb)
                        c = conn.cursor()
                        rows = c.execute("SELECT key, value FROM ItemTable WHERE key LIKE '%composerData%' OR key LIKE '%chatData%' OR key LIKE '%cascade%' OR key LIKE '%ChatSessionStore%'").fetchall()
                        conn.close()

                        for key, val in rows:
                            if not val:
                                continue
                            try:
                                val_obj = json.loads(val)
                            except Exception:
                                continue

                            sid = f"{ws_hash}_{key[:15]}"
                            title = f"{app_name} 会话 ({key})"

                            if isinstance(val_obj, dict):
                                if val_obj.get("name"):
                                    title = val_obj.get("name")
                                elif val_obj.get("title"):
                                    title = val_obj.get("title")

                            session = UnifiedSession(
                                session_id=sid,
                                source_tool=app_name,
                                tool_id=self.tool_id,
                                title=title,
                                workspace_path=ws_path,
                                created_at=datetime.fromtimestamp(os.path.getmtime(vscdb)),
                                updated_at=datetime.fromtimestamp(os.path.getmtime(vscdb)),
                                raw_source_path=vscdb,
                                metadata={"app": app_name, "db_key": key}
                            )
                            sessions.append(session)
                    except Exception:
                        pass

        sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        vscdb = session.raw_source_path
        db_key = session.metadata.get("db_key")
        if not os.path.exists(vscdb) or not db_key:
            return session

        messages: List[UnifiedMessage] = []
        try:
            conn = sqlite3.connect(vscdb)
            c = conn.cursor()
            row = c.execute("SELECT value FROM ItemTable WHERE key = ?", (db_key,)).fetchone()
            conn.close()
            if not row or not row[0]:
                return session

            val_obj = json.loads(row[0])
            if isinstance(val_obj, dict):
                bubbles = val_obj.get("conversation") or val_obj.get("bubbles") or val_obj.get("messages") or []
                if isinstance(bubbles, list):
                    for b in bubbles:
                        if isinstance(b, dict):
                            role = "user" if b.get("type") in ("user", "human") or b.get("sender") == "user" else "assistant"
                            text = b.get("text") or b.get("content") or b.get("richText") or ""
                            if text:
                                messages.append(UnifiedMessage(role=role, content=str(text)))
        except Exception:
            pass

        session.messages = messages
        return session
