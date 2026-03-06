import json
import os
import time
import uuid

from PyQt5 import QtCore, QtGui, QtWidgets

from basic_def import APP_INSTALL_PATH


SCANNERS_JSON_PATH = os.path.join(APP_INSTALL_PATH, "config", "scanners.json")


def _ensure_scanner_store_dir():
    os.makedirs(os.path.dirname(SCANNERS_JSON_PATH), exist_ok=True)


def normalize_scanner(scanner):
    item = dict(scanner or {})
    item.setdefault("id", uuid.uuid4().hex)
    item["name"] = str(item.get("name", "")).strip()
    item["type"] = str(item.get("type", "custom")).strip().lower()
    item["source"] = str(item.get("source", "")).strip()
    item["enabled"] = bool(item.get("enabled", True))
    item["include_hidden"] = bool(item.get("include_hidden", False))
    item["recursive"] = bool(item.get("recursive", True))
    item["emulator_path"] = str(item.get("emulator_path", "")).strip()
    item["emulator_args"] = str(item.get("emulator_args", "{rom}")).strip() or "{rom}"
    item["rom_extensions"] = str(item.get("rom_extensions", ".zip,.7z,.iso,.cue,.chd")).strip()
    item.setdefault("last_run", "")
    item.setdefault("last_result", "")
    item.setdefault("created_at", int(time.time()))
    item["updated_at"] = int(time.time())
    return item


