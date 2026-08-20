"""
单元测试与适配器功能验证
"""

import os
import sys
import tempfile
import unittest
from datetime import datetime

# 修复 Windows 控制台 GBK 编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 注入路径
test_dir = os.path.dirname(os.path.abspath(__file__))
pkg_dir = os.path.dirname(test_dir)
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from core.models import UnifiedSession, UnifiedMessage, UnifiedToolCall, UnifiedArtifact
from core.scanner import SessionScanner
from exporters import MarkdownExporter, HTMLExporter, JSONExporter, IndexExporter, CleanTextExporter


class TestAIExporter(unittest.TestCase):

    def setUp(self):
        self.scanner = SessionScanner()
        self.temp_dir = tempfile.mkdtemp(prefix="ai_export_test_")

    def test_scanner_detection(self):
        tools = self.scanner.get_detected_tools()
        print(f"\n[Test] Detected {len(tools)} tools on this machine:")
        for t in tools:
            try:
                print(f"  - {t['icon']} {t['tool_name']} ({t['tool_id']})")
            except Exception:
                print(f"  - {t['tool_name']} ({t['tool_id']})")
        self.assertIsInstance(tools, list)

    def test_scan_all_sessions(self):
        sessions = self.scanner.scan_all()
        print(f"\n[Test] Total scanned sessions: {len(sessions)}")
        for s in sessions[:5]:
            print(f"  - [{s.source_tool}] {s.title} ({s.formatted_created_at})")
        self.assertIsInstance(sessions, list)
        self.assertGreater(len(sessions), 0)

    def test_load_session_detail(self):
        sessions = self.scanner.scan_all()
        if sessions:
            sample = sessions[0]
            detailed = self.scanner.load_detail(sample)
            print(f"\n[Test] Loaded detail for session '{detailed.title}':")
            print(f"  Messages count: {len(detailed.messages)}")
            print(f"  Artifacts count: {len(detailed.artifacts)}")
            self.assertIsNotNone(detailed.messages)

    def test_exporters(self):
        dummy_session = UnifiedSession(
            session_id="test_session_12345",
            source_tool="Unit Test AI",
            tool_id="test_ai",
            title="测试导出功能与排版",
            workspace_path=r"d:\MyTools",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            messages=[
                UnifiedMessage(
                    role="user",
                    content="请帮我写一个快速排序算法。",
                    timestamp=datetime.now()
                ),
                UnifiedMessage(
                    role="assistant",
                    content="这是快速排序的 Python 实现：\n\n```python\ndef quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)\n```",
                    thinking="用户需要快速排序算法，先给出递归分治思路，再附带 Python 代码示例。",
                    tool_calls=[
                        UnifiedToolCall(
                            tool_name="code_runner",
                            tool_summary="执行测试用例",
                            arguments={"code": "print(quicksort([3,6,8,10,1,2,1]))"},
                            output="[1, 1, 2, 3, 6, 8, 10]"
                        )
                    ],
                    timestamp=datetime.now()
                )
            ],
            artifacts=[
                UnifiedArtifact(
                    title="quicksort.py",
                    content="def quicksort(arr): return arr",
                    artifact_type="code"
                )
            ]
        )

        md_exp = MarkdownExporter()
        html_exp = HTMLExporter()
        json_exp = JSONExporter()
        clean_exp = CleanTextExporter()
        index_exp = IndexExporter()

        md_file = md_exp.export(dummy_session, self.temp_dir)
        html_file = html_exp.export(dummy_session, self.temp_dir)
        json_file = json_exp.export(dummy_session, self.temp_dir)
        clean_md_file = clean_exp.export_clean_markdown(dummy_session, self.temp_dir)
        clean_txt_file = clean_exp.export_clean_text(dummy_session, self.temp_dir)

        self.assertTrue(os.path.exists(md_file))
        self.assertTrue(os.path.exists(html_file))
        self.assertTrue(os.path.exists(json_file))
        self.assertTrue(os.path.exists(clean_md_file))
        self.assertTrue(os.path.exists(clean_txt_file))

        with open(clean_md_file, "r", encoding="utf-8") as f:
            clean_content = f.read()
            self.assertIn("快速排序算法", clean_content)
            self.assertNotIn("用户需要快速排序算法", clean_content)  # 思维链已被剔除
            self.assertNotIn("code_runner", clean_content)  # 工具调用已被剔除

        index_exp.export([
            {
                "session": dummy_session,
                "md_path": os.path.relpath(md_file, self.temp_dir),
                "html_path": os.path.relpath(html_file, self.temp_dir),
                "json_path": os.path.relpath(json_file, self.temp_dir),
                "clean_md_path": os.path.relpath(clean_md_file, self.temp_dir),
                "clean_txt_path": os.path.relpath(clean_txt_file, self.temp_dir),
            }
        ], self.temp_dir)

        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "INDEX.md")))
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "index.html")))
        print("\n[Test] All exporter assertions (including clean text exporter) passed!")


if __name__ == "__main__":
    unittest.main()
