"""
Cline / Claude Dev / Roo Code 插件适配器
解析 VS Code 插件 Cline、Roo Code 的任务历史与对话记录
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


class ClineAdapter(BaseAdapter):
    tool_id = "cline"
    tool_name = "Cline / Roo Code"
    icon = "🤖"
    description = "VS Code 自主编程插件 Cline (Claude Dev) 与 Roo Code 任务历史"

    def get_task_dirs(self) -> List[str]:
        dirs = [
            os.path.join(self.appdata, "Code", "User", "globalStorage", "saoudrizwan.claude-dev", "tasks"),
            os.path.join(self.appdata, "Code", "User", "globalStorage", "rooveterinaryinc.roo-cline", "tasks"),
            os.path.join(self.appdata, "Cursor", "User", "globalStorage", "saoudrizwan.claude-dev", "tasks"),
            os.path.join(self.appdata, "Cursor", "User", "globalStorage", "rooveterinaryinc.roo-cline", "tasks"),
            os.path.join(self.home, ".cline", "tasks"),
        ]
        return [d for d in dirs if os.path.exists(d)]

    def detect(self) -> bool:
        tdirs = self.get_task_dirs()
        for td in tdirs:
            if os.path.exists(td) and bool(os.listdir(td)):
                return True
        return False

    @staticmethod
    def parse_ts(val) -> Optional[datetime]:
        if not val:
            return None
        try:
            v = float(val)
            if v > 1e11:
                v /= 1000.0
            return datetime.fromtimestamp(v)
        except Exception:
            return None

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        tdirs = self.get_task_dirs()

        for tdir in tdirs:
            plugin_name = "Roo Code" if "roo-cline" in tdir else "Cline"
            for task_id in os.listdir(tdir):
                task_path = os.path.join(tdir, task_id)
                if not os.path.isdir(task_path):
                    continue

                ui_msg_file = os.path.join(task_path, "ui_messages.json")
                title = f"{plugin_name} 任务 {task_id[:8]}"
                created_at = self.parse_ts(task_id)
                if not created_at:
                    try:
                        created_at = datetime.fromtimestamp(os.path.getctime(task_path))
                    except Exception:
                        created_at = datetime.now()

                try:
                    updated_at = datetime.fromtimestamp(os.path.getmtime(task_path))
                except Exception:
                    updated_at = created_at

                if os.path.exists(ui_msg_file):
                    try:
                        with open(ui_msg_file, "r", encoding="utf-8", errors="ignore") as f:
                            msgs = json.load(f)
                            if isinstance(msgs, list):
                                for m in msgs:
                                    if m.get("say") == "task" and m.get("text"):
                                        title = m["text"].strip().split("\n")[0][:60]
                                        break
                    except Exception:
                        pass

                session = UnifiedSession(
                    session_id=task_id,
                    source_tool=f"{plugin_name}",
                    tool_id=self.tool_id,
                    title=title,
                    workspace_path="",
                    created_at=created_at,
                    updated_at=updated_at,
                    raw_source_path=task_path,
                    metadata={"plugin": plugin_name}
                )
                sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        task_path = session.raw_source_path
        ui_msg_file = os.path.join(task_path, "ui_messages.json")
        api_file = os.path.join(task_path, "api_conversation_history.json")

        messages: List[UnifiedMessage] = []

        if os.path.exists(ui_msg_file):
            try:
                with open(ui_msg_file, "r", encoding="utf-8", errors="ignore") as f:
                    items = json.load(f)

                pending_tools: List[UnifiedToolCall] = []
                current_thinking = ""

                for it in items:
                    if not isinstance(it, dict):
                        continue

                    say_type = it.get("say")
                    text_val = it.get("text") or ""
                    ts = self.parse_ts(it.get("ts"))

                    if say_type == "task":
                        messages.append(UnifiedMessage(
                            role="user",
                            content=text_val,
                            timestamp=ts or session.created_at
                        ))

                    elif say_type == "user_feedback":
                        messages.append(UnifiedMessage(
                            role="user",
                            content=text_val,
                            timestamp=ts
                        ))

                    elif say_type in ("reasoning", "thought"):
                        current_thinking += str(text_val) + "\n"

                    elif say_type == "tool":
                        try:
                            tool_info = json.loads(text_val) if isinstance(text_val, str) and text_val.startswith("{") else {"raw": text_val}
                        except Exception:
                            tool_info = {"raw": text_val}
                        pending_tools.append(UnifiedToolCall(
                            tool_name=tool_info.get("tool", "tool"),
                            tool_summary=tool_info.get("description", ""),
                            arguments=tool_info
                        ))

                    elif say_type in ("text", "completion_result"):
                        if text_val or pending_tools or current_thinking:
                            messages.append(UnifiedMessage(
                                role="assistant",
                                content=text_val,
                                thinking=current_thinking.strip(),
                                tool_calls=list(pending_tools),
                                timestamp=ts
                            ))
                            pending_tools.clear()
                            current_thinking = ""

            except Exception:
                pass

        elif os.path.exists(api_file):
            try:
                with open(api_file, "r", encoding="utf-8", errors="ignore") as f:
                    history = json.load(f)
                    for item in history:
                        role = item.get("role", "user")
                        content = item.get("content", "")
                        if isinstance(content, list):
                            parts = [c.get("text", "") for c in content if isinstance(c, dict) and "text" in c]
                            content = "\n".join(parts)
                        messages.append(UnifiedMessage(
                            role=role,
                            content=str(content),
                            timestamp=session.created_at
                        ))
            except Exception:
                pass

        session.messages = messages
        return session
