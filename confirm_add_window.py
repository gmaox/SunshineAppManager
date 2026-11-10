import os
import threading
import uuid
from io import BytesIO

from PyQt5 import QtCore, QtGui, QtWidgets

from basic_def import generate_covers_for_entries, config, save_config, restart_sunshine_after_add, load_config
from sgdb_cover_window import choose_cover_with_sgdb_qt
from main import find_main_window, _pick_file


def _cc(widget, card_type, title, message, on_result=None, yes_text=None, no_text=None, default_yes=False):
    """通过父级 MainWindow 的 confirm_card 统一显示卡片；找不到主窗口则回退 QMessageBox。"""
    mw = find_main_window(widget)
    if mw is not None:
        return mw.confirm_card(card_type, title, message, yes_text=yes_text, no_text=no_text,
                              default_yes=default_yes, on_result=on_result)
    from PyQt5.QtWidgets import QMessageBox
    if card_type == 'question':
        reply = QMessageBox.question(widget, title, message, QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.Yes if default_yes else QMessageBox.No)
        if on_result:
            on_result(reply == QMessageBox.Yes)
    else:
        fn = {'information': QMessageBox.information, 'warning': QMessageBox.warning,
              'critical': QMessageBox.critical}.get(card_type, QMessageBox.information)
        fn(widget, title, message)
        if on_result:
            on_result(True)
    return None

THUMB_SIZE = (80, 120)


