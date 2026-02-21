import os, sys, time, glob, json, re, shutil, threading, configparser, subprocess, urllib3
import tkinter as tk
from tkinter import filedialog, messagebox
import winreg, win32com.client, pythoncom, win32api, win32con, win32security, win32process, win32gui, psutil, vdf
from PIL import Image, ImageDraw, ImageFont, ImageTk
from colorthief import ColorThief
from io import BytesIO
import requests, webbrowser
from icoextract import IconExtractor, IconExtractorError
#& C:/Users/86150/AppData/Local/Programs/Python/Python38/python.exe -m PyInstaller QuickStreamAppAdd.py -i fav.ico --uac-admin --noconsole --additional-hooks-dir=. --noconfirm
#312 INFO: PyInstaller: 6.6.0, contrib hooks: 2024.4 Python: 3.8.5 Platform: Windows-10-10.0.22621-SP0
from tkinterdnd2 import *
class RedirectPrint:
    def __init__(self, label):
        self.label = label
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        self.label.config(text=self.buffer)
        self.label.update()

    def flush(self):
        pass

def quickaddmain():
    # 从命令行参数获取目标文件夹
    if len(sys.argv) < 3:
        print("错误：未提供目标文件夹路径")
        return
        
    target_folder = sys.argv[2]  # 获取第二个参数作为目标文件夹路径
    if not os.path.exists(target_folder):
        print(f"错误：目标文件夹不存在: {target_folder}")
        return

    # 创建新窗口
    add_window = TkinterDnD.Tk()
    add_window.title("快速添加")
    add_window.geometry("360x280")
    add_window.attributes("-topmost", True)  # 窗口始终显示于最前端
    # 创建标签用于显示拖放区域
    drop_label = tk.Label(add_window, text="拖放文件到这里\n或点击下方按钮选择文件", 
                         relief="solid", borderwidth=2, width=45, height=9)
    drop_label.pack(pady=20)

    # 重定向输出到drop_label
    redirector = RedirectPrint(drop_label)
    sys.stdout = redirector
    sys.stderr = redirector

    # 处理文件的函数
    def process_file(file_path):
        if not file_path:
            return

        # 检查文件扩展名
        if not file_path.lower().endswith('.exe'):
            print("请选择.exe文件")
            return

        shortcut_name = os.path.splitext(os.path.basename(file_path))[0] + ".lnk"
        shortcut_path = os.path.join(target_folder, shortcut_name)

        # 如果是lnk文件，直接复制
        if file_path.endswith('.lnk'):
            shutil.copy(file_path, shortcut_path)
        else:
            # 创建新的快捷方式
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(shortcut_path)
            shortcut.TargetPath = file_path
            shortcut.WorkingDirectory = os.path.dirname(file_path)
            shortcut.save()
        
        print(f"快捷方式已创建: {shortcut_path}")
        add_window.destroy()

    # 创建按钮用于选择文件
    def select_file():
        selected_file = filedialog.askopenfilename(
            title="选择一个exe可执行文件，生成快捷方式到目录文件夹",
            filetypes=[("Executable Files", "*.exe")]
        )
        if selected_file:
            process_file(selected_file)

    # 将选择文件和关闭按钮放在同一行
    file_btn_frame = tk.Frame(add_window)
    file_btn_frame.pack(pady=(5, 0))

    select_button = tk.Button(file_btn_frame, text="选择文件", width=25, bg='#aaaaaa', command=select_file)
    select_button.pack(side=tk.LEFT, padx=5)

    # 创建关闭按钮并放在同一行
    close_button = tk.Button(file_btn_frame, text="关闭", width=20, bg='#aaaaaa', command=add_window.destroy)
    close_button.pack(side=tk.LEFT)

    # 新增：添加运行中游戏按钮（点击后隐藏自身并显示运行中进程列表）
    def show_running_processes():
        # 隐藏触发按钮和 drop_label
        running_btn.pack_forget()
        drop_label.pack_forget()

        # 创建可滚动区域来显示进程列表（单独一行）
        proc_frame = tk.Frame(add_window, relief='flat')
        proc_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=(8, 0))

        canvas = tk.Canvas(proc_frame, height=220)
        scrollbar = tk.Scrollbar(proc_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = tk.Frame(canvas)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        # 鼠标滚轮支持（Windows）
        def _on_mousewheel(event):
            # event.delta 为 120 的倍数
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # 仅在鼠标进入 canvas/inner 时绑定全局滚轮，离开时解绑，避免影响其它控件
        def _bind_wheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_wheel(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)
        inner.bind("<Enter>", _bind_wheel)
        inner.bind("<Leave>", _unbind_wheel)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 枚举所有有前台窗口且不是隐藏的进程
        hwnd_pid_map = {}
        try:
            def enum_window_callback(hwnd, lParam):
                try:
                    if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        hwnd_pid_map[pid] = hwnd
                except Exception:
                    pass
                return True
            win32gui.EnumWindows(enum_window_callback, None)
        except Exception as e:
            tk.messagebox.showerror("错误", f"枚举窗口失败: {e}")
            return

        # 收集进程信息
        proc_list = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if (
                        proc.info['pid'] in hwnd_pid_map
                        and proc.info.get('exe')
                        and proc.info.get('name')
                        and proc.info['name'].lower() != "explorer.exe"
                        and proc.info['name'].lower() != "desktopgame.exe"
                        and proc.info['name'].lower() != "textinputhost.exe"
                        and proc.info['name'].lower() != "quickstreamappadd.exe"
                    ):
                        proc_list.append(proc)
                except Exception:
                    continue
        except Exception as e:
            tk.Label(inner, text=f"无法枚举进程: {e}", fg='red').pack(padx=8, pady=8)

        if not proc_list:
            tk.Label(inner, text="没有检测到可用进程", fg='white', bg='#333333').pack(padx=8, pady=8)
        else:
            for proc in proc_list:
                proc_name = proc.info.get('name', '未知')
                proc_exe = proc.info.get('exe', '')
                row = tk.Frame(inner)
                row.pack(fill=tk.X, padx=4, pady=4)
                # 文件夹选择小按钮
                def open_file_dialog(proc_exe=proc_exe):
                    start_dir = os.path.dirname(proc_exe) if proc_exe and os.path.exists(proc_exe) else ''
                    file_dialog = filedialog.askopenfilename(title="手动选择要添加的游戏文件",
                                                             filetypes=[("可执行文件", "*.exe;*.lnk")],
                                                             initialdir=start_dir)
                    if file_dialog:
                        process_file(file_dialog)
                folder_btn = tk.Button(row, text="📁", width=3, bg='#666666', fg='white', command=open_file_dialog)
                folder_btn.pack(side=tk.LEFT, padx=(0,0))

                # 进程按钮
                btn_text = f"{proc_name} ({proc_exe})"
                btn = tk.Button(row, text=btn_text, anchor='w', justify='left', bg='#444444', fg='white',
                                command=(lambda exe=proc_exe: process_file(exe)))
                btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
    running_btn = tk.Button(add_window, text="添加运行中游戏", width=47, bg='#aaaaaa', command=show_running_processes)
    running_btn.pack(pady=(5,0))

    # 实现拖放功能
    def on_drop(event):
        try:
            # 获取拖放的文件路径
            file_path = event.data.strip('{}')  # 移除可能的大括号
            if not file_path:
                return
                
            # 处理多个文件的情况（只取第一个）
            if isinstance(file_path, tuple):
                file_path = file_path[0]
                
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"文件不存在: {file_path}")
                return
                
            if file_path.lower().endswith('.exe') or file_path.lower().endswith('.lnk'):
                process_file(file_path)
            else:
                print("只能处理 .exe 或 .lnk 文件")
        except Exception as e:
            print(f"处理拖放文件时出错: {e}")

    # 设置拖放目标
    try:
        add_window.drop_target_register(DND_FILES)
        add_window.dnd_bind('<<Drop>>', on_drop)
    except Exception as e:
        print(f"初始化拖放功能时出错: {e}")
        # 如果拖放功能初始化失败，禁用拖放功能
        drop_label.config(text="拖放功能不可用\n请使用选择文件按钮")

    add_window.mainloop()

if len(sys.argv) > 2 and sys.argv[1] == "-quickadd":
    quickaddmain() 
    sys.exit(0)  # 退出程序
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) #禁用SSL警告
# 在文件开头添加全局变量
hidden_files = []
steam_excluded_games = []  # 新增：steam 屏蔽游戏 appid 列表
config = configparser.ConfigParser()
if getattr(sys, 'frozen', False):
    # 如果是打包后的应用程序
    config_file_path = os.path.join(os.path.dirname(sys.executable), 'config.ini')  # 存储在可执行文件同级目录
