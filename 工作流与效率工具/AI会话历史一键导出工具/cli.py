"""
命令行交互接口 (CLI Interface)
支持自动化与终端一键批量导出 AI 会话历史（支持完整版与精简优化版）
"""

import os
import sys
import argparse
from datetime import datetime
from typing import List

# 修复 Windows 控制台编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 确保能找到本包模块
pkg_dir = os.path.dirname(os.path.abspath(__file__))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

from core.scanner import SessionScanner
from exporters import MarkdownExporter, HTMLExporter, JSONExporter, IndexExporter, CleanTextExporter


def run_cli(args: argparse.Namespace):
    scanner = SessionScanner()

    print("=========================================================")
    print("  🧰 AI 会话历史一键导出工具 (CLI 模式)")
    print("=========================================================")

    # 1. 检测本机工具
    detected_tools = scanner.get_detected_tools()
    print(f"[*] 正在检测本机已安装的 AI 工具...")
    if not detected_tools:
        print("[!] 未检测到任何支持的 AI 工具历史数据。")
        return

    for t in detected_tools:
        try:
            print(f"  + [{t['icon']}] {t['tool_name']} ({t['tool_id']})")
        except Exception:
            print(f"  + {t['tool_name']} ({t['tool_id']})")
    print("")

    # 2. 扫描会话
    tool_filter = args.tool if args.tool and args.tool != "all" else None
    print(f"[*] 正在扫描会话记录 (过滤: {tool_filter or '所有工具'})...")
    sessions = scanner.scan_all(tool_id_filter=tool_filter)

    if args.keyword:
        sessions = scanner.filter_sessions(sessions, keyword=args.keyword)

    print(f"[+] 共发现 {len(sessions)} 条历史会话！\n")
    if not sessions:
        print("[!] 没有匹配到任何会话。")
        return

    if args.list:
        print("--- 会话列表 ---")
        for i, s in enumerate(sessions[:50], 1):
            print(f"{i:2d}. [{s.source_tool}] {s.title} ({s.formatted_created_at}) -> {s.workspace_path or '无工作区'}")
        if len(sessions) > 50:
            print(f"... 还有 {len(sessions) - 50} 条未显示")
        return

    # 3. 确定导出选项
    output_dir = os.path.abspath(args.output or os.path.join(os.getcwd(), "exported_ai_sessions"))
    formats = [f.strip().lower() for f in args.format.split(",") if f.strip()]
    if args.clean and "clean_md" not in formats:
        formats.append("clean_md")
    if not formats:
        formats = ["md", "html", "clean_md"]

    print(f"[*] 导出目标路径: {output_dir}")
    print(f"[*] 导出格式: {', '.join(formats)}")
    print(f"[*] 开始解析与导出 {len(sessions)} 个会话...")

    md_exp = MarkdownExporter() if "md" in formats else None
    html_exp = HTMLExporter() if "html" in formats else None
    json_exp = JSONExporter() if "json" in formats else None
    clean_exp = CleanTextExporter() if ("clean_md" in formats or "clean_txt" in formats or "clean" in formats) else None
    index_exp = IndexExporter()

    exported_records = []
    for idx, s in enumerate(sessions, 1):
        try:
            print(f"  [{idx}/{len(sessions)}] 解析并导出: [{s.source_tool}] {s.title[:35]}...", end="\r")
        except Exception:
            pass
        full_session = scanner.load_detail(s)

        record = {"session": full_session}
        tool_sub_dir = os.path.join(output_dir, full_session.tool_id)

        if md_exp:
            md_path = md_exp.export(full_session, tool_sub_dir)
            record["md_path"] = os.path.relpath(md_path, output_dir)

        if html_exp:
            html_path = html_exp.export(full_session, tool_sub_dir)
            record["html_path"] = os.path.relpath(html_path, output_dir)

        if json_exp:
            json_path = json_exp.export(full_session, tool_sub_dir)
            record["json_path"] = os.path.relpath(json_path, output_dir)

        if clean_exp and ("clean_md" in formats or "clean" in formats):
            cmd_path = clean_exp.export_clean_markdown(full_session, tool_sub_dir)
            record["clean_md_path"] = os.path.relpath(cmd_path, output_dir)

        if clean_exp and "clean_txt" in formats:
            ctxt_path = clean_exp.export_clean_text(full_session, tool_sub_dir)
            record["clean_txt_path"] = os.path.relpath(ctxt_path, output_dir)

        exported_records.append(record)

    print("\n[+] 对话内容已成功导出！")
    print("[*] 正在生成全局导航索引 (INDEX.md & index.html)...")
    index_exp.export(exported_records, output_dir)

    print("=========================================================")
    print(f"  🎉 导出完成！已成功导出 {len(exported_records)} 条会话。")
    print(f"  📂 导出目录: {output_dir}")
    print(f"  🌐 导航主页: {os.path.join(output_dir, 'index.html')}")
    print(f"  📄 索引文档: {os.path.join(output_dir, 'INDEX.md')}")
    print("=========================================================")


def parse_args():
    parser = argparse.ArgumentParser(description="AI 会话历史一键导出工具")
    parser.add_argument("--all", action="store_true", help="一键全量导出所有检测到的 AI 会话")
    parser.add_argument("-t", "--tool", type=str, default="", help="指定导出的 AI 工具 ID (如 antigravity, kiro, workbuddy, vscode_copilot, claude_code, cline 等)")
    parser.add_argument("-k", "--keyword", type=str, default="", help="按关键词过滤会话标题或项目路径")
    parser.add_argument("-f", "--format", type=str, default="md,html,clean_md", help="导出格式，逗号分隔，可选 md,html,json,clean_md,clean_txt (默认: md,html,clean_md)")
    parser.add_argument("--clean", action="store_true", help="同时导出精简优化版对话文本")
    parser.add_argument("-o", "--output", type=str, default="", help="自定义导出目录路径 (默认: ./exported_ai_sessions)")
    parser.add_argument("-l", "--list", action="store_true", help="仅列出已发现的会话清单，不执行导出")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_cli(args)
