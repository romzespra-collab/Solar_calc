"""mod_wx_draw.py  v1.4.0
Отрисовка погоды: объёмные значки (Солнце, Луна, облака, дождь, снег, гроза, туман) и экран погоды
(сейчас + восход/закат/Луна + по часам + по дням). Цвета — из темы программы.

Журнал:
v1.4.0: перенесено из Smart_BMS 4.81 (weather_window.py); восход/закат, Луна и ночь у значков —
        по mod_astro для места и пояса станции; тёмная/светлая тема.
"""

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF,
                           QRadialGradient)
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import mod_astro as A
from . import mod_weather as W

BASE_W = 700
BASE_H = 524


# ---------- значки (объёмные: градиенты, блики, капли, снежинки) ----------

def _ca(h, a):
    c = QColor(h)
    c.setAlpha(max(0, min(255, int(a))))
    return c


def _sun(p, cx, cy, r):
    c = QPointF(cx, cy)
    p.setPen(Qt.NoPen)
    g = QRadialGradient(c, r * 2.0)
    g.setColorAt(0, _ca("#ffd75e", 90))
    g.setColorAt(1, _ca("#ffd75e", 0))
    p.setBrush(QBrush(g))
    p.drawEllipse(c, r * 2.0, r * 2.0)
    # лучи — сужающиеся треугольники
    rg = QRadialGradient(c, r * 1.75)
    rg.setColorAt(0.55, QColor("#ffcf3a"))
    rg.setColorAt(1, _ca("#ffab1a", 60))
    p.setBrush(QBrush(rg))
    for k in range(12):
        a = k * math.pi / 6
        ln = r * (1.72 if k % 2 == 0 else 1.45)
        w = 0.17
        p.drawPolygon(QPolygonF([
            QPointF(cx + math.cos(a - w) * r * 1.08,
                    cy + math.sin(a - w) * r * 1.08),
            QPointF(cx + math.cos(a) * ln, cy + math.sin(a) * ln),
            QPointF(cx + math.cos(a + w) * r * 1.08,
                    cy + math.sin(a + w) * r * 1.08)]))
    dg = QRadialGradient(QPointF(cx - r * 0.35, cy - r * 0.35), r * 1.25)
    dg.setColorAt(0, QColor("#fffbe0"))
    dg.setColorAt(0.45, QColor("#ffe066"))
    dg.setColorAt(1, QColor("#f7a21b"))
    p.setPen(QPen(_ca("#f08c00", 170), max(0.8, r * 0.05)))
    p.setBrush(QBrush(dg))
    p.drawEllipse(c, r, r)


def _moon(p, cx, cy, r):
    c = QPointF(cx, cy)
    p.setPen(Qt.NoPen)
    g = QRadialGradient(c, r * 1.8)
    g.setColorAt(0, _ca("#b9cbe8", 70))
    g.setColorAt(1, _ca("#b9cbe8", 0))
    p.setBrush(QBrush(g))
    p.drawEllipse(c, r * 1.8, r * 1.8)
    full = QPainterPath()
    full.addEllipse(c, r, r)
    cut = QPainterPath()
    cut.addEllipse(QPointF(cx + r * 0.62, cy - r * 0.38), r * 0.95, r * 0.95)
    mg = QLinearGradient(cx - r, cy - r, cx + r * 0.3, cy + r)
    mg.setColorAt(0, QColor("#f3f7ff"))
    mg.setColorAt(1, QColor("#a9bddc"))
    p.fillPath(full.subtracted(cut), QBrush(mg))
    p.setBrush(_ca("#8fa3c4", 150))                  # «моря»
    for dx, dy, rr in ((-0.45, 0.1, 0.13), (-0.2, 0.5, 0.1), (-0.6, -0.3, 0.08)):
        p.drawEllipse(QPointF(cx + dx * r, cy + dy * r), rr * r, rr * r)


