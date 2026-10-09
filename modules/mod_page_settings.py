"""mod_page_settings.py  v1.8.0
Страница «Настройки станции»: карточка «Моя станция» (что стоит), поля, пресеты, реакция на изменения.

Журнал:
v1.8.0: входы MPPT видны везде: схема «2 входа MPPT × по 9 панелей (9 посл. × 1 пар.)», сколько входов занято
        и свободно; у инвертора — «2 входа MPPT»; строка встроенного MPPT — окно, Voc, ток на вход, занято.
v1.7.0: «Моя станция» — поля своей ширины (не на всё окно); АКБ: «＋ Другая сборка» — разные АКБ параллельно
        (до 5 других: тип × сборок, ✕ — убрать, меню по правому клику).
v1.6.0: инвертор — производитель → напряжение АКБ (12 / 24 / 48 В, с MPPT / без) → модель.
v1.5.1: АКБ × сборок (1–10); у сборок из ячеек/АКБ последовательно — «сб.», у готовых АКБ на систему — «шт».
v1.5.0: панели — производитель → серия → мощность из полной базы (21 тыс.), 🔎 поиск у всех выборов.
v1.4.0: текстовое поле (место/город).
v1.3.0: вынесено из solar_calc.pyw v1.2.1; карточка «Моя станция»: панели (производитель → модель) × шт,
        схема по входам MPPT с проверкой и подбором ★, инвертор, MPPT встроенный / отдельный (карточка
        MPPT и провод MPPT→АКБ видны только для отдельного контроллера или своего инвертора), АКБ × шт.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QComboBox, QLabel, QLineEdit, QToolButton

from .mod_base import log
from .mod_panels import PANEL_DB, PANEL_SERIES
from .mod_equipment import INVERTER_DB, INVERTER_SERIES, MPPT_DB, BATTERY_DB, MPPT_PRESETS, inv_is_hybrid
from .mod_fields import (INPUT_CARDS, INT_KEYS, INV_KEYS, WIRE_S_KEYS, WIRE_RANGE, PRESET_GROUPS, MPPT_MODES,
                         s2d, d2s)
from .mod_model import (make_ctx, layouts, layout_status, best_layout, bank_series, bank_groups, layout_text,
                        inputs_word, plural)
from .mod_config import BAT_EXTRA_MAX
from .mod_theme import _OK, _ERR, _WARN
from .mod_widgets import Toggle, Segmented, NoWheelCombo, Stepper, PresetPicker, _lab, _card, _btn

LVL_ICON = {"ok": "✓", "warn": "⚠", "err": "✗"}
LVL_COL = {"ok": _OK, "warn": _WARN, "err": _ERR}


class SettingsPage:
    """Часть главного окна App (миксин)."""

    SETTINGS_COLS = {"Место и ориентация": 0, "Паспорт панели": 0, "Потери поля": 0,
                     "Провода и соединения": 1, "MPPT": 1, "Пределы температур": 1,
                     "Аккумуляторы": 2, "Инвертор": 2, "Потребление дома": 2, "Сеть и тариф": 2}

    # ─────────────── построение ───────────────
    def _input_card(self, title, fields):
        fr, v = _card(title)
        self.cards[title] = fr
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(7)
        g.setColumnStretch(1, 1)
        for row, (key, label, kind, opt, tip) in enumerate(fields):
            if kind == "head":
                lh = _lab(label, "subHead")
                g.addWidget(lh, row, 0, 1, 2)
                self.rows[key] = [lh]
                continue
            wdg = self._make_field(key, kind, opt)
            wdg.setToolTip(tip)
            lb = _lab(label, "fieldLab", True)
            lb.setMaximumWidth(150)
            lb.setToolTip(tip)
            g.addWidget(lb, row, 0)
            g.addWidget(wdg, row, 1)
            self.rows[key] = [lb, wdg]
        v.addLayout(g)
        if title == "Провода и соединения":
            self.lab_wire = _lab("", "hint", True)
            v.addWidget(self.lab_wire)
        return fr

    def _station_card(self):
        fr, v = _card("Моя станция — что стоит")
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(6)
        g.setColumnStretch(1, 1)

        def lab(text, tip):
            lb = _lab(text, "fieldLab")
            lb.setToolTip(tip)
            lb.setMinimumWidth(70)
            return lb

        def hint(rich=False):
            h = _lab("", "hint", True)
            h.setMaximumWidth(1100)
            if rich:
                h.setTextFormat(Qt.RichText)
            return h

        def count(lo, hi, key, tip):
            st = Stepper(lo, hi, 1, 0, "шт")
            st.setMaximumWidth(160)
            st.setToolTip(tip)
            st.changed.connect(lambda val, k=key: self._on_field(k, val))
            self.w[key] = st
            return st

        def row(*items):
            """Строка: поля своей ширины слева, справа пусто (поля не растягиваются на всё окно)."""
            h = QHBoxLayout()
            h.setSpacing(6)
            for it in items:
                if isinstance(it, tuple):
                    h.addWidget(*it)
                else:
                    h.addWidget(it)
            h.addStretch(1)                        # поля (вес 10) растут до своего предела, остальное — пусто
            return h

        # панели × шт
        self.pk_pan = PresetPicker(PANEL_DB, "Своя панель — паспорт ниже", series=PANEL_SERIES, what="панель")
        self.pk_pan.setToolTip("Производитель → серия → мощность; 🔎 — поиск по всей базе. Подставит паспорт")
        self.pk_pan.changed.connect(lambda k: self._on_field("p_preset", k))
        self.w["p_preset"] = self.pk_pan
        g.addWidget(lab("Панели", "Какие панели стоят"), 0, 0)
        g.addLayout(row((self.pk_pan, 10), _lab("×", "fieldLab"), count(1, 300, "n_pan", "Сколько панелей всего")), 0, 1)
        self.lab_total = hint()
        g.addWidget(self.lab_total, 1, 1)
        # схема
        self.cb_layout = NoWheelCombo()
        self.cb_layout.setToolTip("Как соединены панели: последовательно × параллельно, на сколько входов MPPT")
        self.cb_layout.setMinimumWidth(260)
        self.cb_layout.setMaximumWidth(460)
        self.cb_layout.currentIndexChanged.connect(self._on_layout)
        g.addWidget(lab("Схема", "Соединение панелей"), 2, 0)
        g.addLayout(row((self.cb_layout, 10), _btn("★ Лучшая", "chip", "Подобрать схему с наибольшей выработкой без ошибок",
                                                   lambda: self._fit_layout(force=True, announce=True))), 2, 1)
        self.lab_layout = hint(True)
        g.addWidget(self.lab_layout, 3, 1)
        # инвертор
        self.pk_inv = PresetPicker(INVERTER_DB, "Свой инвертор — параметры ниже", series=INVERTER_SERIES, what="инвертор")
        self.pk_inv.changed.connect(lambda k: self._on_field("inv_preset", k))
        self.w["inv_preset"] = self.pk_inv
        g.addWidget(lab("Инвертор", "Инвертор: гибрид (MPPT внутри) или без MPPT"), 4, 0)
        g.addLayout(row((self.pk_inv, 10)), 4, 1)
        self.lab_inv = hint()
        g.addWidget(self.lab_inv, 5, 1)
        # MPPT
        self.seg_mppt = Segmented(MPPT_MODES)
        self.seg_mppt.setToolTip("Гибридный инвертор — MPPT встроен; к инвертору без MPPT нужен отдельный контроллер")
        self.seg_mppt.setMaximumWidth(420)
        self.seg_mppt.changed.connect(lambda k: self._on_field("mppt_mode", k))
        self.w["mppt_mode"] = self.seg_mppt
        self.pk_mppt = PresetPicker(MPPT_DB, "Свой контроллер — параметры ниже", what="контроллер")
        self.pk_mppt.changed.connect(lambda k: self._on_field("m_preset", k))
        self.w["m_preset"] = self.pk_mppt
        self.lab_x2 = _lab("×", "fieldLab")
        g.addWidget(lab("MPPT", "Солнечный контроллер заряда"), 6, 0)
        g.addLayout(row((self.seg_mppt, 4), (self.pk_mppt, 10), self.lab_x2,
                        count(1, 12, "n_mppt_max", "Сколько контроллеров (или входов MPPT у своего инвертора)")), 6, 1)
        self.lab_mppt = hint()
        g.addWidget(self.lab_mppt, 7, 1)
        # АКБ × сборок; ниже — другие сборки (разные АКБ параллельно)
        self.pk_bat = PresetPicker(BATTERY_DB, "Свои АКБ — параметры ниже", what="АКБ")
        self.pk_bat.changed.connect(lambda k: self._on_field("bat_preset", k))
        self.pk_bat.extra_menu = lambda m: m.addAction("＋ Добавить другую сборку", self._bat_extra_add)
        self.w["bat_preset"] = self.pk_bat
        g.addWidget(lab("АКБ", "Аккумуляторы: основная сборка; другие — кнопкой «＋ Другая сборка»"), 8, 0)
        g.addLayout(row((self.pk_bat, 10), _lab("×", "fieldLab"),
                        count(1, 10, "bat_packs", "Сколько таких сборок (или готовых АКБ) параллельно, до 10. Сколько "
                                                  "штук последовательно в сборке — по напряжению системы, считается само")), 8, 1)
        self.lay_bat_extra = QVBoxLayout()
        self.lay_bat_extra.setSpacing(6)
        self.bat_extra_w = []
        g.addLayout(self.lay_bat_extra, 9, 1)
        self.btn_bat_add = _btn("＋ Другая сборка", "chip", "Есть ещё АКБ другого типа или ёмкости — добавьте их сюда. "
                                "Все сборки стоят параллельно на одном напряжении системы", self._bat_extra_add)
        g.addLayout(row(self.btn_bat_add, _lab("разные АКБ параллельно на одной шине — до 5 других сборок", "hint")), 10, 1)
        self.lab_bank = hint(True)
        g.addWidget(self.lab_bank, 11, 1)
        v.addLayout(g)
        return fr

    # ─────────────── другие сборки АКБ ───────────────
    def _bat_extra_rows(self):
        """Строки «другая сборка» — по s["bat_extra"] (после загрузки профиля, добавления, удаления)."""
        lay = self.lay_bat_extra
        while lay.count():
            it = lay.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        self.bat_extra_w = []
        for i, it in enumerate(self.s.get("bat_extra") or []):
            w = QWidget()
            h = QHBoxLayout(w)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            pk = PresetPicker(BATTERY_DB, "", what="АКБ", allow_custom=False)
            pk.setValue(it["preset"])
            pk.setToolTip(f"Сборка {i + 2}: какие АКБ")
            st = Stepper(1, 10, 1, 0, "сб.")
            st.setMaximumWidth(160)
            st.setValue(it["n"])
            st.setToolTip("Сколько таких сборок параллельно")
            rm = QToolButton()
            rm.setText("✕")
            rm.setObjectName("stepBtn")
            rm.setCursor(Qt.PointingHandCursor)
            rm.setToolTip("Убрать эту сборку")
            h.addWidget(pk, 10)
            h.addWidget(_lab("×", "fieldLab"))
            h.addWidget(st)
            h.addWidget(rm)
            h.addStretch(1)
            pk.changed.connect(lambda k, i=i: self._bat_extra_set(i, preset=k))
            st.changed.connect(lambda val, i=i: self._bat_extra_set(i, n=int(round(val))))
            rm.clicked.connect(lambda _=False, i=i: self._bat_extra_del(i))

            def menu(m, i=i):
                m.addAction("🗑 Убрать эту сборку", lambda: self._bat_extra_del(i))
                m.addAction("＋ Добавить ещё сборку", self._bat_extra_add)
            pk.extra_menu = menu
            w.setContextMenuPolicy(Qt.CustomContextMenu)
            w.customContextMenuRequested.connect(lambda pos, w=w, pk=pk: pk._menu(w.mapToGlobal(pos)))
            lay.addWidget(w)
            self.bat_extra_w.append((pk, st))
        self.btn_bat_add.setEnabled(len(self.s.get("bat_extra") or []) < BAT_EXTRA_MAX)

    def _bat_extra_changed(self):
        self._refresh_station()
        self._recalc_timer.start(200)

    def _bat_extra_set(self, i, **kw):
        ex = [dict(x) for x in self.s.get("bat_extra") or []]      # новый список — расчёт в фоне видит целый
        if 0 <= i < len(ex):
            ex[i].update(kw)
            self.s["bat_extra"] = ex
            self._bat_extra_changed()

    def _bat_extra_add(self):
        ex = [dict(x) for x in self.s.get("bat_extra") or []]
        if len(ex) >= BAT_EXTRA_MAX:
            return
        key = self.s.get("bat_preset")
        ex.append(dict(preset=key if key in BATTERY_DB else "eve_lf280k", n=1))
        self.s["bat_extra"] = ex
        self._bat_extra_rows()
        self._bat_extra_changed()
        log.info(f"＋ Добавлена сборка АКБ {len(ex) + 1} — выберите её тип")

    def _bat_extra_del(self, i):
        ex = [dict(x) for x in self.s.get("bat_extra") or []]
        if 0 <= i < len(ex):
            ex.pop(i)
            self.s["bat_extra"] = ex
            self._bat_extra_rows()
            self._bat_extra_changed()

    def _page_settings(self):
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(16, 16, 16, 16)
        iv.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(_lab("Настройки станции", "bigTitle"))
        top.addSpacing(14)
        self.chk_summary = self._rich()
        self.chk_summary.setWordWrap(False)
        top.addWidget(self.chk_summary)
        top.addStretch(1)
        top.addWidget(_btn("📂 Открыть", "chip", "Открыть профиль станции", self.load_profile))
        top.addWidget(_btn("💾 Сохранить", "chip", "Сохранить профиль станции", self.save_profile))
        top.addWidget(_btn("↺ По умолчанию", "chip", "Сбросить все параметры", self.reset_defaults))
        iv.addLayout(top)
        iv.addWidget(_lab("Сначала выберите, что у вас стоит. Ниже — подробности (паспорт меняется сам при выборе модели). "
                          "Результаты — на страницах 📊 Прогноз, 🏠 Покрытие дома, 🔌 Горсеть; пересчёт сразу.", "hint", True))
        iv.addWidget(self._station_card())
        row = QHBoxLayout()
        row.setSpacing(12)
        cols = [QVBoxLayout() for _ in range(3)]
        for c in cols:
            c.setSpacing(12)
        for title, fields in INPUT_CARDS:
            cols[self.SETTINGS_COLS.get(title, 2)].addWidget(self._input_card(title, fields))
        for c in cols:
            c.addStretch(1)
            box = QWidget()
            box.setLayout(c)
            box.setMinimumWidth(330)
            row.addWidget(box, 1)
        iv.addLayout(row)
        iv.addStretch(1)
        sa = self._scroll(inner)
        inner.setContextMenuPolicy(Qt.CustomContextMenu)
        inner.customContextMenuRequested.connect(lambda pos: self._inputs_menu(inner.mapToGlobal(pos)))
        return sa

    def _make_field(self, key, kind, opt):
        if kind == "wire":
            kind, opt = "num", WIRE_RANGE[self.s.get("wire_mode", "s")]
        if kind == "num":
            lo, hi, step, dec, suf = opt
            wdg = Stepper(lo, hi, step, dec, suf)
            wdg.changed.connect(lambda v, k=key: self._on_field(k, v))
        elif kind == "seg":
            wdg = Segmented(opt)
            wdg.changed.connect(lambda v, k=key: self._on_field(k, v))
        elif kind == "text":
            wdg = QLineEdit()
            wdg.editingFinished.connect(lambda k=key, wd=wdg: wd.text() != self.s.get(k) and self._on_field(k, wd.text()))
        elif kind == "toggle":
            wdg = Toggle()
            self.toggles.append(wdg)
            wdg.toggled.connect(lambda v, k=key: self._on_field(k, bool(v)))
            box = QWidget()
            bl = QHBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.addWidget(wdg)
            bl.addStretch(1)
            self.w[key] = wdg
            return box
        else:
            wdg = NoWheelCombo()
            for k, (t, _) in opt.items():
                wdg.addItem(t, k)
            wdg.currentIndexChanged.connect(lambda i, k=key, wd=wdg: self._on_field(k, wd.itemData(i)))
        self.w[key] = wdg
        return wdg

    # ─────────────── значения ───────────────
    def _set_widget(self, key, val):
        wdg = self.w.get(key)
        if wdg is None:
            return
        wdg.blockSignals(True)
        try:
            if isinstance(wdg, Stepper):
                if key in WIRE_S_KEYS and self.s.get("wire_mode") == "d":
                    val = s2d(val)
                wdg.setValue(val)
            elif isinstance(wdg, (Segmented, PresetPicker)):
                wdg.setValue(str(val))
            elif isinstance(wdg, Toggle):
                wdg.setChecked(bool(val))
            elif isinstance(wdg, QLineEdit):
                wdg.setText(str(val))
            elif isinstance(wdg, QComboBox):
                i = wdg.findData(val)
                wdg.setCurrentIndex(i if i >= 0 else 0)
        finally:
            wdg.blockSignals(False)

    def _load_fields(self):
        for k in WIRE_S_KEYS:
            self.w[k].reconfigure(*WIRE_RANGE[self.s.get("wire_mode", "s")])
        for k in self.w:
            if k in self.s:
                self._set_widget(k, self.s[k])
        self._bat_extra_rows()
        self._sync_mw()
        self.st_ser_days.setValue(self.s["ser_days"])
        self.seg_ser_w.setValue(self.s["ser_weather"])
        self.st_ser_soc.setValue(self.s["ser_soc0"])
        self.st_g.setValue(self.s["pt_g"])
        self.st_t.setValue(self.s["pt_t"])
        self._refresh_station()

    def _on_field(self, key, val):
        s = self.s
        if key in INT_KEYS:
            val = int(round(val))
        if key in WIRE_S_KEYS and s.get("wire_mode") == "d":
            val = round(d2s(val), 2)
        if key == "load_mode" and val != s.get("load_mode"):
            k = 12.0 if val == "y" else 1 / 12.0
            s["load_kwh"] = round(float(s["load_kwh"]) * k)
            self._set_widget("load_kwh", s["load_kwh"])
        s[key] = val
        if key == "wire_mode":
            for k in WIRE_S_KEYS:
                self.w[k].reconfigure(*WIRE_RANGE[val])
                self._set_widget(k, s[k])
        builtin = s.get("mppt_mode") == "builtin"
        for pkey, presets, keys in PRESET_GROUPS:
            if pkey == "m_preset" and builtin:
                continue                      # у встроенного MPPT параметры — от инвертора
            if key == pkey:
                if pkey == "inv_preset":
                    continue                  # инвертор — ниже, особым образом
                pr = presets.get(val, (None, None))[1]
                if pr:
                    for k, v in pr.items():
                        s[k] = v
                        self._set_widget(k, v)
                    if pkey == "bat_preset":
                        self._bat_auto()
                    if pkey in ("p_preset", "m_preset"):
                        self._fit_layout()
            elif key in keys and s.get(pkey) != "custom":
                pr = presets.get(s[pkey], (None, None))[1]
                if pr and key in pr:
                    a = pr[key]
                    diff = (a != val) if isinstance(a, str) else abs(float(a) - float(val)) > 1e-9
                    if diff:
                        s[pkey] = "custom"
                        self._set_widget(pkey, "custom")
        if key == "inv_preset":
            self._apply_inv_preset(val)
        elif key == "mppt_mode":
            self._apply_mppt_source(mode_changed=True)
        elif key == "n_pan":
            self._fit_layout(force=True)
        elif key == "n_mppt_max":
            self._fit_layout()
        if key in ("bat_v", "chem"):
            self._bat_auto()
        if key in ("pt_g", "pt_t"):
            self._update_point()
            return
        if key in ("month", "weather"):
            self._sync_mw()
            if self.R is not None:
                self._show_results()
            return
        if key in ("ser_days", "ser_weather", "ser_soc0"):
            if self.R is not None:
                self._show_series()
            return
        self._refresh_station()
        self._recalc_timer.start(200)

    def _bat_auto(self):
        n = int(self.s["bat_v"]) / 12
        self.s["bat_ch"] = round((14.2 if self.s["chem"] == "lfp" else 14.4) * n, 1)
        self.s["eta_bat"] = 97 if self.s["chem"] == "lfp" else 85
        self._set_widget("bat_ch", self.s["bat_ch"])
        self._set_widget("eta_bat", self.s["eta_bat"])

    # ─────────────── инвертор и MPPT ───────────────
    def _apply_inv_preset(self, key):
        d = INVERTER_DB.get(key)
        if not d:
            return                            # свой инвертор: оставить как есть, правится в карточках
        s, pr = self.s, d[2]
        for k in INV_KEYS:
            s[k] = pr[k]
            self._set_widget(k, pr[k])
        s["inv_bat_v"] = pr["inv_bat_v"]
        if pr["inv_bat_v"] in (12, 24, 48) and str(pr["inv_bat_v"]) != str(s["bat_v"]):
            s["bat_v"] = str(pr["inv_bat_v"])
            self._set_widget("bat_v", s["bat_v"])
            self._bat_auto()
        mode = "builtin" if pr.get("mppt") else "separate"
        changed = mode != s.get("mppt_mode")
        s["mppt_mode"] = mode
        self._set_widget("mppt_mode", mode)
        self._apply_mppt_source(mode_changed=changed)

    def _apply_mppt_source(self, mode_changed=False):
        """Параметры MPPT: встроенный — из паспорта инвертора, отдельный — из выбранного контроллера."""
        s = self.s
        if s["mppt_mode"] == "builtin":
            d = INVERTER_DB.get(s["inv_preset"])
            mp = d[2].get("mppt") if d else None
            if mp:
                for k, v in mp.items():
                    s[k] = v
                    self._set_widget(k, v)
        else:
            pr = MPPT_PRESETS.get(s["m_preset"], (None, None))[1]
            if pr:
                for k, v in pr.items():
                    s[k] = v
                    self._set_widget(k, v)
            s["pv_pmax"] = 0
            self._set_widget("pv_pmax", 0)
            if mode_changed:
                s["n_mppt_max"] = 1
                self._set_widget("n_mppt_max", 1)
        self._fit_layout()

    # ─────────────── схема (раскладка панелей) ───────────────
    def _layout_sig(self):
        s = self.s
        return tuple(str(s.get(k)) for k in ("n_pan", "n_mppt_max", "mppt_mode", "inv_preset", "m_preset", "p_preset",
                                              "pmax", "vmp", "voc", "imp", "v_max", "vmpp_min", "vmpp_max", "iin_max"))

    def _fit_layout(self, force=False, announce=False):
        """Подобрать раскладку: по кнопке/при смене количества, или если текущая не подходит (входы, ошибка)."""
        s = self.s
        n, kmax = int(s["n_pan"]), int(s["n_mppt_max"])
        cur = (int(s["n_in"]), int(s["ns"]), int(s["np"]))
        bad = cur[0] > kmax or cur[0] * cur[1] * cur[2] != n
        if not (force or bad or layout_status(s, *cur)[0] == "err"):
            return
        opts = layouts(n, kmax)
        if not opts:
            return
        best = best_layout(s, self.sd, opts)
        self._best, self._best_sig = best, self._layout_sig()
        if best is None:                       # все с ошибками — хотя бы всё последовательно на один вход
            best = (1, n, 1) if (1, n, 1) in opts else opts[0]
        s["n_in"], s["ns"], s["np"] = best
        s["n_pan"] = best[0] * best[1] * best[2]
        if announce:
            k, ns, np_ = best
            log.info(f"★ Схема: {ns} посл. × {np_} пар." + (f" на каждый из {k} входов" if k > 1 else ""))
            self._refresh_station()
            self._recalc_timer.start(50)

    def _on_layout(self, i):
        o = self.cb_layout.itemData(i)
        if not o:
            return
        s = self.s
        s["n_in"], s["ns"], s["np"] = (int(x) for x in o)
        s["n_pan"] = s["n_in"] * s["ns"] * s["np"]
        self._refresh_station()
        self._recalc_timer.start(200)

    def _rebuild_layouts(self):
        s = self.s
        sep = s.get("mppt_mode") != "builtin"
        cur = (int(s["n_in"]), int(s["ns"]), int(s["np"]))
        best = getattr(self, "_best", None) if getattr(self, "_best_sig", None) == self._layout_sig() else None
        cb = self.cb_layout
        cb.blockSignals(True)
        cb.clear()
        sel = -1
        for o in layouts(int(s["n_pan"]), int(s["n_mppt_max"])):
            k, ns, np_ = o
            lvl, msg = layout_status(s, *o)
            cb.addItem(f"{LVL_ICON[lvl]}  {layout_text(k, ns, np_, sep)}" + ("   ★ лучшая" if o == best else ""), o)
            j = cb.count() - 1
            cb.setItemData(j, msg or "Замечаний нет", Qt.ToolTipRole)
            if lvl != "ok":
                cb.setItemData(j, QColor(LVL_COL[lvl]), Qt.ForegroundRole)
            if o == cur:
                sel = j
        if sel < 0:                             # текущей нет в списке (не делится) — показать как есть
            cb.addItem(f"✗  {layout_text(cur[0], cur[1], cur[2], sep)} — не совпадает с количеством панелей", cur)
            sel = cb.count() - 1
        cb.setCurrentIndex(sel)
        cb.blockSignals(False)
        lvl, msg = layout_status(s, *cur)
        c = make_ctx(s)
        k, ns, np_ = cur
        voc_cold = ns * c["voc"] * (1 + c["bvoc"] * (float(s["t_min"]) - 25))
        lim = f" (предел {c['iin_max']:.0f} А)" if c["iin_max"] > 0 else ""
        kmax = int(s["n_mppt_max"])
        where = (f"На {'каждый ' if k > 1 else ''}{'контроллер' if sep else 'вход MPPT'}: {ns * np_} "
                 f"{plural(ns * np_, 'панель', 'панели', 'панелей')} — ")
        free = (f" · занято {k} из {kmax}, свободно {kmax - k}" if kmax > k else
                (f" · заняты все {kmax}" if kmax > 1 else ""))
        txt = (where + f"цепочка из {ns}: Vmp {ns * c['vmp']:.0f} В, Voc {ns * c['voc']:.0f} В, на морозе {voc_cold:.0f} В "
               f"(MPPT до {c['v_max']:.0f} В) · ток {np_ * c['imp']:.1f} А на вход{lim}{free}")
        if msg:
            txt += f"<br><span style='color:{LVL_COL[lvl]}'>{LVL_ICON[lvl]} {msg}</span>"
        self.lab_layout.setText(txt)

    # ─────────────── сводки и видимость ───────────────
    def _refresh_station(self):
        s = self.s
        builtin = s.get("mppt_mode") == "builtin"
        inv = s.get("inv_preset", "custom")
        custom_inv = inv not in INVERTER_DB
        hybrid = inv_is_hybrid(inv)
        if builtin and not (hybrid or custom_inv):        # к инвертору без MPPT — только отдельный
            s["mppt_mode"] = "separate"
            self._set_widget("mppt_mode", "separate")
            self._apply_mppt_source(mode_changed=True)
            builtin = False
        self.seg_mppt.btns["builtin"].setEnabled(hybrid or custom_inv)
        self.pk_mppt.setVisible(not builtin)
        self.lab_x2.setVisible(not builtin)
        st = self.w["n_mppt_max"]
        st.setVisible(not builtin or custom_inv)
        st.reconfigure(1, 12, 1, 0, "шт" if not builtin else "вх. MPPT")
        st.setValue(s["n_mppt_max"])
        card = self.cards.get("MPPT")
        if card is not None:
            card.setVisible(not builtin or custom_inv)
            t = card.findChild(QLabel, "cardTitle")
            if t is not None:
                t.setText("MPPT ИНВЕРТОРА" if builtin else "MPPT-КОНТРОЛЛЕР")
        for key in ("pv_pmax",):
            for wdg in self.rows.get(key, []):
                wdg.setVisible(builtin)
        h1 = self.rows.get("_h1")
        if h1:
            h1[0].setText("Кабель от панелей до инвертора" if builtin else "Кабель от панелей до контроллера")
        for key in ("_h2", "bw_len", "bw_s", "bw_mat"):
            for wdg in self.rows.get(key, []):
                wdg.setVisible(not builtin)
        if hasattr(self, "seg_wire"):
            self.seg_wire.btns["bw"].setVisible(not builtin)
            if builtin and self.seg_wire.value() == "bw":
                self.seg_wire.setValue("pv")
        # инвертор
        d = INVERTER_DB.get(inv)
        if d:
            pr = d[2]
            mp = pr.get("mppt")
            bv = f"АКБ {pr['inv_bat_v']} В" if pr["inv_bat_v"] else "АКБ любые"
            t = f"{pr['inv_p'] / 1000:g} кВт · {bv} · холостой ход ≈{pr['inv_idle']:g} Вт"
            if mp:
                nt = mp["n_mppt_max"]
                t += (f" · {inputs_word(nt)} ({nt} {plural(nt, 'трекер', 'трекера', 'трекеров')}), "
                      f"{mp['vmpp_min']:g}–{mp['vmpp_max']:g} В (Voc ≤ {mp['v_max']:g} В)"
                      + (f", до {mp['iin_max']:g} А на вход" if mp["iin_max"] else "")     # не указан — сказано в описании
                      + (f", PV до {mp['pv_pmax'] / 1000:g} кВт" if mp["pv_pmax"] else "")
                      + f", заряд до {mp['iout_max']:g} А")
            else:
                t += " · без MPPT — нужен отдельный контроллер"
            if d[3]:
                t += f" · {d[3]}"
        else:
            t = (f"Свой инвертор: {float(s['inv_p']) / 1000:g} кВт · КПД {float(s['inv_eta']):g}% · холостой ход "
                 f"{float(s['inv_idle']):g} Вт — правится в карточке «Инвертор»")
        self.lab_inv.setText(t)
        # MPPT
        if builtin:
            n = int(s["n_mppt_max"])
            io, ii = float(s["iout_max"]), float(s["iin_max"])
            t = (("Свой инвертор — параметры MPPT в карточке «MPPT инвертора». " if custom_inv else "Встроенный MPPT: ")
                 + f"{inputs_word(n)}, окно {float(s['vmpp_min']):g}–{float(s['vmpp_max']):g} В, Voc ≤ {float(s['v_max']):g} В"
                 + (f", до {ii:g} А на каждый вход" if ii > 0 else "") + f", заряд до {io:g} А"
                 + f" · занято {int(s['n_in'])} из {n}")
        else:
            n = int(s["n_mppt_max"])
            io = float(s["iout_max"])
            t = (f"Voc до {float(s['v_max']):g} В · заряд {io:g} А" + (f" × {n} = {io * n:g} А" if n > 1 else "")
                 + f" · КПД {float(s['eta']):g}% · свой расход {float(s['own_w']):g} Вт")
            md = MPPT_DB.get(s.get("m_preset"))
            if md and md[3]:
                t += f" · {md[3]}"
        self.lab_mppt.setText(t)
        # АКБ: из ячеек / АКБ меньшего напряжения — «сборки», готовые на напряжение системы — «шт»
        nser = bank_series(s)[1]
        st = self.w["bat_packs"]
        st.reconfigure(1, 10, 1, 0, "сб." if nser > 1 else "шт")
        st.setValue(s["bat_packs"])
        st.setToolTip(f"Сборок по {nser} шт последовательно, параллельно — до 10" if nser > 1
                      else "Сколько АКБ параллельно, до 10")
        for (pk, st2), gr in zip(self.bat_extra_w, bank_groups(s)[1:]):      # другие сборки: «сб.» или «шт»
            st2.reconfigure(1, 10, 1, 0, "сб." if gr["nser"] > 1 else "шт")
            st2.setValue(gr["n"])
        self._rebuild_layouts()
