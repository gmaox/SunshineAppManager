from PyQt5.QtGui import QFont, QColor, QTextCursor, QTextCharFormat
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
import sys
from io import StringIO

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QHBoxLayout, QStackedWidget, QPushButton, QButtonGroup, QSizePolicy,
    QTextEdit
)

# 嵌入管理界面 (确保 manage_games_pyqt.py 与本文件位于同一目录)
try:
    from manage_games import ManageWindow
except Exception:
    ManageWindow = None


# 日志信号发射器
class LogSignalEmitter(QObject):
    log_signal = pyqtSignal(str, bool)  # 信号：(文本, 是否为错误)


# 输出重定向器
class StreamRedirector:
    def __init__(self, log_emitter, is_error=False):
        self.log_emitter = log_emitter
        self.is_error = is_error
        self.buffer = ""

    def write(self, text):
        if text:
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


# 日志标签页
class LogTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
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
        
        # 创建或获取通知标签
        if not hasattr(self.parent_window, 'error_notification'):
            notification = QLabel(self.parent_window)
            notification.setStyleSheet(
                "background-color: #ffcccc; border: 2px solid #ff0000; "
                "padding: 10px; border-radius: 5px; font-weight: bold; color: #cc0000;"
            )
            notification.setFont(QFont("Segoe UI", 10))
            notification.setWordWrap(True)
            notification.setMaximumWidth(300)
            self.parent_window.error_notification = notification
            
            # 创建隐藏定时器
            if not hasattr(self.parent_window, 'notification_timer'):
                self.parent_window.notification_timer = QTimer(self.parent_window)
                self.parent_window.notification_timer.timeout.connect(
                    lambda: self.parent_window.error_notification.hide()
                )
        
        notification = self.parent_window.error_notification
        
        # 截断过长的错误信息
        display_text = error_text[:100] + "..." if len(error_text) > 100 else error_text
        notification.setText(f"❌ 错误：{display_text}")
        
        # 计算右下角位置
        geometry = self.parent_window.geometry()
        notification_width = notification.sizeHint().width() + 20
        notification_height = notification.sizeHint().height() + 20
        
        pos_x = geometry.x() + geometry.width() - notification_width - 15
        pos_y = geometry.y() + geometry.height() - notification_height - 15
        
        notification.setGeometry(pos_x, pos_y, notification_width, notification_height)
        notification.show()
        
        # 3秒后隐藏通知
        self.parent_window.notification_timer.stop()
        self.parent_window.notification_timer.start(3000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pytk 标签页示例")
        self.setGeometry(100, 100, 900, 520)

        tab_names = [
            '添加游戏', '浏览游戏', '日志', '设置',
            '忽略列表', '添加扫描器', '扫描器管理'
        ]

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
        stacked = QStackedWidget()
        # 去掉堆栈自身的内容边距
        stacked.setContentsMargins(0, 0, 0, 0)

        for i, name in enumerate(tab_names):
            # 页面
            page = QWidget()
            v = QVBoxLayout()
            # 减少页面内部边距，避免内容被推离右侧
            v.setContentsMargins(6, 6, 6, 6)
            v.setSpacing(6)
            
            # 根据标签页索引创建不同内容
            if i == 1 and ManageWindow is not None:
                # 浏览游戏 - 嵌入管理窗口
                manage_widget = ManageWindow()
                # 作为内嵌控件时去掉独立窗口的最小尺寸限制
                manage_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(manage_widget)
            elif i == 2:
                # 日志标签页
                log_tab = LogTab(self)
                v.addWidget(log_tab)
            else:
                # 其他标签页 - 显示占位符
                label = QLabel(f"这是标签页{i+1}的内容")
                label.setAlignment(Qt.AlignCenter)
                label.setFont(QFont("Segoe UI", 14))
                v.addStretch()
                v.addWidget(label)
                v.addStretch()
            
            page.setLayout(v)
            stacked.addWidget(page)

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
            stacked.setCurrentIndex(id_)

        button_group.idClicked.connect(on_button_clicked)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(stacked)

        self.setCentralWidget(main_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    print("这是一个普通日志输出示例。")
    window.show()
    sys.exit(app.exec_())