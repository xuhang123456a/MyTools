"""
Workbuddy 适配器
解析 ~/.workbuddy/projects/ 与 ~/.workbuddy/app/sessions.json 中的历史对话
"""

import os
import glob
import json
import re
from datetime import datetime
from typing import List, Optional

try:
    from core.adapters.base_adapter import BaseAdapter
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact
except (ImportError, ValueError):
    from .base_adapter import BaseAdapter
    from ..models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact


class WorkbuddyAdapter(BaseAdapter):
    tool_id = "workbuddy"
    tool_name = "Workbuddy"
    icon = "💼"
    description = "腾讯 Workbuddy 智能工作助手与 Agent 历史"

    def get_wb_dir(self) -> str:
        return os.path.join(self.home, ".workbuddy")

    def detect(self) -> bool:
        pdir = os.path.join(self.get_wb_dir(), "projects")
        sfile = os.path.join(self.get_wb_dir(), "app", "sessions.json")
        return (os.path.exists(pdir) and bool(os.listdir(pdir))) or os.path.exists(sfile)

    @staticmethod
    def parse_iso_or_ms(val) -> Optional[datetime]:
        if not val:
            return None
        if isinstance(val, (int, float)):
            try:
                v = float(val)
                if v > 1e11:
                    v /= 1000.0
                return datetime.fromtimestamp(v)
            except Exception:
                return None
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass
        return None

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        wb_dir = self.get_wb_dir()
        projects_dir = os.path.join(wb_dir, "projects")
        sessions_json_path = os.path.join(wb_dir, "app", "sessions.json")

        meta_map = {}
        if os.path.exists(sessions_json_path):
            try:
                with open(sessions_json_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                    for item in data.get("sessions", []):
                        if isinstance(item, dict) and "conversationId" in item:
                            meta_map[item["conversationId"]] = item
            except Exception:
                pass

        if not os.path.exists(projects_dir):
            return sessions

        for root, dirs, files in os.walk(projects_dir):
            for fname in files:
                if not fname.endswith(".jsonl"):
                    continue

                session_id = fname[:-6]
                fpath = os.path.join(root, fname)
                meta = meta_map.get(session_id, {})

                title = f"Workbuddy 会话 {session_id[:8]}"
                work_dir = meta.get("workDir", "")
                started_at = self.parse_iso_or_ms(meta.get("startedAt"))
                resumed_at = self.parse_iso_or_ms(meta.get("resumedAt"))

                if not started_at:
                    try:
                        started_at = datetime.fromtimestamp(os.path.getctime(fpath))
                    except Exception:
                        started_at = datetime.now()

                if not resumed_at:
                    try:
                        resumed_at = datetime.fromtimestamp(os.path.getmtime(fpath))
                    except Exception:
                        resumed_at = started_at

                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as jf:
                        for _ in range(30):
                            line = jf.readline()
                            if not line:
                                break
                            obj = json.loads(line)
                            if obj.get("type") == "ai-title" and obj.get("aiTitle"):
                                title = obj.get("aiTitle")
                            elif obj.get("type") == "message" and obj.get("role") == "user" and title.startswith("Workbuddy 会话"):
                                content_list = obj.get("content", [])
                                if isinstance(content_list, list):
                                    for c in content_list:
                                        if isinstance(c, dict) and c.get("text"):
                                            raw_t = c.get("text")
                                            clean_t = re.sub(r"<system-reminder.*?>.*?</system-reminder>", "", raw_t, flags=re.DOTALL).strip()
                                            if clean_t:
                                                first_l = clean_t.split("\n")[0][:60]
                                                if first_l:
                                                    title = first_l
                                                    break
                except Exception:
                    pass

                session = UnifiedSession(
                    session_id=session_id,
                    source_tool=self.tool_name,
                    tool_id=self.tool_id,
                    title=title,
                    workspace_path=work_dir,
                    created_at=started_at,
                    updated_at=resumed_at,
                    raw_source_path=fpath,
                    metadata={"project_folder": os.path.basename(root)}
                )
                sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        fpath = session.raw_source_path
        if not os.path.exists(fpath):
            return session

        messages: List[UnifiedMessage] = []
        pending_tools: List[UnifiedToolCall] = []
        current_reasoning = ""

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
                    role = obj.get("role")
                    ts = self.parse_iso_or_ms(obj.get("timestamp"))

                    if entry_type == "ai-title" and obj.get("aiTitle"):
                        session.title = obj.get("aiTitle")
                        if obj.get("cwd") and not session.workspace_path:
                            session.workspace_path = obj.get("cwd")

                    elif entry_type == "reasoning":
                        r_text = obj.get("reasoning") or obj.get("text") or ""
                        if r_text:
                            current_reasoning += str(r_text) + "\n"

                    elif entry_type == "function_call":
                        fn_name = obj.get("name") or obj.get("function_name") or "tool"
                        fn_args = obj.get("args") or obj.get("arguments") or {}
                        pending_tools.append(UnifiedToolCall(
                            tool_name=fn_name,
                            tool_summary=f"调用工具: {fn_name}",
                            arguments=fn_args if isinstance(fn_args, dict) else {"raw": fn_args}
                        ))

                    elif entry_type == "function_call_result":
                        res = obj.get("result") or obj.get("output") or ""
                        if pending_tools:
                            pending_tools[-1].output = str(res)[:2500]

                    elif entry_type == "message":
                        content_raw = obj.get("content")
                        text_parts = []
                        if isinstance(content_raw, str):
                            text_parts.append(content_raw)
                        elif isinstance(content_raw, list):
                            for part in content_raw:
                                if isinstance(part, str):
                                    text_parts.append(part)
                                elif isinstance(part, dict):
                                    if part.get("type") in ("input_text", "output_text", "text") and part.get("text"):
                                        text_parts.append(part.get("text"))
                                    elif part.get("content"):
                                        text_parts.append(str(part.get("content")))

                        final_text = "\n".join(text_parts).strip()
                        if role == "user":
                            # 清洗系统注入的 system-reminder 标签
                            clean_text = re.sub(r"<system-reminder.*?>.*?</system-reminder>", "", final_text, flags=re.DOTALL).strip()
                            if clean_text:
                                final_text = clean_text

                        if final_text or pending_tools or current_reasoning:
                            msg = UnifiedMessage(
                                role="user" if role == "user" else "assistant",
                                content=final_text,
                                thinking=current_reasoning.strip(),
                                tool_calls=list(pending_tools),
                                timestamp=ts or session.created_at
                            )
                            messages.append(msg)
                            pending_tools.clear()
                            current_reasoning = ""
        except Exception:
            pass

        session.messages = messages
        return session