def load_scanners():
    _ensure_scanner_store_dir()
    if not os.path.exists(SCANNERS_JSON_PATH):
        return []

    try:
        with open(SCANNERS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    scanners = data if isinstance(data, list) else []
    return [normalize_scanner(s) for s in scanners]


def save_scanners(scanners):
    _ensure_scanner_store_dir()
    normalized = [normalize_scanner(s) for s in (scanners or [])]
    with open(SCANNERS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)


class ScannerAddPage(QtWidgets.QWidget):
    scanners_changed = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._update_type_fields()
        self._update_saved_count()

    def _setup_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QtWidgets.QLabel("添加扫描器")
        title.setFont(QtGui.QFont("Segoe UI", 16, QtGui.QFont.Bold))
        root.addWidget(title)

        desc = QtWidgets.QLabel(
            "创建类似 Steam ROM Manager 解析器的扫描器预设。"
            "支持类型：Steam、Epic、ROM 和自定义文件夹扫描器。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#555;")
        root.addWidget(desc)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        form.setFormAlignment(QtCore.Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("扫描器名称，例如 Steam 库")
        form.addRow("名称：", self.name_input)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem("Steam 库", "steam")
        self.type_combo.addItem("Epic 清单", "epic")
        self.type_combo.addItem("ROM 文件夹", "rom")
        self.type_combo.addItem("自定义文件夹", "custom")
        self.type_combo.currentIndexChanged.connect(self._update_type_fields)
        form.addRow("类型：", self.type_combo)

        source_row = QtWidgets.QHBoxLayout()
        self.source_input = QtWidgets.QLineEdit()
        self.source_input.setPlaceholderText("留空则自动检测")
        source_row.addWidget(self.source_input, 1)
        source_btn = QtWidgets.QPushButton("浏览")
        source_btn.clicked.connect(self._browse_source)
        source_row.addWidget(source_btn)
        form.addRow("源路径：", source_row)

        self.enabled_chk = QtWidgets.QCheckBox("已启用")
        self.enabled_chk.setChecked(True)
        form.addRow("", self.enabled_chk)

        self.recursive_chk = QtWidgets.QCheckBox("递归扫描子文件夹")
        self.recursive_chk.setChecked(True)
        form.addRow("", self.recursive_chk)

        self.hidden_chk = QtWidgets.QCheckBox("包含隐藏文件")
        self.hidden_chk.setChecked(False)
        form.addRow("", self.hidden_chk)

        emu_row = QtWidgets.QHBoxLayout()
        self.emulator_input = QtWidgets.QLineEdit()
        self.emulator_input.setPlaceholderText("仅限 ROM 类型：模拟器可执行文件路径")
        emu_row.addWidget(self.emulator_input, 1)
        emu_btn = QtWidgets.QPushButton("浏览")
        emu_btn.clicked.connect(self._browse_emulator)
        emu_row.addWidget(emu_btn)
        form.addRow("模拟器：", emu_row)

        self.args_input = QtWidgets.QLineEdit("{rom}")
        self.args_input.setPlaceholderText("参数模板，使用 {rom} 占位符")
        form.addRow("参数：", self.args_input)

        self.rom_ext_input = QtWidgets.QLineEdit(".zip,.7z,.iso,.cue,.chd")
        self.rom_ext_input.setPlaceholderText("ROM 扩展名，逗号分隔")
        form.addRow("ROM 扩展名：", self.rom_ext_input)

        root.addLayout(form)

        row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("添加扫描器")
        add_btn.clicked.connect(self._on_add_scanner)
        row.addWidget(add_btn)

        reset_btn = QtWidgets.QPushButton("重置")
        reset_btn.clicked.connect(self._reset_form)
        row.addWidget(reset_btn)
        row.addStretch()
        root.addLayout(row)

        self.saved_label = QtWidgets.QLabel("")
        self.saved_label.setStyleSheet("color:#666;")
        root.addWidget(self.saved_label)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color:#2E7D9B;")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        root.addStretch()

    def _update_saved_count(self):
        count = len(load_scanners())
        self.saved_label.setText(f"已保存的扫描器：{count}")

    def _reset_form(self):
        self.name_input.clear()
        self.type_combo.setCurrentIndex(0)
        self.source_input.clear()
        self.enabled_chk.setChecked(True)
        self.recursive_chk.setChecked(True)
        self.hidden_chk.setChecked(False)
        self.emulator_input.clear()
        self.args_input.setText("{rom}")
        self.rom_ext_input.setText(".zip,.7z,.iso,.cue,.chd")
        self.status_label.setText("表单已重置。")
        self._update_type_fields()

    def _browse_source(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "选择扫描器源文件夹")
        if directory:
            self.source_input.setText(os.path.normpath(directory))

    def _browse_emulator(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择模拟器可执行文件", "", "可执行文件 (*.exe);;所有文件 (*.*)"
        )
        if file_path:
            self.emulator_input.setText(os.path.normpath(file_path))

    def _update_type_fields(self):
        scanner_type = self.type_combo.currentData()
        rom_mode = scanner_type == "rom"
        custom_mode = scanner_type == "custom"
        steam_or_epic_mode = scanner_type in ("steam", "epic")

        self.emulator_input.setEnabled(rom_mode)
        self.args_input.setEnabled(rom_mode)
        self.rom_ext_input.setEnabled(rom_mode)

        self.recursive_chk.setEnabled(rom_mode or custom_mode)
        self.hidden_chk.setEnabled(rom_mode or custom_mode)

        if scanner_type == "steam":
            self.source_input.setPlaceholderText("可选的 Steam 根路径（留空则自动检测）")
        elif scanner_type == "epic":
            self.source_input.setPlaceholderText("可选的 Epic 清单目录（留空则自动检测）")
        elif scanner_type == "rom":
            self.source_input.setPlaceholderText("ROM 目录")
        else:
            self.source_input.setPlaceholderText("要扫描的文件夹，查找 .exe/.lnk/.url")

        if steam_or_epic_mode and not self.source_input.text().strip():
            self.recursive_chk.setChecked(False)

    def _build_scanner(self):
        scanner_type = self.type_combo.currentData()
        name = self.name_input.text().strip()
        source = self.source_input.text().strip()
        emulator_path = self.emulator_input.text().strip()

        if not name:
            raise ValueError("扫描器名称是必需的。")
        if scanner_type in ("rom", "custom") and not source:
            raise ValueError("ROM/自定义扫描器需要源文件夹。")
        if scanner_type == "rom" and not emulator_path:
            raise ValueError("ROM 扫描器需要模拟器路径。")

        return normalize_scanner({
            "name": name,
            "type": scanner_type,
            "source": source,
            "enabled": self.enabled_chk.isChecked(),
            "recursive": self.recursive_chk.isChecked(),
            "include_hidden": self.hidden_chk.isChecked(),
            "emulator_path": emulator_path,
            "emulator_args": self.args_input.text().strip() or "{rom}",
            "rom_extensions": self.rom_ext_input.text().strip(),
        })

    def _on_add_scanner(self):
        try:
            scanner = self._build_scanner()
            scanners = load_scanners()

            scanner_key = (
                scanner.get("type", ""),
                scanner.get("name", "").lower(),
                scanner.get("source", "").lower(),
            )
            for s in scanners:
                existing_key = (
                    str(s.get("type", "")),
                    str(s.get("name", "")).strip().lower(),
                    str(s.get("source", "")).strip().lower(),
                )
                if existing_key == scanner_key:
                    raise ValueError("已存在相同类型/名称/源的扫描器。")

            scanners.append(scanner)
            save_scanners(scanners)
            self.status_label.setText(f"已添加扫描器：{scanner['name']}")
            self._update_saved_count()
            self.scanners_changed.emit()
        except Exception as e:
            self.status_label.setText(f"添加扫描器失败：{e}")
