"""mod_page_sky.py  v1.4.0
Страницы «🌤 Погода» и «🌌 Небо» + опрос погоды. Всё согласовано со станцией: место и часовой пояс —
из настроек, Солнце — та же формула, что в расчёте, прогноз выработки — тот же расчёт панелей/MPPT/АКБ.

Журнал:
v1.4.0: первая версия — экран погоды и сцена неба из Smart_BMS 4.81, прогноз выработки по погоде
        на 6 дней (кВт·ч, заряд АКБ, переход на сеть), «сейчас по погоде», поиск города, полный экран.
"""

import urllib.error

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLineEdit, QMenu, QVBoxLayout, QWidget)

from . import mod_astro as A
from . import mod_forecast as F
from . import mod_sky
from .mod_base import APP_ROOT, MONTHS_S, log
from .mod_model import grid_times, fmt_t
from .mod_sky import SkyView
from .mod_theme import _OK, _ERR, _WARN, SERIES_COL
from .mod_weather import MODELS, POLLS, fetch, geocode, wx_word, dow_word
from .mod_widgets import (Chart, NoWheelCombo, Stepper, Toggle, _btn, _card, _fmt, _item, _lab, _save_failed,
                          app_name, app_version, make_table)
from .mod_wx_draw import WeatherPane

LIKE = {"clear": "☀ ясный", "avg": "⛅ средний", "over": "☁ пасмурный"}


def _short_err(e):
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}"
    if isinstance(e, urllib.error.URLError):
        return f"нет связи ({e.reason})"[:90]
    return (str(e) or e.__class__.__name__)[:90]


class SkyWindow(QDialog):
    """«Небо» отдельным окном: F11 / двойной клик — полный экран, Esc — выход, курсор прячется."""

    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Небо — {app_name()}")
        self.setWindowFlag(Qt.Window, True)
        self.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setStyleSheet("QDialog{background:#0b0e12;}")
        self.resize(1024, 768)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        self.view = SkyView(provider)
        self.view.setMouseTracking(True)
        self.view.installEventFilter(self)
        v.addWidget(self.view)
        self._cur = QTimer(self)
        self._cur.setSingleShot(True)
        self._cur.setInterval(2500)
        self._cur.timeout.connect(lambda: self.isFullScreen() and self.view.setCursor(Qt.BlankCursor))

    def toggle_full(self):
        if self.isFullScreen():
            self.showNormal()
            self.view.unsetCursor()
        else:
            self.showFullScreen()
            self._cur.start()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.MouseButtonDblClick:
            self.toggle_full()
            return True
        if ev.type() == QEvent.MouseMove and self.isFullScreen():
            self.view.unsetCursor()
            self._cur.start()
        return super().eventFilter(obj, ev)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11:
            self.toggle_full()
            return
        if e.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(e)


