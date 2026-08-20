"""
AI 会话历史一键导出工具 - 主程序入口
默认双击启动现代图形化 GUI 界面，带参数时启动自动化 CLI 模式
"""

import sys
import os

# 确保包路径正确
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from cli import parse_args, run_cli


def main():
    if len(sys.argv) > 1 and not (len(sys.argv) == 2 and sys.argv[1] in ("--gui", "-g")):
        args = parse_args()
        run_cli(args)
    else:
        try:
            from gui import run_gui
            run_gui()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            try:
                import tkinter as tk
                import tkinter.messagebox as mb
                root = tk.Tk()
                root.withdraw()
                mb.showerror("AI 导出工具错误", f"程序运行遇到错误：\n\n{e}\n\n详细信息：\n{tb}")
                root.destroy()
            except Exception:
                print(f"[Fatal Error] {e}\n{tb}")


if __name__ == "__main__":
    main()
