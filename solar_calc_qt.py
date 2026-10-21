"""solar_calc_qt.py  v1.11.0
Главное окно программы (PySide6): боковая панель, страницы, лог, статус.

Журнал:
v1.11.0: страница «🔄 Обновление» (общий модуль gh_update: токен, ветка, автопроверка, «Что нового», перезапуск) —
         внизу боковой панели над «🎨 Цвета»; создаётся при запуске (автопроверка идёт сама); новая версия —
         «⬆» на кнопке страницы и «⬆ X.Y.Z» в строке состояния (клик — открыть страницу).
v1.10.0: страница «💰 Зелёный тариф» (окупаемость, смета, ОСР, солнце за 5 лет, документы) — после «🔌 Горсеть»;
         пересчёт, тема, профиль и сброс обновляют её. Страница «🔀 Сравнение схем S×P» убрана.
v1.9.7: профиль и config с BOM (Блокнот) открываются; «Настройки сохранены» — только если сохранились; смена
        темы перерисовывает текущую страницу (схемы, угол, провод, погода); сохранить без расширения — добавит
        его; ошибки интерфейса — с трассировкой в файле лога; ручка переключателей — белая в обеих темах.
v1.9.4: погода «📍 Регион 5 лет»: выбрана, а данных для точки нет — загрузка сама (один раз на точку).
v1.9.0: тема и итог расчёта обновляют холст конструктора станции.
v1.5.0: без изменений окна — версия поднята вместе с программой (база панелей, выбор серии, поиск).
v1.4.0: страницы «🌤 Погода» (погода + выработка по прогнозу) и «🌌 Небо», опрос погоды, разделитель
        в боковой панели по имени страницы.
v1.3.0: вынесено из solar_calc.pyw v1.2.1; страницы — миксины из modules/mod_page_*.py.
"""
import base64
import json
import logging
import queue
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QByteArray
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QToolButton, QButtonGroup,
                               QHBoxLayout, QVBoxLayout, QGridLayout, QStackedWidget, QSplitter, QScrollArea,
                               QPlainTextEdit, QMenu, QMessageBox, QFileDialog, QPushButton)

from modules.mod_base import APP_ROOT, MONTHS, WEATHER, _DONE, UIQ, log, Worker
from modules.mod_sun import SunData
from modules.mod_config import DEFAULT_SYS, clean_sys, load_config, save_config
from modules.mod_model import compute_all
from modules.mod_theme import _QT_THEMES, _OK, _ERR, _WARN, _qss
from modules.mod_widgets import app_name, app_version, Segmented, NoWheelCombo, _lab, _card, _save_failed, ask_save

from modules.mod_page_settings import SettingsPage
from modules.mod_page_results import ResultsPages
from modules.mod_page_tools import ToolPages
from modules.mod_page_sky import SkyPages
from modules.mod_page_green import GreenPages
from modules.mod_weather import WeatherState
from modules import gh_update, gh_update_qt


