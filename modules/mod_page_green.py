"""mod_page_green.py  v1.10.0
Страница «💰 Зелёный тариф» — одна страница без вкладок: слева настройки группами (раскрываются: место и сеть,
счётчик и тариф, монтаж и инвертор, мои цены, цены рынка, документы и шаги), справа результат одной лентой
(накопленная выгода, итоги за год, по месяцам, проверки, смета, солнце за 5 лет, расчёт по месяцам; таблицы —
по высоте строк, без пустых окон). Станция (панели, инвертор, АКБ, выработка, потребление дома) — из ⚙ Настроек.

Журнал:
v1.10.0: первая версия — из «Калькулятора зелёного тарифа» v1.2.0, связана со станцией и погодой региона.
"""

import json

from PySide6.QtCore import Qt, QTimer, QUrl, QRect, QSize
from PySide6.QtGui import QDesktopServices, QGuiApplication, QFontMetrics
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QFrame, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QMenu, QTableWidgetItem, QLineEdit, QHeaderView, QPushButton, QLabel,
                               QComboBox)

from .mod_base import APP_ROOT, log
from .mod_equipment import INVERTER_DB
from .mod_theme import _OK, _ERR, _WARN
from .mod_widgets import (Toggle, Segmented, NoWheelCombo, Stepper, Chart, _Spin, _lab, _card, _btn, _item,
                          make_table, export_table_csv, table_tsv, ask_save, _save_failed, app_version)
from . import mod_green as G

GEN_COL, CONS_COL, EXP_COL = "#f5b545", "#4f8cff", "#3ecf8e"
SUN_COLS = ("#f5b545", "#8a91a3", "#5c6577")


class _Section(QWidget):
    """Группа настроек слева: заголовок (▾/▸, клик — свернуть) + поля; свёрнутая показывает краткий итог."""

    def __init__(self, title, opened=True, first=False):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self.head = QPushButton()
        self.head.setObjectName("accHead")
        self.head.setProperty("first", "true" if first else "false")
        self.head.setCheckable(True)
        self.head.setCursor(Qt.PointingHandCursor)
        hl = QHBoxLayout(self.head)
        hl.setContentsMargins(2, 0, 2, 0)
        hl.setSpacing(6)
        self.arrow = QLabel()
        self.arrow.setObjectName("accTitle")
        self.title = QLabel(title.upper())
        self.title.setObjectName("accTitle")
        self.sum = QLabel("")
        self.sum.setObjectName("accSum")
        for lb in (self.arrow, self.title, self.sum):
            lb.setAttribute(Qt.WA_TransparentForMouseEvents)
        hl.addWidget(self.arrow)
        hl.addWidget(self.title)
        hl.addStretch(1)
        hl.addWidget(self.sum)
        self.body = QWidget()
        self.grid = QGridLayout(self.body)
        self.grid.setContentsMargins(0, 2, 0, 10)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(7)
        self.grid.setColumnMinimumWidth(0, 96)
        self.grid.setColumnStretch(1, 1)
        v.addWidget(self.head)
        v.addWidget(self.body)
        self.head.toggled.connect(self._show)
        self.head.setChecked(opened)
        self._show(opened)

    def _show(self, on):
        self.body.setVisible(on)
        self.arrow.setText("▾" if on else "▸")
        self.sum.setVisible(not on)


