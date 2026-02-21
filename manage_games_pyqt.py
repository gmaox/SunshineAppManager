import os
import sys
import json
import re, winreg
import uuid
from functools import partial
from PyQt5 import QtWidgets, QtGui, QtCore

THUMB_SIZE = (80, 120)
IMAGE_CACHE = {}


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

def get_thumb(path):
    if not path:
        return None
    key = os.path.abspath(path)
    if key in IMAGE_CACHE:
        return IMAGE_CACHE[key]
    try:
        from PIL import Image
        img = Image.open(key)
        img.thumbnail(THUMB_SIZE)
        data = img.tobytes("raw", "RGBA") if img.mode == 'RGBA' else None
        qimg = None
        if data:
            qimg = QtGui.QImage(data, img.width, img.height, QtGui.QImage.Format_RGBA8888)
        else:
            img = img.convert('RGBA')
            data = img.tobytes('raw', 'RGBA')
            qimg = QtGui.QImage(data, img.width, img.height, QtGui.QImage.Format_RGBA8888)
        pix = QtGui.QPixmap.fromImage(qimg)
        IMAGE_CACHE[key] = pix
        return pix
    except Exception:
        return None


class EditGameCard(QtWidgets.QFrame):
    def __init__(self, entry, parent, apps_json, apps_json_path, refresh_cb, manage_window=None):
        super().__init__(parent)
        self.entry = entry
        self.apps_json = apps_json
        self.apps_json_path = apps_json_path
        self.refresh_cb = refresh_cb
        self.manage_window = manage_window  # ManageWindow的引用
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setStyleSheet('background:white;')
        self.init_ui()

    def init_ui(self):
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(8, 8, 8, 8)
        # cover
        self.cover_lbl = QtWidgets.QLabel('无封面')
        self.cover_lbl.setFixedSize(80, 120)
        self.cover_lbl.setStyleSheet('background:#333;color:white')
        self.cover_lbl.setAlignment(QtCore.Qt.AlignCenter)
        h.addWidget(self.cover_lbl)

        # info
        v = QtWidgets.QVBoxLayout()
        name = self.entry.get('name', '未知游戏')
        name = re.sub(r'^\d{2} ', '', name)
        self.name_lbl = QtWidgets.QLabel(name)
        font = self.name_lbl.font()
        font.setBold(True)
        self.name_lbl.setFont(font)
        v.addWidget(self.name_lbl)

        cmd = self.entry.get('cmd', '')
        # 不截断命令行路径，允许 QLabel 自动换行显示完整内容
        self.cmd_lbl = QtWidgets.QLabel('路径: ' + cmd)
        self.cmd_lbl.setStyleSheet('color:#666')
        self.cmd_lbl.setWordWrap(True)
        v.addWidget(self.cmd_lbl)
        v.addStretch()

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch()
        self.edit_btn = QtWidgets.QPushButton('编辑')
        self.del_btn = QtWidgets.QPushButton('删除')
        self.cover_btn = QtWidgets.QPushButton('更换封面')
        for btn in (self.del_btn, self.edit_btn, self.cover_btn):
            btn.setFixedHeight(26)
            btns.addWidget(btn)

        v.addLayout(btns)
        h.addLayout(v)

        # load cover
        cover_filename = self.entry.get('image-path')
        if cover_filename:
            cover_full = os.path.join(APP_INSTALL_PATH, 'config', 'covers', cover_filename)
            pix = get_thumb(cover_full)
            if pix:
                self.cover_lbl.setPixmap(pix.scaled(80, 120, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

        # signals
        self.del_btn.clicked.connect(self.on_delete)
        self.edit_btn.clicked.connect(self.on_edit)
        self.cover_btn.clicked.connect(self.on_change_cover)

    def on_delete(self):
        name = self.entry.get('name', '未知游戏')
        if QtWidgets.QMessageBox.question(self, '确认删除', f"确定要删除游戏 '{name}' 吗？") != QtWidgets.QMessageBox.Yes:
            return
        for i, e in enumerate(self.apps_json.get('apps', [])):
            if e is self.entry or e == self.entry:
                self.apps_json['apps'].pop(i)
                save_apps_json(self.apps_json, self.apps_json_path)
                self.refresh_cb()
                return

    def on_edit(self):
        """点击编辑按钮时，在右侧面板显示编辑界面而不是弹出对话框"""
        if self.manage_window:
            self.manage_window.show_edit_panel(self.entry)
        else:
            pass
    def _save_edit_legacy(self, name, cmd, dlg):
        """降级的保存编辑方法（用于弹出对话框模式）"""
        self.entry['name'] = name
        if cmd:
            self.entry['cmd'] = cmd
        else:
            self.entry.pop('cmd', None)
        save_apps_json(self.apps_json, self.apps_json_path)
        dlg.accept()
        self.refresh_cb()

    def _save_edit(self, name, cmd, dlg):
        self.entry['name'] = name
        if cmd:
            self.entry['cmd'] = cmd
        else:
            self.entry.pop('cmd', None)
        save_apps_json(self.apps_json, self.apps_json_path)
        dlg.accept()
        self.refresh_cb()

    def on_change_cover(self):
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(self, '选择封面图片', '', '图片 (*.jpg *.jpeg *.png *.bmp)')
        if not fp:
            return
        covers_dir = os.path.join(APP_INSTALL_PATH, 'config', 'covers')
        os.makedirs(covers_dir, exist_ok=True)
        try:
            from PIL import Image
            img = Image.open(fp)
            img = img.resize((600, 900), Image.LANCZOS)
            newname = f"custom_{uuid.uuid4().hex[:8]}.jpg"
            full = os.path.join(covers_dir, newname)
            img.save(full, 'JPEG', quality=95)
            self.entry['image-path'] = newname
            save_apps_json(self.apps_json, self.apps_json_path)
            IMAGE_CACHE.clear()  # clear cache so new thumb used
            self.refresh_cb()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, '错误', f'更换封面失败: {e}')


class ManageWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('管理现有游戏')
        self.resize(799, 600)
        self.apps_json_path = os.path.join(APP_INSTALL_PATH, 'config', 'apps.json')
        os.makedirs(os.path.dirname(self.apps_json_path), exist_ok=True)
        if not os.path.exists(self.apps_json_path):
            save_apps_json({"env": "", "apps": []}, self.apps_json_path)
        self.apps_json = load_apps_json(self.apps_json_path)
        self.current_edit_entry = None  # 当前编辑的条目
        self._setup_ui()
        self._debounce_timer = QtCore.QTimer(singleShot=True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._do_refresh)

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        # search row
        h = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText('搜索游戏...')
        self.search_edit.textChanged.connect(self._debounce_refresh)
        self.search_edit.setFixedHeight(30)
        h.addWidget(self.search_edit)
        self.search_btn = QtWidgets.QPushButton('搜索')
        self.search_btn.clicked.connect(self._debounce_refresh)
        # 按钮尺寸调整：固定高度，宽度合理
        self.search_btn.setFixedHeight(30)
        self.search_btn.setFixedWidth(80)
        h.addWidget(self.search_btn)
        main_layout.addLayout(h)

        self.path_lbl = QtWidgets.QLabel('')
        self.path_lbl.setStyleSheet('color:gray')
        main_layout.addWidget(self.path_lbl)

        # 左右分割布局
        h_split = QtWidgets.QHBoxLayout()
        
        # 左侧：游戏列表
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        # 禁用横向滚动条，避免横向滚动导致卡片错位
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.container = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.container)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setSpacing(10)
        self.scroll.setWidget(self.container)
        left_layout.addWidget(self.scroll)
        
        # 底部按钮
        bottom = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton('刷新游戏列表')
        refresh_btn.clicked.connect(self.reload_apps)
        # 按钮尺寸调整：固定高度，宽度合理
        refresh_btn.setFixedHeight(40)
        refresh_btn.setFixedWidth(120)
        bottom.addWidget(refresh_btn)
        bottom.addStretch()
        left_layout.addLayout(bottom)
        
        h_split.addWidget(left_container, 3)  # 左侧占60%
        
        # 右侧：编辑面板
        self.edit_panel = self._create_edit_panel()
        self.edit_panel.setVisible(False)
        h_split.addWidget(self.edit_panel, 2)  # 右侧占40%
        
        main_layout.addLayout(h_split)

        self.path_lbl.setText(f'当前加载路径: {self.apps_json_path}')
        # 安装容器的事件过滤器以响应子控件尺寸变化
        self.container.installEventFilter(self)
        self._do_refresh()
    
    def _create_edit_panel(self):
        """创建右侧编辑面板"""
        panel = QtWidgets.QFrame()
        panel.setStyleSheet('background:#f5f5f5;border-left:1px solid #ddd')
        panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)
        
        title = QtWidgets.QLabel('编辑游戏信息')
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        title.setFont(font)
        layout.addWidget(title)
        
        layout.addWidget(QtWidgets.QLabel('游戏名称:'))
        self.edit_name = QtWidgets.QLineEdit()
        layout.addWidget(self.edit_name)
        
        layout.addWidget(QtWidgets.QLabel('命令行/路径:'))
        self.edit_cmd = QtWidgets.QLineEdit()
        self.edit_cmd.setMinimumHeight(60)
        layout.addWidget(self.edit_cmd)
        
        layout.addStretch()
        
        btns = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton('保存')
        save_btn.setFixedHeight(26)
        save_btn.setFixedWidth(80)
        cancel_btn = QtWidgets.QPushButton('取消')
        cancel_btn.setFixedHeight(26)
        cancel_btn.setFixedWidth(80)
        save_btn.clicked.connect(self._save_edit)
        cancel_btn.clicked.connect(self._close_edit_panel)
        btns.addStretch()
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
        
        return panel
    
    def show_edit_panel(self, entry):
        """显示编辑面板，编辑指定的条目"""
        self.current_edit_entry = entry
        self.edit_name.setText(entry.get('name', ''))
        self.edit_cmd.setText(entry.get('cmd', ''))
        self.edit_panel.setVisible(True)
    
    def _save_edit(self):
        """保存编辑结果"""
        if self.current_edit_entry:
            self.current_edit_entry['name'] = self.edit_name.text()
            cmd = self.edit_cmd.text()
            if cmd:
                self.current_edit_entry['cmd'] = cmd
            else:
                self.current_edit_entry.pop('cmd', None)
            save_apps_json(self.apps_json, self.apps_json_path)
            self._close_edit_panel()
    
    def _close_edit_panel(self):
        """关闭编辑面板"""
        self.edit_panel.setVisible(False)
        self.current_edit_entry = None
        self._debounce_refresh()
    def resizeEvent(self, event):
        # 窗口尺寸变化时防抖刷新布局
        self._debounce_refresh()
        return super().resizeEvent(event)

    def eventFilter(self, watched, event):
        # 监听容器本身的 Resize 事件，保证内部控件变化也触发重绘
        if watched is self.container and event.type() == QtCore.QEvent.Resize:
            self._debounce_refresh()
        return super().eventFilter(watched, event)

    def _debounce_refresh(self):
        self._debounce_timer.start()

    def _do_refresh(self):
        # clear grid
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.setParent(None)
        term = self.search_edit.text().strip().lower()
        apps = [a for a in self.apps_json.get('apps', []) if (not term or term in a.get('name','').lower())]
        if not apps:
            label = QtWidgets.QLabel('没有找到游戏条目')
            self.grid.addWidget(label, 0, 0)
            return
        width = max(300, self.width())
        if width < 400:
            cols = 1
        elif width < 800:
            cols = 2
        elif width < 1200:
            cols = 3
        else:
            cols = 4
        # 确保网格列有伸缩，使卡片水平填充且不触发横向滚动
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

        viewport_width = max(300, self.scroll.viewport().width())
        # 卡片最大宽度按列数平均分配，减去布局间距（近似）
        max_card_w = max(240, (viewport_width - (self.grid.horizontalSpacing() * (cols + 1))) // cols)

        for idx, entry in enumerate(apps):
            card = EditGameCard(entry, self, self.apps_json, self.apps_json_path, self._debounce_refresh, manage_window=self)
            # 使卡片可水平扩展并设置最大宽度以避免横向扩展
            card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            card.setMaximumWidth(max_card_w)
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(card, row, col)

        # 保证容器至少与视口同宽，防止内容比视口窄时触发奇怪布局
        self.container.setMinimumWidth(viewport_width)
        QtCore.QTimer.singleShot(0, lambda: self.container.updateGeometry())

    def reload_apps(self):
        """从磁盘重新读取 apps.json 并刷新显示。"""
        # 重新加载文件（load_apps_json 内部会处理编码和错误）
        self.apps_json = load_apps_json(self.apps_json_path)
        # 触发防抖刷新以更新界面
        self._debounce_refresh()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    w = ManageWindow()
    w.show()
    sys.exit(app.exec_())
