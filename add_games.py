import os

import psutil
import win32gui
import win32process
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFrame, QMessageBox, QDialog, QFileDialog
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt
from basic_def import runtomain, add_files_to_work_folder_as_shortcuts
from scanner_add_page import load_scanners, save_scanners
from scanner_manage_page import run_scanner, _load_ignored_targets, _get_work_folder


class AddGameWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI界面"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)
        
        # ========== 左侧：开始添加 ==========
        left_widget = QFrame()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(12, 20, 12, 20)
        left_layout.setSpacing(15)
        
        # 标题
        left_title = QLabel("开始添加")
        left_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        left_layout.addWidget(left_title)
        
        # 说明文本 - 第一段
        left_desc1 = QLabel("将您的添加列表（工作文件夹）的游戏添加至Sunshine")
        left_desc1.setFont(QFont("Segoe UI", 10))
        left_desc1.setWordWrap(True)
        left_layout.addWidget(left_desc1)
        left_desc11 = QLabel("以下是简要的操作步骤：")
        left_desc11.setFont(QFont("Segoe UI", 12))
        left_desc11.setWordWrap(True)
        left_layout.addWidget(left_desc11)
        
        # 说明文本 - 第二段
        left_desc2 = QLabel(
            "1. 点击\"run\"按钮来解析您的游戏。\n"
            "2. 等到所有图片都下载完成为止\n"
            "3. 点击\"保存至\"，然后等待出现\"添加/删除条目完成\""
            "的提示信息。"
        )
        left_desc2.setFont(QFont("Segoe UI", 12))
        left_desc2.setWordWrap(True)
        left_layout.addWidget(left_desc2)
        
        # 说明文本 - 第三段
        left_desc3 = QLabel("如果游戏的美术设计有误，请点击\"修复\"并选择正确的游戏，然后点击\"保存\"并关闭。")
        left_desc3.setFont(QFont("Segoe UI", 12))
        left_desc3.setWordWrap(True)
        left_layout.addWidget(left_desc3)
        
        # 说明文本 - 第四段
        left_desc4 = QLabel("如果您不想添加所有游戏，请点击\"忽略应用\"，然后选择您不想添加的那些应用，最后点击\"保存忽略项\"即可。")
        left_desc4.setFont(QFont("Segoe UI", 12))
        left_desc4.setWordWrap(True)
        left_layout.addWidget(left_desc4)        
        left_desc5 = QLabel("（也可以将游戏启动文件拖入此处添加，一次可拖入多个）")
        left_desc5.setFont(QFont("Segoe UI", 10))
        left_desc5.setWordWrap(True)
        left_layout.addWidget(left_desc5)
        
        # 添加弹性间隔
        left_layout.addStretch()
        
        # Run 按钮
        run_btn = QPushButton("run")
        run_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        run_btn.setFixedHeight(60)
        run_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2E7D9B;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 5px;"
            "  padding: 10px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #245A71;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #1C4455;"
            "}"
        )
        left_layout.addWidget(run_btn)
        
        left_widget.setLayout(left_layout)
        # 仅保留分割线，不设背景以继承全局主题
        left_widget.setStyleSheet("QFrame { border-right: 1px solid #555555; }")
        # 连接按钮至方法
        run_btn.clicked.connect(runtomain)
        
        # ========== 右侧：运作扫描器 ==========
        right_widget = QFrame()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(12, 20, 12, 20)
        right_layout.setSpacing(15)
        
        # 标题 + 右上角悬浮按钮
        right_title = QLabel("运作扫描器")
        right_title.setFont(QFont("Segoe UI", 16, QFont.Bold))

        add_running_btn = QPushButton("添加运行中游戏")
        add_running_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        add_running_btn.setFixedHeight(34)
        add_running_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2E7D9B;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 5px;"
            "  padding: 6px 12px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #245A71;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #1C4455;"
            "}"
        )
        self.add_running_btn = add_running_btn
        add_running_btn.clicked.connect(self.quick_add_running_game)

        title_layout = QHBoxLayout()
        title_layout.addWidget(right_title)
        title_layout.addStretch()
        title_layout.addWidget(add_running_btn)
        right_layout.addLayout(title_layout)
        
        # 说明文本 - 第一段
        right_desc1 = QLabel("扫描器能便捷的添加游戏至添加列表（工作文件夹）")
        right_desc1.setFont(QFont("Segoe UI", 10))
        right_desc1.setWordWrap(True)
        right_layout.addWidget(right_desc1)
        right_desc11 = QLabel("扫描器分为以下两类：")
        right_desc11.setFont(QFont("Segoe UI", 12))
        right_desc11.setWordWrap(True)
        right_layout.addWidget(right_desc11)
        
        # 说明文本 - 第二段
        right_desc2 = QLabel("1. 平台扫描器：用于扫描steam，epic内游戏\n2. rom扫描器：用于添加模拟器内游戏")
        right_desc2.setFont(QFont("Segoe UI", 12))
        right_desc2.setWordWrap(True)
        right_layout.addWidget(right_desc2)
        
        # 说明文本 - 第三段
        right_desc3 = QLabel("扫描器不会扫描忽略列表的游戏。\n你可以在右侧某单编辑运作的扫描器\n启用的扫描器：（双击可切换状态）")
        right_desc3.setFont(QFont("Segoe UI", 12))
        right_desc3.setWordWrap(True)
        right_layout.addWidget(right_desc3)
        
        # 扫描器列表
        self.scanner_list = QListWidget()
        self.scanner_list.setMinimumHeight(120)
        # 背景与文字颜色由全局主题控制，深色模式下会使用深色背景
        self.scanner_list.setStyleSheet(
            "QListWidget { border: 2px solid #2E7D9B; border-radius: 5px; padding: 5px; }"
            "QListWidget::item:selected { background-color: #2E7D9B; color: white; }"
        )
        right_layout.addWidget(self.scanner_list)
        
        # 连接双击事件以切换启用状态
        self.scanner_list.itemDoubleClicked.connect(self._toggle_scanner_enabled)

        # 初始加载扫描器
        self.reload_scanners()

        right_layout.addStretch()
        
        # 添加弹性间隔
        right_layout.addStretch()
        
        # Scan 按钮
        scan_btn = QPushButton("scan")
        scan_btn.setFont(QFont("Segoe UI", 14, QFont.Bold))
        scan_btn.setFixedHeight(60)
        scan_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #2E7D9B;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 5px;"
            "  padding: 10px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #245A71;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #1C4455;"
            "}"
        )
        right_layout.addWidget(scan_btn)
        
        right_widget.setLayout(right_layout)
        
        # 添加左右两部分到主布局
        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 1)
        
        self.setLayout(main_layout)

        # 连接扫描按钮
        scan_btn.clicked.connect(self.run_enabled_scanners)

    def reload_scanners(self):
        """刷新扫描器列表，灰色显示未启用条目"""
        self.scanner_list.clear()
        scanners = load_scanners()
        if not scanners:
            item = QListWidgetItem("（无扫描器）")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.scanner_list.addItem(item)
            return

        for s in scanners:
            name = s.get("name", "")
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, s.get("id"))
            if not bool(s.get("enabled", True)):
                item.setForeground(Qt.gray)
            self.scanner_list.addItem(item)

    def _toggle_scanner_enabled(self, item):
        sid = item.data(Qt.UserRole)
        scanners = load_scanners()
        changed = False
        for s in scanners:
            if s.get("id") == sid:
                s["enabled"] = not bool(s.get("enabled", True))
                changed = True
                break
        if changed:
            save_scanners(scanners)
            self.reload_scanners()

    def run_enabled_scanners(self):
        scanners = [s for s in load_scanners() if s.get("enabled", True)]
        if not scanners:
            QMessageBox.information(self, "扫描", "没有已启用的扫描器可运行。")
            return

        ignored = _load_ignored_targets()
        work_folder = _get_work_folder()
        total_created = total_skipped = total_errors = 0
        for s in scanners:
            created, skipped, errors, note = run_scanner(s, work_folder, ignored, progress_cb=lambda m: None)
            total_created += created
            total_skipped += skipped
            total_errors += errors

        # 用非阻塞通知显示结果
        from PyQt5.QtWidgets import QApplication
        msg = (
            f"已运行 {len(scanners)} 个扫描器\n"
            f"创建 {total_created}, 跳过 {total_skipped}, 错误 {total_errors}\n"
            f"输出文件夹: {work_folder}"
        )
        print(msg)  # 同时打印到日志
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                if hasattr(w, 'log_tab'):
                    w.log_tab.show_success_notification(msg)
                    break
    def _extract_dropped_paths(self, event):
        paths = []
        mime = event.mimeData()

        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    local_path = url.toLocalFile()
                    if local_path:
                        paths.append(local_path)

        if not paths and mime.hasText():
            raw = mime.text().strip()
            if raw:
                # Fallback for drag sources that provide text payload.
                chunks = [x.strip().strip('{}') for x in raw.splitlines() if x.strip()]
                paths.extend(chunks)

        return paths

    def _has_supported_drop_file(self, event):
        for path in self._extract_dropped_paths(event):
            lowered = path.lower()
            if lowered.endswith('.exe') or lowered.endswith('.lnk'):
                return True
        return False

    def dragEnterEvent(self, event):
        if self._has_supported_drop_file(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._has_supported_drop_file(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [
            p for p in self._extract_dropped_paths(event)
            if p.lower().endswith('.exe') or p.lower().endswith('.lnk')
        ]

        if not paths:
            QMessageBox.warning(self, '提示', '仅支持拖入 .exe 或 .lnk 文件。')
            event.ignore()
            return

        result = add_files_to_work_folder_as_shortcuts(paths)
        created_count = len(result.get('created', []))
        skipped_count = len(result.get('skipped', []))
        error_count = len(result.get('errors', []))

        lines = [f"已在工作文件夹创建 {created_count} 个快捷方式。"]
        if skipped_count:
            lines.append(f"已跳过 {skipped_count} 个不支持文件。")
        if error_count:
            lines.append(f"有 {error_count} 个文件处理失败，请查看日志页。")
        lines.append(f"工作文件夹: {result.get('work_folder', '')}")

        # 用成功通知代替阻塞对话框
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        msg = '\n'.join(lines)
        if app:
            for w in app.topLevelWidgets():
                if hasattr(w, 'log_tab'):
                    w.log_tab.show_success_notification(msg)
                    break

        event.acceptProposedAction()

    def quick_add_running_game(self):
        """快速添加运行中游戏"""
        scale = 1.0
        proc_dialog = QDialog(self)
        proc_dialog.setWindowTitle("选择运行中游戏进程")
        proc_dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup)
        proc_dialog.setStyleSheet(f"""
            QDialog {{
                background-color: rgba(46, 46, 46, 0.98);
                border-radius: {int(10 * scale)}px;
                border: {int(2 * scale)}px solid #444444;
            }}
        """)

        vbox = QVBoxLayout(proc_dialog)
        vbox.setSpacing(int(10 * scale))
        vbox.setContentsMargins(
            int(20 * scale),
            int(20 * scale),
            int(20 * scale),
            int(20 * scale)
        )

        label = QLabel(
            "选择一个运行中游戏进程，加入到游戏列表。"
        )
        label.setStyleSheet("color: white; font-size: 16px;")
        label.setWordWrap(True)
        vbox.addWidget(label)

        # 枚举所有有前台窗口且不是隐藏的进程
        hwnd_pid_map = {}
        def enum_window_callback(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                hwnd_pid_map[pid] = hwnd
            return True
        win32gui.EnumWindows(enum_window_callback, None)

        proc_list = []
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                pid = proc.info.get('pid')
                name = proc.info.get('name', '')
                exe = proc.info.get('exe', '')
                if (
                    not pid
                    or pid not in hwnd_pid_map
                    or not exe
                    or name.lower() in ("explorer.exe", "desktopgame.exe", "textinputhost.exe")
                ):
                    continue
                proc_list.append(proc)
            except Exception:
                continue

        if not proc_list:
            label2 = QLabel("没有检测到可用进程")
            label2.setStyleSheet("color: white; font-size: 16px;")
            vbox.addWidget(label2)
        else:
            for proc in proc_list:
                proc_name = proc.info.get('name', '未知')
                proc_exe = proc.info.get('exe', '')

                hbox = QHBoxLayout()
                hbox.setSpacing(8)

                btn = QPushButton(f"{proc_name} ({proc_exe})")
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #444444;
                        color: white;
                        border-radius: {int(8 * scale)}px;
                        font-size: {int(14 * scale)}px;
                        padding: {int(8 * scale)}px;
                        text-align: left;
                    }}
                    QPushButton:hover {{
                        background-color: #555555;
                    }}
                """)
                btn.clicked.connect(
                    lambda checked, exe=proc_exe: self._quick_add_and_notify(exe, proc_dialog)
                )
                hbox.addWidget(btn)

                folder_btn = QPushButton("📁")
                folder_btn.setFixedSize(32, 32)
                folder_btn.setStyleSheet(
                    "QPushButton {"
                    "  background-color: #666666;"
                    "  color: white;"
                    "  border-radius: 6px;"
                    "  font-size: 18px;"
                    "  padding: 0px;"
                    "}"
                    "QPushButton:hover {"
                    "  background-color: #888888;"
                    "}"
                )

                def open_file_dialog(proc_exe=proc_exe):
                    start_dir = os.path.dirname(proc_exe) if proc_exe and os.path.exists(proc_exe) else ""
                    file_dialog = QFileDialog(proc_dialog)
                    file_dialog.setWindowTitle("手动选择要添加的游戏文件")
                    file_dialog.setNameFilter("可执行文件 (*.exe *.lnk)")
                    file_dialog.setFileMode(QFileDialog.ExistingFile)
                    if start_dir:
                        file_dialog.setDirectory(start_dir)
                    if file_dialog.exec_():
                        selected_file = file_dialog.selectedFiles()[0]
                        self._quick_add_and_notify(selected_file, proc_dialog)

                folder_btn.clicked.connect(
                    lambda checked, proc_exe=proc_exe: open_file_dialog(proc_exe)
                )
                hbox.addWidget(folder_btn)
                vbox.addLayout(hbox)

        proc_dialog.setLayout(vbox)
        proc_dialog.show()

        # 将对话框定位到“添加运行中游戏”按钮右上角对齐
        try:
            btn_pos = self.add_running_btn.mapToGlobal(self.add_running_btn.rect().topLeft())
            dlg_size = proc_dialog.sizeHint()
            x = btn_pos.x() + self.add_running_btn.width() - dlg_size.width()
            y = btn_pos.y() + self.add_running_btn.height() + 6
            proc_dialog.move(x, y)
        except Exception:
            pass

    def _quick_add_and_notify(self, exe_path, dialog):
        """添加游戏并提示"""
        dialog.accept()
        result = add_files_to_work_folder_as_shortcuts([exe_path])
        created = len(result.get('created', []))
        skipped = len(result.get('skipped', []))
        errors = len(result.get('errors', []))

        lines = [f"已在工作文件夹创建 {created} 个快捷方式。"]
        if skipped:
            lines.append(f"已跳过 {skipped} 个不支持文件。")
        if errors:
            lines.append(f"有 {errors} 个文件处理失败，请查看日志页。")
        msg = "\n".join(lines)

        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                if hasattr(w, 'log_tab'):
                    w.log_tab.show_success_notification(msg)
                    break
