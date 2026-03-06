from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QComboBox, QLineEdit, QFileDialog, QFrame, QSpacerItem, QSizePolicy,
    QScrollArea
)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt
import os
import basic_def


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """初始化设置页面UI"""
        # 从 basic_def 读取配置
        try:
            basic_def.load_config()
        except Exception:
            pass
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        # 创建内容容器
        content_widget = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # ========== 设置区域 ==========
        settings_frame = QFrame()
        settings_layout = QVBoxLayout()
        settings_layout.setContentsMargins(15, 15, 15, 15)
        settings_layout.setSpacing(20)
        
        # 标题
        settings_title = QLabel("设置")
        settings_title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        settings_layout.addWidget(settings_title)
        
        # 1. 开关示例（完成后关闭）
        enable_notify_layout = QHBoxLayout()
        enable_notify_label = QLabel("完成后关闭程序：")
        enable_notify_label.setFont(QFont("Segoe UI", 12))
        self.enable_notify_checkbox = QCheckBox()
        self.enable_notify_checkbox.setChecked(basic_def.close_after_completion)
        # 现代开关样式（视觉为滑动开关）
        self.enable_notify_checkbox.setStyleSheet(
            "QCheckBox::indicator { width:44px; height:24px; border-radius:12px; }"
            "QCheckBox::indicator:unchecked { background: #e6e6e6; border: 1px solid #d0d0d0; }"
            "QCheckBox::indicator:checked { background: #2E7D9B; border: 1px solid #225962; }"
        )
        enable_notify_layout.addWidget(enable_notify_label)
        enable_notify_layout.addWidget(self.enable_notify_checkbox)
        enable_notify_layout.addStretch()
        settings_layout.addLayout(enable_notify_layout)
        
        # 2. 开关示例（伪排序）
        auto_save_layout = QHBoxLayout()
        auto_save_label = QLabel("启用伪排序：")
        auto_save_label.setFont(QFont("Segoe UI", 12))
        self.auto_save_checkbox = QCheckBox()
        self.auto_save_checkbox.setChecked(basic_def.pseudo_sorting_enabled)
        self.auto_save_checkbox.setStyleSheet(
            "QCheckBox::indicator { width:44px; height:24px; border-radius:12px; }"
            "QCheckBox::indicator:unchecked { background: #e6e6e6; border: 1px solid #d0d0d0; }"
            "QCheckBox::indicator:checked { background: #2E7D9B; border: 1px solid #225962; }"
        )
        auto_save_layout.addWidget(auto_save_label)
        auto_save_layout.addWidget(self.auto_save_checkbox)
        auto_save_layout.addStretch()
        settings_layout.addLayout(auto_save_layout)
        # 3. 自动删除不在工作目录中的条目（默认关闭）
        orphan_cleanup_layout = QHBoxLayout()
        orphan_cleanup_label = QLabel("自动删除孤立条目：")
        orphan_cleanup_label.setFont(QFont("Segoe UI", 12))
        self.orphan_cleanup_checkbox = QCheckBox()
        self.orphan_cleanup_checkbox.setChecked(basic_def.auto_delete_orphaned_entries)
        self.orphan_cleanup_checkbox.setStyleSheet(
            "QCheckBox::indicator { width:44px; height:24px; border-radius:12px; }"
            "QCheckBox::indicator:unchecked { background: #e6e6e6; border: 1px solid #d0d0d0; }"
            "QCheckBox::indicator:checked { background: #2E7D9B; border: 1px solid #225962; }"
        )
        orphan_cleanup_layout.addWidget(orphan_cleanup_label)
        orphan_cleanup_layout.addWidget(self.orphan_cleanup_checkbox)
        orphan_cleanup_layout.addStretch()
        settings_layout.addLayout(orphan_cleanup_layout)
        
        # 3. 文件选择器（工作路径）
        work_path_layout = QHBoxLayout()
        work_path_label = QLabel("工作路径：")
        work_path_label.setFont(QFont("Segoe UI", 12))
        self.work_path_input = QLineEdit()
        self.work_path_input.setPlaceholderText("选择工作路径...")
        self.work_path_input.setReadOnly(True)
        self.work_path_input.setStyleSheet("QLineEdit { border: none; background-color: #ffffff; padding:6px; }")
        # 显示当前配置中的工作路径
        try:
            if getattr(basic_def, 'folder', None):
                self.work_path_input.setText(os.path.normpath(basic_def.folder))
        except Exception:
            pass

        work_path_btn = QPushButton("浏览")
        work_path_btn.setFixedWidth(100)
        work_path_btn.setFixedHeight(34)
        work_path_btn.setStyleSheet(
            "QPushButton{ background-color:#2E7D9B; color:white; border:none; border-radius:6px; padding:6px 12px;}"
            "QPushButton:hover{ background-color:#256070;}"
        )
        work_path_layout.addWidget(work_path_label)
        work_path_layout.addWidget(self.work_path_input)
        work_path_layout.addWidget(work_path_btn)
        settings_layout.addLayout(work_path_layout)
        
        # 4. 文件选择器（配置文件）
        config_path_layout = QHBoxLayout()
        config_path_label = QLabel("配置文件：")
        config_path_label.setFont(QFont("Segoe UI", 12))
        self.config_path_input = QLineEdit()
        self.config_path_input.setPlaceholderText("选择配置文件...")
        self.config_path_input.setReadOnly(True)
        self.config_path_input.setStyleSheet("QLineEdit { border: none; color: #666666; background-color: #f5f5f5; padding:6px; }")
        # 显示当前 config.ini 路径
        try:
            self.config_path_input.setText(os.path.join(basic_def.APP_INSTALL_PATH, 'config', 'apps.json'))
        except Exception:
            pass

        config_path_layout.addWidget(config_path_label)
        config_path_layout.addWidget(self.config_path_input)
        settings_layout.addLayout(config_path_layout)
        
        # 5. 下拉列表（语言）
        language_layout = QHBoxLayout()
        language_label = QLabel("语言：")
        language_label.setFont(QFont("Segoe UI", 12))
        language_combo = QComboBox()
        language_combo.addItems(["中文", "English"])
        language_combo.setCurrentIndex(0)
        language_combo.setMinimumHeight(34)
        language_combo.setFont(QFont("Segoe UI", 12))
        language_combo.setStyleSheet(
            "QComboBox{ padding:6px 10px; border-radius:6px; border:1px solid #d0d0d0; background:white; }"
            "QComboBox QAbstractItemView{ selection-background-color:#2E7D9B; }"
        )
        language_layout.addWidget(language_label)
        language_layout.addWidget(language_combo)
        language_layout.addStretch()
        settings_layout.addLayout(language_layout)
        
        # 6. 下拉列表（主题）
        theme_layout = QHBoxLayout()
        theme_label = QLabel("主题：")
        theme_label.setFont(QFont("Segoe UI", 12))
        theme_combo = QComboBox()
        theme_combo.addItems(["浅色", "深色", "自动"])
        theme_combo.setCurrentIndex(0)
        theme_combo.setMinimumHeight(34)
        theme_combo.setFont(QFont("Segoe UI", 12))
        theme_combo.setStyleSheet(
            "QComboBox{ padding:6px 10px; border-radius:6px; border:1px solid #d0d0d0; background:white; }"
            "QComboBox QAbstractItemView{ selection-background-color:#2E7D9B; }"
        )
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(theme_combo)
        theme_layout.addStretch()
        settings_layout.addLayout(theme_layout)
        
        
        settings_frame.setLayout(settings_layout)
        # 移除边框以去掉顶部小灰色圆角装饰，保留背景色
        settings_frame.setStyleSheet(
            "QFrame { border: none; background-color: #fafafa; }"
        )
        
        content_layout.addWidget(settings_frame)
        
        # 添加弹性间隔，将"关于"部分推到底部
        content_layout.addStretch()
        
        # ========== 关于部分 ==========
        about_frame = QFrame()
        about_layout = QVBoxLayout()
        about_layout.setContentsMargins(15, 15, 15, 15)
        about_layout.setSpacing(10)
        
        # 关于标题
        about_title = QLabel("关于 Sunshine App Manager")
        about_title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        about_layout.addWidget(about_title)
        
        # 关于文本
        about_text = QLabel(
            "该软件一个辅助工具，旨在简化将应用程序和游戏添加到 Sunshine 的过程。\n\n"

            "项目开源地址：https://github.com/gmaox/QuickStreamAppAdd"
        )
        about_text.setFont(QFont("Segoe UI", 10))
        about_text.setWordWrap(True)
        about_layout.addWidget(about_text)
        
        about_frame.setLayout(about_layout)
        about_frame.setStyleSheet(
            "QFrame { border: 1px solid #e0e0e0; border-radius: 5px; background-color: #f0f5ff; }"
        )
        
        content_layout.addWidget(about_frame)
        
        # 设置内容容器到滚动区域
        content_widget.setLayout(content_layout)
        scroll_area.setWidget(content_widget)
        
        # 将滚动区域添加到主布局
        main_layout.addWidget(scroll_area)
        
        self.setLayout(main_layout)

        # 连接信号并初始化状态
        self.work_path_btn = work_path_btn
        self.init_signals()

    def init_signals(self):
        try:
            self.enable_notify_checkbox.stateChanged.connect(self.on_close_after_changed)
        except Exception:
            pass
        try:
            self.auto_save_checkbox.stateChanged.connect(self.on_pseudo_sorting_changed)
        except Exception:
            pass
        try:
            self.orphan_cleanup_checkbox.stateChanged.connect(self.on_orphan_cleanup_changed)
        except Exception:
            pass
        try:
            self.work_path_btn.clicked.connect(self.on_browse_work_path)
        except Exception:
            pass

    def on_close_after_changed(self, state):
        # state: 0 or 2
        try:
            basic_def.close_after_completion = bool(state)
            basic_def.save_config()
        except Exception as e:
            print(f"保存 close_after_completion 失败: {e}")

    def on_pseudo_sorting_changed(self, state):
        try:
            basic_def.pseudo_sorting_enabled = bool(state)
            basic_def.save_config()
        except Exception as e:
            print(f"保存 pseudo_sorting_enabled 失败: {e}")

    def on_orphan_cleanup_changed(self, state):
        try:
            basic_def.auto_delete_orphaned_entries = bool(state)
            basic_def.save_config()
        except Exception as e:
            print(f"保存 auto_delete_orphaned_entries 失败: {e}")

    def on_browse_work_path(self):
        try:
            dirname = QFileDialog.getExistingDirectory(self, "选择工作路径", basic_def.folder or os.path.expanduser("~"))
            if dirname:
                dirname = os.path.normpath(dirname).replace('\\', '/')
                self.work_path_input.setText(dirname)
                basic_def.folder = dirname
                basic_def.folder_selected = dirname
                if not os.path.isdir(dirname):
                    os.makedirs(dirname, exist_ok=True)
                basic_def.save_config()
        except Exception as e:
            print(f"选择工作路径失败: {e}")