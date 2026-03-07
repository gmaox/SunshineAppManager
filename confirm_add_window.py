import os
import threading
import uuid
from io import BytesIO

from PyQt5 import QtCore, QtGui, QtWidgets

from basic_def import generate_covers_for_entries, config, save_config, restart_sunshine_after_add, load_config
from sgdb_cover_window import choose_cover_with_sgdb_qt

THUMB_SIZE = (80, 120)


class ConfirmGameCard(QtWidgets.QFrame):
    def __init__(self, entry, parent_window):
        super().__init__(parent_window)
        self.entry = entry
        self.parent_window = parent_window
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setStyleSheet('background:white;')
        self._setup_ui()
        self.refresh_cover()

    def _setup_ui(self):
        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(8, 8, 8, 8)

        self.cover_lbl = QtWidgets.QLabel('没有封面')
        self.cover_lbl.setFixedSize(80, 120)
        self.cover_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.cover_lbl.setStyleSheet('background:#333;color:white')
        self.cover_lbl.setCursor(QtCore.Qt.PointingHandCursor)  # 设置鼠标指针为手型
        self.cover_lbl.mousePressEvent = self.on_cover_click  # 连接点击事件
        h.addWidget(self.cover_lbl)

        v = QtWidgets.QVBoxLayout()

        self.name_lbl = QtWidgets.QLabel(self.entry.get('app_name', 'Unknown'))
        font = self.name_lbl.font()
        font.setBold(True)
        self.name_lbl.setFont(font)
        v.addWidget(self.name_lbl)

        self.path_lbl = QtWidgets.QLabel('路径: ' + str(self.entry.get('target_path', '')))
        self.path_lbl.setStyleSheet('color:#666')
        self.path_lbl.setWordWrap(True)
        v.addWidget(self.path_lbl)
        v.addStretch()

        control = QtWidgets.QHBoxLayout()

        self.btn_container = QtWidgets.QWidget()
        btns = QtWidgets.QHBoxLayout(self.btn_container)
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(2)

        self.left_btn = QtWidgets.QPushButton('←')
        self.left_btn.setFixedSize(28, 22)
        self.left_btn.clicked.connect(lambda: self.parent_window.move_entry(self.entry, -1))
        btns.addWidget(self.left_btn)

        self.right_btn = QtWidgets.QPushButton('→')
        self.right_btn.setFixedSize(28, 22)
        self.right_btn.clicked.connect(lambda: self.parent_window.move_entry(self.entry, 1))
        btns.addWidget(self.right_btn)

        self.import_btn = QtWidgets.QPushButton('导入封面')
        self.import_btn.setFixedHeight(22)
        self.import_btn.clicked.connect(lambda: self.parent_window.on_import_cover(self.entry))
        btns.addWidget(self.import_btn)

        self.edit_btn = QtWidgets.QPushButton('编辑')
        self.edit_btn.setFixedHeight(22)
        self.edit_btn.clicked.connect(lambda: self.parent_window.show_edit_panel(self.entry))
        btns.addWidget(self.edit_btn)

        control.addWidget(self.btn_container)

        self.checkbox = QtWidgets.QCheckBox('包含')
        self.checkbox.setChecked(self.entry.get('selected', True))
        self.checkbox.setVisible(False)
        self.checkbox.stateChanged.connect(
            lambda state: self.entry.__setitem__('selected', state == QtCore.Qt.Checked)
        )
        control.addWidget(self.checkbox)
        control.addStretch()

        v.addLayout(control)
        h.addLayout(v)

    def set_ignore_mode(self, ignore_mode):
        self.btn_container.setVisible(not ignore_mode)
        self.checkbox.setVisible(ignore_mode)

    def refresh_text(self):
        self.name_lbl.setText(self.entry.get('app_name', 'Unknown'))
        self.path_lbl.setText('路径: ' + str(self.entry.get('target_path', '')))

    def refresh_cover(self):
        cover_bytes = self.entry.get('cover_bytes')
        if not cover_bytes:
            self.cover_lbl.setPixmap(QtGui.QPixmap())
            self.cover_lbl.setText('没有封面')
            return

        pix = QtGui.QPixmap()
        if not pix.loadFromData(cover_bytes):
            self.cover_lbl.setPixmap(QtGui.QPixmap())
            self.cover_lbl.setText('没有封面')
            return

        self.cover_lbl.setPixmap(
            pix.scaled(THUMB_SIZE[0], THUMB_SIZE[1], QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        )
        self.cover_lbl.setText('')

    def on_cover_click(self, event):
        """点击封面时使用 SGDB 选择封面"""
        self._change_cover_with_sgdb()

    def _change_cover_with_sgdb(self):
        """使用 SGDB 选择封面"""
        app_name = self.entry.get('app_name', 'Unknown')
        exe_path = self.entry.get('target_path', '')
        
        # 确定输出路径
        from basic_def import TEMP_COVERS_DIR
        import os
        os.makedirs(TEMP_COVERS_DIR, exist_ok=True)
        newname = f"sgdb_{uuid.uuid4().hex[:8]}.jpg"
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
                    self.entry['app_name'] = sgdb_name  # 更新名称如果选择了应用 SGDB 名称
                self.parent_window._refresh_entry_card(self.entry)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Error', f'Failed to process SGDB cover: {e}')


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
        self.search_edit.setPlaceholderText('搜索应用...')
        self.search_edit.textChanged.connect(self._debounce_refresh)
        self.search_edit.setFixedHeight(30)
        h.addWidget(self.search_edit)

        self.search_btn = QtWidgets.QPushButton('搜索')
        self.search_btn.setFixedHeight(30)
        self.search_btn.setFixedWidth(80)
        self.search_btn.clicked.connect(self._debounce_refresh)
        h.addWidget(self.search_btn)
        main_layout.addLayout(h)

        # self.path_lbl = QtWidgets.QLabel(f'Current data path: {self.apps_json_path}')
        # self.path_lbl.setStyleSheet('color:gray')
        # main_layout.addWidget(self.path_lbl)

        self.info_label = QtWidgets.QLabel(f'待添加的应用: {len(self.pending_entries)}')
        self.info_label.setStyleSheet('color: gray;')
        main_layout.addWidget(self.info_label)

        h_split = QtWidgets.QHBoxLayout()

        # Left: list
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.container = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.container)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setSpacing(10)
        self.scroll.setWidget(self.container)
        left_layout.addWidget(self.scroll)

        self.status_label = QtWidgets.QLabel(f'正在后台生成封面... (0/{len(self.pending_entries)})')
        self.status_label.setStyleSheet('color:#2E7D9B')
        self.status_label.setMaximumWidth(600)
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        bottom = QtWidgets.QHBoxLayout()
        self.ignore_btn = QtWidgets.QPushButton('选择忽略的应用')
        self.ignore_btn.clicked.connect(self._toggle_ignore_mode)
        self.ignore_btn.setFixedHeight(40)
        bottom.addWidget(self.ignore_btn)

        bottom.addStretch()

        # 添加重启提示标签（开关开启时显示）
        self.restart_hint_label = QtWidgets.QLabel('写入会重启sunshine')
        self.restart_hint_label.setStyleSheet('color:#666;font-size:8px;padding:0px;margin:0px;')
        from basic_def import restart_sunshine_after_add as current_value
        self.restart_hint_label.setVisible(current_value)
        bottom.addWidget(self.restart_hint_label)

        self.confirm_btn = QtWidgets.QPushButton('写入 Sunshine')
        self.confirm_btn.setFixedHeight(40)
        self.confirm_btn.setFixedWidth(150)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        bottom.addWidget(self.confirm_btn)

        cancel_btn = QtWidgets.QPushButton('取消')
        cancel_btn.setFixedHeight(40)
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
        panel.setStyleSheet('background:#f5f5f5;border-left:1px solid #ddd')
        panel.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QtWidgets.QLabel('编辑应用')
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        title.setFont(font)
        layout.addWidget(title)

        layout.addWidget(QtWidgets.QLabel('名称:'))
        self.edit_name = QtWidgets.QLineEdit()
        layout.addWidget(self.edit_name)

        layout.addWidget(QtWidgets.QLabel('目标路径:'))
        self.edit_target = QtWidgets.QLineEdit()
        self.edit_target.setReadOnly(True)
        self.edit_target.setMinimumHeight(60)
        layout.addWidget(self.edit_target)

        layout.addStretch()

        btns = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton('保存')
        save_btn.setFixedSize(80, 26)
        cancel_btn = QtWidgets.QPushButton('取消')
        cancel_btn.setFixedSize(80, 26)
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
        self._cancel_cover_event.set()
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
            label = QtWidgets.QLabel('没有找到待添加的应用')
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

    def move_entry(self, entry, delta):
        try:
            idx = self.pending_entries.index(entry)
        except ValueError:
            return
        new_idx = idx + delta
        if new_idx < 0 or new_idx >= len(self.pending_entries):
            return
        self.pending_entries[idx], self.pending_entries[new_idx] = self.pending_entries[new_idx], self.pending_entries[idx]
        self._debounce_refresh()

    def _toggle_ignore_mode(self):
        if self.ignore_mode:
            # 从忽略模式切换回正常模式，处理被忽略的应用
            ignored_entries = [e for e in self.pending_entries if not e.get('selected', True)]
        if self.ignore_mode:
            # 从忽略模式切换回正常模式，处理被忽略的应用
            ignored_entries = [e for e in self.pending_entries if not e.get('selected', True)]
            if ignored_entries:
                # 加载配置
                import json
                ignored_apps_str = config.get('Settings', 'ignored_apps', fallback='[]')
                try:
                    ignored_apps = json.loads(ignored_apps_str)
                except json.JSONDecodeError:
                    ignored_apps = []
                
                # 添加到忽略列表
                for entry in ignored_entries:
                    app_path = entry.get('target_path', '')
                    app_name = entry.get('app_name', 'Unknown')
                    
                    # 检查是否已存在
                    exists = any(app.get('path') == app_path for app in ignored_apps)
                    if not exists and app_path:
                        ignored_apps.append({
                            'name': app_name,
                            'path': app_path
                        })
                
                # 保存配置
                ignored_apps_str = json.dumps(ignored_apps, ensure_ascii=False)
                config.set('Settings', 'ignored_apps', ignored_apps_str)
                save_config()
                
                # 使用绿色成功通知而不是弹出对话框
                from PyQt5.QtWidgets import QApplication
                app = QApplication.instance()
                if app:
                    for w in app.topLevelWidgets():
                        if hasattr(w, 'log_tab'):
                            w.log_tab.show_success_notification(
                                f'已将 {len(ignored_entries)} 个应用添加到忽略列表'
                            )
                            break
            
            # 从pending_entries中移除被忽略的应用
            self.pending_entries = [e for e in self.pending_entries if e.get('selected', True)]
            self._debounce_refresh()
        
        self.ignore_mode = not self.ignore_mode
        self.ignore_btn.setText('完成选择' if self.ignore_mode else '选择忽略的应用')
        for card in self._cards:
            card.set_ignore_mode(self.ignore_mode)

    def on_import_cover(self, entry):
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(self, '选择封面图片', '', '图片 (*.jpg *.jpeg *.png *.bmp)')
        if not fp:
            return

        try:
            from PIL import Image

            img = Image.open(fp)
            img = img.resize((600, 900), Image.LANCZOS)

            newname = f'custom_{uuid.uuid4().hex[:8]}.jpg'
            buf = BytesIO()
            img.save(buf, 'JPEG', quality=95)

            entry['cover_bytes'] = buf.getvalue()
            entry['image-path'] = newname
            self._refresh_entry_card(entry)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, '错误', f'导入封面失败: {e}')

    def _start_cover_thread(self):
        if not self.pending_entries:
            self.status_label.setText('没有应用需要生成封面。')
            self.covers_finished.emit()
            return

        def worker():
            image_target_paths, need_choose_cover_names = generate_covers_for_entries(
                self.pending_entries,
                self.output_folder,
                progress_callback=lambda payload: self.cover_progress.emit(payload),
                cover_ready_callback=lambda entry, source: self.cover_item_ready.emit(entry, source),
                cancel_event=self._cancel_cover_event
            )
            self.image_target_paths = image_target_paths
            self.need_choose_cover_names = need_choose_cover_names
            self.covers_finished.emit()

        self._cover_thread = threading.Thread(target=worker, daemon=True)
        self._cover_thread.start()

    @QtCore.pyqtSlot()
    def _on_covers_finished(self):
        done = self._cover_stats.get('done', 0)
        total = self._cover_stats.get('total', len(self.pending_entries))
        success = self._cover_stats.get('success', 0)
        failed = self._cover_stats.get('failed', 0)
        self.status_label.setText(
            f'封面一一生成完成 ({done}/{total}) | 成功: {success} | 失败: {failed}。请确认应用。'
        )
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

        self.status_label.setText(
            f'正在后台生成封面... ({done}/{total}) | 成功: {success} '
            f'(Steam {steam} / SGDB {sgdb} / 图标 {icon}) | 失败: {failed}{suffix}'
        )

    def update_restart_hint(self):
        """更新重启提示标签的显示状态"""
        from basic_def import restart_sunshine_after_add as current_value
        self.restart_hint_label.setVisible(current_value)

    def _on_confirm_clicked(self):
        selected = [e for e in self.pending_entries if e.get('selected', True)]
        if not selected:
            QtWidgets.QMessageBox.information(self, '提示', '没有选择任何应用。')
            return
        self.pending_entries = selected
        self.confirmed.emit(selected)

    def _on_cancel_clicked(self):
        # stop background work
        self._cancel_cover_event.set()
        self.cancelled.emit()

    def get_selected_entries(self):
        return [e for e in self.pending_entries if e.get('selected', True)]