else:
    # 如果是开发环境
    config_file_path = 'config.ini'
onestart = True
skipped_entries = []
folder_selected = ''
close_after_completion = True  # 默认开启
pseudo_sorting_enabled = False  # 新增伪排序适应选项，默认关闭
auto_delete_orphaned_entries = False  # 自动删除孤立条目（不再询问），默认关闭

# 重定向print函数，使输出显示在tkinter的文本框中
class RedirectPrint:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.yview(tk.END)  # 滚动到文本框底部
    def flush(self):
        pass
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
                    messagebox.showerror("读取错误",msg)
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

def load_config():
    """加载配置文件"""
    global close_after_completion, pseudo_sorting_enabled, hidden_files ,folder, steam_excluded_games, auto_delete_orphaned_entries
    config.read(config_file_path)
    folder = config.get('Settings', 'folder_selected', fallback='')
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
        if not os.path.exists(folder):
            os.makedirs(folder)  # 创建目录
        #folder = os.path.realpath(os.path.join(os.path.expanduser("~"), "Desktop")).replace("\\", "/") + "\n\n选择"是"使用程序目录，选择"否"使用桌面目录（之后可随时修改）"
        save_config()
    return folder

def save_config():
    """保存选择的目录到配置文件"""
    try:
        global hidden_files, folder, close_after_completion, pseudo_sorting_enabled, steam_excluded_games, auto_delete_orphaned_entries  # 添加全局变量声明
        config['Settings'] = {
            'folder_selected': folder,
            'close_after_completion': close_after_completion,
            'pseudo_sorting_enabled': pseudo_sorting_enabled,
            # 将 hidden_files 列表转换为逗号分隔的字符串
            'hidden_files': ','.join(hidden_files) if hidden_files else '',
            # 新增 steam_excluded_games
            'steam_excluded_games': ','.join(steam_excluded_games) if steam_excluded_games else '',
            # 新增 auto_delete_orphaned_entries
            'auto_delete_orphaned_entries': auto_delete_orphaned_entries
        }
        with open(config_file_path, 'w') as configfile:
            config.write(configfile)
    except Exception as e:
        print(f"保存配置文件时出错: {e}")

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
# 创建Tkinter窗口
def create_gui():
    global folder_selected, close_after_completion, hidden_files, root
    # 确保 folder_selected 是有效的目录
    root = tk.Tk()
    root.title("QuickStreamAppAdd")
    root.geometry("700x400")
    #width, height = 700, 400
    #x = (root.winfo_screenwidth() // 2) - (width // 2)
    #y = (root.winfo_screenheight() // 2) - (height // 2)
    #root.geometry(f"{width}x{height}+{x}+{y}")
    folder_selected = load_config()  # 加载配置文件中的目录
    if not os.path.isdir(folder_selected):
        messagebox.showerror("错误", f"目录不存在，程序退出")
        root.destroy()
        return

    # 创建一个框架用于放置文件夹选择文本框和按钮
    folder_frame = tk.Frame(root)
    folder_frame.pack(padx=10, pady=(10, 0), fill=tk.X)  # 上边距为10，下边距为0，填充X方向

    # 创建文本框显示选择的文件夹
    folder_entry = tk.Entry(folder_frame, width=50)
    folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)  # 左对齐，填充X方向并扩展
    folder_entry.insert(0, folder_selected)  # 显示加载的文件夹路径
    folder_entry.config(state=tk.DISABLED)

    def select_directory():
        global folder_selected, onestart , folder
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            print(f"选择的目录: {folder_selected}")
            text_box.delete('1.0', tk.END)
            folder_entry.config(state=tk.NORMAL)  # 允许编辑
            folder_entry.delete(0, tk.END)  # 清空文本框
            folder_entry.insert(0, folder_selected)  # 显示选择的文件夹路径
            folder = folder_selected
            save_config()  # 保存选择的目录
            onestart = True
            main()
            folder_entry.config(state=tk.DISABLED)  # 选择后再设置为不可编辑

    # 文件夹选择按钮
    folder_button = tk.Button(folder_frame, text="指定文件夹", command=select_directory)
    folder_button.pack(padx=(10, 0), side=tk.LEFT)  # 上边距为0，左对齐

    def open_folder():
        if os.path.exists(folder_selected):
            os.startfile(folder_selected)
        else:
            print(f"文件夹不存在: {folder_selected}")

    # 文件夹打开按钮
    folder_button = tk.Button(folder_frame, text="📂", command=open_folder)
    folder_button.pack(padx=(0, 0), side=tk.LEFT)  # 上边距为0，左对齐

    def runonestart():
        text_box.delete('1.0', tk.END)
        # 运行main()
        global onestart
        onestart = True
        main()
        # 将主窗口置于前台
        root.lift()
        root.attributes('-topmost', True)
        root.after(500, lambda: root.attributes('-topmost', False))

    # 刷新按钮
    folder_button = tk.Button(folder_frame, text="↻", command=runonestart)
    folder_button.pack(padx=(0, 0), side=tk.LEFT)  # 上边距为0，左对齐

    def open_sun_apps():
        import webbrowser
        webbrowser.open('https://localhost:47990/apps')

    # 打开sunapp管理按钮
    apps_button = tk.Button(folder_frame, text="应用管理",bg='#FFA500',command=open_sun_apps)
    apps_button.pack(padx=(0, 0), side=tk.LEFT)  # 上边距为0，左对齐

    # 创建文本框用来显示程序输出
    text_box = tk.Text(root, wrap=tk.WORD, height=15, bg='#333333', fg='white')
    text_box.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

    # 完成后关闭程序的选项
    def toggle_close_option():
        global close_after_completion
        close_after_completion = close_var.get()
        save_config()  # 保存选项状态
    def pseudo_sorting_option():
        global pseudo_sorting_enabled
        pseudo_sorting_enabled = pseudo_sorting_var.get()  # 获取伪排序选项状态
        apps_json_path = f"{APP_INSTALL_PATH}\\config\\apps.json"  # 修改为你的 apps.json 文件路径
        apps_json = load_apps_json(apps_json_path)  # 加载现有的 apps.json 文件
        if not pseudo_sorting_enabled:
            for idx, entry in enumerate(apps_json["apps"]):
                entry["name"] = re.sub(r'^\d{2} ', '', entry["name"])
            save_apps_json(apps_json, apps_json_path)
            print("已清除伪排序标志")
        else:
            for idx, entry in enumerate(apps_json["apps"]):
                entry["name"] = re.sub(r'^\d{2} ', '', entry["name"])
                entry["name"] = f"{idx:02d} {entry['name']}"  # 在名称前加上排序数字，格式化为两位数
            save_apps_json(apps_json, apps_json_path)
            print("已添加伪排序标志")
        save_config()  # 保存选项状态

    # 创建一个框架来包含复选框
    checkbox_frame = tk.Frame(root)
    checkbox_frame.pack(side=tk.LEFT, padx=(10,0), pady=(0, 0))

    close_var = tk.BooleanVar(value=close_after_completion) # 设置复选框的初始值
    close_checkbox = tk.Checkbutton(checkbox_frame, text="完成后关闭程序", variable=close_var, command=toggle_close_option)
    close_checkbox.pack(side=tk.TOP, pady=(0, 0)) # 上边距为0

    # 在创建 GUI 时，添加伪排序选项
    pseudo_sorting_var = tk.BooleanVar(value=pseudo_sorting_enabled) # 设置复选框的初始值
    pseudo_sorting_checkbox = tk.Checkbutton(checkbox_frame, text="启用伪排序      ", variable=pseudo_sorting_var, command=pseudo_sorting_option)
    pseudo_sorting_checkbox.pack(side=tk.TOP, pady=(0, 0)) # 上边距为0
    
    def start_button_on():
        text_box.delete('1.0', tk.END)
        threading.Thread(target=main).start()
    # 开始程序按钮
    start_button = tk.Button(root, text="--点此开始程序--", command=start_button_on, width=25, height=2, bg='#333333', fg='white')  # 设置背景色为黑色，文字颜色为白色
    start_button.pack(side=tk.RIGHT, padx=(0,10), pady=3)  # 右侧对齐
    def about_more():
        # 自定义窗口以支持可点击的超链接
        url = "https://github.com/gmaox/QuickStreamAppAdd"
        win = tk.Toplevel()
        win.title("关于 QuickStreamAppAdd")
        win.geometry("520x240")
        try:
            if 'root' in globals() and root:
                win.transient(root)
        except:
            pass
        win.resizable(False, False)

        txt = (
            "QuickStreamAppAdd (QSAA) 是一个辅助工具，旨在简化将应用程序和游戏添加到 Sunshine 的过程。\n"
            "主要功能包括：\n"
            "1. 快速添加本地可执行文件的快捷方式。\n"
            "2. 检测并添加已安装的 Steam 游戏。\n"
            "3. 支持拖放文件添加\n"
            "4. 运行中游戏的快速添加\n\n"
            "更多功能开发中，项目开源地址："
        )
        lbl = tk.Label(win, text=txt, justify="left", anchor="nw", wraplength=500)
        lbl.pack(padx=12, pady=(12, 6), fill=tk.BOTH)

        # 可点击的链接标签
        link = tk.Label(win, text=url, fg="blue", cursor="hand2", wraplength=500)
        try:
            link.config(font=(None, 9, "underline"))
        except Exception:
            pass
        link.pack(padx=12, pady=(0, 12), anchor="w")

        def open_link(event=None):
            try:
                webbrowser.open(url)
            except Exception:
                messagebox.showinfo("提示", f"无法打开链接，请手动访问：\n{url}")

        # 鼠标效果
        def on_enter(e):
            link.config(fg="#0000ee")
        def on_leave(e):
            link.config(fg="blue")

        link.bind("<Button-1>", open_link)
        link.bind("<Enter>", on_enter)
        link.bind("<Leave>", on_leave)
        # 将窗口置顶并聚焦
        win.attributes("-topmost", True)
        win.after(200, lambda: win.attributes("-topmost", False))
        win.focus_force()
    delete_button = tk.Button(root, text="关于＆\n更多功能", command=about_more, width=10, height=2, bg='#aaaaaa', fg='white')  # 设置背景色为黑色，文字颜色为白色
    delete_button.pack(side=tk.RIGHT, padx=0, pady=(3, 3))  # 上边距为0，下边距为10

    def add_steamgame_window():
        """打开新窗口，自动读取本地Steam已安装游戏，选择后生成.url快捷方式"""
        steam_base_dir = get_steam_base_dir()
        if not steam_base_dir:
            tk.messagebox.showerror("错误", "未检测到Steam安装目录！")
            return
        # 1. 读取所有Steam库路径
        libraryfolders_path = os.path.join(steam_base_dir, 'steamapps', 'libraryfolders.vdf')
        try:
            with open(libraryfolders_path, encoding='utf-8') as f:
                vdf_data = vdf.load(f)
        except Exception as e:
            tk.messagebox.showerror("错误", f"无法读取libraryfolders.vdf: {e}")
            return
        # 兼容新版/旧版VDF结构
        if 'libraryfolders' in vdf_data:
            folders = vdf_data['libraryfolders']
        else:
            folders = vdf_data['LibraryFolders']
        library_paths = []
        for k, v in folders.items():
            if isinstance(v, dict) and 'path' in v:
                library_paths.append(v['path'])
            elif isinstance(v, str) and v.isdigit() == False:
                library_paths.append(v)
        if steam_base_dir not in library_paths:
            library_paths.append(steam_base_dir)
        # 2. 遍历所有库，收集所有appmanifest_*.acf
        games = []
        for lib in library_paths:
            steamapps = os.path.join(lib, 'steamapps')
            if not os.path.exists(steamapps):
                continue
            for file in os.listdir(steamapps):
                if file.startswith('appmanifest_') and file.endswith('.acf'):
                    try:
                        with open(os.path.join(steamapps, file), encoding='utf-8') as f:
                            acf = vdf.load(f)
                        appid = acf['AppState']['appid']
                        name = acf['AppState']['name']
                        games.append({'appid': appid, 'name': name})
                    except Exception as e:
                        continue
        # 3. 创建窗口和Listbox
        steam_cover_window = tk.Toplevel()
        steam_cover_window.title("添加 Steam 游戏")
        steam_cover_window.geometry("360x400")
        label = tk.Label(steam_cover_window, text="选择一个本地Steam游戏，快速添加到sunshine应用中")
        label.pack(pady=10)
        
        # 过滤被屏蔽的游戏
        visible_games = [g for g in games if g['appid'] not in steam_excluded_games]
        listbox = tk.Listbox(steam_cover_window, height=12)
        listbox.pack(pady=0, padx=15, fill=tk.BOTH, expand=True)
        for g in visible_games:
            listbox.insert(tk.END, g['name'])
        # 选择并生成.url快捷方式
        def on_select(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            game = visible_games[sel[0]]
            appid = game['appid']
            # 替换不能作为文件名的特殊符号为''
            safe_name = re.sub(r'[\\/:*?"<>|]', '', game['name'])
            shortcut_name = f"{safe_name}.url"
            shortcut_path = os.path.join(folder_selected, shortcut_name)
            icon_path = os.path.join(steam_base_dir, 'steam.exe')
            url_content = f"[InternetShortcut]\nURL=steam://rungameid/{appid}\nIconFile={icon_path}\nIconIndex=0\n"
            with open(shortcut_path, 'w', encoding='utf-8') as f:
                f.write(url_content)
            steam_cover_window.destroy()
            runonestart()
        listbox.bind('<Double-Button-1>', on_select)

        # 新增：屏蔽部分steam游戏按钮
        def edit_steam_excluded_games():
            global steam_excluded_games
            exclude_win = tk.Toplevel(steam_cover_window)
            exclude_win.title("屏蔽/取消屏蔽 Steam 游戏")
            exclude_win.geometry("360x800")
            tk.Label(exclude_win, text="多选屏蔽/取消屏蔽，保存后立即生效").pack(pady=10)
            lb = tk.Listbox(exclude_win, selectmode=tk.MULTIPLE, height=15)
            lb.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
            # 全部游戏列表，带屏蔽标记
            for g in games:
                suffix = " --已屏蔽" if g['appid'] in steam_excluded_games else ""
                lb.insert(tk.END, g['name'] + suffix)
            # 预选已屏蔽项
            for idx, g in enumerate(games):
                if g['appid'] in steam_excluded_games:
                    lb.selection_set(idx)
            def save_exclude():
                global steam_excluded_games
                selected = lb.curselection()
                new_excluded = [games[idx]['appid'] for idx in selected]
                steam_excluded_games = new_excluded
                save_config()
                exclude_win.destroy()
                # 刷新主列表
                steam_cover_window.destroy()
                add_steamgame_window()
            btn_frame = tk.Frame(exclude_win)
            btn_frame.pack(pady=10)
            def select_all():
                lb.select_set(0, tk.END)
            select_all_btn = tk.Button(btn_frame, text="全选", command=select_all, width=10, bg='#aaaaaa')
            select_all_btn.pack(side=tk.LEFT, padx=5)
            btn = tk.Button(btn_frame, text="保存", command=save_exclude, width=15, bg='#aaaaaa')
            btn.pack(side=tk.LEFT, padx=5)        # 新增：导入全部游戏按钮
        def import_all_games():
            # 读取已存在的快捷方式名（不含扩展名）
            existing_files = set(os.path.splitext(f)[0] for f in os.listdir(folder_selected) if f.endswith('.url'))
            count = 0
            for g in visible_games:
                safe_name = re.sub(r'[\\/:*?"<>|]', '', g['name'])
                if safe_name in existing_files:
                    continue  # 已存在
                shortcut_name = f"{safe_name}.url"
                shortcut_path = os.path.join(folder_selected, shortcut_name)
                icon_path = os.path.join(steam_base_dir, 'steam.exe')
                url_content = f"[InternetShortcut]\nURL=steam://rungameid/{g['appid']}\nIconFile={icon_path}\nIconIndex=0\n"
                with open(shortcut_path, 'w', encoding='utf-8') as f:
                    f.write(url_content)
                count += 1
            tk.messagebox.showinfo("批量导入", f"已导入 {count} 个新游戏快捷方式！")
            steam_cover_window.destroy()
            runonestart()
        fold_frame = tk.Frame(steam_cover_window)
        fold_frame.pack(padx=10, pady=(10, 0))
        c_button = tk.Button(fold_frame, text="--添加--", width=25, bg='#aaaaaa', command=on_select)
        c_button.pack(side=tk.LEFT, padx=5)
        close_button = tk.Button(fold_frame, text="关闭窗口", width=20, bg='#aaaaaa', command=steam_cover_window.destroy)
        close_button.pack(side=tk.LEFT)
        btn_row = tk.Frame(steam_cover_window)
        btn_row.pack(padx=10, pady=(10, 0))
        exclude_btn = tk.Button(btn_row, text="屏蔽部分steam游戏", command=edit_steam_excluded_games, width=25, bg='#aaaaaa')
        exclude_btn.pack(side=tk.LEFT, padx=5)
        import_btn = tk.Button(btn_row, text="导入全部游戏", command=import_all_games, width=20, bg='#aaaaaa')
        import_btn.pack(side=tk.LEFT)

    steam_cover_button = tk.Button(root, text="从本地steam库\n加入游戏", command=add_steamgame_window, width=13, height=2, bg='#aaaaaa', fg='white')  # 设置背景色为黑色，文字颜色为白色
    steam_cover_button.pack(side=tk.RIGHT, padx=0, pady=(3, 3))  # 上边距为0，下边距为10

    # 添加两个新按钮
    def edit_excluded_shortcuts_window():
        """打开编辑排除快捷方式的新窗口"""
        excluded_window = tk.Toplevel()
        excluded_window.title("编辑排除的快捷方式项目")
        excluded_window.geometry("360x250")
        print("--------------------------分隔线---------------------------")
        # 在新窗口中添加内容，例如标签和按钮
        label = tk.Label(excluded_window, text="选择一个列表中的项目，选中隐藏后的项目将不会添加\n（可多选，可以把办公软件和系统软件隐藏）")
        label.pack(pady=10)

        # 创建支持多选的Listbox
        listbox = tk.Listbox(excluded_window, height=4, selectmode=tk.MULTIPLE)
        listbox.pack(pady=0, padx=15, fill=tk.BOTH, expand=True)

        # 获取包含已隐藏文件的完整列表
        os.chdir(folder_selected)
        current_lnk = get_lnk_files(include_hidden=True)  # 包含已隐藏
        current_url = get_url_files(include_hidden=True)  # 包含已隐藏（正确调用方式）
        current_files = current_lnk + [url[0] for url in current_url]
        print("--------------------------分隔线---------------------------")

        # 将内容添加到Listbox并添加已隐藏标记
        for file in current_files:
            # 统一格式化显示名称（使用固定宽度字体对齐）
            max_name_len = 34
            status_suffix = " --已隐藏" if file in hidden_files else ""
            
            # 移除路径只显示文件名
            display_name = os.path.basename(file)
            
            if len(display_name) > max_name_len:
                trimmed = display_name[:max_name_len-3] + '...'
            else:
                trimmed = display_name.ljust(max_name_len)
            
            listbox.insert(tk.END, f"{trimmed}{status_suffix}")

        # 创建一个框架用于放置按钮
        fold_frame = tk.Frame(excluded_window)
        fold_frame.pack(padx=10, pady=(10, 0))

        # 创建两个按钮并放置在同一行
        def toggle_hidden():
            selected_indices = listbox.curselection()
            
            # 获取包含隐藏文件的完整列表
            current_lnk = get_lnk_files(include_hidden=True)
            current_url = [url[0] for url in get_url_files(include_hidden=True)]
            current_files = current_lnk + current_url
            
            # 更新选中项状态
            for idx in selected_indices:
                original_item = current_files[idx]  # 从最新文件列表获取
                if original_item in hidden_files:
                    hidden_files.remove(original_item)
                    print(f"已显示: {original_item}")
                else:
                    hidden_files.append(original_item)
                    print(f"已隐藏: {original_item}")
            save_config()
            
            # 完全刷新Listbox
            listbox.delete(0, tk.END)
            for file in current_files:
                # 统一格式化显示名称（使用固定宽度字体对齐）
                max_name_len = 34
                status_suffix = " --已隐藏" if file in hidden_files else ""
                
                # 移除路径只显示文件名
                display_name = os.path.basename(file)
                
                if len(display_name) > max_name_len:
                    trimmed = display_name[:max_name_len-3] + '...'
                else:
                    trimmed = display_name.ljust(max_name_len)
                
                listbox.insert(tk.END, f"{trimmed}{status_suffix}")
            # 清空文本框并运行main()
            text_box.delete('1.0', tk.END)
            global onestart
            onestart = True
            main()

        c_button = tk.Button(fold_frame, text="--显示/隐藏--", width=25, bg='#aaaaaa', command=toggle_hidden)
        c_button.pack(side=tk.LEFT, padx=5)  # 使用 side=tk.LEFT 使按钮在同一行

        close_button = tk.Button(fold_frame, text="关闭窗口", width=20, bg='#aaaaaa', command=excluded_window.destroy)
        close_button.pack(side=tk.LEFT)  # 使用 side=tk.LEFT 使按钮在同一行


    button1 = tk.Button(root, text="编辑排除\n快捷方式项目", width=11, height=2, bg='#aaaaaa', fg='white', command=edit_excluded_shortcuts_window)
    button1.pack(side=tk.RIGHT, padx=0, pady=(3, 3))

    def edit_excluded_shortcuts(): 
        global folder
        if not folder:
            print("没有可用的目标文件夹")
            return

        try:
            # 获取当前用户的令牌
            token = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32con.TOKEN_QUERY | win32con.TOKEN_DUPLICATE | win32con.TOKEN_ASSIGN_PRIMARY
            )
            
            # 创建新的令牌
            new_token = win32security.DuplicateTokenEx(
                token,
                win32security.SecurityImpersonation,
                win32con.TOKEN_ALL_ACCESS,
                win32security.TokenPrimary
            )
            
            # 创建中等完整性级别的SID
            medium_sid = win32security.CreateWellKnownSid(win32security.WinMediumLabelSid, None)
            
            # 设置令牌的权限级别
            win32security.SetTokenInformation(
                new_token,
                win32security.TokenIntegrityLevel,
                (medium_sid, 0)  # 使用正确的SID格式
            )
            
            # 创建进程
            startup_info = win32process.STARTUPINFO()
            startup_info.dwFlags = win32con.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = win32con.SW_NORMAL
            
            process_info = win32process.CreateProcessAsUser(
                new_token,
                sys.executable,  # application_name: 只写可执行文件路径
                f'"{sys.executable}" -quickadd "{folder}"',  # command_line: 包含命令行参数
                None,  # 进程安全属性
                None,  # 线程安全属性
                False,  # 不继承句柄
                win32con.NORMAL_PRIORITY_CLASS,  # 创建标志
                None,  # 新环境
                None,  # 当前目录
                startup_info
            )
            
            # 获取进程ID
            pid = process_info[2]
            
            # 关闭不需要的句柄
            win32api.CloseHandle(process_info[1])  # 线程句柄
            win32api.CloseHandle(new_token)
            win32api.CloseHandle(token)
            
            # 等待进程结束
            while True:
                try:
                    # 尝试打开进程
                    process_handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION, False, pid)
                    if process_handle:
                        # 获取退出码
                        exit_code = win32process.GetExitCodeProcess(process_handle)
                        if exit_code != win32con.STILL_ACTIVE:
                            # 进程已结束
                            win32api.CloseHandle(process_handle)
                            break
                        win32api.CloseHandle(process_handle)
                except:
                    # 进程已结束
                    break
                time.sleep(0.1)  # 避免CPU占用过高
            
            # 关闭进程句柄
            win32api.CloseHandle(process_info[0])
            runonestart()
            
        except Exception as e:
            print(f"运行quickadd时出错: {e}")

    button2 = tk.Button(root, text="快速\n添加", width=6, height=2, bg='#aaaaaa', fg='white') 
    button2.pack(side=tk.RIGHT, padx=0, pady=(3, 3))
    button2.config(command=edit_excluded_shortcuts)
    def sgdboop_select():
        # 1. 读取 apps.json
        apps_json_path = f"{APP_INSTALL_PATH}\\config\\apps.json"
        apps_json = load_apps_json(apps_json_path)
        app_names = [entry["name"] for entry in apps_json.get("apps", [])]
    
        # 2. 弹出选择窗口
        select_win = tk.Toplevel()
        select_win.title("选择游戏以在SGDB搜索")
        select_win.geometry("360x250")
    
        label = tk.Label(select_win, text="请选择一个游戏名称：")
        label.pack(pady=10)
    
        listbox = tk.Listbox(select_win, height=4)
        for name in app_names:
            listbox.insert(tk.END, name)
        listbox.pack(pady=0, padx=15, fill=tk.BOTH, expand=True)

        def on_select(event=None):
            sel = listbox.curselection()
            if not sel:
                return
            game_name = listbox.get(sel[0])
            # 找到对应app_entry
            app_entry = None
            for entry in apps_json.get("apps", []):
                if entry["name"] == game_name:
                    app_entry = entry
                    break
            if app_entry:
                # 统一调用choose_cover_with_sgdb
                covers_dir = os.path.join(APP_INSTALL_PATH, "config", "covers")
                os.makedirs(covers_dir, exist_ok=True)
                appid = app_entry.get("appid") or app_entry.get("id") or app_entry.get("name")
                filename = os.path.join(covers_dir, f"{appid}_SGDB.jpg")
                exe_path = None
                # 尝试获取可执行路径
                if app_entry.get("cmd"):
                    exe_path = app_entry["cmd"].strip('"')
                elif app_entry.get("detached") and len(app_entry["detached"]) > 0:
                    exe_path = app_entry["detached"][0].strip('"')
                select_win.destroy()
                cover_path, used_icon, sgdb_name = choose_cover_with_sgdb(game_name, filename, exe_path)
                # 如果选择了封面，更新 apps.json
                if os.path.exists(filename):
                    app_entry["image-path"] = os.path.basename(filename)
                    # 如果返回了SGDB游戏名称，则更新名称
                    if sgdb_name:
                        app_entry["name"] = sgdb_name
                    save_apps_json(apps_json, apps_json_path)
        listbox.bind('<Double-Button-1>', on_select)
        fold_frame = tk.Frame(select_win)
        fold_frame.pack(padx=10, pady=(10, 0))
        btn = tk.Button(fold_frame, text="选择并更换SGDB封面", width=25, bg='#aaaaaa', command=on_select)
        btn.pack(side=tk.LEFT, padx=5)
    
        close_btn = tk.Button(fold_frame, text="关闭", width=20, bg='#aaaaaa', command=select_win.destroy)
        close_btn.pack(side=tk.LEFT)
    button2 = tk.Button(root, text="SGDB\n封面查找", width=6, height=2, bg='#aaaaaa', fg='white') 
    button2.pack(side=tk.RIGHT, padx=0, pady=(3, 3))
    button2.config(command=sgdboop_select)
    #button2.config(command=lambda: webbrowser.open("https://www.steamgriddb.com/"))
    # 重定向 stdout 和 stderr 到文本框
    redirector = RedirectPrint(text_box)
    sys.stdout = redirector  # 重定向标准输出
    sys.stderr = redirector  # 重定向错误输出
    threading.Thread(target=main).start()
    root.mainloop()

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
            dominant_colors = get_dominant_colors(icon_img)
            color1, color2 = dominant_colors[0], dominant_colors[1]

            img = Image.new('RGBA', (600, 800), color=(255, 255, 255, 0))
            draw = ImageDraw.Draw(img)

            for y in range(800):
                for x in range(600):
                    ratio_x = x / 600
                    ratio_y = y / 800
                    ratio = (ratio_x + ratio_y) / 2
                    r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
                    g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
                    b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
                    draw.point((x, y), fill=(r, g, b, 255))

            icon_x = (600 - icon_width) // 2
            icon_y = (800 - icon_height) // 2
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

