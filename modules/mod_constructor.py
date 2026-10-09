"""mod_constructor.py  v1.9.0
Конструктор станции — холст: во главе инвертор; слева поля панелей на его входах MPPT; от инвертора вниз —
линия к шине АКБ, к этой линии сбоку подключены отдельные MPPT-контроллеры со своими полями; внизу — сборки
АКБ на шине; справа — дом и сеть. Линии «живые» (зигзаг с бегущими точками), цвет — проверка (✓ ⚠ ✗).
Клик — выбрать узел (справа его настройки), пунктирные «＋» — добавить, правый клик — меню.

Журнал:
v1.9.0: первая версия (вместо карточки «Моя станция»).
"""

import math

from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QSize, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath, QRadialGradient, QGuiApplication, QFontMetrics
from PySide6.QtWidgets import QWidget, QMenu, QFileDialog, QToolTip

from .mod_base import APP_ROOT, log
from .mod_theme import _OK, _WARN, _ERR

LVL = {"ok": _OK, "warn": _WARN, "err": _ERR}
C_INV, C_BAT, C_PV, C_CTL, C_HOUSE, C_GRID, C_BUS = "#3ecf8e", "#46a8e0", "#e8b04a", "#b48cf0", "#3ecf8e", "#8a91a3", "#36c2d9"
GAP = 44


