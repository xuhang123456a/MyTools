"""
会话扫描管理器 (Session Scanner)
统一调度所有 AI 适配器，实现快速扫描、检测、过滤与详情加载
"""

import os
from datetime import datetime
from typing import List, Dict, Optional, Type

from .models import UnifiedSession
from .adapters import ALL_ADAPTERS, BaseAdapter


class SessionScanner:
    """会话扫描管理器"""

    def __init__(self, custom_adapters: Optional[List[Type[BaseAdapter]]] = None):
        adapter_classes = custom_adapters or ALL_ADAPTERS
        self.adapters: Dict[str, BaseAdapter] = {}
        for cls in adapter_classes:
            inst = cls()
            self.adapters[inst.tool_id] = inst

    def get_detected_tools(self) -> List[Dict[str, str]]:
        """获取本机已检测到的 AI 工具列表"""
        detected = []
        for tool_id, adapter in self.adapters.items():
            is_present = False
            try:
                is_present = adapter.detect()
            except Exception:
                pass
            if is_present:
                detected.append({
                    "tool_id": adapter.tool_id,
                    "tool_name": adapter.tool_name,
                    "icon": adapter.icon,
                    "description": adapter.description,
                })
        return detected

    def scan_all(self, tool_id_filter: Optional[str] = None) -> List[UnifiedSession]:
        """扫描所有（或指定工具）的会话列表"""
        all_sessions: List[UnifiedSession] = []
        for tid, adapter in self.adapters.items():
            if tool_id_filter and tid != tool_id_filter:
                continue
            try:
                if adapter.detect():
                    sessions = adapter.scan_sessions()
                    all_sessions.extend(sessions)
            except Exception as e:
                print(f"[Scanner] 扫描 {adapter.tool_name} 失败: {e}")

        # 按最后更新时间降序排序
        all_sessions.sort(key=lambda s: s.updated_at or datetime.min, reverse=True)
        return all_sessions

    def load_detail(self, session: UnifiedSession) -> UnifiedSession:
        """加载单个会话的详细对话内容"""
        adapter = self.adapters.get(session.tool_id)
        if not adapter:
            return session
        try:
            return adapter.load_session_detail(session)
        except Exception as e:
            print(f"[Scanner] 加载会话详情失败 ({session.session_id}): {e}")
            return session

    def filter_sessions(
        self,
        sessions: List[UnifiedSession],
        keyword: str = "",
        tool_id: str = "",
        workspace: str = "",
    ) -> List[UnifiedSession]:
        """过滤搜索会话"""
        kw = keyword.lower().strip()
        results = []
        for s in sessions:
            if tool_id and s.tool_id != tool_id:
                continue
            if workspace and workspace.lower() not in (s.workspace_path or "").lower():
                continue
            if kw:
                match_title = kw in s.title.lower()
                match_id = kw in s.session_id.lower()
                match_ws = kw in (s.workspace_path or "").lower()
                if not (match_title or match_id or match_ws):
                    continue
            results.append(s)
        return results