def remove_entries_with_output_image(apps_json, base_names):
    # 删除 apps.json 中包含 "output_image" 或"_SGDB"或"_library_600x900"的条目，且 cmd 和 detached 字段不在 base_names 中
    
    # 先找出需要删除的条目
    entries_to_delete = []
    for entry in apps_json['apps']:
        if (("output_image" in entry.get("image-path", "") or
             "_SGDB" in entry.get("image-path", "") or
             "_library_600x900" in entry.get("image-path", ""))
            and not (
                (entry.get("cmd") and os.path.basename(entry["cmd"].strip('"')) in base_names) or 
                (entry.get("detached") and any(os.path.basename(detached_item.strip('"')) in base_names for detached_item in entry["detached"]))
            )):
            entries_to_delete.append(entry)
    
    # 如果没有需要删除的条目，直接返回
    if not entries_to_delete:
        return
    
    # 如果设置了自动删除，直接删除
    global auto_delete_orphaned_entries
    if auto_delete_orphaned_entries:
        apps_json['apps'] = [
            entry for entry in apps_json['apps'] 
            if entry not in entries_to_delete
        ]
        print(f"已自动删除 {len(entries_to_delete)} 个不符合条件的条目")
        return
    
    # 询问用户是否删除
    deleted_entry_names = [entry.get("name", "未知") for entry in entries_to_delete]
    entry_list = "\n".join([f"  - {name}" for name in deleted_entry_names[:10]])  # 最多显示10个
    if len(deleted_entry_names) > 10:
        entry_list += f"\n  ... 还有 {len(deleted_entry_names) - 10} 个条目"
    
    message = f"检测到 {len(entries_to_delete)} 个孤立的条目需要删除（对应的快捷方式已不存在）：\n\n{entry_list}\n\n是否删除这些条目？"
    
    # 创建自定义对话框
    dialog_result = {"value": None}
    
    # 获取主窗口或创建临时窗口
    parent_window = None
    try:
        # 尝试从全局命名空间获取 root
        if 'root' in globals() and globals()['root']:
            parent_window = globals()['root']
    except:
        pass
    
    # 如果无法获取主窗口，创建一个临时根窗口
    temp_root = None
    if not parent_window:
        temp_root = tk.Tk()
        temp_root.withdraw()
        parent_window = temp_root
    
    dialog = tk.Toplevel(parent_window)
    dialog.title("确认删除")
    dialog.geometry("450x350")
    dialog.attributes("-topmost", True)
    if parent_window and parent_window != temp_root:
        try:
            dialog.transient(parent_window)
        except:
            pass
    
    # 居中显示
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (450 // 2)
    y = (dialog.winfo_screenheight() // 2) - (350 // 2)
    dialog.geometry(f"450x350+{x}+{y}")
    
    tk.Label(dialog, text=message, wraplength=420, justify=tk.LEFT, padx=10, pady=10).pack()
    
    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=20)
    
    def delete_click():
        dialog_result["value"] = "delete"
        dialog.destroy()
        if temp_root:
            temp_root.destroy()
    
    def cancel_click():
        dialog_result["value"] = "cancel"
        dialog.destroy()
        if temp_root:
            temp_root.destroy()
    
    def ignore_click():
        dialog_result["value"] = "ignore"
        dialog.destroy()
        if temp_root:
            temp_root.destroy()
    
    tk.Button(button_frame, text="删除", command=delete_click, width=12, bg='#aaaaaa').pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="取消", command=cancel_click, width=12, bg='#aaaaaa').pack(side=tk.LEFT, padx=5)
    tk.Button(button_frame, text="忽略并记住", command=ignore_click, width=12, bg='#aaaaaa').pack(side=tk.LEFT, padx=5)
    
    dialog.protocol("WM_DELETE_WINDOW", cancel_click)
    dialog.focus_force()
    dialog.grab_set()  # 设置为模态对话框
    dialog.wait_window()
    if temp_root:
        temp_root.update()
    
    # 处理用户选择
    if dialog_result["value"] == "delete":
        apps_json['apps'] = [
            entry for entry in apps_json['apps'] 
            if entry not in entries_to_delete
        ]
        print(f"已删除 {len(entries_to_delete)} 个不符合条件的条目")
    elif dialog_result["value"] == "ignore":
        # 设置自动删除标志，以后不再询问
        auto_delete_orphaned_entries = True
        save_config()
        print("已设置自动删除孤立条目，以后将不再询问")
    else:
        # 取消删除
        print("已取消删除操作")


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

