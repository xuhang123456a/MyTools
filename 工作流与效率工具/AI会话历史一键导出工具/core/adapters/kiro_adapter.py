"""
Kiro AI Agent 适配器
解析 AppData/Roaming/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/ 下的历史会话
"""

import os
import glob
import json
import base64
from datetime import datetime
from typing import List, Optional, Dict, Any

try:
    from core.adapters.base_adapter import BaseAdapter
    from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact
except (ImportError, ValueError):
    from .base_adapter import BaseAdapter
    from ..models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact


class KiroAdapter(BaseAdapter):
    tool_id = "kiro"
    tool_name = "Kiro AI Agent"
    icon = "⚡"
    description = "Kiro IDE 智能 Agent 任务流与会话历史"

    def get_kiro_dir(self) -> str:
        return os.path.join(self.appdata, "Kiro", "User", "globalStorage", "kiro.kiroagent")

    def detect(self) -> bool:
        kdir = self.get_kiro_dir()
        ws_dir = os.path.join(kdir, "workspace-sessions")
        return os.path.exists(ws_dir) and bool(os.listdir(ws_dir))

    @staticmethod
    def decode_ws_name(encoded_name: str) -> str:
        """还原 Kiro 的 Base64 工作区路径编码"""
        try:
            padded = encoded_name + "=" * ((4 - len(encoded_name) % 4) % 4)
            padded = padded.replace("-", "+").replace("_", "/")
            decoded_bytes = base64.b64decode(padded)
            return decoded_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return encoded_name

    def _get_executions_map(self) -> Dict[str, Dict[str, Any]]:
        """从 Kiro 全局 hash 文件夹中预加载 execution 元数据映射表"""
        exec_map = {}
        kdir = self.get_kiro_dir()
        if not os.path.exists(kdir):
            return exec_map

        for entry in os.listdir(kdir):
            p = os.path.join(kdir, entry)
            if os.path.isdir(p):
                efile = os.path.join(p, "f62de366d0006e17ea00a01f6624aabf")
                if os.path.exists(efile):
                    try:
                        with open(efile, "r", encoding="utf-8", errors="ignore") as f:
                            data = json.load(f)
                            for ex in data.get("executions", []):
                                if isinstance(ex, dict) and "executionId" in ex:
                                    exec_map[ex["executionId"]] = ex
                    except Exception:
                        pass
        return exec_map

    def scan_sessions(self) -> List[UnifiedSession]:
        sessions = []
        kdir = self.get_kiro_dir()
        ws_dir = os.path.join(kdir, "workspace-sessions")
        if not os.path.exists(ws_dir):
            return sessions

        for ws_encoded in os.listdir(ws_dir):
            ws_folder = os.path.join(ws_dir, ws_encoded)
            if not os.path.isdir(ws_folder) or ws_encoded.startswith("."):
                continue

            workspace_real_path = self.decode_ws_name(ws_encoded)

            sessions_meta_file = os.path.join(ws_folder, "sessions.json")
            meta_map = {}
            if os.path.exists(sessions_meta_file):
                try:
                    with open(sessions_meta_file, "r", encoding="utf-8", errors="ignore") as mf:
                        meta_list = json.load(mf)
                        if isinstance(meta_list, list):
                            for m in meta_list:
                                if isinstance(m, dict) and "sessionId" in m:
                                    meta_map[m["sessionId"]] = m
                except Exception:
                    pass

            for fname in os.listdir(ws_folder):
                # 严格过滤隐藏文件、占位迁移锁及非 json 记录
                if not fname.endswith(".json") or fname == "sessions.json" or fname.startswith(".") or "migrat" in fname.lower():
                    continue

                session_id = fname[:-5]
                fpath = os.path.join(ws_folder, fname)
                meta = meta_map.get(session_id, {})

                title = meta.get("title") or f"Kiro 会话 {session_id[:8]}"
                created_at = None
                if meta.get("createdTime"):
                    try:
                        created_at = datetime.fromtimestamp(meta["createdTime"] / 1000.0)
                    except Exception:
                        pass

                try:
                    mtime = os.path.getmtime(fpath)
                    updated_at = datetime.fromtimestamp(mtime)
                    if not created_at:
                        created_at = datetime.fromtimestamp(os.path.getctime(fpath))
                except Exception:
                    created_at = datetime.now()
                    updated_at = datetime.now()

                msg_count_est = 0
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            history = data.get("history", [])
                            msg_count_est = len(history)
                            if history:
                                for h in history:
                                    msg = h.get("message", {})
                                    if msg.get("role") == "user":
                                        content = msg.get("content")
                                        if isinstance(content, str):
                                            title = content.strip().split("\n")[0][:60]
                                        elif isinstance(content, list):
                                            for c in content:
                                                if isinstance(c, dict) and c.get("text"):
                                                    title = c["text"].strip().split("\n")[0][:60]
                                                    break
                                        if not title.startswith("Kiro 会话"):
                                            break
                except Exception:
                    pass

                # 过滤完全没有历史记录的空白占位文件
                if msg_count_est == 0:
                    continue

                session = UnifiedSession(
                    session_id=session_id,
                    source_tool=self.tool_name,
                    tool_id=self.tool_id,
                    title=title,
                    workspace_path=workspace_real_path,
                    created_at=created_at,
                    updated_at=updated_at,
                    raw_source_path=fpath,
                    estimated_msg_count=msg_count_est,
                    metadata={"workspace_encoded": ws_encoded}
                )
                sessions.append(session)

        sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return sessions

    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        fpath = session.raw_source_path
        if not os.path.exists(fpath):
            return session

        exec_map = self._get_executions_map()
        messages: List[UnifiedMessage] = []

        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)

            if isinstance(data, dict):
                history = data.get("history", [])
                for h in history:
                    if not isinstance(h, dict):
                        continue

                    msg = h.get("message", {})
                    role = msg.get("role", "user")
                    content_raw = msg.get("content")
                    exec_id = h.get("executionId") or ""
                    prompt_logs = h.get("promptLogs") or []

                    text_parts = []
                    if isinstance(content_raw, str):
                        text_parts.append(content_raw)
                    elif isinstance(content_raw, list):
                        for item in content_raw:
                            if isinstance(item, str):
                                text_parts.append(item)
                            elif isinstance(item, dict) and item.get("text"):
                                text_parts.append(item["text"])

                    if not text_parts and "editorState" in h:
                        ed = h["editorState"]
                        if isinstance(ed, dict):
                            for p in ed.get("content", []):
                                for c in p.get("content", []):
                                    if c.get("text"):
                                        text_parts.append(c["text"])

                    final_text = "\n".join(text_parts).strip()

                    thinking_text = ""
                    tool_calls = []

                    if role == "assistant":
                        if prompt_logs:
                            for pl in prompt_logs:
                                if isinstance(pl, dict):
                                    m_title = pl.get("modelTitle", "Agent")
                                    if pl.get("prompt"):
                                        thinking_text += f"[{m_title} 上下文规划]\n{pl['prompt'][:1000]}\n"

                        if exec_id and exec_id in exec_map:
                            ex_info = exec_map[exec_id]
                            st = ex_info.get("status", "succeed")
                            status_desc = "执行成功 (succeed)" if st == "succeed" else f"状态: {st}"
                            tool_calls.append(UnifiedToolCall(
                                tool_name="KiroTaskExecutor",
                                tool_summary=f"执行 Agent 自动化任务 ({status_desc})",
                                arguments={"executionId": exec_id, "type": ex_info.get("type", "chat-agent")},
                                output=f"任务状态: {st}\n开始时间: {ex_info.get('startTime')}\n结束时间: {ex_info.get('endTime')}"
                            ))

                        if final_text == "On it." or not final_text:
                            status_line = "✅ **Kiro Agent 任务执行完成**" if (exec_id and exec_map.get(exec_id, {}).get("status") == "succeed") else "⚡ **Kiro Agent 自动化任务处理**"
                            final_text = f"{status_line}\n\n> 🤖 Kiro Agent 已自动分析工作区代码、执行所需工具并完成相关文件改动。"
                            if exec_id:
                                final_text += f"\n> 🆔 任务执行编号: `{exec_id}`"

                    if final_text or tool_calls or thinking_text:
                        messages.append(UnifiedMessage(
                            role="user" if role in ("user", "human") else "assistant",
                            content=final_text,
                            thinking=thinking_text.strip(),
                            tool_calls=tool_calls,
                            timestamp=session.created_at
                        ))
        except Exception:
            pass

        session.messages = messages
        return session
