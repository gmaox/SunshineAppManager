import os
import threading
import uuid
from io import BytesIO

from PyQt5 import QtCore, QtGui, QtWidgets

from basic_def import generate_covers_for_entries

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

        self.cover_lbl = QtWidgets.QLabel('No Cover')
        self.cover_lbl.setFixedSize(80, 120)
        self.cover_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.cover_lbl.setStyleSheet('background:#333;color:white')
        h.addWidget(self.cover_lbl)

        v = QtWidgets.QVBoxLayout()

        self.name_lbl = QtWidgets.QLabel(self.entry.get('app_name', 'Unknown'))
        font = self.name_lbl.font()
        font.setBold(True)
        self.name_lbl.setFont(font)
        v.addWidget(self.name_lbl)

        self.path_lbl = QtWidgets.QLabel('Path: ' + str(self.entry.get('target_path', '')))
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

        self.import_btn = QtWidgets.QPushButton('Import Cover')
        self.import_btn.setFixedHeight(22)
        self.import_btn.clicked.connect(lambda: self.parent_window.on_import_cover(self.entry))
        btns.addWidget(self.import_btn)

        self.edit_btn = QtWidgets.QPushButton('Edit')
        self.edit_btn.setFixedHeight(22)
        self.edit_btn.clicked.connect(lambda: self.parent_window.show_edit_panel(self.entry))
        btns.addWidget(self.edit_btn)

        control.addWidget(self.btn_container)

        self.checkbox = QtWidgets.QCheckBox('Include')
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
        self.path_lbl.setText('Path: ' + str(self.entry.get('target_path', '')))

    def refresh_cover(self):
        cover_bytes = self.entry.get('cover_bytes')
        if not cover_bytes:
            self.cover_lbl.setPixmap(QtGui.QPixmap())
            self.cover_lbl.setText('No Cover')
            return

        pix = QtGui.QPixmap()
        if not pix.loadFromData(cover_bytes):
            self.cover_lbl.setPixmap(QtGui.QPixmap())
            self.cover_lbl.setText('No Cover')
            return

        self.cover_lbl.setPixmap(
            pix.scaled(THUMB_SIZE[0], THUMB_SIZE[1], QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        )
        self.cover_lbl.setText('')


class ConfirmAddWindow(QtWidgets.QWidget):
    covers_finished = QtCore.pyqtSignal()
    confirmed = QtCore.pyqtSignal(list)
    cancelled = QtCore.pyqtSignal()

    def __init__(self, pending_entries, apps_json, apps_json_path, output_folder,
                 pseudo_sorting_enabled=False, close_after_completion=True, parent=None):
        super().__init__(parent)

        self.pending_entries = pending_entries
        self.apps_json = apps_json
        self.apps_json_path = apps_json_path
        self.output_folder = output_folder
        self.pseudo_sorting_enabled = pseudo_sorting_enabled
        self.close_after_completion = close_after_completion

        for e in self.pending_entries:
            e.setdefault('selected', True)

        self.filtered_entries = list(self.pending_entries)
        self.need_choose_cover_names = []
        self.image_target_paths = []
        self._cover_thread = None
        self.ignore_mode = False
        self.current_edit_entry = None
        self._cards = []

        self.covers_finished.connect(self._on_covers_finished)

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
        self.search_edit.setPlaceholderText('Search apps...')
        self.search_edit.textChanged.connect(self._debounce_refresh)
        self.search_edit.setFixedHeight(30)
        h.addWidget(self.search_edit)

        self.search_btn = QtWidgets.QPushButton('Search')
        self.search_btn.setFixedHeight(30)
        self.search_btn.setFixedWidth(80)
        self.search_btn.clicked.connect(self._debounce_refresh)
        h.addWidget(self.search_btn)
        main_layout.addLayout(h)

        # self.path_lbl = QtWidgets.QLabel(f'Current data path: {self.apps_json_path}')
        # self.path_lbl.setStyleSheet('color:gray')
        # main_layout.addWidget(self.path_lbl)

        self.info_label = QtWidgets.QLabel(f'Pending apps: {len(self.pending_entries)}')
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

        self.status_label = QtWidgets.QLabel('Generating covers in background...')
        self.status_label.setStyleSheet('color:#2E7D9B')
        left_layout.addWidget(self.status_label)

        bottom = QtWidgets.QHBoxLayout()
        self.ignore_btn = QtWidgets.QPushButton('Select ignored apps')
        self.ignore_btn.clicked.connect(self._toggle_ignore_mode)
        self.ignore_btn.setFixedHeight(40)
        bottom.addWidget(self.ignore_btn)

        bottom.addStretch()

        self.confirm_btn = QtWidgets.QPushButton('Write to Sunshine')
        self.confirm_btn.setFixedHeight(40)
        self.confirm_btn.setFixedWidth(150)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        bottom.addWidget(self.confirm_btn)

        cancel_btn = QtWidgets.QPushButton('Cancel')
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

        title = QtWidgets.QLabel('Edit App')
        font = title.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        title.setFont(font)
        layout.addWidget(title)

        layout.addWidget(QtWidgets.QLabel('Name:'))
        self.edit_name = QtWidgets.QLineEdit()
        layout.addWidget(self.edit_name)

        layout.addWidget(QtWidgets.QLabel('Target Path:'))
        self.edit_target = QtWidgets.QLineEdit()
        self.edit_target.setReadOnly(True)
        self.edit_target.setMinimumHeight(60)
        layout.addWidget(self.edit_target)

        layout.addStretch()

        btns = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton('Save')
        save_btn.setFixedSize(80, 26)
        cancel_btn = QtWidgets.QPushButton('Cancel')
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

        if not self.filtered_entries:
            label = QtWidgets.QLabel('No pending app found')
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
        self.ignore_mode = not self.ignore_mode
        self.ignore_btn.setText('Finish Selection' if self.ignore_mode else 'Select ignored apps')
        for card in self._cards:
            card.set_ignore_mode(self.ignore_mode)

    def on_import_cover(self, entry):
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Choose cover image', '', 'Image (*.jpg *.jpeg *.png *.bmp)')
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
            self._debounce_refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Import cover failed: {e}')

    def _start_cover_thread(self):
        if not self.pending_entries:
            self.status_label.setText('No app needs cover generation.')
            self.covers_finished.emit()
            return

        def worker():
            image_target_paths, need_choose_cover_names = generate_covers_for_entries(
                self.pending_entries,
                self.output_folder
            )
            self.image_target_paths = image_target_paths
            self.need_choose_cover_names = need_choose_cover_names
            self.covers_finished.emit()

        self._cover_thread = threading.Thread(target=worker, daemon=True)
        self._cover_thread.start()

    @QtCore.pyqtSlot()
    def _on_covers_finished(self):
        self.status_label.setText('Cover generation finished. Please confirm apps to write.')
        self.confirm_btn.setEnabled(True)
        self._debounce_refresh()

    def _on_confirm_clicked(self):
        selected = [e for e in self.pending_entries if e.get('selected', True)]
        if not selected:
            QtWidgets.QMessageBox.information(self, 'Tip', 'No app selected.')
            return
        self.pending_entries = selected
        self.confirmed.emit(selected)

    def _on_cancel_clicked(self):
        self.cancelled.emit()

    def get_selected_entries(self):
        return [e for e in self.pending_entries if e.get('selected', True)]
