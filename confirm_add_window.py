import os
import sys
import json
import threading
import uuid
from PyQt5 import QtWidgets, QtGui, QtCore
from basic_def import APP_INSTALL_PATH, load_apps_json, save_apps_json, generate_covers_for_entries


class ConfirmAddWindow(QtWidgets.QWidget):
    """
    确认即将写入 Sunshine 的应用列表。
    布局严格遵循 manage_games.ManageWindow，卡片包含 4 个按钮及增强的交互逻辑。
    """

    covers_finished = QtCore.pyqtSignal()
    confirmed = QtCore.pyqtSignal(list)  # 确认后发射选中的条目
    cancelled = QtCore.pyqtSignal()  # 取消时发射

    def __init__(self, pending_entries, apps_json, apps_json_path, output_folder,
                 pseudo_sorting_enabled=False, close_after_completion=True, parent=None):
        super().__init__(parent)

        self.pending_entries = pending_entries
        self.apps_json = apps_json
        self.apps_json_path = apps_json_path
        self.output_folder = output_folder
        self.pseudo_sorting_enabled = pseudo_sorting_enabled
        self.close_after_completion = close_after_completion

        self.filtered_entries = list(pending_entries)
        self.need_choose_cover_names = []
        self._cover_thread = None
        self.ignore_mode = False  # 是否进入忽略编辑模式

        self.covers_finished.connect(self._on_covers_finished)

        self._setup_ui()
        self._start_cover_thread()

    def _setup_ui(self):
        """构建 UI，参考 manage_games.ManageWindow 的布局"""
        main_layout = QtWidgets.QVBoxLayout(self)

        # 搜索行
        h_search = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("搜索游戏...")
        self.search_edit.textChanged.connect(self._apply_filter)
        self.search_edit.setFixedHeight(30)
        h_search.addWidget(self.search_edit)

        search_btn = QtWidgets.QPushButton("搜索")
        search_btn.setFixedHeight(30)
        search_btn.setFixedWidth(80)
        search_btn.clicked.connect(self._apply_filter)
        h_search.addWidget(search_btn)
        main_layout.addLayout(h_search)

        # 信息标签
        self.info_label = QtWidgets.QLabel(f"已扫描到新增游戏：{len(self.pending_entries)} 个")
        self.info_label.setStyleSheet("color: gray;")
        main_layout.addWidget(self.info_label)

        # 左右分割布局（暂时不分割，以后可扩展）
        h_split = QtWidgets.QHBoxLayout()

        # 左侧：游戏列表容器
        left_container = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # 滚动区域
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.container = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.container)
        self.grid.setContentsMargins(10, 10, 10, 10)
        self.grid.setSpacing(10)
        self.scroll_area.setWidget(self.container)
        left_layout.addWidget(self.scroll_area)

        # 状态标签
        self.status_label = QtWidgets.QLabel("正在后台生成封面，请稍候...")
        self.status_label.setStyleSheet("color: #2E7D9B;")
        left_layout.addWidget(self.status_label)

        # 底部按钮
        bottom_layout = QtWidgets.QHBoxLayout()

        self.ignore_btn = QtWidgets.QPushButton("选择忽略游戏")
        self.ignore_btn.clicked.connect(self._toggle_ignore_mode)
        bottom_layout.addWidget(self.ignore_btn)

        bottom_layout.addStretch()

        self.confirm_btn = QtWidgets.QPushButton("写入 Sunshine")
        self.confirm_btn.setFixedWidth(140)
        self.confirm_btn.setFixedHeight(40)
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._on_confirm_clicked)
        bottom_layout.addWidget(self.confirm_btn)

        cancel_btn = QtWidgets.QPushButton("取消")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setFixedHeight(40)
        cancel_btn.clicked.connect(self._on_cancel_clicked)
        bottom_layout.addWidget(cancel_btn)

        left_layout.addLayout(bottom_layout)

        h_split.addWidget(left_container, 1)
        main_layout.addLayout(h_split)

        self._rebuild_cards()

    def _rebuild_cards(self):
        """重新构建卡片网格"""
        # 清空旧卡片
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        if not self.filtered_entries:
            label = QtWidgets.QLabel("没有需要添加的新游戏。")
            label.setAlignment(QtCore.Qt.AlignCenter)
            self.grid.addWidget(label, 0, 0)
            return

        # 根据宽度确定列数
        width = max(300, self.width())
        if width < 600:
            cols = 2
        elif width < 1000:
            cols = 3
        else:
            cols = 4

        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

        for idx, entry in enumerate(self.filtered_entries):
            card = self._create_card_widget(entry)
            card.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            row = idx // cols
            col = idx % cols
            self.grid.addWidget(card, row, col)

        viewport_width = max(300, self.scroll_area.viewport().width())
        max_card_w = max(240, (viewport_width - (self.grid.horizontalSpacing() * (cols + 1))) // cols)
        
        # 更新所有卡片最大宽度
        for i in range(self.grid.count()):
            card = self.grid.itemAt(i).widget()
            if card:
                card.setMaximumWidth(max_card_w)

        self.container.setMinimumWidth(viewport_width)
        QtCore.QTimer.singleShot(0, lambda: self.container.updateGeometry())

    def _create_card_widget(self, entry):
        """创建单个游戏卡片"""
        frame = QtWidgets.QFrame()
        frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        frame.setStyleSheet("QFrame { background:white; border-radius:4px; border: 1px solid #ddd; }")

        h = QtWidgets.QHBoxLayout(frame)
        h.setContentsMargins(8, 8, 8, 8)

        # 左侧：封面
        cover_lbl = QtWidgets.QLabel("封面生成中")
        cover_lbl.setFixedSize(80, 120)
        cover_lbl.setAlignment(QtCore.Qt.AlignCenter)
        cover_lbl.setStyleSheet("background:#333;color:white;font-size:10px")
        h.addWidget(cover_lbl)

        # 中间：文本信息
        v = QtWidgets.QVBoxLayout()

        name_lbl = QtWidgets.QLabel(entry["app_name"])
        font = name_lbl.font()
        font.setBold(True)
        name_lbl.setFont(font)
        v.addWidget(name_lbl)

        path_lbl = QtWidgets.QLabel(f"路径: {entry['target_path']}")
        path_lbl.setStyleSheet("color:#666;font-size:9px")
        path_lbl.setWordWrap(True)
        v.addWidget(path_lbl)

        # 操作按钮或复选框（根据模式）
        control_layout = QtWidgets.QHBoxLayout()

        # 按钮组
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        # 4 个按钮
        left_btn = QtWidgets.QPushButton("←")
        left_btn.setFixedWidth(28)
        left_btn.setFixedHeight(22)
        left_btn.clicked.connect(lambda e=entry: self._on_left_clicked(e))
        btn_layout.addWidget(left_btn)

        right_btn = QtWidgets.QPushButton("→")
        right_btn.setFixedWidth(28)
        right_btn.setFixedHeight(22)
        right_btn.clicked.connect(lambda e=entry: self._on_right_clicked(e))
        btn_layout.addWidget(right_btn)

        import_btn = QtWidgets.QPushButton("导入图像")
        import_btn.setFixedHeight(22)
        import_btn.clicked.connect(lambda e=entry: self._on_import_cover(e))
        btn_layout.addWidget(import_btn)

        edit_btn = QtWidgets.QPushButton("修复名称")
        edit_btn.setFixedHeight(22)
        edit_btn.clicked.connect(lambda e=entry: self._on_edit_name(e))
        btn_layout.addWidget(edit_btn)

        control_layout.addWidget(btn_container)

        # 复选框（初始隐藏）
        checkbox = QtWidgets.QCheckBox("添加此应用")
        checkbox.setChecked(entry.get("selected", True))
        checkbox.setVisible(False)
        checkbox.stateChanged.connect(lambda state, e=entry: e.__setitem__("selected", state == QtCore.Qt.Checked))
        control_layout.addWidget(checkbox)

        control_layout.addStretch()

        v.addLayout(control_layout)
        v.addStretch()

        h.addLayout(v)

        # 保存引用
        entry["_cover_label"] = cover_lbl
        entry["_checkbox"] = checkbox
        entry["_btn_container"] = btn_container

        return frame

    def _set_cover_label_from_bytes(self, label, cover_bytes):
        """Load cover from in-memory bytes to avoid temp-file dependency."""
        if not label or not cover_bytes:
            return
        pix = QtGui.QPixmap()
        if not pix.loadFromData(cover_bytes):
            return
        label.setPixmap(pix.scaled(80, 120, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        label.setText("")
    # ========== 按钮事件处理 ==========

    def _on_left_clicked(self, entry):
        """左箭头按钮：在待添加列表中向前移动"""
        idx = self.filtered_entries.index(entry)
        if idx > 0:
            self.filtered_entries[idx], self.filtered_entries[idx - 1] = \
                self.filtered_entries[idx - 1], self.filtered_entries[idx]
            self._rebuild_cards()

    def _on_right_clicked(self, entry):
        """右箭头按钮：在待添加列表中向后移动"""
        idx = self.filtered_entries.index(entry)
        if idx < len(self.filtered_entries) - 1:
            self.filtered_entries[idx], self.filtered_entries[idx + 1] = \
                self.filtered_entries[idx + 1], self.filtered_entries[idx]
            self._rebuild_cards()


    def _on_import_cover(self, entry):
        """导入图片按钮：选择并导入自定义封面（内存模式）。"""
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择封面图片", "", "图片 (*.jpg *.jpeg *.png *.bmp)"
        )
        if not fp:
            return

        try:
            from PIL import Image
            from io import BytesIO

            img = Image.open(fp)
            img = img.resize((600, 900), Image.LANCZOS)

            newname = f"custom_{uuid.uuid4().hex[:8]}.jpg"
            buf = BytesIO()
            img.save(buf, "JPEG", quality=95)

            entry["cover_bytes"] = buf.getvalue()
            entry["image-path"] = newname

            label = entry.get("_cover_label")
            if label:
                self._set_cover_label_from_bytes(label, entry.get("cover_bytes"))

            QtWidgets.QMessageBox.information(self, "成功", "封面导入成功")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"导入封面失败: {e}")
    def _on_edit_name(self, entry):
        """修复名称按钮：编辑游戏名称"""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("修改游戏名称")
        dlg.setModal(True)

        layout = QtWidgets.QVBoxLayout(dlg)

        layout.addWidget(QtWidgets.QLabel("游戏名称:"))
        name_edit = QtWidgets.QLineEdit(entry.get("app_name", ""))
        layout.addWidget(name_edit)

        btns = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("确定")
        cancel_btn = QtWidgets.QPushButton("取消")

        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)

        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            entry["app_name"] = name_edit.text()
            self._rebuild_cards()

    # ========== 模式切换 ==========

    def _toggle_ignore_mode(self):
        """切换忽略编辑模式：隐藏按钮，显示复选框"""
        self.ignore_mode = not self.ignore_mode

        if self.ignore_mode:
            self.ignore_btn.setText("完成选择")
        else:
            self.ignore_btn.setText("选择忽略游戏")

        # 更新所有卡片的按钮/复选框可见性
        for entry in self.filtered_entries:
            btn_container = entry.get("_btn_container")
            checkbox = entry.get("_checkbox")

            if btn_container:
                btn_container.setVisible(not self.ignore_mode)
            if checkbox:
                checkbox.setVisible(self.ignore_mode)

    # ========== 封面生成（后台线程） ==========

    def _start_cover_thread(self):
        """启动后台线程生成封面"""
        if not self.pending_entries:
            self.status_label.setText("没有需要生成封面的应用。")
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
        """封面生成完成后的回调"""
        self.status_label.setText("封面整理完成，请确认要写入 Sunshine 的应用。")
        self.confirm_btn.setEnabled(True)

        # 更新卡片上的封面缩略图
        for entry in self.pending_entries:
            label = entry.get("_cover_label")
            cover_bytes = entry.get("cover_bytes")
            try:
                self._set_cover_label_from_bytes(label, cover_bytes)
            except Exception:
                pass
    # ========== 交互逻辑 ==========

    def _apply_filter(self):
        """应用搜索过滤"""
        term = self.search_edit.text().strip().lower()
        if not term:
            self.filtered_entries = list(self.pending_entries)
        else:
            self.filtered_entries = [
                e for e in self.pending_entries
                if term in e["app_name"].lower() or term in str(e["target_path"]).lower()
            ]
        self._rebuild_cards()

    def _on_confirm_clicked(self):
        """确认按钮：提交选中的条目"""
        selected = [e for e in self.pending_entries if e.get("selected", True)]
        if not selected:
            QtWidgets.QMessageBox.information(self, "提示", "当前没有选中的应用。")
            return
        self.pending_entries = selected
        self.confirmed.emit(selected)
    
    def _on_cancel_clicked(self):
        """取消按钮：发射取消信号"""
        self.cancelled.emit()

    def get_selected_entries(self):
        """返回选中的条目"""
        return list(self.pending_entries)
