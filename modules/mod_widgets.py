"""mod_widgets.py  v1.7.0
виджеты Qt: Toggle, Segmented, Stepper, график Chart, таблицы с меню

Журнал:
v1.7.0: PresetPicker: поля не длиннее нужного (производитель ≤200, серия ≤330, модель ≤300/360 px);
        allow_custom=False — без «Своё» (для дополнительных сборок АКБ); extra_menu — свои пункты меню.
v1.6.0: PresetPicker: группа без диапазона мощности (инверторы — по напряжению АКБ).
v1.5.0: PresetPicker — третий уровень «серия» (панели: производитель → серия → мощность), 🔎 поиск по всей
        базе (FindDialog), меню по правому клику (найти, копировать название/паспорт, своё).
v1.3.0: вынесено из solar_calc.pyw v1.2.1; PresetPicker — выбор «производитель → модель» из базы.
"""

import csv
import math

from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QSize, QCoreApplication
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QGuiApplication, QPainterPath
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QToolButton, QButtonGroup, QHBoxLayout,
                               QVBoxLayout, QDoubleSpinBox, QComboBox, QAbstractButton, QTableWidget,
                               QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
                               QFileDialog, QSizePolicy, QDialog, QLineEdit, QListWidget, QListWidgetItem)

from .mod_base import APP_ROOT, log
from .mod_model import fmt_t
from .mod_theme import _QT_THEMES


def app_name():
    return QCoreApplication.applicationName() or "Солнечный калькулятор"


def app_version():
    return QCoreApplication.applicationVersion()