def dir_word(aspect):
    """Азимут → «юг», «юго-запад», … (0 — юг, −90 — восток, +90 — запад)."""
    a = (float(aspect) + 360) % 360
    return ("юг", "юго-запад", "запад", "северо-запад", "север", "северо-восток", "восток", "юго-восток")[int((a + 22.5) // 45) % 8]


class StationCanvas(QWidget):
    """Рисует граф станции из data (готовит страница настроек) и сообщает о выборе / добавлении / удалении."""
    picked = Signal(str, int)          # узел: inv, field, ctl, bat, house, grid, cable_pv, cable_bus, cable_ctl
    add = Signal(str)                  # pv, ctl, bat
    remove = Signal(str, int)          # field, bat
    clone = Signal(str, int)           # field

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.pal = {}
        self.dark = True
        self.sel = ("inv", 0)
        self.hover = None
        self.hits = []                 # [(QRectF, kind, idx, tip)]
        self.phase = 0
        self._h = 560
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setMinimumSize(640, 560)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(110)

    def set_data(self, data, pal, dark=True):
        self.data, self.pal, self.dark = data, pal, dark
        self.update()

    def select(self, kind, idx=0):
        self.sel = (kind, idx)
        self.update()

    def _tick(self):
        if self.isVisible() and not self.visibleRegion().isEmpty():     # не видно (прокручено, свёрнуто) — не рисуем
            self.phase = (self.phase + 1) % 1000
            self.update()

    def sizeHint(self):
        return QSize(900, self._h)

    # ── краски ──
    def _c(self, key):
        dark = self.dark
        return {"bg": "#0e1014" if dark else "#eef1f6", "card": "#181b22" if dark else "#ffffff",
                "dot": "#1b1f27" if dark else "#dde2ea", "text": "#ffffff" if dark else "#1c2230",
                "muted": self.pal.get("muted", "#8a91a3")}[key]

    # ── рисование ──
    def _zig(self, p, pts, col, w=2.0, amp=3.2, step=9, dots=True, dashed=False, flow=1):
        path = QPainterPath()
        samples = []
        first = True
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            L = math.hypot(x1 - x0, y1 - y0)
            if L < 1:
                continue
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            nx, ny = -uy, ux
            n = max(2, int(L // step))
            for i in range(n + 1):
                t = i / n
                off = 0 if dashed else ((amp if i % 2 else -amp) if 0 < i < n else 0)
                x, y = x0 + (x1 - x0) * t + nx * off, y0 + (y1 - y0) * t + ny * off
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)
                samples.append((x, y))
        c = QColor(col)
        if not dashed:
            glow = QColor(c)
            glow.setAlpha(55)
            p.setPen(QPen(glow, w + 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        p.setPen(QPen(c, w, Qt.DashLine if dashed else Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        if dots and samples and flow:
            p.setPen(Qt.NoPen)
            p.setBrush(c.lighter(150))
            k = 6
            off = (self.phase * flow) % k
            for i in range(off, len(samples), k):
                x, y = samples[i]
                p.drawEllipse(QPointF(x, y), 2.2, 2.2)

    def _node(self, p, r, icon, big, lines, border, kind, idx, tip="", dashed=False, big_col=None, badge=None):
        sel = self.sel == (kind, idx)
        hov = self.hover == (kind, idx)
        if sel:
            g = QRadialGradient(r.center(), max(r.width(), r.height()) * 0.85)
            cc = QColor(border)
            cc.setAlpha(80)
            g.setColorAt(0, cc)
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(r.adjusted(-14, -14, 14, 14), 20, 20)
        p.setBrush(QColor(self._c("card")) if not dashed else Qt.NoBrush)
        bc = QColor(border)
        if hov and not sel:
            bc = bc.lighter(130)
        p.setPen(QPen(bc, 2.8 if sel else (2.0 if hov else 1.5), Qt.DashLine if dashed else Qt.SolidLine))
        p.drawRoundedRect(r, 12, 12)
        y = r.top() + 6
        f = QFont(self.font())
        f.setPointSize(14)
        p.setFont(f)
        p.setPen(QColor(self._c("text") if not dashed else self._c("muted")))
        p.drawText(QRectF(r.left(), y, r.width(), 24), Qt.AlignCenter, icon)
        y += 24
        if badge:
            fb = QFont(self.font())
            fb.setPointSize(7)
            fb.setBold(True)
            p.setFont(fb)
            bw = QFontMetrics(fb).horizontalAdvance(badge) + 10
            br = QRectF(r.right() - bw - 8, r.top() + 8, bw, 15)
            p.setPen(QPen(QColor(border), 1.2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(br, 4, 4)
            p.drawText(br, Qt.AlignCenter, badge)
        fbig = QFont(self.font())
        fbig.setPointSize(13)
        fbig.setBold(True)
        p.setFont(fbig)
        p.setPen(QColor(big_col or self._c("text")) if not dashed else QColor(self._c("muted")))
        fm = QFontMetrics(fbig)
        p.drawText(QRectF(r.left() + 4, y, r.width() - 8, 24), Qt.AlignCenter,
                   fm.elidedText(big, Qt.ElideRight, int(r.width() - 10)))
        y += 24
        fs = QFont(self.font())
        fs.setPointSizeF(max(7.0, fs.pointSizeF() - 1.6))
        p.setFont(fs)
        fms = QFontMetrics(fs)
        for ln in lines:
            if y + 14 > r.bottom() - 2:
                break
            col = self._c("muted")
            if isinstance(ln, tuple):
                ln, col = ln
            p.setPen(QColor(col))
            p.drawText(QRectF(r.left() + 4, y, r.width() - 8, 15), Qt.AlignCenter,
                       fms.elidedText(ln, Qt.ElideRight, int(r.width() - 10)))
            y += 15
        self.hits.append((r, kind, idx, tip))

    def _label(self, p, x, y, text, col, kind=None, idx=0, left=False):
        f = QFont(self.font())
        f.setPointSizeF(max(7.0, f.pointSizeF() - 1.6))
        p.setFont(f)
        tw = QFontMetrics(f).horizontalAdvance(text) + 12
        r = QRectF(x if left else x - tw / 2, y - 9, tw, 18)
        p.setPen(QPen(QColor(col), 1.0) if kind and self.sel == (kind, idx) else Qt.NoPen)
        p.setBrush(QColor(self._c("bg")))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(QColor(col))
        p.drawText(r, Qt.AlignCenter, text)
        if kind:
            self.hits.append((r.adjusted(-4, -4, 4, 4), kind, idx, "Кабель — нажмите, чтобы настроить"))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(self._c("bg")))
        p.setPen(QColor(self._c("dot")))
        for x in range(10, self.width(), 24):
            for y in range(10, self.height(), 24):
                p.drawPoint(x, y)
        d = self.data
        if not d:
            return
        self.hits = []
        W = self.width()
        M = 16
        CW = max(150, min(200, (W - 2 * M - 3 * GAP) / 4))
        CH_F, CH_I, CH_C, CH_B, CH_H = 118, 150, 96, 106, 100
        x0 = M
        x1 = x0 + CW + GAP
        x2 = x1 + CW + GAP
        x3 = max(x2 + CW + GAP, W - M - CW)
        y0 = 14
        A = d["a"]
        nA = len(A) + (1 if d.get("add_a") else 0)
        stack_h = max(1, nA) * (CH_F + 14) - 14
        inv = QRectF(x2, y0 + max(0, (stack_h - CH_I) / 2), CW, CH_I)
        house = QRectF(x3, y0, CW, CH_H)
        grid = QRectF(x3, y0 + CH_H + 16, CW, CH_H)
        top_bottom = max(y0 + stack_h, inv.bottom(), grid.bottom())
        # ── поля на входах инвертора ──
        nports = max(1, d["inv"]["ports"]) if d["inv"]["builtin"] else 0

        def port_y(k):
            return inv.top() + 34 + (k + 0.5) * (inv.height() - 44) / max(1, nports)
        for i, f in enumerate(A):
            r = QRectF(x0, y0 + i * (CH_F + 14), CW, CH_F)
            col = LVL.get(f["lvl"], C_GRID)
            xe = x1 + CW / 2 + (i - len(A) / 2) * 10
            for q in range(f["k"]):                              # поле на k входов — к каждому своя цепочка
                py = port_y(f["port"] + q)
                yo = r.center().y() + (q - (f["k"] - 1) / 2) * 12
                self._zig(p, [(r.right(), yo), (xe + q * 8, yo), (xe + q * 8, py), (inv.left(), py)], col)
            self._label(p, r.right() + 6, r.top() + 12, f["cable"], col, "cable_pv", f["idx"], left=True)
            self._node(p, r, "☀", f["big"], f["lines"], C_PV, "field", f["idx"], f.get("tip", ""), big_col="#ffd27a" if self.dark else "#b57a00")
        if d.get("add_a"):
            r = QRectF(x0, y0 + len(A) * (CH_F + 14), CW, 74)
            self._node(p, r, "＋", d["add_a"], ["свободный вход MPPT"], C_GRID, "add_pv", 0, "Подключить поле на свободный вход", dashed=True)
        # ── инвертор ──
        iv = d["inv"]
        self._node(p, inv, "⚡", iv["big"], iv["lines"], C_INV, "inv", 0, iv.get("tip", ""), badge="MPPT" if iv["builtin"] else None)
        f = QFont(self.font())
        f.setPointSizeF(max(6.5, f.pointSizeF() - 2.2))
        p.setFont(f)
        for k in range(nports):
            used = any(a["port"] <= k < a["port"] + a["k"] for a in A)
            col = QColor(_OK if used else self._c("muted"))
            p.setPen(col)
            p.drawText(QRectF(inv.left() - 52, port_y(k) - 16, 48, 13), Qt.AlignRight | Qt.AlignVCenter, f"MPPT {k + 1}")
            p.setPen(QPen(col, 1.6))
            p.setBrush(QColor(self._c("card")) if not used else col)
            p.drawEllipse(QPointF(inv.left(), port_y(k)), 4, 4)
        # ── дом и сеть ──
        hs, gr = d["house"], d["grid"]
        clamp = lambda y: min(max(y, inv.top() + 22), inv.bottom() - 22)
        yh = clamp(house.center().y())
        yg = max(clamp(grid.center().y()), yh + 26)
        xm = (inv.right() + house.left()) / 2
        self._zig(p, [(inv.right(), yh), (xm - 6, yh), (xm - 6, house.center().y()), (house.left(), house.center().y())], C_HOUSE)
        self._zig(p, [(grid.left(), grid.center().y()), (xm + 6, grid.center().y()), (xm + 6, yg), (inv.right(), yg)],
                  C_GRID, 1.8, dashed=not gr.get("on", True), flow=-1 if gr.get("on", True) else 0)
        self._node(p, house, "🏠", hs["big"], hs["lines"], C_HOUSE, "house", 0, hs.get("tip", ""))
        self._node(p, grid, "🔌", gr["big"], gr["lines"], C_GRID, "grid", 0, gr.get("tip", ""))
        # ── отдельные MPPT — к линии «АКБ → инвертор» ──
        B = d["b"]
        yb0 = top_bottom + 30
        xv = inv.center().x()
        nB = len(B) + (1 if d.get("add_b") else 0)
        y_bus = yb0 + max(0, nB) * (CH_F + 14) + 24
        for j, b in enumerate(B):
            rf = QRectF(x0, yb0 + j * (CH_F + 14), CW, CH_F)
            rc = QRectF(x1, rf.center().y() - CH_C / 2, CW, CH_C)
            col = LVL.get(b["lvl"], C_GRID)
            self._zig(p, [(rf.right(), rf.center().y()), (rc.left(), rc.center().y())], col)
            self._zig(p, [(rc.right(), rc.center().y()), (xv, rc.center().y())], C_BUS, 2.4, flow=1)
            self._label(p, (rc.right() + xv) / 2, rc.center().y() - 14, b["cable2"], C_BUS, "cable_ctl", b["idx"])
            self._node(p, rf, "☀", b["big"], b["lines"], C_PV, "field", b["idx"], b.get("tip", ""), big_col="#ffd27a" if self.dark else "#b57a00")
            ct = b["ctl"]
            self._node(p, rc, "🔀", ct["big"], ct["lines"], C_CTL, "ctl", b["idx"], ct.get("tip", ""))
        if d.get("add_b"):
            r = QRectF(x1, yb0 + len(B) * (CH_F + 14) + (CH_F - 80) / 2, CW, 80)
            self._zig(p, [(r.right(), r.center().y()), (xv, r.center().y())], C_GRID, 1.2, dots=False, dashed=True)
            self._node(p, r, "＋", d["add_b"], ["к линии АКБ → инвертор"], C_GRID, "add_ctl", 0,
                       "Отдельный MPPT-контроллер со своим полем — на линию АКБ", dashed=True)
        # ── линия инвертор → шина АКБ и сборки ──
        bus = d["bus"]
        self._zig(p, [(xv, inv.bottom()), (xv, y_bus)], LVL.get(bus["lvl"], C_BUS) if bus["lvl"] != "ok" else C_BUS, 3.2, amp=4, flow=-1)
        self._label(p, xv + 8, (inv.bottom() + min(y_bus, (yb0 if B else y_bus))) / 2 if not B else inv.bottom() + 16,
                    bus["text"], LVL.get(bus["lvl"], C_BUS), "cable_bus", 0, left=True)
        bats = d["bats"]
        nb = len(bats) + (1 if d.get("add_bat") else 0)
        per_row = max(1, int((W - 2 * M + 14) // (CW + 14)))
        xs = []
        for j in range(nb):
            rr, cc = divmod(j, per_row)
            xs.append((M + cc * (CW + 14), y_bus + 26 + rr * (CH_B + 30)))
        if xs:
            xa = min(x + CW / 2 for x, y in xs[:per_row])
            xb = max(max(x + CW / 2 for x, y in xs[:per_row]), xv)
            p.setPen(QPen(QColor(C_BUS), 3.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(min(xa, xv), y_bus), QPointF(xb, y_bus))
            self._label(p, xb + 8, y_bus - 12, d.get("bus_v", ""), C_BUS, left=True)
        for j, b in enumerate(bats):
            x, y = xs[j]
            r = QRectF(x, y, CW, CH_B)
            if y > y_bus + 30:                                  # второй ряд — своя «ветка» от шины
                self._zig(p, [(r.center().x(), y_bus), (r.center().x(), r.top())], C_BUS, 1.6, amp=2, flow=0)
            else:
                self._zig(p, [(r.center().x(), y_bus), (r.center().x(), r.top())], C_BUS, 2.0, amp=3, flow=1)
            self._node(p, r, "🔋", b["big"], b["lines"], C_BAT, "bat", j, b.get("tip", ""), big_col="#9fd4ff" if self.dark else "#1f6fa8")
        if d.get("add_bat"):
            x, y = xs[-1]
            r = QRectF(x, y + 12, min(CW, 120), CH_B - 24)
            self._node(p, r, "＋", "АКБ", ["ещё сборка"], C_GRID, "add_bat", 0, "Другая сборка АКБ на ту же шину", dashed=True)
        bottom = (max(y for _, y in xs) + CH_B + 16) if xs else y_bus + 40
        h = int(bottom)
        if h != self._h:
            self._h = h
            self.setMinimumHeight(h)
            self.updateGeometry()
        p.end()

    # ── мышь ──
    def _hit(self, pos):
        for r, kind, idx, tip in reversed(self.hits):
            if r.contains(QPointF(pos)):
                return kind, idx, tip
        return None

    def mouseMoveEvent(self, e):
        h = self._hit(e.position())
        new = (h[0], h[1]) if h else None
        if new != self.hover:
            self.hover = new
            self.update()
        self.setCursor(Qt.PointingHandCursor if h else Qt.ArrowCursor)
        if h and h[2]:
            QToolTip.showText(e.globalPosition().toPoint(), h[2], self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, e):
        self.hover = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        h = self._hit(e.position())
        if not h:
            return
        kind, idx, _ = h
        if kind.startswith("add_"):
            self.add.emit(kind[4:])
            return
        self.select(kind, idx)
        self.picked.emit(kind, idx)

    def _menu(self, pos):
        h = self._hit(pos)
        d = self.data or {}
        m = QMenu(self)
        if h and not h[0].startswith("add_"):
            kind, idx, _ = h
            m.addAction("⚙ Настроить", lambda: (self.select(kind, idx), self.picked.emit(kind, idx)))
            if kind == "field":
                m.addAction("⧉ Копия поля (ещё такое же)", lambda: self.clone.emit("field", idx))
                a = m.addAction("🗑 Убрать поле", lambda: self.remove.emit("field", idx))
                a.setEnabled(idx > 0)
            if kind == "bat":
                a = m.addAction("🗑 Убрать сборку", lambda: self.remove.emit("bat", idx))
                a.setEnabled(idx > 0)
            m.addSeparator()
        a = m.addAction("＋ Поле на свободный вход MPPT", lambda: self.add.emit("pv"))
        a.setEnabled(bool(d.get("add_a")))
        a = m.addAction("＋ Отдельный MPPT с полем (к линии АКБ)", lambda: self.add.emit("ctl"))
        a.setEnabled(bool(d.get("add_b")))
        a = m.addAction("＋ Ещё сборка АКБ", lambda: self.add.emit("bat"))
        a.setEnabled(bool(d.get("add_bat")))
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
