import os
import sys

# 仅保存模式：由普通进程以 runas 拉起，执行写入 cover 与 apps.json 后退出（不启动 GUI）
if __name__ == "__main__" and "--elevated-save" in sys.argv:
    argv = sys.argv
    try:
        i = argv.index("--elevated-save")
        work_dir = apps_json_out = covers_dst = None
        j = i + 1
        while j < len(argv):
            if argv[j] == "--work-dir" and j + 1 < len(argv):
                work_dir, j = argv[j + 1], j + 2
            elif argv[j] == "--apps-json-out" and j + 1 < len(argv):
                apps_json_out, j = argv[j + 1], j + 2
            elif argv[j] == "--covers-dst" and j + 1 < len(argv):
                covers_dst, j = argv[j + 1], j + 2
            else:
                j += 1
        if work_dir and apps_json_out and covers_dst:
            from basic_def import do_elevated_save_work
            do_elevated_save_work(work_dir, apps_json_out, covers_dst)
            sys.exit(0)
    except Exception as e:
        print(e)
        sys.exit(1)

# CLI 模式：支持选择封面和删除游戏
if __name__ == "__main__" and ("--choosecover" in sys.argv or "--delete" in sys.argv):
    # 避免在 GUI 启动前导入 PyQt
    from basic_def import APP_INSTALL_PATH, load_apps_json, save_apps_json, TEMP_COVERS_DIR
    from sgdb_cover_window import choose_cover_with_sgdb_qt
    import uuid

    def _normalize_name(name: str) -> str:
        return "" if name is None else " ".join(str(name).strip().split()).lower()

    def _strip_pseudo_prefix(value: str) -> str:
        """去掉伪排序添加的两位数字前缀（如 "00 "）。"""
        import re
        return re.sub(r"^\d{2} ", "", value or "")

    def _collect_shortcut_files(entry):
        """收集条目 cmd/detached 中指向的 .lnk / .url 快捷方式文件。"""
        candidates = []
        cmd = entry.get("cmd")
        if isinstance(cmd, str) and cmd.strip():
            candidates.append(cmd.strip().strip('"'))
        detached = entry.get("detached")
        if isinstance(detached, (list, tuple)):
            for item in detached:
                if isinstance(item, str) and item.strip():
                    candidates.append(item.strip().strip('"'))
        return [c for c in candidates if c.lower().endswith((".lnk", ".url"))]

    def _delete_shortcut_files(entries):
        """删除条目对应的 .lnk / .url 文件，避免下次扫描又出现在“待添加”中。"""
        shortcuts = []
        for entry in entries:
            for path in _collect_shortcut_files(entry):
                if path not in shortcuts:
                    shortcuts.append(path)
        for path in shortcuts:
            if not os.path.exists(path):
                print(f"快捷方式不存在，跳过: {path}")
                continue
            try:
                os.remove(path)
                print(f"已删除快捷方式: {path}")
            except Exception as exc:
                print(f"删除快捷方式失败: {path} ({exc})")

    apps_json_path = os.path.join(APP_INSTALL_PATH, "config", "apps.json")
    if not os.path.exists(apps_json_path):
        save_apps_json({"env": "", "apps": []}, apps_json_path, apply_to_sunshine=False)
    apps_json = load_apps_json(apps_json_path)

    args = sys.argv[1:]
    ok = True
    i = 0
    while i < len(args):
        if args[i] == "--choosecover" and i + 1 < len(args):
            game_name = args[i + 1]
            i += 2
            norm_target = _normalize_name(game_name)
            # 先做精确匹配，再做包含匹配
            entry = next((e for e in apps_json.get("apps", []) if _normalize_name(e.get("name")) == norm_target), None)
            if entry is None:
                entry = next((e for e in apps_json.get("apps", []) if norm_target in _normalize_name(e.get("name"))), None)

            if not entry:
                print(f"未找到名称为 '{game_name}' 的游戏，跳过选择封面。")
                ok = False
                continue

            exe_path = entry.get("cmd", "")
            os.makedirs(TEMP_COVERS_DIR, exist_ok=True)
            newname = f"sgdb_{uuid.uuid4().hex[:8]}.png"
            output_path = os.path.join(TEMP_COVERS_DIR, newname)

            result_bytes, used_icon, sgdb_name = choose_cover_with_sgdb_qt(
                app_name=entry.get("name", ""),
                output_path=output_path,
                exe_path=exe_path,
            )

            if result_bytes:
                from basic_def import format_image_path_for_apps_json
                entry["image-path"] = format_image_path_for_apps_json(newname)
                if sgdb_name:
                    entry["name"] = sgdb_name
                save_apps_json(apps_json, apps_json_path, extra_covers=[(newname, result_bytes)])
                print(f"已为 '{entry.get('name')}' 选择封面: {newname}")
            else:
                print(f"为 '{entry.get('name')}' 选择封面已取消或失败。")

        elif args[i] == "--delete" and i + 1 < len(args):
            game_name = args[i + 1]
            i += 2
            norm_target = _normalize_name(game_name)
            apps_list = apps_json.get("apps", [])
            # 先按原始名称精确匹配
            removed_entries = [e for e in apps_list if _normalize_name(e.get("name")) == norm_target]
            # 兼容伪排序：apps.json 里可能存的是 "00 游戏名"，而调用方传入的是去掉前缀的显示名
            if not removed_entries:
                removed_entries = [
                    e for e in apps_list
                    if _strip_pseudo_prefix(str(e.get("name") or "")) != str(e.get("name") or "")
                    and _normalize_name(_strip_pseudo_prefix(str(e.get("name") or ""))) == norm_target
                ]
            if removed_entries:
                removed_ids = {id(e) for e in removed_entries}
                apps_json["apps"] = [e for e in apps_list if id(e) not in removed_ids]
                save_apps_json(apps_json, apps_json_path)
                # 同时删除对应的 .lnk / .url，否则扫描时又会出现在“待添加”里
                _delete_shortcut_files(removed_entries)
                print(f"已删除 {len(removed_entries)} 个名称为 '{game_name}' 的游戏")
            else:
                print(f"未找到名称为 '{game_name}' 的游戏")
                ok = False
        else:
            i += 1

    sys.exit(0 if ok else 1)

from PyQt5.QtGui import QFont, QColor, QTextCursor, QTextCharFormat, QKeyEvent
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPropertyAnimation, QEasingCurve, QRect, QParallelAnimationGroup, QTranslator, QLocale, QEvent
from PyQt5 import QtCore
from io import StringIO

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QHBoxLayout, QStackedWidget, QPushButton, QButtonGroup, QSizePolicy,
    QTextEdit, QAbstractButton, QComboBox, QDialog, QListWidget,
    QTableWidget, QAbstractItemView, QScrollArea, QFrame, QLineEdit
)
from basic_def import initialize, load_config, _process_confirm_add_entries, ConfirmCard


def find_main_window(widget):
    """向上查找包含 confirm_card() 的 MainWindow。"""
    w = widget
    while w is not None:
        if hasattr(w, 'confirm_card') and callable(getattr(w, 'confirm_card', None)):
            return w
        w = w.parent()
    return None

def _pick_file(widget, mode='file', file_types=None, initial_path=None,
               title=None, on_result=None, on_cancel=None):
    """通过父级 MainWindow 的 show_file_picker 内嵌显示自制文件选择器；
    找不到主窗口时回退到原生 QFileDialog（同步调用回调）。"""
    mw = find_main_window(widget)
    if mw is not None and hasattr(mw, 'show_file_picker'):
        mw.show_file_picker(mode=mode, file_types=file_types,
                            initial_path=initial_path, title=title,
                            on_result=on_result, on_cancel=on_cancel)
        return
    # 回退：原生 QFileDialog（同步）
    from PyQt5.QtWidgets import QFileDialog
    if mode == 'directory':
        path = QFileDialog.getExistingDirectory(widget, title or '', initial_path or '')
        if path and on_result:
            on_result(path)
        elif on_cancel:
            on_cancel()
        return
    exts = file_types or ['.exe', '.lnk']
    filt = ' '.join(f'*{e}' for e in exts)
    path, _ = QFileDialog.getOpenFileName(widget, title or '', initial_path or '', filt)
    if path and on_result:
        on_result(path)
    elif on_cancel:
        on_cancel()

