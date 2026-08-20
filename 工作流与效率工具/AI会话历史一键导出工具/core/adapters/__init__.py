"""
适配器统一导出
"""
from .base_adapter import BaseAdapter
from .antigravity_adapter import AntigravityAdapter
from .kiro_adapter import KiroAdapter
from .workbuddy_adapter import WorkbuddyAdapter
from .vscode_chat_adapter import VSCodeChatAdapter
from .cline_adapter import ClineAdapter
from .claude_code_adapter import ClaudeCodeAdapter
from .cursor_windsurf_adapter import CursorWindsurfAdapter
from .continue_adapter import ContinueAdapter
from .chatbox_adapter import ChatboxAdapter

ALL_ADAPTERS = [
    AntigravityAdapter,
    KiroAdapter,
    WorkbuddyAdapter,
    VSCodeChatAdapter,
    ClineAdapter,
    ClaudeCodeAdapter,
    CursorWindsurfAdapter,
    ContinueAdapter,
    ChatboxAdapter,
]

__all__ = [
    "BaseAdapter",
    "AntigravityAdapter",
    "KiroAdapter",
    "WorkbuddyAdapter",
    "VSCodeChatAdapter",
    "ClineAdapter",
    "ClaudeCodeAdapter",
    "CursorWindsurfAdapter",
    "ContinueAdapter",
    "ChatboxAdapter",
    "ALL_ADAPTERS",
]
