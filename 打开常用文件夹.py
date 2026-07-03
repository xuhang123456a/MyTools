# -*- coding: utf-8 -*-
"""
对象池智能列阵 —— 一键把常用文件夹按你指定的位置/大小摆好。

特点：
- 复用已打开的窗口（精确匹配 > 废物利用 > 新建），不会疯狂堆窗口。
- 每个窗口的位置和大小由你在 LAYOUT_CONFIG 里用 rect 精确控制。
- DPI 感知，在 125%/150% 缩放下坐标也准确。
- 强制置顶采用线程输入附加技巧，绕过 Windows 前台锁。
- rect 可留空（None），则自动在网格里补一个位置。
"""
import time
import ctypes
import subprocess
from ctypes import wintypes
from pathlib import Path

import win32com.client

# ---------------------------------------------------------
# 常量与 Win32 句柄
# ---------------------------------------------------------
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
SPI_GETWORKAREA = 0x0030


def enable_dpi_awareness():
    """开启 DPI 感知，保证 MoveWindow 用的是真实物理像素坐标。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            user32.SetProcessDPIAware()  # 老系统兜底
        except Exception:
            pass


def get_work_area():
    """获取主屏工作区（排除任务栏）(left, top, right, bottom)。"""
    rect = wintypes.RECT()
    if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
        return rect.left, rect.top, rect.right, rect.bottom
    return 0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def auto_grid_rect(index, total, columns=2, gap=8):
    """给没有指定 rect 的窗口，自动算一个网格位置作为兜底。"""
    left, top, right, bottom = get_work_area()
    area_w = right - left
    area_h = bottom - top
    columns = max(1, min(columns, total))
    rows = (total + columns - 1) // columns
    cell_w = (area_w - gap * (columns + 1)) // columns
    cell_h = (area_h - gap * (rows + 1)) // rows
    r, c = divmod(index, columns)
    x = left + gap + c * (cell_w + gap)
    y = top + gap + r * (cell_h + gap)
    return (x, y, cell_w, cell_h)


def normalize_path(raw):
    """统一路径格式，便于匹配（处理大小写、尾部斜杠、盘符根）。"""
    try:
        return str(Path(raw).resolve()).rstrip("\\/").lower()
    except Exception:
        return str(raw).rstrip("\\/").lower()


def force_foreground(hwnd):
    """
    强制把窗口拉到前台。
    直接 SetForegroundWindow 常被 Windows 前台锁拦截，
    这里通过附加前台线程输入的方式绕过。
    """
    try:
        fg = user32.GetForegroundWindow()
        cur_thread = kernel32.GetCurrentThreadId()
        fg_thread = user32.GetWindowThreadProcessId(fg, None)
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)

        user32.AttachThreadInput(cur_thread, fg_thread, True)
        user32.AttachThreadInput(cur_thread, target_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.AttachThreadInput(cur_thread, fg_thread, False)
        user32.AttachThreadInput(cur_thread, target_thread, False)
    except Exception:
        user32.SetForegroundWindow(hwnd)


def get_explorer_windows(shell):
    """扫描当前所有有效的资源管理器窗口，返回对象池。"""
    pool = []
    for win in shell.Windows():
        try:
            path = normalize_path(win.Document.Folder.Self.Path)
            pool.append({
                "win_obj": win,
                "hwnd": win.HWND,
                "path": path,
                "claimed": False,
            })
        except Exception:
            pass
    return pool


def organize_smart_layout(layout_config):
    print("====== 开始执行对象池智能列阵 ======\n")

    enable_dpi_awareness()

    shell = win32com.client.Dispatch("Shell.Application")
    window_pool = get_explorer_windows(shell)
    print(f"[*] 扫描完毕，当前共有 {len(window_pool)} 个活动文件夹窗口\n")

    total = len(layout_config)
    tasks = []
    for i, cfg in enumerate(layout_config):
        # rect 缺省或为 None 时，自动补一个网格位置
        rect = cfg.get("rect") or auto_grid_rect(i, total)
        tasks.append({
            "path": cfg["path"],
            "rect": rect,
            "target_path": normalize_path(cfg["path"]),
            "hwnd": None,
        })

    # 第一轮：精确匹配，优先锁定已在目标路径的窗口
    for task in tasks:
        for item in window_pool:
            if not item["claimed"] and item["path"] == task["target_path"]:
                task["hwnd"] = item["hwnd"]
                item["claimed"] = True
                print(f"[=] 精确匹配: [{Path(task['path']).name}] 已打开，直接锁定")
                break

    # 第二轮：废物利用，把闲置窗口 Navigate 到目标路径
    for task in tasks:
        if task["hwnd"] is not None:
            continue
        for item in window_pool:
            if not item["claimed"]:
                print(f"[~] 废物利用: 重定向闲置窗口 -> [{Path(task['path']).name}]")
                try:
                    item["win_obj"].Navigate(task["path"])
                except Exception:
                    continue
                task["hwnd"] = item["hwnd"]
                item["claimed"] = True
                break

    # 第三轮：池子空了，新建窗口
    known_hwnds = {item["hwnd"] for item in window_pool}
    for task in tasks:
        if task["hwnd"] is not None:
            continue
        print(f"[+] 池子已空: 新建窗口 -> [{Path(task['path']).name}]")
        subprocess.Popen(["explorer", task["path"]])

        for _ in range(20):  # 最多等 2 秒轮询新窗口
            time.sleep(0.1)
            for win in shell.Windows():
                try:
                    if win.HWND in known_hwnds:
                        continue
                    if normalize_path(win.Document.Folder.Self.Path) == task["target_path"]:
                        task["hwnd"] = win.HWND
                        known_hwnds.add(win.HWND)
                        break
                except Exception:
                    continue
            if task["hwnd"] is not None:
                break

    # 部署阵型：逆序置顶，保证第一个配置的窗口最终获得焦点
    print("\n[*] 正在执行阵型部署...")
    for task in reversed(tasks):
        hwnd = task["hwnd"]
        if not hwnd:
            print(f"  [!] 警告: 遗失了对 {task['path']} 的窗口控制权")
            continue
        x, y, w, h = task["rect"]
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.MoveWindow(hwnd, x, y, w, h, True)
        force_foreground(hwnd)

    print("\n====== 列阵完美结束！ ======")


if __name__ == "__main__":
    # 配置区：rect = (x, y, 宽, 高)，单位是物理像素，自己想怎么摆就怎么摆
    # 不想指定某个窗口的位置时，把 rect 写成 None 即可自动补位
    LAYOUT_CONFIG = [
        {
            "path": r"E:\rocket-nano\scripts\export",
            "rect": (100, 150, 1088, 600),        # 左上
        },
        {
            "path": r"E:\rocket-nano\external\excel",
            "rect": (750, 150, 1088, 600),      # 右上
        },
        {
            "path": r"E:\rocket-nano",
            "rect": (100, 250, 1088, 600),      # 左下
        },
        {
            "path": r"D:\360极速浏览器X下载",
            "rect": (750, 250, 1088, 600),    # 右下
        },
    ]

    organize_smart_layout(LAYOUT_CONFIG)
