from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFrame
)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import Qt


class AddGameWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI界面"""
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(15)
        
        # ========== 左侧：开始添加 ==========
        left_widget = QFrame()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(20, 20, 20, 20)
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
        left_widget.setStyleSheet("QFrame { border-right: 1px solid #e0e0e0; }")
        
        # ========== 右侧：运作扫描器 ==========
        right_widget = QFrame()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)
        
        # 标题
        right_title = QLabel("运作扫描器")
        right_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        right_layout.addWidget(right_title)
        
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
        right_desc3 = QLabel("扫描器不会扫描忽略列表的游戏。\n你可以在右侧某单编辑运作的扫描器，运作的扫描器：")
        right_desc3.setFont(QFont("Segoe UI", 12))
        right_desc3.setWordWrap(True)
        right_layout.addWidget(right_desc3)
        
        # 扫描器列表
        scanner_list = QListWidget()
        scanner_list.setMinimumHeight(120)
        scanner_list.setStyleSheet(
            "QListWidget {"
            "  border: 2px solid #2E7D9B;"
            "  border-radius: 5px;"
            "  padding: 5px;"
            "  background-color: #f9f9f9;"
            "}"
            "QListWidget::item:selected {"
            "  background-color: #2E7D9B;"
            "  color: white;"
            "}"
        )
        # 为空列表添加占位符
        placeholder_item = QListWidgetItem("（未选择任何扫描器）")
        placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemIsSelectable)
        scanner_list.addItem(placeholder_item)
        
        right_layout.addWidget(scanner_list)
        
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
