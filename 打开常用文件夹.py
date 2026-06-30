# -*- coding: utf-8 -*-
import time
import ctypes
import subprocess
from pathlib import Path
import win32com.client

user32 = ctypes.windll.user32
SW_RESTORE = 9

def organize_smart_layout(layout_config):
    print("====== 开始执行对象池智能列阵 ======\n")
    
    shell = win32com.client.Dispatch("Shell.Application")
    
    # ---------------------------------------------------------
    # 步骤 1：捕获当前所有的资源管理器窗口，建立“对象池”
    # ---------------------------------------------------------
    window_pool = []
    for win in shell.Windows():
        try:
            # 尝试获取路径，如果能获取到，说明是有效的文件浏览器窗口
            path = str(Path(win.Document.Folder.Self.Path).resolve()).lower()
            window_pool.append({
                "win_obj": win,     # COM 对象，用于后期控制 Navigate
                "hwnd": win.HWND,   # 句柄，用于控制移动和置顶
                "path": path,       # 当前所在路径
                "claimed": False    # 标记是否已被我们征用
            })
        except Exception:
            pass

    print(f"[*] 扫描完毕，当前屏幕上共有 {len(window_pool)} 个活动文件夹窗口\n")

    # 存储最终每个配置对应的句柄
    tasks = []

    # ---------------------------------------------------------
    # 步骤 2：第一轮扫描（精确匹配）—— 优先征用已经在目标路径的窗口
    # ---------------------------------------------------------
    for cfg in layout_config:
        target_path = str(Path(cfg["path"]).resolve()).lower()
        matched_hwnd = None
        
        for item in window_pool:
            if not item["claimed"] and item["path"] == target_path:
                matched_hwnd = item["hwnd"]
                item["claimed"] = True
                print(f"[=] 精确匹配: [{Path(cfg['path']).name}] 已经打开，直接锁定！")
                break
                
        tasks.append({"config": cfg, "hwnd": matched_hwnd, "target_path": target_path})

    # ---------------------------------------------------------
    # 步骤 3：第二轮扫描（废物利用）—— 把那些没用的闲置窗口强行“洗脑”
    # ---------------------------------------------------------
    for task in tasks:
        if task["hwnd"] is None:
            # 尝试从对象池里找一个还没被征用的窗口
            for item in window_pool:
                if not item["claimed"]:
                    print(f"[~] 废物利用: 征用无关窗口，强行重定向至 -> [{Path(task['config']['path']).name}]")
                    # 【核心黑科技】底层调用 Navigate 让旧窗口瞬间跳转到新路径！
                    item["win_obj"].Navigate(task["config"]["path"])
                    task["hwnd"] = item["hwnd"]
                    item["claimed"] = True
                    break

    # ---------------------------------------------------------
    # 步骤 4：第三轮（池子干了）—— 如果没用的窗口都不够了，只能新建
    # ---------------------------------------------------------
    known_hwnds = {item["hwnd"] for item in window_pool}
    for task in tasks:
        if task["hwnd"] is None:
            print(f"[+] 池子已空: 正在拉起新窗口 -> [{Path(task['config']['path']).name}]")
            subprocess.Popen(['explorer', '/n,', task["config"]["path"]])
            time.sleep(1.0) # 给系统一点时间渲染新窗口
            
            # 重新扫描捕获新窗口的句柄
            for win in shell.Windows():
                try:
                    if win.HWND not in known_hwnds:
                        path = str(Path(win.Document.Folder.Self.Path).resolve()).lower()
                        if path == task["target_path"]:
                            task["hwnd"] = win.HWND
                            known_hwnds.add(win.HWND)
                            break
                except Exception:
                    continue
                    
            # 终极兜底：如果没扫到，盲抓当前焦点
            if task["hwnd"] is None:
                task["hwnd"] = user32.GetForegroundWindow()

    # ---------------------------------------------------------
    # 步骤 5：终极检阅（乾坤大挪移 + 绝对置顶）
    # ---------------------------------------------------------
    print("\n[*] 正在执行阵型部署...")
    
    # 逆序遍历执行置顶。原因：后置顶的窗口会盖在先置顶的窗口上面。
    # 我们希望配置在第一位的窗口具有最高的焦点级别，所以必须反着来。
    for task in reversed(tasks):
        hwnd = task["hwnd"]
        cfg = task["config"]
        x, y, w, h = cfg["rect"]
        
        if hwnd:
            # 1. 解除最小化
            user32.ShowWindow(hwnd, SW_RESTORE)
            # 2. 移动窗口并调整大小
            user32.MoveWindow(hwnd, x, y, w, h, True)
            # 3. 强行拽到所有界面的最前面
            user32.SetForegroundWindow(hwnd)
        else:
            print(f"  [!] 警告: 遗失了对 {cfg['path']} 的窗口控制权！")
            
    print("\n====== 列阵完美结束！ ======")

if __name__ == "__main__":
    # 配置区
    LAYOUT_CONFIG = [
        {
            "path": r"E:\rocket-nano\scripts\export",
            "rect": (0, 150, 1088, 795)        # 放在左上角
        },
        {
            "path": r"E:\rocket-nano\external\excel",
            "rect": (600, 150, 1088, 795)      # 放在右上角 (紧挨着上一个)
        },
        {
            "path": r"E:\rocket-nano",
            "rect": (0, 250, 1088, 795)
        },
        {
            "path": r"D:\360极速浏览器X下载",
            "rect": (600, 250, 1088, 795)
        }
    ]

    organize_smart_layout(LAYOUT_CONFIG)