class SkyPages:
    """Часть главного окна App (миксин): погода, небо, прогноз выработки по погоде."""

    # ─────────────── данные для экранов ───────────────
    def _zone(self):
        return (self.s["tz"], self.s["dst"])

    def _place_text(self):
        s = self.s
        tz = float(s["tz"])
        return (f"{s.get('place') or 'место станции'} · {float(s['lat']):.2f}, {float(s['lon']):.2f} · "
                f"UTC{tz:+g}" + (" (летом +1)" if s["dst"] else ""))

    def _wx_snap(self):
        """→ (данные, палитра) для экрана погоды."""
        snap = self.wx.snapshot()
        s = self.s
        lat, lon = float(s["lat"]), float(s["lon"])
        now = A.station_now(self._zone())
        snap.update(city=s.get("place") or "", lat=lat, lon=lon,
                    rise_set=A.sun_rise_set(lat, lon, now.date(), self._zone()),
                    moon=A.moon_phase(A.jd_utc(A.utc_now())), sun_alt=A.sun_pos(lat, lon, now, self._zone())[0])
        return snap, self._p()

    def _sky_snap(self):
        """→ данные для «Неба»: станция + погода."""
        snap = self.wx.snapshot()
        s = self.s
        snap.update(lat=float(s["lat"]), lon=float(s["lon"]), tilt=float(s["tilt"]), aspect=float(s["aspect"]),
                    tz=float(s["tz"]), dst=bool(s["dst"]), city=s.get("place") or "")
        return snap

    # ─────────────── страница «Погода» ───────────────
    def _page_weather(self):
        rin = QWidget()
        rv = QVBoxLayout(rin)
        rv.setContentsMargins(16, 16, 16, 16)
        rv.setSpacing(12)
        wcfg = self.cfg["weather"]
        top = QHBoxLayout()
        tv = QVBoxLayout()
        tv.setSpacing(2)
        tv.addWidget(_lab("Погода и выработка по прогнозу", "bigTitle"))
        self.lab_wx_place = _lab("", "muted")
        tv.addWidget(self.lab_wx_place)
        top.addLayout(tv)
        top.addStretch(1)
        self.ed_city = QLineEdit()
        self.ed_city.setPlaceholderText("Город — найти координаты…")
        self.ed_city.setMinimumWidth(200)
        self.ed_city.setToolTip("Введите город и нажмите Enter или «Найти» — широта/долгота станции подставятся")
        self.ed_city.returnPressed.connect(self._wx_find)
        top.addWidget(self.ed_city)
        top.addWidget(_btn("🔎 Найти", "chip", "Найти город (геокодер Open-Meteo)", self._wx_find))
        top.addSpacing(8)
        self.cb_wx_model = NoWheelCombo()
        for k, t in MODELS:
            self.cb_wx_model.addItem(t, k)
        self.cb_wx_model.setCurrentIndex(max(0, self.cb_wx_model.findData(wcfg["model"])))
        self.cb_wx_model.setToolTip("Модель прогноза Open-Meteo («Авто» — лучшая для места)")
        self.cb_wx_model.currentIndexChanged.connect(lambda i: self._wx_cfg("model", self.cb_wx_model.itemData(i)))
        top.addWidget(self.cb_wx_model)
        self.cb_wx_poll = NoWheelCombo()
        for mn in POLLS:
            self.cb_wx_poll.addItem(f"раз в {mn} мин", mn)
        self.cb_wx_poll.setCurrentIndex(max(0, self.cb_wx_poll.findData(wcfg["poll"])))
        self.cb_wx_poll.setToolTip("Как часто обновлять погоду")
        self.cb_wx_poll.currentIndexChanged.connect(lambda i: self._wx_cfg("poll", self.cb_wx_poll.itemData(i)))
        top.addWidget(self.cb_wx_poll)
        top.addSpacing(6)
        top.addWidget(_lab("Погода", "fieldLab"))
        self.tg_wx = Toggle()
        self.tg_wx.setToolTip("Запрашивать погоду из интернета (Open-Meteo)")
        self.tg_wx.setChecked(bool(wcfg["on"]))
        self.tg_wx.toggled.connect(lambda v: self._wx_cfg("on", bool(v)))
        self.toggles.append(self.tg_wx)
        top.addWidget(self.tg_wx)
        top.addWidget(_btn("🔄 Обновить", "chip", "Запросить погоду сейчас", self._wx_poll))
        rv.addLayout(top)
        fr, v = _card("Погода сейчас — место станции")
        self.wxpane = WeatherPane(self._wx_snap)
        self.wxpane.setMinimumHeight(380)
        self.wxpane.setMaximumHeight(560)
        self.wxpane.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wxpane.customContextMenuRequested.connect(
            lambda pos: self._pic_menu(self.wxpane, self.wxpane.mapToGlobal(pos), "погода"))
        v.addWidget(self.wxpane)
        rv.addWidget(fr)
        fr, v = _card("Выработка по прогнозу погоды — тот же расчёт, что на «📊 Прогнозе»")
        self.lab_fc_now = self._rich()
        v.addWidget(self.lab_fc_now)
        kp = self._kpi_grid(tuple((f"fc{i}", "—") for i in range(6)), cols=3)
        v.addLayout(kp)
        row = QHBoxLayout()
        row.addWidget(_lab("Заряд АКБ в начале сегодняшних суток", "fieldLab"))
        self.st_fc_soc = Stepper(0, 100, 5, 0, "%")
        self.st_fc_soc.setMaximumWidth(150)
        self.st_fc_soc.setToolTip("С какого заряда начинать прогноз заряда АКБ (в 00:00 сегодня)")
        self.st_fc_soc.setValue(self.s["fc_soc0"])
        self.st_fc_soc.changed.connect(lambda val: self._fc_soc(val))
        row.addWidget(self.st_fc_soc)
        row.addStretch(1)
        v.addLayout(row)
        self.ch_fc = Chart("line", "Вт")
        self.ch_fc.setMinimumHeight(240)
        self.charts.append(self.ch_fc)
        v.addWidget(self.ch_fc)
        self.ch_fc_soc = Chart("line", "%")
        self.ch_fc_soc.ymax_fixed = 100
        self.ch_fc_soc.setMinimumHeight(190)
        self.charts.append(self.ch_fc_soc)
        v.addWidget(self.ch_fc_soc)
        self.tb_fc = make_table(["День", "Погода", "t, °C", "Солнце, кВт·ч/м²", "На панели, кВт·ч/м²", "В АКБ, кВт·ч",
                                 "Похоже на", "Мин. заряд", "Из сети, кВт·ч", "На сеть"])
        self.tb_fc.setMinimumHeight(230)
        v.addWidget(self.tb_fc)
        rv.addWidget(fr)
        rv.addStretch(1)
        return self._results_scroll(rin)

    def _fc_soc(self, val):
        self.s["fc_soc0"] = val
        self._show_weather()

    def _wx_cfg(self, key, val):
        self.cfg["weather"][key] = val
        if key in ("model", "on"):
            self._wx_poll()
        elif key == "poll" and self.wx.ok:
            self._wx_timer.start(int(val) * 60000)
        if key == "on" and not val:
            self.wx.apply(dict(on=False))
            self._wx_refresh()

    # ─────────────── страница «Небо» ───────────────
    def _page_sky(self):
        pg, v = self._page()
        top = QHBoxLayout()
        top.addWidget(_lab("Небо", "bigTitle"))
        top.addSpacing(10)
        self.lab_sky_place = _lab("", "muted")
        top.addWidget(self.lab_sky_place)
        top.addStretch(1)
        self.tg_sky = {}
        for key, text, tip in (("names", "Созвездия", "Линии и названия созвездий, подписи ярких звёзд"),
                               ("stars", "Звёзды всегда", "Ночью звёзды видны даже при облачности"),
                               ("anim", "Анимация", "Облака, дождь, дерево, мерцание. Выкл. — кадр раз в 30 с, почти без нагрузки")):
            top.addWidget(_lab(text, "fieldLab"))
            tg = Toggle()
            tg.setToolTip(tip)
            tg.setChecked(bool(self.cfg["sky"][key]))
            tg.toggled.connect(lambda val, k=key: self._sky_set(k, val))
            self.toggles.append(tg)
            self.tg_sky[key] = tg
            top.addWidget(tg)
            top.addSpacing(8)
        top.addWidget(_btn("⛶ На весь экран", "chip", "Небо отдельным окном на весь экран (Esc — выход)", self._sky_full))
        v.addLayout(top)
        self.sky = SkyView(self._sky_snap)
        self.sky.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sky.customContextMenuRequested.connect(lambda pos: self._sky_menu(self.sky.mapToGlobal(pos)))
        v.addWidget(self.sky, 1)
        self._sky_flags()
        return pg

    def _sky_flags(self):
        sk = self.cfg["sky"]
        mod_sky.SHOW_NAMES = bool(sk["names"])
        mod_sky.FORCE_STARS = bool(sk["stars"])
        anim = bool(sk["anim"])
        mod_sky.ANIMATE = mod_sky.ANIM_CLOUDS = mod_sky.ANIM_TREE = mod_sky.ANIM_PANELS = mod_sky.ANIM_STARS = anim
        for view in (getattr(self, "sky", None), getattr(getattr(self, "_skywin", None), "view", None)):
            if view is not None:
                view._lay_key = None
                view.apply_anim()

    def _sky_set(self, key, val):
        self.cfg["sky"][key] = bool(val)
        tg = self.tg_sky.get(key)
        if tg is not None and tg.isChecked() != bool(val):
            tg.blockSignals(True)
            tg.setChecked(bool(val))
            tg.blockSignals(False)
        self._sky_flags()

    def _sky_full(self):
        win = getattr(self, "_skywin", None)
        if win is None or not win.isVisible():
            self._skywin = win = SkyWindow(self._sky_snap, self)
            win.view.setContextMenuPolicy(Qt.CustomContextMenu)
            win.view.customContextMenuRequested.connect(lambda pos: self._sky_menu(win.view.mapToGlobal(pos), win))
        win.showFullScreen()
        win._cur.start()

    def _sky_menu(self, gpos, win=None):
        m = QMenu(self)
        for key, text in (("names", "Созвездия и названия"), ("stars", "Звёзды при облачности"), ("anim", "Анимация")):
            a = m.addAction(text, lambda k=key: self._sky_set(k, not self.cfg["sky"][k]))
            a.setCheckable(True)
            a.setChecked(bool(self.cfg["sky"][key]))
        m.addSeparator()
        if win is None:
            m.addAction("⛶ На весь экран", self._sky_full)
        else:
            m.addAction("⛶ Полный экран / окно (F11)", win.toggle_full)
            m.addAction("✕ Закрыть (Esc)", win.close)
        view = win.view if win else self.sky
        m.addAction("📋 Копировать картинку", lambda: QGuiApplication.clipboard().setPixmap(view.grab()))
        m.addAction("💾 Сохранить картинку…", lambda: self._save_pic(view, "небо"))
        m.exec(gpos)

    def _pic_menu(self, wdg, gpos, name):
        m = QMenu(self)
        m.addAction("🔄 Обновить погоду", self._wx_poll)
        m.addSeparator()
        m.addAction("📋 Копировать картинку", lambda: QGuiApplication.clipboard().setPixmap(wdg.grab()))
        m.addAction("💾 Сохранить картинку…", lambda: self._save_pic(wdg, name))
        m.exec(gpos)

    def _save_pic(self, wdg, name):
        fn, _ = QFileDialog.getSaveFileName(self, "Сохранить картинку", str(APP_ROOT / f"{name}.png"), "PNG (*.png)",
                                            options=QFileDialog.DontUseNativeDialog)
        if not fn:
            return
        if wdg.grab().save(fn, "PNG"):
            log.info(f"✓ Картинка сохранена: {fn}")
        else:
            _save_failed(self, fn, "ошибка записи PNG")

    # ─────────────── опрос погоды ───────────────
    def _wx_init(self):
        self._wx_timer = QTimer(self)
        self._wx_timer.setSingleShot(True)
        self._wx_timer.timeout.connect(self._wx_poll)
        self._wx_timer.start(2500)                     # дать окну подняться

    def _wx_poll(self):
        w = self.cfg["weather"]
        if not w["on"]:
            self.wx.apply(dict(on=False))
            self._wx_refresh()
            return
        lat, lon, model = float(self.s["lat"]), float(self.s["lon"]), w["model"]
        ua = f"solar_calc/{app_version()}"

        def job():
            try:
                d = fetch(lat, lon, model, ua)
            except Exception as e:                      # нет сети и т.п. — не ошибка программы
                d = dict(ok=None, err=_short_err(e))
            d.update(lat=lat, lon=lon, model=model, on=True)
            return d
        self.worker.submit("погода", job, self._wx_done)

    def _wx_done(self, d):
        prev = self.wx.err
        if d.get("ok"):
            if prev or not self.wx.ok:
                n = len(d.get("fc", []))
                log.info(f"✓ Погода: {wx_word(d['cur'].get('code'))}, {_fmt(d['cur'].get('temp') or 0)}°C · "
                         f"прогноз радиации на {n // 24} сут")
            self._wx_timer.start(int(self.cfg["weather"]["poll"]) * 60000)
        else:
            if d.get("err") != prev:
                log.warning(f"⚠ Погода: {d.get('err')} — повтор через 5 мин")
            d = {k: v for k, v in d.items() if k in ("err", "on")}
            if self.wx.ok and (abs(self.wx.lat - float(self.s["lat"])) > 0.01 or abs(self.wx.lon - float(self.s["lon"])) > 0.01):
                d["ok"] = False                           # старые данные — для другого места
            self._wx_timer.start(5 * 60000)
        self.wx.apply(d)
        self._wx_refresh()

    def _wx_place_changed(self):
        """Станция переехала — погоду запросить заново (через 1.5 с, чтобы не дёргать на каждый шаг)."""
        if self.wx.ok and (abs(self.wx.lat - float(self.s["lat"])) > 0.01 or abs(self.wx.lon - float(self.s["lon"])) > 0.01):
            self.wx.apply(dict(ok=False, err="место изменилось — обновляю…"))
            self._wx_timer.start(1500)

    def _wx_refresh(self):
        txt = self._place_text()
        self.lab_wx_place.setText(txt)
        self.lab_sky_place.setText(txt)
        self.wxpane.update()
        self._show_weather()

    def _wx_find(self):
        name = self.ed_city.text().strip()
        if not name:
            self.ed_city.setFocus()
            return
        ua = f"solar_calc/{app_version()}"

        def job():
            try:
                return name, geocode(name, ua), ""
            except Exception as e:
                return name, [], _short_err(e)

        def done(r):
            nm, found, err = r
            if err:
                log.warning(f"⚠ Поиск «{nm}»: {err}")
                return
            if not found:
                log.warning(f"⚠ «{nm}» не найден")
                return
            m = QMenu(self)
            for lab, la, lo in found:
                m.addAction(f"{lab}   ({la:.2f}, {lo:.2f})", lambda la=la, lo=lo, lab=lab: self._wx_set_place(lab, la, lo))
            m.exec(self.ed_city.mapToGlobal(self.ed_city.rect().bottomLeft()))
        self.worker.submit("поиск города", job, done)

    def _wx_set_place(self, label, lat, lon):
        self.s["place"] = label.split(",")[0]
        self.s["lat"], self.s["lon"] = round(lat, 4), round(lon, 4)
        for k in ("place", "lat", "lon"):
            self._set_widget(k, self.s[k])
        log.info(f"✓ Место станции: {label} ({lat:.4f}, {lon:.4f}) — проверьте часовой пояс в настройках")
        self.recalc()

    # ─────────────── прогноз выработки по погоде ───────────────
    def _show_weather(self):
        if not hasattr(self, "tb_fc"):
            return
        txt = self._place_text()
        self.lab_wx_place.setText(txt)
        self.lab_sky_place.setText(txt)
        snap = self.wx.snapshot()
        mute = self._p()["muted"]
        t = self.tb_fc
        if not snap["ok"] or self.R is None:
            why = ("погода выключена" if not snap["on"] else
                   f"нет данных о погоде{(' — ' + snap['err']) if snap['err'] else ''}")
            self.lab_fc_now.setText(f"<span style='color:{mute}'>{why}. Прогноз выработки появится, когда придёт погода.</span>")
            for i in range(6):
                self.kpi[f"fc{i}"][0].setText("—")
                self.kpi[f"fc{i}"][1].setText("")
            self.ch_fc.set_data([])
            self.ch_fc_soc.set_data([])
            t.setRowCount(0)
            return
        s, R = self.s, self.R
        fc = F.run(s, self.wx.fc, R["res"], float(s["fc_soc0"]))
        days = fc["days"]
        alt, _az = F.sun_now(s)
        nowp = F.now_power(s, snap)
        if nowp and alt > 0:
            self.lab_fc_now.setText(
                f"<b>Сейчас по погоде:</b> ≈ <b style='color:{_OK}'>{_fmt(nowp[0])} Вт</b> в АКБ · на панели "
                f"{_fmt(nowp[1])} Вт/м² · Солнце {alt:.0f}° · {wx_word(snap['code'])}, облачность {snap['cloud']}%"
                f"<span style='color:{mute}'> · радиация и температура — Open-Meteo, расчёт — ваша станция</span>")
        else:
            self.lab_fc_now.setText(f"<b>Сейчас:</b> Солнце под горизонтом ({alt:.0f}°) · {wx_word(snap['code'])}"
                                    f"<span style='color:{mute}'> · радиация и температура — Open-Meteo, расчёт — ваша станция</span>")
        dmap = {d["date"]: d for d in snap["daily"]}
        today = A.station_now(self._zone()).date()
        xs, pv, ld, gw, soc, marks = [], [], [], [], [], []
        for i in range(6):
            val, sub = self.kpi[f"fc{i}"]
            if i >= len(days):
                val.setText("—")
                sub.setText("")
                continue
            d = days[i]
            dd = dmap.get(d["date"])
            name = "сегодня" if d["date"] == today else "завтра" if (d["date"] - today).days == 1 else \
                f"{dow_word(d['date'].isoweekday() % 7)} {d['date']:%d.%m}"
            val.setText(f"{_fmt(d['out'] / 1000, 1)} кВт·ч")
            wx = f"{wx_word(dd['code'])} {dd['max']:+d}°/{dd['min']:+d}°" if dd else ""
            like = f"≈ {LIKE[d['like']]} день {MONTHS_S[d['date'].month - 1].lower()}" if d["like"] else "неполные сутки"
            sub.setText(f"{name} · {wx} · {like} · пик {_fmt(d['peak'] / 1000, 1)} кВт · мин. заряд {d['soc']['soc_min']:.0f}%")
            val.setStyleSheet(f"color: {_OK if d['soc']['grid_wh'] < 1 else _WARN};")
        t.setRowCount(0)
        for i, d in enumerate(days):
            r = d["soc"]
            for p in r["pts"]:
                xs.append(i * 24 + p[0])
                pv.append(p[1])
                ld.append(p[2])
                gw.append(p[3])
                soc.append(p[4])
            if i:
                marks.append((i * 24.0, f"{dow_word(d['date'].isoweekday() % 7)} {d['date']:%d.%m}", self._p()["muted"]))
            for tt, k in r["events"]:
                if k == "grid":
                    marks.append((i * 24 + tt, "сеть" if self.s.get("grid_mode") != "off" else "откл.", _ERR))
            a, b = grid_times(r)
            dd = dmap.get(d["date"])
            j = t.rowCount()
            t.insertRow(j)
            t.setItem(j, 0, _item(f"{dow_word(d['date'].isoweekday() % 7)} {d['date']:%d.%m}", bold=d["date"] == today))
            t.setItem(j, 1, _item(wx_word(dd["code"]) if dd else "—"))
            t.setItem(j, 2, _item(f"{dd['max']:+d} / {dd['min']:+d}" if dd else "—", True))
            t.setItem(j, 3, _item(_fmt(d["ghi"] / 1000, 2), True))
            t.setItem(j, 4, _item(_fmt(d["poa"] / 1000, 2), True))
            t.setItem(j, 5, _item(_fmt(d["out"] / 1000, 1), True, _OK, True))
            t.setItem(j, 6, _item(LIKE[d["like"]] if d["like"] else "неполные сутки"))
            t.setItem(j, 7, _item(f"{r['soc_min']:.0f} %", True))
            t.setItem(j, 8, _item(_fmt(r["grid_wh"] / 1000, 1), True, _ERR if r["grid_wh"] > 1 else _OK))
            t.setItem(j, 9, _item(fmt_t(a) if a is not None else "—", color=_ERR if a is not None else None))
        n = max(1, len(days))
        acc = self._p()["accent"]
        lost = "Без света" if self.s.get("grid_mode") == "off" else "Из сети"
        self.ch_fc.title = f"{len(days)} сут по прогнозу"
        self.ch_fc.set_data([("Солнце в АКБ", SERIES_COL["clear"], pv), ("Расход дома", acc, ld), (lost, _ERR, gw)],
                            xs=xs, xmin=0, xmax=24 * n, markers=marks)
        cap = max(1.0, self.R["ctx"]["bank_wh"])
        base = (1 - self.R["ctx"]["usable_wh"] / cap) * 100
        self.ch_fc_soc.title = "Заряд АКБ по прогнозу"
        self.ch_fc_soc.set_data([("Заряд АКБ", _OK, soc), (f"Минимум {base:.0f}%", _ERR, [base] * len(soc))],
                                xs=xs, xmin=0, xmax=24 * n, markers=marks)
