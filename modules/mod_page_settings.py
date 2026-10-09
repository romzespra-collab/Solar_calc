"""mod_page_settings.py  v1.9.7
Страница «Настройки станции»: карточка «Моя станция» (что стоит), поля, пресеты, реакция на изменения.

Журнал:
v1.9.7: исправлено: «🗑 Убрать» на боковой панели убирал поле 1 / сборку 1 вместо выбранного (кнопка передавала
        checked=False как номер); «⧉ Копия» открывала не копию; инвертор без MPPT ставил 1 контроллер при 2 полях
        (ложная ошибка), копия поля в этом режиме не добавляла контроллер; «занято k из N» у поля 1 не считало
        другие поля; при смене гибрида на гибрид с меньшим числом входов лишние поля не уходили на отдельный MPPT;
        места узлов не сбрасываются, если поля не переносились. Убраны пустые подписи и мёртвые ветки.
v1.9.4: выбор погоды «📍 Регион 5 лет» — загрузка погоды региона, если её нет для точки станции.
v1.9.3: добавлять — только правым кликом на схеме: кнопок «⧉ Копия поля», «＋ Другая сборка», «＋ Ещё сборка»
        в боковой панели больше нет.
v1.9.2: нет переключателя «встроенный / отдельный»: у гибрида (и своего инвертора) — свои входы MPPT, к ним
        подключаются поля; отдельные MPPT — отдельные приборы на линии АКБ («＋ отдельный MPPT»), своя страница
        у контроллера инвертора без MPPT. Старые настройки «гибрид + отдельный» переводятся сами: поле 1 — на вход
        инвертора, полям без свободного входа — отдельный MPPT. Убрать можно и поле 1 / сборку 1 (их место
        занимает следующее), и отдельный MPPT из меню.
v1.9.1: узлы конструктора перетаскиваются мышью; места — в s["cons_pos"] (сохраняются в настройках и профиле),
        при удалении поля / сборки места следующих сдвигаются.
v1.9.0: «Моя станция» — конструктор: шаги (инвертор → АКБ → поля → кабели → дом и сеть), холст со схемой
        (во главе инвертор, поля на его входах MPPT, отдельные MPPT — к линии АКБ → инвертор, сборки АКБ, дом,
        сеть), справа — настройки выбранного узла; поля-дубли синхронны с карточками ниже.
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
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QComboBox, QLabel, QLineEdit,
                               QFrame, QScrollArea, QStackedWidget, QPushButton, QButtonGroup)

from .mod_base import log
from .mod_panels import PANEL_DB, PANEL_SERIES
from .mod_equipment import INVERTER_DB, INVERTER_SERIES, MPPT_DB, BATTERY_DB, MPPT_PRESETS, inv_is_hybrid
from .mod_fields import (INPUT_CARDS, INT_KEYS, INV_KEYS, WIRE_S_KEYS, WIRE_RANGE, PRESET_GROUPS,
                         s2d, d2s)
from .mod_model import (make_ctx, layouts, layout_status, best_layout, bank_series, layout_text,
                        inputs_word, plural, field_status, field_label, group_name, wire_r, ampacity,
                        inv_inputs_used)
from .mod_constructor import StationCanvas, dir_word as _dir_word
from .mod_config import BAT_EXTRA_MAX, PV_EXTRA_MAX, CTL_EXTRA_MAX
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

    # ─────────────── конструктор станции ───────────────
    STEPS = (("① Инвертор", "inv"), ("② АКБ", "bat"), ("③ Поля панелей", "field"), ("④ Кабели", "cable_pv"),
             ("⑤ Дом и сеть", "house"))

    def _station_card(self):
        """Конструктор: шаги сверху, холст (во главе инвертор), справа — настройки выбранного узла."""
        fr, v = _card("Моя станция — конструктор")
        self.w2 = {}                                   # поля-дубли в конструкторе (синхронны с карточками ниже)
        self._spec = {k: (lab, kind, opt, tip) for _, fields in INPUT_CARDS for k, lab, kind, opt, tip in fields}
        # шаги
        top = QHBoxLayout()
        top.setSpacing(6)
        self.step_btns = []
        grp = QButtonGroup(fr)
        grp.setExclusive(True)
        for i, (name, kind) in enumerate(self.STEPS):
            b = QPushButton(name)
            b.setObjectName("step")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, kind=kind: self._cons_pick(kind, 0, from_step=True))
            grp.addButton(b)
            self.step_btns.append(b)
            top.addWidget(b)
            if i < len(self.STEPS) - 1:
                top.addWidget(_lab("→", "fieldLab"))
        top.addStretch(1)
        self.lab_cons_sum = _lab("", "hint")
        top.addWidget(self.lab_cons_sum)
        v.addLayout(top)
        # холст + боковая панель
        body = QHBoxLayout()
        body.setSpacing(0)
        self.canvas = StationCanvas()
        self.canvas.picked.connect(lambda k, i: self._cons_pick(k, i))
        self.canvas.add.connect(self._cons_add)
        self.canvas.remove.connect(self._cons_remove)
        self.canvas.clone.connect(lambda k, i: self._fx_clone(i))
        self.canvas.moved.connect(self._cons_moved)
        body.addWidget(self.canvas, 1)
        side = QFrame()
        side.setObjectName("sidePanel")
        side.setFixedWidth(360)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(14, 12, 14, 12)
        sv.setSpacing(6)
        self.side_title = _lab("", "sideTitle")
        self.side_big = _lab("", "sideBig", True)
        self.side_big.setTextFormat(Qt.RichText)
        sv.addWidget(self.side_title)
        sv.addWidget(self.side_big)
        self.side_stack = QStackedWidget()
        sv.addWidget(self.side_stack, 1)
        body.addWidget(side)
        v.addLayout(body)
        self.pages = {}
        for name, fn in (("inv", self._pg_inv), ("ctl0", self._pg_ctl0), ("field0", self._pg_field0), ("fx", self._pg_dyn),
                         ("bat0", self._pg_bat0),
                         ("bx", self._pg_dyn), ("house", self._pg_house), ("grid", self._pg_grid), ("cable", self._pg_cable)):
            w = fn(name)
            self.pages[name] = w
            self.side_stack.addWidget(w)
        self.sel = ("inv", 0)
        return fr

    # ── страницы боковой панели ──
    def _page(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 4, 0, 0)
        v.setSpacing(6)
        return w, v

    def _cap(self, text):
        return _lab(text, "fieldLab", True)

    def _hint(self, rich=False):
        h = _lab("", "hint", True)
        if rich:
            h.setTextFormat(Qt.RichText)
        return h

    def _count(self, lo, hi, key, tip, suf="шт"):
        st = Stepper(lo, hi, 1, 0, suf)
        st.setToolTip(tip)
        st.changed.connect(lambda val, k=key: self._on_field(k, val))
        self.w[key] = st
        return st

    def _dfield(self, v, key):
        """Поле-дубль из карточек ниже (тот же ключ s) — с подписью."""
        lab, kind, opt, tip = self._spec[key]
        wdg = self._make_field(key, kind, opt, dup=True)
        wdg.setToolTip(tip)
        v.addWidget(self._cap(lab))
        v.addWidget(wdg)
        return wdg

    def _pg_inv(self, name):
        w, v = self._page()
        self.pk_inv = PresetPicker(INVERTER_DB, "Свой инвертор — параметры в карточках ниже", series=INVERTER_SERIES,
                                   what="инвертор", vertical=True)
        self.pk_inv.changed.connect(lambda k: self._on_field("inv_preset", k))
        self.w["inv_preset"] = self.pk_inv
        v.addWidget(self._cap("Инвертор: производитель → напряжение АКБ → модель"))
        v.addWidget(self.pk_inv)
        self.lab_inv = self._hint()
        v.addWidget(self.lab_inv)
        self.lab_x2 = self._cap("Сколько входов MPPT у своего инвертора")
        v.addWidget(self.lab_x2)
        v.addWidget(self._count(1, 12, "n_mppt_max", "Сколько входов MPPT у своего инвертора"))
        self.lab_mppt = self._hint()
        v.addWidget(self.lab_mppt)
        v.addStretch(1)
        return w

    def _pg_ctl0(self, name):
        """Отдельный MPPT (прибор) — у инвертора без своих MPPT: тип контроллера и сколько таких."""
        w, v = self._page()
        v.addWidget(self._cap("Отдельный MPPT-контроллер (прибор на линии АКБ → инвертор)"))
        self.pk_mppt = PresetPicker(MPPT_DB, "Свой контроллер — параметры в карточке «MPPT» ниже", what="контроллер",
                                    vertical=True)
        self.pk_mppt.changed.connect(lambda k: self._on_field("m_preset", k))
        self.w["m_preset"] = self.pk_mppt
        v.addWidget(self.pk_mppt)
        v.addWidget(self._cap("Сколько таких контроллеров (у каждого своя цепочка панелей)"))
        st = Stepper(1, 12, 1, 0, "шт")
        st.setToolTip("Сколько одинаковых контроллеров — поле 1 делится между ними")
        st.changed.connect(lambda val: self._on_field("n_mppt_max", val))
        self.w2.setdefault("n_mppt_max", []).append(st)
        self.st_nctl = st
        v.addWidget(st)
        self.lab_ctl0 = self._hint()
        v.addWidget(self.lab_ctl0)
        v.addStretch(1)
        return w

    def _pg_field0(self, name):
        w, v = self._page()
        self.pk_pan = PresetPicker(PANEL_DB, "Своя панель — паспорт ниже", series=PANEL_SERIES, what="панель", vertical=True)
        self.pk_pan.setToolTip("Производитель → серия → мощность; 🔎 — поиск по всей базе. Подставит паспорт")
        self.pk_pan.changed.connect(lambda k: self._on_field("p_preset", k))
        self.w["p_preset"] = self.pk_pan
        v.addWidget(self._cap("Панели: производитель → серия → мощность"))
        v.addWidget(self.pk_pan)
        v.addWidget(self._cap("Сколько панелей в поле"))
        v.addWidget(self._count(1, 300, "n_pan", "Сколько панелей в этом поле"))
        self.lab_total = self._hint()
        v.addWidget(self.lab_total)
        v.addWidget(self._cap("Схема поля"))
        self.cb_layout = NoWheelCombo()
        self.cb_layout.setToolTip("Как соединены панели: последовательно × параллельно, на сколько входов MPPT")
        self.cb_layout.currentIndexChanged.connect(self._on_layout)
        v.addWidget(self.cb_layout)
        v.addWidget(_btn("★ Лучшая схема", "chip", "Подобрать схему с наибольшей выработкой без ошибок",
                         lambda: self._fit_layout(force=True, announce=True)))
        self.lab_layout = self._hint(True)
        v.addWidget(self.lab_layout)
        h = QHBoxLayout()
        for key in ("tilt", "aspect"):
            vv = QVBoxLayout()
            self._dfield(vv, key)
            h.addLayout(vv)
        v.addLayout(h)
        v.addStretch(1)
        return w

    def _pg_dyn(self, name):
        w, v = self._page()
        box = QVBoxLayout()
        box.setSpacing(6)
        v.addLayout(box)
        v.addStretch(1)
        setattr(self, f"box_{name}", box)
        return w

    def _pg_bat0(self, name):
        w, v = self._page()
        self.pk_bat = PresetPicker(BATTERY_DB, "Свои АКБ — параметры в карточке ниже", what="АКБ", vertical=True)
        self.pk_bat.changed.connect(lambda k: self._on_field("bat_preset", k))
        self.w["bat_preset"] = self.pk_bat
        v.addWidget(self._cap("АКБ / ячейки"))
        v.addWidget(self.pk_bat)
        v.addWidget(self._cap("Сколько таких сборок параллельно"))
        v.addWidget(self._count(1, 10, "bat_packs", "Сколько таких сборок (или готовых АКБ) параллельно, до 10. Сколько "
                                                    "штук последовательно — по напряжению системы, считается само", "сб."))
        self.lab_bank = self._hint(True)
        v.addWidget(self.lab_bank)
        v.addStretch(1)
        return w

    def _pg_house(self, name):
        w, v = self._page()
        for key in ("load_mode", "load_kwh", "load_winter", "load_profile"):
            self._dfield(v, key)
        v.addStretch(1)
        return w

    def _pg_grid(self, name):
        w, v = self._page()
        for key in ("grid_mode", "back_soc", "tariff"):
            self._dfield(v, key)
        v.addStretch(1)
        return w

    def _pg_cable(self, name):
        w, v = self._page()
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(0, 0, 4, 0)
        iv.setSpacing(5)
        self.cab_pv = _lab("Кабель панели → инвертор", "subHead")
        iv.addWidget(self.cab_pv)
        for key in ("wire_len", "wire_s", "wire_mat", "n_main", "contact"):
            self._dfield(iv, key)
        self.cab_bw = _lab("Кабель контроллер → АКБ", "subHead")
        iv.addWidget(self.cab_bw)
        self.cab_bw_w = [self.cab_bw]
        for key in ("bw_len", "bw_s", "bw_mat"):
            wd = self._dfield(iv, key)
            self.cab_bw_w += [iv.itemAt(iv.count() - 2).widget(), wd]
        iv.addWidget(_lab("Кабель АКБ → инвертор", "subHead"))
        for key in ("iw_len", "iw_s", "iw_mat"):
            self._dfield(iv, key)
        iv.addStretch(1)
        sa.setWidget(inner)
        v.addWidget(sa, 1)
        return w

    # ── выбор узла ──
    def _cons_pick(self, kind, idx, from_step=False):
        s = self.s
        c = make_ctx(s)
        if kind == "bat" and from_step:
            idx = 0
        if kind == "ctl" and idx >= len(c["fields"]):
            kind, idx = "inv", 0
        self.sel = (kind, idx)
        self.canvas.select(kind, idx)
        step = {"inv": 0, "bat": 1, "field": 2, "ctl": 2, "cable_pv": 3, "cable_bus": 3, "cable_ctl": 3, "house": 4, "grid": 4}.get(kind)
        if step is not None:
            self.step_btns[step].setChecked(True)
        if kind == "inv":
            self.side_stack.setCurrentWidget(self.pages["inv"])
        elif kind == "ctl" and not c["fields"][idx]["ctl"]:      # контроллеры инвертора без MPPT (поле 1 и др.)
            self.side_stack.setCurrentWidget(self.pages["ctl0"])
        elif kind in ("field", "ctl"):
            if idx == 0:
                self.side_stack.setCurrentWidget(self.pages["field0"])
            else:
                self._fx_page(c, idx)
                self.side_stack.setCurrentWidget(self.pages["fx"])
        elif kind == "bat":
            if idx == 0 or idx >= len(c["groups"]):
                self.sel = ("bat", 0)
                self.canvas.select("bat", 0)
                self.side_stack.setCurrentWidget(self.pages["bat0"])
            else:
                self._bx_page(idx)
                self.side_stack.setCurrentWidget(self.pages["bx"])
        elif kind in ("house", "grid"):
            self.side_stack.setCurrentWidget(self.pages[kind])
        elif kind.startswith("cable"):
            self.side_stack.setCurrentWidget(self.pages["cable"])
        self._side_sync(c)

    def _clear(self, box):
        while box.count():
            it = box.takeAt(0)
            wd = it.widget()
            if wd is not None:
                wd.hide()
                wd.setParent(None)
                wd.deleteLater()
            elif it.layout() is not None:
                self._clear(it.layout())

    def _fx_where(self, c, idx):
        """Поле idx → («pv» | «ctl», номер в своём списке)."""
        fc = c["fields"][idx]
        kind = "ctl" if fc["ctl"] else "pv"
        same = [i for i, f in enumerate(c["fields"]) if i > 0 and bool(f["ctl"]) == bool(fc["ctl"])]
        return kind, same.index(idx)

    def _fx_page(self, c, idx):
        """Страница другого поля: (контроллер) / панели / схема / ориентация / проверка / копия, убрать."""
        box = self.box_fx
        self._clear(box)
        kind, j = self._fx_where(c, idx)
        it = (self.s.get(self._fx_key(kind)) or [])[j]
        if kind == "ctl":
            box.addWidget(self._cap("MPPT-контроллер (к линии АКБ → инвертор)"))
            mp = PresetPicker(MPPT_DB, "", what="контроллер", allow_custom=False, vertical=True)
            mp.setValue(it["mppt"])
            mp.changed.connect(lambda k, j=j: self._fx_set("ctl", j, mppt=k))
            box.addWidget(mp)
        box.addWidget(self._cap("Панели: производитель → серия → мощность"))
        pk = PresetPicker(PANEL_DB, "", series=PANEL_SERIES, what="панель", allow_custom=False, vertical=True)
        pk.setValue(it["preset"])
        pk.changed.connect(lambda k, j=j, kind=kind: self._fx_set(kind, j, preset=k))
        box.addWidget(pk)

        def step(lo, hi, val, suf, key, tip, stp=1):
            st = Stepper(lo, hi, stp, 0, suf)
            st.setValue(val)
            st.setToolTip(tip)
            st.changed.connect(lambda x, j=j, kind=kind, key=key: self._fx_set(kind, j, **{key: int(round(x)) if key in ("ns", "np") else x}))
            return st
        box.addWidget(self._cap("Схема поля: последовательно × параллельно"))
        h = QHBoxLayout()
        h.addWidget(step(1, 40, it["ns"], "посл.", "ns", "Панелей последовательно в цепочке"))
        h.addWidget(step(1, 30, it["np"], "пар.", "np", "Цепочек параллельно"))
        box.addLayout(h)
        box.addWidget(self._cap("Угол и азимут (0 — юг, −90 — восток, +90 — запад)"))
        h = QHBoxLayout()
        h.addWidget(step(0, 90, it["tilt"], "° угол", "tilt", "Угол наклона панелей этого поля"))
        h.addWidget(step(-180, 180, it["aspect"], "° азимут", "aspect", "Азимут поля", 5))
        box.addLayout(h)
        self.fx_status = self._hint(True)
        box.addWidget(self.fx_status)
        h = QHBoxLayout()
        h.addWidget(_btn("🗑 Убрать", "chip", "Убрать это поле", lambda idx=idx: self._cons_remove("field", idx)))
        h.addStretch(1)
        box.addLayout(h)

    def _bx_page(self, j):
        """Страница другой сборки АКБ."""
        box = self.box_bx
        self._clear(box)
        it = (self.s.get("bat_extra") or [])[j - 1]
        box.addWidget(self._cap("АКБ / ячейки"))
        pk = PresetPicker(BATTERY_DB, "", what="АКБ", allow_custom=False, vertical=True)
        pk.setValue(it["preset"])
        pk.changed.connect(lambda k, i=j - 1: self._bat_extra_set(i, preset=k))
        box.addWidget(pk)
        box.addWidget(self._cap("Сколько таких сборок параллельно"))
        st = Stepper(1, 10, 1, 0, "сб.")
        st.setValue(it["n"])
        st.changed.connect(lambda x, i=j - 1: self._bat_extra_set(i, n=int(round(x))))
        box.addWidget(st)
        self.bx_step = st
        self.bx_hint = self._hint()
        box.addWidget(self.bx_hint)
        h = QHBoxLayout()
        h.addWidget(_btn("🗑 Убрать", "chip", "Убрать эту сборку", lambda j=j: self._cons_remove("bat", j)))
        h.addStretch(1)
        box.addLayout(h)

    def _side_sync(self, c=None):
        """Заголовок боковой панели и проверка выбранного узла."""
        s = self.s
        c = c or make_ctx(s)
        kind, idx = self.sel
        tmin, tmax = float(s["t_min"]), float(s["t_max"])
        big = ""
        if kind == "inv":
            title = "⚡ Инвертор"
            big = f"{c['inv_p'] / 1000:g} кВт · АКБ {s['bat_v']} В"
        elif kind == "ctl" and idx < len(c["fields"]) and not c["fields"][idx]["ctl"]:
            md = MPPT_DB.get(s.get("m_preset"))
            title = "🔀 Отдельный MPPT — прибор на линии АКБ"
            big = f"{md[1] if md else 'свой контроллер'} × {int(s['n_mppt_max'])}"
        elif kind in ("field", "ctl") and idx < len(c["fields"]):
            fc = c["fields"][idx]
            lvl, msg, n = field_status(fc, tmin, tmax)
            lab = field_label(c, idx)
            title = (f"🔀 {lab} — прибор на линии АКБ, поле {idx + 1}" if kind == "ctl" else f"☀ Поле {idx + 1} → {lab}")
            big = f"<span style='color:{LVL_COL[lvl]}'>{fc['pstc_tot'] / 1000:.2f} кВт · {LVL_ICON[lvl]} {msg or 'в норме'}</span>"
            if idx > 0 and getattr(self, "fx_status", None) is not None:
                try:
                    self.fx_status.setText(
                        f"{fc['npan']} {plural(fc['npan'], 'панель', 'панели', 'панелей')} · Vmp {n['vmp']:.0f} В "
                        f"(окно {fc['vin_min']:.0f}–{fc['vmpp_max']:g} В) · Voc на морозе {n['voc_cold']:.0f} В "
                        f"(до {fc['v_max']:g} В) · ток {n['i']:.1f} А" + (f" (до {fc['iin_max']:g} А)" if fc["iin_max"] else ""))
                except RuntimeError:
                    pass
        elif kind == "bat":
            gr = c["groups"][min(idx, len(c["groups"]) - 1)]
            title = f"🔋 Сборка {idx + 1}"
            big = f"{gr['n'] * gr['ah'] * gr['v'] / 1000:.1f} кВт·ч · {gr['nser']}S × {gr['n']}"
            if idx > 0 and getattr(self, "bx_hint", None) is not None:
                try:
                    self.bx_step.reconfigure(1, 10, 1, 0, "сб." if gr["nser"] > 1 else "шт")
                    self.bx_step.setValue(gr["n"])
                    self.bx_hint.setText(f"{gr['nser']} шт последовательно — по напряжению {s['bat_v']} В (само) · "
                                         f"{gr['v']:.1f} В, {gr['n'] * gr['ah']:.0f} А·ч · заряд до {gr['n'] * gr['ah'] * gr['c']:.0f} А")
                except RuntimeError:
                    pass
        elif kind == "house":
            title = "🏠 Дом"
            big = f"≈{c['load_month']:.0f} кВт·ч в месяц"
        elif kind == "grid":
            title = "🔌 Горсеть"
            big = "есть" if s.get("grid_mode") == "backup" else "нет / отключают"
        else:
            title = "〰 Кабели"
            big = f"панели {float(s['wire_s']):g} мм² · АКБ {float(s['iw_s']):g} мм²"
        self.side_title.setText(title)
        self.side_big.setText(big)

    # ── данные холста ──
    def _cable_pv(self, fc):
        i = fc["np"] * fc["imp"]
        r20 = wire_r(fc, 20)
        du = i * r20 / max(1.0, fc["ns"] * fc["vmp"]) * 100
        lvl = "ok" if du <= 2 else "warn" if du <= 5 else "err"
        return f"{float(self.s['wire_s']):g} мм² · {float(self.s['wire_len']):g} м · −{du:.1f}%", lvl

    def _bus_lvl(self, c):
        """Кабель АКБ → инвертор (как в проверках): ток на полной мощности, допустимый ток, падение."""
        s = self.s
        i_inv = c["inv_p"] / max(0.5, c["inv_eta"]) / (c["sys_nom"] * 0.95)
        if i_inv * 1.25 > ampacity(float(s["iw_s"]), s["iw_mat"]):
            return "err", i_inv
        du = i_inv * c["ri"] / c["sys_nom"] * 100
        return ("ok" if du <= 1 else "warn" if du <= 2 else "err"), i_inv

    def _graph(self, c):
        """Узлы и связи для холста + текст схемы."""
        s = self.s
        tmin, tmax = float(s["t_min"]), float(s["t_max"])
        builtin = c["builtin"]
        nports = int(s["n_mppt_max"])
        d_inv = INVERTER_DB.get(s.get("inv_preset"))
        inv_name = (d_inv[1] if d_inv[0] == "Типовые" else f"{d_inv[0]} {d_inv[1]}") if d_inv else "Свой инвертор"
        mdb = MPPT_DB.get(s.get("m_preset"))
        A, B, lines = [], [], [f"Инвертор: {inv_name}, {c['inv_p'] / 1000:g} кВт, АКБ {s['bat_v']} В"]
        port = 0
        for i, fc in enumerate(c["fields"]):
            lvl, msg, n = field_status(fc, tmin, tmax)
            d = PANEL_DB.get(fc["key"])
            pname = (f"{d[0] if d[0] != 'Типовые' else 'панели'} {fc['pmax']:g} Вт" if d else f"панели {fc['pmax']:g} Вт")
            lab = field_label(c, i)
            mark = LVL_ICON[lvl]
            flines = [f"Поле {i + 1} → {lab.split(' (')[0]}", f"{fc['npan']} × {pname}",
                      f"{fc['ns']}S × {fc['np']}P" + (f" × {fc['k']} вх." if fc["k"] > 1 else "") + f" · {fc['tilt']:g}° {_dir_word(fc['aspect'])}",
                      (f"{mark} Vmp {n['vmp']:.0f} В · {n['i']:.1f} А", LVL_COL[lvl])]
            cab, clvl = self._cable_pv(fc)
            tip = f"Поле {i + 1} → {lab}: {fc['npan']} × {pname}\nVmp {n['vmp']:.0f} В, Voc на морозе {n['voc_cold']:.0f} В, " \
                  f"ток {n['i']:.1f} А — {mark} {msg or 'в норме'}"
            if i == 0:
                nkey = "m"
            else:
                fk, fj = self._fx_where(c, i)
                nkey = ("p" if fk == "pv" else "c") + str(fj)
            item = dict(idx=i, key=nkey, big=f"{fc['pstc_tot'] / 1000:.2f} кВт", lines=flines, lvl=lvl if clvl == "ok" else
                        ("err" if "err" in (lvl, clvl) else "warn"), cable=cab, tip=tip)
            lines.append(f"  Поле {i + 1} → {lab}: {fc['npan']} × {pname}, {fc['ns']}S×{fc['np']}P, "
                         f"{fc['pstc_tot'] / 1000:.2f} кВт, {fc['tilt']:g}° {_dir_word(fc['aspect'])} — {mark} {msg or 'в норме'}")
            if builtin and not fc["ctl"]:
                item.update(port=port, k=fc["k"])
                port += fc["k"]
                A.append(item)
            else:
                md = MPPT_DB.get(fc["ctl"]) if fc["ctl"] else mdb
                cname = md[1] if md else "свой контроллер"
                item["ctl"] = dict(big=f"{fc['iout']:.0f} А", lines=[cname, f"Voc ≤ {fc['v_max']:g} В", f"КПД {fc['eta'] * 100:.0f}%"],
                                   tip=f"{lab}: {cname}, заряд до {fc['iout']:.0f} А")
                item["cable2"] = f"{float(s['bw_s']):g} мм² · {float(s['bw_len']):g} м"
                B.append(item)
        groups = c["groups"]
        bats = []
        for j, gr in enumerate(groups):
            kwh = gr["n"] * gr["ah"] * gr["v"] / 1000
            bats.append(dict(big=f"{kwh:.1f} кВт·ч", lines=[f"Сборка {j + 1} · {gr['nser']}S × {gr['n']}", group_name(gr),
                                                           (f"полезно {kwh * gr['dod'] / 100:.1f}", _OK)],
                             tip=f"Сборка {j + 1}: {gr['nser']} шт последовательно × {gr['n']} параллельно"))
            lines.append(f"АКБ {j + 1}: {gr['nser']}S{gr['n']}P {group_name(gr)} — {kwh:.1f} кВт·ч")
        blvl, i_inv = self._bus_lvl(c)
        R = getattr(self, "R", None)
        cover = grid_y = None
        if R:
            yg = R.get("ygrid", {}).get("avg")
            if yg and yg["load"] > 0:
                cover = (1 - yg["grid_load"] / yg["load"]) * 100
                grid_y = yg["grid"]
        used = sum(a["k"] for a in A)
        return dict(
            inv=dict(big=f"{c['inv_p'] / 1000:g} кВт", builtin=builtin, ports=nports if builtin else 0,
                     lines=[inv_name, f"{s['bat_v']} В · " + (inputs_word(nports) if builtin else
                                                    "без MPPT"),
                            (f"занято {used} из {nports}" if builtin else "панели — через контроллеры",
                             _OK if (not builtin or used <= nports) else _ERR)],
                     tip=f"{inv_name}: {c['inv_p'] / 1000:g} кВт, АКБ {s['bat_v']} В"),
            a=A, b=B, bats=bats,
            add_a=(f"поле → MPPT {port + 1}" if builtin and port < nports and len(s.get("pv_extra") or []) < PV_EXTRA_MAX else None),
            add_b=("отдельный MPPT" if len(s.get("ctl_extra") or []) < CTL_EXTRA_MAX else None),
            add_bat=len(s.get("bat_extra") or []) < BAT_EXTRA_MAX,
            rm_main=bool(int(s["n_in"]) > 1 or s.get("pv_extra") or (s.get("ctl_extra") and not builtin)),
            rm_bat0=bool(s.get("bat_extra")),
            house=dict(big=f"{c['load_month']:.0f} кВт·ч", lines=["в месяц · AC 230 В"] + ([f"закрыто станцией {cover:.0f}%"] if cover is not None else [])),
            grid=dict(big="сеть" if s.get("grid_mode") == "backup" else "нет сети", on=s.get("grid_mode") == "backup",
                      lines=[f"{float(s['tariff']):g} грн/кВт·ч"] + ([f"≈{grid_y:.0f} кВт·ч/год"] if grid_y is not None else [])),
            bus=dict(text=f"{float(s['iw_s']):g} мм² · {float(s['iw_len']):g} м · {i_inv:.0f} А" + {"ok": "", "warn": " ⚠", "err": " ✗"}[blvl],
                     lvl=blvl),
            bus_v=f"шина АКБ {c['bank_v']:.1f} В",
            text="\n".join(lines))

    def _cons_update(self, c=None):
        c = c or make_ctx(self.s)
        self.canvas.set_data(self._graph(c), self._p(), dark=self.cfg.get("theme", "dark") == "dark",
                             pos=self.s.get("cons_pos") or {})
        # шаги: цвет по проверке
        s = self.s
        tmin, tmax = float(s["t_min"]), float(s["t_max"])
        fl = [field_status(fc, tmin, tmax)[0] for fc in c["fields"]]
        iv = int(float(s.get("inv_bat_v", 0) or 0))
        st_inv = "err" if (iv and iv != int(s["bat_v"])) or inv_inputs_used(c) > int(s["n_mppt_max"]) else "ok"
        st_bat = "err" if c["mismatch_v"] or len({g["chem"] for g in c["groups"]}) > 1 else "ok"
        st_pv = "err" if "err" in fl else "warn" if "warn" in fl else "ok"
        cab = [self._cable_pv(fc)[1] for fc in c["fields"]] + [self._bus_lvl(c)[0]]
        st_cab = "err" if "err" in cab else "warn" if "warn" in cab else "ok"
        for b, st in zip(self.step_btns, (st_inv, st_bat, st_pv, st_cab, "ok")):
            if b.property("st") != st:
                b.setProperty("st", st)
                b.style().unpolish(b)
                b.style().polish(b)
        yr = f" · ≈{self.R['year']['avg']:,.0f} кВт·ч/год".replace(",", " ") if getattr(self, "R", None) else ""
        self.lab_cons_sum.setText(f"Итог: {c['pstc_tot'] / 1000:.2f} кВт панелей · {c['bank_wh'] / 1000:.1f} кВт·ч АКБ{yr}")

    # ── места узлов (перетащены мышью) ──
    def _cons_moved(self, pos):
        self.s["cons_pos"] = dict(pos)                      # новый словарь — не трогаем общий по умолчанию

    def _pos_shift(self, tag, i):
        """Убрали узел i («p» — поле на входе, «c» — отдельный MPPT, «bat» — сборка): его место забыть,
        у следующих номер на 1 меньше."""
        out = {}
        for k, v in (self.s.get("cons_pos") or {}).items():
            node, _, t = k.partition(":")
            if tag == "bat":
                num, mk = (t if node == "bat" else ""), (lambda n: f"bat:{n}")
            else:
                num = t[1:] if node in ("field", "ctl") and t[:1] == tag else ""
                mk = lambda n, node=node: f"{node}:{tag}{n}"
            if num.isdigit():
                n = int(num)
                if n == i:
                    continue
                if n > i:
                    k = mk(n - 1)
            out[k] = v
        self.s["cons_pos"] = out

    # ── добавить / убрать / копия ──
    def _cons_add(self, kind):
        if kind == "bat":
            self._bat_extra_add()
            n = len(self.s.get("bat_extra") or [])
            if n:
                self._cons_pick("bat", n)
            return
        before = len(self.s.get(self._fx_key(kind)) or [])
        self._fx_add(kind)
        after = self.s.get(self._fx_key(kind)) or []
        if len(after) > before:
            c = make_ctx(self.s)
            idx = [i for i, f in enumerate(c["fields"]) if i > 0 and bool(f["ctl"]) == (kind == "ctl")][-1]
            self._cons_pick("field", idx)

    def _cons_remove(self, kind, idx):
        s = self.s
        if kind == "bat":
            if idx > 0:
                self._pos_shift("bat", idx)
                self._bat_extra_del(idx - 1)
            elif s.get("bat_extra"):                       # сборка 1: её место занимает следующая
                ex = [dict(x) for x in s["bat_extra"]]
                it = ex.pop(0)
                self._pos_shift("bat", 0)
                s["bat_extra"] = ex
                self._set_widget("bat_preset", it["preset"])
                self._on_field("bat_preset", it["preset"])
                s["bat_packs"] = int(it["n"])
                self._set_widget("bat_packs", s["bat_packs"])
                self._bat_extra_changed()
                log.info("🗑 Сборка 1 убрана — первой стала следующая")
            else:
                log.warning("⚠ Это единственная сборка АКБ — её можно поменять, но не убрать")
            self._cons_pick("bat", 0)
        elif kind in ("field", "ctl"):
            if idx > 0:
                c = make_ctx(s)
                k, j = self._fx_where(c, idx)
                self._pos_shift("p" if k == "pv" else "c", j)
                self._fx_del(k, j)
            else:
                self._remove_main()
            self._cons_pick("inv", 0)

    def _remove_main(self):
        """Убрать поле 1: на нескольких входах — на один вход меньше; иначе его место занимает следующее поле."""
        s = self.s
        if int(s["n_in"]) > 1:
            s["n_in"] = int(s["n_in"]) - 1
            s["n_pan"] = s["n_in"] * int(s["ns"]) * int(s["np"])
            self._set_widget("n_pan", s["n_pan"])
            self._refresh_station()
            self._recalc_timer.start(200)
            log.info(f"🗑 Поле 1 — на один вход меньше: {s['n_pan']} {plural(s['n_pan'], 'панель', 'панели', 'панелей')}")
            return
        builtin = s.get("mppt_mode") == "builtin"
        src = "pv_extra" if s.get("pv_extra") else ("ctl_extra" if s.get("ctl_extra") and not builtin else None)
        if not src:
            log.warning("⚠ Поле 1 — единственное " + ("на входах инвертора" if builtin else "поле")
                        + ": его можно поменять (панели, количество), но не убрать")
            return
        tag = "p" if src == "pv_extra" else "c"
        old = dict(s.get("cons_pos") or {})
        ex = [dict(x) for x in s[src]]
        it = ex.pop(0)
        s[src] = ex
        self._pos_shift(tag, 0)
        pos = {k: v for k, v in s["cons_pos"].items() if k not in ("field:m", "ctl:m")}
        for node in ("field", "ctl"):
            if f"{node}:{tag}0" in old:
                pos[f"{node}:m"] = old[f"{node}:{tag}0"]
        s["cons_pos"] = pos
        for k, v in (("ns", int(it["ns"])), ("np", int(it["np"])), ("n_in", 1), ("tilt", float(it["tilt"])),
                     ("aspect", float(it["aspect"]))):
            s[k] = v
            self._set_widget(k, v)
        s["n_pan"] = s["ns"] * s["np"]
        self._set_widget("n_pan", s["n_pan"])
        if src == "ctl_extra" and it.get("mppt") != s.get("m_preset"):
            self._set_widget("m_preset", it["mppt"])
            self._on_field("m_preset", it["mppt"])
        self._set_widget("p_preset", it["preset"])
        self._on_field("p_preset", it["preset"])
        log.info("🗑 Поле 1 убрано — первым стало следующее поле")

    def _fx_clone(self, idx):
        """Копия поля: основное → ещё одно такое же на следующий вход; другое — ещё такое же в свой список."""
        s = self.s
        c = make_ctx(s)
        if idx == 0:
            if s.get("mppt_mode") == "builtin" and inv_inputs_used(c) < int(s["n_mppt_max"]):
                s["n_in"] = int(s["n_in"]) + 1                      # одинаковое поле — ещё на один вход
                s["n_pan"] = s["n_in"] * int(s["ns"]) * int(s["np"])
                self._set_widget("n_pan", s["n_pan"])
                self._refresh_station()
                self._recalc_timer.start(200)
            elif s.get("mppt_mode") == "builtin":
                log.warning(f"⚠ У инвертора {inputs_word(int(s['n_mppt_max']))} — все заняты. Ещё поле — через "
                            f"отдельный MPPT (＋ отдельный MPPT на схеме)")
            else:
                self._cons_add("pv")
            return
        kind, j = self._fx_where(c, idx)
        key = self._fx_key(kind)
        ex = [dict(x) for x in s.get(key) or []]
        if kind == "pv" and s.get("mppt_mode") == "builtin" and inv_inputs_used(c) >= int(s["n_mppt_max"]):
            log.warning("⚠ У инвертора все входы MPPT заняты — копия не влезет")
            return
        if len(ex) >= (PV_EXTRA_MAX if kind == "pv" else CTL_EXTRA_MAX):
            return
        ex.append(dict(ex[j]))
        s[key] = ex
        if kind == "pv" and s.get("mppt_mode") != "builtin" and int(s["n_in"]) + len(ex) > int(s["n_mppt_max"]):
            s["n_mppt_max"] = int(s["n_in"]) + len(ex)           # у отдельных контроллеров — ещё один такой же
            self._set_widget("n_mppt_max", s["n_mppt_max"])
        self._refresh_station()
        self._recalc_timer.start(200)
        fields = make_ctx(s)["fields"]                           # копия — последняя в своём списке
        self._cons_pick("field", max(i for i, f in enumerate(fields) if i > 0 and bool(f["ctl"]) == (kind == "ctl")))

    # ─────────────── другие поля: на входах инвертора и на отдельных MPPT ───────────────
    def _fx_key(self, kind):
        return "pv_extra" if kind == "pv" else "ctl_extra"

    def _fx_set(self, kind, i, **kw):
        key = self._fx_key(kind)
        ex = [dict(x) for x in self.s.get(key) or []]           # новый список — расчёт в фоне видит целый
        if 0 <= i < len(ex):
            ex[i].update(kw)
            self.s[key] = ex
            self._refresh_station()
            self._recalc_timer.start(200)

    def _fx_add(self, kind):
        s = self.s
        key = self._fx_key(kind)
        ex = [dict(x) for x in s.get(key) or []]
        if kind == "pv":
            used = int(s["n_in"]) + len(ex)
            if s.get("mppt_mode") == "builtin" and used >= int(s["n_mppt_max"]):
                log.warning(f"⚠ У инвертора {inputs_word(int(s['n_mppt_max']))} — все заняты. Поставьте отдельный MPPT "
                            f"на линию АКБ (＋ отдельный MPPT)")
                return
            if len(ex) >= PV_EXTRA_MAX:
                return
        elif len(ex) >= CTL_EXTRA_MAX:
            return
        pk = s.get("p_preset") if s.get("p_preset") in PANEL_DB else "p410"
        it = dict(preset=pk, ns=int(s["ns"]), np=int(s["np"]), tilt=float(s["tilt"]), aspect=float(s["aspect"]))
        if kind == "ctl":
            it["mppt"] = s.get("m_preset") if s.get("m_preset") in MPPT_DB else "cn60"
            mp = MPPT_DB[it["mppt"]][2]
            p = PANEL_DB[pk][2]                                  # столько последовательно, чтобы Voc на морозе влез
            voc_cold = p["voc"] * (1 + p["bvoc"] / 100.0 * (float(s["t_min"]) - 25))
            it["ns"] = max(1, min(40, int(mp["v_max"] * 0.95 // max(1.0, voc_cold))))
            it["np"] = 1
        ex.append(it)
        s[key] = ex
        if kind == "pv" and s.get("mppt_mode") != "builtin" and int(s["n_in"]) + len(ex) > int(s["n_mppt_max"]):
            s["n_mppt_max"] = int(s["n_in"]) + len(ex)           # у отдельных контроллеров — ещё один такой же
            self._set_widget("n_mppt_max", s["n_mppt_max"])
        self._refresh_station()
        self._recalc_timer.start(200)
        log.info("＋ Добавлено поле " + ("на вход MPPT" if kind == "pv" else "с отдельным MPPT на линии АКБ") + " — выберите панели и схему")

    def _fx_del(self, kind, i):
        key = self._fx_key(kind)
        ex = [dict(x) for x in self.s.get(key) or []]
        if 0 <= i < len(ex):
            ex.pop(i)
            self.s[key] = ex
            self._refresh_station()
            self._recalc_timer.start(200)

    def _cons_reset(self):
        """После загрузки профиля: выбранный узел мог исчезнуть — показать заново."""
        kind, idx = getattr(self, "sel", ("inv", 0))
        c = make_ctx(self.s)
        if (kind == "field" and idx >= len(c["fields"])) or (kind == "bat" and idx >= len(c["groups"])):
            kind, idx = "inv", 0
        self._cons_pick(kind, idx)

    # ─────────────── другие сборки АКБ ───────────────
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
        self._bat_extra_changed()
        log.info(f"＋ Добавлена сборка АКБ {len(ex) + 1} — выберите её тип")

    def _bat_extra_del(self, i):
        ex = [dict(x) for x in self.s.get("bat_extra") or []]
        if 0 <= i < len(ex):
            ex.pop(i)
            self.s["bat_extra"] = ex
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

    def _make_field(self, key, kind, opt, dup=False):
        """Поле ввода по описанию. dup=True — второе поле того же ключа (в конструкторе), синхронное с первым."""
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
        if dup:
            self.w2.setdefault(key, []).append(wdg)
        else:
            self.w[key] = wdg
        return wdg

    # ─────────────── значения ───────────────
    def _set_widget(self, key, val):
        for wdg in [self.w.get(key)] + getattr(self, "w2", {}).get(key, []):
            if wdg is not None:
                self._set_one(wdg, key, val)

    def _set_one(self, wdg, key, val):
        wdg.blockSignals(True)
        try:
            if isinstance(wdg, Stepper):
                if key in WIRE_S_KEYS and self.s.get("wire_mode") == "d":
                    val = s2d(val)
                if abs(float(wdg.value()) - float(val)) > 1e-9:      # то же — не трогаем (не сбить ввод)
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
            for wd in [self.w[k]] + self.w2.get(k, []):
                wd.reconfigure(*WIRE_RANGE[self.s.get("wire_mode", "s")])
        for k in self.w:
            if k in self.s:
                self._set_widget(k, self.s[k])
        self._sync_mw()
        self.st_ser_days.setValue(self.s["ser_days"])
        self.seg_ser_w.setValue(self.s["ser_weather"])
        self.st_ser_soc.setValue(self.s["ser_soc0"])
        self.st_g.setValue(self.s["pt_g"])
        self.st_t.setValue(self.s["pt_t"])
        self._refresh_station()
        self._cons_reset()

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
        if key in getattr(self, "w2", {}):
            self._set_widget(key, val)                     # то же поле в конструкторе и в карточке ниже
        if key == "wire_mode":
            for k in WIRE_S_KEYS:
                for wd in [self.w[k]] + self.w2.get(k, []):
                    wd.reconfigure(*WIRE_RANGE[val])
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
        elif key == "n_pan":
            self._fit_layout(force=True)
        elif key == "n_mppt_max":
            self._fit_layout()
        if key in ("bat_v", "chem"):
            self._bat_auto()
        if key in ("pt_g", "pt_t"):
            self._update_point()
            return
        if key in ("weather", "ser_weather") and val == "reg":
            self.load_region(auto=True)                # погоды региона для точки нет — загрузить (в фоне)
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
            self._overflow_to_ctl()                        # входов меньше, чем полей — лишние на отдельный MPPT
        else:
            pr = MPPT_PRESETS.get(s["m_preset"], (None, None))[1]
            if pr:
                for k, v in pr.items():
                    s[k] = v
                    self._set_widget(k, v)
            s["pv_pmax"] = 0
            self._set_widget("pv_pmax", 0)
            if mode_changed:                               # контроллеров — столько, сколько полей на них
                s["n_mppt_max"] = max(1, int(s["n_in"]) + len(s.get("pv_extra") or []))
                self._set_widget("n_mppt_max", s["n_mppt_max"])
        self._fit_layout()

    def _overflow_to_ctl(self):
        """Поля на входы инвертора: кому не хватило входа MPPT — на отдельный MPPT у линии АКБ (тот же контроллер)."""
        s = self.s
        n = int(s["n_mppt_max"])
        ex = [dict(x) for x in s.get("pv_extra") or []]
        keep = max(0, n - 1)                                   # основному полю — хотя бы один вход
        if len(ex) <= keep:
            return
        ce = [dict(x) for x in s.get("ctl_extra") or []]
        mp = s.get("m_preset") if s.get("m_preset") in MPPT_DB else "cn60"
        moved = []
        while len(ex) > keep and len(ce) < CTL_EXTRA_MAX:
            it = ex.pop(keep)
            ce.append(dict(it, mppt=mp))
            moved.append(len(moved) + keep + 2)
        if not moved:
            return
        s["pv_extra"], s["ctl_extra"] = ex, ce
        s["cons_pos"] = {k: v for k, v in (s.get("cons_pos") or {}).items()
                         if not k.split(":")[-1].startswith(("p", "c"))}   # номера сменились — места заново
        if moved:
            log.warning(f"⚠ У инвертора {inputs_word(n)} — " + ("поле " if len(moved) == 1 else "поля ")
                        + ", ".join(map(str, moved)) + " подключены к отдельному MPPT на линии АКБ. Чтобы все поля "
                        f"шли в инвертор, выберите модель с {n + len(moved)} входами MPPT")

    # ─────────────── схема (раскладка панелей) ───────────────
    def _layout_sig(self):
        s = self.s
        return tuple(str(s.get(k)) for k in ("n_pan", "n_mppt_max", "mppt_mode", "inv_preset", "m_preset", "p_preset",
                                              "pmax", "vmp", "voc", "imp", "v_max", "vmpp_min", "vmpp_max", "iin_max"))

    def _fit_layout(self, force=False, announce=False):
        """Подобрать раскладку: по кнопке/при смене количества, или если текущая не подходит (входы, ошибка)."""
        s = self.s
        n, kmax = int(s["n_pan"]), self._main_kmax()
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

    def _main_kmax(self):
        """Сколько входов может занять основное поле: остальные — под другие поля."""
        return max(1, int(self.s["n_mppt_max"]) - len(self.s.get("pv_extra") or []))

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
        for o in layouts(int(s["n_pan"]), self._main_kmax()):
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
        k_all = inv_inputs_used(c) if not sep else k + len(s.get("pv_extra") or [])   # с другими полями
        where = (f"На {'каждый ' if k > 1 else ''}{'контроллер' if sep else 'вход MPPT'}: {ns * np_} "
                 f"{plural(ns * np_, 'панель', 'панели', 'панелей')} — ")
        free = (f" · занято {k_all} из {kmax}, свободно {kmax - k_all}" if kmax > k_all else
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
        want = "builtin" if (hybrid or custom_inv) else "separate"   # свои MPPT — у гибрида; без MPPT — отдельные приборы
        if s.get("mppt_mode") != want:
            s["mppt_mode"] = want
            self._apply_mppt_source(mode_changed=True)
            builtin = want == "builtin"
        self.lab_x2.setVisible(builtin and custom_inv)
        st = self.w["n_mppt_max"]
        st.setVisible(builtin and custom_inv)
        st.reconfigure(1, 12, 1, 0, "вх. MPPT")
        st.setValue(s["n_mppt_max"])
        self.st_nctl.reconfigure(1, 12, 1, 0, "шт")
        self.st_nctl.setValue(s["n_mppt_max"])
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
        sep_any = (not builtin) or bool(s.get("ctl_extra"))      # есть контроллер со своим кабелем до АКБ
        for key in ("_h2", "bw_len", "bw_s", "bw_mat"):
            for wdg in self.rows.get(key, []):
                wdg.setVisible(sep_any)
        if hasattr(self, "seg_wire"):
            self.seg_wire.btns["bw"].setVisible(sep_any)
            if not sep_any and self.seg_wire.value() == "bw":
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
            t = (("Свой инвертор — параметры MPPT в карточке «MPPT инвертора». " if custom_inv else "Свои MPPT инвертора: ")
                 + f"{inputs_word(n)}, окно {float(s['vmpp_min']):g}–{float(s['vmpp_max']):g} В, Voc ≤ {float(s['v_max']):g} В"
                 + (f", до {ii:g} А на каждый вход" if ii > 0 else "") + f", заряд до {io:g} А"
                 + f" · занято {inv_inputs_used(make_ctx(s))} из {n}")
        else:
            n = int(s["n_mppt_max"])
            io = float(s["iout_max"])
            t2 = (f"Voc до {float(s['v_max']):g} В · заряд {io:g} А" + (f" × {n} = {io * n:g} А" if n > 1 else "")
                  + f" · КПД {float(s['eta']):g}% · свой расход {float(s['own_w']):g} Вт")
            md = MPPT_DB.get(s.get("m_preset"))
            if md and md[3]:
                t2 += f" · {md[3]}"
            self.lab_ctl0.setText(t2)
            t = ("У этого инвертора нет своих MPPT — панели подключаются через отдельные MPPT-контроллеры (приборы "
                 "на линии АКБ → инвертор). Нажмите на контроллер на схеме, чтобы выбрать его")
        self.lab_mppt.setText(t)
        # АКБ: из ячеек / АКБ меньшего напряжения — «сборки», готовые на напряжение системы — «шт»
        nser = bank_series(s)[1]
        st = self.w["bat_packs"]
        st.reconfigure(1, 10, 1, 0, "сб." if nser > 1 else "шт")
        st.setValue(s["bat_packs"])
        st.setToolTip(f"Сборок по {nser} шт последовательно, параллельно — до 10" if nser > 1
                      else "Сколько АКБ параллельно, до 10")
        for wd in getattr(self, "cab_bw_w", []):
            wd.setVisible(sep_any)
        self.cab_pv.setText("Кабель панели → инвертор" if builtin else "Кабель панели → контроллер")
        c = make_ctx(s)
        self._cons_update(c)
        self._side_sync(c)
        self._rebuild_layouts()
