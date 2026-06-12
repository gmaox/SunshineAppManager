import os
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from basic_def import config, save_config


class IgnoreManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        ignored_apps_str = config.get('Settings', 'ignored_apps', fallback='[]')
        try:
            self.ignored_apps = json.loads(ignored_apps_str)
        except json.JSONDecodeError:
            self.ignored_apps = []
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题
        title = QtWidgets.QLabel(self.tr("忽略列表管理"))
        title.setFont(QtGui.QFont('Microsoft YaHei', 14, QtGui.QFont.Bold))
        layout.addWidget(title)

        # 说明
        desc = QtWidgets.QLabel(self.tr("在此管理被忽略的应用列表。这些应用在下次扫描时将被自动跳过。"))
        desc.setWordWrap(True)
        desc.setStyleSheet('color: #666;')
        layout.addWidget(desc)

        # 列表视图
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self.list_widget)

        # 按钮区域
        button_layout = QtWidgets.QHBoxLayout()

        self.add_btn = QtWidgets.QPushButton(self.tr("添加"))
        self.add_btn.clicked.connect(self._add_ignored_app)
        button_layout.addWidget(self.add_btn)

        self.remove_btn = QtWidgets.QPushButton(self.tr("删除选中"))
        self.remove_btn.clicked.connect(self._remove_selected)
        button_layout.addWidget(self.remove_btn)

        self.clear_btn = QtWidgets.QPushButton(self.tr("清空列表"))
        self.clear_btn.clicked.connect(self._clear_all)
        button_layout.addWidget(self.clear_btn)

        button_layout.addStretch()

        self.refresh_btn = QtWidgets.QPushButton(self.tr("刷新"))
        self.refresh_btn.clicked.connect(self._refresh_list)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

        # 状态标签
        self.status_label = QtWidgets.QLabel('')
        self.status_label.setStyleSheet('color: #666;')
        layout.addWidget(self.status_label)

    def _refresh_list(self):
        self.list_widget.clear()
        ignored_apps_str = config.get('Settings', 'ignored_apps', fallback='[]')
        try:
            self.ignored_apps = json.loads(ignored_apps_str)
        except json.JSONDecodeError:
            self.ignored_apps = []
        
        for app in self.ignored_apps:
            item = QtWidgets.QListWidgetItem()
            item.setText(app.get('name', 'Unknown') + ' - ' + app.get('path', ''))
            item.setData(QtCore.Qt.UserRole, app)
            self.list_widget.addItem(item)
        
        self.status_label.setText(self.tr("共 %1 个被忽略的应用").replace('%1', str(len(self.ignored_apps))))

    def _add_ignored_app(self):
        # 打开文件对话框选择应用
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("选择要忽略的应用"), '', self.tr("可执行文件 (*.exe);;所有文件 (*.*)")
        )
        if not file_path:
            return

        app_name = os.path.splitext(os.path.basename(file_path))[0]

        # 检查是否已存在
        for app in self.ignored_apps:
            if app.get('path') == file_path:
                QtWidgets.QMessageBox.information(self, self.tr("提示"), self.tr("该应用已在忽略列表中"))
                return

        # 添加到列表
        self.ignored_apps.append({
            'name': app_name,
            'path': file_path
        })

        self._save_config()
        self._refresh_list()
        QtWidgets.QMessageBox.information(self, self.tr("成功"), self.tr('已添加 "%1" 到忽略列表').replace('%1', app_name))

    def _remove_selected(self):
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, self.tr("提示"), self.tr("请先选择要删除的项目"))
            return

        reply = QtWidgets.QMessageBox.question(
            self, self.tr("确认删除"),
            self.tr("确定要删除选中的 %1 个项目吗？").replace('%1', str(len(selected_items))),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            for item in selected_items:
                app_data = item.data(QtCore.Qt.UserRole)
                if app_data in self.ignored_apps:
                    self.ignored_apps.remove(app_data)

            self._save_config()
            self._refresh_list()

    def _clear_all(self):
        if not self.ignored_apps:
            QtWidgets.QMessageBox.information(self, self.tr("提示"), self.tr("忽略列表为空"))
            return

        reply = QtWidgets.QMessageBox.question(
            self, self.tr("确认清空"),
            self.tr("确定要清空整个忽略列表吗？"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self.ignored_apps.clear()
            self._save_config()
            self._refresh_list()

    def _save_config(self):
        ignored_apps_str = json.dumps(self.ignored_apps, ensure_ascii=False)
        config.set('Settings', 'ignored_apps', ignored_apps_str)
        save_config()

    def get_ignored_paths(self):
        """获取被忽略的应用路径列表"""
        return [app.get('path') for app in self.ignored_apps if app.get('path')]