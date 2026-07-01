# -*- coding: utf-8 -*-
import os
import re
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading

# ==========================================
# 【配置区】
# ==========================================
TARGET_DIR = os.path.dirname(os.path.abspath(__file__))
VALID_EXTENSIONS = {".txt", ".md", ".json", ".html", ".js"}
# 因为加入了网盘网页拉取，超时时间稍微设长一点
TIMEOUT = 8 
CURRENT_SCRIPT_PATH = Path(__file__).resolve()
# ==========================================

url_cache = {}
print_lock = threading.Lock()

def safe_print(msg: str):
    """线程安全的打印函数"""
    with print_lock:
        print(msg)

def is_url_valid(url: str) -> bool:
    """
    核心检测逻辑：包含网盘深度嗅探
    """
    if url in url_cache:
        status = "✅(缓存有效)" if url_cache[url] else "❌(缓存失效)"
        safe_print(f"    -> [命中缓存] {url} {status}")
        return url_cache[url]

    safe_print(f"    -> [网络探测] {url} ...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9'
    }
    
    try:
        # 【核心修正】：统一使用 GET 获取网页内容，用于网盘深度检测
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        
        # 1. 基础状态码拦截（拦截 404 等常规死链）
        if response.status_code >= 400 and response.status_code not in (401, 403):
            safe_print(f"      ❌ [死链: HTTP {response.status_code}] {url}")
            url_cache[url] = False
            return False
            
        # 2. 网盘“软失效”深度检测
        html_text = response.text
        
        # 常见网盘失效关键字
        dead_keywords = [
            "百度网盘-链接不存在", 
            "啊哦，你所访问的页面不存在了", 
            "分享无缝切换", "你来晚了", "分享已取消", "分享已被取消", 
            "链接已失效", "文件已取消分享", 
            "很抱歉，此链接已失效", "分享内容可能已被删除", 
            "文件不存在", "该分享已过期"
        ]
        
        for keyword in dead_keywords:
            if keyword in html_text:
                safe_print(f"      ❌ [死链: 网盘失效提取] {url}")
                url_cache[url] = False
                return False
                
        # 没触发任何死亡条件，认为是活链接
        safe_print(f"      ✅ [存活] {url}")
        valid = True
        
    except requests.RequestException as e:
        valid = False
        safe_print(f"      ❌ [死链: 网络异常或超时] {url}")

    url_cache[url] = valid
    return valid

def read_file_safely(file_path: Path):
    encodings = ['utf-8', 'gbk', 'utf-8-sig']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read(), enc
        except UnicodeDecodeError:
            continue
    return None, None

def process_file(file_path: Path, executor: ThreadPoolExecutor):
    safe_print(f"\n[📂] 打开文件: {file_path.name}")
    content, used_encoding = read_file_safely(file_path)
    
    if content is None:
        safe_print("  [-] 无法读取文件编码，已跳过。")
        return

    # 正则提取 URL
    pattern = r'https?://[^\s<>"\'()]+'
    raw_urls = set(re.findall(pattern, content))

    if not raw_urls:
        safe_print("  [-] 未发现任何链接。")
        return

    clean_urls = {url.rstrip('.,;:!?，。；：！？') for url in raw_urls}
    safe_print(f"  [*] 提取到 {len(clean_urls)} 个独立链接，开始并发检测...")

    invalid_urls = []
    
    # 提交给线程池处理
    future_to_url = {executor.submit(is_url_valid, url): url for url in clean_urls}
    for future in future_to_url:
        url = future_to_url[future]
        if not future.result():
            invalid_urls.append(url)

    if not invalid_urls:
        safe_print("  [√] 完美！该文件内所有链接均有效。")
        return

    # 替换死链文本
    new_content = content
    for dead_url in invalid_urls:
        replacement = f"【 ■■■！！！××× 失效死链: {dead_url} ×××！！！■■■ 】"
        new_content = new_content.replace(dead_url, replacement)

    # 写回文件
    with open(file_path, 'w', encoding=used_encoding) as f:
        f.write(new_content)

    safe_print(f"  [+] 修复完毕: 已在 '{file_path.name}' 中暴力高亮了 {len(invalid_urls)} 个死链。")

def scan_directory(directory: str):
    print("====== 开始全功率死链扫描 ======")
    dir_path = Path(directory)
    
    if not dir_path.exists() or not dir_path.is_dir():
        print(f"[!] 目录不存在: {directory}")
        return

    files_scanned = 0
    with ThreadPoolExecutor(max_workers=10) as global_executor:
        for file_path in dir_path.rglob("*"):
            if file_path.resolve() == CURRENT_SCRIPT_PATH:
                continue
                
            if file_path.is_file() and file_path.suffix.lower() in VALID_EXTENSIONS:
                files_scanned += 1
                process_file(file_path, global_executor)
            
    print(f"\n====== 扫描全部结束！共扫描了 {files_scanned} 个有效文件 ======")
    input("\n[*] 按回车键 (Enter) 退出...")

if __name__ == "__main__":
    scan_directory(TARGET_DIR)