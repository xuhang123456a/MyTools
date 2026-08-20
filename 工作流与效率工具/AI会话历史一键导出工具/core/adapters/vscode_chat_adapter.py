"""
VS Code & GitHub Copilot Chat 适配器
深度解析 %APPDATA%/Code/User/workspaceStorage 下的 chatSessions/*.jsonl (增量补丁流) 与 emptyWindowChatSessions
"""

import os
import glob
import json
import urllib.parse
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    from core.adapters.base_adapter import BaseAdapter
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact
except (ImportError, ValueError):
    from .base_adapter import BaseAdapter
    from ..models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact


class VSCodeChatAdapter(BaseAdapter):
    tool_id = "vscode_copilot"
    tool_name = "VS Code / Copilot Chat"
    icon = "🐙"
    description = "VS Code 原生 Chat 及 GitHub Copilot 对话历史"

    def get_storage_dir(self) -> str:
        return os.path.join(self.appdata, "Code", "User", "workspaceStorage")

    def get_global_storage_dir(self) -> str:
        return os.path.join(self.appdata, "Code", "User", "globalStorage")

    def detect(self) -> bool:
        sdir = self.get_storage_dir()
        if not os.path.exists(sdir):
            return False
        matches = glob.glob(os.path.join(sdir, "*", "chatSessions", "*.jsonl"))
        return len(matches) > 0

    @staticmethod
    def parse_workspace_json(ws_dir: str) -> str:
        wfile = os.path.join(ws_dir, "workspace.json")
        if not os.path.exists(wfile):
            return ""
        try:
            with open(wfile, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                folder_uri = data.get("folder") or data.get("workspace") or ""
                if folder_uri.startswith("file:///"):
                    raw_path = folder_uri[8:]
                    unquoted = urllib.parse.unquote(raw_path)
                    return os.path.normpath(unquoted)
        except Exception:
            pass
        return ""

    @classmethod
    def replay_vscode_chat_jsonl(cls, filepath: str) -> Dict[str, Any]:
        """重放 VS Code chatSessions/*.jsonl 的增量补丁流，还原完整会话状态"""
        session_data: Dict[str, Any] = {"requests": []}
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue

                    kind = obj.get("kind")
                    k = obj.get("k", [])
                    v = obj.get("v")

                    if kind == 0:
                        if isinstance(v, dict):
                            session_data.update(v)
                    elif kind == 1 and k:
                        curr = session_data
                        for p in k[:-1]:
                            if isinstance(p, int):
                                while len(curr) <= p:
                                    curr.append({})
                                curr = curr[p]
                            else:
                                if p not in curr or not isinstance(curr[p], (dict, list)):
                                    curr[p] = {}
                                curr = curr[p]
                        last_k = k[-1]
                        if isinstance(last_k, int) and isinstance(curr, list):
                            while len(curr) <= last_k:
                                curr.append(None)
                            curr[last_k] = v
                        elif isinstance(curr, dict):
                            curr[last_k] = v
                    elif kind == 2 and k:
                        curr = session_data
                        for p in k[:-1]:
                            if isinstance(p, int):
                                while len(curr) <= p:
                                    curr.append({})
                                curr = curr[p]
                            else:
                                if p not in curr or not isinstance(curr[p], list):
                                    curr[p] = []
                                curr = curr[p]
                        last_k = k[-1]
                        if isinstance(last_k, int) and isinstance(curr, list):
                            while len(curr) <= last_k:
                                curr.append([])
                            target_arr = curr[last_k]
                        elif isinstance(curr, dict):
                            if last_k not in curr or not isinstance(curr[last_k], list):
                                curr[last_k] = []
                            target_arr = curr[last_k]
                        else:
                            target_arr = None

                        if isinstance(target_arr, list):
                            if isinstance(v, list):
                                target_arr.extend(v)
                            else:
                                target_arr.append(v)
        except Exception:
            pass
        return session_data

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        sdir = self.get_storage_dir()
        if not os.path.exists(sdir):
            return sessions

        for ws_entry in os.listdir(sdir):
            ws_path = os.path.join(sdir, ws_entry)
            chat_dir = os.path.join(ws_path, "chatSessions")
            if not os.path.isdir(chat_dir):
                continue

            workspace_real_path = self.parse_workspace_json(ws_path)

            for fname in os.listdir(chat_dir):
                if not fname.endswith(".jsonl"):
                    continue
                fpath = os.path.join(chat_dir, fname)
                session_id = fname[:-6]

                try:
                    mtime = os.path.getmtime(fpath)
                    updated_at = datetime.fromtimestamp(mtime)
                    created_at = datetime.fromtimestamp(os.path.getctime(fpath))
                except Exception:
                    created_at = datetime.now()
                    updated_at = datetime.now()

                data = self.replay_vscode_chat_jsonl(fpath)
                requests = data.get("requests", [])
                
                # 严格过滤没有实际对话消息的空会话
                if not requests:
                    continue

                title = f"VS Code 会话 {session_id[:8]}"
                first_req = requests[0]
                msg_obj = first_req.get("message", {})
                if isinstance(msg_obj, dict):
                    text = msg_obj.get("text") or ""
                else:
                    text = str(msg_obj)
                first_line = text.strip().split("\n")[0].strip()
                if first_line:
                    title = first_line[:60]

                session = UnifiedSession(
                    session_id=session_id,
                    source_tool=self.tool_name,
                    tool_id=self.tool_id,
                    title=title,
                    workspace_path=workspace_real_path,
                    created_at=created_at,
                    updated_at=updated_at,
                    raw_source_path=fpath,
                    estimated_msg_count=len(requests) * 2,
                    metadata={"workspace_storage_id": ws_entry}
                )
                sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        fpath = session.raw_source_path
        if not os.path.exists(fpath):
            return session

        data = self.replay_vscode_chat_jsonl(fpath)
        requests = data.get("requests", [])
        messages: List[UnifiedMessage] = []

        for req in requests:
            if not isinstance(req, dict):
                continue

            msg_obj = req.get("message", {})
            user_text = ""
            if isinstance(msg_obj, dict):
                user_text = msg_obj.get("text") or ""
            elif isinstance(msg_obj, str):
                user_text = msg_obj

            req_ts = None
            if req.get("timestamp"):
                try:
                    req_ts = datetime.fromtimestamp(float(req["timestamp"]) / 1000.0)
                except Exception:
                    pass

            if user_text:
                messages.append(UnifiedMessage(
                    role="user",
                    content=user_text.strip(),
                    timestamp=req_ts or session.created_at
                ))

            resps = req.get("response", [])
            resp_text_parts = []
            thinking_parts = []
            tool_calls = []

            for r in resps:
                if isinstance(r, dict):
                    r_kind = r.get("kind")
                    if r_kind == "thinking":
                        t_val = r.get("value") or ""
                        if t_val:
                            thinking_parts.append(str(t_val))
                    elif r_kind in ("toolInvocation", "toolCall") or "toolId" in r:
                        tool_name = r.get("toolId") or r.get("toolName") or "tool"
                        tool_msg = r.get("invocationMessage") or r.get("pastTenseMessage") or ""
                        tool_calls.append(UnifiedToolCall(
                            tool_name=tool_name,
                            tool_summary=str(tool_msg),
                            arguments={"raw": str(r.get("parameters") or r.get("args") or "")},
                            output=str(r.get("result") or r.get("resultDetails") or "")
                        ))
                    elif r.get("value"):
                        resp_text_parts.append(str(r.get("value")))
                    elif r.get("text"):
                        resp_text_parts.append(str(r.get("text")))
                elif isinstance(r, str):
                    resp_text_parts.append(r)

            final_resp = "".join(resp_text_parts).strip()
            final_thinking = "\n\n".join(thinking_parts).strip()

            if final_resp or final_thinking or tool_calls:
                messages.append(UnifiedMessage(
                    role="assistant",
                    content=final_resp,
                    thinking=final_thinking,
                    tool_calls=tool_calls,
                    timestamp=req_ts or session.updated_at
                ))

        session.messages = messages
        return session