class ConfirmGameCard(QtWidgets.QFrame):
    def __init__(self, entry, parent_window):
        super().__init__(parent_window)
        self.entry = entry
        self.parent_window = parent_window
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        # 背景由全局主题控制，深色模式下使用深色背景
        self._setup_ui()
        self.refresh_cover()

    def _setup_ui(self):
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(8, 8, 8, 8)

        self.cover_lbl = QtWidgets.QPushButton(self.tr("没有封面"))
        self.cover_lbl.setFixedSize(80, 120)
        # 继承全局主题背景，并补充 focus 样式以呼应其它按钮
        self.cover_lbl.setStyleSheet(
            "QPushButton {"
            "  background-color: #333;"
            "  color: white;"
            "  border: 2px solid transparent;"
            "  border-radius: 4px;"
            "  text-align: center;"
            "}"
            "QPushButton:focus {"
            "  background-color: #66ccff;"
            "  color: #003344;"
            "  border: 4px solid #66ccff;"
            "  outline: 2px solid #ffffff;"
            "  outline-offset: 2px;"
            "}"
        )
        self.cover_lbl.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.cover_lbl.setCursor(QtCore.Qt.PointingHandCursor)
        self.cover_lbl.clicked.connect(self.on_cover_click)
        h.addWidget(self.cover_lbl)

        v = QtWidgets.QVBoxLayout()

        self.name_lbl = QtWidgets.QLabel(self.entry.get('app_name', 'Unknown'))
        font = self.name_lbl.font()
        font.setBold(True)
        self.name_lbl.setFont(font)
        v.addWidget(self.name_lbl)

        self.path_lbl = QtWidgets.QLabel(self.tr("路径: ") + str(self.entry.get('target_path', '')))
        self.path_lbl.setStyleSheet('')
        self.path_lbl.setWordWrap(True)
        v.addWidget(self.path_lbl)
        v.addStretch()

        control = QtWidgets.QHBoxLayout()

        self.btn_container = QtWidgets.QWidget()
        btns = QtWidgets.QHBoxLayout(self.btn_container)
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(4)

        self.import_btn = QtWidgets.QPushButton(self.tr("导入封面"))
        self.import_btn.setFixedSize(90, 30)
        self.import_btn.clicked.connect(lambda: self.parent_window.on_import_cover(self.entry))
        btns.addWidget(self.import_btn)

        self.edit_btn = QtWidgets.QPushButton(self.tr("编辑"))
        self.edit_btn.setFixedSize(70, 30)
        self.edit_btn.clicked.connect(lambda: self.parent_window.show_edit_panel(self.entry))
        btns.addWidget(self.edit_btn)

        control.addWidget(self.btn_container)

        # 忽略按钮：仅在忽略模式下显示，点击即隐藏该游戏
        self.ignore_btn = QtWidgets.QPushButton(self.tr("忽略"))
        self.ignore_btn.setFixedHeight(30)
        self.ignore_btn.setVisible(False)
        self.ignore_btn.clicked.connect(lambda: self.parent_window.ignore_entry(self.entry))
        control.addWidget(self.ignore_btn)
        control.addStretch()

        v.addLayout(control)
        h.addLayout(v)

    def set_ignore_mode(self, ignore_mode):
        """忽略模式下隐藏其它操作按钮，只显示“忽略”按钮。"""
        self.btn_container.setVisible(not ignore_mode)
        self.ignore_btn.setVisible(ignore_mode)

    def refresh_text(self):
        self.name_lbl.setText(self.entry.get('app_name', 'Unknown'))
        self.path_lbl.setText(self.tr("路径: ") + str(self.entry.get('target_path', '')))

    def refresh_cover(self):
        cover_bytes = self.entry.get('cover_bytes')
        if not cover_bytes:
            self.cover_lbl.setIcon(QtGui.QIcon())
            self.cover_lbl.setText(self.tr("没有封面"))
            return

        pix = QtGui.QPixmap()
        if not pix.loadFromData(cover_bytes):
            self.cover_lbl.setIcon(QtGui.QIcon())
            self.cover_lbl.setText(self.tr("没有封面"))
            return

        scaled = pix.scaled(THUMB_SIZE[0], THUMB_SIZE[1], QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.cover_lbl.setIcon(QtGui.QIcon(scaled))
        self.cover_lbl.setIconSize(QtCore.QSize(THUMB_SIZE[0], THUMB_SIZE[1]))
        self.cover_lbl.setText('')

    def on_cover_click(self):
        """点击封面时使用 SGDB 选择封面"""
        self._change_cover_with_sgdb()

    def _change_cover_with_sgdb(self):
        """使用 SGDB 选择封面（内嵌在主窗口中）"""
        app_name = self.entry.get('app_name', 'Unknown')
        exe_path = self.entry.get('target_path', '')

        # 查找 MainWindow 以使用内嵌封面选择器
        main_window = self._find_main_window()
        if main_window is not None and hasattr(main_window, 'show_sgdb_cover_picker'):
            main_window.show_sgdb_cover_picker(
                app_name=app_name,
                exe_path=exe_path,
                on_result=self._on_sgdb_cover_result,
            )
        else:
            # 降级：使用模态对话框
            self._change_cover_with_sgdb_legacy(app_name, exe_path)

    def _find_main_window(self):
        """向上查找包含 show_sgdb_cover_picker 的主窗口"""
        w = self.parent_window
        while w is not None:
            if hasattr(w, 'show_sgdb_cover_picker'):
                return w
            w = w.parent()
        return None

    def _on_sgdb_cover_result(self, result_bytes, used_icon, sgdb_name, newname):
        """内嵌封面选择器回调"""
        if result_bytes:
            try:
                self.entry['cover_bytes'] = result_bytes
                self.entry['image-path'] = newname
                if sgdb_name:
                    self.entry['app_name'] = sgdb_name
                self.parent_window._refresh_entry_card(self.entry)
            except Exception as e:
                _cc(self, 'critical', 'Error', f'Failed to process SGDB cover: {e}')

    def _change_cover_with_sgdb_legacy(self, app_name, exe_path):
        """降级：使用模态对话框选择封面"""
        from basic_def import TEMP_COVERS_DIR
        os.makedirs(TEMP_COVERS_DIR, exist_ok=True)
        newname = f"sgdb_{uuid.uuid4().hex[:8]}.png"
        output_path = os.path.join(TEMP_COVERS_DIR, newname)

        result_bytes, used_icon, sgdb_name = choose_cover_with_sgdb_qt(
            app_name=app_name,
            output_path=output_path,
            exe_path=exe_path
        )

        if result_bytes:
            try:
                self.entry['cover_bytes'] = result_bytes
                self.entry['image-path'] = newname
                if sgdb_name:
                    self.entry['app_name'] = sgdb_name
                self.parent_window._refresh_entry_card(self.entry)
            except Exception as e:
                _cc(self, 'critical', 'Error', f'Failed to process SGDB cover: {e}')


class ConfirmAddWindow(QtWidgets.QWidget):
    covers_finished = QtCore.pyqtSignal()
    cover_progress = QtCore.pyqtSignal(object)
    cover_item_ready = QtCore.pyqtSignal(object, str)
    confirmed = QtCore.pyqtSignal(list)
    cancelled = QtCore.pyqtSignal()

    def __init__(self, pending_entries, apps_json, apps_json_path, output_folder,
                 pseudo_sorting_enabled=False, close_after_completion=True, parent=None):
        super().__init__(parent)

        # 确保配置已加载
        load_config()

        self.pending_entries = pending_entries
        self.apps_json = apps_json
        self.apps_json_path = apps_json_path
        self.output_folder = output_folder
        self.pseudo_sorting_enabled = pseudo_sorting_enabled
        self.close_after_completion = close_after_completion

        # event to signal that background cover generation should stop
        self._cancel_cover_event = threading.Event()
        # 仅用于取消 SGDB 阶段，不影响后续图标兜底封面生成
        self._cancel_sgdb_event = threading.Event()

        for e in self.pending_entries:
            e.setdefault('selected', True)

        self.filtered_entries = list(self.pending_entries)
        self.need_choose_cover_names = []
        self.image_target_paths = []
        self._cover_thread = None
        self.ignore_mode = False
        self.current_edit_entry = None
        self._cards = []
        self._entry_card_map = {}
        self._cover_stats = {
            'done': 0,
            'total': len(self.pending_entries),
            'success': 0,
            'steam': 0,
            'sgdb': 0,
            'icon': 0,
            'failed': 0,
            'message': ''
        }

        self.covers_finished.connect(self._on_covers_finished)
        self.cover_progress.connect(self._on_cover_progress)
        self.cover_item_ready.connect(self._on_cover_item_ready)

        self._setup_ui()

        self._debounce_timer = QtCore.QTimer(singleShot=True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self._do_refresh)

        self.container.installEventFilter(self)
        self._do_refresh()
        self._start_cover_thread()

    def _setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        # Search row
        h = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText(self.tr("搜索应用..."))
        self.search_edit.textChanged.connect(self._debounce_refresh)
        self.search_edit.setFixedHeight(30)
        h.addWidget(self.search_edit)

        self.search_btn = QtWidgets.QPushButton(self.tr("搜索"))
        self.search_btn.setFixedHeight(30)
        self.search_btn.setFixedWidth(80)
        self.search_btn.clicked.connect(self._debounce_refresh)
        h.addWidget(self.search_btn)
        main_layout.addLayout(h)

        # self.path_lbl = QtWidgets.QLabel(f'Current data path: {self.apps_json_path}')
        # self.path_lbl.setStyleSheet('color:gray')
        # main_layout.addWidget(self.path_lbl)

        self.info_label = QtWidgets.QLabel(self.tr("待添加的应用: %1").replace('%1', str(len(self.pending_entries))))
        self.info_label.setStyleSheet('')
        main_layout.addWidget(self.info_label)

        h_split = QtWidgets.QHBoxLayout()

        # Left: list
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # 启用触摸滚动支持
        QtWidgets.QScroller.grabGesture(self.scroll.viewport(), QtWidgets.QScroller.TouchGesture)

        self.container = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.container)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setSpacing(10)
        self.scroll.setWidget(self.container)
        left_layout.addWidget(self.scroll)

        self.status_label = QtWidgets.QLabel(self.tr("正在后台生成封面... (0/%1)").replace('%1', str(len(self.pending_entries))))
        self.status_label.setStyleSheet('')
        self.status_label.setMaximumWidth(600)
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        bottom = QtWidgets.QHBoxLayout()
        self.ignore_toggle_btn = QtWidgets.QPushButton(self.tr("选择忽略的应用"))
        self.ignore_toggle_btn.clicked.connect(self._toggle_ignore_mode)
        self.ignore_toggle_btn.setFixedHeight(48)
        bottom.addWidget(self.ignore_toggle_btn)

        bottom.addStretch()

        # 添加重启提示标签（仅在新方式失败回退旧方式、且开关开启时显示）
        self.restart_hint_label = QtWidgets.QLabel(self.tr("写入会重启sunshine"))
        self.restart_hint_label.setStyleSheet('font-size:8px;padding:0px;margin:0px;')
        from basic_def import restart_sunshine_after_add as current_value
        from basic_def import sunshine_api_fallback_used as fallback_used
        self.restart_hint_label.setVisible(current_value and fallback_used)
        bottom.addWidget(self.restart_hint_label)

        self.confirm_btn = QtWidgets.QPushButton(self.tr("写入 Sunshine"))
        self.confirm_btn.setFixedHeight(48)
        self.confirm_btn.setFixedWidth(150)
        self.confirm_btn.setEnabled(False)
        # 统一派发：封面生成期间点击=终止 SGDB；生成完成后点击=写入 Sunshine
        self._cover_generating = False
        self.confirm_btn.clicked.connect(self._on_confirm_btn_clicked)
        bottom.addWidget(self.confirm_btn)

        cancel_btn = QtWidgets.QPushButton(self.tr("取消"))
        cancel_btn.setFixedHeight(48)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self._on_cancel_clicked)
        bottom.addWidget(cancel_btn)

        left_layout.addLayout(bottom)
        h_split.addWidget(left_container, 3)

        # Right: edit panel (same style as manage_games)
        self.edit_panel = self._create_edit_panel()
        self.edit_panel.setVisible(False)
        h_split.addWidget(self.edit_panel, 2)

        main_layout.addLayout(h_split)

    def _create_edit_panel(self):
        panel = QtWidgets.QFrame()
        # 背景与边框由全局主题控制，深色模式下使用深色背景
        panel.setStyleSheet('QFrame { border-left: 1px solid #555555; }')
        panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QtWidgets.QLabel(self.tr("编辑应用"))
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        title.setFont(font)
        layout.addWidget(title)

        layout.addWidget(QtWidgets.QLabel(self.tr("名称:")))
        self.edit_name = QtWidgets.QLineEdit()
        layout.addWidget(self.edit_name)

        layout.addWidget(QtWidgets.QLabel(self.tr("目标路径:")))
        self.edit_target = QtWidgets.QLineEdit()
        self.edit_target.setReadOnly(True)
        self.edit_target.setMinimumHeight(60)
        layout.addWidget(self.edit_target)

        layout.addStretch()

        btns = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton(self.tr("保存"))
        save_btn.setFixedSize(90, 34)
        cancel_btn = QtWidgets.QPushButton(self.tr("取消"))
        cancel_btn.setFixedSize(90, 34)
        save_btn.clicked.connect(self._save_edit)
        cancel_btn.clicked.connect(self._close_edit_panel)
        btns.addStretch()
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        return panel

    def show_edit_panel(self, entry):
        self.current_edit_entry = entry
        self.edit_name.setText(entry.get('app_name', ''))
        self.edit_target.setText(str(entry.get('target_path', '')))
        self.edit_panel.setVisible(True)

    def _save_edit(self):
        if self.current_edit_entry is None:
            return
        self.current_edit_entry['app_name'] = self.edit_name.text().strip() or self.current_edit_entry.get('app_name', '')
        self._close_edit_panel()

    def _close_edit_panel(self):
        self.edit_panel.setVisible(False)
        self.current_edit_entry = None
        self._debounce_refresh()

    def resizeEvent(self, event):
        self._debounce_refresh()
        return super().resizeEvent(event)

    def closeEvent(self, event):
        """When the window is closed we should cancel any pending cover generation."""
        self.shutdown_cover_thread()
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        if watched is self.container and event.type() == QtCore.QEvent.Resize:
            self._debounce_refresh()
        return super().eventFilter(watched, event)

    def _debounce_refresh(self):
        self._debounce_timer.start()

    def _do_refresh(self):
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        term = self.search_edit.text().strip().lower()
        if not term:
            self.filtered_entries = list(self.pending_entries)
        else:
            self.filtered_entries = [
                e for e in self.pending_entries
                if term in e.get('app_name', '').lower() or term in str(e.get('target_path', '')).lower()
            ]

        self._entry_card_map = {}

        if not self.filtered_entries:
            label = QtWidgets.QLabel(self.tr("没有找到待添加的应用"))
            self.grid.addWidget(label, 0, 0)
            self._cards = []
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

        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

        viewport_width = max(300, self.scroll.viewport().width())
        max_card_w = max(240, (viewport_width - (self.grid.horizontalSpacing() * (cols + 1))) // cols)

        cards = []
        for idx, entry in enumerate(self.filtered_entries):
            card = ConfirmGameCard(entry, self)
            card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            card.setMaximumWidth(max_card_w)
            card.set_ignore_mode(self.ignore_mode)
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(card, row, col)
            cards.append(card)
            self._entry_card_map[id(entry)] = card

        self._cards = cards
        self.container.setMinimumWidth(viewport_width)
        QtCore.QTimer.singleShot(0, lambda: self.container.updateGeometry())

    def _toggle_ignore_mode(self):
        """切换忽略模式：进入时卡片只显示“忽略”按钮；退出时恢复其它按钮。"""
        self.ignore_mode = not self.ignore_mode
        self.ignore_toggle_btn.setText(self.tr("完成选择") if self.ignore_mode else self.tr("选择忽略的应用"))
        for card in self._cards:
            card.set_ignore_mode(self.ignore_mode)

    def ignore_entry(self, entry):
        """点击卡片的“忽略”按钮：将该游戏加入忽略列表并从列表隐藏。"""
        app_path = entry.get('target_path', '')
        app_name = entry.get('app_name', 'Unknown')

        # 加入 ignored_apps 配置
        import json
        ignored_apps_str = config.get('Settings', 'ignored_apps', fallback='[]')
        try:
            ignored_apps = json.loads(ignored_apps_str)
        except json.JSONDecodeError:
            ignored_apps = []

        exists = any(app.get('path') == app_path for app in ignored_apps)
        if not exists and app_path:
            ignored_apps.append({'name': app_name, 'path': app_path})
            config.set('Settings', 'ignored_apps', json.dumps(ignored_apps, ensure_ascii=False))
            save_config()

        # 从 pending_entries 移除并刷新
        try:
            self.pending_entries.remove(entry)
        except ValueError:
            pass
        self._cover_stats['total'] = len(self.pending_entries)
        self.info_label.setText(self.tr("待添加的应用: %1").replace('%1', str(len(self.pending_entries))))
        self._debounce_refresh()

        # 绿色成功通知
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                if hasattr(w, 'log_tab'):
                    w.log_tab.show_success_notification(
                        self.tr("已将“%1”添加到忽略列表").replace('%1', app_name)
                    )
                    break

    def on_import_cover(self, entry):
        def _on_picked(fp):
            if not fp:
                return
            try:
                from PIL import Image

                img = Image.open(fp)
                img = img.resize((600, 900), Image.LANCZOS)

                newname = f'custom_{uuid.uuid4().hex[:8]}.png'
                buf = BytesIO()
                img.save(buf, 'PNG')

                entry['cover_bytes'] = buf.getvalue()
                entry['image-path'] = newname
                self._refresh_entry_card(entry)
            except Exception as e:
                _cc(self, 'critical', self.tr("错误"),
                    self.tr("导入封面失败: %1").replace('%1', str(e)))

        _pick_file(self, mode='file',
                   file_types=['.jpg', '.jpeg', '.png', '.bmp'],
                   title=self.tr("选择封面图片"),
                   on_result=_on_picked)

    def _start_cover_thread(self):
        if not self.pending_entries:
            self.status_label.setText(self.tr("没有应用需要生成封面。"))
            self.covers_finished.emit()
            return

        # 重置 SGDB 取消标志（支持多次运行）
        self._cancel_sgdb_event.clear()
        # 进入"终止封面获取"模式：写入按钮复用为终止 SGDB 入口
        self._enter_terminate_mode()

        def worker():
            try:
                image_target_paths, need_choose_cover_names = generate_covers_for_entries(
                    self.pending_entries,
                    self.output_folder,
                    progress_callback=lambda payload: self.cover_progress.emit(payload),
                    cover_ready_callback=lambda entry, source: self.cover_item_ready.emit(entry, source),
                    cancel_event=self._cancel_cover_event,
                    cancel_sgdb_event=self._cancel_sgdb_event
                )
            except Exception as e:
                # 线程内的任何异常都不能逃逸，否则会打印到日志并被误认为崩溃
                print(f"封面生成线程异常: {e}")
                return
            self.image_target_paths = image_target_paths
            self.need_choose_cover_names = need_choose_cover_names
            try:
                self.covers_finished.emit()
            except RuntimeError:
                # 窗口已被销毁（例如重新打开添加窗口），忽略即可
                pass

        self._cover_thread = threading.Thread(target=worker, daemon=True)
        self._cover_thread.start()

    def shutdown_cover_thread(self, timeout=3.0):
        """取消并等待封面线程结束，避免窗口销毁后线程继续访问 Qt 对象导致 C++ 崩溃。"""
        self._cancel_cover_event.set()
        self._cancel_sgdb_event.set()
        thread = self._cover_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)
        self._cover_thread = None

    def _enter_terminate_mode(self):
        """封面生成期间：把"写入 Sunshine"按钮复用为"终止封面获取"。"""
        self._cover_generating = True
        self.confirm_btn.setText(self.tr("终止封面获取"))
        # 不太明显的颜色：暗灰蓝
        self.confirm_btn.setStyleSheet(
            "QPushButton { background-color: #6A737D; color: white; "
            "border: 2px solid transparent; border-radius: 5px; }"
            "QPushButton:hover { background-color: #5A6570; }"
            "QPushButton:pressed { background-color: #4A5358; }"
            "QPushButton:focus { background-color: #66ccff; color: #003344; "
            "border: 2px solid #66ccff; outline: 2px solid #ffffff; outline-offset: 2px; }"
            "QPushButton:disabled { background-color: #888; color: #ccc; }"
        )
        self.confirm_btn.setEnabled(True)

    def _terminate_sgdb(self):
        """用户点击"终止封面获取"：仅取消 SGDB 阶段，图标兜底封面继续生成。"""
        if self._cancel_sgdb_event.is_set():
            return
        self._cancel_sgdb_event.set()
        # 按钮切为"已终止"灰色不可点击，避免重复触发
        self.confirm_btn.setText(self.tr("已终止"))
        self.confirm_btn.setStyleSheet('')
        self.confirm_btn.setEnabled(False)
        # 状态栏追加提示
        cur = self.status_label.text()
        self.status_label.setText(cur + self.tr("  | SGDB 已终止，继续生成图标封面…"))

    def _on_confirm_btn_clicked(self):
        """按钮统一派发：封面生成中=终止 SGDB；生成完成后=写入 Sunshine。"""
        if self._cover_generating:
            self._terminate_sgdb()
        else:
            self._on_confirm_clicked()

    @QtCore.pyqtSlot()
    def _on_covers_finished(self):
        # 封面生成结束：恢复按钮为"写入 Sunshine"并启用
        self._cover_generating = False
        self.confirm_btn.setText(self.tr("写入 Sunshine"))
        self.confirm_btn.setStyleSheet('')
        self.confirm_btn.setEnabled(True)
        done = self._cover_stats.get('done', 0)
        total = self._cover_stats.get('total', len(self.pending_entries))
        success = self._cover_stats.get('success', 0)
        failed = self._cover_stats.get('failed', 0)
        text = self.tr("封面一一生成完成 (%1/%2) | 成功: %3 | 失败: %4。请确认应用。")
        text = text.replace('%1', str(done)).replace('%2', str(total)).replace('%3', str(success)).replace('%4', str(failed))
        self.status_label.setText(text)
        self.confirm_btn.setEnabled(True)
        self._debounce_refresh()

    def _refresh_entry_card(self, entry):
        card = self._entry_card_map.get(id(entry))
        if card is not None:
            card.refresh_cover()
            card.refresh_text()
            card.update()

    @QtCore.pyqtSlot(object, str)
    def _on_cover_item_ready(self, entry, source):
        self._refresh_entry_card(entry)

    @QtCore.pyqtSlot(object)
    def _on_cover_progress(self, payload):
        if not isinstance(payload, dict):
            return

        self._cover_stats.update({
            'done': payload.get('done', self._cover_stats.get('done', 0)),
            'total': payload.get('total', self._cover_stats.get('total', 0)),
            'success': payload.get('success', self._cover_stats.get('success', 0)),
            'steam': payload.get('steam', self._cover_stats.get('steam', 0)),
            'sgdb': payload.get('sgdb', self._cover_stats.get('sgdb', 0)),
            'icon': payload.get('icon', self._cover_stats.get('icon', 0)),
            'failed': payload.get('failed', self._cover_stats.get('failed', 0)),
            'message': payload.get('message', '') or ''
        })

        done = self._cover_stats['done']
        total = self._cover_stats['total']
        success = self._cover_stats['success']
        steam = self._cover_stats['steam']
        sgdb = self._cover_stats['sgdb']
        icon = self._cover_stats['icon']
        failed = self._cover_stats['failed']
        msg = self._cover_stats['message']
        app_name = payload.get('app_name')

        suffix = ''
        if app_name:
            suffix = f' | Current: {app_name}'
        if msg:
            suffix += f' | {msg}'

        status_text = self.tr("正在后台生成封面... (%1/%2) | 成功: %3 (Steam %4 / SGDB %5 / 图标 %6) | 失败: %7%8")
        status_text = status_text.replace('%1', str(done)).replace('%2', str(total)).replace('%3', str(success))
        status_text = status_text.replace('%4', str(steam)).replace('%5', str(sgdb)).replace('%6', str(icon))
        status_text = status_text.replace('%7', str(failed)).replace('%8', suffix)
        self.status_label.setText(status_text)

    def update_restart_hint(self):
        """更新重启提示标签的显示状态"""
        from basic_def import restart_sunshine_after_add as current_value
        from basic_def import sunshine_api_fallback_used as fallback_used
        self.restart_hint_label.setVisible(current_value and fallback_used)

    def _on_confirm_clicked(self):
        selected = [e for e in self.pending_entries if e.get('selected', True)]
        if not selected:
            _cc(self, 'information', self.tr("提示"), self.tr("没有选择任何应用。"))
            return
        self.pending_entries = selected
        self.confirmed.emit(selected)

    def _on_cancel_clicked(self):
        # stop background work
        self._cancel_cover_event.set()
        self.cancelled.emit()

    def get_selected_entries(self):
        return [e for e in self.pending_entries if e.get('selected', True)]
