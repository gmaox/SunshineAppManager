import os, sys, time, glob, json, re, shutil, threading, configparser, subprocess, urllib3
import tkinter as tk
from tkinter import filedialog, messagebox

import winreg, win32com.client, pythoncom, win32api, win32con, win32security, win32process, win32gui, psutil, vdf
from PIL import Image, ImageDraw, ImageFont, ImageTk
from colorthief import ColorThief
from io import BytesIO
import requests, webbrowser
from icoextract import IconExtractor, IconExtractorError
from PyQt5 import QtWidgets, QtCore, QtGui

config = configparser.ConfigParser()
# 始终使用与代码文件同级的绝对路径，避免相对工作目录导致的读写不一致
if getattr(sys, 'frozen', False):
    # 打包后的可执行文件：使用可执行文件所在目录
    config_file_path = os.path.join(os.path.dirname(sys.executable), 'config.ini')
    SCRIPT_DIR = os.path.dirname(sys.executable)
else:
    # 开发环境：使用当前模块文件所在目录下的 config.ini（绝对路径）
    config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    SCRIPT_DIR = os.path.dirname(__file__)

# 脚本目录下的 temp 文件夹，用于暂存封面文件
TEMP_COVERS_DIR = os.path.join(SCRIPT_DIR, 'temp')
hidden_files = []
skipped_entries = []
folder_selected = ''
close_after_completion = True  # 默认开启
pseudo_sorting_enabled = False  # 新增伪排序适应选项，默认关闭
auto_delete_orphaned_entries = False  # 自动删除孤立条目（不再询问），默认关闭

def get_app_install_path():
    app_name = "sunshine"
    try:
        # 打开注册表键，定位到安装路径信息
        registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                                      r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
        # 遍历注册表中的子项，查找对应应用名称
        for i in range(winreg.QueryInfoKey(registry_key)[0]):
            subkey_name = winreg.EnumKey(registry_key, i)
            subkey = winreg.OpenKey(registry_key, subkey_name)
            try:
                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                if app_name.lower() in display_name.lower():
                    install_location, _ = winreg.QueryValueEx(subkey, "DisplayIcon")
                    if os.path.exists(install_location):
                        return os.path.dirname(install_location)
            except FileNotFoundError:
                continue
    except Exception as e:
        print(f"Error: {e}")
    print(f"未检测到安装目录！")
    return os.path.dirname(sys.executable)
APP_INSTALL_PATH=get_app_install_path()