# 手柄支持（可选模块，加载失败时退化为不可用）
try:
    from gamepad import (
        GamepadManager,
        SDL_CONTROLLER_BUTTON_A,
        SDL_CONTROLLER_BUTTON_B,
    )
    _GAMEPAD_AVAILABLE = True
except Exception as _e:
    print(f"[Main] 手柄模块加载失败，手柄支持将被禁用: {_e}")
    _GAMEPAD_AVAILABLE = False
    GamepadManager = None
# 嵌入管理界面 (确保 manage_games_pyqt.py 与本文件位于同一目录)
try:
    from manage_games import ManageWindow
except Exception:
    ManageWindow = None

# 嵌入添加游戏界面
try:
    from add_games import AddGameWindow
except Exception:
    AddGameWindow = None

# 嵌入设置页面
try:
    from settings_page import SettingsPage
except Exception:
    SettingsPage = None

# 嵌入确认添加窗口
try:
    from confirm_add_window import ConfirmAddWindow
except Exception:
    ConfirmAddWindow = None

# 嵌入忽略列表管理
try:
    from ignore_manager import IgnoreManager
except Exception:
    IgnoreManager = None

# 嵌入扫描器界面
try:
    from scanner_page import ScannerPage
except Exception:
    ScannerPage = None


# 日志信号发射器
class LogSignalEmitter(QObject):
    log_signal = pyqtSignal(str, bool)  # 信号：(文本, 是否为错误)


# 输出重定向器
class StreamRedirector:
    def __init__(self, log_emitter, is_error=False, fallback=None):
        self.log_emitter = log_emitter
        self.is_error = is_error
        self.buffer = ""
        # 回退到原始标准流，确保未丢失 traceback 输出
        self.fallback = fallback if fallback is not None else (sys.__stderr__ if is_error else sys.__stdout__)

    def write(self, text):
        if not text:
            return
        # 同时写回原始流，便于在终端看到完整的 traceback
        try:
            self.fallback.write(text)
            try:
                self.fallback.flush()
            except Exception:
                pass
        except Exception:
            pass

        self.buffer += text
        # 每行发送一次信号
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            if line or self.is_error:
                self.log_emitter.log_signal.emit(line, self.is_error)

    def flush(self):
        if self.buffer:
            self.log_emitter.log_signal.emit(self.buffer, self.is_error)
            self.buffer = ""
        try:
            self.fallback.flush()
        except Exception:
            pass