# ========== SGDB封面选择窗口全局函数 ==========
def choose_cover_with_sgdb(app_name, output_path, exe_path=None):
    import tkinter as tk
    from tkinter import messagebox
    import requests
    from PIL import Image, ImageTk
    from io import BytesIO
    import threading
    cover_win = tk.Toplevel()
    cover_win.title(f"SGDB封面选择 - {app_name} - 正在搜索游戏，请耐心等待")
    width, height = 800, 500
    if hasattr(sys.modules[__name__], 'root'):
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        cover_win.geometry(f"{width}x{height}+{x}+{y}")
    else:
        cover_win.geometry(f"{width}x{height}")
    cover_win.update()
    api_key = "1b378d4482f7088146d2f7e320139b74"
    class SteamGridDBApi:
        def __init__(self, api_key):
            self.api_key = api_key
            self.base_url = "https://www.steamgriddb.com/api/v2"
            self.headers = {"Authorization": f"Bearer {api_key}"}
        def search_game(self, name):
            url = f"{self.base_url}/search/autocomplete/{name}"
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            return r.json()["data"]
        def get_grids(self, game_id):
            url = f"{self.base_url}/grids/game/{game_id}?types=static&dimensions=600x900"
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            return r.json()["data"]
    sgdb = SteamGridDBApi(api_key)
    search_frame = tk.Frame(cover_win)
    search_frame.pack(fill=tk.X, padx=10, pady=5)
    tk.Label(search_frame, text="SGDB搜索:").pack(side=tk.LEFT)
    search_var = tk.StringVar(value=app_name)
    entry = tk.Entry(search_frame, textvariable=search_var, width=30)
    entry.pack(side=tk.LEFT)
    # 左侧区域：游戏列表和勾选框
    left_panel = tk.Frame(cover_win)
    left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
    result_listbox = tk.Listbox(left_panel, width=40, height=10)
    result_listbox.pack(fill=tk.BOTH, expand=True)
    # 添加勾选框："将SGDB游戏名称应用至本地"
    apply_name_var = tk.BooleanVar(value=True)
    tk.Checkbutton(left_panel, text="将SGDB游戏名称应用至本地", variable=apply_name_var).pack(anchor=tk.W, pady=(5, 0))
    thumb_frame = tk.Frame(cover_win)
    thumb_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
    grid_images = []
    grid_datas = []
    grids_meta = []
    result = {"path": None, "used_icon": False, "sgdb_name": None}
    stop_event = threading.Event()  # 新增线程终止事件
    fetch_thread = [None]  # 用列表包裹以便内部赋值
    selected_game_name = None  # 存储当前选中的SGDB游戏名称
    # 计算 exe_path 的父目录名，用作备用搜索关键词
    parent_dir_name = None
            
    try:
        if exe_path:
            ep = exe_path.strip('"')
            resolved = ep
            # 如果是快捷方式，解析到目标可执行路径
            try:
                if resolved.lower().endswith('.lnk'):
                    resolved = get_target_path_from_lnk(resolved)
                elif resolved.lower().endswith('.url'):
                    resolved = get_url_target_path(resolved)
            except Exception:
                # 解析失败则保留原始路径
                resolved = ep
            # 取解析后路径的父目录名
            parent_dir_name = os.path.basename(os.path.dirname(resolved)) or None
    except Exception:
        parent_dir_name = None
    def do_search():
        name = search_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入游戏名称")
            return
        result_listbox.delete(0, tk.END)
        try:
            games = sgdb.search_game(name)
            for g in games:
                result_listbox.insert(tk.END, f"{g['name']} (ID: {g['id']})")
            # 在列表末尾添加一个用父目录名搜索的选项（如果可用）
            if parent_dir_name:
                result_listbox.insert(tk.END, f"使用 {parent_dir_name} 搜索")
            if games:
                result_listbox.select_set(0)
                nonlocal selected_game_name
                selected_game_name = games[0]["name"]  # 保存第一个游戏名称
                load_covers()
        except Exception as e:
            messagebox.showerror("错误", f"搜索失败: {e}")
    def load_covers(event=None):
        idx = result_listbox.curselection()
        if not idx:
            messagebox.showwarning("提示", "请先选择一个游戏")
            return
        # 如果用户选择了列表中的“使用 <父目录> 搜索”项，则用父目录名重新发起搜索
        sel_index = idx[0]
        list_size = result_listbox.size()
        if parent_dir_name and sel_index == list_size - 1 and result_listbox.get(sel_index).startswith("使用"):
            # 重新设置搜索词并发起搜索
            search_var.set(parent_dir_name)
            do_search()
            return
        games = sgdb.search_game(search_var.get().strip())
        game_id = games[idx[0]]["id"]
        nonlocal selected_game_name
        selected_game_name = games[idx[0]]["name"]  # 保存当前选中的游戏名称
        def fetch():
            try:
                grids = sgdb.get_grids(game_id)
                if not grids:
                    cover_win.after(0, lambda: messagebox.showinfo("提示", "未找到该游戏的封面"))
                    return
                def clear_thumbs():
                    for widget in thumb_frame.winfo_children():
                        widget.destroy()
                    grid_images.clear()
                    grid_datas.clear()
                    grids_meta.clear()
                cover_win.after(0, clear_thumbs)
                import functools
                for i, grid in enumerate(grids[:8]):
                    if stop_event.is_set():
                        return
                    url = grid["url"]
                    try:
                        resp = requests.get(url)
                        if stop_event.is_set(): 
                            return
                        img_data = resp.content
                        image = Image.open(BytesIO(img_data))
                        thumb = image.copy()
                        thumb.thumbnail((100, 150))
                        thumb_img = ImageTk.PhotoImage(thumb)
                        grid_images.append(thumb_img)
                        grid_datas.append(img_data)
                        grids_meta.append(grid)
                        def create_btn(idx, timg):
                            btn = tk.Button(thumb_frame, image=timg, command=functools.partial(save_cover, idx))
                            btn.grid(row=idx//4, column=idx%4, padx=5, pady=5)
                        cover_win.after(0, create_btn, i, thumb_img)
                    except Exception as e:
                        print(f"加载图片失败: {e}")
            except Exception as e:
                if not stop_event.is_set():
                    cover_win.after(0, lambda: messagebox.showerror("错误", f"获取封面失败: {e}"))
        # 启动前先终止旧线程
        if fetch_thread[0] and fetch_thread[0].is_alive():
            stop_event.set()
            fetch_thread[0].join()
            stop_event.clear()
        fetch_thread[0] = threading.Thread(target=fetch, daemon=True)
        fetch_thread[0].start()
    def save_cover(idx):
        if idx >= len(grid_datas):
            print("图片尚未加载完成，无法保存。")
            return
        stop_event.set()  # 终止图片加载线程
        img_data = grid_datas[idx]
        with open(output_path, "wb") as f:
            f.write(img_data)
        result["path"] = output_path
        result["used_icon"] = False
        # 如果勾选了"将SGDB游戏名称应用至本地"，则保存游戏名称
        if apply_name_var.get() and selected_game_name:
            result["sgdb_name"] = selected_game_name
        cover_win.destroy()
        cover_win.quit()
    def on_close():
        # 新增：参数启动时关闭窗口直接退出
        if len(sys.argv) >= 3 and sys.argv[1] == "-choosecover":
            sys.exit(0)
        stop_event.set()
        cover_win.destroy()
        cover_win.quit()
    #def use_icon():
    #    stop_event.set()  # 终止图片加载线程
    #    if exe_path:
    #        import os, re
    #        safe_name = re.sub(r'[\w]', '_', app_name)
    #        output_dir = os.path.dirname(output_path)
    #        icon_img_path = create_image_with_icon(exe_path, output_dir, app_name)
    #        result["path"] = icon_img_path
    #        result["used_icon"] = True
    #    cover_win.destroy()
    #btn_frame = tk.Frame(cover_win)
    #btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
    #tk.Button(btn_frame, text="使用图标作为封面", command=use_icon, width=30, bg="#aaaaaa").pack()
    def select_local_image():
        """选择本地图片作为封面"""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="选择本地图片",
            filetypes=[
                ("图片文件", "*.jpg *.jpeg *.png *.bmp *.gif"),
                ("JPEG文件", "*.jpg *.jpeg"),
                ("PNG文件", "*.png"),
                ("所有文件", "*.*")
            ]
        )
        if not file_path:
            return  # 用户取消选择
        
        try:
            stop_event.set()  # 终止图片加载线程
            # 打开并处理图片
            local_image = Image.open(file_path)
            # 转换为RGB模式（如果是RGBA等模式）
            if local_image.mode != 'RGB':
                local_image = local_image.convert('RGB')
            
            # 调整图片大小到 600x900（保持比例，居中裁剪）
            target_size = (600, 900)
            # 计算缩放比例，选择较大的比例以填充整个区域
            scale = max(target_size[0] / local_image.width, target_size[1] / local_image.height)
            new_width = int(local_image.width * scale)
            new_height = int(local_image.height * scale)
            
            # 使用兼容的方式调用resize
            try:
                resampler = Image.Resampling.LANCZOS
            except AttributeError:
                resampler = Image.LANCZOS
            local_image = local_image.resize((new_width, new_height), resampler)
            
            # 创建新的图片，居中裁剪
            final_image = Image.new('RGB', target_size, (0, 0, 0))
            x_offset = (new_width - target_size[0]) // 2
            y_offset = (new_height - target_size[1]) // 2
            # 确保裁剪区域不超出图片边界
            crop_box = (
                max(0, x_offset),
                max(0, y_offset),
                min(new_width, x_offset + target_size[0]),
                min(new_height, y_offset + target_size[1])
            )
            cropped = local_image.crop(crop_box)
            # 计算粘贴位置，使图片居中
            paste_x = (target_size[0] - cropped.width) // 2
            paste_y = (target_size[1] - cropped.height) // 2
            final_image.paste(cropped, (paste_x, paste_y))
            
            # 保存图片（根据输出路径的扩展名决定格式）
            if output_path.lower().endswith('.png'):
                final_image.save(output_path, "PNG")
            else:
                final_image.save(output_path, "JPEG", quality=95)
            result["path"] = output_path
            result["used_icon"] = False
            # 如果勾选了"将SGDB游戏名称应用至本地"且已选择游戏，则保存游戏名称
            if apply_name_var.get() and selected_game_name:
                result["sgdb_name"] = selected_game_name
            cover_win.destroy()
            cover_win.quit()
        except Exception as e:
            messagebox.showerror("错误", f"处理本地图片失败: {e}")
    
    entry.bind('<Return>', lambda e: do_search())
    tk.Button(search_frame, text="搜索", command=do_search).pack(side=tk.LEFT, padx=5)
    tk.Button(search_frame, text="选择本地图片", command=select_local_image, bg="#aaaaaa").pack(side=tk.LEFT, padx=5)
    tk.Label(search_frame, text="图片加载较慢，请耐心等候").pack(side=tk.LEFT, padx=5)
    
    # 在同一行添加剩余游戏数量和默认封面按钮
    if len(sys.argv) >= 4:  # 如果有传入剩余游戏数量参数
        remaining_games = int(sys.argv[3])
        if remaining_games > 1:
            # 添加剩余游戏数量提示和默认封面按钮
            tk.Label(search_frame, text=f"剩余：{remaining_games}个", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=5)
            
            # 添加全部使用默认封面按钮
            def skip_all_covers():
                msg = "确定对所有剩余游戏使用默认封面吗？\n这将关闭所有封面选择窗口。"
                if messagebox.askyesno("确认", msg):
                    try:
                        # 获取当前进程ID
                        current_pid = os.getpid()
                        # 获取进程名称
                        process_name = os.path.basename(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0])
                        
                        # 使用WMIC获取所有Python进程及其父进程ID
                        cmd = f'wmic process where name="{process_name}" get ProcessId,ParentProcessId,CommandLine /format:csv'
                        output = subprocess.check_output(cmd, shell=True, text=True)
                        
                        # 解析输出
                        lines = [line.strip() for line in output.split('\n') if line.strip()]
                        if len(lines) > 1:  # 跳过标题行
                            for line in lines[1:]:
                                try:
                                    parts = line.split(',')
                                    if len(parts) >= 3:
                                        cmd_line = parts[-3]  # CommandLine
                                        if "-choosecover" in cmd_line:  # 确认是封面选择窗口
                                            pid = int(parts[-2])  # ProcessId
                                            if pid != current_pid:  # 不终止自己
                                                # 强制终止进程及其子进程
                                                subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], 
                                                            creationflags=subprocess.CREATE_NO_WINDOW,
                                                            stdout=subprocess.DEVNULL, 
                                                            stderr=subprocess.DEVNULL)
                                except:
                                    continue
                        
                        # 最后终止自己
                        os._exit(0)
                    except Exception as e:
                        print(f"终止进程时出错: {e}")
                        os._exit(0)
                        
            skip_button = tk.Button(search_frame, text="全部使用默认", 
                                  command=skip_all_covers, bg="#ff9999",
                                  font=("微软雅黑", 9))
            skip_button.pack(side=tk.LEFT, padx=5)
    else:
        tk.Label(search_frame, text="关闭窗口使用默认封面", font=("微软雅黑", 9)).pack(side=tk.LEFT, padx=5)
    
    result_listbox.bind('<Double-Button-1>', load_covers)
    do_search()
    cover_win.protocol("WM_DELETE_WINDOW", on_close)
    cover_win.title(f"SGDB封面选择 - {app_name}")
    cover_win.mainloop()
    return result["path"], result["used_icon"], result["sgdb_name"]