class Toggle(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self._on, self._off, self._knob = QColor("#4f8cff"), QColor("#454b59"), QColor("#ffffff")

    def set_theme(self, on, off, knob):
        self._on, self._off, self._knob = QColor(on), QColor(off), QColor(knob)
        self.update()

    def sizeHint(self):
        return QSize(40, 22)

    def paintEvent(self, e):
        pa = QPainter(self)
        pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(Qt.NoPen)
        pa.setBrush(self._on if self.isChecked() else self._off)
        pa.drawRoundedRect(0, 0, 40, 22, 11, 11)
        pa.setBrush(QColor("#ffffff"))
        pa.drawEllipse(21 if self.isChecked() else 3, 3, 16, 16)


class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.btns = {}
        n = len(items)
        for i, (k, t) in enumerate(items):
            b = QPushButton(t)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("pos", "s" if n == 1 else "l" if i == 0 else "r" if i == n - 1 else "m")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.group.addButton(b)
            self.btns[k] = b
            lay.addWidget(b)
            b.clicked.connect(lambda _=False, k=k: self.changed.emit(k))

    def value(self):
        for k, b in self.btns.items():
            if b.isChecked():
                return k
        return next(iter(self.btns))

    def setValue(self, k):
        b = self.btns.get(str(k))
        if b:
            b.setChecked(True)


class _Spin(QDoubleSpinBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class NoWheelCombo(QComboBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class FindDialog(QDialog):
    """Поиск по всей базе: слова через пробел (порядок любой), Enter / двойной клик — выбрать."""
    LIMIT = 400

    def __init__(self, items, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 460)
        self.items = items                                 # [(ключ, подпись, текст для поиска)]
        self.key = None
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        self.ed = QLineEdit()
        self.ed.setPlaceholderText("🔎 модель, серия, мощность — например: risen 330  или  RSM72  или  tiger 440")
        self.ed.setClearButtonEnabled(True)
        self.lst = QListWidget()
        self.lst.setUniformItemSizes(True)
        self.lst.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lst.customContextMenuRequested.connect(self._menu)
        self.lab = QLabel()
        self.lab.setObjectName("hint")
        bb = QHBoxLayout()
        bb.addWidget(self.lab, 1)
        ok, cancel = QPushButton("Выбрать"), QPushButton("Отмена")
        ok.setObjectName("primary")
        ok.clicked.connect(self._pick)
        cancel.clicked.connect(self.reject)
        bb.addWidget(ok)
        bb.addWidget(cancel)
        v.addWidget(self.ed)
        v.addWidget(self.lst, 1)
        v.addLayout(bb)
        self.ed.textChanged.connect(self._filter)
        self.ed.returnPressed.connect(self._pick)
        self.lst.itemDoubleClicked.connect(lambda _: self._pick())
        self._filter("")

    def _filter(self, text):
        words = text.lower().replace(",", " ").split()
        hits = [it for it in self.items if all(w in it[2] for w in words)] if words else self.items
        self.lst.setUpdatesEnabled(False)
        self.lst.clear()
        for k, label, _ in hits[:self.LIMIT]:
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, k)
            self.lst.addItem(it)
        self.lst.setUpdatesEnabled(True)
        if hits:
            self.lst.setCurrentRow(0)
        n = len(hits)
        self.lab.setText(f"найдено {n}" + (f", показаны первые {self.LIMIT} — уточните запрос" if n > self.LIMIT else "")
                         if words else f"всего {n} — начните вводить")

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Down, Qt.Key_Up, Qt.Key_PageDown, Qt.Key_PageUp) and self.ed.hasFocus():
            self.lst.setFocus()
            self.lst.keyPressEvent(e)
            return
        super().keyPressEvent(e)

    def _pick(self):
        it = self.lst.currentItem()
        if it is not None:
            self.key = it.data(Qt.UserRole)
            self.accept()

    def _menu(self, pos):
        it = self.lst.itemAt(pos)
        m = QMenu(self)
        m.addAction("✓ Выбрать", self._pick).setEnabled(it is not None)
        m.addAction("📋 Копировать строку", lambda: QGuiApplication.clipboard().setText(it.text())).setEnabled(it is not None)
        m.addSeparator()
        m.addAction("🧹 Очистить поиск", self.ed.clear)
        m.exec(self.lst.viewport().mapToGlobal(pos))


class PresetPicker(QWidget):
    """Выбор из базы: производитель → (серия →) модель. Значение — ключ базы, «custom» — своё.
    series={ключ: серия} — третий уровень (панели). 🔎 — поиск по всей базе; правый клик — меню."""
    changed = Signal(str)

    def __init__(self, db, custom_label, parent=None, series=None, what="модель", allow_custom=True):
        super().__init__(parent)
        self.db = db                                   # {ключ: (производитель, модель, параметры, описание)}
        self.series = series
        self.allow_custom = allow_custom
        self.extra_menu = None                         # fn(QMenu) — свои пункты в меню по правому клику
        self.custom_label = custom_label
        self.what = what
        self.tree = {}                                 # производитель → серия → [ключи] (порядок базы)
        for k, (b, *_rest) in db.items():
            self.tree.setdefault(b, {}).setdefault(series[k] if series else "", []).append(k)
        self._find_items = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.setSizeConstraint(QHBoxLayout.SetMinAndMaxSize)   # ширина выбора — не больше суммы полей
        self.cb_brand = NoWheelCombo()
        self.cb_brand.setToolTip("Производитель")
        self.cb_brand.setMaxVisibleItems(24)
        self.cb_series = NoWheelCombo()
        self.cb_series.setToolTip("Серия: «xxx» — место мощности в названии")
        self.cb_series.setMaxVisibleItems(24)
        self.cb_model = NoWheelCombo()
        self.cb_model.setToolTip("Модель")
        self.cb_model.setMaxVisibleItems(24)
        for cb, n in ((self.cb_brand, 10), (self.cb_series, 14), (self.cb_model, 16 if series else 18)):
            cb.setMinimumContentsLength(n)
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setContextMenuPolicy(Qt.CustomContextMenu)
            cb.customContextMenuRequested.connect(lambda pos, cb=cb: self._menu(cb.mapToGlobal(pos)))
        self.cb_series.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cb_model.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cb_brand.setMaximumWidth(200)             # не растягивать на всё окно
        self.cb_series.setMaximumWidth(330)
        self.cb_model.setMaximumWidth(300 if series else 360)
        for cb in (self.cb_brand, self.cb_series, self.cb_model):
            cb.view().setMinimumWidth(320)             # список шире поля — названия видны целиком
        for b, ss in self.tree.items():
            self.cb_brand.addItem(f"{b}  ({sum(len(x) for x in ss.values())})", b)
        if allow_custom:
            self.cb_brand.addItem("Своё", "")
        self.btn_find = QToolButton()
        self.btn_find.setText("🔎")
        self.btn_find.setObjectName("stepBtn")
        self.btn_find.setCursor(Qt.PointingHandCursor)
        self.btn_find.setToolTip(f"Найти {what} по названию или мощности во всей базе ({len(db)} шт)")
        self.btn_find.clicked.connect(self.find)
        lay.addWidget(self.cb_brand)
        if series:
            lay.addWidget(self.cb_series, 3)
        lay.addWidget(self.cb_model, 2 if series else 1)
        lay.addWidget(self.btn_find)
        self.cb_series.setVisible(bool(series))
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self._menu(self.mapToGlobal(pos)))
        self.cb_brand.currentIndexChanged.connect(self._brand_changed)
        self.cb_series.currentIndexChanged.connect(self._series_changed)
        self.cb_model.currentIndexChanged.connect(self._model_changed)
        self._fill_series(self.cb_brand.currentData())

    # ── заполнение ──
    def _fill_series(self, brand, pick=None):
        cs = self.cb_series
        cs.blockSignals(True)
        cs.clear()
        ss = self.tree.get(brand) if brand else None
        if ss:
            for name, keys in ss.items():
                if not self.series:
                    cs.addItem(name or "—", name)
                    continue
                ps = [self.db[k][2].get("pmax") for k in keys if isinstance(self.db[k][2], dict)]
                if ps and None not in ps:                          # панели: диапазон мощности серии
                    lo, hi = min(ps), max(ps)
                    rng = f"  ·  {lo:g} Вт" if lo == hi else f"  ·  {lo:g}–{hi:g} Вт"
                    info = self.db[keys[0]][3]
                else:
                    rng, info = "", ""
                cs.addItem(f"{name}{rng}  ({len(keys)})", name)
                if info:
                    cs.setItemData(cs.count() - 1, info, Qt.ToolTipRole)
        else:
            cs.addItem("—", None)
        cs.setEnabled(bool(ss))
        if pick is not None:
            cs.setCurrentIndex(max(0, cs.findData(pick)))
        cs.blockSignals(False)
        self._fill_models(brand, cs.currentData())

    def _fill_models(self, brand, ser):
        cm = self.cb_model
        cm.blockSignals(True)
        cm.clear()
        if not brand:
            cm.addItem(self.custom_label, "custom")
        else:
            for k in self.tree.get(brand, {}).get(ser, []):
                _, name, _, info = self.db[k]
                cm.addItem(name, k)
                if info:
                    cm.setItemData(cm.count() - 1, info, Qt.ToolTipRole)
        cm.blockSignals(False)

    def _brand_changed(self, i):
        self._fill_series(self.cb_brand.itemData(i))
        self._model_changed(self.cb_model.currentIndex())

    def _series_changed(self, i):
        self._fill_models(self.cb_brand.currentData(), self.cb_series.itemData(i))
        self._model_changed(self.cb_model.currentIndex())

    def _model_changed(self, i):
        k = self.cb_model.itemData(i)
        self.cb_model.setToolTip((self.db[k][3] if k in self.db else "") or "Модель")
        if k:
            self.changed.emit(k)

    # ── значение ──
    def value(self):
        return self.cb_model.currentData() or "custom"

    def setValue(self, key):
        brand = self.db[key][0] if key in self.db else ""
        ser = (self.series.get(key, "") if self.series else "") if key in self.db else None
        self.cb_brand.blockSignals(True)
        self.cb_brand.setCurrentIndex(max(0, self.cb_brand.findData(brand)))
        self.cb_brand.blockSignals(False)
        self._fill_series(brand, pick=ser)
        self.cb_model.blockSignals(True)
        self.cb_model.setCurrentIndex(max(0, self.cb_model.findData(key if key in self.db else "custom")))
        self.cb_model.blockSignals(False)
        info = self.db[key][3] if key in self.db else ""
        self.cb_model.setToolTip(info or "Модель")

    def _select(self, key):
        if key in self.db and key != self.value():
            self.setValue(key)
            self.changed.emit(key)

    # ── поиск и меню ──
    def find(self):
        if self._find_items is None:
            items = []
            for k, (b, name, p, info) in self.db.items():
                ser = self.series.get(k, "") if self.series else ""
                label = f"{b}  ·  {name}" + (f"   — {ser}" if ser and ser != b else "")
                text = f"{b} {name} {ser} {info} {k}".lower()
                if isinstance(p, dict) and p.get("pmax"):
                    text += f" {p['pmax']:g}w {p['pmax']:g}вт"
                items.append((k, label, text))
            self._find_items = items
        dlg = FindDialog(self._find_items, f"Поиск: {self.what}", self.window())
        cur = self.value()
        if cur in self.db:
            b, name, *_ = self.db[cur]
            dlg.ed.setText(f"{b} {name.split('·')[-1].strip()}".lower())
            dlg.ed.selectAll()
        if dlg.exec() == QDialog.Accepted and dlg.key:
            self._select(dlg.key)

    def _passport(self):
        k = self.value()
        if k not in self.db:
            return ""
        b, name, p, info = self.db[k]
        ps = ", ".join(f"{a}={v:g}" if isinstance(v, (int, float)) else f"{a}={v}" for a, v in p.items()) \
            if isinstance(p, dict) else ""
        return f"{b} {name}\n{info}\n{ps}".strip()

    def _menu(self, gpos):
        k = self.value()
        m = QMenu(self)
        m.addAction(f"🔎 Найти {self.what}…", self.find)
        m.addSeparator()
        cb = QGuiApplication.clipboard()
        if k in self.db:
            b, name, *_ = self.db[k]
            m.addAction("📋 Копировать название", lambda: cb.setText(f"{b} {name}"))
            m.addAction("📋 Копировать паспорт", lambda: cb.setText(self._passport()))
        if self.allow_custom:
            m.addSeparator()
            a = m.addAction("✎ Своё — параметры вручную", lambda: (self.setValue("custom"), self.changed.emit("custom")))
            a.setEnabled(k != "custom")
        if self.extra_menu:
            m.addSeparator()
            self.extra_menu(m)
        m.exec(gpos)


