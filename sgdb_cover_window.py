import os
import sys
import time
import threading
import webbrowser
from io import BytesIO
from urllib.parse import quote

import requests
from PIL import Image
from PyQt5 import QtCore, QtGui, QtWidgets


SGDB_API_BASE_URL = "https://www.steamgriddb.com/api/v2"
DEFAULT_SGDB_API_KEY = "1b378d4482f7088146d2f7e320139b74"


def _get_sgdb_api_key():
    env_key = os.environ.get("QSAA_SGDB_API_KEY") or os.environ.get("STEAMGRIDDB_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()
    return DEFAULT_SGDB_API_KEY


def _get_sgdb_network_options():
    use_system_proxy = False
    proxy_url = ""

    env_use_system = os.environ.get("QSAA_SGDB_USE_SYSTEM_PROXY", "").strip().lower()
    if env_use_system in ("1", "true", "yes", "on"):
        use_system_proxy = True

    env_proxy = os.environ.get("QSAA_SGDB_PROXY", "").strip()
    if env_proxy:
        proxy_url = env_proxy

    return {
        "use_system_proxy": use_system_proxy,
        "proxy_url": proxy_url,
    }


class SteamGridDBApiClient:
    def __init__(self, api_key, timeout=(8, 20), use_system_proxy=False, proxy_url=""):
        self.base_url = SGDB_API_BASE_URL
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = bool(use_system_proxy)
        if proxy_url:
            self.session.proxies.update({
                "http": proxy_url,
                "https": proxy_url,
            })
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Steam-ROM-Manager/2.5 (QSAA)",
        })

    def _request(self, url, timeout=None):
        last_error = None
        request_timeout = timeout or self.timeout

        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=request_timeout)
                resp.raise_for_status()
                return resp
            except requests.exceptions.ProxyError as e:
                last_error = e
                if attempt == 0 and self.session.proxies:
                    self.session.proxies.clear()
                    continue
                if attempt <= 1 and self.session.trust_env:
                    self.session.trust_env = False
                    continue
                raise
            except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) as e:
                last_error = e
                if attempt < 2:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError("SGDB request failed unexpectedly")

    def search_game(self, name):
        query = (name or "").strip()
        if not query:
            return []
        url = f"{self.base_url}/search/autocomplete/{quote(query)}"
        payload = self._request(url, timeout=(8, 25)).json()
        data = payload.get("data") if isinstance(payload, dict) else []
        return data if isinstance(data, list) else []

    def get_grids(self, game_id):
        gid = int(game_id)
        url = f"{self.base_url}/grids/game/{gid}?types=static&dimensions=600x900"
        payload = self._request(url, timeout=(8, 25)).json()
        data = payload.get("data") if isinstance(payload, dict) else []
        return data if isinstance(data, list) else []


def _download_cdn_bytes(url, sgdb_client, timeout=(8, 30)):
    if not url:
        return None

    image_session = requests.Session()
    image_session.trust_env = sgdb_client.session.trust_env
    if sgdb_client.session.proxies:
        image_session.proxies.update(sgdb_client.session.proxies)
    image_session.headers.update({
        "User-Agent": sgdb_client.session.headers.get("User-Agent", "QSAA"),
        "Accept": "image/*,*/*;q=0.8",
        "Referer": "https://www.steamgriddb.com/",
    })

    last_error = None
    for attempt in range(3):
        try:
            resp = image_session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except requests.exceptions.ProxyError as e:
            last_error = e
            if attempt == 0 and image_session.proxies:
                image_session.proxies.clear()
                continue
            if attempt <= 1 and image_session.trust_env:
                image_session.trust_env = False
                continue
            raise
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout) as e:
            last_error = e
            if attempt < 2:
                time.sleep(0.4 * (attempt + 1))
                continue
            raise

    if last_error:
        raise last_error
    return None


def _prepare_cover_bytes(raw_bytes):
    if not raw_bytes:
        return None
    with Image.open(BytesIO(raw_bytes)) as image:
        image = image.convert("RGB")
        if image.size != (600, 900):
            image = image.resize((600, 900), Image.LANCZOS)
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