def load_apps_json(json_path):
    # 加载已有的 apps.json
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            # 如果普通 utf-8 读取失败，尝试用带 BOM 的 utf-8-sig 读取并回写为纯 utf-8
            try:
                with open(json_path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                try:
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                except Exception as e2:
                    print(f"保存为 utf-8 失败: {e2}")
                return data
            except Exception as e2:
                print(f"读取 apps.json 失败: {e} / {e2}")
                # 使用 Win32 API弹窗提示
                try:
                    msg = f"读取 apps.json 失败：\n{e}\n{e2}\n。"
                    print("读取错误",msg)
                    sys.exit(1)
                except Exception:
                    pass
    else:
        # 如果文件不存在，返回一个空的基础结构
        return {"env": "", "apps": []}
    
def save_apps_json(apps_json, file_path):
    # 将更新后的 apps.json 保存到文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(apps_json, f, ensure_ascii=False, indent=4)
    
    # 将 temp 目录中的所有封面文件一起写入到目标目录
    if os.path.exists(TEMP_COVERS_DIR):
        try:
            covers_target_dir = os.path.join(APP_INSTALL_PATH, 'config', 'covers')
            os.makedirs(covers_target_dir, exist_ok=True)
            
            for filename in os.listdir(TEMP_COVERS_DIR):
                src_path = os.path.join(TEMP_COVERS_DIR, filename)
                dst_path = os.path.join(covers_target_dir, filename)
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                    print(f"已将封面文件 {filename} 写入目标目录")
            
            # 清空 temp 目录
            shutil.rmtree(TEMP_COVERS_DIR)
            print("已清空 temp 目录")
        except Exception as e:
            print(f"处理 temp 封面文件失败: {e}")
def load_config():
    """加载配置文件并同步 `folder_selected` 变量"""
    global close_after_completion, pseudo_sorting_enabled, hidden_files, folder, folder_selected, steam_excluded_games, auto_delete_orphaned_entries
    # 优先使用 UTF-8 打开配置文件以避免系统默认编码（如 GBK）导致的 UnicodeDecodeError。
    # 如果文件不存在则跳过，后续会调用 save_config() 创建默认文件。
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                config.read_file(f)
        except UnicodeDecodeError:
            try:
                # 尝试带 BOM 的 utf-8-sig
                with open(config_file_path, 'r', encoding='utf-8-sig') as f:
                    config.read_file(f)
            except Exception:
                # 回退到系统默认编码（例如 GBK/CP936），但使用 errors='replace' 避免抛出异常
                with open(config_file_path, 'r', encoding='cp936', errors='replace') as f:
                    config.read_file(f)
    else:
        # 文件不存在，保持 config 为空，后续 save_config() 会创建它
        pass
    folder = config.get('Settings', 'folder_selected', fallback='')
    # 同步到运行时使用的变量名
    folder_selected = folder
    hidden_files_str = config.get('Settings', 'hidden_files', fallback='')  # 获取隐藏的文件路径字符串
    hidden_files = hidden_files_str.split(',') if hidden_files_str else []  # 将字符串转换为列表
    close_after_completion = config.getboolean('Settings', 'close_after_completion', fallback=True)  # 获取关闭选项
    pseudo_sorting_enabled = config.getboolean('Settings', 'pseudo_sorting_enabled', fallback=False)  # 获取伪排序选项
    # 新增 steam_excluded_games
    steam_excluded_games_str = config.get('Settings', 'steam_excluded_games', fallback='')
    steam_excluded_games = steam_excluded_games_str.split(',') if steam_excluded_games_str else []
    # 新增 auto_delete_orphaned_entries
    auto_delete_orphaned_entries = config.getboolean('Settings', 'auto_delete_orphaned_entries', fallback=False)
    if os.path.exists(config_file_path)==False:
        save_config()  #没有配置文件保存下
    # 检查 folder 是否有效
    if not os.path.isdir(folder):
        
        # 弹窗提示
        messagebox.showinfo(
            "首次启动QSAA - 关于工作路径",
            "这似乎是你第一次启动QSAA，请了解工作路径是什么\n\n该程序会扫描工作路径的快捷方式，加入到Sunshine中\n程序默认工作路径为：程序同级路径\\appfolder\n游戏添加方法：快速添加按钮/主页添加steam游戏/手动拖入文件夹\n工作目录可在主页中修改\ntip：若选择桌面目录，主页的排除功能是很有用的（排除非游戏快捷方式）",
            icon="question"
        )
        folder = os.path.realpath(os.path.join(os.path.dirname(sys.executable), "appfolder")).replace("\\", "/")
        # 同步两个变量，确保后续代码使用的 `folder_selected` 有值
        folder_selected = folder
        if not os.path.exists(folder):
            os.makedirs(folder)  # 创建目录
        #folder = os.path.realpath(os.path.join(os.path.expanduser("~"), "Desktop")).replace("\\", "/") + "\n\n选择"是"使用程序目录，选择"否"使用桌面目录（之后可随时修改）"
        save_config()
    return folder

def save_config():
    """保存选择的目录到配置文件"""
    try:
        global hidden_files, folder, folder_selected, close_after_completion, pseudo_sorting_enabled, steam_excluded_games, auto_delete_orphaned_entries  # 添加全局变量声明
        # 优先使用运行时的 `folder_selected`，保持一致性
        if folder_selected:
            folder = folder_selected
        config['Settings'] = {
            'folder_selected': folder,
            # 确保以字符串形式写入配置文件，避免 configparser 在不同环境下解析不一致
            'close_after_completion': str(close_after_completion),
            'pseudo_sorting_enabled': str(pseudo_sorting_enabled),
            # 将 hidden_files 列表转换为逗号分隔的字符串
            'hidden_files': ','.join(hidden_files) if hidden_files else '',
            # 新增 steam_excluded_games
            'steam_excluded_games': ','.join(steam_excluded_games) if steam_excluded_games else '',
            # 新增 auto_delete_orphaned_entries
            'auto_delete_orphaned_entries': str(auto_delete_orphaned_entries)
        }
        # 显式使用 UTF-8 编码写入，确保跨平台和 BOM 行为一致
        with open(config_file_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
    except Exception as e:
        print(f"保存配置文件时出错: {e}")

def _build_unique_shortcut_path(target_folder, base_name):
    """Generate a non-conflicting .lnk path in target folder."""
    candidate = os.path.join(target_folder, f"{base_name}.lnk")
    if not os.path.exists(candidate):
        return candidate

    index = 1
    while True:
        candidate = os.path.join(target_folder, f"{base_name} ({index}).lnk")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def add_files_to_work_folder_as_shortcuts(file_paths):
    """
    Add dropped .exe/.lnk files into work folder as shortcuts.
    - .exe: create new .lnk
    - .lnk: copy as .lnk (with auto-rename on name conflict)
    """
    global folder_selected

    load_config()
    if not folder_selected:
        folder_selected = os.path.realpath(
            os.path.join(os.path.dirname(sys.executable), "appfolder")
        ).replace("\\", "/")

    os.makedirs(folder_selected, exist_ok=True)
    shell = win32com.client.Dispatch("WScript.Shell")

    result = {
        "work_folder": folder_selected,
        "created": [],
        "skipped": [],
        "errors": [],
    }

    for raw_path in file_paths or []:
        src = (raw_path or "").strip().strip('"')
        if not src:
            continue
        if not os.path.exists(src):
            result["errors"].append((src, "file_not_found"))
            continue

        ext = os.path.splitext(src)[1].lower()
        if ext not in (".exe", ".lnk"):
            result["skipped"].append(src)
            continue

        base_name = os.path.splitext(os.path.basename(src))[0]
        shortcut_path = _build_unique_shortcut_path(folder_selected, base_name)

        try:
            if ext == ".lnk":
                shutil.copy2(src, shortcut_path)
            else:
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.TargetPath = src
                shortcut.WorkingDirectory = os.path.dirname(src)
                shortcut.IconLocation = src
                shortcut.save()
            result["created"].append(shortcut_path)
            print(f"已创建快捷方式: {shortcut_path}")
        except Exception as e:
            result["errors"].append((src, str(e)))
            print(f"创建快捷方式失败: {src} -> {e}")

    return result
def get_lnk_files(include_hidden=False):
    # 获取当前工作目录下的所有 .lnk 文件
    lnk_files = glob.glob("*.lnk")
    valid_lnk_files = []
    
    # 过滤掉指向文件夹的快捷方式和已隐藏文件
    for lnk in lnk_files:
        try:
            # 检查是否在隐藏列表中（当不需要包含隐藏文件时）
            if not include_hidden and lnk in hidden_files:
                continue
                
            target_path = get_target_path_from_lnk(lnk)
            if os.path.isdir(target_path):
                print(f"跳过文件夹快捷方式: {lnk} -> {target_path}")
            else:
                valid_lnk_files.append(lnk)
        except Exception as e:
            print(f"无法获取 {lnk} 的目标路径: {e}")
    
    if include_hidden:
        print("找到所有.lnk文件（包含已隐藏）:")
    else:
        print("找到的可见.lnk文件:")
        
    for idx, lnk in enumerate(valid_lnk_files):
        print(f"{idx+1}. {lnk}")
    return valid_lnk_files

def get_target_path_from_lnk(lnk_file):
    pythoncom.CoInitialize()
    # 使用 win32com 获取快捷方式目标路径
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(lnk_file)
    return shortcut.TargetPath

def extract_icon(exe_path):
    try:
        extractor = IconExtractor(exe_path)
        output_icon_path = "temp_icon.ico"
        extractor.export_icon(output_icon_path, num=0)
        return output_icon_path
    except IconExtractorError as e:
        print(f"提取图标失败: {e}")
        return None

def get_dominant_colors(image, num_colors=2):
    with BytesIO() as output:
        image.save(output, format="PNG")
        img_bytes = output.getvalue()

    color_thief = ColorThief(BytesIO(img_bytes))
    return color_thief.get_palette(color_count=num_colors)

def create_image_with_icon(exe_path, output_path ,idx):
    global skipped_entries  # 声明使用全局变量
    try:
        # 检查是否为 .ico 文件
        if exe_path.lower().endswith('.ico'):
            icon_path = exe_path  # 直接使用 .ico 文件
        else:
            icon_path = extract_icon(exe_path)
            if icon_path is None:
                print(f"无法提取图标: {exe_path}")
                return

        with Image.open(icon_path) as icon_img:
            # 确保图标是RGBA模式
            if icon_img.mode != 'RGBA':
                icon_img = icon_img.convert('RGBA')

            icon_width, icon_height = icon_img.size

            # 调整图标大小，使最长边为 256 像素（无论原图大或小）。
            # 保持宽高比。直接改变原图以节省内存。
            max_dim = max(icon_width, icon_height)
            if max_dim != 256:
                scale = 256.0 / max_dim
                new_w = int(icon_width * scale)
                new_h = int(icon_height * scale)
                # Pillow 10+ removed ANTIALIAS; use LANCZOS which is equivalent
                icon_img = icon_img.resize((new_w, new_h), Image.LANCZOS)
                icon_width, icon_height = icon_img.size

            dominant_colors = get_dominant_colors(icon_img)
            # 将两个主要颜色调暗30%
            color1 = tuple(int(c * 0.7) for c in dominant_colors[0])
            color2 = tuple(int(c * 0.7) for c in dominant_colors[1])

            # Use PIL native gradient composition instead of per-pixel Python loops.
            # This greatly reduces CPU load and keeps UI responsive while covers are generated.
            # diagonal gradient: blend color1→color2 from top-left to bottom-right
            try:
                # create mask manually since linear_gradient doesn't support diagonal directly
                gradient_mask = Image.new('L', (600, 900))
                pix = gradient_mask.load()
                for yy in range(900):
                    for xx in range(600):
                        ratio = (xx / 600 + yy / 900) / 2
                        pix[xx, yy] = int(ratio * 255)
                bg_1 = Image.new('RGBA', (600, 900), color1 + (255,))
                bg_2 = Image.new('RGBA', (600, 900), color2 + (255,))
                img = Image.composite(bg_2, bg_1, gradient_mask)
            except Exception:
                # Fallback for any unexpected error, still manual diagonal loop
                img = Image.new('RGBA', (600, 900), color=color1 + (255,))
                draw = ImageDraw.Draw(img)
                for y in range(900):
                    for x in range(600):
                        ratio_x = x / 600
                        ratio_y = y / 900
                        ratio = (ratio_x + ratio_y) / 2
                        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                        draw.point((x, y), fill=(r, g, b, 255))

            icon_x = (600 - icon_width) // 2
            icon_y = (900 - icon_height) // 2
            img.paste(icon_img, (icon_x, icon_y), icon_img.convert('RGBA'))

            img.save(output_path, format="PNG")
            print(f"图像已保存至 {output_path}")

        try:
            if not exe_path.lower().endswith('.ico'):
                os.remove(icon_path)  # 仅在提取图标时删除临时文件
            print(f"\n {exe_path}\n")
        except PermissionError:
            print(f"无法删除临时图标文件: {icon_path}. 稍后再试.")
            time.sleep(1)
            os.remove(icon_path)

    except Exception as e:
        print(f"创建图像时发生异常，跳过此文件: {exe_path}\n异常信息: {e}")
        skipped_entries.append(idx)  # 记录异常条目


def generate_app_entry(lnk_file, index):
    # 跳过已记录的异常条目
    if index in skipped_entries:
        print(f"跳过已记录的异常条目: {lnk_file}")
        return None  # 返回 None 以表示跳过该条目

    # 判断 lnk_file 是否为 .url 文件
    if lnk_file.lower().endswith('.url'):
        entry = {
            "name": os.path.splitext(lnk_file)[0],  # 使用快捷方式文件名作为名称
            "output": "",
            "cmd": "",
            "exclude-global-prep-cmd": "false",
            "elevated": "false",
            "auto-detach": "true",
            "wait-all": "true",
            "exit-timeout": "5",
            "menu-cmd": "",
            "image-path": f"output_image{index}.png",
            "detached": [
                f"\"{os.path.abspath(lnk_file)}\""
            ]
        }
    else:
        # 为每个快捷方式生成对应的 app 条目
        entry = {
            "name": os.path.splitext(lnk_file)[0],  # 使用快捷方式文件名作为名称
            "output": "",
            "cmd": f"\"{os.path.abspath(lnk_file)}\"",
            "exclude-global-prep-cmd": "false",
            "elevated": "false",
            "auto-detach": "true",
            "wait-all": "true",
            "exit-timeout": "5",
            "menu-cmd": "",
            "image-path": f"output_image{index}.png",
        }
    return entry

def add_entries_to_apps_json(valid_lnk_files, apps_json, modified_target_paths,image_target_paths):
    
    # 为每个有效的快捷方式生成新的条目并添加到 apps 中
    for index, lnk_file in enumerate(valid_lnk_files):
        # 检查是否在 modified_target_paths 中标记为存在
        if any(target_path == lnk_file and is_existing for target_path, is_existing in modified_target_paths):
            print(f"跳过已存在的条目: {lnk_file}")
            continue  # 跳过已有条目的处理
        matching_image_entry = next((item for item in image_target_paths if item[0] == lnk_file), None)
        app_entry = generate_app_entry(lnk_file, matching_image_entry[1])
        if app_entry:  # 仅在 app_entry 不为 None时添加
            apps_json["apps"].append(app_entry)
            print(f"新加入: {lnk_file}")

def _normalize_path(path):
    return os.path.normcase(os.path.abspath(path))


def _extract_shortcut_paths_from_entry(entry):
    """Extract .lnk/.url paths from app entry cmd/detached fields."""
    paths = []

    cmd = entry.get("cmd")
    if isinstance(cmd, str):
        cmd_val = cmd.strip().strip('"')
        if cmd_val.lower().endswith((".lnk", ".url")):
            paths.append(cmd_val)
    elif isinstance(cmd, (list, tuple)):
        for item in cmd:
            if isinstance(item, str):
                cmd_val = item.strip().strip('"')
                if cmd_val.lower().endswith((".lnk", ".url")):
                    paths.append(cmd_val)

    detached = entry.get("detached")
    if isinstance(detached, (list, tuple)):
        for item in detached:
            if isinstance(item, str):
                detached_val = item.strip().strip('"')
                if detached_val.lower().endswith((".lnk", ".url")):
                    paths.append(detached_val)

    return paths


def remove_entries_with_output_image(apps_json, base_names):
    """
    删除由 QSAA 生成封面的孤立条目：
    - 仅处理 image-path 含 output_image / _SGDB / _library_600x900 的条目
    - 仅当该条目的快捷方式路径不在当前工作目录中时删除
    功能由 auto_delete_orphaned_entries 开关控制（默认关闭）。
    """
    global auto_delete_orphaned_entries, folder_selected

    if not auto_delete_orphaned_entries:
        return

    work_dir = folder_selected or ""
    if not work_dir:
        return
    work_dir = _normalize_path(work_dir)

    current_shortcut_paths = set()
    for name in base_names:
        if not isinstance(name, str) or not name:
            continue
        current_shortcut_paths.add(_normalize_path(os.path.join(work_dir, name)))

    entries_to_delete = []
    for entry in apps_json.get('apps', []):
        image_path = entry.get("image-path", "")
        is_qsaa_cover = (
            "output_image" in image_path or
            "_SGDB" in image_path or
            "_library_600x900" in image_path
        )
        if not is_qsaa_cover:
            continue

        shortcut_paths = _extract_shortcut_paths_from_entry(entry)
        if not shortcut_paths:
            continue

        normalized_entry_paths = {_normalize_path(p) for p in shortcut_paths}
        if normalized_entry_paths.isdisjoint(current_shortcut_paths):
            entries_to_delete.append(entry)

    if not entries_to_delete:
        return

    apps_json['apps'] = [
        entry for entry in apps_json['apps']
        if entry not in entries_to_delete
    ]
    print(f"已自动删除 {len(entries_to_delete)} 个不在当前工作目录的条目")

def get_url_files(include_hidden=False):
    # 获取当前工作目录下的所有 .url 文件
    url_files = glob.glob("*.url")
    valid_url_files = []
    
    for url in url_files:
        try:
            # 检查是否在隐藏列表中（当不需要包含隐藏文件时）
            if not include_hidden and url in hidden_files:
                continue
                
            target_path = get_url_target_path(url)
            valid_url_files.append((url, target_path))
        except Exception as e:
            print(f"无法获取 {url} 的目标路径: {e}")
    
    print("找到的 .url 文件:")
    for idx, (url, target) in enumerate(valid_url_files):
        print(f"{idx+1}. {url}")
    return valid_url_files

def get_url_target_path(url_file):
    # 读取 .url 文件并获取目标路径
    with open(url_file, 'r', encoding='utf-8') as f:
        content = f.readlines()
    
    for line in content:
        if line.startswith("IconFile="):
            icon_file = line.split("=", 1)[1].strip()
            return icon_file  # 返回图标文件路径或可执行文件路径
    raise ValueError("未找到 IconFile 路径")

def restart_service():
    """
    发送POST请求以重启服务
    """
    try:
        response = requests.post('https://localhost:47990/api/restart', verify=False)
        if response.status_code == 200:
            print("sunshine服务重启")
        else:
            print(f"sunshine服务重启")
    except requests.exceptions.RequestException as e:
        print(f"sunshine服务已重启")

def find_unused_index(apps_json, image_target_paths):
    existing_indices = {int(entry["image-path"].split("output_image")[-1].split(".png")[0]) for entry in apps_json['apps'] if "output_image" in entry.get("image-path", "")}
    existing_indices = existing_indices.union({ima[1] for ima in image_target_paths})  # 使用 union 合并集合
    index = 0
    while index in existing_indices:
        index += 1
    return index

def initialize():
    global folder_selected, lnkandurl_files, output_folder, apps_json_path, target_paths, lnk_files, url_files
    # 确保 folder_selected 已设置，避免 os.chdir('') 导致 OSError
    load_config()

    if not folder_selected:
        # 回退到默认的 appfolder（与 load_config 中的逻辑一致）
        folder_selected = os.path.realpath(os.path.join(os.path.dirname(sys.executable), "appfolder")).replace("\\", "/")
        print(f"工作目录 '{folder_selected}'")
        os.makedirs(folder_selected)

    # 获取当前目录下所有有效的 .lnk 和 .url 文件
    try:
        os.chdir(folder_selected)  # 设置为用户选择的目录
    except Exception as e:
        print(f"无法切换到工作目录 '{folder_selected}'：{e}")
        return
    lnk_files = get_lnk_files()
    url_files = get_url_files()
    
    target_paths = [get_target_path_from_lnk(lnk) for lnk in lnk_files]
    target_paths += [url[1] for url in url_files]  # 添加 .url 文件的目标路径
    lnkandurl_files = lnk_files + [url[0] for url in url_files]

    # 确保目标文件夹存在
    output_folder = f"{APP_INSTALL_PATH}\\config\\covers"  # 更改为适当的文件夹

    # 加载现有的 apps.json 文件
    apps_json_path = f"{APP_INSTALL_PATH}\\config\\apps.json"  # 修改为你的 apps.json 文件路径
    print(f"该应用会使用《{output_folder}》文件夹来存放输出的图像\n修改以下文件《{apps_json_path}》来添加sunshine应用程序")

def generate_covers_for_entries(pending_entries, output_folder):
    """
    根据待添加条目的 exe / 图标，生成封面图片（内存模式）。
    不再落地 temp 文件，统一存入 entry["cover_bytes"]。
    """
    image_target_paths = []
    need_choose_cover_names = []

    print("--------------------生成封面--------------------")
    for entry in pending_entries:
        app_name = entry["app_name"]
        shortcut_file = entry["shortcut_file"]
        target_path = entry["target_path"]
        image_index = entry["image_index"]

        image_target_paths.append((shortcut_file, image_index))
        entry["image-path"] = f"output_image{image_index}.png"

        # 优先尝试 Steam 本地封面（内存）
        steam_cover_bytes = try_get_steam_cover_bytes_for_shortcut(app_name, shortcut_file)
        if steam_cover_bytes:
            entry["cover_bytes"] = steam_cover_bytes
            print(f"已为Steam游戏 {app_name} 准备内存封面")
            continue

        # 使用图标生成封面（内存）
        from io import BytesIO
        cover_buffer = BytesIO()
        create_image_with_icon(target_path, cover_buffer, image_index)
        cover_bytes = cover_buffer.getvalue()
        if cover_bytes:
            entry["cover_bytes"] = cover_bytes
        print(f"已生成封面: {app_name}")
        need_choose_cover_names.append(app_name)

    return image_target_paths, need_choose_cover_names

from confirm_add_window import ConfirmAddWindow


def runtomain():
    """
    扫描工作目录中的 .lnk / .url，通过 main window 显示确认窗口供用户选择要写入 Sunshine 的应用。
    在窗口显示期间后台异步生成封面，确认后再写入 apps.json 并重启 Sunshine。
    """
    global folder_selected, close_after_completion, pseudo_sorting_enabled, lnkandurl_files

    initialize()
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    apps_json = load_apps_json(apps_json_path)
    
    # 获取 main window 实例
    app = QtWidgets.QApplication.instance()
    if app is None:
        return
    
    main_window = app.activeWindow()
    if main_window is None or not hasattr(main_window, 'show_confirm_add_window'):
        # 如果没有找到 main window，使用旧的对话框方式
        return _runtomain_legacy(apps_json)

    # 收集已有条目的名称（不含扩展名）用于去重
    existing_names = set()
    for entry in apps_json.get('apps', []):
        cmd = entry.get('cmd')
        if isinstance(cmd, str):
            cmd_str = cmd.strip('"')
            if cmd_str:
                existing_names.add(os.path.splitext(os.path.basename(cmd_str))[0])
        elif isinstance(cmd, (list, tuple)) and cmd:
            for item in cmd:
                if isinstance(item, str) and item:
                    item_str = item.strip('"')
                    existing_names.add(os.path.splitext(os.path.basename(item_str))[0])
                    break

        detached_list = entry.get('detached')
        if isinstance(detached_list, (list, tuple)):
            for detached_item in detached_list:
                if isinstance(detached_item, str) and detached_item:
                    di = detached_item.strip('"')
                    existing_names.add(os.path.splitext(os.path.basename(di))[0])

    # 删除孤立条目
    remove_entries_with_output_image(apps_json, lnkandurl_files)

    # 构造待添加的快捷方式列表（不写入 apps.json，只做预览）
    pending_entries = []

    # 当前目录下的 .lnk
    for lnk in lnk_files:
        base_name = os.path.splitext(lnk)[0]
        if base_name in existing_names:
            continue
        try:
            target_path = get_target_path_from_lnk(lnk)
        except Exception as e:
            print(f"获取 {lnk} 目标路径失败: {e}")
            continue
        image_index = find_unused_index(apps_json, [])
        pending_entries.append({
            "app_name": base_name,
            "shortcut_file": lnk,
            "target_path": target_path,
            "image_index": image_index,
            "selected": True,
        })

    # .url 文件
    for url_file, target_path in url_files:
        base_name = os.path.splitext(url_file)[0]
        if base_name in existing_names:
            continue
        image_index = find_unused_index(apps_json, [])
        pending_entries.append({
            "app_name": base_name,
            "shortcut_file": url_file,
            "target_path": target_path,
            "image_index": image_index,
            "selected": True,
        })

    if not pending_entries:
        # 模拟一个错误，使用stderr输出以触发错误通知
        import sys
        error_message = "没有检测到需要添加的新应用。"
        print(f"Error: {error_message}", file=sys.stderr)
        return
    
    # 通过 main window 显示确认窗口
    main_window.show_confirm_add_window(
        pending_entries=pending_entries,
        apps_json=apps_json,
        apps_json_path=apps_json_path,
        output_folder=output_folder,
        pseudo_sorting_enabled=pseudo_sorting_enabled,
        close_after_completion=close_after_completion
    )


def _process_confirm_add_entries(selected_entries, apps_json, apps_json_path):
    """处理确认添加的条目，将其写入 apps.json。内存封面会在此阶段写入目标目录。"""
    global pseudo_sorting_enabled, close_after_completion

    covers_target_dir = os.path.join(APP_INSTALL_PATH, 'config', 'covers')
    os.makedirs(covers_target_dir, exist_ok=True)

    # 将选中的条目写入 apps.json
    for entry in selected_entries:
        shortcut_file = entry["shortcut_file"]
        image_index = entry["image_index"]
        app_entry = generate_app_entry(shortcut_file, image_index)
        if app_entry:
            custom_image_path = entry.get("image-path")
            if custom_image_path:
                app_entry["image-path"] = custom_image_path

            cover_bytes = entry.get("cover_bytes")
            if cover_bytes:
                cover_filename = app_entry.get("image-path")
                if cover_filename:
                    cover_full_path = os.path.join(covers_target_dir, cover_filename)
                    with open(cover_full_path, "wb") as f:
                        f.write(cover_bytes)

            apps_json["apps"].append(app_entry)
            print(f"新加入: {shortcut_file}")

    # 如果启用了伪排序，更新名称前缀
    if pseudo_sorting_enabled:
        for idx, entry in enumerate(apps_json["apps"]):
            entry["name"] = re.sub(r'^\d{2} ', '', entry["name"])
            entry["name"] = f"{idx:02d} {entry['name']}"
        print("已添加伪排序标志")

    save_apps_json(apps_json, apps_json_path)

    restart_service()

    if close_after_completion:
        os._exit(0)

def _runtomain_legacy(apps_json):
    """旧的对话框方式（当没有 main window 时使用）"""
    global folder_selected, close_after_completion, pseudo_sorting_enabled, lnkandurl_files
    print("使用旧的对话框方式")
    return


def get_steam_base_dir():
    """
    获取Steam的安装目录
    返回: str - Steam安装路径，如果未找到则返回None
    """
    try:
        # 打开Steam的注册表键
        hkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        
        # 获取SteamPath值
        steam_path = winreg.QueryValueEx(hkey, "SteamPath")[0]
        winreg.CloseKey(hkey)
        
        # 确保路径存在
        if os.path.exists(steam_path):
            return steam_path
            
    except WindowsError:
        return None
        
    return None
def generate_steamapp(app_id):
    # 检查图片文件是否存在
    steam_base_dir = get_steam_base_dir()
    image_path = f"{steam_base_dir}/appcache/librarycache/{app_id}_library_600x900.jpg"
    if not os.path.exists(image_path):
        image_path = f"{steam_base_dir}/appcache/librarycache/{app_id}_library_600x900_schinese.jpg"
        if not os.path.exists(image_path):
            return None  # 如果图片文件不存在，则返回None
    return image_path
# ========== 新增：为steam游戏快捷方式优先设置封面 ==========
def try_set_steam_cover_for_shortcut(app_name, target_path, output_dir, index):
    """
    检查 target_path 是否为 steam 游戏快捷方式，若是则尝试用本地 steam 封面，成功返回图片路径，否则返回 None。
    """
    import re
    steamid = None
    # 检查.lnk/.url文件内容是否包含 steam://rungameid/ 并提取id
    try:
        if target_path.lower().endswith('.url'):
            with open(target_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("URL=") and "steam://rungameid/" in line:
                        m = re.search(r'steam://rungameid/(\d+)', line)
                        if m:
                            steamid = m.group(1)
                            break
    except Exception as e:
        print(f"检查steam快捷方式失败: {e}")
        return None
    if not steamid:
        return None
    # 查找本地steam封面
    steam_base_dir = get_steam_base_dir()
    if not steam_base_dir:
        return None
    image_path = f"{steam_base_dir}/appcache/librarycache/{steamid}/library_600x900.jpg"
    if not os.path.exists(image_path):
        image_path = f"{steam_base_dir}/appcache/librarycache/{steamid}/library_600x900_schinese.jpg"
        if not os.path.exists(image_path):
            return None
    # 拷贝图片到 output_dir，文件名采用统一索引方式
    import shutil
    output_path = os.path.join(output_dir, f"output_image{index}.png")
    try:
        shutil.copy(image_path, output_path)
        print(f"已为Steam游戏 {app_name} 设置本地封面: {output_path}")
        return output_path
    except Exception as e:
        print(f"拷贝Steam封面失败: {e}")
        return None

def try_get_steam_cover_bytes_for_shortcut(app_name, target_path):
    """Return steam cover image bytes for shortcut if available, else None."""
    import re
    steamid = None
    try:
        if target_path.lower().endswith('.url') and os.path.exists(target_path):
            with open(target_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith("URL=") and "steam://rungameid/" in line:
                        m = re.search(r'steam://rungameid/(\d+)', line)
                        if m:
                            steamid = m.group(1)
                            break
    except Exception as e:
        print(f"检查steam快捷方式失败: {e}")
        return None

    if not steamid:
        return None

    steam_base_dir = get_steam_base_dir()
    if not steam_base_dir:
        return None

    image_path = f"{steam_base_dir}/appcache/librarycache/{steamid}/library_600x900.jpg"
    if not os.path.exists(image_path):
        image_path = f"{steam_base_dir}/appcache/librarycache/{steamid}/library_600x900_schinese.jpg"
        if not os.path.exists(image_path):
            return None

    try:
        with open(image_path, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"读取Steam封面失败: {e}")
        return None