class Stepper(QWidget):
    changed = Signal(float)

    def __init__(self, lo, hi, step=1.0, dec=0, suffix="", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.sp = _Spin()
        self.sp.setRange(lo, hi)
        self.sp.setSingleStep(step)
        self.sp.setDecimals(dec)
        if suffix:
            self.sp.setSuffix(" " + suffix)
        # не NoButtons: в Qt 6.12 с QSS поле ввода тогда сжимается до 1 px; свои кнопки скрыты в QSS
        self.sp.setFocusPolicy(Qt.StrongFocus)
        self.sp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sp.setKeyboardTracking(False)
        self.sp.setMinimumWidth(80)
        bm, bp = QToolButton(), QToolButton()
        for b, t in ((bm, "−"), (bp, "+")):
            b.setText(t)
            b.setObjectName("stepBtn")
            b.setAutoRepeat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
        bm.clicked.connect(self.sp.stepDown)
        bp.clicked.connect(self.sp.stepUp)
        lay.addWidget(self.sp, 1)
        lay.addWidget(bm)
        lay.addWidget(bp)
        self.sp.valueChanged.connect(self.changed.emit)

    def value(self):
        return self.sp.value()

    def reconfigure(self, lo, hi, step, dec, suffix):
        self.sp.blockSignals(True)
        self.sp.setDecimals(dec)
        self.sp.setRange(lo, hi)
        self.sp.setSingleStep(step)
        self.sp.setSuffix(" " + suffix if suffix else "")
        self.sp.blockSignals(False)

    def setValue(self, v):
        self.sp.blockSignals(True)
        self.sp.setValue(float(v))
        self.sp.blockSignals(False)


def _lab(text, name=None, wrap=False):
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    if wrap:
        l.setWordWrap(True)
    return l


def _card(title):
    fr = QFrame()
    fr.setObjectName("card")
    v = QVBoxLayout(fr)
    v.setContentsMargins(14, 10, 14, 12)
    v.setSpacing(8)
    if title:
        v.addWidget(_lab(title.upper(), "cardTitle"))
    return fr, v


def _btn(text, name=None, tip=None, slot=None):
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


def _menu_style(menu):
    return menu


def _save_failed(parent, fn, e):
    log.error(f"✗ Не удалось сохранить {fn}: {e}")
    QMessageBox.warning(parent, app_name(), f"Не удалось сохранить файл:\n{fn}\n\n{e}\n\n"
                                          "Возможно, он открыт в другой программе (Excel) или нет прав на запись.")


def _nice(v):
    if v <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * e >= v:
            return m * e
    return 10 * e


def _fmt(v, dec=0):
    v = round(v, dec) + 0.0
    s = f"{v:,.{dec}f}".replace(",", " ").replace("-", "−")
    return s.replace(".", ",")


class Chart(QWidget):
    """Простой график: линии (x — числа) или сгруппированные столбцы (x — подписи)."""

    def __init__(self, kind="line", unit="Вт", title="", parent=None):
        super().__init__(parent)
        self.kind, self.unit, self.title = kind, unit, title
        self.series = []          # [(name, color, values)]
        self.xs, self.labels = [], []
        self.xmin, self.xmax = 0.0, 24.0
        self.hover = None
        self.p = _QT_THEMES["dark"]
        self.ydec = 0
        self.xfmt = "hour"
        self.markers = []        # [(x, подпись, цвет)]
        self.ymax_fixed = None
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def set_theme(self, p):
        self.p = p
        self.update()

    def set_data(self, series, xs=None, labels=None, xmin=None, xmax=None, ydec=0, markers=None):
        self.series = series
        self.markers = markers or []
        self.xs = xs or []
        self.labels = labels or []
        self.ydec = ydec
        if xmin is not None:
            self.xmin, self.xmax = xmin, xmax
        self.update()

    def _plot_rect(self):
        return QRectF(52, 54, max(10, self.width() - 64), max(10, self.height() - 84))

    def _ymax(self):
        if self.ymax_fixed:
            return self.ymax_fixed
        vals = [v for _, _, s in self.series for v in s]
        return _nice(max(vals) * 1.08) if vals and max(vals) > 0 else 1.0

    def paintEvent(self, e):
        p = self.p
        pa = QPainter(self)
        pa.setRenderHint(QPainter.Antialiasing)
        r = self._plot_rect()
        fnt = QFont("Segoe UI", 8)
        pa.setFont(fnt)
        fm = QFontMetrics(fnt)
        muted, line, text = QColor(p["muted"]), QColor(p["line"]), QColor(p["text"])
        # заголовок + легенда
        x = 8
        if self.title:
            f2 = QFont("Segoe UI", 9)
            f2.setBold(True)
            pa.setFont(f2)
            pa.setPen(text)
            pa.drawText(QPointF(x, 18), self.title)
            x += QFontMetrics(f2).horizontalAdvance(self.title) + 18
            pa.setFont(fnt)
        for name, col, _ in self.series:
            pa.setPen(Qt.NoPen)
            pa.setBrush(QColor(col))
            pa.drawRoundedRect(QRectF(x, 10, 10, 10), 3, 3)
            pa.setPen(muted)
            pa.drawText(QPointF(x + 14, 19), name)
            x += 14 + fm.horizontalAdvance(name) + 16
        ymax = self._ymax()
        ystep = ymax / 5
        ydig = 0 if abs(ystep - round(ystep)) < 1e-6 else 1 if abs(ystep * 10 - round(ystep * 10)) < 1e-6 else 2
        # сетка
        for i in range(6):
            yv = ymax * i / 5
            yy = r.bottom() - r.height() * i / 5
            pa.setPen(QPen(line, 1, Qt.SolidLine if i == 0 else Qt.DotLine))
            pa.drawLine(QPointF(r.left(), yy), QPointF(r.right(), yy))
            pa.setPen(muted)
            lab = _fmt(yv, ydig)
            pa.drawText(QRectF(0, yy - 8, r.left() - 6, 16), Qt.AlignRight | Qt.AlignVCenter, lab)
        pa.setPen(muted)
        pa.drawText(QRectF(0, r.top() - 28, r.left() - 6, 14), Qt.AlignRight | Qt.AlignVCenter, self.unit)
        if not self.series:
            pa.drawText(r, Qt.AlignCenter, "нет данных")
            return
        if self.kind == "line":
            span = max(1e-6, self.xmax - self.xmin)
            if self.xfmt == "deg":
                step = 10 if span > 40 else 5
            else:
                step = 1 if span <= 8 else 2 if span <= 16 else 3 if span <= 30 else 6 if span <= 80 else 12
            h = math.ceil(self.xmin)
            while h <= self.xmax:
                xx = r.left() + (h - self.xmin) / span * r.width()
                if int(h) % step == 0:
                    pa.setPen(muted)
                    lab = f"{int(h)}°" if self.xfmt == "deg" else f"{int(h) % 24}:00"
                    pa.drawText(QRectF(xx - 20, r.bottom() + 4, 40, 16), Qt.AlignCenter, lab)
                h += 1
            for name, col, vals in self.series:
                path = QPainterPath()
                fill = QPainterPath()
                started = False
                for xv, yv in zip(self.xs, vals):
                    if xv < self.xmin or xv > self.xmax:
                        continue
                    pt = QPointF(r.left() + (xv - self.xmin) / span * r.width(),
                                 r.bottom() - yv / ymax * r.height())
                    if not started:
                        path.moveTo(pt)
                        fill.moveTo(QPointF(pt.x(), r.bottom()))
                        fill.lineTo(pt)
                        started = True
                    else:
                        path.lineTo(pt)
                        fill.lineTo(pt)
                if started:
                    fill.lineTo(QPointF(path.currentPosition().x(), r.bottom()))
                    fill.closeSubpath()
                    fc = QColor(col)
                    fc.setAlpha(28)
                    pa.setPen(Qt.NoPen)
                    pa.setBrush(fc)
                    pa.drawPath(fill)
                    pa.setBrush(Qt.NoBrush)
                    pa.setPen(QPen(QColor(col), 2))
                    pa.drawPath(path)
            for mx, mlab, mcol in self.markers:
                if self.xmin <= mx <= self.xmax:
                    xx = r.left() + (mx - self.xmin) / span * r.width()
                    pa.setPen(QPen(QColor(mcol), 1.5, Qt.DashLine))
                    pa.drawLine(QPointF(xx, r.top()), QPointF(xx, r.bottom()))
                    pa.setPen(QColor(mcol))
                    pa.drawText(QPointF(xx + 4, r.top() + 12), mlab)
            if self.hover is not None and self.xs:
                xv = self.hover
                xx = r.left() + (xv - self.xmin) / span * r.width()
                pa.setPen(QPen(muted, 1, Qt.DashLine))
                pa.drawLine(QPointF(xx, r.top()), QPointF(xx, r.bottom()))
                idx = min(range(len(self.xs)), key=lambda i: abs(self.xs[i] - xv))
                hh = self.xs[idx]
                lines = [f"{hh:g}°" if self.xfmt == "deg" else
                         (f"день {int(hh // 24) + 1}, " if self.xmax > 25 else "") + fmt_t(hh)]
                lines += [f"{n}: {_fmt(v[idx], self.ydec)} {self.unit}" for n, _, v in self.series]
                self._tip_box(pa, xx, r, lines)
        else:
            n = len(self.labels)
            if n == 0:
                return
            gw = r.width() / n
            k = len(self.series)
            bw = min(16.0, gw * 0.8 / max(1, k))
            for i, lab in enumerate(self.labels):
                cx = r.left() + gw * (i + 0.5)
                pa.setPen(muted)
                pa.drawText(QRectF(cx - gw / 2, r.bottom() + 4, gw, 16), Qt.AlignCenter, lab)
                for j, (name, col, vals) in enumerate(self.series):
                    v = vals[i] if i < len(vals) else 0
                    hgt = v / ymax * r.height()
                    bx = cx - k * bw / 2 + j * bw
                    pa.setPen(Qt.NoPen)
                    c = QColor(col)
                    if self.hover is not None and self.hover != i:
                        c.setAlpha(150)
                    pa.setBrush(c)
                    pa.drawRoundedRect(QRectF(bx + 1, r.bottom() - hgt, bw - 2, hgt), 2.5, 2.5)
            if self.hover is not None and 0 <= self.hover < n:
                i = self.hover
                lines = [self.labels[i]] + [f"{nm}: {_fmt(v[i], self.ydec)} {self.unit}" for nm, _, v in self.series]
                self._tip_box(pa, r.left() + gw * (i + 0.5), r, lines)

    def _tip_box(self, pa, xx, r, lines):
        p = self.p
        fm = QFontMetrics(pa.font())
        w = max(fm.horizontalAdvance(s) for s in lines) + 16
        h = len(lines) * 16 + 8
        bx = xx + 10 if xx + 10 + w < r.right() else xx - 10 - w
        box = QRectF(bx, r.top() + 4, w, h)
        pa.setPen(QPen(QColor(p["accent"]), 1))
        pa.setBrush(QColor(p["panel2"]))
        pa.drawRoundedRect(box, 6, 6)
        pa.setPen(QColor(p["text"]))
        for i, s in enumerate(lines):
            pa.drawText(QPointF(bx + 8, r.top() + 20 + i * 16), s)

    def mouseMoveEvent(self, e):
        r = self._plot_rect()
        x = e.position().x()
        if not r.contains(e.position()):
            self.hover = None
        elif self.kind == "line":
            self.hover = self.xmin + (x - r.left()) / r.width() * (self.xmax - self.xmin)
        else:
            n = len(self.labels)
            self.hover = int((x - r.left()) / (r.width() / n)) if n else None
        self.update()

    def leaveEvent(self, e):
        self.hover = None
        self.update()

    def data_tsv(self):
        names = [n for n, _, _ in self.series]
        rows = []
        if self.kind == "line":
            deg, multi = self.xfmt == "deg", self.xmax > 25
            rows.append("\t".join(["Угол" if deg else "Время"] + names))
            for i, xv in enumerate(self.xs):
                if self.xmin <= xv <= self.xmax:
                    x = f"{xv:g}°" if deg else (f"день {int(xv // 24) + 1} " if multi else "") + fmt_t(xv)
                    rows.append("\t".join([x] + [f"{s[i]:.1f}".replace(".", ",") for _, _, s in self.series]))
        else:
            rows.append("\t".join([""] + names))
            for i, l in enumerate(self.labels):
                rows.append("\t".join([l] + [f"{s[i]:.2f}".replace(".", ",") for _, _, s in self.series]))
        return "\n".join(rows)

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("📋 Копировать изображение", lambda: QGuiApplication.clipboard().setPixmap(self.grab()))
        m.addAction("📋 Копировать данные (для Excel)", lambda: QGuiApplication.clipboard().setText(self.data_tsv()))
        m.addSeparator()
        m.addAction("💾 Сохранить PNG…", self._save_png)
        m.exec(self.mapToGlobal(pos))

    def _save_png(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Сохранить график", str(APP_ROOT / "график.png"),
                                            "PNG (*.png)", options=QFileDialog.DontUseNativeDialog)
        if not fn:
            return
        if self.grab().save(fn, "PNG"):
            log.info(f"✓ График сохранён: {fn}")
        else:
            _save_failed(self, fn, "ошибка записи PNG")


def make_table(headers, extra_actions=None):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(26)
    t.horizontalHeader().setStretchLastSection(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.setContextMenuPolicy(Qt.CustomContextMenu)
    t._extra = extra_actions or []

    def menu(pos):
        m = QMenu(t)
        row = t.rowAt(pos.y())
        for text, fn in t._extra:
            a = m.addAction(text, lambda fn=fn, row=row: fn(row))
            a.setEnabled(row >= 0)
        if t._extra:
            m.addSeparator()
        m.addAction("📋 Копировать строку", lambda: QGuiApplication.clipboard().setText(table_tsv(t, row)))
        m.addAction("📋 Копировать таблицу", lambda: QGuiApplication.clipboard().setText(table_tsv(t)))
        m.addAction("💾 Экспорт CSV…", lambda: export_table_csv(t))
        m.exec(t.viewport().mapToGlobal(pos))

    t.customContextMenuRequested.connect(menu)
    return t


def table_tsv(t, row=None):
    hdr = [t.horizontalHeaderItem(c).text() for c in range(t.columnCount())]
    rows = range(t.rowCount()) if row is None or row < 0 else [row]
    out = ["\t".join(hdr)] if row is None or row < 0 else []
    for r in rows:
        out.append("\t".join((t.item(r, c).text() if t.item(r, c) else "") for c in range(t.columnCount())))
    return "\n".join(out)


def export_table_csv(t):
    fn, _ = QFileDialog.getSaveFileName(t, "Экспорт CSV", str(APP_ROOT / "таблица.csv"), "CSV (*.csv)",
                                        options=QFileDialog.DontUseNativeDialog)
    if not fn:
        return
    try:
        with open(fn, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow([t.horizontalHeaderItem(c).text() for c in range(t.columnCount())])
            for r in range(t.rowCount()):
                w.writerow([(t.item(r, c).text() if t.item(r, c) else "") for c in range(t.columnCount())])
    except OSError as e:
        _save_failed(t, fn, e)
        return
    log.info(f"✓ CSV сохранён: {fn}")


def _item(text, align_right=False, color=None, bold=False):
    it = QTableWidgetItem(str(text))
    if align_right:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if color:
        it.setForeground(QColor(color))
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it