def main():
    global folder_selected, onestart, close_after_completion, pseudo_sorting_enabled, lnkandurl_files
    # 获取当前目录下所有有效的 .lnk 和 .url 文件
    os.chdir(folder_selected)  # 设置为用户选择的目录
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
    if onestart:
        onestart = False
        return
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    apps_json = load_apps_json(apps_json_path)

    # 检查 target_paths 是否与 apps.json 中的条目名称相同
    # 处理 cmd 字段
    existing_names1 = set()
    for entry in apps_json.get('apps', []):
        cmd = entry.get('cmd')
        if isinstance(cmd, str):
            cmd_str = cmd.strip('"')
            if cmd_str:
                existing_names1.add(os.path.splitext(os.path.basename(cmd_str))[0])
        elif isinstance(cmd, (list, tuple)) and cmd:
            # 取列表中第一个合理的字符串元素
            for item in cmd:
                if isinstance(item, str) and item:
                    item_str = item.strip('"')
                    existing_names1.add(os.path.splitext(os.path.basename(item_str))[0])
                    break
        # 其他类型（如 None 或 dict）直接跳过

    # 处理 detached 字段，注意 detached 通常为列表
    existing_names2 = set()
    for entry in apps_json.get('apps', []):
        detached_list = entry.get('detached')
        if isinstance(detached_list, (list, tuple)):
            for detached_item in detached_list:
                if isinstance(detached_item, str) and detached_item:
                    di = detached_item.strip('"')
                    existing_names2.add(os.path.splitext(os.path.basename(di))[0])
    modified_target_paths = []  # 确保在这里初始化

    for idx, target_path in enumerate(target_paths):
        name = lnkandurl_files[idx]  # 获取文件名作为名称
        base_name = name.rsplit('.', 1)[0]
        # 修正条件判断，确保正确识别 .lnk 和 .url 文件
        if base_name in existing_names1 or base_name in existing_names2:
            modified_target_paths.append((target_path, True))  # 添加特殊标识符
        else:
            modified_target_paths.append((target_path, False))  # 不存在则标记为 False

    # 删除不存在的条目
    remove_entries_with_output_image(apps_json, lnkandurl_files)
    image_target_paths = []
    need_choose_cover_names = []
    print("--------------------生成封面--------------------")
    # 创建并处理图像
    for idx, (target_path, is_existing) in enumerate(modified_target_paths):
        if is_existing:
            print(f"跳过已存在的条目: {target_path}")
            continue  # 跳过已有条目的处理
        app_name = os.path.splitext(os.path.basename(lnkandurl_files[idx]))[0]
        exe_path = target_path
        output_dir = output_folder
        # ========== 优先为steam游戏设置封面 ==========
        output_index = find_unused_index(apps_json, image_target_paths)  # 获取未使用的索引
        cover_path = try_set_steam_cover_for_shortcut(app_name, lnkandurl_files[idx], output_dir, output_index)
        if cover_path:
            image_target_paths.append((lnkandurl_files[idx], output_index))
            print(f"已为Steam游戏 {app_name} 设置本地封面: {cover_path}")
        else:
            image_target_paths.append((lnkandurl_files[idx], output_index))
            output_path = os.path.join(output_folder, f"output_image{output_index}.png")
            create_image_with_icon(target_path, output_path, idx)
            print(f"已生成封面: {app_name}")
            need_choose_cover_names.append(app_name)  # 记录需要选择封面的app_name
    # 转换 modified_target_paths
    modified_target_paths1 = modified_target_paths
    modified_target_paths = []
    for idx, (target_path, is_existing) in enumerate(modified_target_paths1):
        modified_target_paths.append((lnkandurl_files[idx], is_existing))
    
    print("--------------------更新配置--------------------")
    # 添加新的快捷方式条目
    add_entries_to_apps_json(lnk_files, apps_json, modified_target_paths, image_target_paths)

    # 处理 .url 文件的条目
    for index, (url_file, target_path) in enumerate(url_files, start=len(lnk_files)):
        if any(target_path == url_file and is_existing for target_path, is_existing in modified_target_paths):
            print(f"跳过已存在的条目: {url_file}")
            continue  # 跳过已有条目的处理
        matching_image_entry = next((item for item in image_target_paths if item[0] == url_file), None)
        app_entry = generate_app_entry(url_file, matching_image_entry[1])
        if app_entry:  # 仅在 app_entry 不为 None 时添加
            apps_json["apps"].append(app_entry)
            print(f"新加入: {url_file}")

    # 如果启用了伪排序，更新条目的名称
    if pseudo_sorting_enabled:
        for idx, entry in enumerate(apps_json["apps"]):
            # 去掉之前的序号
            entry["name"] = re.sub(r'^\d{2} ', '', entry["name"])  # 去掉开头的两位数字和空格
            entry["name"] = f"{idx:02d} {entry['name']}"  # 在名称前加上排序数字，格式化为两位数
        print("已添加伪排序标志")

    # 保存更新后的 apps.json 文件
    save_apps_json(apps_json, apps_json_path)
    restart_service()
    # 新增：统一调用-choosecover进行选择，并传递剩余游戏数量
    if need_choose_cover_names:
        exe_path = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
        total_games = len(need_choose_cover_names)
        for i, name in enumerate(need_choose_cover_names):
            remaining_games = total_games - i
            try:
                cmd = [exe_path, "-choosecover", name, str(remaining_games)]
                process = subprocess.Popen(cmd)
                process.wait()  # 等待子进程完成
            except Exception as e:
                print(f"调用SGDB封面选择失败: {e}")
    if close_after_completion:
        os._exit(0)  # 正常退出

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

