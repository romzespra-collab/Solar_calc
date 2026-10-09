"""mod_constructor.py  v1.9.2
Конструктор станции — холст: во главе инвертор; слева поля панелей на его входах MPPT; от инвертора вниз —
линия к шине АКБ, к этой линии сбоку подключены отдельные MPPT-контроллеры со своими полями; внизу — сборки
АКБ на шине; справа — дом и сеть. Линии «живые» (зигзаг с бегущими точками), цвет — проверка (✓ ⚠ ✗).
Клик — выбрать узел (справа его настройки), перетащить мышью — переставить (линии идут следом, место
запоминается), пунктирные «＋» — добавить, правый клик — меню.

Журнал:
v1.9.2: линии — как в Smart_BMS: сторона входа по зазору между краями карточек (поле выше инвертора — сверху),
        у каждой линии своя дорожка (±14 px), из двух колен — то, что не режет чужие узлы, середина колена
        отходит от чужих карточек; входы MPPT отмечены там, где входит линия поля (нет такого входа — красным);
        меню контроллера: «⧉ Копия», «🗑 Убрать» (вместе с его полем); поле 1 и сборку 1 тоже можно убрать,
        если есть другие (data rm_main / rm_bat0).
v1.9.1: узлы перетаскиваются мышью, места запоминаются (pos → сигнал moved); меню «↺ Вернуть на место»,
        «↺ Расставить автоматически»; линии прокладываются от узла к узлу с любой стороны.
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
    moved = Signal(dict)               # места узлов после перетаскивания: {ключ: [x, y]}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self.pal = {}
        self.dark = True
        self.sel = ("inv", 0)
        self.hover = None
        self.hits = []                 # [(QRectF, kind, idx, tip, ключ узла | None)]
        self.placed = []               # прямоугольники подписей кабелей (чтобы не налезали)
        self.pos = {}                  # места, переставленные мышью: {ключ узла: (x, y)}
        self.press = None              # (точка, ключ, kind, idx, левый верх узла)
        self.dragging = False
        self.phase = 0
        self._h = 560
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.setMinimumSize(640, 560)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(110)

    def set_data(self, data, pal, dark=True, pos=None):
        self.data, self.pal, self.dark = data, pal, dark
        if pos is not None and not self.dragging:
            self.pos = {k: tuple(v) for k, v in pos.items()}
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

    def _node(self, p, r, icon, big, lines, border, kind, idx, tip="", dashed=False, big_col=None, badge=None, key=None):
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
        self.hits.append((r, kind, idx, tip, key))

    def _lab_font(self):
        f = QFont(self.font())
        f.setPointSizeF(max(7.0, f.pointSizeF() - 1.6))
        return f

    def _lab_rect(self, x, y, text, left=False, right=False):
        tw = QFontMetrics(self._lab_font()).horizontalAdvance(text) + 12
        return QRectF(x if left else x - tw if right else x - tw / 2, y - 9, tw, 18)

    def _label(self, p, x, y, text, col, kind=None, idx=0, left=False, right=False):
        """Подпись на плашке: left — от x вправо, right — до x слева, иначе по центру x."""
        p.setFont(self._lab_font())
        r = self._lab_rect(x, y, text, left, right)
        self.placed.append(r)
        p.setPen(QPen(QColor(col), 1.0) if kind and self.sel == (kind, idx) else Qt.NoPen)
        p.setBrush(QColor(self._c("bg")))
        p.drawRoundedRect(r, 6, 6)
        p.setPen(QColor(col))
        p.drawText(r, Qt.AlignCenter, text)
        if kind:
            self.hits.append((r.adjusted(-4, -4, 4, 4), kind, idx, "Кабель — нажмите, чтобы настроить", None))

    # ── раскладка: сама + переставленное мышью ──
    def _layout(self, d, W):
        """Прямоугольники узлов {ключ: QRectF}: раскладка по умолчанию, поверх — места из self.pos."""
        M = 16
        CW = max(150, min(200, (W - 2 * M - 3 * GAP) / 4))
        CH_F, CH_I, CH_C, CH_B, CH_H = 118, 150, 96, 106, 100
        x0 = M
        x1 = x0 + CW + GAP
        x2 = x1 + CW + GAP
        x3 = max(x2 + CW + GAP, W - M - CW)
        y0 = 14
        R = {}
        A, B = d["a"], d["b"]
        nA = len(A) + (1 if d.get("add_a") else 0)
        stack_h = max(1, nA) * (CH_F + 14) - 14
        R["inv"] = QRectF(x2, y0 + max(0, (stack_h - CH_I) / 2), CW, CH_I)
        R["house"] = QRectF(x3, y0, CW, CH_H)
        R["grid"] = QRectF(x3, y0 + CH_H + 16, CW, CH_H)
        for i, f in enumerate(A):
            R["field:" + f["key"]] = QRectF(x0, y0 + i * (CH_F + 14), CW, CH_F)
        if d.get("add_a"):
            R["add_pv"] = QRectF(x0, y0 + len(A) * (CH_F + 14), CW, 74)

        top_bottom = max(y0 + stack_h, R["inv"].bottom(), R["grid"].bottom())
        yb0 = top_bottom + 30
        for j, b in enumerate(B):
            rf = QRectF(x0, yb0 + j * (CH_F + 14), CW, CH_F)
            R["field:" + b["key"]] = rf
            R["ctl:" + b["key"]] = QRectF(x1, rf.center().y() - CH_C / 2, CW, CH_C)
        if d.get("add_b"):
            R["add_ctl"] = QRectF(x1, yb0 + len(B) * (CH_F + 14) + (CH_F - 80) / 2, CW, 80)
        nB = len(B) + (1 if d.get("add_b") else 0)
        y_bus = yb0 + nB * (CH_F + 14) + 24
        nb = len(d["bats"]) + (1 if d.get("add_bat") else 0)
        per_row = max(1, int((W - 2 * M + 14) // (CW + 14)))
        for j in range(nb):
            rr, cc = divmod(j, per_row)
            x, y = M + cc * (CW + 14), y_bus + 26 + rr * (CH_B + 30)
            if j < len(d["bats"]):
                R[f"bat:{j}"] = QRectF(x, y, CW, CH_B)
            else:
                R["add_bat"] = QRectF(x, y + 12, min(CW, 120), CH_B - 24)
        for k, r in R.items():                                 # переставленные мышью — на своё место
            if k in self.pos:
                x, y = self.pos[k]
                r.moveTo(min(max(0.0, float(x)), max(0.0, W - r.width())), max(0.0, float(y)))
        return R

    # ── линии (как в Smart_BMS): сторона входа — по зазору между краями карточек, у каждой линии своя дорожка,
    #    из двух колен (гориз./верт.) — то, что не режет чужие узлы; середина колена отходит от чужих карточек ──
    @staticmethod
    def _box(r, pad=7):
        return (r.left() - pad, r.top() - pad, r.right() + pad, r.bottom() + pad)

    @staticmethod
    def _clear_v(x, ya, yb, boxes):
        """Сдвинуть вертикаль x на [ya..yb] прочь с чужих узлов."""
        lo, hi = sorted((ya, yb))
        for _ in range(4):
            hit = False
            for bx0, by0, bx1, by1 in boxes:
                if bx0 <= x <= bx1 and not (hi < by0 or lo > by1):
                    x = bx0 - 2 if (x - bx0) <= (bx1 - x) else bx1 + 2
                    hit = True
            if not hit:
                break
        return x

    @staticmethod
    def _clear_h(y, xa, xb, boxes):
        """Сдвинуть горизонталь y на [xa..xb] прочь с чужих узлов."""
        lo, hi = sorted((xa, xb))
        for _ in range(4):
            hit = False
            for bx0, by0, bx1, by1 in boxes:
                if by0 <= y <= by1 and not (hi < bx0 or lo > bx1):
                    y = by0 - 2 if (y - by0) <= (by1 - y) else by1 + 2
                    hit = True
            if not hit:
                break
        return y

    @staticmethod
    def _cross(pts, boxes):
        """Сколько чужих узлов режет ломаная."""
        n = 0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for bx0, by0, bx1, by1 in boxes:
                if abs(x1 - x0) < 1 and bx0 <= x0 <= bx1 and not (max(y0, y1) < by0 or min(y0, y1) > by1):
                    n += 1
                elif abs(y1 - y0) < 1 and by0 <= y0 <= by1 and not (max(x0, x1) < bx0 or min(x0, x1) > bx1):
                    n += 1
        return n

    @staticmethod
    def _plen(pts):
        return sum(abs(x1 - x0) + abs(y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:]))

    @staticmethod
    def _simplify(pts):
        out = []
        for pt in pts:
            if out and abs(out[-1][0] - pt[0]) < 0.5 and abs(out[-1][1] - pt[1]) < 0.5:
                continue
            if len(out) >= 2:
                (x0, y0), (x1, y1) = out[-2], out[-1]
                if (abs(x0 - x1) < 0.5 and abs(x1 - pt[0]) < 0.5) or (abs(y0 - y1) < 0.5 and abs(y1 - pt[1]) < 0.5):
                    out[-1] = pt                                   # на одной прямой — без лишнего колена
                    continue
            out.append(pt)
        return out

    @staticmethod
    def _entry(a, b):
        """Как линия из узла a входит в узел b — по ЗАЗОРУ между краями: («h», «l»/«r») или («v», «t»/«b»)."""
        gap_h = abs(b.center().x() - a.center().x()) - (a.width() + b.width()) / 2
        gap_v = abs(b.center().y() - a.center().y()) - (a.height() + b.height()) / 2
        if gap_h >= gap_v:
            return "h", ("l" if a.center().x() < b.center().x() else "r")
        return "v", ("t" if a.center().y() < b.center().y() else "b")

    def _route(self, a, b, off, boxes, axis="h", top=False):
        """Линия из a в b; off — дорожка (сдвиг точки входа вдоль стороны b). top — поле над приёмником: входит
        сверху (сбоку поля — горизонтально к своей дорожке, колено и вниз)."""
        sx, sy, tx, ty = a.center().x(), a.center().y(), b.center().x(), b.center().y()
        shw, shh, dhw, dhh = a.width() / 2, a.height() / 2, b.width() / 2, b.height() / 2
        forced = None
        if top and a.bottom() < b.top() - 6:
            lx = tx + off
            if abs(lx - sx) <= shw:                                 # прямо над дорожкой — из нижней грани
                my = self._clear_h((a.bottom() + b.top()) / 2, sx, lx, boxes)
                forced = [(sx, a.bottom()), (sx, my), (lx, my), (lx, b.top())]
            else:
                ex = sx + (shw if lx >= sx else -shw)
                forced = [(ex, sy), (lx, sy), (lx, b.top())]
            if not self._cross(forced, boxes):
                return self._simplify(forced)
        ddx, ddy = tx - sx, ty - sy
        ex = sx + (shw if ddx >= 0 else -shw)
        ax = tx - (dhw if ddx >= 0 else -dhw)
        ey2 = ty + off
        # колено ближе к приёмнику у той линии, что входит выше: слева входящие — минус дорожка, справа — плюс
        mx = self._clear_v((ex + ax) / 2 + (off if ddx < 0 else -off), sy, ey2, boxes)
        cand_h = [(ex, sy), (mx, sy), (mx, ey2), (ax, ey2)]
        ey = sy + (shh if ddy >= 0 else -shh)
        ay = ty - (dhh if ddy >= 0 else -dhh)
        ex2 = tx + off
        my = self._clear_h((ey + ay) / 2 + off, sx, ex2, boxes)
        cand_v = [(sx, ey), (sx, my), (ex2, my), (ex2, ay)]
        cands = [(cand_h, 0 if axis == "h" else 1), (cand_v, 0 if axis == "v" else 1)]
        if forced:
            cands.append((forced, -1))
        best = min(cands, key=lambda c: (self._cross(c[0], boxes), c[1], self._plen(c[0])))[0]
        return self._simplify(best)

    @staticmethod
    def _end_side(pts):
        """С какой стороны линия входит в приёмник: l / r / t / b (по последнему отрезку)."""
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        if abs(x1 - x0) < 1:
            return "t" if y0 < y1 else "b"
        return "l" if x0 < x1 else "r"

    @staticmethod
    def _lanes(entries, skip0=(), step=14.0):
        """Дорожки: линии в одну сторону приёмника разносятся на step px по порядку источников (выше / левее —
        ближе к началу стороны), так они не перекрещиваются; skip0 — стороны, где середина занята (низ инвертора —
        линия к АКБ): там левые — левее середины, правые — правее."""
        by, out = {}, {}
        for i, (key, side, coord) in enumerate(entries):
            by.setdefault(side, []).append((coord, i, key))
        for side, lst in by.items():
            lst.sort()
            if side in skip0:
                neg = [k for c, i, k in lst if c < 0]
                pos = [k for c, i, k in lst if c >= 0]
                for j, k in enumerate(reversed(neg)):
                    out[k] = -step * (j + 1)
                for j, k in enumerate(pos):
                    out[k] = step * (j + 1)
            else:
                n = len(lst)
                for j, (c, i, k) in enumerate(lst):
                    out[k] = (j - (n - 1) / 2) * step
        return out

    def _label_at(self, p, pts, text, col, kind, idx, nodes=()):
        """Подпись кабеля — туда, где её не закроет узел и другая подпись: сначала первый отрезок (если длинный),
        потом самые длинные; над / под горизонталью, справа / слева от вертикали."""
        segs = list(zip(pts, pts[1:]))
        ln = lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1])
        order = sorted(segs, key=lambda s: (-(ln(s) >= 90 and s is segs[0]), -ln(s)))
        opts = []
        for (x0, y0), (x1, y1) in order:
            if ln(((x0, y0), (x1, y1))) < 30:
                continue
            for t in (0.5, 0.3, 0.7, 0.15, 0.85):                  # по отрезку: середина, ближе к краям
                if abs(y1 - y0) < 1:
                    xm = x0 + (x1 - x0) * t
                    opts += [(xm, y0 - 13, False, False), (xm, y0 + 13, False, False)]
                else:
                    ym = y0 + (y1 - y0) * t
                    opts += [(x0 + 8, ym, True, False), (x0 - 8, ym, False, True)]
        if not opts:
            return
        busy = [r.adjusted(-3, -3, 3, 3) for r in nodes] + self.placed

        def overlap(o):
            rr = self._lab_rect(o[0], o[1], text, o[2], o[3])
            return sum(max(0.0, min(rr.right(), b.right()) - max(rr.left(), b.left()))
                       * max(0.0, min(rr.bottom(), b.bottom()) - max(rr.top(), b.top())) for b in busy)
        x, y, left, right = next((o for o in opts if overlap(o) == 0), None) or min(opts, key=overlap)
        self._label(p, x, y, text, col, kind, idx, left=left, right=right)

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
        self.placed = []                                           # подписи, уже стоящие на холсте
        W = self.width()
        R = self._layout(d, W)
        nodes = list(R.values())
        A, B = d["a"], d["b"]
        inv = R["inv"]
        iv = d["inv"]
        pv_col = "#ffd27a" if self.dark else "#b57a00"
        nports = max(1, iv["ports"]) if iv["builtin"] else 0

        def others(*keep):
            return [self._box(r) for k, r in R.items() if r not in keep]
        # ── входы инвертора: поля (каждый вход MPPT — своя линия), дом, сеть — дорожки по сторонам ──
        # 1-й проход — какой стороной линия на самом деле входит в инвертор; 2-й — по дорожкам этой стороны
        src = [((f["key"], q), R["field:" + f["key"]]) for f in A for q in range(f["k"])] + \
              [("house", R["house"]), ("grid", R["grid"])]
        ent, axes = [], {}
        for key, r in src:
            ax0 = self._entry(r, inv)[0]
            top = key not in ("house", "grid") and r.bottom() < inv.top() - 6        # поле выше — сверху
            side = self._end_side(self._route(r, inv, 0, others(r, inv), ax0, top))
            c, ic = r.center(), inv.center()
            ent.append((key, side, (c.x() - ic.x()) if side in ("t", "b") else (c.y() - ic.y())))
            axes[key] = ("v" if side in ("t", "b") else "h", top and side == "t", side)
        lane = self._lanes(ent, skip0=("b",), step=22.0)
        ports = []                                                  # (точка входа, сторона, № входа, цвет, дорожка)
        for f in A:
            r = R["field:" + f["key"]]
            for q in range(f["k"]):
                key = (f["key"], q)
                n = f["port"] + q
                col = LVL.get(f["lvl"], C_GRID) if n < max(1, nports) else _ERR
                ax, top, side = axes[key]
                pts = self._route(r, inv, lane[key], others(r, inv), ax, top)
                self._zig(p, pts, col)
                if q == 0:
                    self._label_at(p, pts, f["cable"], col, "cable_pv", f["idx"], nodes)
                ports.append((pts[-1], self._end_side(pts), n, col, lane[key]))
        hs, gr = d["house"], d["grid"]
        on = gr.get("on", True)
        pts = self._route(R["house"], inv, lane["house"], others(R["house"], inv), axes["house"][0])
        self._zig(p, list(reversed(pts)), C_HOUSE)
        pts = self._route(R["grid"], inv, lane["grid"], others(R["grid"], inv), axes["grid"][0])
        self._zig(p, pts, C_GRID, 1.8, dashed=not on, flow=1 if on else 0)
        # ── линия инвертор → шина АКБ ──
        xv = inv.center().x()
        bats = d["bats"]
        brs = [R[f"bat:{j}"] for j in range(len(bats))]
        y_bus = (min(r.top() for r in brs) - 26) if brs else inv.bottom() + 60
        t0, t1 = sorted((inv.bottom(), y_bus))

        def trunk_y(y):
            return min(max(y, t0 + 10), t1)
        bus = d["bus"]
        bus_col = LVL.get(bus["lvl"], C_BUS) if bus["lvl"] != "ok" else C_BUS
        y_from = inv.bottom() if y_bus >= inv.bottom() else inv.top()
        self._zig(p, [(xv, y_from), (xv, y_bus)], bus_col, 3.2, amp=4, flow=-1)
        # ── отдельные MPPT (приборы) — к линии «АКБ → инвертор» ──
        for b in B:
            rf, rc = R["field:" + b["key"]], R["ctl:" + b["key"]]
            col = LVL.get(b["lvl"], C_GRID)
            ax, side = self._entry(rf, rc)
            pts = self._route(rf, rc, 0, others(rf, rc), ax, top=rf.bottom() < rc.top() - 6)
            self._zig(p, pts, col)
            if rc.left() - 8 <= xv <= rc.right() + 8 and t0 <= rc.center().y() <= t1:   # стоит прямо на линии
                self._label(p, rc.center().x(), rc.bottom() + 12, b["cable2"], C_BUS, "cable_ctl", b["idx"])
                continue
            cx = rc.right() if rc.center().x() <= xv else rc.left()
            ty = trunk_y(rc.center().y())
            pts = self._simplify([(cx, rc.center().y()), ((cx + xv) / 2, rc.center().y()), ((cx + xv) / 2, ty), (xv, ty)])
            self._zig(p, pts, C_BUS, 2.4, flow=1)
            self._label(p, (cx + (pts[1][0] if len(pts) > 2 else xv)) / 2, rc.center().y() - 14, b["cable2"], C_BUS,
                        "cable_ctl", b["idx"])
        if "add_ctl" in R:
            r = R["add_ctl"]
            cx = r.right() if r.center().x() <= xv else r.left()
            ty = trunk_y(r.center().y())
            self._zig(p, self._simplify([(cx, r.center().y()), ((cx + xv) / 2, r.center().y()), ((cx + xv) / 2, ty), (xv, ty)]),
                      C_GRID, 1.2, dots=False, dashed=True)
        ly = inv.bottom() + 16 if B else (inv.bottom() + y_bus) / 2
        if not B and y_bus - inv.bottom() < 56:                    # линия короткая — подпись левее, не на шине
            self._label(p, xv - 8, ly, bus["text"], LVL.get(bus["lvl"], C_BUS), "cable_bus", 0, right=True)
        else:
            self._label(p, xv + 8, ly, bus["text"], LVL.get(bus["lvl"], C_BUS), "cable_bus", 0, left=True)
        # ── шина и сборки АКБ ──
        if brs:
            xs = [r.center().x() for r in brs] + [xv]
            p.setPen(QPen(QColor(C_BUS), 3.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(min(xs), y_bus), QPointF(max(xs), y_bus))
            self._label(p, max(xs) + 8, y_bus - 12, d.get("bus_v", ""), C_BUS, left=True)
        for j, r in enumerate(brs):
            self._zig(p, [(r.center().x(), y_bus), (r.center().x(), r.top())], C_BUS, 2.0, amp=3, flow=1)
        # ── узлы поверх линий ──
        for f in A:
            self._node(p, R["field:" + f["key"]], "☀", f["big"], f["lines"], C_PV, "field", f["idx"], f.get("tip", ""),
                       big_col=pv_col, key="field:" + f["key"])
        if "add_pv" in R:
            self._node(p, R["add_pv"], "＋", d["add_a"], ["свободный вход MPPT"], C_GRID, "add_pv", 0,
                       "Подключить поле на свободный вход MPPT инвертора", dashed=True, key="add_pv")
        for b in B:
            self._node(p, R["field:" + b["key"]], "☀", b["big"], b["lines"], C_PV, "field", b["idx"], b.get("tip", ""),
                       big_col=pv_col, key="field:" + b["key"])
            ct = b["ctl"]
            self._node(p, R["ctl:" + b["key"]], "🔀", ct["big"], ct["lines"], C_CTL, "ctl", b["idx"], ct.get("tip", ""),
                       key="ctl:" + b["key"])
        if "add_ctl" in R:
            self._node(p, R["add_ctl"], "＋", d["add_b"], ["прибор на линии АКБ"], C_GRID, "add_ctl", 0,
                       "Отдельный MPPT-контроллер (прибор) со своим полем — на линию АКБ", dashed=True, key="add_ctl")
        for j, b in enumerate(bats):
            self._node(p, brs[j], "🔋", b["big"], b["lines"], C_BAT, "bat", j, b.get("tip", ""),
                       big_col="#9fd4ff" if self.dark else "#1f6fa8", key=f"bat:{j}")
        if "add_bat" in R:
            self._node(p, R["add_bat"], "＋", "АКБ", ["ещё сборка"], C_GRID, "add_bat", 0,
                       "Другая сборка АКБ на ту же шину", dashed=True, key="add_bat")
        self._node(p, R["house"], "🏠", hs["big"], hs["lines"], C_HOUSE, "house", 0, hs.get("tip", ""), key="house")
        self._node(p, R["grid"], "🔌", gr["big"], gr["lines"], C_GRID, "grid", 0, gr.get("tip", ""), key="grid")
        self._node(p, inv, "⚡", iv["big"], iv["lines"], C_INV, "inv", 0, iv.get("tip", ""),
                   badge="MPPT" if iv["builtin"] else None, key="inv")
        # ── входы MPPT — там, где в инвертор входит линия поля ──
        f = QFont(self.font())
        f.setPointSizeF(max(6.5, f.pointSizeF() - 2.2))
        f.setBold(True)
        p.setFont(f)
        for (x, y), side, n, col, off in ports:
            bad = n >= max(1, nports)
            c = QColor(_ERR if bad else col)
            p.setPen(QPen(c, 1.6))
            p.setBrush(c)
            p.drawEllipse(QPointF(x, y), 4, 4)
            text = f"MPPT {n + 1}" + (" ✗ нет входа" if bad else "")
            tw = QFontMetrics(f).horizontalAdvance(text) + 4
            xa = x - tw - 6 if off < 0 else x + 6                    # сверху/снизу — в сторону своей дорожки
            rr = {"l": QRectF(x - tw - 6, y - 17, tw, 13), "r": QRectF(x + 6, y - 17, tw, 13),
                  "t": QRectF(xa, y - 17, tw, 13), "b": QRectF(xa, y + 4, tw, 13)}[side]
            p.setPen(c)
            p.drawText(rr, Qt.AlignCenter, text)
        h = int(max(r.bottom() for r in R.values()) + 16)
        if h != self._h:
            self._h = h
            self.setMinimumHeight(h)
            self.updateGeometry()
        p.end()

    # ── мышь: клик — выбрать, перетащить — переставить ──
    def _hit(self, pos):
        for r, kind, idx, tip, key in reversed(self.hits):
            if r.contains(QPointF(pos)):
                return kind, idx, tip, key
        return None

    def mouseMoveEvent(self, e):
        pt = e.position()
        if self.press and e.buttons() & Qt.LeftButton:
            p0, key, kind, idx, tl = self.press
            dx, dy = pt.x() - p0.x(), pt.y() - p0.y()
            if not self.dragging and abs(dx) + abs(dy) > 5:
                self.dragging = True
                QToolTip.hideText()
                self.setCursor(Qt.ClosedHandCursor)
            if self.dragging:
                x = round((tl.x() + dx) / 4) * 4                   # шаг 4 px — ровнее выставлять
                y = round((tl.y() + dy) / 4) * 4
                self.pos[key] = (max(0, x), max(0, y))
                self.update()
            return
        h = self._hit(pt)
        new = (h[0], h[1]) if h else None
        if new != self.hover:
            self.hover = new
            self.update()
        self.setCursor((Qt.OpenHandCursor if h[3] else Qt.PointingHandCursor) if h else Qt.ArrowCursor)
        if h and h[2]:
            tip = h[2] + ("\nПеретащите мышью — переставить" if h[3] and not h[0].startswith("add_") else "")
            QToolTip.showText(e.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, e):
        self.hover = None
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        h = self._hit(e.position())
        self.press = None
        self.dragging = False
        if not h:
            return
        kind, idx, _, key = h
        tl = None
        if key:
            r = next(r for r, k, i, t, kk in self.hits if kk == key)
            tl = r.topLeft()
        self.press = (e.position(), key, kind, idx, tl)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.press:
            return
        _, key, kind, idx, _ = self.press
        dragged = self.dragging
        self.press = None
        self.dragging = False
        if dragged:
            self.setCursor(Qt.OpenHandCursor)
            self.moved.emit({k: [round(v[0]), round(v[1])] for k, v in self.pos.items()})
            return
        if kind.startswith("add_"):
            self.add.emit(kind[4:])
            return
        self.select(kind, idx)
        self.picked.emit(kind, idx)

    def _reset(self, key=None):
        """Вернуть узел (или все) на место по умолчанию."""
        if key is None:
            self.pos = {}
        else:
            self.pos.pop(key, None)
        self.update()
        self.moved.emit({k: [round(v[0]), round(v[1])] for k, v in self.pos.items()})

    def _menu(self, pos):
        h = self._hit(pos)
        d = self.data or {}
        m = QMenu(self)
        if h:
            kind, idx, _, key = h
            if not kind.startswith("add_"):
                m.addAction("⚙ Настроить", lambda: (self.select(kind, idx), self.picked.emit(kind, idx)))
                if kind in ("field", "ctl"):
                    what = "поле" if kind == "field" else "MPPT с его полем"
                    m.addAction(f"⧉ Копия ({'ещё такое же поле' if kind == 'field' else 'ещё такой же MPPT с полем'})",
                                lambda: self.clone.emit("field", idx))
                    ok = idx > 0 or bool(d.get("rm_main"))
                    a = m.addAction(f"🗑 Убрать {what}" if ok else "🗑 Убрать — это единственное поле", lambda: self.remove.emit("field", idx))
                    a.setEnabled(ok)
                if kind == "bat":
                    ok = idx > 0 or bool(d.get("rm_bat0"))
                    a = m.addAction("🗑 Убрать сборку" if ok else "🗑 Убрать — это единственная сборка", lambda: self.remove.emit("bat", idx))
                    a.setEnabled(ok)
            if key:
                a = m.addAction("↺ Вернуть на место", lambda: self._reset(key))
                a.setEnabled(key in self.pos)
            m.addSeparator()
        a = m.addAction("＋ Поле на свободный вход MPPT инвертора", lambda: self.add.emit("pv"))
        a.setEnabled(bool(d.get("add_a")))
        a = m.addAction("＋ Отдельный MPPT (прибор) с полем — к линии АКБ", lambda: self.add.emit("ctl"))
        a.setEnabled(bool(d.get("add_b")))
        a = m.addAction("＋ Ещё сборка АКБ", lambda: self.add.emit("bat"))
        a.setEnabled(bool(d.get("add_bat")))
        m.addSeparator()
        a = m.addAction("↺ Расставить всё автоматически", lambda: self._reset())
        a.setEnabled(bool(self.pos))
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