def _cloud_path(cx, cy, r):
    """Контур облака: плоское дно + три клуба (единый путь)."""
    path = QPainterPath()
    path.addRoundedRect(QRectF(cx - r, cy - r * 0.1, 2 * r, r * 0.62),
                        r * 0.31, r * 0.31)
    for dx, dy, rr in ((-0.48, -0.08, 0.42), (0.08, -0.36, 0.6),
                       (0.62, -0.02, 0.4)):
        one = QPainterPath()
        one.addEllipse(QPointF(cx + dx * r, cy + dy * r), rr * r, rr * r)
        path = path.united(one)
    return path


def _cloud(p, cx, cy, r, style="light"):
    """style: light / grey / rain / storm / snow / night."""
    pal = {"light": ("#ffffff", "#e9eef5", "#b9c5d6"),
           "grey": ("#dde3eb", "#b6c0cd", "#8894a6"),
           "rain": ("#c9d6e8", "#98abc4", "#62789a"),
           "storm": ("#9aa5b6", "#6d788b", "#3f4858"),
           "snow": ("#ffffff", "#e3ebf6", "#aebfd6"),
           "night": ("#aeb9c8", "#8a97aa", "#5b687c")}[style]
    path = _cloud_path(cx, cy, r)
    top, bot = cy - r * 1.0, cy + r * 0.52
    p.setPen(Qt.NoPen)
    sh = QPainterPath(path)                          # тень под облаком
    sh.translate(r * 0.05, r * 0.1)
    p.fillPath(sh, _ca("#000000", 60))
    g = QLinearGradient(0, top, 0, bot)
    g.setColorAt(0, QColor(pal[0]))
    g.setColorAt(0.55, QColor(pal[1]))
    g.setColorAt(1, QColor(pal[2]))
    p.fillPath(path, QBrush(g))
    p.save()
    p.setClipPath(path)
    hg = QRadialGradient(QPointF(cx - r * 0.05, cy - r * 0.62), r * 0.7)
    hg.setColorAt(0, _ca("#ffffff", 150))
    hg.setColorAt(1, _ca("#ffffff", 0))
    p.setBrush(QBrush(hg))
    p.drawEllipse(QPointF(cx - r * 0.05, cy - r * 0.62), r * 0.7, r * 0.7)
    p.restore()
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(_ca(pal[2], 170), max(0.7, r * 0.04)))
    p.drawPath(path)


def _drop(p, x, y, s):
    """Капля-слеза, наклонённая по ветру."""
    path = QPainterPath(QPointF(x + s * 0.35, y - s))
    path.cubicTo(QPointF(x + s * 0.7, y - s * 0.1), QPointF(x + s * 0.55,
                                                            y + s * 0.55),
                 QPointF(x, y + s * 0.55))
    path.cubicTo(QPointF(x - s * 0.55, y + s * 0.55), QPointF(x - s * 0.55,
                                                              y - s * 0.05),
                 QPointF(x + s * 0.35, y - s))
    g = QLinearGradient(x, y - s, x, y + s * 0.6)
    g.setColorAt(0, QColor("#bfe0ff"))
    g.setColorAt(1, QColor("#3d8fe0"))
    p.fillPath(path, QBrush(g))


def _flake(p, x, y, s):
    p.setPen(QPen(QColor("#eef5ff"), max(1.0, s * 0.22), Qt.SolidLine,
                  Qt.RoundCap))
    for k in range(3):
        a = k * math.pi / 3
        dx, dy = math.cos(a) * s, math.sin(a) * s
        p.drawLine(QPointF(x - dx, y - dy), QPointF(x + dx, y + dy))
    p.setPen(Qt.NoPen)


def _bolt(p, x, y, s):
    path = QPainterPath(QPointF(x + s * 0.25, y))
    for px, py in ((-0.35, 1.0), (0.05, 1.0), (-0.25, 1.9), (0.55, 0.7),
                   (0.12, 0.7), (0.4, 0.0)):
        path.lineTo(QPointF(x + px * s, y + py * s))
    path.closeSubpath()
    g = QRadialGradient(QPointF(x, y + s), s * 1.6)
    g.setColorAt(0, _ca("#ffe45c", 110))
    g.setColorAt(1, _ca("#ffe45c", 0))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(g))
    p.drawEllipse(QPointF(x, y + s), s * 1.6, s * 1.6)
    lg = QLinearGradient(x, y, x, y + 1.9 * s)
    lg.setColorAt(0, QColor("#fff3a0"))
    lg.setColorAt(1, QColor("#ffb300"))
    p.fillPath(path, QBrush(lg))
    p.setPen(QPen(_ca("#e08a00", 200), max(0.6, s * 0.06)))
    p.drawPath(path)
    p.setPen(Qt.NoPen)


