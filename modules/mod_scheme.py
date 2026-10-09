"""mod_scheme.py  v1.9.0
Схема подключения станции (рисунок): во главе инвертор, на его входах MPPT — поля панелей; отдельные
MPPT-контроллеры со своими полями — на шине АКБ; сборки АКБ; дом и сеть. Цвет линии поля — проверка входа
(✓ зелёный, ⚠ жёлтый, ✗ красный). Клик по свободному входу — подключить поле; правый клик — меню.

Журнал:
v1.9.0: первая версия.
"""

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QGuiApplication, QPainterPath
from PySide6.QtWidgets import QWidget, QMenu, QFileDialog, QToolTip

from .mod_base import APP_ROOT, log
from .mod_theme import _OK, _WARN, _ERR

ROW = 58          # высота строки поля
BOX = 46          # высота блока поля / контроллера
LVL_COL = {"ok": _OK, "warn": _WARN, "err": _ERR, "off": None}


def _dir_word(aspect):
    a = (float(aspect) + 360) % 360
    return ("юг", "юго-запад", "запад", "северо-запад", "север", "северо-восток", "восток", "юго-восток")[int((a + 22.5) // 45) % 8]


class SchemeView(QWidget):
    """data = dict(inv=dict(name, sub, ports, builtin), fields=[dict(port, k, title, sub, lvl, tip, ctl)],
    ctls=[dict(title, sub, field_idx)], bats=[dict(title, sub)], bus_v, free_ports=[…])."""
    addField = Signal()            # подключить поле на свободный вход
    addCtl = Signal()              # отдельный MPPT с полем
    addBat = Signal()              # ещё сборка АКБ
    picked = Signal(str, int)      # что нажали: «field»/«ctl»/«bat»/«inv», номер

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.pal = {}
        self.hits = []             # [(QRectF, kind, idx, tip)]
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setMinimumHeight(180)

    def set_data(self, data, pal):
        self.data, self.pal = data, pal
        self.setMinimumHeight(self._height())
        self.updateGeometry()
        self.update()

    # ── размеры ──
    def _rows(self):
        d = self.data or {}
        a = max(2, d.get("inv", {}).get("ports", 1)) if d.get("inv", {}).get("builtin") else 2
        b = len(d.get("ctl_rows", []))
        return a, b

    def _height(self):
        if not self.data:
            return 180
        a, b = self._rows()
        bats = len(self.data.get("bats", []))
        h_left = 14 + a * ROW + (b * ROW + 26 if b else 0)
        h_bats = 14 + 2 * ROW + 20 + bats * 52
        return int(max(h_left, h_bats, 180) + 10)

    def sizeHint(self):
        return QSize(1000, self._height())

    # ── рисование ──
    def _box(self, p, r, title, sub, lvl=None, accent=False, dashed=False):
        pal = self.pal
        path = QPainterPath()
        path.addRoundedRect(r, 9, 9)
        p.setPen(QPen(QColor(pal["accent"] if accent else pal["line"]), 1.6 if accent else 1.0,
                      Qt.DashLine if dashed else Qt.SolidLine))
        p.setBrush(QColor(pal["panel2"]) if not dashed else Qt.NoBrush)
        p.drawPath(path)
        if lvl in ("ok", "warn", "err"):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(LVL_COL[lvl]))
            p.drawRoundedRect(QRectF(r.left() + 1, r.top() + 6, 4, r.height() - 12), 2, 2)
        f = QFont(self.font())
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(pal["text"] if not dashed else pal["muted"]))
        fm = QFontMetrics(f)
        tr = QRectF(r.left() + 12, r.top() + 4, r.width() - 18, r.height() / 2)
        p.drawText(tr, Qt.AlignLeft | Qt.AlignVCenter, fm.elidedText(title, Qt.ElideRight, int(tr.width())))
        if sub:
            f2 = QFont(self.font())
            f2.setPointSizeF(max(7.5, f2.pointSizeF() - 1.2))
            p.setFont(f2)
            p.setPen(QColor(pal["muted"]))
            fm2 = QFontMetrics(f2)
            sr = QRectF(r.left() + 12, r.top() + r.height() / 2 - 1, r.width() - 18, r.height() / 2 - 3)
            p.drawText(sr, Qt.AlignLeft | Qt.AlignVCenter, fm2.elidedText(sub, Qt.ElideRight, int(sr.width())))

    def _wire(self, p, pts, col, w=2.0, dashed=False):
        p.setPen(QPen(QColor(col), w, Qt.DashLine if dashed else Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath(QPointF(*pts[0]))
        for x, y in pts[1:]:
            path.lineTo(QPointF(x, y))
        p.drawPath(path)

    def _small(self, p, x, y, text, col=None, align=Qt.AlignLeft):
        f = QFont(self.font())
        f.setPointSizeF(max(7.0, f.pointSizeF() - 1.5))
        p.setFont(f)
        p.setPen(QColor(col or self.pal["muted"]))
        w = 220
        r = QRectF(x if align == Qt.AlignLeft else x - w, y - 9, w, 18)
        p.drawText(r, align | Qt.AlignVCenter, text)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.pal
        if not self.data or not pal:
            return
        d = self.data
        self.hits = []
        W = self.width()
        a_rows, b_rows = self._rows()
        top = 10
        xf0, xf1 = 8, int(W * 0.34)                     # поля
        xm0, xm1 = int(W * 0.40), int(W * 0.60)         # инвертор / контроллеры
        xbus = int(W * 0.66)                            # шина АКБ
        xr0, xr1 = int(W * 0.70), W - 8                 # дом, сеть, АКБ
        inv = d["inv"]
        # ── инвертор ──
        h_inv = max(2, a_rows) * ROW - 12
        ri = QRectF(xm0, top, xm1 - xm0, h_inv)
        self._box(p, ri, inv["name"], "", accent=True)
        f = QFont(self.font())
        f.setPointSizeF(max(7.5, f.pointSizeF() - 1.2))
        p.setFont(f)
        p.setPen(QColor(pal["muted"]))
        p.drawText(QRectF(ri.left() + 12, ri.top() + 26, ri.width() - 18, ri.height() - 30),
                   Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, inv["sub"])
        self.hits.append((ri, "inv", 0, inv.get("tip", "")))
        # дом и сеть — справа от инвертора, сверху
        rh = QRectF(xr0, top, xr1 - xr0, 38)
        rg = QRectF(xr0, top + 46, xr1 - xr0, 38)
        self._box(p, rh, "🏠 Дом", d.get("house", ""))
        self._box(p, rg, "🔌 Сеть", d.get("grid", ""))
        ac = QColor(pal["muted"])
        self._wire(p, [(ri.right(), rh.center().y()), (rh.left(), rh.center().y())], ac, 2)
        self._wire(p, [(ri.right(), rg.center().y()), (rg.left(), rg.center().y())], ac, 2, dashed=True)
        self._small(p, ri.right() + 6, rh.center().y() - 9, "AC 230 В")
        # шина АКБ
        y_dc = ri.bottom() - 16
        y_bus_end = max(y_dc + 30, top + 2 * ROW + 20 + max(1, len(d.get("bats", []))) * 52 - 20)
        ctl_rows = d.get("ctl_rows", [])
        y_ctl0 = top + a_rows * ROW + 26
        if ctl_rows:
            y_bus_end = max(y_bus_end, y_ctl0 + (len(ctl_rows) - 1) * ROW + BOX / 2)
        dcc = QColor(pal["accent"])
        self._wire(p, [(ri.right(), y_dc), (xbus, y_dc)], dcc, 3)
        self._wire(p, [(xbus, y_dc), (xbus, y_bus_end)], dcc, 4)
        self._small(p, ri.right() + 6, y_dc - 10, f"DC {d.get('bus_v', '')}", pal["accent"])
        # АКБ — справа от шины, ниже дома/сети
        yb = top + 2 * ROW - 10
        for j, b in enumerate(d.get("bats", [])):
            rb = QRectF(xr0, yb + j * 52, xr1 - xr0, BOX)
            if rb.center().y() < y_dc:
                rb.moveTop(y_dc - BOX / 2 + j * 52)
            self._box(p, rb, b["title"], b["sub"])
            self._wire(p, [(xbus, rb.center().y()), (rb.left(), rb.center().y())], dcc, 2.5)
            self.hits.append((rb, "bat", j, b.get("tip", "")))
        # ── поля на входах инвертора (или на контроллерах основной модели) ──
        ports = d.get("ports", [])
        for r in ports:
            y = top + r["row"] * ROW + BOX / 2
            if r["kind"] == "field":
                rf = QRectF(xf0, y - BOX / 2, xf1 - xf0, BOX)
                self._box(p, rf, r["title"], r["sub"], r["lvl"])
                col = LVL_COL.get(r["lvl"]) or pal["muted"]
                xin = ri.left()
                self._wire(p, [(rf.right(), y), (xin, y)], col, 2.2)
                self._small(p, rf.right() + 8, y - 10, r.get("wire", ""), col)
                self.hits.append((rf, "field", r["idx"], r.get("tip", "")))
            else:                                       # свободный вход
                rf = QRectF(xf0, y - BOX / 2, xf1 - xf0, BOX)
                self._box(p, rf, "＋ подключить поле", "вход свободен — нажмите", dashed=True)
                self._wire(p, [(rf.right(), y), (ri.left(), y)], pal["line"], 1.5, dashed=True)
                self.hits.append((rf, "free", r["port"], "Подключить поле панелей на этот вход"))
            # подпись входа внутри инвертора
            self._small(p, ri.left() + 8, y, r["port_label"], pal["text"])
        # ── отдельные MPPT-контроллеры со своими полями ──
        if ctl_rows:
            self._small(p, xf0, y_ctl0 - 16, d.get("ctl_head", "Отдельные MPPT на шине АКБ"), pal["text"])
        for j, r in enumerate(ctl_rows):
            y = y_ctl0 + j * ROW + BOX / 2
            rf = QRectF(xf0, y - BOX / 2, xf1 - xf0, BOX)
            rc = QRectF(xm0, y - BOX / 2, xm1 - xm0, BOX)
            self._box(p, rf, r["title"], r["sub"], r["lvl"])
            self._box(p, rc, r["ctl_title"], r["ctl_sub"])
            col = LVL_COL.get(r["lvl"]) or pal["muted"]
            self._wire(p, [(rf.right(), y), (rc.left(), y)], col, 2.2)
            self._small(p, rf.right() + 8, y - 10, r.get("wire", ""), col)
            self._wire(p, [(rc.right(), y), (xbus, y)], dcc, 2.5)
            self.hits.append((rf, "field", r["idx"], r.get("tip", "")))
            self.hits.append((rc, "ctl", r["idx"], r.get("ctl_tip", "")))
        p.end()

    # ── мышь ──
    def _hit(self, pos):
        for r, kind, idx, tip in self.hits:
            if r.contains(QPointF(pos)):
                return kind, idx, tip
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor)
        if h and h[2]:
            QToolTip.showText(e.globalPosition().toPoint(), h[2], self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        h = self._hit(e.position())
        if not h:
            return
        if h[0] == "free":
            self.addField.emit()
        else:
            self.picked.emit(h[0], h[1])

    def _menu(self, pos):
        m = QMenu(self)
        d = self.data or {}
        a = m.addAction("＋ Подключить поле на свободный вход", self.addField.emit)
        a.setEnabled(bool(d.get("can_add_field")))
        a = m.addAction("＋ Отдельный MPPT-контроллер с полем", self.addCtl.emit)
        a.setEnabled(bool(d.get("can_add_ctl")))
        a = m.addAction("＋ Ещё сборка АКБ", self.addBat.emit)
        a.setEnabled(bool(d.get("can_add_bat")))
        m.addSeparator()
        m.addAction("📋 Копировать схему (картинка)", lambda: QGuiApplication.clipboard().setPixmap(self.grab()))
        m.addAction("📋 Копировать схему (текст)", lambda: QGuiApplication.clipboard().setText(d.get("text", "")))
        m.addAction("💾 Сохранить картинку…", self._save)
        m.exec(self.mapToGlobal(pos))

    def _save(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Сохранить схему", str(APP_ROOT / "схема_станции.png"), "PNG (*.png)",
                                            options=QFileDialog.DontUseNativeDialog)
        if fn:
            if self.grab().save(fn):
                log.info(f"✓ Схема сохранена: {fn}")
            else:
                log.error(f"✗ Не удалось сохранить схему: {fn}")
