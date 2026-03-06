import glob
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

import basic_def
from scanner_add_page import load_scanners, save_scanners, normalize_scanner

try:
    import winreg
except Exception:
    winreg = None

try:
    import win32com.client
except Exception:
    win32com = None


SCANNER_TYPE_LABELS = {
    "steam": "Steam",
    "epic": "Epic",
    "rom": "ROM",
    "custom": "自定义",
}


def _normalize_path(value):
    raw = str(value or "").strip().strip('"')
    if not raw:
        return ""
    if raw.lower().startswith(("steam://", "http://", "https://")):
        return raw.lower()
    return os.path.normcase(os.path.normpath(raw))


def _safe_name(value):
    text = str(value or "").strip() or "unnamed"
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    return text[:140].strip() or "unnamed"


def _is_hidden(path):
    name = os.path.basename(path).strip()
    return bool(name.startswith("."))


def _load_ignored_targets():
    try:
        basic_def.load_config()
    except Exception:
        pass

    raw = basic_def.config.get("Settings", "ignored_apps", fallback="[]")
    try:
        ignored = json.loads(raw)
    except Exception:
        ignored = []

    targets = set()
    for item in ignored if isinstance(ignored, list) else []:
        target = _normalize_path((item or {}).get("path"))
        if target:
            targets.add(target)
    return targets


def _is_ignored(target, ignored_targets):
    normalized = _normalize_path(target)
    return bool(normalized and normalized in ignored_targets)


def _get_work_folder():
    try:
        basic_def.load_config()
    except Exception:
        pass

    work_folder = getattr(basic_def, "folder", "") or getattr(basic_def, "folder_selected", "")
    work_folder = str(work_folder or "").strip()
    if not work_folder:
        work_folder = os.path.realpath(os.path.join(os.path.dirname(sys.executable), "appfolder"))

    os.makedirs(work_folder, exist_ok=True)
    return work_folder


def _write_url_shortcut(path, url):
    content = "[InternetShortcut]\nURL=" + url + "\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _create_lnk(shortcut_path, target_path, arguments="", working_dir="", icon_location=""):
    if win32com is None:
        raise RuntimeError("win32com is unavailable")
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(shortcut_path)
    shortcut.TargetPath = target_path
    if arguments:
        shortcut.Arguments = arguments
    if working_dir:
        shortcut.WorkingDirectory = working_dir
    if icon_location:
        shortcut.IconLocation = icon_location
    shortcut.save()


def _detect_steam_root():
    candidates = []

    if winreg is not None:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
            if steam_path:
                candidates.append(steam_path)
        except Exception:
            pass

    env_x86 = os.environ.get("PROGRAMFILES(X86)")
    if env_x86:
        candidates.append(os.path.join(env_x86, "Steam"))
    env_pf = os.environ.get("PROGRAMFILES")
    if env_pf:
        candidates.append(os.path.join(env_pf, "Steam"))

    for item in candidates:
        if item and os.path.exists(item):
            return os.path.normpath(item)
    return ""