def _resolve_exe_path(exe_path):
    path = (exe_path or "").strip().strip('"')
    if not path:
        return None
    if not os.path.exists(path):
        return path

    lower = path.lower()
    if lower.endswith(".lnk"):
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(path)
            target = (shortcut.TargetPath or "").strip()
            return target or path
        except Exception:
            return path
    if lower.endswith(".url"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("IconFile="):
                        return line.split("=", 1)[1].strip()
        except Exception:
            return path
    return path


class SgdbCoverPickerDialog(QtWidgets.QDialog):
    search_done = QtCore.pyqtSignal(int, object, str)
    search_error = QtCore.pyqtSignal(int, str)
    grids_done = QtCore.pyqtSignal(int, object, str)
    grids_error = QtCore.pyqtSignal(int, str)
    thumb_done = QtCore.pyqtSignal(int, int, object)
    thumb_error = QtCore.pyqtSignal(int, int, str)
    cover_saved = QtCore.pyqtSignal(object, object)
    cover_error = QtCore.pyqtSignal(str)

    def __init__(self, app_name, output_path, exe_path=None, remaining_games=None, parent=None):
        super().__init__(parent)
        self.app_name = app_name
        self.output_path = output_path
        self.exe_path = exe_path
        self.remaining_games = remaining_games

        self.result_bytes = None
        self.result_sgdb_name = None
        self.used_icon = False
        self.selected_game_name = None
        self._search_token = 0
        self._grid_token = 0
        self._thumb_total = 0
        self._thumb_loaded = 0
        self._grid_buttons = []
        self._grid_data = []
        self._all_search_games = []
        self._clipboard_hint_window = None

        net = _get_sgdb_network_options()
        self.sgdb = SteamGridDBApiClient(
            _get_sgdb_api_key(),
            use_system_proxy=net["use_system_proxy"],
            proxy_url=net["proxy_url"],
        )
        self.net_mode = net["proxy_url"] or ("system-proxy" if net["use_system_proxy"] else "direct")

        self.parent_dir_name = None
        resolved = _resolve_exe_path(exe_path)
        if resolved:
            try:
                self.parent_dir_name = os.path.basename(os.path.dirname(resolved)) or None
            except Exception:
                self.parent_dir_name = None

        self._setup_ui()
        self._bind_signals()
        self._start_search(self.app_name)

    def _setup_ui(self):
        self.setWindowTitle(self.tr("SGDB封面选择 - %1").arg(self.app_name))
        self.resize(900, 480)

        main = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel(self.tr("SGDB搜索:")))
        self.search_edit = QtWidgets.QLineEdit(self.app_name)
        self.search_edit.returnPressed.connect(lambda: self._start_search(self.search_edit.text().strip()))
        top.addWidget(self.search_edit, 1)

        self.search_btn = QtWidgets.QPushButton(self.tr("搜索"))
        self.search_btn.clicked.connect(lambda: self._start_search(self.search_edit.text().strip()))
        top.addWidget(self.search_btn)
        main.addLayout(top)

        split = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main.addWidget(split, 1)

        left = QtWidgets.QWidget()
        left_l = QtWidgets.QVBoxLayout(left)
        left_l.addWidget(QtWidgets.QLabel(self.tr("搜索结果:")))
        self.game_list = QtWidgets.QListWidget()
        self.game_list.itemDoubleClicked.connect(lambda _: self._load_selected_game_grids())
        self.game_list.itemClicked.connect(lambda _: self._load_selected_game_grids())
        left_l.addWidget(self.game_list, 1)

        self.apply_name_chk = QtWidgets.QCheckBox(self.tr("将SGDB游戏名称应用至本地"))
        self.apply_name_chk.setChecked(True)
        left_l.addWidget(self.apply_name_chk)
        split.addWidget(left)

        right = QtWidgets.QWidget()
        right_l = QtWidgets.QVBoxLayout(right)
        right_l.addWidget(QtWidgets.QLabel(self.tr("封面候选:")))
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        # 启用触摸滚动支持
        QtWidgets.QScroller.grabGesture(self.scroll.viewport(), QtWidgets.QScroller.TouchGesture)
        self.thumb_wrap = QtWidgets.QWidget()
        self.thumb_grid = QtWidgets.QGridLayout(self.thumb_wrap)
        self.thumb_grid.setContentsMargins(8, 8, 8, 8)
        self.thumb_grid.setSpacing(10)
        self.scroll.setWidget(self.thumb_wrap)
        right_l.addWidget(self.scroll, 1)
        split.addWidget(right)
        split.setSizes([340, 640])

        if isinstance(self.remaining_games, int) and self.remaining_games > 1:
            main.addWidget(QtWidgets.QLabel(self.tr("剩余待选封面: %1 个").arg(str(self.remaining_games))))

        self.status_label = QtWidgets.QLabel(f"网络模式: {self.net_mode}")
        self.status_label.setStyleSheet("color:#2E7D9B;")
        main.addWidget(self.status_label)

        bottom = QtWidgets.QHBoxLayout()
        bottom.addStretch()
        self.sgdb_btn = QtWidgets.QPushButton(self.tr("查看SGDB网页"))
        self.sgdb_btn.clicked.connect(self._open_sgdb_page)
        bottom.addWidget(self.sgdb_btn)
        self.browser_btn = QtWidgets.QPushButton(self.tr("在浏览器中查找"))
        self.browser_btn.clicked.connect(self._open_browser_search_helper)
        bottom.addWidget(self.browser_btn)

        self.local_btn = QtWidgets.QPushButton(self.tr("选择本地图片"))
        self.local_btn.clicked.connect(self._select_local_image)
        bottom.addWidget(self.local_btn)

        cancel_btn = QtWidgets.QPushButton(self.tr("关闭"))
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        main.addLayout(bottom)

    def _bind_signals(self):
        self.search_done.connect(self._on_search_done)
        self.search_error.connect(self._on_search_error)
        self.grids_done.connect(self._on_grids_done)
        self.grids_error.connect(self._on_grids_error)
        self.thumb_done.connect(self._on_thumb_done)
        self.thumb_error.connect(self._on_thumb_error)
        self.cover_saved.connect(self._on_cover_saved)
        self.cover_error.connect(self._on_cover_error)

    def _run_thread(self, fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()

    def _set_status(self, text):
        self.status_label.setText(text)

    def _open_browser_search_helper(self):
        name = (self.search_edit.text() or "").strip() or (self.app_name or "").strip()
        if not name:
            self._set_status(self.tr("请输入游戏名称后再在浏览器中查找"))
            return

        try:
            query = quote(name)
            url = f"https://www.bing.com/images/search?q={query}"
            webbrowser.open(url)
        except Exception as e:
            self._set_status(self.tr("打开浏览器失败: %1").arg(str(e)))
            return

        hint = ClipboardCoverHintWindow(self)
        self._clipboard_hint_window = hint
        hint.show()

    def _open_sgdb_page(self):
        name = (self.search_edit.text() or "").strip() or (self.app_name or "").strip()
        if not name:
            self._set_status(self.tr("请输入游戏名称后再查看SGDB网页"))
            return

        # 检查是否有选中的游戏
        item = self.game_list.currentItem()
        if item:
            payload = item.data(QtCore.Qt.UserRole) or {}
            game_id = payload.get("id")
            if game_id:
                url = f"https://www.steamgriddb.com/game/{game_id}"
            else:
                url = f"https://www.steamgriddb.com/search/grids?term={quote(name)}"
        else:
            url = f"https://www.steamgriddb.com/search/grids?term={quote(name)}"

        try:
            webbrowser.open(url)
        except Exception as e:
            self._set_status(self.tr("打开浏览器失败: %1").arg(str(e)))
            return

        hint = ClipboardCoverHintWindow(self)
        self._clipboard_hint_window = hint
        hint.show()

    def _start_search(self, keyword):
        name = (keyword or "").strip()
        if not name:
            self._set_status(self.tr("请输入游戏名称"))
            return

        self._search_token += 1
        token = self._search_token
        self._set_status(self.tr("正在搜索: %1").arg(name))
        self.game_list.clear()
        self._clear_thumbs()

        def worker():
            try:
                games = self.sgdb.search_game(name)
                self.search_done.emit(token, games, name)
            except Exception as e:
                self.search_error.emit(token, str(e))

        self._run_thread(worker)

    @QtCore.pyqtSlot(int, object, str)
    def _on_search_done(self, token, games, query_name):
        if token != self._search_token:
            return

        self._all_search_games = games if isinstance(games, list) else []
        self.game_list.clear()
        for game in self._all_search_games:
            item = QtWidgets.QListWidgetItem(f"{game.get('name', 'Unknown')} (ID: {game.get('id')})")
            item.setData(QtCore.Qt.UserRole, game)
            self.game_list.addItem(item)

        if self.parent_dir_name and _normalize_text(self.parent_dir_name) != _normalize_text(query_name):
            item = QtWidgets.QListWidgetItem(self.tr("使用 %1 搜索").arg(self.parent_dir_name))
            item.setData(QtCore.Qt.UserRole, {"use_parent_search": True})
            self.game_list.addItem(item)

        if self.game_list.count() == 0:
            self._set_status(self.tr("未找到搜索结果: %1").arg(query_name))
            return

        self.game_list.setCurrentRow(0)
        self._set_status(self.tr("搜索完成: %1，共 %2 条").arg(query_name).arg(str(len(self._all_search_games))))
        self._load_selected_game_grids()

    @QtCore.pyqtSlot(int, str)
    def _on_search_error(self, token, message):
        if token != self._search_token:
            return
        self._set_status(self.tr("搜索失败: %1").arg(message))

    def _load_selected_game_grids(self):
        item = self.game_list.currentItem()
        if item is None:
            return
        payload = item.data(QtCore.Qt.UserRole) or {}

        if payload.get("use_parent_search"):
            self.search_edit.setText(self.parent_dir_name or "")
            self._start_search(self.parent_dir_name or "")
            return

        game_id = payload.get("id")
        self.selected_game_name = payload.get("name")
        if not game_id:
            self._set_status(self.tr("无效游戏ID"))
            return

        self._grid_token += 1
        token = self._grid_token
        self._set_status(self.tr("正在获取封面: %1").arg(self.selected_game_name))
        self._clear_thumbs()

        def worker():
            try:
                grids = self.sgdb.get_grids(game_id)
                self.grids_done.emit(token, grids, self.selected_game_name or "")
            except Exception as e:
                self.grids_error.emit(token, str(e))

        self._run_thread(worker)

    @QtCore.pyqtSlot(int, object, str)
    def _on_grids_done(self, token, grids, game_name):
        if token != self._grid_token:
            return

        self._grid_data = [g for g in (grids or []) if isinstance(g, dict) and (g.get("thumb") or g.get("url"))][:12]
        self._thumb_total = len(self._grid_data)
        self._thumb_loaded = 0
        self._grid_buttons = []
        self._clear_thumbs()

        if not self._grid_data:
            self._set_status(self.tr("未找到封面: %1").arg(game_name))
            return

        for idx, grid in enumerate(self._grid_data):
            btn = QtWidgets.QPushButton(self.tr("加载中..."))
            btn.setFixedSize(120, 180)
            btn.setEnabled(False)
            btn.clicked.connect(lambda _, i=idx: self._select_grid(i))
            self.thumb_grid.addWidget(btn, idx // 4, idx % 4)
            self._grid_buttons.append(btn)
            self._start_load_thumb(token, idx, grid)

        self._set_status(self.tr("正在加载缩略图: 0/%1").arg(str(self._thumb_total)))

    @QtCore.pyqtSlot(int, str)
    def _on_grids_error(self, token, message):
        if token != self._grid_token:
            return
        self._set_status(self.tr("获取封面失败: %1").arg(message))

    def _start_load_thumb(self, token, idx, grid):
        thumb_url = grid.get("url") or grid.get("thumb")

        def worker():
            try:
                raw = _download_cdn_bytes(thumb_url, self.sgdb, timeout=(8, 20))
                if raw:
                    grid['cached_bytes'] = raw  # 缓存下载的字节
                    pix = QtGui.QPixmap()
                    if pix.loadFromData(raw):
                        self.thumb_done.emit(token, idx, pix)
                    else:
                        self.thumb_error.emit(token, idx, self.tr("无法解码图片"))
                else:
                    self.thumb_error.emit(token, idx, self.tr("下载失败"))
            except Exception as e:
                self.thumb_error.emit(token, idx, str(e))

        self._run_thread(worker)

    @QtCore.pyqtSlot(int, int, object)
    def _on_thumb_done(self, token, idx, pix):
        if token != self._grid_token or idx >= len(self._grid_buttons):
            return
        btn = self._grid_buttons[idx]
        btn.setIcon(QtGui.QIcon(pix))
        btn.setIconSize(QtCore.QSize(110, 165))
        btn.setText("")
        btn.setEnabled(True)
        self._thumb_loaded += 1
        self._set_status(self.tr("正在加载缩略图: %1/%2").arg(str(self._thumb_loaded)).arg(str(self._thumb_total)))

    @QtCore.pyqtSlot(int, int, str)
    def _on_thumb_error(self, token, idx, message):
        if token != self._grid_token or idx >= len(self._grid_buttons):
            return
        btn = self._grid_buttons[idx]
        btn.setText(self.tr("加载失败"))
        btn.setEnabled(False)
        self._thumb_loaded += 1
        self._set_status(self.tr("缩略图加载异常(%1/%2): %3").arg(str(self._thumb_loaded)).arg(str(self._thumb_total)).arg(message))

    def _select_grid(self, idx):
        if idx >= len(self._grid_data):
            return
        grid = self._grid_data[idx]
        self._set_status(self.tr("正在下载封面: %1").arg(self.selected_game_name or self.app_name))

        # 使用缓存的字节，如果有的话
        cached_raw = grid.get('cached_bytes')
        if cached_raw:
            try:
                final_bytes = _prepare_cover_bytes(cached_raw)
                if final_bytes:
                    sgdb_name = self.selected_game_name if self.apply_name_chk.isChecked() and self.selected_game_name else None
                    self.cover_saved.emit(final_bytes, sgdb_name)
                    return
            except Exception as e:
                self.cover_error.emit(str(e))
                return

        # 如果没有缓存，下载
        candidate_urls = [grid.get("url"), grid.get("thumb")]

        def worker():
            try:
                final_bytes = None
                for url in candidate_urls:
                    if not url:
                        continue
                    try:
                        raw = _download_cdn_bytes(url, self.sgdb, timeout=(8, 30))
                        final_bytes = _prepare_cover_bytes(raw)
                        if final_bytes:
                            break
                    except Exception:
                        continue
                if not final_bytes:
                    raise RuntimeError(self.tr("封面下载失败，url/thumb 均不可用"))

                sgdb_name = self.selected_game_name if self.apply_name_chk.isChecked() and self.selected_game_name else None
                self.cover_saved.emit(final_bytes, sgdb_name)
            except Exception as e:
                self.cover_error.emit(str(e))

        self._run_thread(worker)

    @QtCore.pyqtSlot(object, object)
    def _on_cover_saved(self, output_path, sgdb_name):
        self.result_bytes = output_path  # 这里output_path实际上是bytes
        self.result_sgdb_name = sgdb_name
        self.used_icon = False
        self.accept()

    @QtCore.pyqtSlot(str)
    def _on_cover_error(self, message):
        self._set_status(self.tr("封面保存失败: %1").arg(message))

    def _select_local_image(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            self.tr("选择本地图片"),
            "",
            self.tr("图片文件 (*.jpg *.jpeg *.png *.bmp *.gif);;所有文件 (*.*)")
        )
        if not file_path:
            return

        try:
            with Image.open(file_path) as local_image:
                if local_image.mode != "RGB":
                    local_image = local_image.convert("RGB")
                target_size = (600, 900)
                scale = max(target_size[0] / local_image.width, target_size[1] / local_image.height)
                new_size = (int(local_image.width * scale), int(local_image.height * scale))
                local_image = local_image.resize(new_size, Image.LANCZOS)

                x = max(0, (local_image.width - target_size[0]) // 2)
                y = max(0, (local_image.height - target_size[1]) // 2)
                final_image = local_image.crop((x, y, x + target_size[0], y + target_size[1]))

                output = BytesIO()
                final_image.save(output, "PNG")
                final_bytes = output.getvalue()

            self.result_bytes = final_bytes
            self.result_sgdb_name = self.selected_game_name if self.apply_name_chk.isChecked() and self.selected_game_name else None
            self.used_icon = False
            self.accept()
        except Exception as e:
            self._set_status(self.tr("处理本地图片失败: %1").arg(str(e)))

    def _clear_thumbs(self):
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._grid_buttons = []


def _normalize_text(value):
    return " ".join(str(value or "").strip().lower().split())


class ClipboardCoverHintWindow(QtWidgets.QDialog):
    def __init__(self, parent_dialog: "SgdbCoverPickerDialog"):
        super().__init__(parent_dialog)
        self.parent_dialog = parent_dialog
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setWindowOpacity(0.9)
        self.setModal(False)

        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(
            self.tr("请在浏览器中找到合适的封面图片并复制到剪贴板，然后点击下方按钮从剪贴板读取图像作为封面。")
        )
        label.setWordWrap(True)
        layout.addWidget(label)

        btn = QtWidgets.QPushButton(self.tr("读取剪贴板中图像并使用为封面"))
        btn.setFixedHeight(40)
        btn.clicked.connect(self._read_clipboard_image)
        layout.addWidget(btn)

        cancel_btn = QtWidgets.QPushButton(self.tr("取消"))
        cancel_btn.setFixedHeight(40)
        cancel_btn.clicked.connect(self.close)
        layout.addWidget(cancel_btn)

        self.adjustSize()
        self._move_to_top_center()

    def _move_to_top_center(self):
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + 10
        self.move(x, y)

    def _read_clipboard_image(self):
        cb = QtWidgets.QApplication.clipboard()
        img = cb.image()
        if img.isNull():
            pix = cb.pixmap()
            if not pix.isNull():
                img = pix.toImage()

        if img.isNull():
            self.parent_dialog._set_status(self.tr("剪贴板中未检测到图像，请先在浏览器中复制图片"))
            return

        try:
            buffer = QtCore.QBuffer()
            buffer.open(QtCore.QIODevice.WriteOnly)
            img.save(buffer, "PNG")
            data = bytes(buffer.data())

            with Image.open(BytesIO(data)) as pil_image:
                if pil_image.mode != "RGB":
                    pil_image = pil_image.convert("RGB")
                target_size = (600, 900)
                scale = max(target_size[0] / pil_image.width, target_size[1] / pil_image.height)
                new_size = (int(pil_image.width * scale), int(pil_image.height * scale))
                pil_image = pil_image.resize(new_size, Image.LANCZOS)

                x = max(0, (pil_image.width - target_size[0]) // 2)
                y = max(0, (pil_image.height - target_size[1]) // 2)
                final_image = pil_image.crop((x, y, x + target_size[0], y + target_size[1]))

                output = BytesIO()
                final_image.save(output, "PNG")
                final_bytes = output.getvalue()

            self.parent_dialog.result_bytes = final_bytes
            self.parent_dialog.result_sgdb_name = (
                self.parent_dialog.selected_game_name
                if self.parent_dialog.apply_name_chk.isChecked()
                and self.parent_dialog.selected_game_name
                else None
            )
            self.parent_dialog.used_icon = False
            self.parent_dialog.accept()
            self.close()
        except Exception as e:
            self.parent_dialog._set_status(self.tr("读取剪贴板图像失败: %1").arg(str(e)))

def choose_cover_with_sgdb_qt(app_name, output_path, exe_path=None, remaining_games=None):
    app = QtWidgets.QApplication.instance()
    created = False
    if app is None:
        app = QtWidgets.QApplication(sys.argv[:1])
        created = True

    dlg = SgdbCoverPickerDialog(
        app_name=app_name,
        output_path=output_path,
        exe_path=exe_path,
        remaining_games=remaining_games,
    )
    accepted = dlg.exec_() == QtWidgets.QDialog.Accepted

    result = (dlg.result_bytes if accepted else None, dlg.used_icon, dlg.result_sgdb_name)

    if created:
        app.quit()
    return result