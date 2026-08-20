"""
基础适配器抽象类 (Base Adapter)
定义所有 AI 工具适配器的统一接口
"""

from abc import ABC, abstractmethod
from typing import List, Optional
import os
import sys

try:
    from core.models import UnifiedSession, UnifiedMessage
except (ImportError, ValueError):
    from ..models import UnifiedSession, UnifiedMessage


class BaseAdapter(ABC):
    """AI 工具适配器抽象基类"""
    tool_id: str = "base"
    tool_name: str = "Base Tool"
    icon: str = "🤖"
    description: str = ""

    def __init__(self):
        self.home = os.path.expanduser("~")
        self.appdata = os.environ.get("APPDATA", "")
        self.localappdata = os.environ.get("LOCALAPPDATA", "")

    @abstractmethod
    def detect(self) -> bool:
        """检测本机是否存在该工具的历史数据"""
        pass

    @abstractmethod
    def scan_sessions(self) -> List[UnifiedSession]:
        """
        快速扫描该工具的所有会话元信息列表
        返回包含 session_id, title, workspace_path, created_at, updated_at 等基本信息的会话列表
        """
        pass

    @abstractmethod
    def load_session_detail(self, session: UnifiedSession) -> UnifiedSession:
        """
        根据会话元数据，深入解析并填充完整的 messages、artifacts 与 metadata
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} tool_id={self.tool_id} tool_name={self.tool_name}>"
