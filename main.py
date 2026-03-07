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

from PyQt5.QtGui import QFont, QColor, QTextCursor, QTextCharFormat
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPropertyAnimation, QEasingCurve, QRect, QParallelAnimationGroup
from io import StringIO

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QHBoxLayout, QStackedWidget, QPushButton, QButtonGroup, QSizePolicy,
    QTextEdit
)
from basic_def import initialize, load_config, _process_confirm_add_entries
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
    from scanner_add_page import ScannerAddPage
except Exception:
    ScannerAddPage = None

try:
    from scanner_manage_page import ScannerManagePage
except Exception:
    ScannerManagePage = None


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

        # 日志显示文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 10))
        self.log_text.setStyleSheet("background-color: #f5f5f5;")
        layout.addWidget(self.log_text)
        
        # 清空日志按钮
        button_layout = QHBoxLayout()
        clear_btn = QPushButton("清空日志")
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
        notification.text_label.setText(f"❌ 错误：{display_text}")
        
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
        notification.text_label.setText(f"✅ 成功：{display_text}")
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
        self.setWindowTitle("Sunshine App Manager v1.0")
        self.resize(900, 480)

        tab_names = [
            '添加游戏', '浏览游戏', '日志', '设置',
            '忽略列表', '添加扫描器', '扫描器管理'
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

        button_group = QButtonGroup(self)
        button_group.setExclusive(True)

        # 右侧页面区 (堆栈)
        self.stacked = QStackedWidget()
        # 去掉堆栈自身的内容边距
        self.stacked.setContentsMargins(0, 0, 0, 0)

        self.confirm_add_window = None  # 确认添加窗口引用
        self.confirm_add_page_index = None  # 确认添加窗口页面索引
        
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
            elif i == 5 and ScannerAddPage is not None:
                # 添加扫描器标签页
                scanner_add_widget = ScannerAddPage()
                scanner_add_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(scanner_add_widget)
            elif i == 6 and ScannerManagePage is not None:
                # 扫描器管理标签页
                scanner_manage_widget = ScannerManagePage()
                scanner_manage_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(scanner_manage_widget)
            else:
                # 其他标签页 - 显示占位符
                label = QLabel(f"这是标签页{i+1}的内容")
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
            btn.setStyleSheet(
                "QPushButton{border:none;background:#f5f5f5;}"
                "QPushButton:checked{background:#e8e8e8;font-weight:600;}"
            )
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

        button_group.idClicked.connect(on_button_clicked)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stacked)

        self.setCentralWidget(main_widget)
    
    def show_confirm_add_window(self, pending_entries, apps_json, apps_json_path, output_folder,
                                pseudo_sorting_enabled=False, close_after_completion=True):
        """显示确认添加窗口"""
        if ConfirmAddWindow is None:
            return
        
        # 如果之前的窗口存在，删除它
        if self.confirm_add_window is not None and self.confirm_add_page_index is not None:
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
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "错误", f"处理确认添加时出错: {e}")
    
    def _on_confirm_add_cancelled(self):
        """取消添加时的处理"""
        # 返回到上一个页面（如添加游戏页面）
        self.stacked.setCurrentIndex(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
