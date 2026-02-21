from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
import sys

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QHBoxLayout, QStackedWidget, QPushButton, QButtonGroup, QSizePolicy
)

# 嵌入管理界面 (确保 manage_games_pyqt.py 与本文件位于同一目录)
try:
    from manage_games_pyqt import ManageWindow
except Exception:
    ManageWindow = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pytk 标签页示例")
        self.setGeometry(100, 100, 900, 520)

        tab_names = [
            '添加游戏', '浏览游戏', '日志', '设置',
            '忽略列表', '添加扫描器', '扫描器管理'
        ]
        tab_contents = [
            "这是标签页1的内容",
            "这是标签页2的内容",
            "这是标签页3的内容",
            "这是标签页4的内容",
            "这是标签页5的内容",
            "这是标签页6的内容",
            "这是标签页7的内容"
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

        for i, (name, content) in enumerate(zip(tab_names, tab_contents)):
            # 页面
            page = QWidget()
            v = QVBoxLayout()
            # 减少页面内部边距，避免内容被推离右侧
            v.setContentsMargins(6, 6, 6, 6)
            v.setSpacing(6)
            # 如果是第二个标签（浏览游戏）且 ManageWindow 可用，嵌入管理窗口
            if i == 1 and ManageWindow is not None:
                manage_widget = ManageWindow()
                # 作为内嵌控件时去掉独立窗口的最小尺寸限制
                manage_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                v.addWidget(manage_widget)
            else:
                label = QLabel(content)
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
    window.show()
    sys.exit(app.exec_())