if __name__ == "__main__":
    # 命令行参数支持
    if len(sys.argv) >= 3 and sys.argv[1] == "-choosecover":
        root = tk.Tk()
        # 1. 读取 apps.json
        apps_json_path = f"{APP_INSTALL_PATH}\\config\\apps.json"
        apps_json = load_apps_json(apps_json_path)
        app_names = [entry["name"] for entry in apps_json.get("apps", [])]

        game_name = sys.argv[2] # 获取游戏名称参数
        # 找到对应app_entry
        app_entry = None
        for entry in apps_json.get("apps", []):
            if entry["name"] == game_name:
                app_entry = entry
                break
        if app_entry:
            # 统一调用choose_cover_with_sgdb
            covers_dir = os.path.join(APP_INSTALL_PATH, "config", "covers")
            os.makedirs(covers_dir, exist_ok=True)
            appid = app_entry.get("appid") or app_entry.get("id") or app_entry.get("name")
            filename = os.path.join(covers_dir, f"{appid}_SGDB.jpg")
            exe_path = None
            # 尝试获取可执行路径
            if app_entry.get("cmd"):
                exe_path = app_entry["cmd"].strip('"')
            elif app_entry.get("detached") and len(app_entry["detached"]) > 0:
                exe_path = app_entry["detached"][0].strip('"')
            root.withdraw() 
            cover_path, used_icon, sgdb_name = choose_cover_with_sgdb(game_name, filename, exe_path)
            # 如果选择了封面，更新 apps.json
            if os.path.exists(filename):
                # 更新 apps.json
                app_entry["image-path"] = os.path.basename(filename)
                # 如果返回了SGDB游戏名称，则更新名称
                if sgdb_name:
                    app_entry["name"] = sgdb_name
                save_apps_json(apps_json, apps_json_path)
        else:
            tk.messagebox.showerror("错误", f"未找到游戏名称为 {game_name} 的条目")
        sys.exit(0)
    if len(sys.argv) >= 3 and sys.argv[1] == "-addlnk":
        root1 = tk.Tk()
        root1.withdraw()  # 隐藏主窗口
        target_path = sys.argv[2]
        folder_selected = load_config()
        if not os.path.isdir(folder_selected):
            messagebox.showerror("错误", f"目标文件夹不存在: {folder_selected}")
            sys.exit(1)
        if not os.path.exists(target_path):
            messagebox.showerror("错误", f"指定的程序路径不存在: {target_path}")
            sys.exit(1)
        # 生成快捷方式名称
        base_name = os.path.splitext(os.path.basename(target_path))[0]
        lnk_name = f"{base_name}.lnk"
        lnk_path = os.path.join(folder_selected, lnk_name)
        try:
            pythoncom.CoInitialize()
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            shortcut.TargetPath = target_path
            shortcut.WorkingDirectory = os.path.dirname(target_path)
            shortcut.IconLocation = target_path
            shortcut.save()
            #messagebox.showinfo("成功", f"已创建快捷方式: {lnk_path}")
            onestart = False
            root1.destroy()  # 销毁隐藏窗口
            create_gui()
        except Exception as e:
            messagebox.showerror("错误", f"创建快捷方式失败: {e}")
            sys.exit(1)
        sys.exit(0)
    if len(sys.argv) >= 3 and sys.argv[1] == "-delete":
        del_name = sys.argv[2]
        folder_selected = load_config()
        apps_json_path = f"{APP_INSTALL_PATH}\\config\\apps.json"
        apps_json = load_apps_json(apps_json_path)
        import re
        found = False
    
        # 1. 先在 apps.json 查找对应条目（支持伪排序名）
        matched_entry = None
        for entry in apps_json["apps"]:
            entry_name = entry.get("name", "")
            if entry_name == del_name or re.sub(r'^\d{2} ', '', entry_name) == del_name:
                matched_entry = entry
                break
    
        if matched_entry:
            # 2. 检查 cmd 或 detached 字段，判断快捷方式是否存在
            possible_files = []
            if matched_entry.get("cmd"):
                cmd_path = matched_entry["cmd"].strip('"')
                base = os.path.splitext(os.path.basename(cmd_path))[0]
                for ext in [".lnk", ".url"]:
                    possible_files.append(os.path.join(folder_selected, f"{base}{ext}"))
            if matched_entry.get("detached"):
                for det in matched_entry["detached"]:
                    det_path = det.strip('"')
                    base = os.path.splitext(os.path.basename(det_path))[0]
                    for ext in [".lnk", ".url"]:
                        possible_files.append(os.path.join(folder_selected, f"{base}{ext}"))
            # 3. 删除存在的快捷方式文件
            for file_path in possible_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"已删除文件: {file_path}")
                        found = True
                    except Exception as e:
                        print(f"删除文件失败: {file_path}，原因: {e}")
            # 4. apps.json 删除该条目
            apps_json["apps"] = [
                entry for entry in apps_json["apps"]
                if entry is not matched_entry
            ]
            save_apps_json(apps_json, apps_json_path)
            print(f"已从 apps.json 删除名称为 {del_name} 的条目")
            #if found:
            #    onestart = False
            #    create_gui()
            sys.exit(0)
        else:
            print(f"未找到名称为 {del_name} 的 apps.json 条目")
            sys.exit(0)
    # if len(sys.argv) >= 4 and sys.argv[1] == "-rename":
    #     old_name = sys.argv[2]
    #     new_name = sys.argv[3]
    #     folder_selected = load_config()
    #     found = False
    #     # 1. 重命名文件夹中的 .lnk 或 .url 文件
    #     for ext in [".lnk", ".url"]:
    #         old_path = os.path.join(folder_selected, f"{old_name}{ext}")
    #         new_path = os.path.join(folder_selected, f"{new_name}{ext}")
    #         if os.path.exists(old_path):
    #             try:
    #                 os.rename(old_path, new_path)
    #                 print(f"已重命名文件: {old_path} -> {new_path}")
    #                 found = True
    #                 onestart = False
    #                 create_gui()
    #             except Exception as e:
    #                 print(f"重命名文件失败: {old_path}，原因: {e}")
    #     # 2. 如果没找到文件，则尝试在 apps.json 中重命名
    #     if not found:
    #         apps_json_path = f"{APP_INSTALL_PATH}\\config\\apps.json"
    #         apps_json = load_apps_json(apps_json_path)
    #         import re
    #         changed = False
    #         for entry in apps_json["apps"]:
    #             entry_name = entry.get("name", "")
    #             if entry_name == old_name or re.sub(r'^\d{2} ', '', entry_name) == old_name:
    #                 # 保留伪排序前缀
    #                 prefix = ""
    #                 m = re.match(r'^(\d{2} )', entry_name)
    #                 if m:
    #                     prefix = m.group(1)
    #                 entry["name"] = prefix + new_name
    #                 changed = True
    #         if changed:
    #             save_apps_json(apps_json, apps_json_path)
    #             print(f"已在 apps.json 中重命名为 {new_name}")
    #             found = True
    #     if not found:
    #         print(f"未找到名称为 {old_name} 的快捷方式或 apps.json 条目")
    #     sys.exit(0)
    if "-run" in sys.argv:
        onestart = False
        create_gui()
    else:
        create_gui()  # 启动Tkinter界面
