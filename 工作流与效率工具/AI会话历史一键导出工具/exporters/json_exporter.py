"""
JSON / JSONL 导出器 (JSON Exporter)
将 UnifiedSession 导出为标准结构化 JSON 或 JSONL 文件
"""

import os
import re
import json
from typing import Optional

try:
    from core.models import UnifiedSession
except (ImportError, ValueError):
    from ..core.models import UnifiedSession


class JSONExporter:
    """JSON 导出器"""

    @staticmethod
    def sanitize_filename(name: str, max_len: int = 40) -> str:
        clean = re.sub(r'[\\/*?:"<>|\r\n\t]', "_", name).strip()
        clean = re.sub(r'_+', '_', clean)
        clean = clean.strip("._ ")
        if not clean:
            clean = "untitled"
        return clean[:max_len]

    def export(self, session: UnifiedSession, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)

        date_prefix = session.created_at.strftime("%Y%m%d_%H%M") if session.created_at else "nodate"
        safe_title = self.sanitize_filename(session.title)
        sid_short = session.session_id[:8]
        filename = f"{date_prefix}_{session.tool_id}_{sid_short}_{safe_title}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

        return filepath