class App(SettingsPage, ResultsPages, ToolPages, SkyPages, GreenPages, QMainWindow):
    """Главное окно: каркас, пересчёт, тема, лог, профили. Страницы — в modules/mod_page_*.py."""

    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.s = self.cfg["sys"]
        self.sd = SunData(self.cfg)
        self._reg_tried = set()                          # точки, для которых погода региона уже запрашивалась
        self.R = None
        self.gen = 0
        self.page_gen = {}
        self.w = {}
        self.rows = {}           # ключ поля → [подпись, виджет] (для скрытия строк)
        self.cards = {}          # заголовок → карточка
        self.toggles = []
        self.charts = []
        self.worker = Worker()
        self.wx = WeatherState()
        self.wx.apply(dict(on=bool(self.cfg["weather"]["on"]), model=self.cfg["weather"]["model"]))
        self._recalc_timer = QTimer(self)
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.timeout.connect(self.recalc)
        self.setWindowTitle(f"{app_name()} — v{app_version()} · Qt6")
        self.resize(1380, 900)
        self.setMinimumSize(980, 640)
        self._build()
        self._load_fields()
        self._apply_theme()
        try:
            if self.cfg.get("geometry"):
                self.restoreGeometry(QByteArray(base64.b64decode(self.cfg["geometry"])))
        except Exception:
            pass
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_log)
        self._timer.start(150)
        self._wx_init()
        log.info(f"✓ {app_name()} v{app_version()} запущен")
        self.recalc()

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(62)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(7, 10, 7, 10)
        sv.setSpacing(6)
        self.stack = QStackedWidget()
        self.side_group = QButtonGroup(self)
        self.month_combos, self.weather_segs = [], []
        pages = [("📊", "Прогноз выработки", "forecast", self._page_forecast()),
                 ("🏠", "Покрытие дома: хватит ли станции", "home", self._page_home()),
                 ("🔌", "Когда переходить на горсеть", "grid", self._page_grid()),
                 ("💰", "Зелёный тариф: окупаемость, смета, документы", "green", self._page_green()),
                 ("🌤", "Погода и выработка по прогнозу", "weather", self._page_weather()),
                 ("🌌", "Небо: Солнце, Луна, звёзды над станцией", "sky", self._page_sky()),
                 ("⚙", "Настройки станции", "settings", self._page_settings()),
                 ("📐", "Подбор угла и азимута", "tilt", self._page_tilt()),
                 ("🧵", "Подбор сечения провода", "wire", self._page_wire()),
                 ("🌐", "Данные солнца (PVGIS)", "data", self._page_data()),
                 ("🔄", "Обновление с GitHub", "update", self._page_update()),
                 ("🎨", "Цвета", "colors", self._page_colors())]
        self.page_names = [p[2] for p in pages]
        self.page_idx = {n: i for i, n in enumerate(self.page_names)}
        for i, (ico, tip, name, page) in enumerate(pages):
            b = QToolButton()
            b.setText(ico)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(48, 46)
            b.setCursor(Qt.PointingHandCursor)
            self.side_group.addButton(b, i)
            if name == "update":                         # «Обновление» и «Цвета» — внизу
                sv.addStretch(1)
            if name == "tilt":
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setObjectName("sideSep")
                sv.addWidget(sep)
            sv.addWidget(b)
            self.stack.addWidget(page)
        self.btn_side_upd = self.side_group.button(self.page_idx["update"])
        self.side_group.button(0).setChecked(True)
        self.side_group.idClicked.connect(self._go_page)
        h.addWidget(side)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.vsplit = QSplitter(Qt.Vertical)
        self.vsplit.addWidget(self.stack)
        self.vsplit.addWidget(self._log_card())
        self.vsplit.setStretchFactor(0, 1)
        self.vsplit.setSizes([780, 110])
        self.vsplit.setCollapsible(0, False)
        right.addWidget(self.vsplit, 1)
        sb = QFrame()
        sb.setObjectName("statusbar")
        sb.setFixedHeight(30)
        sh = QHBoxLayout(sb)
        sh.setContentsMargins(10, 0, 12, 0)
        self.pill = _lab("● готов", "pill")
        self.src_lab = _lab("", "muted")
        self.status_lab = _lab("", "muted")
        sh.addWidget(self.pill)
        sh.addSpacing(10)
        sh.addWidget(self.src_lab)
        sh.addStretch(1)
        self.btn_upd = QPushButton()                     # «⬆ X.Y.Z» — есть новая версия на GitHub
        self.btn_upd.setObjectName("updchip")
        self.btn_upd.setCursor(Qt.PointingHandCursor)
        self.btn_upd.clicked.connect(self.show_update)
        self.btn_upd.hide()
        sh.addWidget(self.btn_upd)
        sh.addSpacing(10)
        sh.addWidget(self.status_lab)
        right.addWidget(sb)
        h.addLayout(right, 1)

    # ── обновление с GitHub (общий модуль gh_update) ──
    def _page_update(self):
        """Страница «🔄 Обновление»: создаётся при запуске — автопроверка идёт, даже если её не открывали."""
        gh_update_qt.set_colors(lambda: {"accent": self._p()["accent"], "text": self._p()["text"],
                                         "dim": self._p()["muted"], "panel": self._p()["panel"],
                                         "border": self._p()["line"]})
        target = gh_update.UpdateTarget(
            owner="romzespra-collab", repo="Solar_calc", name="solar_calc", current=app_version(),
            app_dir=str(APP_ROOT), main_file="solar_calc.pyw", changelog="",
            version_files=("solar_calc.py",), where="боковая панель → 🔄 Обновление")
        c = self.cfg

        def cfg_get():
            return {"token": c.get("upd_token", ""), "auto": bool(c.get("upd_auto", True)),
                    "branch": c.get("upd_branch") or "main", "every_h": int(c.get("upd_every_h") or 12)}

        def cfg_set(d):                                  # сохраняется сразу
            c.update(upd_token=d["token"], upd_auto=bool(d["auto"]), upd_branch=d["branch"] or "main",
                     upd_every_h=int(d.get("every_h") or 12))
            save_config(c)

        pg, v = self._page()
        v.addWidget(_lab("Обновление с GitHub", "bigTitle"))
        self.update_page = gh_update_qt.UpdatePage(target, cfg_get, cfg_set, on_quit=self.quit_app, log=log.info)
        self.update_page.layout().setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.update_page, 1)
        self.update_page.box.available.connect(self._update_available)
        return pg

    def show_update(self):
        i = self.page_idx["update"]
        self.side_group.button(i).setChecked(True)
        self._go_page(i)

    def _update_available(self, ver):
        """Нашлась новая версия: «⬆» на боковой панели и кнопка в строке состояния."""
        tip = f"Доступна новая версия {ver} (у вас {app_version()}) — 🔄 Обновление с GitHub"
        self.btn_side_upd.setText("⬆")
        self.btn_side_upd.setToolTip(tip)
        self.btn_upd.setText(f"⬆ {ver}")
        self.btn_upd.setToolTip(tip)
        self.btn_upd.show()

    def quit_app(self):
        """Полный выход (после обновления новая копия уже запущена)."""
        self.close()
        QApplication.instance().quit()

    def _page(self):
        pg = QWidget()
        pg.setObjectName("page")
        v = QVBoxLayout(pg)
        v.setContentsMargins(16, 16, 16, 12)
        v.setSpacing(12)
        return pg, v

    def _scroll(self, inner):
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        inner.setObjectName("scrollInner")
        sa.setWidget(inner)
        return sa

    def _mw_bar(self, title, extra=None):
        hdr = QHBoxLayout()
        hdr.addWidget(_lab(title, "bigTitle"))
        hdr.addSpacing(12)
        cb = NoWheelCombo()
        cb.addItems(MONTHS)
        cb.setToolTip("Месяц")
        cb.currentIndexChanged.connect(lambda i: self._on_field("month", i))
        self.month_combos.append(cb)
        hdr.addWidget(cb)
        seg = Segmented(WEATHER)
        seg.setToolTip("Погода")
        seg.changed.connect(lambda k: self._on_field("weather", k))
        self.weather_segs.append(seg)
        hdr.addWidget(seg)
        hdr.addStretch(1)
        for w in extra or []:
            hdr.addWidget(w)
        return hdr

    def _sync_mw(self):
        for cb in self.month_combos:
            cb.blockSignals(True)
            cb.setCurrentIndex(int(self.s["month"]))
            cb.blockSignals(False)
        for sg in self.weather_segs:
            sg.setValue(self.s["weather"])

    def _kpi_grid(self, items, cols=3):
        kp = QGridLayout()
        kp.setSpacing(10)
        for i, (k, cap) in enumerate(items):
            fr = QFrame()
            fr.setObjectName("kpi")
            fv = QVBoxLayout(fr)
            fv.setContentsMargins(12, 8, 12, 8)
            fv.setSpacing(0)
            val = _lab("—", "kpiVal")
            sub = _lab(cap, "kpiCap", True)
            fv.addWidget(val)
            fv.addWidget(sub)
            self.kpi[k] = (val, sub)
            kp.addWidget(fr, i // cols, i % cols)
        return kp

    def _results_scroll(self, inner):
        sa = self._scroll(inner)
        inner.setContextMenuPolicy(Qt.CustomContextMenu)
        inner.customContextMenuRequested.connect(lambda pos: self._results_menu(inner.mapToGlobal(pos)))
        return sa

    def _rich(self):
        l = QLabel()
        l.setTextFormat(Qt.RichText)
        l.setWordWrap(True)
        l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return l

    def recalc(self):
        self.gen += 1
        self.sd = SunData(self.cfg)
        t0 = time.perf_counter()
        try:
            self.R = compute_all(dict(self.s), self.sd)
        except Exception as e:
            log.error(f"✗ Ошибка расчёта: {e}")
            return
        dt = (time.perf_counter() - t0) * 1000
        self._show_results()
        if (self.s.get("weather") == "reg" or self.s.get("ser_weather") == "reg") and hasattr(self, "btn_reg"):
            self.load_region(auto=True)                  # выбрана погода региона — данных для точки нет: загрузить
        if hasattr(self, "canvas"):
            self._cons_update()                      # итог за год и «закрыто станцией» на схеме
        self._status(f"расчёт {dt:.0f} мс")
        self._wx_place_changed()
        cur = self.page_names[self.stack.currentIndex()]
        if cur in ("tilt", "wire"):
            self._refresh_page(cur)
        elif cur == "data":
            self._fill_data_table()
        elif cur in ("weather", "sky"):
            self._wx_refresh()
        elif cur == "green":
            self._green_update()

    def _set_theme(self, k):
        self.cfg["theme"] = k
        self._apply_theme()
        if self.R is not None:
            self._show_results()
        cur = self.page_names[self.stack.currentIndex()]
        if cur in ("tilt", "wire"):                       # графики и подписи этих страниц — в новых цветах
            self._refresh_page(cur, force=True)
        elif cur in ("weather", "sky"):
            self._wx_refresh()
        elif cur == "green":
            self._green_update()

    def _p(self):
        return _QT_THEMES.get(self.cfg.get("theme", "dark"), _QT_THEMES["dark"])

    def _apply_theme(self):
        p = self._p()
        app = QApplication.instance()
        app.setStyleSheet(_qss(p))
        off = "#454b59" if self.cfg.get("theme", "dark") == "dark" else "#c3c8d2"
        for t in self.toggles:
            t.set_theme(p["accent"], off, "#ffffff")        # ручка — белая в обеих темах
        for c in self.charts:
            c.set_theme(p)
        if hasattr(self, "wxpane"):
            self.wxpane.update()
        if hasattr(self, "canvas"):
            self._cons_update()

    def _log_card(self):
        fr, v = _card("Лог")
        v.setContentsMargins(14, 8, 14, 8)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._log_menu)
        v.addWidget(self.log_view)
        return fr

    def _log_menu(self, pos):
        lv = self.log_view
        m = QMenu(self)
        a = m.addAction("📋 Копировать", lv.copy)
        a.setEnabled(lv.textCursor().hasSelection())
        m.addAction("📋 Копировать всё", lambda: QGuiApplication.clipboard().setText(lv.toPlainText()))
        m.addAction("Выделить всё", lv.selectAll)
        m.addSeparator()
        m.addAction("💾 Сохранить в файл…", self._save_log)
        m.addAction("🗑 Очистить", lv.clear)
        m.exec(lv.mapToGlobal(pos))

    def _save_log(self):
        fn = ask_save(self, "Сохранить лог", str(APP_ROOT / "лог.txt"), "Текст (*.txt)")
        if not fn:
            return
        try:
            Path(fn).write_text(self.log_view.toPlainText(), encoding="utf-8")
            log.info(f"✓ Лог сохранён: {fn}")
        except OSError as e:
            _save_failed(self, fn, e)

    def _append_log(self, level, text):
        lv = self.log_view
        sb = lv.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        col = None
        if "✗" in text or "⛔" in text or level >= logging.ERROR:
            col = _ERR
        elif "⚠" in text or level >= logging.WARNING:
            col = _WARN
        elif "✓" in text or "✅" in text:
            col = _OK
        esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lv.appendHtml(f"<span style='color:{col}'>{esc}</span>" if col else esc)
        if at_bottom:
            sb.setValue(sb.maximum())

    def _drain_log(self):
        for _ in range(200):
            try:
                item = UIQ.get_nowait()
            except queue.Empty:
                break
            if item is _DONE:
                if self.worker.jobs.empty() and not self.worker.pending:
                    self.pill.setText("● готов")
                    self.btn_pv.setEnabled(True)
                    self.btn_reg.setEnabled(True)
            elif callable(item):
                try:
                    item()
                except Exception as e:
                    log.error(f"✗ Ошибка интерфейса: {e}", exc_info=True)
            elif isinstance(item, tuple) and item[0] == "log":
                self._append_log(item[1], item[2])
            elif isinstance(item, tuple) and item[0] == "busy":
                self.pill.setText(f"● {item[1]}…")

    def _status(self, text):
        self.status_lab.setText(text)

    def _go_page(self, i):
        self.stack.setCurrentIndex(i)
        name = self.page_names[i]
        if name in ("tilt", "wire"):
            self._refresh_page(name)
        elif name == "data":
            self._fill_data_table()
        elif name in ("weather", "sky"):
            self._wx_refresh()
        elif name == "green":
            self._green_update()

    def _refresh_page(self, i, force=False):
        if not force and self.page_gen.get(i) == self.gen:
            return
        s, sd, gen = dict(self.s), self.sd, self.gen
        name, job, fill = {"tilt": ("подбор угла", self._job_tilt, self._fill_tilt),
                           "wire": ("подбор провода", self._job_wire, self._fill_wire)}[i]

        def done(res):
            fill(res)
            self.page_gen[i] = gen
            if gen != self.gen and self.page_names[self.stack.currentIndex()] == i:
                QTimer.singleShot(0, lambda: self._refresh_page(i))

        extra = (self.seg_wire.value(),) if i == "wire" else ()
        self.worker.submit(name, lambda: job(s, sd, *extra), done)

    def _inputs_menu(self, gpos):
        m = QMenu(self)
        m.addAction("📂 Открыть профиль…", self.load_profile)
        m.addAction("💾 Сохранить профиль…", self.save_profile)
        m.addAction("📋 Копировать параметры (JSON)",
                    lambda: QGuiApplication.clipboard().setText(json.dumps(self.s, ensure_ascii=False, indent=2)))
        m.addSeparator()
        m.addAction("↺ Сбросить к умолчанию…", self.reset_defaults)
        m.exec(gpos)

    def _results_menu(self, gpos):
        m = QMenu(self)
        m.addAction("📋 Копировать отчёт", self.copy_report)
        m.addAction("💾 Экспорт CSV по месяцам…", self.export_months)
        m.addAction("🔄 Пересчитать", self.recalc)
        m.exec(gpos)

    def reset_defaults(self):
        if QMessageBox.question(self, app_name(), "Сбросить все параметры станции к значениям по умолчанию?") != QMessageBox.Yes:
            return
        self.s.clear()
        self.s.update(DEFAULT_SYS)
        self._load_fields()
        self._g_load()
        log.info("↺ Параметры сброшены")
        self.recalc()

    def _dir(self):
        d = self.cfg.get("last_dir") or str(APP_ROOT)
        return d if Path(d).exists() else str(APP_ROOT)

    def save_profile(self):
        fn = ask_save(self, "Сохранить профиль", str(Path(self._dir()) / "моя_станция.json"), "Профиль (*.json)")
        if not fn:
            return
        try:
            Path(fn).write_text(json.dumps({"solar_calc": app_version(), "sys": self.s}, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            _save_failed(self, fn, e)
            return
        self.cfg["last_dir"] = str(Path(fn).parent)
        log.info(f"✓ Профиль сохранён: {fn}")

    def load_profile(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Открыть профиль", self._dir(), "Профиль (*.json)",
                                            options=QFileDialog.DontUseNativeDialog)
        if not fn:
            return
        try:
            data = json.loads(Path(fn).read_text(encoding="utf-8-sig"))
            sysd = data.get("sys", data) if isinstance(data, dict) else None
            if not isinstance(sysd, dict) or not set(sysd) & set(DEFAULT_SYS):
                raise ValueError("в файле нет параметров станции")
            new = clean_sys(sysd)
            self.s.clear()
            self.s.update(new)
            self.cfg["last_dir"] = str(Path(fn).parent)
            self._load_fields()
            self._g_load()
            log.info(f"✓ Профиль загружен: {fn}")
            self.recalc()
        except Exception as e:
            log.error(f"✗ Не удалось открыть профиль: {e}")
            QMessageBox.warning(self, app_name(), f"Не удалось открыть профиль:\n{e}")

    def _save_all(self):
        self.cfg["geometry"] = base64.b64encode(bytes(self.saveGeometry())).decode()
        if save_config(self.cfg):
            log.info("💾 Настройки сохранены")
            self._status("сохранено")
        else:
            self._status("не сохранено!")

    def closeEvent(self, e):
        win = getattr(self, "_skywin", None)
        if win is not None:
            win.close()
        self._save_all()
        super().closeEvent(e)
