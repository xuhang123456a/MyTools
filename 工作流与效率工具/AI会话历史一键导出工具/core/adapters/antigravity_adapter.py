"""
Google Antigravity 适配器
解析 ~/.gemini/antigravity/brain/ 下的会话记录与 Artifacts 产物
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


class AntigravityAdapter(BaseAdapter):
    tool_id = "antigravity"
    tool_name = "Google Antigravity"
    icon = "🪐"
    description = "Google DeepMind Antigravity AI 编程助手与 Agent 历史"

    def get_brain_dir(self) -> str:
        return os.path.join(self.home, ".gemini", "antigravity", "brain")

    def detect(self) -> bool:
        bdir = self.get_brain_dir()
        return os.path.exists(bdir) and bool(os.listdir(bdir))

    @staticmethod
    def extract_workspace_path(line_obj: dict) -> str:
        """从 tool_calls 参数中提取真实的工作区物理路径"""
        tool_calls = line_obj.get("tool_calls", [])
        for tc in tool_calls:
            args = tc.get("args") or tc.get("arguments") or {}
            for k in ("DirectoryPath", "SearchDirectory", "Cwd", "TargetFile", "AbsolutePath"):
                val = args.get(k)
                if val and isinstance(val, str):
                    val_clean = val.strip('"\'' )
                    m = re.match(r"^([a-zA-Z]:\\[^\\/:*?\"<>|\r\n]+(?:\\[^\\/:*?\"<>|\r\n]+)*)", val_clean)
                    if m:
                        path_found = m.group(1)
                        if not any(x in path_found.lower() for x in ("appdata", ".gemini", "temp", "tmp")):
                            return path_found
        return ""

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        bdir = self.get_brain_dir()
        if not os.path.exists(bdir):
            return sessions

        for entry in os.listdir(bdir):
            brain_path = os.path.join(bdir, entry)
            if not os.path.isdir(brain_path):
                continue

            transcript_path = os.path.join(brain_path, ".system_generated", "logs", "transcript.jsonl")
            if not os.path.exists(transcript_path):
                transcript_path = os.path.join(brain_path, ".system_generated", "logs", "transcript_full.jsonl")
                if not os.path.exists(transcript_path):
                    continue

            try:
                mtime = os.path.getmtime(transcript_path)
                updated_at = datetime.fromtimestamp(mtime)
                ctime = os.path.getctime(transcript_path)
                created_at = datetime.fromtimestamp(ctime)
            except Exception:
                created_at = datetime.now()
                updated_at = datetime.now()

            title = f"Antigravity 会话 {entry[:8]}"
            workspace_path = ""
            user_msg_preview = ""

            try:
                with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                    for _ in range(60):
                        line = f.readline()
                        if not line:
                            break
                        try:
                            obj = json.loads(line)
                            if not workspace_path:
                                ws_cand = self.extract_workspace_path(obj)
                                if ws_cand:
                                    workspace_path = ws_cand

                            if obj.get("type") == "USER_INPUT" and not user_msg_preview:
                                raw_text = str(obj.get("content", ""))
                                req_match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", raw_text, re.DOTALL)
                                if req_match:
                                    raw_text = req_match.group(1).strip()
                                first_line = raw_text.strip().split("\n")[0].strip()
                                if first_line:
                                    user_msg_preview = first_line[:60]
                                    title = user_msg_preview
                        except Exception:
                            continue
            except Exception:
                pass

            session = UnifiedSession(
                session_id=entry,
                source_tool=self.tool_name,
                tool_id=self.tool_id,
                title=title,
                workspace_path=workspace_path,
                created_at=created_at,
                updated_at=updated_at,
                raw_source_path=brain_path,
                metadata={"brain_id": entry}
            )
            sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        brain_path = session.raw_source_path
        transcript_path = os.path.join(brain_path, ".system_generated", "logs", "transcript.jsonl")
        if not os.path.exists(transcript_path):
            transcript_path = os.path.join(brain_path, ".system_generated", "logs", "transcript_full.jsonl")
            if not os.path.exists(transcript_path):
                return session

        messages: List[UnifiedMessage] = []
        turn_tool_calls: List[UnifiedToolCall] = []
        turn_thinking_parts: List[str] = []
        turn_text_parts: List[str] = []

        def flush_assistant_turn():
            nonlocal turn_tool_calls, turn_thinking_parts, turn_text_parts
            if turn_text_parts or turn_tool_calls or turn_thinking_parts:
                final_content = "\n\n".join(filter(None, [t.strip() for t in turn_text_parts]))
                final_thinking = "\n\n".join(filter(None, [t.strip() for t in turn_thinking_parts]))
                messages.append(UnifiedMessage(
                    role="assistant",
                    content=final_content,
                    thinking=final_thinking,
                    tool_calls=list(turn_tool_calls),
                    timestamp=session.updated_at
                ))
                turn_tool_calls.clear()
                turn_thinking_parts.clear()
                turn_text_parts.clear()

        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                step_type = obj.get("type", "")
                source = obj.get("source", "")
                content = obj.get("content", "")
                tool_calls_data = obj.get("tool_calls", [])

                if not session.workspace_path:
                    ws_cand = self.extract_workspace_path(obj)
                    if ws_cand:
                        session.workspace_path = ws_cand

                # 忽略 checkpoint 系统消息
                if step_type == "CHECKPOINT":
                    continue

                # 工具输出 (GENERIC / TOOL_OUTPUT)
                if step_type in ("GENERIC", "TOOL_OUTPUT") or source == "TOOL":
                    if turn_tool_calls:
                        turn_tool_calls[-1].output = str(content)[:2500]
                    continue

                # 1. 用户输入 (USER_INPUT)
                if step_type == "USER_INPUT" or source == "USER_EXPLICIT":
                    flush_assistant_turn()
                    raw_text = str(content)
                    req_match = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", raw_text, re.DOTALL)
                    if req_match:
                        clean_content = req_match.group(1).strip()
                    else:
                        clean_content = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", raw_text, flags=re.DOTALL)
                        clean_content = re.sub(r"<USER_SETTINGS_CHANGE>.*?</USER_SETTINGS_CHANGE>", "", clean_content, flags=re.DOTALL).strip()
                        if not clean_content:
                            clean_content = raw_text

                    if clean_content:
                        messages.append(UnifiedMessage(
                            role="user",
                            content=clean_content,
                            timestamp=session.created_at
                        ))

                # 2. 模型回复 (PLANNER_RESPONSE)
                elif step_type == "PLANNER_RESPONSE" or source == "MODEL":
                    if obj.get("thinking"):
                        turn_thinking_parts.append(str(obj["thinking"]))

                    if content and str(content).strip():
                        turn_text_parts.append(str(content).strip())

                    if tool_calls_data and isinstance(tool_calls_data, list):
                        for tc in tool_calls_data:
                            tool_name = tc.get("name") or tc.get("tool_name") or "tool"
                            args = tc.get("args") or tc.get("arguments") or tc.get("parameters") or {}
                            cleaned_args = {}
                            if isinstance(args, dict):
                                for k, v in args.items():
                                    if isinstance(v, str) and v.startswith('"') and v.endswith('"'):
                                        cleaned_args[k] = v[1:-1]
                                    else:
                                        cleaned_args[k] = v
                            else:
                                cleaned_args = {"raw": args}

                            tool_summary = cleaned_args.get("toolSummary") or cleaned_args.get("toolAction") or ""
                            turn_tool_calls.append(UnifiedToolCall(
                                tool_name=tool_name,
                                tool_summary=tool_summary,
                                arguments=cleaned_args
                            ))

        flush_assistant_turn()

        artifacts: List[UnifiedArtifact] = []
        for root, dirs, files in os.walk(brain_path):
            if ".system_generated" in root:
                continue
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    rel_name = os.path.relpath(fpath, brain_path)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as af:
                        art_content = af.read()
                    art_type = "document" if fname.endswith((".md", ".txt")) else "code"
                    artifacts.append(UnifiedArtifact(
                        title=rel_name,
                        path=fpath,
                        content=art_content,
                        artifact_type=art_type
                    ))
                except Exception:
                    pass

        session.messages = messages
        session.artifacts = artifacts
        return session