class GreenPages:
    """Миксин окна: страница зелёного тарифа. Настройки — в self.s["green"] (сохраняются с профилем станции)."""

    # ─────────────── построение ───────────────
    def _page_green(self):
        self.gw = {}
        self.g_secs = {}
        self._G = None
        self._g_loading = False
        self._g_timer = QTimer(self)
        self._g_timer.setSingleShot(True)
        self._g_timer.setInterval(80)
        self._g_timer.timeout.connect(self._green_update)
        pg, v = self._page()
        v.setSpacing(10)
        pg.setContextMenuPolicy(Qt.CustomContextMenu)
        pg.customContextMenuRequested.connect(lambda pos: self._green_menu(pg.mapToGlobal(pos)))
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        hdr.addWidget(_lab("💰 Зелёный тариф", "bigTitle"))
        sub = _lab(f"{G.fnum(G.GREEN_TARIFF, 3)} грн/кВт·ч до 01.01.2030 (НКРЭКУ № 1613) · станция — из ⚙ Настроек",
                   "hint")
        hdr.addWidget(sub)
        hdr.addStretch(1)
        hdr.addWidget(_btn("⚙ Станция", None, "Панели, инвертор, АКБ, потребление дома — в настройках станции",
                           lambda: self._go_page(self.page_idx["settings"])))
        hdr.addWidget(_btn("📄 Отчёт HTML…", "primary", "Сохранить отчёт и открыть в браузере (печать, отправка)",
                           self.green_report))
        v.addLayout(hdr)
        kp = QGridLayout()
        kp.setSpacing(10)
        self.gk = {}
        for i, (k, cap) in enumerate((("station", "Станция"), ("budget", "Бюджет (мин – макс)"),
                                      ("osr", "Платежи в ОСР (РЭС)"), ("pay", "Окупаемость"))):
            fr = QFrame()
            fr.setObjectName("kpi")
            fv = QVBoxLayout(fr)
            fv.setContentsMargins(12, 6, 12, 6)
            fv.setSpacing(0)
            val = _lab("—", "kpiVal")
            sub = _lab("", "kpiCap", True)
            fv.addWidget(_lab(cap, "kpiCap"))
            fv.addWidget(val)
            fv.addWidget(sub)
            self.gk[k] = (val, sub)
            kp.addWidget(fr, 0, i)
        v.addLayout(kp)
        body = QHBoxLayout()
        body.setSpacing(10)
        left = self._g_left()
        left.setFixedWidth(404)
        body.addWidget(left)
        body.addWidget(self._g_right(), 1)
        v.addLayout(body, 1)
        self._g_load()
        return pg

    def _g_menu_on(self, w):
        w.setContextMenuPolicy(Qt.CustomContextMenu)
        w.customContextMenuRequested.connect(lambda pos, w=w: self._green_menu(w.mapToGlobal(pos)))

    # ── слева: настройки группами (раскрываются) ──
    def _g_left(self):
        inner = QWidget()
        self._g_menu_on(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(0)
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 2, 12, 8)
        cl.setSpacing(0)
        for key, title, opened, build in (("place", "Место и сеть", True, self._g_sec_place),
                                          ("tariff", "Счётчик и тариф", True, self._g_sec_tariff),
                                          ("mount", "Монтаж и инвертор", False, self._g_sec_mount),
                                          ("own", "Мои цены", False, self._g_sec_own),
                                          ("prices", "Цены рынка", False, self._g_sec_prices),
                                          ("docs", "Документы и шаги", False, self._g_sec_docs)):
            sec = _Section(title, opened, first=not self.g_secs)
            build(sec.grid)
            if key == "docs":
                sec.head.toggled.connect(lambda on: on and QTimer.singleShot(0, self._g_fit_list))
            cl.addWidget(sec)
            self.g_secs[key] = sec
        lay.addWidget(card)
        lay.addStretch(1)
        sa = self._scroll(inner)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return sa

    @staticmethod
    def _g_row(grid, label, w, tip=""):
        r = grid.rowCount()
        lb = _lab(label, "fieldLab")
        if tip:
            lb.setToolTip(tip)
            w.setToolTip(tip)
        grid.addWidget(lb, r, 0)
        grid.addWidget(w, r, 1)
        return lb

    @staticmethod
    def _g_span(grid, w):
        grid.addWidget(w, grid.rowCount(), 0, 1, 2)
        return w

    def _g_toggle_row(self, grid, key, text, tip=""):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self._g_toggle(key))
        lb = _lab(text, "fieldLab", True)
        row.addWidget(lb, 1)
        w = QWidget()
        w.setLayout(row)
        if tip:
            w.setToolTip(tip)
        self._g_span(grid, w)

    def _g_sec_place(self, grid):
        self._g_row(grid, "Область", self._g_combo("region", [("", "Авто — по координатам")] +
                                                  [(r[0], r[0]) for r in G.REGIONS]),
                    "Область станции — для ставок ОСР. Авто: ближайший областной центр к широте/долготе из ⚙ Настроек")
        self._g_row(grid, "ОСР", self._g_combo("osr", [("", "По области")] + [(n, n) for n in sorted(G.OSR_RATES)]),
                    "Оператор системы распределения (облэнерго)")
        self._g_row(grid, "Местность", self._g_seg("area", G.AREAS), "Ставки присоединения в селе ниже, чем в городе")
        self._g_row(grid, "Подключение", self._g_combo("conn", (("ok", "Мощности хватает"),
                                                               ("increase", "Увеличить мощность"),
                                                               ("new", "Подключения ещё нет"))))
        self._g_row(grid, "Ввод в дом", self._g_seg("phase", (("3", "3 фазы"), ("1", "1 фаза"), ("?", "не знаю"))))
        self._g_row(grid, "Разрешено", self._g_step("permitted", 0, 150, 0.5, 1, "кВт"),
                    "Разрешённая мощность — из договора с ОСР или личного кабинета облэнерго; 0 — не знаю")
        self._g_toggle_row(grid, "grid_auto", "Плату ОСР оценить по ставкам НКРЭКУ 2026")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self._g_step("grid_cost", 0, 5_000_000, 500, 0, "грн"), 1)
        row.addWidget(_btn("↗", "chip", "Калькулятор стандартного присоединения НКРЭКУ (поиск)",
                           lambda: QDesktopServices.openUrl(QUrl(G.URL_CONN_CALC))))
        w = QWidget()
        w.setLayout(row)
        self._g_row(grid, "Своя сумма", w, "Сумма из счёта ОСР или калькулятора НКРЭКУ")
        self.g_grid = self._g_span(grid, self._rich())

    def _g_sec_tariff(self, grid):
        self._g_row(grid, "Учёт", self._g_seg("meter_zones", (("2", "День/ночь"), ("1", "1 зона"), ("3", "3 зоны"))),
                    "Счётчик: день/ночь (2 зоны), однозонный или ночь/полупик/пик (3 зоны)")
        self.g_tariff = Stepper(0, 50, 0.01, 2, "грн")
        self.g_tariff.changed.connect(self._g_tariff)
        self._g_row(grid, "Цена дома", self.g_tariff, "Цена для населения, грн/кВт·ч — общая со станцией (⚙ Сеть и "
                                                      "тариф): 4,32 грн до 31.10.2026, дальше — решение КМУ")
        self.g_zones = self._g_span(grid, _lab("", "hint", True))
        self._g_row(grid, "Взаимозачёт", self._g_seg("net_mode", (("total", "За месяц"), ("zones", "По зонам"))),
                    "Как поставщик сводит сальдо при зонном учёте — уточните в договоре.\n«По зонам» выгоднее: "
                    "ночное потребление не «съедает» дневную продажу")
        self._g_row(grid, "Погода", self._g_seg("weather", (("reg", "📍 Регион"), ("avg", "⛅ Средний"))),
                    "📍 Регион 5 лет — реальная погода (и разброс по годам), если загружена; иначе — средний год")
        self._g_row(grid, "Зелёный тариф", self._g_step("green", 0, 50, 0.001, 3, "грн"),
                    "Грн/кВт·ч без НДС. НКРЭКУ № 1613 с 01.10.2026 — 613,40 коп. Пересматривается ежеквартально")
        self._g_row(grid, "Налог", self._g_step("tax", 0, 60, 0.5, 1, "%"),
                    "18 % НДФЛ + 5 % военный сбор, удерживает поставщик")
        self._g_row(grid, "Год ввода", self._g_step("start_year", 2024, 2040, 1, 0, ""),
                    "Год ввода СЭС. Зелёный тариф платят до 01.01.2030")
        self._g_row(grid, "После 2029", self._g_step("post_price", 0, 20, 0.05, 2, "грн"),
                    "Цена продажи после 2029, грн/кВт·ч: самопроизводство — цена РДН, но не выше тарифа для населения")
        self._g_row(grid, "Деградация", self._g_step("degr", 0, 5, 0.1, 1, "%/год"), "Деградация панелей в год")
        self._g_row(grid, "Горизонт", self._g_step("years", 5, 40, 1, 0, "лет"), "На сколько лет считать выгоду")

    def _g_sec_mount(self, grid):
        self.g_station = self._g_span(grid, self._rich())
        self._g_row(grid, "Панели", self._g_seg("mount", (("roof", "Крыша"), ("ground", "Земля"))),
                    "Крыша / фасад — до 50 кВт; на земле (участок) — до 30 кВт")
        self._g_row(grid, "Поле → щит", self._g_step("field_dist", 0, 1000, 5, 0, "м"),
                    "Длина кабеля и траншеи от поля до электрощита")
        self._g_row(grid, "Отдаёт в сеть", self._g_seg("export", G.EXPORT_MODES),
                    "Умеет ли инвертор продавать в сеть (on-grid / гибрид с экспортом). «По модели» — по серии инвертора")
        self._g_toggle_row(grid, "meter_paid", "Двунаправленный счётчик покупаю у ОСР")

    def _g_sec_own(self, grid):
        self._g_span(grid, _lab("Если цена уже известна (счёт, предложение) — впишите всю сумму: она заменит оценку.",
                                "hint", True))
        self.g_own = {}
        for key, title in G.OWN_KEYS:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            st = Stepper(0, 100_000_000, 1000, 0, "грн")
            st.changed.connect(lambda x, key=key: self._g_own_set(key, float(x)))
            row.addWidget(st, 1)
            rb = _btn("↺", "chip", "Вернуть оценку", lambda key=key: self._g_own_set(key, 0.0, True))
            row.addWidget(rb)
            box = QWidget()
            box.setLayout(row)
            self._g_row(grid, title.replace(" (все)", ""), box)
            hint = _lab("", "hint", True)
            grid.addWidget(hint, grid.rowCount(), 1)
            self.g_own[key] = (st, rb, hint)
        self._g_row(grid, "Доп. материалы", self._g_step("extra_mat", 0, 10_000_000, 500, 0, "грн"),
                    "Ваша сумма: бетон, сетка/забор, болты, кабель-канал — всё, чего нет в смете")
        ed = QLineEdit()
        ed.setPlaceholderText("бетон, забор, болты…")
        ed.editingFinished.connect(lambda: self._g_set("extra_note", ed.text()[:200]))
        self.gw["extra_note"] = ed
        self._g_row(grid, "Что это", ed)

    def _g_sec_prices(self, grid):
        self._g_span(grid, _lab("Ориентиры рынка 2026, мин – макс. Подставьте цены из своих предложений — смета и "
                                "окупаемость пересчитаются сразу. Правый клик по строке — сбросить её.", "hint", True))
        self.g_price_w = {}
        for r, (key, label, unit, _mn, _mx, dec) in enumerate(G.PRICE_DEFS):
            lb = _lab(f"{label}, {unit}", "fieldLab", True)
            lb.setContextMenuPolicy(Qt.CustomContextMenu)
            lb.customContextMenuRequested.connect(lambda pos, r=r, lb=lb: self._g_price_menu(r, lb.mapToGlobal(pos)))
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            pair = []
            for idx in (0, 1):
                sp = _Spin()
                sp.setDecimals(dec)
                sp.setRange(0, 10_000_000)
                sp.setSingleStep(0.05 if dec else 100)
                sp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                sp.setKeyboardTracking(False)
                sp.setFocusPolicy(Qt.StrongFocus)
                sp.setFixedWidth(84)
                sp.setToolTip(("Мин" if idx == 0 else "Макс") + f", {unit}")
                sp.valueChanged.connect(lambda val, k=key, i=idx: self._g_price_set(k, i, val))
                row.addWidget(sp)
                pair.append(sp)
            box = QWidget()
            box.setLayout(row)
            rr = grid.rowCount()
            grid.addWidget(lb, rr, 0)
            grid.addWidget(box, rr, 1, Qt.AlignRight)
            self.g_price_w[key] = pair
        self._g_span(grid, _btn("↺ Все цены — ориентиры 2026", None, "Вернуть все диапазоны цен по умолчанию",
                                self._g_prices_reset))

    def _g_sec_docs(self, grid):
        self.g_progress = self._g_span(grid, _lab("", "hint", True))
        self.g_check = QListWidget()
        self.g_check.setObjectName("gcheck")
        self.g_check.setWordWrap(True)
        self.g_check.setTextElideMode(Qt.ElideNone)
        self.g_check.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.g_check.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.g_check.setContextMenuPolicy(Qt.CustomContextMenu)
        self.g_check.customContextMenuRequested.connect(self._g_check_menu)
        for section, items in G.STEPS:
            h = QListWidgetItem(section.upper())
            h.setFlags(Qt.ItemIsEnabled)
            f = h.font()
            f.setBold(True)
            h.setFont(f)
            h.setData(Qt.UserRole, "")
            self.g_check.addItem(h)
            for text in items:
                it = QListWidgetItem(text)
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
                it.setCheckState(Qt.Unchecked)
                it.setData(Qt.UserRole, text)
                self.g_check.addItem(it)
        self.g_check.itemChanged.connect(self._g_check_changed)
        self._g_span(grid, self.g_check)
        QTimer.singleShot(0, self._g_fit_list)
        notes = self._g_span(grid, self._rich())
        notes.setText(G.NOTES_HTML)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for text, url in (("НКРЭКУ ↗", G.URL_NERC), ("Присоединение ↗", G.URL_CONN_CALC), ("Тариф № 1613 ↗", G.URL_TARIFF_NEWS)):
            row.addWidget(_btn(text, "chip", url, lambda u=url: QDesktopServices.openUrl(QUrl(u))))
        row.addStretch(1)
        w = QWidget()
        w.setLayout(row)
        self._g_span(grid, w)
        self.g_notes = QPlainTextEdit()
        self.g_notes.setPlaceholderText("Мои заметки: номера заявок, ответы ОСР, контакты установщика…")
        self.g_notes.setFixedHeight(96)
        self.g_notes.textChanged.connect(self._g_notes_changed)
        self._g_span(grid, self.g_notes)

    def _g_fit_list(self):
        """Список шагов — по высоте содержимого (без своей прокрутки): высота каждой строки по переносу текста."""
        lw = self.g_check
        w = lw.width() - 2 * lw.frameWidth() - 44            # галочка, отступы
        if w < 120:
            return
        total = 0
        for i in range(lw.count()):
            it = lw.item(i)
            fm = QFontMetrics(it.font())
            h = fm.boundingRect(QRect(0, 0, w, 10000), Qt.TextWordWrap, it.text()).height() + 12
            it.setSizeHint(QSize(w, h))
            total += h
        lw.setFixedHeight(total + 2 * lw.frameWidth() + 4)

    # ── справа: результат одной лентой ──
    def _g_right(self):
        inner = QWidget()
        self._g_menu_on(inner)
        grid = QGridLayout(inner)
        grid.setContentsMargins(0, 0, 6, 0)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 6)
        grid.setColumnStretch(1, 5)
        self.g_cards = {}

        def chart_card(ch, key):
            fr = QFrame()
            fr.setObjectName("card")
            cl = QVBoxLayout(fr)
            cl.setContentsMargins(10, 8, 10, 6)
            cl.addWidget(ch)
            self.charts.append(ch)
            self.g_cards[key] = fr
            return fr

        self.gch_cum = Chart("line", "грн", "Накопленная выгода")
        self.gch_cum.xfmt = "year"
        grid.addWidget(chart_card(self.gch_cum, "cum"), 0, 0)
        fr, cv = _card("Итоги за год")
        kv = QGridLayout()
        kv.setHorizontalSpacing(14)
        kv.setVerticalSpacing(3)
        kv.setColumnStretch(1, 1)
        self.g_ev, self.g_el = {}, {}
        for key, title in (("gen", "Выработка (AC)"), ("cons", "Потребление"), ("exp", "В сеть (сальдо)"),
                           ("save", "Экономия на счетах"), ("inc", "Доход от продажи"), ("tax", "Налог"),
                           ("bill", "Счёт: без СЭС → с СЭС"), ("bgreen", "Польза до 2030"),
                           ("bpost", "Польза после 2029"), ("pb", "Окупаемость"), ("pbbad", "Каждый год как худший"),
                           ("self", "Без продажи в сеть"), ("profit", "Чистая выгода")):
            lb = _lab(title, "fieldLab")
            val = _lab("—")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            f = val.font()
            f.setBold(True)
            val.setFont(f)
            r = kv.rowCount()
            kv.addWidget(lb, r, 0)
            kv.addWidget(val, r, 1)
            self.g_el[key], self.g_ev[key] = lb, val
        cv.addLayout(kv)
        cv.addStretch(1)
        grid.addWidget(fr, 0, 1)
        self.gch_month = Chart("bar", "кВт·ч", "По месяцам")
        grid.addWidget(chart_card(self.gch_month, "month"), 1, 0)
        fr, cv = _card("Проверки")
        self.g_checks = self._rich()
        cv.addWidget(self.g_checks)
        cv.addStretch(1)
        grid.addWidget(fr, 1, 1)
        # смета: таблица по высоте строк + итог и рынок справа
        fr, cv = _card("Смета")
        self.g_cards["budget"] = fr
        row = QHBoxLayout()
        row.setSpacing(14)
        self.gtb_budget = make_table(["✓", "Статья", "Кому", "Мин, грн", "Макс, грн"],
                                     [("🏠 Станция уже есть — оставить только оформление", lambda _r: self._g_only_docs()),
                                      ("✓ Включить все статьи", lambda _r: self._g_set("excluded", [], True))])
        hh = self.gtb_budget.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setStretchLastSection(False)
        self.gtb_budget.itemChanged.connect(self._g_budget_item)
        row.addWidget(self.gtb_budget, 1)
        sidew = QWidget()
        sidew.setFixedWidth(300)
        side = QVBoxLayout(sidew)
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(6)
        self.g_total = _lab("—", "kpiVal", True)
        self.g_total_sub = self._rich()
        self.g_market = self._rich()
        side.addWidget(self.g_total)
        side.addWidget(self.g_total_sub)
        side.addWidget(self.g_market)
        side.addStretch(1)
        row.addWidget(sidew)
        cv.addLayout(row)
        cv.addWidget(_lab("Снимите галочку, если статья уже куплена или входит в «под ключ». Станция уже стоит? Правый "
                          "клик → «Станция уже есть». Свои цены и цены рынка — слева.", "hint", True))
        grid.addWidget(fr, 2, 0, 1, 2)
        # солнце за 5 лет
        fr, cv = _card("Солнце за 5 лет")
        self.g_cards["sun"] = fr
        row = QHBoxLayout()
        self.g_sun_hint = self._rich()
        row.addWidget(self.g_sun_hint, 1)
        row.addWidget(_btn("📍 Загрузить погоду региона", "primary", "Погода за 5 лет для точки станции (Open-Meteo / "
                                                                     "PVGIS-SARAH3 — выбор на странице 🌐 Данные солнца)",
                           lambda: self.load_region()))
        cv.addLayout(row)
        kp = QGridLayout()
        kp.setSpacing(8)
        self.gks = {}
        for i, (k, cap) in enumerate((("sunday", "Дней с солнцем (≥ 1 ч)"), ("clear", "Ясных · пасмурных дней"),
                                      ("hours", "Часов солнца в год"), ("yield", "Выработка на 1 кВт·п"))):
            box = QFrame()
            box.setObjectName("kpi")
            fv = QVBoxLayout(box)
            fv.setContentsMargins(10, 5, 10, 5)
            fv.setSpacing(0)
            fv.addWidget(_lab(cap, "kpiCap"))
            val = _lab("—", "kpiVal")
            sub = _lab("", "kpiCap", True)
            fv.addWidget(val)
            fv.addWidget(sub)
            self.gks[k] = (val, sub)
            kp.addWidget(box, 0, i)
        cv.addLayout(kp)
        self.g_sun_note = self._rich()
        cv.addWidget(self.g_sun_note)
        charts = QHBoxLayout()
        charts.setSpacing(12)
        self.gch_days = Chart("bar", "дней", "Дней в месяце, среднее за 5 лет")
        self.gch_years = Chart("bar", "кВт·ч", "Выработка станции по годам погоды")
        for ch in (self.gch_days, self.gch_years):
            self.charts.append(ch)
            charts.addWidget(ch, 1)
        cv.addLayout(charts)
        self.gtb_sun = make_table(["Месяц", "Ясных", "Переменных", "Пасмурных", "Часов солнца", "кВт·ч/м² (гориз.)",
                                   "На 1 кВт·п, кВт·ч", "Мин – макс"])
        self.gtb_sun.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cv.addWidget(self.gtb_sun)
        cv.addWidget(_lab("Ясный день — пришло ≥ 70 % от ясного неба, пасмурный — < 35 %. Час солнца — прямое > 120 Вт/м² "
                          "(как у метеостанций). Выработка на 1 кВт·п — из расчёта станции, по годам — по солнцу "
                          "каждого года.", "hint", True))
        grid.addWidget(fr, 3, 0, 1, 2)
        # расчёт по месяцам
        fr, cv = _card("Расчёт по месяцам")
        self.g_cards["months"] = fr
        self.gtb_month = make_table(["Месяц", "Выработка, кВт·ч", "Потребление", "В сеть (оплата)", "Из сети",
                                     "Экономия, грн", "Доход, грн"])
        self.gtb_month.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        cv.addWidget(self.gtb_month)
        cv.addWidget(_lab("Помесячный взаимозачёт по часовой выработке станции (панели, MPPT, провода, КПД и мощность "
                          "инвертора). Своё потребление экономит по цене зоны, излишек месяца оплачивается по зелёному "
                          "тарифу минус налог (до 2029 г.), дальше — по цене продажи после 2029. АКБ не сдвигает "
                          "энергию на ночь (в расчёте не учтено).", "hint", True))
        grid.addWidget(fr, 4, 0, 1, 2)
        grid.setRowStretch(5, 1)
        self.g_right_sa = self._scroll(inner)
        self.g_right_sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        return self.g_right_sa

    @staticmethod
    def _g_fit(t):
        """Таблица по высоте строк — без своей прокрутки и пустого места."""
        t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hh = t.horizontalHeader()
        h = max(hh.height(), hh.sizeHint().height())
        h += sum(t.rowHeight(r) for r in range(t.rowCount())) + 2 * t.frameWidth() + 2
        t.setFixedHeight(h)

    def _g_goto(self, key):
        fr = self.g_cards.get(key)
        if fr is not None:
            self.g_right_sa.verticalScrollBar().setValue(fr.y())

    def _g_open_all(self, on):
        for sec in self.g_secs.values():
            sec.head.setChecked(on)

    # поля → self.s["green"]
    def _g_seg(self, key, items):
        w = Segmented(items)
        w.changed.connect(lambda k, key=key: self._g_set(key, k))
        self.gw[key] = w
        return w

    def _g_step(self, key, lo, hi, step, dec, suf):
        w = Stepper(lo, hi, step, dec, suf)
        w.changed.connect(lambda x, key=key, dec=dec: self._g_set(key, int(round(x)) if dec == 0 and key in
                                                                  ("start_year", "years") else float(x)))
        self.gw[key] = w
        return w

    def _g_combo(self, key, items):
        w = NoWheelCombo()
        for data, text in items:
            w.addItem(text, data)
        w.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        w.setMinimumContentsLength(10)
        w.view().setMinimumWidth(w.view().sizeHintForColumn(0) + 36)
        w.currentIndexChanged.connect(lambda _i, key=key, w=w: self._g_set(key, w.currentData()))
        self.gw[key] = w
        return w

    def _g_toggle(self, key):
        w = Toggle()
        self.toggles.append(w)
        w.toggled.connect(lambda on, key=key: self._g_set(key, bool(on)))
        self.gw[key] = w
        return w

    def _g_copy(self):
        return json.loads(json.dumps(self.s.get("green") or G.green_clean(None)))

    def _g_set(self, key, val, now=False):
        if self._g_loading:
            return
        g = self._g_copy()                                  # новый словарь — общий по умолчанию не трогаем
        g[key] = val
        self.s["green"] = g
        if now:
            self._green_update()
        else:
            self._g_timer.start()

    # ─────────────── значения ───────────────
    def _g_load(self):
        """Настройки зелёного тарифа → поля (без каскада сигналов)."""
        g = self.s.get("green") or G.green_clean(None)
        self._g_loading = True
        try:
            for k, w in self.gw.items():
                v = g.get(k)
                if isinstance(w, Segmented):
                    w.setValue(v)
                elif isinstance(w, Stepper):
                    w.setValue(v)
                elif isinstance(w, NoWheelCombo):
                    i = w.findData(v)
                    w.setCurrentIndex(max(0, i))
                elif isinstance(w, Toggle):
                    w.setChecked(bool(v))
                elif isinstance(w, QLineEdit):
                    w.setText(str(v or ""))
            for key, (st, _rb, _h) in self.g_own.items():
                st.setValue(g["own"].get(key, 0.0))
            for key, pair in self.g_price_w.items():
                for i in (0, 1):
                    pair[i].blockSignals(True)
                    pair[i].setValue(float(g["prices"][key][i]))
                    pair[i].blockSignals(False)
            self.g_check.blockSignals(True)
            for i in range(self.g_check.count()):
                it = self.g_check.item(i)
                key = it.data(Qt.UserRole)
                if key:
                    it.setCheckState(Qt.Checked if g["checklist"].get(key) else Qt.Unchecked)
            self.g_check.blockSignals(False)
            self.g_notes.blockSignals(True)
            if self.g_notes.toPlainText() != g.get("notes", ""):
                self.g_notes.setPlainText(g.get("notes", ""))
            self.g_notes.blockSignals(False)
        finally:
            self._g_loading = False

    def _g_tariff(self, x):
        """Цена для населения — общая со станцией (⚙ Сеть и тариф): поле там тоже обновляется."""
        self._set_widget("tariff", float(x))
        self._on_field("tariff", float(x))
        self._g_timer.start()

    def _g_own_set(self, key, val, reload=False):
        g = self._g_copy()
        g["own"][key] = max(0.0, float(val))
        self.s["green"] = g
        if reload:
            self._g_loading = True
            self.g_own[key][0].setValue(0.0)
            self._g_loading = False
        self._g_timer.start()

    def _g_price_set(self, key, idx, val):
        if self._g_loading:
            return
        g = self._g_copy()
        g["prices"][key][idx] = float(val)
        self.s["green"] = g
        self._g_timer.start()

    def _g_price_reset_row(self, row):
        if 0 <= row < len(G.PRICE_DEFS):
            key, _l, _u, mn, mx, _d = G.PRICE_DEFS[row]
            g = self._g_copy()
            g["prices"][key] = [float(mn), float(mx)]
            self.s["green"] = g
            self._g_load()
            self._green_update()

    def _g_prices_reset(self):
        g = self._g_copy()
        g["prices"] = {k: [float(mn), float(mx)] for k, _l, _u, mn, mx, _d in G.PRICE_DEFS}
        self.s["green"] = g
        self._g_load()
        self._green_update()
        log.info("↺ Цены сметы — ориентиры рынка 2026")

    def _g_own_reset(self):
        g = self._g_copy()
        g["own"] = {k: 0.0 for k, _t in G.OWN_KEYS}
        self.s["green"] = g
        self._g_load()
        self._green_update()

    def _g_only_docs(self):
        self._g_set("excluded", list(G.GEAR_ROWS), True)
        log.info("🏠 Смета: станция уже есть — оставлено только оформление (счётчик, ОСР, документы, резерв)")

    def _g_budget_item(self, it):
        if self._g_loading or it.column() != 0:
            return
        key = it.data(Qt.UserRole)
        if not key:
            return
        ex = set((self.s.get("green") or {}).get("excluded", []))
        if it.checkState() == Qt.Checked:
            ex.discard(key)
        else:
            ex.add(key)
        self._g_set("excluded", sorted(ex))

    def _g_check_changed(self, it):
        if self._g_loading:
            return
        key = it.data(Qt.UserRole)
        if not key:
            return
        g = self._g_copy()
        g["checklist"][key] = it.checkState() == Qt.Checked
        self.s["green"] = g
        self._g_progress()

    def _g_progress(self):
        g = self.s.get("green") or {}
        done = sum(1 for k in G.STEP_KEYS if g.get("checklist", {}).get(k))
        self.g_progress.setText(f"Выполнено {done} из {len(G.STEP_KEYS)} · отмечайте шаги по мере оформления")

    def _g_notes_changed(self):
        if self._g_loading:
            return
        g = self._g_copy()
        g["notes"] = self.g_notes.toPlainText()[:4000]
        self.s["green"] = g

    def _g_check_menu(self, pos):
        m = QMenu(self)
        m.addAction("☑ Отметить всё", lambda: self._g_check_all(True))
        m.addAction("☐ Снять все отметки", lambda: self._g_check_all(False))
        m.addSeparator()
        m.addAction("📋 Копировать список", self._g_copy_checklist)
        m.exec(self.g_check.viewport().mapToGlobal(pos))

    def _g_check_all(self, on):
        g = self._g_copy()
        g["checklist"] = {k: bool(on) for k in G.STEP_KEYS}
        self.s["green"] = g
        self._g_load()
        self._g_progress()

    def _g_copy_checklist(self):
        g = self.s.get("green") or {}
        lines = []
        for sec, items in G.STEPS:
            lines.append(sec.upper())
            lines += [f"[{'x' if g.get('checklist', {}).get(t) else ' '}] {t}" for t in items]
            lines.append("")
        QGuiApplication.clipboard().setText("\n".join(lines).strip())
        log.info("📋 Список шагов скопирован")

    # ─────────────── расчёт и заполнение ───────────────
    def _green_update(self):
        R = getattr(self, "R", None)
        if R is None or not hasattr(self, "g_secs"):
            return
        s = self.s
        g = s.get("green") or G.green_clean(None)
        c = R["ctx"]
        reg, osr, auto = G.place_of(g, s)
        st = G.station_info(c, s)
        key = s.get("inv_preset", "custom")
        d_inv = INVERTER_DB.get(key)
        name, note = (d_inv[1], d_inv[3]) if d_inv else ("свой инвертор", "")
        inv_name = (name if d_inv and d_inv[0] == "Типовые" else f"{d_inv[0]} {name}") if d_inv else "Свой инвертор"
        exp_auto = G.inv_export(key, name, note)
        exp = exp_auto if g["export"] == "auto" else ((True, "указано вручную") if g["export"] == "yes"
                                                      else (False, "указано вручную"))
        ph3 = G.inv_three_phase(key, note)
        lat, lon = float(s["lat"]), float(s["lon"])
        has_reg = self.sd.use_reg(lat, lon)
        weather = "reg" if (g["weather"] == "reg" and has_reg) else "avg"
        b = G.calc_budget(g, st, osr, ph3)
        gen = G.gen_bins(R, weather)
        house, idle = G.cons_bins(c)
        cons = [[house[m][h] + idle[m][h] for h in range(24)] for m in range(12)]
        rg = self.cfg.get("region") if has_reg else None
        factors = G.year_factors(rg, has_reg)
        e = G.calc_econ(g, float(s["tariff"]), b, gen, factors, cons)
        e_self = G.calc_econ(dict(g, green=0.0, post_price=0.0), float(s["tariff"]), b, gen, factors, cons)
        checks = G.green_checks(g, s, st, b, exp, ph3, has_reg)
        sun = G.sun_summary(rg, gen, factors, st["kwp"])
        gen_src = (f"погода региона {rg.get('years', '')}" if weather == "reg" and rg else "средний год расчёта станции")
        self._G = dict(g=g, s=dict(s), st=st, b=b, e=e, e_self=e_self, checks=checks, sun=sun, region=reg, osr=osr, auto=auto,
                       inv_name=inv_name, exp=exp, exp_auto=exp_auto, ph3=ph3, gen_src=gen_src, ver=app_version(),
                       reg_years=(rg or {}).get("years", ""), house=house, idle=idle,
                       reg_src={"om": "Open-Meteo (ERA5)", "pvgis": "PVGIS-SARAH3"}.get((rg or {}).get("src"), ""))
        p = self._p()
        light = int(p["bg"][1:3], 16) > 128                 # текст на белом — цвета темнее (контраст)
        self._gc = (dict(ok="#15803d", warn="#b45309", err="#dc2626", info="#2563eb", gen="#b45309") if light else
                    dict(ok=_OK, warn=_WARN, err=_ERR, info="#4f8cff", gen=GEN_COL))
        self._g_fill_kpis(p)
        self._g_fill_conn(p)
        self._g_fill_econ(p)
        self._g_fill_budget(p)
        self._g_fill_sun(p)
        self._g_progress()
        self._g_fill_sums()
        QTimer.singleShot(0, self._g_fit_list)

    def _g_fill_sums(self):
        """Краткий итог на заголовке свёрнутой группы."""
        D = self._G
        g, sec = D["g"], self.g_secs
        conn = {"ok": "мощности хватает", "increase": "увеличить мощность", "new": "нет подключения"}[g["conn"]]
        sec["place"].sum.setText(f"{D['region']} · {conn}")
        meter = {"1": "1 зона", "2": "день/ночь", "3": "3 зоны"}[g["meter_zones"]]
        sec["tariff"].sum.setText(f"{meter} · {G.fnum(g['green'], 3)} грн")
        ok = D["exp"][0]
        sec["mount"].sum.setText(("крыша" if g["mount"] == "roof" else "земля") + " · в сеть: "
                                 + ("да" if ok else "нет" if ok is False else "?"))
        n = sum(1 for v in g["own"].values() if v > 0) + (1 if g["extra_mat"] > 0 else 0)
        sec["own"].sum.setText(f"своих: {n}" if n else "оценка")
        n = sum(1 for k, _l, _u, mn, mx, _d in G.PRICE_DEFS if g["prices"][k] != [float(mn), float(mx)])
        sec["prices"].sum.setText(f"изменено: {n}" if n else "ориентиры 2026")
        done = sum(1 for k in G.STEP_KEYS if g["checklist"].get(k))
        sec["docs"].sum.setText(f"{done} из {len(G.STEP_KEYS)}")

    def _g_fill_kpis(self, p):
        D = self._G
        st, b, e, g = D["st"], D["b"], D["e"], D["g"]
        val, sub = self.gk["station"]
        val.setText(f"{G.fkw(round(st['kwp'], 2))} кВт·п")
        val.setStyleSheet(f"color: {self._gc['gen']};")
        sub.setText(f"{st['npan']} панелей · инвертор {G.fkw(st['inv_kw'])} кВт · АКБ {G.fkw(round(st['bat_kwh'], 1))} кВт·ч")
        val, sub = self.gk["budget"]
        val.setText(G.frange(b["mn"], b["mx"]))
        sub.setText(f"в среднем {G.fk(b['mid'])} тыс. грн" + (" · часть статей снята" if g["excluded"] else ""))
        parts = []
        if g["meter_paid"] and "meter" not in g["excluded"]:
            parts.append("счётчик")
        if g["conn"] != "ok" and "grid" not in g["excluded"]:
            parts.append("увеличение мощности" if g["conn"] == "increase" else "присоединение")
        val, sub = self.gk["osr"]
        val.setText(G.frange(b["osr_mn"], b["osr_mx"]))
        if g["conn"] != "ok" and not g["grid_auto"] and g["grid_cost"] <= 0:
            sub.setText("впишите плату за присоединение (вкладка «Подключение»)")
            sub.setStyleSheet(f"color: {self._gc['warn']};")
        else:
            sub.setText((" + ".join(parts) + " · только по счёту ОСР") if parts else "ничего, если счётчик ставит ОСР")
            sub.setStyleSheet("")
        val, sub = self.gk["pay"]
        pb = e["pb_mid"]
        val.setText(f"≈ {self._g_years(pb)}" if pb is not None else f"> {e['years']} лет")
        no_exp = D["exp"][0] is False
        val.setStyleSheet(f"color: {self._gc['err'] if pb is None else self._gc['warn'] if no_exp else self._gc['ok']};")
        if no_exp:
            ps = D["e_self"]["pb_mid"]
            txt = ("⚠ ваш инвертор не отдаёт в сеть — это расчёт с продажей; без продажи "
                   + (f"≈ {G.fnum(ps, 1)} г." if ps is not None else f"> {e['years']} лет"))
        elif e["green_years"] > 0:
            txt = f"{G.fk(e['b_green'])} тыс. грн/год до 2030, потом {G.fk(e['b_post'])}"
        else:
            txt = f"без зелёного тарифа: {G.fk(e['b_post'])} тыс. грн/год"
        sub.setText(txt)
        sub.setStyleSheet(f"color: {self._gc['warn']};" if no_exp else "")

    @staticmethod
    def _g_years(x):
        """14,3 года · 12 лет · 1 год."""
        t = G.fnum(x, 1)
        return f"{t} года" if "," in t else f"{t} {G.plural(int(round(x)), 'год', 'года', 'лет')}"

    def _g_fill_conn(self, p):
        D = self._G
        g, st, b = D["g"], D["st"], D["b"]
        mut = p["muted"]
        reg_cb, osr_cb = self.gw["region"], self.gw["osr"]
        reg_cb.setItemText(0, f"Авто — по координатам станции ({D['region']})" if D["auto"] else
                              "Авто — по координатам станции")
        osr_cb.setItemText(0, f"По области ({G.REGION_MAP[D['region']][4]})")
        self.gw["grid_cost"].setEnabled(g["conn"] != "ok" and not g["grid_auto"])
        self.gw["grid_auto"].setEnabled(g["conn"] != "ok")
        self.gw["field_dist"].setEnabled(g["mount"] == "ground")
        ce = b["conn"]
        if g["conn"] == "ok":
            txt = f"<span style='color:{mut}'>Плата за присоединение не нужна.</span>"
        elif g["grid_auto"]:
            txt = (f"<span style='color:{mut}'>Оценка ОСР ({G.htmlmod.escape(D['osr'])}):</span> "
                   f"<b>{G.htmlmod.escape(ce['text'])}</b><br><span style='color:{mut}'>Точная сумма — в счёте ОСР / "
                   f"калькуляторе НКРЭКУ.</span>")
        else:
            txt = f"<span style='color:{mut}'>Для сравнения, по ставкам 2026: {G.htmlmod.escape(ce['text'])}</span>"
        self.g_grid.setText(txt)
        ok, why = D["exp"]
        col = self._gc['ok'] if ok else self._gc['err'] if ok is False else self._gc['warn']
        word = "да" if ok else "нет" if ok is False else "не знаю"
        auto_why = D["exp_auto"][1]
        self.g_station.setText(
            f"<b>{st['npan']}</b> панелей = <b>{G.fkw(round(st['kwp'], 2))} кВт·п</b> · инвертор <b>"
            f"{G.htmlmod.escape(D['inv_name'])}</b> {G.fkw(st['inv_kw'])} кВт ({'3 фазы' if D['ph3'] else '1 фаза'})"
            + (f" · отдельных MPPT {st['n_ctl']}" if st["n_ctl"] else "")
            + f" · АКБ {G.fkw(round(st['bat_kwh'], 1))} кВт·ч<br>"
            f"Отдаёт в сеть: <span style='color:{col}'><b>{word}</b></span> — {G.htmlmod.escape(why)}"
            + (f"<br><span style='color:{mut}'>По модели: {G.htmlmod.escape(auto_why)}</span>"
               if g["export"] != "auto" else ""))
        self.g_checks.setText("".join(
            f"<p style='margin:4px 0'><span style='color:{self._gc[lv]}'>●</span>&nbsp;&nbsp;{G.htmlmod.escape(t)}</p>"
            for lv, t in D["checks"]))

    def _g_fill_econ(self, p):
        D = self._G
        g, e, b = D["g"], D["e"], D["b"]
        self.g_tariff.setValue(float(self.s["tariff"]))
        self.g_zones.setText(" · ".join(f"{n}: {G.fnum(v, 2)}" for n, v in zip(e["zones"], e["zprices"])) + " грн/кВт·ч")
        self.gw["net_mode"].setEnabled(g["meter_zones"] != "1")
        ev, el = self.g_ev, self.g_el
        idle = sum(sum(r) for r in D["idle"])
        zones = " · ".join(f"{n.split()[0]}: выработка {G.fnum(gz)}, потребление {G.fnum(cz)} кВт·ч"
                           for n, gz, cz in zip(e["zones"], e["zgen"], e["zcons"]))
        price_now = g["green"] if e["start"] <= G.GREEN_LAST_YEAR else g["post_price"]
        yrs = e["years"]
        es = D["e_self"]
        no_exp = D["exp"][0] is False
        pb = (f"не окупается за {yrs} лет" if e["pb_min"] is None
              else f"{G.fpb(e['pb_min'], yrs)} – {G.fpb(e['pb_max'], yrs)} лет")
        rows_kv = {
            "gen": (f"{G.fnum(e['gen'])} кВт·ч", f"Выработка AC за год — {D['gen_src']}.\n{zones}"),
            "cons": (f"{G.fnum(e['cons'])} кВт·ч", f"Дом + холостой ход инвертора ({G.fnum(idle)} кВт·ч)"),
            "exp": (f"{G.fnum(e['exp'])} кВт·ч", "Сальдо месяцев в пользу станции — оплачивается"),
            "save": (f"{G.fnum(e['save'])} грн", "Своя энергия вместо покупки по цене зоны"),
            "inc": (f"{G.fnum(e['inc'])} грн", f"До налога {G.fnum(e['gross'])} грн, по {G.fnum(price_now, 3)} грн/кВт·ч"),
            "tax": (f"{G.fnum(e['tax'])} грн", "18 % НДФЛ + 5 % военный сбор — удерживает поставщик"),
            "bill": (f"{G.fnum(e['bill_without'])} → {G.fnum(e['bill_with'])} грн", "Счёт за свет за год"),
            "bgreen": (f"{G.fnum(e['b_green'])} × {e['green_years']} г." if e["green_years"] > 0 else "не действует",
                       "Экономия + доход после налога в год, пока платят зелёный тариф (до 2029 г. включительно)"),
            "bpost": (f"{G.fnum(e['b_post'])} грн", f"Продажа по {G.fnum(g['post_price'], 2)} грн/кВт·ч"),
            "pb": (pb, "При мин / макс бюджете; при среднем — "
                       + (f"{G.fnum(e['pb_mid'], 1)} г." if e["pb_mid"] is not None else f"> {yrs} лет")),
            "pbbad": (f"{G.fnum(e['pb_bad'], 1)} г." if e["pb_bad"] is not None else f"> {yrs} лет",
                      "Если каждый год погода как в худший из 5 лет (нужна погода региона)"),
            "self": (f"{G.fnum(es['benefit'])} грн · " + (f"≈ {G.fnum(es['pb_mid'], 1)} г." if es["pb_mid"] is not None
                                                         else f"> {yrs} лет"),
                     "Польза в год и окупаемость, если в сеть не продавать (только своё потребление)"
                     + (" — так сейчас: инвертор не отдаёт в сеть" if no_exp else "")),
            "profit": (f"{G.fnum(e['profit'])} грн", "За горизонт расчёта, минус средний бюджет"),
        }
        for k, (txt, tip) in rows_kv.items():
            ev[k].setText(txt)
            ev[k].setToolTip(tip)
            el[k].setToolTip(tip)
        el["tax"].setText(f"Налог {G.fkw(g['tax'])} %")
        el["profit"].setText(f"Чистая выгода, {yrs} лет")
        ev["bgreen"].setStyleSheet(f"color: {self._gc['ok']};")
        ev["pb"].setStyleSheet(f"color: {p['accent']};")
        ev["profit"].setStyleSheet(f"color: {self._gc['ok'] if e['profit'] >= 0 else self._gc['err']};")
        ev["self"].setStyleSheet(f"color: {self._gc['warn']};" if no_exp else "")
        rows = e["rows"]
        t = self.gtb_month
        t.setRowCount(13)
        keys = ("gen", "cons", "exp", "buy", "save", "inc")
        for i, r in enumerate(rows):
            t.setItem(i, 0, _item(r["month"]))
            for col, k in enumerate(keys, start=1):
                t.setItem(i, col, _item(G.fnum(r[k]), True))
        t.setItem(12, 0, _item("За год", bold=True))
        for col, k in enumerate(keys, start=1):
            t.setItem(12, col, _item(G.fnum(sum(r[k] for r in rows)), True, bold=True))
        self._g_fit(t)
        self.gch_month.set_data([("Выработка", GEN_COL, [r["gen"] for r in rows]),
                                 ("Потребление", CONS_COL, [r["cons"] for r in rows]),
                                 ("В сеть (сальдо)", EXP_COL, [r["exp"] for r in rows])], labels=G.MONTHS_S)
        n = len(e["cum"])
        xs = list(range(n + 1))
        series = [("Выгода", _OK, [0.0] + e["cum"])]
        if e["pb_bad"] != e["pb_mid"] and any(abs(a - c) > 1 for a, c in zip(e["cum"], e["cum_bad"])):
            series.append(("Каждый год как худший", _WARN, [0.0] + e["cum_bad"]))
        marks = []
        if 0 < e["green_years"] < n:
            marks.append((e["green_years"], "← зелёный тариф до 2030", "#4f8cff"))
        if e["pb_mid"] is not None and e["pb_mid"] <= n:
            marks.append((e["pb_mid"], f"окупаемость ≈ {G.fnum(e['pb_mid'], 1)} г.", GEN_COL))
        self.gch_cum.hlines = [(b["mid"], f"Вложения ≈ {G.fk(b['mid'])} тыс. грн", _ERR)]
        self.gch_cum.set_data(series, xs=xs, xmin=0, xmax=n, markers=marks)

    def _g_fill_budget(self, p):
        D = self._G
        b, g = D["b"], D["g"]
        t = self.gtb_budget
        self._g_loading = True
        t.blockSignals(True)
        rows = b["rows"]
        t.setRowCount(len(rows) + 1)
        for i, r in enumerate(rows):
            ck = QTableWidgetItem()
            ck.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            ck.setCheckState(Qt.Checked if r["on"] else Qt.Unchecked)
            ck.setData(Qt.UserRole, r["key"])
            t.setItem(i, 0, ck)
            osr = r["payee"].startswith("ОСР")
            col = None if r["on"] else p["muted"]
            t.setItem(i, 1, _item(r["name"], color=col))
            t.setItem(i, 2, _item(r["payee"], color=col or (self._gc['gen'] if osr else None), bold=osr))
            t.setItem(i, 3, _item(G.fnum(r["mn"]), True, col))
            t.setItem(i, 4, _item(G.fnum(r["mx"]), True, col))
        n = len(rows)
        t.setItem(n, 0, _item(""))
        t.setItem(n, 1, _item("ИТОГО", bold=True))
        t.setItem(n, 2, _item(""))
        t.setItem(n, 3, _item(G.fnum(b["mn"]), True, bold=True))
        t.setItem(n, 4, _item(G.fnum(b["mx"]), True, bold=True))
        self._g_fit(t)
        t.blockSignals(False)
        self._g_loading = False
        self.g_total.setText(f"{G.fnum(b['mn'])} – {G.fnum(b['mx'])} грн")
        self.g_total.setStyleSheet(f"color: {self._gc['gen']};")
        self.g_total_sub.setText(
            f"<p style='margin:2px 0'>В среднем: <b>{G.fnum(b['mid'])} грн</b></p>"
            f"<p style='margin:2px 0'>Из них в ОСР (РЭС): <b>{G.frange(b['osr_mn'], b['osr_mx'])}</b> — "
            f"только по официальному счёту</p>"
            f"<p style='margin:6px 0 0 0;color:{p['muted']}'>Цены отдельных комплектующих и «под ключ» не "
            f"складываются: в пакете часть работ уже включена.</p>")
        est = b["est"]
        for key, (_st, rb, hint) in self.g_own.items():
            mn, mx = est[key]
            own = g["own"].get(key, 0.0) > 0
            hint.setText(("✎ ваша цена · " if own else "") + f"моя оценка {G.fnum(mn)}–{G.fnum(mx)} грн"
                         + (f" (≈ {G.fnum((mn + mx) / 2 / max(1, D['st']['npan']))} грн/шт)" if key == "panels" else ""))
            rb.setEnabled(own)
        kwp = b["kwp"]
        typ = "hybrid" if D["st"]["bat_kwh"] > 0 else "grid"
        cands = [m for m in G.MARKET if m[2] == typ] or G.MARKET
        near = min(cands, key=lambda m: abs(m[1] - kwp))
        lines = []
        for nm, _sz, _t, mn, mx in G.MARKET:
            row = f"{nm}: {G.fk(mn)}–{G.fk(mx)} тыс. грн"
            lines.append(f"<p style='margin:3px 0'>{'<b>▶ ' + row + '</b>' if nm == near[0] else row}</p>")
        diff = b["mid"] - (near[3] + near[4]) / 2.0 * (kwp / near[1] if near[1] else 1)
        lines.append(f"<p style='margin:8px 0 0 0;color:{p['muted']}'>Ваш расчёт (в пересчёте на {G.fkw(round(kwp, 2))} "
                     f"кВт·п) {'дороже' if diff > 0 else 'дешевле'} рыночного ориентира на ≈ {G.fk(abs(diff))} тыс. грн. "
                     f"Ориентиры — для крышных СЭС; поле обычно дороже на сваи и кабель.</p>")
        self.g_market.setText("".join(lines))

    def _g_fill_sun(self, p):
        D = self._G
        sun, e, st = D["sun"], D["e"], D["st"]
        rg = self.cfg.get("region")
        mut = p["muted"]
        if sun is None:
            why = ("погода региона загружена для другой точки — загрузите заново" if rg else
                   "погода региона за 5 лет не загружена")
            if rg and not rg.get("stats") and self.sd.use_reg(float(self.s["lat"]), float(self.s["lon"])):
                why = "в загруженной погоде региона нет статистики дней (старая версия) — загрузите заново"
            self.g_sun_hint.setText(f"<span style='color:{self._gc['warn']}'>⚠ {why}.</span> <span style='color:{mut}'>Нажмите "
                                    f"«📍 Загрузить погоду региона» — покажу, сколько реально ясных и пасмурных дней "
                                    f"в вашей точке, и разброс выработки по годам.</span>")
            for k in ("sunday", "clear", "hours"):
                self.gks[k][0].setText("—")
                self.gks[k][1].setText("загрузите погоду региона")
            yk = e["gen"] / st["kwp"] if st["kwp"] else 0.0
            self.gks["yield"][0].setText(f"≈ {G.fnum(yk)} кВт·ч")
            self.gks["yield"][1].setText("средний год расчёта станции")
            self.gch_days.set_data([], labels=[])
            self.gtb_sun.setRowCount(0)
        else:
            self.g_sun_hint.setText(f"<span style='color:{self._gc['ok']}'>✔</span> {G.htmlmod.escape(D['reg_src'])}, "
                                    f"<b>{G.htmlmod.escape(D['reg_years'])}</b> — точка ({rg['lat']}, {rg['lon']})")
            a, mo = sun["annual"], sun["month"]
            nd = round(365 - a["sunday"])
            self.gks["sunday"][0].setText(f"{G.fnum(a['sunday'])} из 365")
            self.gks["sunday"][1].setText(f"{G.fnum(nd)} {G.plural(nd, 'день', 'дня', 'дней')} солнца почти нет")
            self.gks["clear"][0].setText(f"{G.fnum(a['sunny'])} · {G.fnum(a['cloudy'])}")
            self.gks["clear"][1].setText(f"переменная облачность — {G.fnum(a['partly'])}")
            self.gks["hours"][0].setText(f"{G.fnum(a['sun_h'])} ч")
            self.gks["hours"][1].setText(f"из ≈ 4 400 светлых часов · {G.fnum(a['ghi'])} кВт·ч/м² на землю")
            self.gks["yield"][0].setText(f"{G.fnum(a['y_avg'])} кВт·ч")
            self.gks["yield"][1].setText(f"по годам {G.fnum(a['y_min'])}–{G.fnum(a['y_max'])}")
            self.gch_days.set_data([("Ясно", SUN_COLS[0], mo["sunny"]), ("Переменно", SUN_COLS[1], mo["partly"]),
                                    ("Пасмурно", SUN_COLS[2], mo["cloudy"])], labels=G.MONTHS_S, ydec=1)
            t = self.gtb_sun
            t.setRowCount(13)
            for m in range(12):
                t.setItem(m, 0, _item(G.MONTHS_S[m]))
                for col, (k, dd) in enumerate((("sunny", 0), ("partly", 0), ("cloudy", 0), ("sun_h", 0), ("ghi", 1),
                                               ("y_avg", 0)), start=1):
                    t.setItem(m, col, _item(G.fnum(mo[k][m], dd), True))
                t.setItem(m, 7, _item(f"{G.fnum(mo['y_min'][m])} – {G.fnum(mo['y_max'][m])}", True))
            t.setItem(12, 0, _item("За год", bold=True))
            for col, k in enumerate(("sunny", "partly", "cloudy", "sun_h", "ghi", "y_avg"), start=1):
                t.setItem(12, col, _item(G.fnum(a[k]), True, bold=True))
            t.setItem(12, 7, _item(f"{G.fnum(a['y_min'])} – {G.fnum(a['y_max'])}", True, bold=True))
            self._g_fit(t)
        self.gtb_sun.setVisible(sun is not None)
        self.gch_days.setVisible(sun is not None)
        self.gch_years.set_data([("Выработка", GEN_COL, [v for _l, v in e["year_totals"]])],
                                labels=[str(lab) for lab, _v in e["year_totals"]])
        kwp = st["kwp"]
        dec_day = e["rows"][11]["gen"] / 31.0
        jun_day = e["rows"][5]["gen"] / 30.0
        hours = e["gen"] / kwp if kwp else 0.0
        self.g_sun_note.setText(
            f"<p style='margin:2px 0'>Станция {G.fkw(round(kwp, 2))} кВт·п за год выдаёт <b>{G.fnum(e['gen'])} кВт·ч</b> — "
            f"как <b>{G.fnum(hours)} {G.plural(round(hours), 'час', 'часа', 'часов')}</b> работы на полную мощность из "
            f"8 760 (<b>{G.fnum(hours / 87.6)} %</b> времени).</p>"
            f"<p style='margin:2px 0'>В среднем за день: декабрь ≈ <b>{G.fnum(dec_day)} кВт·ч</b>, июнь ≈ "
            f"<b>{G.fnum(jun_day)} кВт·ч</b>. Ночью — 0, в пасмурный день — в 3–8 раз меньше ясного.</p>"
            f"<p style='margin:2px 0;color:{mut}'>Если считать «солнце 24/7», вышло бы {G.fnum(kwp * 8760)} кВт·ч — "
            f"в {G.fnum(8760 / hours) if hours else '—'} раз больше правды.</p>")

    # ─────────────── действия ───────────────
    def _green_menu(self, gpos):
        m = QMenu(self)
        m.addAction("🔄 Пересчитать", self._green_update)
        m.addAction("📄 Отчёт HTML…", self.green_report)
        m.addAction("📋 Копировать итоги", self._green_copy)
        m.addAction("💾 Смета → CSV…", lambda: export_table_csv(self.gtb_budget))
        m.addSeparator()
        go = m.addMenu("Перейти к")
        go.addAction("⬆ Наверх", lambda: self.g_right_sa.verticalScrollBar().setValue(0))
        for key, title in (("budget", "Смета"), ("sun", "Солнце за 5 лет"), ("months", "Расчёт по месяцам")):
            go.addAction(title, lambda key=key: self._g_goto(key))
        m.addAction("▾ Развернуть все группы", lambda: self._g_open_all(True))
        m.addAction("▸ Свернуть все группы", lambda: self._g_open_all(False))
        m.addSeparator()
        m.addAction("🏠 Станция уже есть — в смете только оформление", self._g_only_docs)
        m.addAction("✓ Включить все статьи сметы", lambda: self._g_set("excluded", [], True))
        m.addAction("↺ Мои цены → оценки", self._g_own_reset)
        m.addAction("↺ Цены рынка по умолчанию", self._g_prices_reset)
        m.addSeparator()
        m.addAction("📍 Загрузить погоду региона за 5 лет", lambda: self.load_region())
        m.addAction("⚙ Настройки станции", lambda: self._go_page(self.page_idx["settings"]))
        m.exec(gpos)

    def _g_price_menu(self, row, gpos):
        m = QMenu(self)
        m.addAction("↺ Сбросить эту строку", lambda: self._g_price_reset_row(row))
        m.addAction("↺ Все цены — ориентиры 2026", self._g_prices_reset)
        m.exec(gpos)

    def _green_copy(self):
        if not self._G:
            return
        D = self._G
        e, b = D["e"], D["b"]
        lines = [f"Зелёный тариф · {D['region']} · {G.fkw(round(b['kwp'], 2))} кВт·п",
                 f"Бюджет: {G.frange(b['mn'], b['mx'])} (в ОСР {G.frange(b['osr_mn'], b['osr_mx'])})",
                 f"Выработка {G.fnum(e['gen'])} кВт·ч/год, потребление {G.fnum(e['cons'])}, в сеть {G.fnum(e['exp'])}",
                 f"Польза в год до 2030: {G.fnum(e['b_green'])} грн, после: {G.fnum(e['b_post'])} грн",
                 "Окупаемость: " + (f"≈ {G.fnum(e['pb_mid'], 1)} года" if e["pb_mid"] is not None
                                    else f"> {e['years']} лет")]
        lines += [f"{'✓' if lv == 'ok' else '⚠' if lv == 'warn' else '✗' if lv == 'err' else 'ℹ'} {t}"
                  for lv, t in D["checks"]]
        lines += ["", table_tsv(self.gtb_budget), "", table_tsv(self.gtb_month)]
        QGuiApplication.clipboard().setText("\n".join(lines))
        log.info("📋 Итоги зелёного тарифа скопированы")

    def green_report(self):
        if self._G is None:
            self._green_update()
        if self._G is None:
            return
        fn = ask_save(self, "Отчёт: зелёный тариф", str(APP_ROOT / "Отчёт_СЭС_зелёный_тариф.html"), "HTML (*.html)")
        if not fn:
            return
        try:
            with open(fn, "w", encoding="utf-8") as f:
                f.write(G.report_html(self._G))
        except OSError as e:
            _save_failed(self, fn, e)
            return
        log.info(f"✓ Отчёт сохранён: {fn}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(fn))