def _steam_library_paths(steam_root):
    roots = []
    if not steam_root:
        return roots

    steamapps_main = os.path.join(steam_root, "steamapps")
    if os.path.isdir(steamapps_main):
        roots.append(steamapps_main)

    library_vdf = os.path.join(steamapps_main, "libraryfolders.vdf")
    if os.path.exists(library_vdf):
        try:
            with open(library_vdf, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            for raw_path in re.findall(r'"path"\s+"([^"]+)"', text):
                p = raw_path.replace("\\\\", "\\")
                steamapps_path = os.path.join(p, "steamapps")
                if os.path.isdir(steamapps_path):
                    roots.append(steamapps_path)
        except Exception:
            pass

    unique = []
    seen = set()
    for p in roots:
        norm = _normalize_path(p)
        if norm and norm not in seen:
            seen.add(norm)
            unique.append(p)
    return unique


def _parse_steam_name(acf_path):
    try:
        with open(acf_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception:
        return ""

    m = re.search(r'"name"\s+"([^"]+)"', text)
    return m.group(1).strip() if m else ""


def _scan_steam(scanner, work_folder, ignored_targets, progress_cb):
    source = str(scanner.get("source", "")).strip()
    steam_root = source or _detect_steam_root()
    if not steam_root or not os.path.isdir(steam_root):
        return 0, 0, 1, "Steam 根路径未找到"

    steamapps_dirs = _steam_library_paths(steam_root)
    if not steamapps_dirs:
        return 0, 0, 1, "Steam 库未找到"

    created = skipped = errors = 0
    scanner_name = scanner.get("name") or "Steam"

    for steamapps in steamapps_dirs:
        manifests = glob.glob(os.path.join(steamapps, "appmanifest_*.acf"))
        for manifest in manifests:
            appid_match = re.search(r"appmanifest_(\d+)\.acf$", manifest, flags=re.IGNORECASE)
            if not appid_match:
                continue

            appid = appid_match.group(1)
            app_name = _parse_steam_name(manifest) or f"SteamApp {appid}"
            run_url = f"steam://rungameid/{appid}"

            if _is_ignored(run_url, ignored_targets):
                skipped += 1
                continue

            try:
                # base name is just the app name (no scanner prefix)
                base_name = app_name
                out_path = os.path.join(work_folder, f"{_safe_name(base_name)}.url")
                if os.path.exists(out_path):
                    skipped += 1
                    continue

                _write_url_shortcut(out_path, run_url)
                created += 1
                progress_cb(f"[{scanner_name}] added: {app_name}")
            except Exception as e:
                errors += 1
                progress_cb(f"[{scanner_name}] failed: {app_name} ({e})")

    return created, skipped, errors, "Steam 扫描已完成"


def _get_epic_manifest_dirs(source):
    dirs = []
    if source:
        dirs.append(source)
    else:
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        dirs.append(os.path.join(program_data, "Epic", "EpicGamesLauncher", "Data", "Manifests"))
    return [d for d in dirs if d and os.path.isdir(d)]


def _scan_epic(scanner, work_folder, ignored_targets, progress_cb):
    source = str(scanner.get("source", "")).strip()
    manifest_dirs = _get_epic_manifest_dirs(source)
    if not manifest_dirs:
        return 0, 0, 1, "Epic 清单目录未找到"

    created = skipped = errors = 0
    scanner_name = scanner.get("name") or "Epic"

    for manifest_dir in manifest_dirs:
        for path in glob.glob(os.path.join(manifest_dir, "*.item")):
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
            except Exception:
                errors += 1
                continue

            app_name = data.get("DisplayName") or data.get("AppName") or os.path.splitext(os.path.basename(path))[0]
            launch = str(data.get("LaunchExecutable") or data.get("Executable") or "").strip()
            install = str(data.get("InstallLocation") or "").strip()

            exe_path = launch
            if exe_path and not os.path.isabs(exe_path) and install:
                exe_path = os.path.join(install, exe_path)
            exe_path = os.path.normpath(exe_path) if exe_path else ""

            if not exe_path:
                skipped += 1
                continue
            if _is_ignored(exe_path, ignored_targets):
                skipped += 1
                continue

            try:
                # use app_name directly and skip if target exists
                out_path = os.path.join(work_folder, f"{_safe_name(app_name)}.lnk")
                if os.path.exists(out_path):
                    skipped += 1
                    continue

                _create_lnk(
                    out_path,
                    target_path=exe_path,
                    working_dir=os.path.dirname(exe_path) if os.path.isabs(exe_path) else "",
                    icon_location=exe_path,
                )
                created += 1
                progress_cb(f"[{scanner_name}] added: {app_name}")
            except Exception as e:
                errors += 1
                progress_cb(f"[{scanner_name}] failed: {app_name} ({e})")

    return created, skipped, errors, "Epic 扫描已完成"


def _iter_files(source, recursive):
    if recursive:
        for root, _, files in os.walk(source):
            for name in files:
                yield os.path.join(root, name)
    else:
        for name in os.listdir(source):
            p = os.path.join(source, name)
            if os.path.isfile(p):
                yield p


def _scan_custom(scanner, work_folder, ignored_targets, progress_cb):
    source = str(scanner.get("source", "")).strip()
    if not source or not os.path.isdir(source):
        return 0, 0, 1, "Custom source folder not found"

    recursive = bool(scanner.get("recursive", True))
    include_hidden = bool(scanner.get("include_hidden", False))
    scanner_name = scanner.get("name") or "Custom"

    created = skipped = errors = 0
    for src in _iter_files(source, recursive):
        if not include_hidden and _is_hidden(src):
            continue

        ext = os.path.splitext(src)[1].lower()
        if ext not in (".exe", ".lnk", ".url"):
            continue

        if _is_ignored(src, ignored_targets):
            skipped += 1
            continue

        app_name = os.path.splitext(os.path.basename(src))[0]
        try:
            base_name = app_name
            if ext == ".exe":
                out_path = os.path.join(work_folder, f"{_safe_name(base_name)}.lnk")
                if os.path.exists(out_path):
                    skipped += 1
                    continue
                _create_lnk(
                    out_path,
                    target_path=src,
                    working_dir=os.path.dirname(src),
                    icon_location=src,
                )
            else:
                out_path = os.path.join(work_folder, f"{_safe_name(base_name)}{ext}")
                if os.path.exists(out_path):
                    skipped += 1
                    continue
                shutil.copy2(src, out_path)
            created += 1
            progress_cb(f"[{scanner_name}] added: {app_name}")
        except Exception as e:
            errors += 1
            progress_cb(f"[{scanner_name}] failed: {app_name} ({e})")

    return created, skipped, errors, "自定义扫描已完成"


def _parse_rom_extensions(value):
    text = str(value or "").strip()
    if not text:
        text = ".zip,.7z,.iso,.cue,.chd"
    exts = set()
    for part in text.split(","):
        ext = part.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = "." + ext
        exts.add(ext)
    return exts


def _scan_rom(scanner, work_folder, ignored_targets, progress_cb):
    source = str(scanner.get("source", "")).strip()
    emulator = str(scanner.get("emulator_path", "")).strip()
    if not source or not os.path.isdir(source):
        return 0, 0, 1, "ROM source folder not found"
    if not emulator:
        return 0, 0, 1, "ROM emulator path is empty"

    recursive = bool(scanner.get("recursive", True))
    include_hidden = bool(scanner.get("include_hidden", False))
    args_tpl = str(scanner.get("emulator_args", "{rom}")).strip() or "{rom}"
    exts = _parse_rom_extensions(scanner.get("rom_extensions", ""))
    scanner_name = scanner.get("name") or "ROM"

    created = skipped = errors = 0
    for src in _iter_files(source, recursive):
        if not include_hidden and _is_hidden(src):
            continue
        if os.path.splitext(src)[1].lower() not in exts:
            continue
        if _is_ignored(src, ignored_targets):
            skipped += 1
            continue

        rom_name = os.path.splitext(os.path.basename(src))[0]
        try:
            quoted_rom = f'"{src}"'
            arguments = args_tpl.replace("{rom}", quoted_rom)
            if "{rom}" not in args_tpl:
                arguments = (args_tpl + " " + quoted_rom).strip()

            base_name = rom_name
            out_path = os.path.join(work_folder, f"{_safe_name(base_name)}.lnk")
            if os.path.exists(out_path):
                skipped += 1
                continue

            _create_lnk(
                out_path,
                target_path=emulator,
                arguments=arguments,
                working_dir=os.path.dirname(emulator),
                icon_location=emulator,
            )
            created += 1
            progress_cb(f"[{scanner_name}] added: {rom_name}")
        except Exception as e:
            errors += 1
            progress_cb(f"[{scanner_name}] failed: {rom_name} ({e})")

    return created, skipped, errors, "ROM 扫描已完成"


def run_scanner(scanner, work_folder, ignored_targets, progress_cb=lambda _msg: None):
    s = normalize_scanner(scanner)
    scanner_type = s.get("type", "custom")

    if scanner_type == "steam":
        return _scan_steam(s, work_folder, ignored_targets, progress_cb)
    if scanner_type == "epic":
        return _scan_epic(s, work_folder, ignored_targets, progress_cb)
    if scanner_type == "rom":
        return _scan_rom(s, work_folder, ignored_targets, progress_cb)
    return _scan_custom(s, work_folder, ignored_targets, progress_cb)


class ScannerEditDialog(QtWidgets.QDialog):
    def __init__(self, scanner, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑扫描器")
        self.setModal(True)
        self.resize(520, 380)
        self.scanner = normalize_scanner(scanner)

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.name_input = QtWidgets.QLineEdit(self.scanner.get("name", ""))
        form.addRow("名称：", self.name_input)

        self.type_lbl = QtWidgets.QLabel(SCANNER_TYPE_LABELS.get(self.scanner.get("type"), self.scanner.get("type", "")))
        form.addRow("类型：", self.type_lbl)

        self.source_input = QtWidgets.QLineEdit(self.scanner.get("source", ""))
        # if the user clears the name and then changes the source we can suggest a name again
        self.source_input.textChanged.connect(self._on_source_changed)
        form.addRow("源路径：", self.source_input)

        self.enabled_chk = QtWidgets.QCheckBox("已启用")
        self.enabled_chk.setChecked(bool(self.scanner.get("enabled", True)))
        form.addRow("", self.enabled_chk)

        self.recursive_chk = QtWidgets.QCheckBox("递归")
        self.recursive_chk.setChecked(bool(self.scanner.get("recursive", True)))
        form.addRow("", self.recursive_chk)

        self.hidden_chk = QtWidgets.QCheckBox("包含隐藏")
        self.hidden_chk.setChecked(bool(self.scanner.get("include_hidden", False)))
        form.addRow("", self.hidden_chk)

        self.emulator_input = QtWidgets.QLineEdit(self.scanner.get("emulator_path", ""))
        form.addRow("模拟器：", self.emulator_input)

        self.args_input = QtWidgets.QLineEdit(self.scanner.get("emulator_args", "{rom}"))
        form.addRow("参数：", self.args_input)

        self.ext_input = QtWidgets.QLineEdit(self.scanner.get("rom_extensions", ""))
        form.addRow("ROM 扩展名：", self.ext_input)

        layout.addLayout(form)
        layout.addStretch()

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch()
        ok_btn = QtWidgets.QPushButton("保存")
        cancel_btn = QtWidgets.QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

        self._apply_type_visibility()

    def _apply_type_visibility(self):
        scanner_type = self.scanner.get("type")
        rom_mode = scanner_type == "rom"
        self.emulator_input.setEnabled(rom_mode)
        self.args_input.setEnabled(rom_mode)
        self.ext_input.setEnabled(rom_mode)

    def _auto_fill_name(self):
        """Suggest a name when the name field is currently blank."""
        scanner_type = self.scanner.get("type")
        source = self.source_input.text().strip()
        name = ""
        if scanner_type == "steam":
            name = "Steam 库"
            if source:
                base = os.path.basename(source.rstrip("\\/"))
                if base:
                    name = f"Steam 库 ({base})"
        elif scanner_type == "epic":
            name = "Epic 清单"
            if source:
                base = os.path.basename(source.rstrip("\\/"))
                if base:
                    name = f"Epic 清单 ({base})"
        elif scanner_type == "rom":
            if source:
                name = os.path.basename(source.rstrip("\\/"))
            else:
                name = "ROM 扫描器"
        else:
            if source:
                name = os.path.basename(source.rstrip("\\/"))
            else:
                name = "自定义文件夹"

        if name and not self.name_input.text().strip():
            self.name_input.setText(name)

    def _on_source_changed(self, text):
        if not self.name_input.text().strip():
            self._auto_fill_name()

    def updated_scanner(self):
        out = dict(self.scanner)
        out["name"] = self.name_input.text().strip() or out.get("name", "")
        out["source"] = self.source_input.text().strip()
        out["enabled"] = self.enabled_chk.isChecked()
        out["recursive"] = self.recursive_chk.isChecked()
        out["include_hidden"] = self.hidden_chk.isChecked()
        out["emulator_path"] = self.emulator_input.text().strip()
        out["emulator_args"] = self.args_input.text().strip() or "{rom}"
        out["rom_extensions"] = self.ext_input.text().strip()
        return normalize_scanner(out)


class ScannerManagePage(QtWidgets.QWidget):
    scan_log = QtCore.pyqtSignal(str)
    scan_finished = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._run_buttons = []
        self.scanners = []
        self._setup_ui()
        self.scan_log.connect(self._append_log)
        self.scan_finished.connect(self._on_scan_finished)
        self.reload_scanners()

    def _setup_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QtWidgets.QLabel("扫描器管理")
        title.setFont(QtGui.QFont("Segoe UI", 16, QtGui.QFont.Bold))
        root.addWidget(title)

        desc = QtWidgets.QLabel(
            "管理扫描器预设，并与现有的忽略列表不並执行扫描。"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#555;")
        root.addWidget(desc)

        controls = QtWidgets.QHBoxLayout()
        self.refresh_btn = QtWidgets.QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.reload_scanners)
        controls.addWidget(self.refresh_btn)

        self.run_selected_btn = QtWidgets.QPushButton("运行已选中")
        self.run_selected_btn.clicked.connect(self.run_selected)
        controls.addWidget(self.run_selected_btn)

        self.run_enabled_btn = QtWidgets.QPushButton("运行已启用")
        self.run_enabled_btn.clicked.connect(self.run_enabled)
        controls.addWidget(self.run_enabled_btn)

        self.toggle_btn = QtWidgets.QPushButton("切换启用")
        self.toggle_btn.clicked.connect(self.toggle_selected_enabled)
        controls.addWidget(self.toggle_btn)

        self.edit_btn = QtWidgets.QPushButton("编辑")
        self.edit_btn.clicked.connect(self.edit_selected)
        controls.addWidget(self.edit_btn)

        self.delete_btn = QtWidgets.QPushButton("删除")
        self.delete_btn.clicked.connect(self.delete_selected)
        controls.addWidget(self.delete_btn)

        controls.addStretch()
        root.addLayout(controls)

        self._run_buttons = [self.run_selected_btn, self.run_enabled_btn]

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["名称", "类型", "源路径", "已启用", "上一次运行", "上次结果"])
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)
        root.addWidget(self.table, 1)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color:#2E7D9B;")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        root.addWidget(self.log_text)

    def _append_log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{stamp}] {message}")
        self.status_label.setText(message)

    def _selected_rows(self):
        rows = set()
        for item in self.table.selectedItems():
            rows.add(item.row())
        return sorted(rows)

    def _selected_scanners(self):
        scanners = []
        for row in self._selected_rows():
            if 0 <= row < len(self.scanners):
                scanners.append(self.scanners[row])
        return scanners

    def reload_scanners(self):
        self.scanners = load_scanners()
        self.table.setRowCount(0)

        for row, scanner in enumerate(self.scanners):
            self.table.insertRow(row)
            t = SCANNER_TYPE_LABELS.get(scanner.get("type"), scanner.get("type", ""))
            enabled_text = "Yes" if scanner.get("enabled", True) else "No"

            values = [
                scanner.get("name", ""),
                t,
                scanner.get("source", ""),
                enabled_text,
                scanner.get("last_run", ""),
                scanner.get("last_result", ""),
            ]
            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setData(QtCore.Qt.UserRole, scanner.get("id"))
                self.table.setItem(row, col, item)

        self.status_label.setText(f"已加载扫描器：{len(self.scanners)}")

    def toggle_selected_enabled(self):
        rows = self._selected_rows()
        if not rows:
            self.status_label.setText("请选择至少一个扫描器。")
            return

        for row in rows:
            self.scanners[row]["enabled"] = not bool(self.scanners[row].get("enabled", True))
        save_scanners(self.scanners)
        self.reload_scanners()

    def edit_selected(self):
        rows = self._selected_rows()
        if len(rows) != 1:
            self.status_label.setText("请恰好选择一个扫描器进行编辑。")
            return

        row = rows[0]
        scanner = self.scanners[row]
        dlg = ScannerEditDialog(scanner, self)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return

        self.scanners[row] = dlg.updated_scanner()
        save_scanners(self.scanners)
        self.reload_scanners()
        self.status_label.setText(f"已更新扫描器：{self.scanners[row].get('name', '')}")

    def delete_selected(self):
        rows = self._selected_rows()
        if not rows:
            self.status_label.setText("请选择至少一个扫描器进行删除。")
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "删除扫描器",
            f"删除 {len(rows)} 个已选中的扫描器？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        keep = [s for i, s in enumerate(self.scanners) if i not in set(rows)]
        save_scanners(keep)
        self.reload_scanners()

    def run_selected(self):
        scanners = self._selected_scanners()
        if not scanners:
            self.status_label.setText("请选择至少一个扫描器进行运行。")
            return
        self._start_scan(scanners)

    def run_enabled(self):
        scanners = [s for s in self.scanners if s.get("enabled", True)]
        if not scanners:
            self.status_label.setText("没有已启用的扫描器可运行。")
            return
        self._start_scan(scanners)

    def _set_running(self, running):
        self._running = running
        for btn in self._run_buttons:
            btn.setEnabled(not running)

    def _start_scan(self, scanners):
        if self._running:
            self.status_label.setText("扫描已在运行中。")
            return

        self._set_running(True)
        self.scan_log.emit(f"开始为 {len(scanners)} 个扫描器运行扫描...")  

        def worker():
            summary = {
                "scanner_count": len(scanners),
                "created": 0,
                "skipped": 0,
                "errors": 0,
                "work_folder": "",
            }

            all_scanners = load_scanners()
            scanner_map = {s.get("id"): s for s in all_scanners}

            try:
                ignored_targets = _load_ignored_targets()
                work_folder = _get_work_folder()
                summary["work_folder"] = work_folder

                for scanner in scanners:
                    sid = scanner.get("id")
                    current = scanner_map.get(sid, scanner)
                    name = current.get("name", "Unnamed")
                    self.scan_log.emit(f"Running scanner: {name}")

                    created, skipped, errors, note = run_scanner(
                        current,
                        work_folder,
                        ignored_targets,
                        progress_cb=lambda msg: self.scan_log.emit(msg),
                    )

                    summary["created"] += int(created)
                    summary["skipped"] += int(skipped)
                    summary["errors"] += int(errors)

                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    current["last_run"] = now
                    current["last_result"] = f"Created {created}, Skipped {skipped}, Errors {errors} ({note})"
                    scanner_map[sid] = normalize_scanner(current)

                    self.scan_log.emit(
                        f"{name} finished: created={created}, skipped={skipped}, errors={errors}"
                    )

                save_scanners(list(scanner_map.values()))
            except Exception as e:
                summary["errors"] += 1
                self.scan_log.emit(f"Scan failed: {e}")

            self.scan_finished.emit(summary)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_scan_finished(self, summary):
        self._set_running(False)
        self.reload_scanners()

        created = summary.get("created", 0)
        skipped = summary.get("skipped", 0)
        errors = summary.get("errors", 0)
        scanners = summary.get("scanner_count", 0)
        work_folder = summary.get("work_folder", "")

        self.status_label.setText(
            f"扫描完成。扫描器={scanners}，已创建={created}，已跳过={skipped}，错误={errors}，输出={work_folder}"
        )
