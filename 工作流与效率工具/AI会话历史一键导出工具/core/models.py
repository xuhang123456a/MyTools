"""
统一数据模型 (Unified Data Models)
定义所有 AI Agent 与工具的标准化会话结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class UnifiedToolCall:
    """工具调用与执行返回"""
    tool_name: str
    tool_summary: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    output: str = ""
    status: str = "success"  # success, error, running

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "tool_summary": self.tool_summary,
            "arguments": self.arguments,
            "output": self.output,
            "status": self.status,
        }


@dataclass
class UnifiedArtifact:
    """会话生成的产物/文件"""
    title: str
    path: str = ""
    content: str = ""
    artifact_type: str = "document"  # document, code, diff, log

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "path": self.path,
            "content": self.content,
            "artifact_type": self.artifact_type,
        }


@dataclass
class UnifiedMessage:
    """统一单条消息模型"""
    role: str  # user, assistant, system, tool
    content: str = ""
    thinking: str = ""  # 思考链 / Reasoning / Thought process
    tool_calls: List[UnifiedToolCall] = field(default_factory=list)
    timestamp: Optional[datetime] = None
    model: str = ""
    raw_extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "thinking": self.thinking,
            "tool_calls": [t.to_dict() for t in self.tool_calls],
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "model": self.model,
            "raw_extra": self.raw_extra,
        }


@dataclass
class UnifiedSession:
    """统一标准化会话模型"""
    session_id: str
    source_tool: str  # e.g. "Google Antigravity", "Kiro", "Workbuddy", "GitHub Copilot", "Cline"
    tool_id: str  # e.g. "antigravity", "kiro", "workbuddy", "vscode_copilot", "cline"
    title: str = "Untitled Session"
    workspace_path: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    messages: List[UnifiedMessage] = field(default_factory=list)
    artifacts: List[UnifiedArtifact] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_source_path: str = ""
    estimated_msg_count: int = 0

    @property
    def message_count(self) -> int:
        return len(self.messages) if self.messages else self.estimated_msg_count

    @property
    def user_query_count(self) -> int:
        return sum(1 for m in self.messages if m.role == "user")

    @property
    def tool_call_count(self) -> int:
        return sum(len(m.tool_calls) for m in self.messages)

    @property
    def first_user_query(self) -> str:
        for m in self.messages:
            if m.role == "user" and m.content.strip():
                return m.content.strip()
        return ""

    @property
    def formatted_created_at(self) -> str:
        if self.created_at:
            return self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return "未知时间"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "source_tool": self.source_tool,
            "tool_id": self.tool_id,
            "title": self.title,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": self.message_count,
            "messages": [m.to_dict() for m in self.messages],
            "artifacts": [a.to_dict() for a in self.artifacts],
            "metadata": self.metadata,
            "raw_source_path": self.raw_source_path,
        }