def wx_icon(p, cx, cy, r, code, night):
    p.save()
    p.setRenderHint(QPainter.Antialiasing, True)
    try:
        _wx_icon(p, float(cx), float(cy), float(r), int(code or 0), night)
    finally:
        p.restore()


def _wx_icon(p, cx, cy, r, code, night):
    drizz = 51 <= code <= 57
    rain = (61 <= code <= 67) or (80 <= code <= 82)
    snow = (71 <= code <= 77) or code in (85, 86)
    storm = code >= 95
    few = code in (1, 2)
    clear = code == 0
    fog = code in (45, 48)
    body = (_moon if night else _sun)
    if clear:
        body(p, cx, cy, r * 0.62)
        return
    if few:
        body(p, cx + r * 0.38, cy - r * 0.34, r * 0.42)
        _cloud(p, cx - r * 0.12, cy + r * 0.3, r * 0.62,
               "night" if night else "light")
        return
    front = ("storm" if storm else "rain" if (rain or drizz) else
             "snow" if snow else "night" if night else "grey")
    back = "storm" if storm else "night" if night else "grey"
    fx, fy, fr = cx + r * 0.08, cy - r * 0.02, r * 0.66
    if code == 3 or fog or not (rain or drizz or snow or storm):
        _cloud(p, cx - r * 0.38, cy - r * 0.34, r * 0.46, back)
    else:
        _cloud(p, cx - r * 0.34, cy - r * 0.4, r * 0.44, back)
    _cloud(p, fx, fy, fr, front)
    by = fy + fr * 0.62
    if rain or drizz:
        n = 3 if rain else 2
        s = r * (0.17 if rain else 0.12)
        for i in range(n):
            x = fx + (i - (n - 1) / 2) * fr * 0.62
            _drop(p, x, by + s * 1.4 + (i % 2) * s * 0.9, s)
        if code in (65, 67, 82):
            _drop(p, fx + fr * 0.3, by + s * 3.4, s * 0.8)
            _drop(p, fx - fr * 0.35, by + s * 3.2, s * 0.8)
    if snow:
        s = r * 0.15
        for _i, (dx, dy) in enumerate(((-0.6, 0.35), (0.0, 0.7), (0.6, 0.35))):
            _flake(p, fx + dx * fr, by + dy * fr, s)
    if storm:
        _bolt(p, fx - fr * 0.05, by - fr * 0.1, fr * 0.5)
    if fog:
        p.setPen(QPen(_ca("#b8c2d0", 220), max(1.2, r * 0.1), Qt.SolidLine,
                      Qt.RoundCap))
        for i in range(3):
            y = by + fr * 0.2 + i * fr * 0.3
            x0 = fx - fr * (0.9 - 0.2 * (i % 2))
            p.drawLine(QPointF(x0, y), QPointF(fx + fr * (0.9 - 0.3 * (i % 2)),
                                               y))
        p.setPen(Qt.NoPen)


# ---------- экран погоды ----------