# 日志标签页
class LogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.show_anim_group = None
        self.close_anim_group = None
        self.init_ui()
        
        # 创建日志信号发射器
        self.log_emitter = LogSignalEmitter()
        self.log_emitter.log_signal.connect(self.append_log)
        
        # 重定向输出流
        sys.stdout = StreamRedirector(self.log_emitter, is_error=False)
        sys.stderr = StreamRedirector(self.log_emitter, is_error=True)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 日志显示文本框（背景与文字颜色由全局主题控制，深色模式下会反色）
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 10))
        layout.addWidget(self.log_text)
        
        # 清空日志按钮
        button_layout = QHBoxLayout()
        clear_btn = QPushButton(self.tr("清空日志"))
        clear_btn.clicked.connect(self.clear_log)
        button_layout.addStretch()
        button_layout.addWidget(clear_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)

    def append_log(self, text, is_error):
        """将日志添加到文本框"""
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # 为错误信息设置红色
        if is_error and text.strip():
            cursor.setCharFormat(self.get_error_format())
        else:
            cursor.setCharFormat(self.get_normal_format())
        
        cursor.insertText(text + "\n")
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()
        
        # 如果是错误，显示通知
        if is_error and text.strip():
            self.show_error_notification(text)

    def get_error_format(self):
        """获取错误信息的格式（红色）"""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(255, 0, 0))
        return fmt

    def get_normal_format(self):
        """获取正常信息的格式（黑色）"""
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(0, 0, 0))
        return fmt

    def clear_log(self):
        """清空日志"""
        self.log_text.clear()

    def show_error_notification(self, error_text):
        """在窗口右下角显示错误通知"""
        if not self.parent_window:
            return
        
        # 创建或获取通知容器
        if not hasattr(self.parent_window, 'error_notification'):
            # 创建容器 widget
            notification = QWidget(self.parent_window)
            notification.setStyleSheet(
                "QWidget {background-color: #ffcccc; border: 2px solid #ff0000; "
                "padding: 8px; border-radius: 5px;}"
            )
            
            # 创建布局
            layout = QHBoxLayout()
            layout.setContentsMargins(10, 8, 5, 8)
            layout.setSpacing(10)
            
            # 创建文本标签
            text_label = QLabel()
            text_label.setFont(QFont("Segoe UI", 10))
            text_label.setStyleSheet("color: #cc0000; background: transparent; border: none;")
            text_label.setWordWrap(True)
            notification.text_label = text_label
            layout.addWidget(text_label)
            
            # 创建关闭按钮
            close_btn = QPushButton("✕")
            close_btn.setStyleSheet(
                "QPushButton {background: transparent; border: none; color: #cc0000; font-weight: bold; font-size: 14px; padding: 0px;}"
                "QPushButton:hover {color: #ff0000;}"
            )
            close_btn.setFixedSize(20, 20)
            close_btn.clicked.connect(lambda: self.close_error_notification_with_animation())
            layout.addWidget(close_btn)
            
            notification.setLayout(layout)
            notification.setWindowOpacity(0)  # 初始透明度为 0
            self.parent_window.error_notification = notification
            
            # 创建隐藏定时器
            if not hasattr(self.parent_window, 'notification_timer'):
                self.parent_window.notification_timer = QTimer(self.parent_window)
                self.parent_window.notification_timer.timeout.connect(
                    lambda: self.close_error_notification_with_animation()
                )
        
        notification = self.parent_window.error_notification
        
        # 截断过长的错误信息
        display_text = error_text[:100] + "..." if len(error_text) > 100 else error_text
        notification.text_label.setText(f"❌ {self.tr('错误：')}{display_text}")
        
        # 计算右下角位置（相对于父窗口）
        rect = self.parent_window.rect()
        notification_width = notification.sizeHint().width() + 20
        notification_height = notification.sizeHint().height() + 20
        
        pos_x = rect.right() - notification_width - 15
        pos_y = rect.bottom() - notification_height - 15
        
        # 初始位置在右边关闭外面
        start_x = rect.right() + 20
        notification.setGeometry(start_x, pos_y, notification_width, notification_height)
        notification.show()
        
        # 创建显示动画
        self.show_notification_animation(notification, start_x, pos_x, pos_y, notification_width, notification_height)
        
        # 3秒后隐藏通知
        self.parent_window.notification_timer.stop()
        self.parent_window.notification_timer.start(3000)
    
    def show_notification_animation(self, notification, start_x, end_x, pos_y, width, height):
        """显示通知的动画：从右往左渐显"""
        # 透明度动画
        opacity_anim = QPropertyAnimation(notification, b"windowOpacity")
        opacity_anim.setDuration(400)
        opacity_anim.setStartValue(0)
        opacity_anim.setEndValue(1)
        opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 位置动画
        pos_anim = QPropertyAnimation(notification, b"geometry")
        pos_anim.setDuration(400)
        pos_anim.setStartValue(QRect(start_x, pos_y, width, height))
        pos_anim.setEndValue(QRect(end_x, pos_y, width, height))
        pos_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 同时执行两个动画
        if not hasattr(self, 'show_anim_group') or self.show_anim_group is None:
            self.show_anim_group = QParallelAnimationGroup()
        
        self.show_anim_group.clear()
        self.show_anim_group.addAnimation(opacity_anim)
        self.show_anim_group.addAnimation(pos_anim)
        self.show_anim_group.start()
    
    def close_error_notification_with_animation(self):
        """关闭通知的动画：向右移动并渐隐"""
        if not self.parent_window or not hasattr(self.parent_window, 'error_notification'):
            return
        
        notification = self.parent_window.error_notification
        if notification.isHidden():
            return
        
        # 停止定时器
        if hasattr(self.parent_window, 'notification_timer'):
            self.parent_window.notification_timer.stop()
        
        rect = self.parent_window.rect()
        current_g = notification.geometry()
        
        # 透明度动画
        opacity_anim = QPropertyAnimation(notification, b"windowOpacity")
        opacity_anim.setDuration(400)
        opacity_anim.setStartValue(1)
        opacity_anim.setEndValue(0)
        opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 位置动画（向右移动）
        end_x = rect.right() + 20
        pos_anim = QPropertyAnimation(notification, b"geometry")
        pos_anim.setDuration(400)
        pos_anim.setStartValue(current_g)
        pos_anim.setEndValue(QRect(end_x, current_g.y(), current_g.width(), current_g.height()))
        pos_anim.setEasingCurve(QEasingCurve.InOutQuad)
        
        # 同时执行两个动画
        if not hasattr(self, 'close_anim_group') or self.close_anim_group is None:
            self.close_anim_group = QParallelAnimationGroup()
        
        self.close_anim_group.clear()
        self.close_anim_group.addAnimation(opacity_anim)
        self.close_anim_group.addAnimation(pos_anim)
        self.close_anim_group.finished.connect(lambda: notification.hide())
        self.close_anim_group.start()

    def show_success_notification(self, message_text):
        """在窗口右下角显示成功通知（绿色）"""
        if not self.parent_window:
            return
        
        # 创建或获取通知容器
        if not hasattr(self.parent_window, 'success_notification'):
            notification = QWidget(self.parent_window)
            notification.setStyleSheet(
                "QWidget {background-color: #ccffcc; border: 2px solid #00aa00; "
                "padding: 8px; border-radius: 5px;}"
            )
            layout = QHBoxLayout()
            layout.setContentsMargins(10, 8, 5, 8)
            layout.setSpacing(10)
            text_label = QLabel()
            text_label.setFont(QFont("Segoe UI", 10))
            text_label.setStyleSheet("color: #006600; background: transparent; border: none;")
            text_label.setWordWrap(True)
            notification.text_label = text_label
            layout.addWidget(text_label)
            close_btn = QPushButton("✕")
            close_btn.setStyleSheet(
                "QPushButton {background: transparent; border: none; color: #006600; font-weight: bold; font-size: 14px; padding: 0px;}"
                "QPushButton:hover {color: #00aa00;}"
            )
            close_btn.setFixedSize(20, 20)
            close_btn.clicked.connect(lambda: self.close_success_notification_with_animation())
            layout.addWidget(close_btn)
            notification.setLayout(layout)
            notification.setWindowOpacity(0)
            self.parent_window.success_notification = notification
            if not hasattr(self.parent_window, 'success_notification_timer'):
                self.parent_window.success_notification_timer = QTimer(self.parent_window)
                self.parent_window.success_notification_timer.timeout.connect(
                    lambda: self.close_success_notification_with_animation()
                )
        
        notification = self.parent_window.success_notification
        display_text = message_text[:100] + "..." if len(message_text) > 100 else message_text
        notification.text_label.setText(f"✅ {self.tr('成功：')}{display_text}")
        rect = self.parent_window.rect()
        notification_width = notification.sizeHint().width() + 20
        notification_height = notification.sizeHint().height() + 20
        pos_x = rect.right() - notification_width - 15
        pos_y = rect.bottom() - notification_height - 15
        start_x = rect.right() + 20
        notification.setGeometry(start_x, pos_y, notification_width, notification_height)
        notification.show()
        self.show_notification_animation(notification, start_x, pos_x, pos_y, notification_width, notification_height)
        self.parent_window.success_notification_timer.stop()
        self.parent_window.success_notification_timer.start(3000)

    def close_success_notification_with_animation(self):
        """关闭成功通知的动画"""
        if not self.parent_window or not hasattr(self.parent_window, 'success_notification'):
            return
        notification = self.parent_window.success_notification
        if notification.isHidden():
            return
        if hasattr(self.parent_window, 'success_notification_timer'):
            self.parent_window.success_notification_timer.stop()
        rect = self.parent_window.rect()
        current_g = notification.geometry()
        opacity_anim = QPropertyAnimation(notification, b"windowOpacity")
        opacity_anim.setDuration(400)
        opacity_anim.setStartValue(1)
        opacity_anim.setEndValue(0)
        opacity_anim.setEasingCurve(QEasingCurve.InOutQuad)
        end_x = rect.right() + 20
        pos_anim = QPropertyAnimation(notification, b"geometry")
        pos_anim.setDuration(400)
        pos_anim.setStartValue(current_g)
        pos_anim.setEndValue(QRect(end_x, current_g.y(), current_g.width(), current_g.height()))
        pos_anim.setEasingCurve(QEasingCurve.InOutQuad)
        if not hasattr(self, 'close_anim_group') or self.close_anim_group is None:
            self.close_anim_group = QParallelAnimationGroup()
        self.close_anim_group.clear()
        self.close_anim_group.addAnimation(opacity_anim)
        self.close_anim_group.addAnimation(pos_anim)
        self.close_anim_group.finished.connect(lambda: notification.hide())
        self.close_anim_group.start()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        import basic_def
        # 加载配置
        try:
            basic_def.load_config()
        except Exception:
            pass

        # 初始化翻译器
        self.translator = QTranslator()
        self._apply_language(basic_def.language)

        self.setWindowTitle("Sunshine App Manager v1.5")
        # 手柄激活标志：未操作手柄前不显示焦点高亮
        self._gamepad_active = False
        self.resize(1080, 480)

        tab_names = [
            self.tr('添加游戏'), self.tr('浏览游戏'), self.tr('日志'), self.tr('设置'),
            self.tr('忽略列表'), self.tr('扫描器')
        ]

        # 设置全局字体为微软雅黑
        app = QApplication.instance()
        app.setFont(QFont("Microsoft YaHei", 10))

        # 主容器
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        # 减少主布局边距与间距，缩减右侧空白
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_widget.setLayout(main_layout)

        # 左侧按钮侧栏
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar.setLayout(sidebar_layout)
        sidebar.setFixedWidth(140)
        self.sidebar = sidebar

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)
        # 保存为实例属性，供手柄导航使用
        self.button_group = button_group
        self.sidebar_count = len(tab_names)
        self.sidebar_index = 0  # 当前侧栏选中索引（手柄导航用）

        # 右侧页面区 (堆栈)
        self.stacked = QStackedWidget()
        # 去掉堆栈自身的内容边距
        self.stacked.setContentsMargins(0, 0, 0, 0)

        self.confirm_add_window = None  # 确认添加窗口引用
        self.confirm_add_page_index = None  # 确认添加窗口页面索引
        self._sgdb_cover_widget = None  # 内嵌 SGDB 封面选择器引用
        self._sgdb_cover_page_index = None  # 内嵌 SGDB 封面选择器页面索引
        self._sgdb_cover_prev_index = None  # 打开封面选择器前的页面索引
        self._sgdb_cover_callback = None  # 封面选择完成回调
        self._file_picker_widget = None  # 内嵌文件选择器引用
        self._file_picker_page_index = None  # 内嵌文件选择器页面索引
        self._file_picker_prev_index = None  # 打开文件选择器前的页面索引
        self._file_picker_callback = None  # 文件选择完成回调
        self._file_picker_cancel_callback = None  # 文件选择取消回调
        self._modal_confirm_cards = []  # 显示中的确认卡片栈（支持嵌套）
        
        for i, name in enumerate(tab_names):
            # 页面
            page = QWidget()
            v = QVBoxLayout()
            # 减少页面内部边距，避免内容被推离右侧
            v.setContentsMargins(6, 6, 6, 6)
            v.setSpacing(6)
            
            # 根据标签页索引创建不同内容
            if i == 0 and AddGameWindow is not None:
                # 添加游戏 - 嵌入添加游戏窗口
                add_game_widget = AddGameWindow()
                add_game_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(add_game_widget)
            elif i == 1 and ManageWindow is not None:
                # 浏览游戏 - 嵌入管理窗口
                manage_widget = ManageWindow()
                # 作为内嵌控件时去掉独立窗口的最小尺寸限制
                manage_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(manage_widget)
            elif i == 2:
                # 日志标签页
                log_tab = LogTab(self)
                self.log_tab = log_tab  # keep reference for notifications
                v.addWidget(log_tab)
            elif i == 3 and SettingsPage is not None:
                # 设置标签页
                settings_widget = SettingsPage()
                settings_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(settings_widget)
            elif i == 4 and IgnoreManager is not None:
                # 忽略列表标签页
                ignore_widget = IgnoreManager()
                ignore_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(ignore_widget)
            elif i == 5 and ScannerPage is not None:
                # 扫描器标签页（左列表 + 右详情面板）
                scanner_widget = ScannerPage()
                scanner_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(scanner_widget)
            else:
                # 其他标签页 - 显示占位符
                label = QLabel(self.tr("这是标签页%1的内容").replace('%1', str(i+1)))
                label.setAlignment(Qt.AlignCenter)
                label.setFont(QFont("Segoe UI", 14))
                v.addStretch()
                v.addWidget(label)
                v.addStretch()
            
            page.setLayout(v)
            self.stacked.addWidget(page)

            # 按钮
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setFixedHeight(70)
            btn.setFont(QFont("Segoe UI", 14))
            sidebar_layout.addWidget(btn)
            button_group.addButton(btn, i)

        sidebar_layout.addStretch()

        # 初始选择第一个
        first_btn = button_group.button(0)
        if first_btn:
            first_btn.setChecked(True)

        # 按钮切换处理
        def on_button_clicked(id_):
            self.stacked.setCurrentIndex(id_)
            # 同步手柄导航使用的侧栏索引（鼠标/键盘点击时也要更新）
            try:
                self.sidebar_index = int(id_)
            except Exception:
                pass

        button_group.idClicked.connect(on_button_clicked)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stacked)

        self.setCentralWidget(main_widget)

        # 应用初始主题
        self.apply_theme(basic_def.theme)

        # 初始化手柄支持
        self._init_gamepad()

        # 启动时清除焦点，避免出现初始高亮控件（等待用户操作手柄后再激活）
        self.setFocus()

    # ------------------------------------------------------------------
    # 手柄支持（仅使用方向键 + A + B）
    #   方向键：在屏幕控件间移动焦点（空间导航 + 列表/表格内部导航）
    #   A 键：  点击控件 / 进入下级（侧栏按钮进入页面，列表项激活等）
    #   B 键：  返回上级（关闭对话框 / 页面内容返回侧栏）
    # ------------------------------------------------------------------
    def _init_gamepad(self):
        """初始化手柄管理器并启动轮询定时器。"""
        self.gamepad = None
        self._gamepad_timer = None
        if not _GAMEPAD_AVAILABLE:
            return
        try:
            self.gamepad = GamepadManager()
        except Exception as e:
            print(f"[Main] GamepadManager 初始化失败: {e}")
            self.gamepad = None
            return
        if not self.gamepad.available:
            print("[Main] 手柄支持不可用（SDL2.dll 未加载成功）")
            return
        self._gamepad_timer = QTimer(self)
        self._gamepad_timer.timeout.connect(self._poll_gamepad)
        self._gamepad_timer.start(50)
        # 程序启动时不设置焦点，等手柄操作后再高亮

    def _poll_gamepad(self):
        """轮询手柄输入，转换为焦点导航 / 激活 / 返回动作。"""
        gp = getattr(self, "gamepad", None)
        if gp is None or not gp.available:
            return
        try:
            btn_pressed, _btn_released, dir_events = gp.poll()
        except Exception:
            return

        # 仅处理首个手柄
        if btn_pressed:
            btn_pressed = [(idx, btn) for idx, btn in btn_pressed if idx == 0]
        if dir_events:
            dir_events = [(idx, ev) for idx, ev in dir_events if idx == 0]
        if not btn_pressed and not dir_events:
            return

        # 首次手柄操作：激活焦点高亮，并将焦点设到当前侧栏按钮
        if not self._gamepad_active:
            self._gamepad_active = True
            import basic_def
            self.apply_theme(basic_def.theme)
            self._focus_sidebar_current()

        # ---- 方向事件 → 焦点移动 ----
        for _idx, ev in dir_events:
            base = ev
            if base.startswith('FIRST-'):
                base = base[len('FIRST-'):]
            elif base.endswith('_EDGE'):
                base = base[:-len('_EDGE')]
            if base in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
                self._move_focus(base)

        # ---- A / B 按钮 ----
        for _idx, btn in btn_pressed:
            if btn == SDL_CONTROLLER_BUTTON_A:
                self._activate_focused()
            elif btn == SDL_CONTROLLER_BUTTON_B:
                self._go_back()

    # ---- 焦点空间导航 ----

    _DIR_KEY_MAP = {
        'UP': Qt.Key_Up,
        'DOWN': Qt.Key_Down,
        'LEFT': Qt.Key_Left,
        'RIGHT': Qt.Key_Right,
    }

    def _move_focus(self, direction):
        """在指定方向上移动焦点。"""
        focus = QApplication.focusWidget()
        if focus is None:
            self._focus_sidebar_current()
            return

        # 确认卡片栈存在时，导航限制在最顶层卡片内的按钮间
        if self._modal_confirm_cards:
            self._move_focus_spatial(direction)
            return

        # 列表项内子控件（如扫描结果的「忽略」按钮）：左右进出、上下项间移动
        if not isinstance(focus, QListWidget):
            list_parent = self._find_parent_listwidget(focus)
            if list_parent is not None:
                if direction == 'LEFT':
                    # 回到列表本身，保持当前项选择
                    list_parent.setFocus()
                    return
                if direction in ('UP', 'DOWN'):
                    if self._move_to_sibling_item_button(list_parent, focus, direction):
                        return
                    # 到边缘了，跳出列表
                    self._move_focus_spatial(direction)
                    return
                # RIGHT：跳出列表到下一个控件
                self._move_focus_spatial(direction)
                return

        # QScrollArea viewport / QFrame 等容器获得焦点时，方向键会被用于滚动
        # 直接跳到空间导航，找到真正的可交互控件
        if isinstance(focus, QScrollArea) or self._is_scrollarea_viewport(focus):
            self._move_focus_spatial(direction)
            return

        # QComboBox 本身不发送方向键（避免被困住），用 A 键打开弹出列表选择
        if isinstance(focus, QComboBox):
            self._move_focus_spatial(direction)
            return

        # 按钮类（QPushButton/QCheckBox）：直接空间导航
        # QPushButton 默认会接受方向键并按 Tab 链移动焦点，不符合空间方向预期
        if isinstance(focus, QAbstractButton):
            self._move_focus_spatial(direction)
            return

        # QListWidget：在边缘时跳出，否则内部移动
        if isinstance(focus, QListWidget):
            if not self._list_can_move(focus, direction):
                # RIGHT：尝试进入当前项内的按钮（如忽略按钮）
                if direction == 'RIGHT' and self._focus_current_item_button(focus):
                    return
                self._move_focus_spatial(direction)
                return
        # QTableWidget：在边缘时跳出，否则内部移动
        elif isinstance(focus, QTableWidget):
            if not self._table_can_move(focus, direction):
                self._move_focus_spatial(direction)
                return

        # QLineEdit：左右方向键在光标已到边缘时跳出（手柄导航到旁边按钮，如“模板/浏览”）
        if isinstance(focus, QLineEdit):
            if direction == 'LEFT' and focus.cursorPosition() == 0:
                self._move_focus_spatial(direction)
                return
            if direction == 'RIGHT' and focus.cursorPosition() == len(focus.text()):
                self._move_focus_spatial(direction)
                return

        # 先将方向键发送给控件（列表/表格内部导航、文本编辑光标移动等）
        key = self._DIR_KEY_MAP.get(direction)
        if key is not None:
            event = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)
            QApplication.sendEvent(focus, event)
            if event.isAccepted():
                self._ensure_visible(focus)
                return

        # 控件未处理 → 空间导航
        self._move_focus_spatial(direction)

    def _move_focus_spatial(self, direction):
        """空间导航：在指定方向上找最近的可聚焦控件并聚焦。"""
        focus = QApplication.focusWidget()
        if focus is None:
            self._focus_sidebar_current()
            return

        cur_rect = QRect(focus.mapToGlobal(focus.rect().topLeft()), focus.size())
        # 使用焦点控件所在的窗口（而非 activeWindow），确保 Popup 弹窗内的控件也能被导航
        active_win = focus.window() or QApplication.activeWindow() or self

        best_widget = None
        best_score = None

        for w in QApplication.allWidgets():
            if w is focus:
                continue
            if not w.isVisible() or not w.isEnabled():
                continue
            if w.focusPolicy() == Qt.NoFocus:
                continue
            # 排除 QScrollArea 及其 viewport（方向键会被用于滚动而非导航）
            if isinstance(w, QScrollArea) or self._is_scrollarea_viewport(w):
                continue
            # 排除纯 QFrame 容器（非交互控件），但保留 QListWidget/QTableWidget 等子类
            if type(w) is QFrame:
                continue
            # 必须属于当前活动窗口
            if not active_win.isAncestorOf(w) and w is not active_win:
                continue

            w_rect = QRect(w.mapToGlobal(w.rect().topLeft()), w.size())
            score = self._directional_score(cur_rect, w_rect, direction)
            if score is None:
                continue
            if best_score is None or score < best_score:
                best_score = score
                best_widget = w

        if best_widget is not None:
            best_widget.setFocus()
            self._ensure_visible(best_widget)

    @staticmethod
    def _directional_score(cur, target, direction):
        """计算从 cur 到 target 在指定方向上的距离分数。返回 None 表示不在该方向。"""
        if direction == 'UP':
            if target.bottom() > cur.top():
                return None
            perp = MainWindow._perp_dist(cur, target, True)
            para = cur.top() - target.bottom()
        elif direction == 'DOWN':
            if target.top() < cur.bottom():
                return None
            perp = MainWindow._perp_dist(cur, target, True)
            para = target.top() - cur.bottom()
        elif direction == 'LEFT':
            if target.right() > cur.left():
                return None
            perp = MainWindow._perp_dist(cur, target, False)
            para = cur.left() - target.right()
        elif direction == 'RIGHT':
            if target.left() < cur.right():
                return None
            perp = MainWindow._perp_dist(cur, target, False)
            para = target.left() - cur.right()
        else:
            return None
        # 垂直对齐权重更高（×3），优先选择对齐的控件
        return perp * 3 + para

    @staticmethod
    def _perp_dist(cur, target, horizontal):
        """计算两矩形在垂直轴上的偏移距离。"""
        if horizontal:
            overlap = min(cur.right(), target.right()) - max(cur.left(), target.left())
            if overlap > 0:
                return 0
            return max(cur.left(), target.left()) - min(cur.right(), target.right())
        else:
            overlap = min(cur.bottom(), target.bottom()) - max(cur.top(), target.top())
            if overlap > 0:
                return 0
            return max(cur.top(), target.top()) - min(cur.bottom(), target.bottom())

    def _ensure_visible(self, widget):
        """确保控件在滚动区域内可见。"""
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                parent.ensureWidgetVisible(widget)
                break
            parent = parent.parentWidget()

    @staticmethod
    def _is_scrollarea_viewport(widget):
        """判断控件是否是 QScrollArea 的 viewport。"""
        p = widget.parentWidget()
        if p is not None and isinstance(p, QScrollArea):
            return p.viewport() is widget
        return False

    @staticmethod
    def _list_can_move(lst, direction):
        """QListWidget 在指定方向上是否还有可移动的项。"""
        row = lst.currentRow()
        if direction == 'UP':
            return row > 0
        elif direction == 'DOWN':
            return row < lst.count() - 1
        return False  # LEFT/RIGHT → 跳出列表

    @staticmethod
    def _table_can_move(tbl, direction):
        """QTableWidget 在指定方向上是否还有可移动的单元格。"""
        r, c = tbl.currentRow(), tbl.currentColumn()
        if direction == 'UP':
            return r > 0
        elif direction == 'DOWN':
            return r < tbl.rowCount() - 1
        elif direction == 'LEFT':
            return c > 0
        elif direction == 'RIGHT':
            return c < tbl.columnCount() - 1
        return False

    # ---- 列表项内子控件导航（如扫描结果的「忽略」按钮）----

    @staticmethod
    def _find_parent_listwidget(widget):
        """向上查找控件所属的 QListWidget（若控件本身就在某个列表项 widget 内）。"""
        p = widget.parentWidget()
        while p is not None:
            if isinstance(p, QListWidget):
                return p
            p = p.parentWidget()
        return None

    @staticmethod
    def _find_item_row_for_widget(lst, widget):
        """找到 widget 所属列表项的 row，找不到返回 None。"""
        for i in range(lst.count()):
            item = lst.item(i)
            w = lst.itemWidget(item)
            if w is None:
                continue
            if w is widget or w.isAncestorOf(widget):
                return i
        return None

    @staticmethod
    def _first_focusable_button_in_item(lst, row):
        """返回指定列表项 itemWidget 内第一个可聚焦的按钮控件，找不到返回 None。"""
        item = lst.item(row)
        if item is None:
            return None
        w = lst.itemWidget(item)
        if w is None:
            return None
        # 优先找按钮类
        for child in w.findChildren(QAbstractButton):
            if child.isVisible() and child.isEnabled() and child.focusPolicy() != Qt.NoFocus:
                return child
        return None

    def _focus_current_item_button(self, lst):
        """聚焦当前列表项 itemWidget 内的第一个可聚焦按钮，成功返回 True。"""
        row = lst.currentRow()
        if row < 0:
            return False
        btn = self._first_focusable_button_in_item(lst, row)
        if btn is None:
            return False
        btn.setFocus()
        return True

    def _move_to_sibling_item_button(self, lst, current_btn, direction):
        """移动到相邻列表项的同位置按钮，成功返回 True。"""
        row = self._find_item_row_for_widget(lst, current_btn)
        if row is None:
            return False
        if direction == 'UP' and row > 0:
            target_row = row - 1
        elif direction == 'DOWN' and row < lst.count() - 1:
            target_row = row + 1
        else:
            return False
        btn = self._first_focusable_button_in_item(lst, target_row)
        if btn is None:
            return False
        lst.setCurrentRow(target_row)
        btn.setFocus()
        return True

    # ---- A 键：激活 ----

    def _activate_focused(self):
        """激活（点击 / 进入）当前焦点控件。"""
        focus = QApplication.focusWidget()
        if focus is None:
            return

        # 侧栏按钮：点击切换页面，然后进入页面内容
        if self.sidebar.isAncestorOf(focus):
            focus.click()
            QTimer.singleShot(0, self._focus_first_in_page)
            return

        # 按钮类（QPushButton / QCheckBox）：点击
        if isinstance(focus, QAbstractButton):
            focus.click()
        # 组合框：弹出下拉列表
        elif isinstance(focus, QComboBox):
            focus.showPopup()
        # 列表：发送 Return 激活当前项（等效双击）
        elif isinstance(focus, QListWidget):
            self._send_key(focus, Qt.Key_Return)
        # 表格：发送 Return 激活当前项
        elif isinstance(focus, QTableWidget):
            self._send_key(focus, Qt.Key_Return)
        else:
            self._send_key(focus, Qt.Key_Return)

    # ---- B 键：返回上级 ----

    def _go_back(self):
        """返回上级：关闭弹出列表 / 关闭对话框 / 页面内容返回侧栏。"""
        focus = QApplication.focusWidget()

        # 0) 有确认卡片在栈中 → B 键关闭最顶层卡片（取消）
        if self._modal_confirm_cards:
            top = self._modal_confirm_cards[-1]
            try:
                if hasattr(top, 'close_card'):
                    top.close_card()
                else:
                    top._finish(False)
            except Exception:
                pass
            return

        # 1) 焦点在 QComboBox 弹出列表上 → 关闭弹出
        if focus is not None and isinstance(focus, QAbstractItemView):
            p = focus.parentWidget()
            while p is not None:
                if isinstance(p, QComboBox):
                    p.hidePopup()
                    return
                p = p.parentWidget()

        # 2) 焦点所在窗口是弹出对话框/浮窗 → 关闭它
        #    Qt.Popup 窗口不会成为 activeWindow，需用 focus.window() 定位
        focus_win = focus.window() if focus is not None else None
        if focus_win is not None and focus_win is not self:
            if isinstance(focus_win, QDialog):
                focus_win.reject()
                return
            if int(focus_win.windowFlags()) & int(Qt.Popup):
                focus_win.close()
                return

        # 再检查 activeWindow（兼容标准模态对话框）
        active = QApplication.activeWindow()
        if active is not None and active is not self and active is not focus_win:
            if isinstance(active, QDialog):
                active.reject()
                return
            self._send_key(active, Qt.Key_Escape)
            return

        # 3) 确认添加页面 → 取消返回
        if (self.confirm_add_window is not None
                and self.confirm_add_page_index is not None
                and self.stacked.currentIndex() == self.confirm_add_page_index):
            self._on_confirm_add_cancelled()
            return

        # 3b) 内嵌 SGDB 封面选择器 → 取消返回
        if (self._sgdb_cover_widget is not None
                and self._sgdb_cover_page_index is not None
                and self.stacked.currentIndex() == self._sgdb_cover_page_index):
            self._on_sgdb_cover_cancelled()
            return

        # 3c) 内嵌文件选择器 → 取消返回
        if (self._file_picker_widget is not None
                and self._file_picker_page_index is not None
                and self.stacked.currentIndex() == self._file_picker_page_index):
            self._on_file_picker_cancelled()
            return

        # 4) 焦点在页面内容中 → 返回侧栏
        if focus is not None and not self.sidebar.isAncestorOf(focus):
            self._focus_sidebar_current()
            return

        # 5) 已在最顶层（焦点在侧栏）→ 显示退出确认卡片
        self.confirm_card(
            'question', self.tr("退出"), self.tr("确定要退出吗？"),
            default_yes=False,
            on_result=lambda yes: yes and self.close()
        )

    # ---- 通用嵌入式确认卡片 ----

    def confirm_card(self, card_type, title, message, yes_text=None, no_text=None,
                     default_yes=False, on_result=None):
        """
        统一的嵌入式卡片弹层入口（供内部和各页面使用）。

        card_type: 'question' / 'information' / 'warning' / 'critical'
        返回：ConfirmCard 实例
        """
        card = ConfirmCard(
            parent=self,
            card_type=card_type,
            title=title,
            message=message,
            yes_text=yes_text,
            no_text=no_text,
            default_yes=default_yes,
        )
        # 入栈：无论外部是否传入 on_result，先保证栈一致
        self._modal_confirm_cards.append(card)

        def _done(result):
            # 出栈
            try:
                if card in self._modal_confirm_cards:
                    self._modal_confirm_cards.remove(card)
            except Exception:
                pass
            # 回调
            if on_result is not None:
                try:
                    on_result(result)
                except Exception:
                    pass

        card.on_finished(_done)
        # 显示并居中（ResizeEvent 会在栈中有卡片时重排所有卡片居中）
        card.show()
        return card

    def _center_all_confirm_cards(self):
        """将栈中所有卡片均重新居中。"""
        if not self._modal_confirm_cards:
            return
        for card in self._modal_confirm_cards:
            try:
                if hasattr(card, '_center'):
                    card._center()
                elif hasattr(card, 'parentWidget') and card.parentWidget() is not None:
                    pw = card.parentWidget()
                    x = (pw.width() - card.width()) // 2
                    y = (pw.height() - card.height()) // 2
                    card.move(x, y)
            except Exception:
                pass

    # ---- 焦点辅助 ----

    def _focus_sidebar_current(self):
        """将焦点设为当前页面对应的侧栏按钮。"""
        idx = self.stacked.currentIndex()
        if (self.confirm_add_page_index is not None
                and idx == self.confirm_add_page_index):
            idx = 0
        if (self._sgdb_cover_page_index is not None
                and idx == self._sgdb_cover_page_index):
            idx = self._sgdb_cover_prev_index if self._sgdb_cover_prev_index is not None else 0
        if (self._file_picker_page_index is not None
                and idx == self._file_picker_page_index):
            idx = self._file_picker_prev_index if self._file_picker_prev_index is not None else 0
        btn = self.button_group.button(idx) if self.button_group else None
        if btn is None:
            btn = self.button_group.button(0) if self.button_group else None
        if btn is not None:
            btn.setFocus()

    def _focus_first_in_page(self):
        """将焦点设为当前页面的第一个可聚焦控件。"""
        page = self.stacked.currentWidget()
        if page is None:
            return
        first = self._find_first_focusable(page)
        if first is not None:
            first.setFocus()
            self._ensure_visible(first)
        else:
            self._focus_sidebar_current()

    def _find_first_focusable(self, container):
        """在容器中查找第一个可聚焦控件（排除侧栏按钮、滚动区域及其 viewport、纯 QFrame 容器）。"""
        # 优先查找可交互控件（按钮 / 复选框 / 组合框 / 输入框 / 列表 / 表格）
        interactive_types = (QAbstractButton, QComboBox, QLineEdit, QListWidget, QTableWidget)
        # 第一轮：找可交互控件
        for w in container.findChildren(QWidget):
            if w is container:
                continue
            if self.sidebar.isAncestorOf(w):
                continue
            if isinstance(w, QScrollArea) or self._is_scrollarea_viewport(w):
                continue
            if type(w) is QFrame:
                continue
            if w.isVisible() and w.isEnabled() and w.focusPolicy() != Qt.NoFocus:
                if isinstance(w, interactive_types):
                    return w
        # 第二轮：任何可聚焦控件（兜底）
        for w in container.findChildren(QWidget):
            if w is container:
                continue
            if self.sidebar.isAncestorOf(w):
                continue
            if isinstance(w, QScrollArea) or self._is_scrollarea_viewport(w):
                continue
            if type(w) is QFrame:
                continue
            if w.isVisible() and w.isEnabled() and w.focusPolicy() != Qt.NoFocus:
                return w
        return None

    def _send_key(self, target, key):
        """向目标控件同步发送一个按键事件（按下并释放）。"""
        try:
            press = QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)
            release = QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier)
            QApplication.sendEvent(target, press)
            QApplication.sendEvent(target, release)
        except Exception:
            pass

    def closeEvent(self, event):
        """窗口关闭时释放手柄资源。"""
        # 先停止确认窗口的封面线程，避免退出时线程仍在回调 Qt 对象
        confirm_win = getattr(self, "confirm_add_window", None)
        if confirm_win is not None:
            try:
                confirm_win.shutdown_cover_thread()
            except Exception:
                pass
        if getattr(self, "_gamepad_timer", None) is not None:
            try:
                self._gamepad_timer.stop()
            except Exception:
                pass
        gp = getattr(self, "gamepad", None)
        if gp is not None:
            try:
                gp.cleanup()
            except Exception:
                pass
        super().closeEvent(event)

    def resizeEvent(self, event):
        """窗口大小变化时保持确认卡片居中。"""
        super().resizeEvent(event)
        self._center_all_confirm_cards()

    def show_confirm_add_window(self, pending_entries, apps_json, apps_json_path, output_folder,
                                pseudo_sorting_enabled=False, close_after_completion=True):
        """显示确认添加窗口"""
        if ConfirmAddWindow is None:
            return
        
        # 如果之前的窗口存在，删除它
        if self.confirm_add_window is not None and self.confirm_add_page_index is not None:
            # 先停止旧窗口的封面线程，避免销毁后线程仍回调 Qt 对象导致 C++ 崩溃
            try:
                self.confirm_add_window.shutdown_cover_thread()
            except Exception:
                pass
            widget = self.stacked.widget(self.confirm_add_page_index)
            self.stacked.removeWidget(widget)
            widget.deleteLater()
        
        # 创建新的确认窗口
        self.confirm_add_window = ConfirmAddWindow(
            pending_entries=pending_entries,
            apps_json=apps_json,
            apps_json_path=apps_json_path,
            output_folder=output_folder,
            pseudo_sorting_enabled=pseudo_sorting_enabled,
            close_after_completion=close_after_completion,
            parent=self
        )
        
        # 连接信号
        self.confirm_add_window.confirmed.connect(self._on_confirm_add_confirmed)
        self.confirm_add_window.cancelled.connect(self._on_confirm_add_cancelled)
        
        # 添加到 stacked widget
        self.confirm_add_page_index = self.stacked.addWidget(self.confirm_add_window)
        
        # 显示该页面
        self.stacked.setCurrentIndex(self.confirm_add_page_index)
    
    def _on_confirm_add_confirmed(self, selected_entries):
        """确认添加时的处理"""
        if self.confirm_add_window is None:
            return
        
        # 获取 apps_json 和其他必要信息
        apps_json = self.confirm_add_window.apps_json
        apps_json_path = self.confirm_add_window.apps_json_path
        
        # 调用处理函数
        try:
            _process_confirm_add_entries(selected_entries, apps_json, apps_json_path)
            # 处理完成后返回到上一个页面
            self.stacked.setCurrentIndex(0)
        except Exception as e:
            self.confirm_card('critical', self.tr("错误"),
                              self.tr("处理确认添加时出错: %1").replace('%1', str(e)))
    
    def _on_confirm_add_cancelled(self):
        """取消添加时的处理"""
        # 返回到上一个页面（如添加游戏页面）
        self.stacked.setCurrentIndex(0)

    def show_sgdb_cover_picker(self, app_name, exe_path, on_result, on_cancel=None):
        """在主窗口 stacked 中内嵌显示 SGDB 封面选择器。

        Args:
            app_name: 游戏名称
            exe_path: 可执行文件路径
            on_result: 回调 fn(result_bytes, used_icon, sgdb_name)
            on_cancel: 可选回调 fn()
        """
        from sgdb_cover_window import SgdbCoverPickerDialog
        import uuid as _uuid
        from basic_def import TEMP_COVERS_DIR as _TEMP_DIR

        # 清理上一次的封面选择器
        self._close_sgdb_cover_picker()

        os.makedirs(_TEMP_DIR, exist_ok=True)
        newname = f"sgdb_{_uuid.uuid4().hex[:8]}.png"
        output_path = os.path.join(_TEMP_DIR, newname)

        dlg = SgdbCoverPickerDialog(
            app_name=app_name,
            output_path=output_path,
            exe_path=exe_path,
            parent=self,
        )
        # 内嵌模式：设为无边框 QWidget 风格
        dlg.setWindowFlags(QtCore.Qt.Widget)

        self._sgdb_cover_widget = dlg
        self._sgdb_cover_newname = newname
        self._sgdb_cover_callback = on_result
        self._sgdb_cover_cancel_callback = on_cancel
        self._sgdb_cover_prev_index = self.stacked.currentIndex()

        dlg.cover_selected.connect(self._on_sgdb_cover_selected)
        dlg.cover_cancelled.connect(self._on_sgdb_cover_cancelled)

        self._sgdb_cover_page_index = self.stacked.addWidget(dlg)
        self.stacked.setCurrentIndex(self._sgdb_cover_page_index)

    def _on_sgdb_cover_selected(self, result_bytes, used_icon, sgdb_name):
        """内嵌封面选择器：选择完成"""
        cb = self._sgdb_cover_callback
        newname = getattr(self, '_sgdb_cover_newname', None)
        prev = self._sgdb_cover_prev_index
        self._close_sgdb_cover_picker()
        if prev is not None:
            self.stacked.setCurrentIndex(prev)
        if cb:
            cb(result_bytes, used_icon, sgdb_name, newname)

    def _on_sgdb_cover_cancelled(self):
        """内嵌封面选择器：取消"""
        cb = getattr(self, '_sgdb_cover_cancel_callback', None)
        prev = self._sgdb_cover_prev_index
        self._close_sgdb_cover_picker()
        if prev is not None:
            self.stacked.setCurrentIndex(prev)
        if cb:
            cb()

    def _close_sgdb_cover_picker(self):
        """移除并清理内嵌封面选择器"""
        if self._sgdb_cover_widget is not None and self._sgdb_cover_page_index is not None:
            w = self.stacked.widget(self._sgdb_cover_page_index)
            if w is not None:
                self.stacked.removeWidget(w)
                w.deleteLater()
        self._sgdb_cover_widget = None
        self._sgdb_cover_page_index = None
        self._sgdb_cover_prev_index = None
        self._sgdb_cover_callback = None
        self._sgdb_cover_cancel_callback = None
        self._sgdb_cover_newname = None

    # ---- 内嵌文件选择器 ----

    def show_file_picker(self, mode='file', file_types=None, initial_path=None,
                         title=None, on_result=None, on_cancel=None):
        """在主窗口 stacked 中内嵌显示自制文件选择器。

        Args:
            mode: 'file' 选择文件；'directory' 选择目录
            file_types: file 模式下的扩展名白名单（如 ['.exe', '.lnk']）
            initial_path: 起始目录
            title: 标题
            on_result: 回调 fn(path)，选择完成时调用
            on_cancel: 回调 fn()，取消时调用
        """
        from custom_file_picker import CustomFilePickerDialog

        self._close_file_picker()

        dlg = CustomFilePickerDialog(
            mode=mode,
            file_types=file_types,
            initial_path=initial_path,
            title=title,
            parent=self,
        )
        dlg.setWindowFlags(Qt.Widget)

        self._file_picker_widget = dlg
        self._file_picker_callback = on_result
        self._file_picker_cancel_callback = on_cancel
        self._file_picker_prev_index = self.stacked.currentIndex()

        dlg.file_selected.connect(self._on_file_picker_selected)
        dlg.picker_cancelled.connect(self._on_file_picker_cancelled)

        self._file_picker_page_index = self.stacked.addWidget(dlg)
        self.stacked.setCurrentIndex(self._file_picker_page_index)
        # 页面切换后焦点落到文件列表的当前选中项
        QtCore.QTimer.singleShot(0, dlg._focus_file_list)

    def _on_file_picker_selected(self, path):
        """内嵌文件选择器：选择完成"""
        cb = self._file_picker_callback
        prev = self._file_picker_prev_index
        self._close_file_picker()
        if prev is not None:
            self.stacked.setCurrentIndex(prev)
        if cb:
            cb(path)

    def _on_file_picker_cancelled(self):
        """内嵌文件选择器：取消"""
        cb = self._file_picker_cancel_callback
        prev = self._file_picker_prev_index
        self._close_file_picker()
        if prev is not None:
            self.stacked.setCurrentIndex(prev)
        if cb:
            cb()

    def _close_file_picker(self):
        """移除并清理内嵌文件选择器"""
        if self._file_picker_widget is not None and self._file_picker_page_index is not None:
            w = self.stacked.widget(self._file_picker_page_index)
            if w is not None:
                self.stacked.removeWidget(w)
                w.deleteLater()
        self._file_picker_widget = None
        self._file_picker_page_index = None
        self._file_picker_prev_index = None
        self._file_picker_callback = None
        self._file_picker_cancel_callback = None

    def apply_theme(self, theme):
        """应用主题"""
        # 焦点高亮样式：仅在用户操作过手柄后才显示，避免启动时有突兀的高亮
        focus_styles = ""
        if getattr(self, '_gamepad_active', False):
            focus_styles = (
                " QPushButton:focus { background-color: #66ccff; color: #003344; border: 2px solid #ffffff; }"
                " QPushButton:checked:focus { background-color: #66ccff; color: #003344; border: 2px solid #ffffff; }"
                " QLineEdit:focus { border: 2px solid #66ccff; }"
                " QComboBox:focus { border: 2px solid #66ccff; }"
                " QTextEdit:focus { border: 2px solid #66ccff; }"
                " QPlainTextEdit:focus { border: 2px solid #66ccff; }"
                " QCheckBox:focus { border: 2px solid #66ccff; }"
                " QListWidget::item:focus { background-color: #2E7D9B; color: #ffffff; }"
            )
            sidebar_focus = (
                " QPushButton:focus { border: 2px solid #66ccff; }"
                " QPushButton:checked:focus { background: #66ccff; color: #003344; border: 2px solid #ffffff; }"
            )
        else:
            sidebar_focus = ""

        if theme == "深色":
            stylesheet = (
                "QWidget { background-color: #2b2b2b; color: #ffffff; } "
                "QWidget:focus { outline: none; } "
                "QPushButton { background-color: #2E7D9B; color: white; border: 2px solid transparent; padding: 2px 6px; border-radius: 5px; } "
                "QPushButton:hover { background-color: #245A71; } "
                "QPushButton:pressed { background-color: #1C4455; } "
                "QPushButton:checked { background-color: #245A71; } "
                "QPushButton:disabled { background-color: #888888; color: #cccccc; } "
                "QLineEdit { background-color: #404040; color: #ffffff; border: 1px solid #555555; padding: 5px; } "
                "QComboBox { background-color: #404040; color: #ffffff; border: 1px solid #555555; padding: 5px; } "
                "QComboBox QAbstractItemView { background-color: #404040; color: #ffffff; selection-background-color: #2E7D9B; } "
                "QTextEdit { background-color: #404040; color: #ffffff; border: 1px solid #555555; } "
                "QPlainTextEdit { background-color: #404040; color: #ffffff; border: 1px solid #555555; } "
                "QLabel { color: #ffffff; } "
                "QFrame { background-color: #333333; border: none; } "
                "QScrollArea { background-color: #2b2b2b; border: none; } "
                "QCheckBox { color: #ffffff; } "
                "QCheckBox::indicator { width:44px; height:24px; border-radius:12px; } "
                "QCheckBox::indicator:unchecked { background: #505050; border: 1px solid #666666; } "
                "QCheckBox::indicator:checked { background: #2E7D9B; border: 1px solid #225962; } "
                "QTableWidget { background-color: #404040; color: #ffffff; gridline-color: #555555; } "
                "QTableWidget::item { background-color: #404040; color: #ffffff; } "
                "QTableWidget::item:selected { background-color: #2E7D9B; color: #ffffff; } "
                "QHeaderView::section { background-color: #505050; color: #ffffff; border: 1px solid #555555; padding: 4px; } "
                "QListWidget { background-color: #404040; color: #ffffff; } "
                "QListWidget::item { background-color: #404040; color: #ffffff; } "
                "QListWidget::item:selected { background-color: #2E7D9B; color: #ffffff; } "
                "QScrollBar:vertical { background: #2b2b2b; width: 12px; border-radius: 6px; } "
                "QScrollBar::handle:vertical { background: #505050; border-radius: 6px; min-height: 20px; } "
                "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; } "
                "QScrollBar:horizontal { background: #2b2b2b; height: 12px; border-radius: 6px; } "
                "QScrollBar::handle:horizontal { background: #505050; border-radius: 6px; min-width: 20px; } "
                "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
                + focus_styles
            )
            # 更新侧边栏样式
            self.sidebar.setStyleSheet("QWidget { background-color: #333333; } QPushButton { border: none; background: #404040; color: #ffffff; } QPushButton:checked { background: #2E7D9B; font-weight: 600; }" + sidebar_focus)
        elif theme == "经典":
            # 暂时默认为浅色
            stylesheet = ("QWidget:focus { outline: none; }" + focus_styles)
            self.sidebar.setStyleSheet("" + sidebar_focus)
        else:  # 浅色
            stylesheet = (
                "QWidget:focus { outline: none; } "
                "QCheckBox::indicator { width:44px; height:24px; border-radius:12px; } "
                "QCheckBox::indicator:unchecked { background: #e6e6e6; border: 1px solid #d0d0d0; } "
                "QCheckBox::indicator:checked { background: #2E7D9B; border: 1px solid #225962; }"
                + focus_styles
            )
            self.sidebar.setStyleSheet("QWidget { background-color: #f0f0f0; } QPushButton { border: none; background: #f5f5f5; } QPushButton:checked { background: #e8e8e8; font-weight: 600; }" + sidebar_focus)
        
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)

    def _apply_language(self, lang_code):
        """应用翻译：加载对应的 .qm 文件"""
        import basic_def
        app = QApplication.instance()
        # 移除旧翻译器
        if self.translator:
            app.removeTranslator(self.translator)
        # 翻译文件路径
        i18n_dir = os.path.join(basic_def.SCRIPT_DIR, '_internal/i18n')
        qm_path = os.path.join(i18n_dir, f'app_{lang_code}.qm')
        if os.path.exists(qm_path):
            self.translator.load(qm_path)
            app.installTranslator(self.translator)
        else:
            # 如果没有对应的翻译文件，不加载翻译（使用源码中的默认中文）
            pass

    def switch_language(self, lang_code):
        """切换语言并重新显示界面"""
        import basic_def
        basic_def.language = lang_code
        basic_def.save_config()
        self._apply_language(lang_code)
        # 需要重建界面以刷新所有 tr() 字符串
        # 最简单的方式是重启应用
        def _restart_if_yes(yes):
            if not yes:
                return
            app = QApplication.instance()
            app.quit()
            # 重新启动
            python = sys.executable
            os.execl(python, python, *sys.argv)

        self.confirm_card(
            'question',
            self.tr("重启应用"),
            self.tr("语言已更改，需要重启应用才能生效。是否立即重启？"),
            default_yes=True,
            on_result=_restart_if_yes,
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