class WeatherView:
    """Отрисовка экрана погоды (логическая база 700×524) в цветах темы программы."""
    @staticmethod
    def paint(p, snap, pal):
        TXT, DIM, LINE, BLUE = pal["text"], pal["muted"], pal["line"], pal["accent"]
        light = QColor(pal["panel"]).lightness() > 128

        def tcol(t):                     # на светлом фоне — темнее, чтобы читалось
            c = W.temp_color(t)
            return c.darker(165) if light else c
        p.setRenderHint(QPainter.Antialiasing, True)

        def text(x, y, s, col, px, bold=False, align="l"):
            f = QFont("Segoe UI"); f.setPixelSize(px); f.setBold(bold)
            p.setFont(f); p.setPen(QColor(col))
            fm = p.fontMetrics(); w = fm.horizontalAdvance(s)
            if align == "c":
                x -= w // 2
            elif align == "r":
                x -= w
            p.drawText(int(x), int(y), s); return w

        def hline(y):
            p.setPen(QPen(QColor(LINE), 1)); p.drawLine(8, y, BASE_W - 8, y)

        def vline(x, y0, y1):
            p.setPen(QPen(QColor(LINE), 1)); p.drawLine(x, y0, x, y1)

        if not snap["on"]:
            text(BASE_W // 2, 260, "погода выключена (кнопка «Погода» вверху)", DIM, 18, align="c"); return
        if not snap["ok"]:
            msg = "нет данных о погоде"
            if snap.get("err"):
                msg += " — " + snap["err"][:70]
            text(BASE_W // 2, 250, msg, DIM, 16, align="c")
            text(BASE_W // 2, 280, "место: %s %.2f, %.2f · обновится само" % (snap.get("city") or "", snap["lat"], snap["lon"]),
                 DIM, 13, align="c"); return

        night = snap["sun_alt"] < -0.833 if snap.get("sun_alt") is not None else not snap["is_day"]
        code = snap["code"]
        # ===== ТЕКУЩАЯ =====
        wx_icon(p, 66, 86, 50, code, night)
        t = snap["temp"]
        if t is not None:
            tv = int(math.floor(t + 0.5)); tc = tcol(t)
            sg = "-" if tv < 0 else "+"
            x = 150
            wsg = text(x, 108, sg, tc.name(), 40, bold=True)
            f = QFont("Segoe UI"); f.setPixelSize(64); f.setBold(True); p.setFont(f)
            num = str(abs(tv)); p.setPen(tc); p.drawText(int(x + wsg + 4), 116, num)
            wn = p.fontMetrics().horizontalAdvance(num)
            ex = x + wsg + 4 + wn + 10
            p.setPen(QPen(tc, 2)); p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(ex), 62, 8, 8)
            text(ex + 14, 96, "C", tc.name(), 22)
        text(150, 140, W.wx_word(code), TXT, 18)
        if snap["feels"] is not None:
            text(150, 162, "ощущается %+d°" % int(math.floor(snap["feels"] + 0.5)), DIM, 14)
        text(66, 140, snap["city"], TXT, 14, align="c")
        text(66, 158, "%.2f, %.2f" % (snap["lat"], snap["lon"]), DIM, 12, align="c")
        # правая колонка — детали
        lx, vr, yy = 430, BASE_W - 16, 52
        def row(lab, val, vc):
            nonlocal yy
            text(lx, yy, lab, DIM, 15); text(vr, yy, val, vc, 16, align="r"); yy += 28
        def pct(v):                      # нет значения -> «—», а не TypeError
            return "—" if v is None else "%d %%" % v
        row("влажность", pct(snap["hum"]), TXT)
        row("давление", "—" if snap["press"] is None
            else "%d мм" % int(round(snap["press"] * 0.750062)), TXT)
        if snap["wind"] is not None:
            row("ветер", "%d м/с %s" % (int(round(snap["wind"])), W.wind_word(snap["wind_dir"])), TXT)
        else:
            row("ветер", "—", TXT)
        row("облачность", pct(snap["cloud"]), TXT)
        row("осадки", pct(snap["pop"]),
            BLUE if (snap["pop"] or 0) >= 50 else TXT)

        # ===== АСТРО (восход/закат/день/луна) =====
        hline(180)
        rs = snap.get("rise_set")
        ax = 16
        if rs:
            r, s = rs
            dl = s - r
            r, s = r % 1440, s % 1440            # пояс города ≠ пояс ПК
            ax += text(ax, 204, "восход %02d:%02d" % (r // 60, r % 60), TXT, 15) + 26
            ax += text(ax, 204, "закат %02d:%02d" % (s // 60, s % 60), TXT, 15) + 26
            ax += text(ax, 204, "день %dч %02dм" % (dl // 60, dl % 60), DIM, 15) + 26
        ph, il = snap.get("moon") or (0.0, 0.0)
        text(ax, 204, "луна: %s (%d%%)" % (A.phase_name(ph), int(il * 100 + 0.5)), DIM, 15)

        # ===== ПО ЧАСАМ =====
        hline(220)
        text(16, 240, "По часам", DIM, 14)
        hrs = snap["hourly"][:8]
        if hrs:
            n = len(hrs); x0 = 8; band = (BASE_W - 16) / n
            for i, hh in enumerate(hrs):
                cx = int(x0 + band * i + band / 2)
                if i > 0:
                    vline(int(x0 + band * i), 250, 336)
                text(cx, 266, "%02d:00" % hh["hh"], TXT, 13, align="c")
                wx_icon(p, cx, 290, 15, hh["code"], hh.get("night", hh["hh"] < 6 or hh["hh"] >= 21))
                text(cx, 322, "%+d" % hh["t"], tcol(hh["t"]).name(), 14, bold=True, align="c")
                if hh["pop"] >= 20:
                    text(cx, 336, "%d%%" % hh["pop"], BLUE, 12, align="c")
        else:
            text(BASE_W // 2, 300, "нет почасовых данных", DIM, 14, align="c")

        # ===== ПО ДНЯМ =====
        hline(348)
        days = snap["daily"][:6]
        if days:
            n = len(days); x0 = 8; band = (BASE_W - 16) / n
            for i, dd in enumerate(days):
                cx = int(x0 + band * i + band / 2)
                if i > 0:
                    vline(int(x0 + band * i), 358, 512)
                dn = "сегодня" if i == 0 else ("завтра" if i == 1 else W.dow_word(dd["dow"]))
                text(cx, 372, dn, TXT if i == 0 else DIM, 14, align="c")
                if dd["dd"]:
                    text(cx, 390, "%02d.%02d" % (dd["dd"], dd["mm"]), DIM, 12, align="c")
                wx_icon(p, cx, 425, 21, dd["code"], False)
                mx, mn = "%+d" % dd["max"], "%+d" % dd["min"]
                f = QFont("Segoe UI"); f.setPixelSize(16); f.setBold(True); p.setFont(f)
                wmx = p.fontMetrics().horizontalAdvance(mx)
                f2 = QFont("Segoe UI"); f2.setPixelSize(13); p.setFont(f2)
                wsl = p.fontMetrics().horizontalAdvance(" / ")
                wmn = p.fontMetrics().horizontalAdvance(mn)
                tot = wmx + wsl + wmn; xx = cx - tot // 2
                p.setFont(f); p.setPen(tcol(dd["max"])); p.drawText(int(xx), 470, mx)
                p.setFont(f2); p.setPen(QColor(DIM)); p.drawText(int(xx + wmx), 470, " / ")
                p.setPen(tcol(dd["min"])); p.drawText(int(xx + wmx + wsl), 470, mn)
                if dd["pop"] >= 20:
                    text(cx, 492, "ос. %d%%" % dd["pop"], BLUE if dd["pop"] >= 50 else DIM, 12, align="c")
        else:
            text(BASE_W // 2, 430, "нет прогноза по дням", DIM, 14, align="c")


class WeatherPane(QWidget):
    """Экран погоды: рисует WeatherView в масштабе, данные и палитру даёт provider() → (snap, pal)."""

    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def heightForWidth(self, w):
        return int(w * BASE_H / BASE_W)

    def hasHeightForWidth(self):
        return True

    def paintEvent(self, _e):
        p = QPainter(self)
        try:
            snap, pal = self.provider()
            p.fillRect(self.rect(), QColor(pal["panel"]))
            w, h = self.width(), self.height()
            k = min(w / BASE_W, h / BASE_H)
            p.save()
            p.translate((w - BASE_W * k) / 2.0, (h - BASE_H * k) / 2.0)
            p.scale(k, k)
            try:
                WeatherView.paint(p, snap, pal)
            finally:
                p.restore()
        except Exception as e:                    # ошибка рисования не роняет программу
            p.setPen(QColor("#e05555"))
            p.drawText(24, 44, "Погода: ошибка отрисовки — %s" % e)
        finally:
            p.end()
