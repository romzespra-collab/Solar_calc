# -*- coding: utf-8 -*-
"""mod_sky.py  v1.4.0
«Небо» — анимированная сцена: путь Солнца за день (сегодня / 22 июня / 22 декабря) над рядом панелей,
Солнце, Луна, звёзды и созвездия на своих местах, облака/дождь/снег/гроза по погоде, небо по высоте
Солнца, холмы, дерево, дом по сезону. Внизу — восход/закат, долгота дня, угол луча к панели, Луна, погода.

Согласовано со станцией: место, часовой пояс (с летним временем ЕС), наклон и азимут панелей — из
настроек; Солнце — та же формула, что в расчёте выработки (mod_astro → mod_sun); погода — mod_weather.
Логическая база 640×480 (4:3), масштабируется под окно, на широком экране сцена тянется.

Журнал:
v1.4.0: перенесено из Smart_BMS 4.81 (sky_view.py): данные — provider() станции, азимут панелей,
        пояс станции вместо пояса ПК.
"""
from __future__ import annotations

import datetime as _dt
import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QImage,
                           QLinearGradient,
                           QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
                           QRadialGradient, QTransform)
from PySide6.QtWidgets import QSizePolicy, QWidget

from . import mod_astro as A
from . import mod_stars as SC
from . import mod_weather as W
from .mod_base import log
from .mod_wx_draw import wx_icon

BASE_W, BASE_H = 640, 480
SCENE_H = 388          # высота сцены (ниже — панель текста, 92)
HORIZON = 296          # линия горизонта (низ дуг)
FONT = "Segoe UI"
SHOW_NAMES = True       # Настройки → Погода: линии и названия созвездий
FORCE_STARS = True      # Настройки → Погода: звёзды ночью всегда (облачность не прячет)
# Настройки → Погода: «Небо: анимация». Выкл. — неподвижная картинка,
# перерисовка раз в 30 с (Солнце/Луна/звёзды по времени) — почти без CPU
ANIMATE = True
# отдельные галочки анимации (Настройки → Погода); ANIMATE = любая из них
ANIM_CLOUDS = True      # облака, дым из трубы, дождь/снег, молния
ANIM_TREE = True        # качание дерева, листопад
ANIM_PANELS = True      # протоны: панели → щитовая → дом
ANIM_STARS = True       # мерцание звёзд
# Широкая сцена: на мониторе 16:9 / 16:10 (полный экран) небо, холмы и земля
# тянутся на всю ширину, а дом/панели/дерево/текст остаются в центральной
# части 640 точек. _X0.._X1 — видимые границы сцены в базовых координатах
# (ставятся в paintEvent; 0..BASE_W — прежний вид 4:3).
_X0, _X1 = 0.0, float(BASE_W)
# сдвиги «к краям» на широкой сцене: дерево — к левому, дом — к правому
# (в 4:3 оба 0 — прежний вид)
_TS, _HS = 0.0, 0.0


# ------------------------------------------------------------ астрономия
def incidence(alt, az, tilt, panel_az=180.0):
    """Угол между лучом и нормалью панели (0° — луч в лоб)."""
    return A.incidence(alt, az, tilt, panel_az)


def _mix(a: QColor, b: QColor, f: float) -> QColor:
    f = max(0.0, min(1.0, f))
    return QColor(int(a.red() + (b.red() - a.red()) * f),
                  int(a.green() + (b.green() - a.green()) * f),
                  int(a.blue() + (b.blue() - a.blue()) * f),
                  int(a.alpha() + (b.alpha() - a.alpha()) * f))


_NOISE = {}


def _dither(p):
    """Зерно ±1 уровень яркости поверх неба — убирает «кольца» (полосы)
    у плавных градиентов на тёмном фоне. Рисуется 1:1 к пикселям экрана."""
    try:
        dpr = float(p.device().devicePixelRatioF())
        dev_w, dev_h = p.device().width(), p.device().height()
    except Exception:                                   # noqa: BLE001
        return
    pm = _NOISE.get(dpr)
    if pm is None:
        rnd = random.Random(5)
        img = QImage(128, 128, QImage.Format_ARGB32_Premultiplied)
        for y in range(128):
            for x in range(128):
                v = rnd.random()
                a = int(rnd.random() * 9)            # 0..8 из 255
                img.setPixel(x, y, (a << 24) | ((a if v > 0.5 else 0) * 0x010101))
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        _NOISE[dpr] = pm
    p.save()
    p.resetTransform()
    p.drawTiledPixmap(QRectF(0, 0, dev_w / dpr, dev_h / dpr), pm)
    p.restore()


# моря видимой стороны Луны: (x, y, rx, ry) в долях радиуса, север вверху
_MARIA = ((-0.36, -0.40, 0.30, 0.24),   # Дождей
          (0.18, -0.40, 0.17, 0.15),    # Ясности
          (0.30, -0.08, 0.21, 0.17),    # Спокойствия
          (0.64, -0.24, 0.12, 0.10),    # Кризисов
          (-0.58, 0.02, 0.26, 0.40),    # Океан Бурь
          (-0.16, 0.34, 0.17, 0.13),    # Облаков
          (0.52, 0.14, 0.13, 0.14),     # Изобилия
          (0.34, 0.30, 0.09, 0.09),     # Нектара
          (-0.46, 0.44, 0.09, 0.08),    # Влажности
          (0.02, -0.66, 0.30, 0.07))    # Холода
_MOON_CACHE = {}


def _moon_sprite(phase, overcast, side):
    """Картинка Луны side×side пикселей для фазы phase (0 — новолуние)."""
    side = max(8, int(side))
    key = (round(phase, 3), overcast, side)
    img = _MOON_CACHE.get(key)
    if img is not None:
        return img
    if len(_MOON_CACHE) > 12:
        _MOON_CACHE.clear()
    R0 = side / 2.0
    C = QPointF(R0, R0)
    rr = R0 - 0.6
    # --- текстура полного диска
    tex = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
    tex.fill(Qt.transparent)
    q = QPainter(tex)
    q.setRenderHint(QPainter.Antialiasing)
    disk = QPainterPath()
    disk.addEllipse(C, rr, rr)
    q.setClipPath(disk)
    g = QRadialGradient(QPointF(R0 * 0.82, R0 * 0.78), rr * 1.35)
    g.setColorAt(0, QColor("#f7f5ea"))
    g.setColorAt(0.7, QColor("#e2e1d6"))
    g.setColorAt(1, QColor("#c7c8bd"))
    q.fillRect(QRectF(0, 0, side, side), g)
    q.setPen(Qt.NoPen)
    for mx, my, mrx, mry in _MARIA:          # моря — мягкие тёмные пятна
        cc = QPointF(R0 + mx * rr, R0 + my * rr)
        q.save()
        q.translate(cc)                       # градиент — в СВОИХ координатах
        q.scale(1.0, mry / mrx)
        mg = QRadialGradient(QPointF(0, 0), mrx * rr)
        mg.setColorAt(0, _c("#6c726e", 190))
        mg.setColorAt(0.6, _c("#777c77", 150))
        mg.setColorAt(1, _c("#8f938c", 0))
        q.setBrush(QBrush(mg))
        q.drawEllipse(QPointF(0, 0), mrx * rr, mrx * rr)
        q.restore()
    rnd = random.Random(42)                  # кратеры: тень + светлая кромка
    for _ in range(30):
        a = rnd.random() * 6.2832
        d = rnd.random() ** 0.6 * 0.88
        cr = rr * (0.012 + rnd.random() ** 3 * 0.05)
        cc = QPointF(R0 + math.cos(a) * d * rr, R0 + math.sin(a) * d * rr)
        q.setBrush(_c("#6f736f", 42))           # чаша (тень)
        q.drawEllipse(cc, cr, cr)
        q.setBrush(_c("#ffffff", 34))           # освещённый край
        q.drawEllipse(QPointF(cc.x() - cr * 0.3, cc.y() - cr * 0.3),
                      cr * 0.6, cr * 0.6)
    ty = QPointF(R0 - 0.10 * rr, R0 + 0.70 * rr)   # Тихо и его лучи
    q.setPen(QPen(_c("#ffffff", 38), max(0.6, rr * 0.018)))
    for k in range(12):
        a = k * 0.5236 + 0.2
        q.drawLine(ty, QPointF(ty.x() + math.cos(a) * rr * 0.8,
                               ty.y() + math.sin(a) * rr * 0.8))
    q.setPen(Qt.NoPen)
    q.setBrush(_c("#ffffff", 150))
    q.drawEllipse(ty, rr * 0.035, rr * 0.035)
    q.setBrush(_c("#ffffff", 120))
    q.drawEllipse(QPointF(R0 - 0.26 * rr, R0 - 0.06 * rr), rr * 0.03,
                  rr * 0.03)                  # Коперник
    lg = QRadialGradient(C, rr)               # потемнение к краю диска
    lg.setColorAt(0, _c("#000000", 0))
    lg.setColorAt(0.72, _c("#000000", 0))
    lg.setColorAt(1, _c("#20242c", 120))
    q.setBrush(QBrush(lg))
    q.drawEllipse(C, rr, rr)
    q.end()
    # --- освещённая часть (фаза) и пепельный свет
    k = math.cos(2 * math.pi * phase)         # 1 новолуние … −1 полнолуние
    waxing = phase < 0.5
    half = QPainterPath()
    rect = QRectF(C.x() - rr, C.y() - rr, 2 * rr, 2 * rr)
    half.moveTo(C.x(), C.y() - rr)
    half.arcTo(rect, 90, -180 if waxing else 180)
    half.closeSubpath()
    ell = QPainterPath()
    ex = max(0.5, abs(k) * rr)                 # у четверти эллипс не вырождать
    ell.addEllipse(QRectF(C.x() - ex, C.y() - rr, 2 * ex, 2 * rr))
    lit = half.united(ell) if k < 0 else half.subtracted(ell)
    img = QImage(side, side, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    q = QPainter(img)
    q.setRenderHint(QPainter.Antialiasing)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setPen(Qt.NoPen)
    q.setBrush(_c("#283042", 225))            # тёмная часть диска
    q.drawPath(disk)
    q.save()
    q.setClipPath(disk.subtracted(lit))
    q.setOpacity(0.13)                        # пепельный свет — море видно
    q.drawImage(0, 0, tex)
    q.restore()
    q.save()
    q.setClipPath(lit)
    q.setOpacity(0.55 if overcast else 1.0)
    q.drawImage(0, 0, tex)
    q.restore()
    if 0.02 < phase < 0.98 and abs(k) < 0.985:   # мягкий терминатор
        q.save()
        # граница свет/тень — дуга эллипса с одной стороны диска: у серпа
        # там же, где освещённая половина, у «почти полной» — с другой
        right = waxing == (k > 0)
        side_clip = QPainterPath()
        side_clip.addRect(QRectF(C.x() if right else 0, 0, R0 * 2 if right
                                 else C.x(), side))
        q.setClipPath(lit.intersected(side_clip))
        q.setBrush(Qt.NoBrush)
        for wdt, al in ((rr * 0.16, 40), (rr * 0.08, 60)):
            q.setPen(QPen(_c("#283042", al), wdt))
            q.drawPath(ell)
        q.restore()
    q.end()
    _MOON_CACHE[key] = img
    return img


def _c(hexs, a=255):
    c = QColor(hexs)
    c.setAlpha(max(0, min(255, int(a))))
    return c


# ------------------------------------------------------------ виджет
class SkyView(QWidget):
    def __init__(self, provider=None, parent=None):
        super().__init__(parent)
        self.provider = provider         # → dict: lat, lon, tilt, aspect, tz, dst, city + погода
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._t0 = time.monotonic()
        rnd = random.Random(7)
        self._drops = [(rnd.random(), rnd.random(), 0.6 + rnd.random() * 0.8)
                       for _ in range(140)]
        # фон — слабые звёзды (не катализ), яркие — реальные из star_catalog
        self._stars = [(rnd.random() * BASE_W, rnd.random() * (HORIZON - 20),
                        0.35 + rnd.random() * 0.45, rnd.random() * 6.3)
                       for _ in range(90)]
        for _ in SC.STARS:               # (бывш. фазы мерцания) — та же
            rnd.random()                 # последовательность для травы
        self._sky_key = None
        self._sky_pos = {}
        self._grass = [(rnd.random() * BASE_W, HORIZON + 6 + rnd.random() *
                        (SCENE_H - HORIZON - 8), rnd.random())
                       for _ in range(260)]
        self._arcs_key = None
        self._arcs = {}
        self._lay_key = None             # кэш слоёв (фон / передний / дерево)
        self._lay = {}
        self._sprites = {}               # облака-спрайты
        self._timer = QTimer(self)
        self._timer.setInterval(66)      # ~15 к/с — дождь/лучи/облака
        self._timer.timeout.connect(self.update)

    def showEvent(self, e):
        super().showEvent(e)
        self.apply_anim()

    def apply_anim(self):
        """Частота перерисовки по настройке «Небо: анимация»."""
        if getattr(self, "stream_card", False):
            # карточка передатчика: кадры снимает сам передатчик с частотой
            # потока — свой таймер не нужен (двойная отрисовка)
            self._timer.stop()
            return
        self._timer.setInterval(66 if ANIMATE else 30000)
        if self.isVisible():
            self._timer.start()
            self.update()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._timer.stop()               # скрыта — не тратим CPU

    def _snap(self):
        try:
            return self.provider() if self.provider else {}
        except Exception:                               # noqa: BLE001
            return {}

    def _zone(self):
        st = self._snap()
        return (st.get("tz", 2), st.get("dst", True))

    def _when(self):
        return A.station_now(self._zone())

    # проекция: азимут 55..305° -> x, высота 0..68° -> y над горизонтом
    @staticmethod
    def _xy(alt, az):
        x = _X0 + 40 + (az - 55) / 250.0 * ((_X1 - _X0) - 80)
        y = HORIZON - max(-8.0, alt) / 68.0 * (HORIZON - 34)
        return QPointF(x, y)

    def _arc(self, lat, lon, day: _dt.date):
        pts = []
        zone = self._zone()
        for m in range(0, 1440, 6):
            t = _dt.datetime(day.year, day.month, day.day, m // 60, m % 60)
            alt, az = A.sun_pos(lat, lon, t, zone)
            if alt > -1:
                pts.append(self._xy(alt, az))
        return pts

    def _get_arcs(self, lat, lon, today):
        key = (round(lat, 3), round(lon, 3), today, round(_X0), self._zone())
        if key != self._arcs_key:
            y = today.year
            self._arcs = {"today": self._arc(lat, lon, today),
                          "jun": self._arc(lat, lon, _dt.date(y, 6, 22)),
                          "dec": self._arc(lat, lon, _dt.date(y, 12, 22))}
            self._arcs_key = key
        return self._arcs

    # ---------------------------------------------------- рисование
    def paintEvent(self, _e):
        p = QPainter(self)
        try:
            p.fillRect(self.rect(), QColor("#0b0e12"))
            global _X0, _X1, _TS, _HS
            w, h = max(1, self.width()), max(1, self.height())
            bw = max(float(BASE_W), BASE_H * w / h)      # ширина сцены
            ext = (bw - BASE_W) / 2.0
            _X0, _X1 = -ext, BASE_W + ext
            _TS = min(0.0, _X0 + 6)                      # дерево у левого края
            _HS = max(0.0, ext - 48)                     # дом у правого края
            k = min(w / bw, h / BASE_H)
            ox = (w - bw * k) / 2 + ext * k              # где базовый x = 0
            oy = (h - BASE_H * k) / 2
            self._frame(p, k, ox, oy)
        except Exception as e:                          # noqa: BLE001
            # ошибка рисования не роняет программу; след — один раз
            if not getattr(self, "_paint_err", False):
                self._paint_err = True
                log.error(f"✗ Небо: ошибка рисования: {e}")
        finally:
            p.end()

    # ---------------------------------------------------- слои (кэш)
    def _layer(self, fn, rect, k, dpr):
        """Нарисовать fn(p) в pixmap области rect (базовые координаты)."""
        pm = QPixmap(max(1, int(math.ceil(rect.width() * k * dpr))),
                     max(1, int(math.ceil(rect.height() * k * dpr))))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        q = QPainter(pm)
        try:
            q.setRenderHint(QPainter.Antialiasing)
            q.setRenderHint(QPainter.SmoothPixmapTransform)
            q.setRenderHint(QPainter.TextAntialiasing)
            q.scale(k, k)
            q.translate(-rect.x(), -rect.y())
            q.setClipRect(rect)
            fn(q)
        finally:
            q.end()
        return pm

    def _scene(self):
        """Параметры сцены на текущий момент (без анимации)."""
        st = self._snap()
        ok = st.get("ok", True)
        lat = st.get("lat")              # 0.0 — законная координата
        lon = st.get("lon")
        lat = 48.72 if lat is None else float(lat)
        lon = 37.55 if lon is None else float(lon)
        tilt = float(20 if st.get("tilt") is None else st.get("tilt"))
        paz = A.panel_az(st.get("aspect", 0) or 0)
        zone = (st.get("tz", 2), st.get("dst", True))
        now = A.station_now(zone)
        code = int(st.get("code") or 0) if ok else 0
        cloud = int(st.get("cloud") or 0) if ok else 0
        alt, az = A.sun_pos(lat, lon, now, zone)
        malt, maz = A.moon_pos(lat, lon, now, zone)
        ph, illum = A.moon_phase(A.jd_local(now, zone))
        return dict(
            st=st, ok=ok, lat=lat, lon=lon, tilt=tilt, paz=paz, zone=zone, now=now, code=code,
            cloud=cloud, alt=alt, az=az, malt=malt, maz=maz, ph=ph,
            illum=illum,
            rainy=(51 <= code <= 67) or code in (80, 81, 82) or code >= 95,
            snowy=(71 <= code <= 77) or code in (85, 86),
            overcast=code >= 3 or cloud >= 70,
            winter=now.month in (12, 1, 2),
            # 0 — день, 1 — глубокая ночь
            night=0.0 if alt > 6 else (1.0 if alt < -10 else (6 - alt) / 16.0))

    def _frame(self, p, k, ox, oy):
        sc = self._scene()
        now = sc["now"]
        dpr = self.devicePixelRatioF() or 1.0
        st = sc["st"]
        key = (self.width(), self.height(), dpr, int(now.timestamp() // 30),
               sc["code"], sc["cloud"], sc["ok"], sc["tilt"], sc["paz"], sc["zone"], SHOW_NAMES, FORCE_STARS,
               sc["lat"], sc["lon"], st.get("temp"), st.get("wind"),
               st.get("pop"), st.get("city"))
        if key != self._lay_key:
            full = QRectF(_X0, 0, _X1 - _X0, BASE_H)
            self._lay = {
                "back": self._layer(lambda q: self._paint_back(q, sc), full,
                                    k, dpr),
                "front": self._layer(lambda q: self._paint_front(q, sc), full,
                                     k, dpr),
            }
            self._lay_key = key
        # дерево (тысячи листьев) — свой кэш: пересобираем только при смене
        # размера, месяца или заметной смене освещения (шаг 1/24 ночи)
        tkey = (self.width(), self.height(), dpr, now.month,
                round(sc["night"] * 24))
        if (tkey != getattr(self, "_tree_key", None)
                or getattr(self, "_tree_img", None) is None):
            self._tree_img = self._layer(
                lambda q: self._tree(q, now, sc["night"]),
                self._TREE_RECT, k, dpr)
            self._tree_key = tkey
        self._lay["tree"] = self._tree_img
        live = time.monotonic() - self._t0
        still = (live // 30.0) * 30.0    # выключенная часть — кадр «стоит»

        def _a(on):                      # (и на регистраторе тоже)
            return live if (ANIMATE and on) else still
        a_cl, a_tr, a_pv, a_st = (_a(ANIM_CLOUDS), _a(ANIM_TREE),
                                  _a(ANIM_PANELS), _a(ANIM_STARS))
        night = sc["night"]
        p.drawPixmap(QPointF(ox + _X0 * k, oy), self._lay["back"])
        p.save()
        p.translate(ox, oy)
        p.scale(k, k)
        p.setClipRect(QRectF(_X0, 0, _X1 - _X0, SCENE_H))
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if night > 0.4 and (FORCE_STARS or not sc["overcast"]):
            self._stars_draw(p, a_st, (night - 0.4) / 0.6)
        if sc["alt"] > -3:
            self._sun(p, self._xy(sc["alt"], sc["az"]), a_cl, sc["overcast"])
        self._clouds(p, sc, a_cl, k * dpr)
        p.restore()
        p.drawPixmap(QPointF(ox + _X0 * k, oy), self._lay["front"])
        p.save()
        p.translate(ox, oy)
        p.scale(k, k)
        p.setClipRect(QRectF(_X0, 0, _X1 - _X0, SCENE_H))
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        # дерево — из кэша, качается (сдвиг кроны относительно корня)
        bx, by = self._TREE_X, self._TREE_Y
        p.save()
        p.translate(_TS, 0)                      # к левому краю (широкий экран)
        p.translate(bx, by)
        p.setTransform(QTransform().shear(0.018 * math.sin(a_tr * 0.7), 0),
                       True)
        p.translate(-bx, -by)
        tr = self._TREE_RECT
        p.drawPixmap(QRectF(tr.x(), tr.y(), tr.width(), tr.height()),
                     self._lay["tree"], QRectF())
        p.restore()
        p.save()
        p.translate(_TS, 0)
        if ANIMATE and ANIM_TREE:        # листопад — только живой
            self._falling(p, now, night, a_tr)
        p.restore()
        self._smoke(p, night, a_cl, now.month, st.get("temp"),
                    st.get("wind"))
        self._protons(p, sc, a_pv)
        if sc["rainy"] or sc["snowy"]:
            self._precip(p, a_cl, sc["snowy"], sc["code"])
        # молния — только в живой анимации (иначе «застывала» вспышкой на 30 с)
        if (ANIMATE and ANIM_CLOUDS and sc["code"] >= 95
                and int(a_cl * 3) % 19 == 0):
            p.fillRect(QRectF(_X0, 0, _X1 - _X0, SCENE_H), _c("#ffffff", 70))
            self._lightning(p, int(a_cl * 3) // 19)
        p.restore()

    @staticmethod
    def _lightning(p, seed):
        """Молния из облака к земле (ломаная + ореол)."""
        rnd = random.Random(seed)
        x, y = 180 + rnd.random() * 300, 70.0
        pts = [QPointF(x, y)]
        while y < HORIZON - 10:
            y += 14 + rnd.random() * 18
            x += (rnd.random() - 0.5) * 34
            pts.append(QPointF(x, min(y, HORIZON - 10)))
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_c("#bcd4ff", 70), 7, Qt.SolidLine, Qt.RoundCap,
                      Qt.RoundJoin))
        p.drawPath(path)
        p.setPen(QPen(_c("#ffffff", 240), 1.8, Qt.SolidLine, Qt.RoundCap,
                      Qt.RoundJoin))
        p.drawPath(path)

    def _paint_back(self, p, sc):
        """Небо, реальные звёзды, дуги Солнца, Луна — меняются раз в 30 с."""
        night = sc["night"]
        self._sky(p, sc["alt"], sc["overcast"])
        if night > 0.4 and (FORCE_STARS or not sc["overcast"]):
            if night > 0.7:
                self._milky_way(p, sc["lat"], sc["lon"], sc["now"],
                                (night - 0.7) / 0.3
                                * (1 - 0.7 * sc["illum"]))
            self._real_stars(p, sc["lat"], sc["lon"], sc["now"],
                             (night - 0.4) / 0.6)
        arcs = self._get_arcs(sc["lat"], sc["lon"], sc["now"].date())
        self._path(p, arcs["jun"], _c("#dfe6ee", 120), dash=True)
        self._path(p, arcs["dec"], _c("#dfe6ee", 90), dash=True)
        self._path(p, arcs["today"], _c("#ffc93c", 230), width=0.9,
                   glow=night < 0.5)
        if sc["malt"] > -3:
            self._moon(p, self._xy(sc["malt"], sc["maz"]), sc["ph"],
                       sc["overcast"])
        _dither(p)

    def _paint_front(self, p, sc):
        """Холмы, земля, панели, дом, виньетка, текст — раз в 30 с."""
        night, winter, now = sc["night"], sc["winter"], sc["now"]
        self._hills(p, night, winter)
        self._ground(p, now, night, winter)
        self._panels(p, sc["tilt"], sc["alt"], sc["az"], night, sc["snowy"], sc["paz"])
        p.save()
        p.translate(_HS, 0)                      # к правому краю (широкий экран)
        self._house(p, night, winter, now.month,
                    (sc["st"] or {}).get("temp"))
        p.restore()
        if _HS and getattr(self, "_chim", None):
            self._chim = (self._chim[0] + _HS, self._chim[1])
        vg = QRadialGradient(QPointF((_X0 + _X1) / 2, SCENE_H / 2),
                             (_X1 - _X0) * 0.7)
        vg.setColorAt(0.75, _c("#000000", 0))
        vg.setColorAt(1.0, _c("#000000", 70))
        p.fillRect(QRectF(_X0, 0, _X1 - _X0, SCENE_H), vg)
        self._panel_text(p, sc["st"], sc["ok"], now, sc["lat"], sc["lon"],
                         sc["tilt"], sc["alt"], sc["az"], sc["malt"],
                         sc["maz"], sc["illum"], sc["ph"], sc["code"], sc["paz"], sc["zone"])

    # ---------------------------------------------------- облака (спрайты)
    _CLOUD_PUFFS = (
        ((0, 12, 20), (22, -2, 27), (50, -8, 30), (78, 4, 24), (98, 14, 16),
         (36, 16, 22), (64, 18, 20), (14, 20, 16), (86, 20, 14)),
        ((0, 10, 17), (20, -4, 24), (44, 2, 21), (64, 10, 16), (30, 14, 18),
         (52, 16, 15)),
        ((0, 8, 14), (18, -2, 20), (38, 4, 17), (56, 10, 12), (26, 12, 14)),
    )

    def _cloud_sprite(self, idx, dark, night, scale):
        nb = round(night * 8) / 8.0
        key = (idx, dark, nb, round(scale, 3))
        pm = self._sprites.get(key)
        if pm is not None:
            return pm
        puffs = self._CLOUD_PUFFS[idx % len(self._CLOUD_PUFFS)]
        x0 = min(dx - r for dx, dy, r in puffs) - 6
        y0 = min(dy - r for dx, dy, r in puffs) - 6
        x1 = max(dx + r for dx, dy, r in puffs) + 6
        y1 = max(dy + r for dx, dy, r in puffs) + 6
        rect = QRectF(x0, y0, x1 - x0, y1 - y0)
        pm = self._layer(lambda q: self._cloud_draw(q, puffs, dark, nb),
                         rect, scale, 1.0)
        pm.setDevicePixelRatio(scale)
        if len(self._sprites) > 40:
            self._sprites.clear()
        self._sprites[key] = (pm, x0, y0)
        return self._sprites[key]

    @staticmethod
    def _cloud_draw(p, puffs, dark, night):
        nc = QColor("#1c2230")
        lite = QColor("#8a93a3") if dark else QColor("#ffffff")
        mid = QColor("#6c7584") if dark else QColor("#eef2f7")
        shade = QColor("#434a57") if dark else QColor("#b3bfcf")
        lite, mid, shade = (_mix(c, nc, night * 0.78)
                            for c in (lite, mid, shade))
        body = QPainterPath()
        for dx, dy, r in puffs:
            one = QPainterPath()
            one.addEllipse(QPointF(dx, dy), r, r)
            body = body.united(one)
        top = min(dy - r for dx, dy, r in puffs)
        bot = max(dy + r for dx, dy, r in puffs)
        # ровное «дно» облака
        lx = min(dx - r * 0.6 for dx, dy, r in puffs)
        rx = max(dx + r * 0.6 for dx, dy, r in puffs)
        base = QPainterPath()
        base.addRoundedRect(QRectF(lx, bot - 22, rx - lx, 18), 9, 9)
        body = body.united(base)
        bot -= 4
        p.setPen(Qt.NoPen)
        # мягкий край (ореол)
        for grow, al in ((5, 18), (2.5, 34)):
            p.setBrush(_c(mid.name(), al))
            for dx, dy, r in puffs:
                p.drawEllipse(QPointF(dx, dy), r + grow, r + grow)
        g = QLinearGradient(0, top, 0, bot)
        g.setColorAt(0, lite)
        g.setColorAt(0.55, mid)
        g.setColorAt(1, shade)
        p.fillPath(body, QBrush(g))
        # объём: блики сверху-слева у каждого клуба, тень снизу
        p.save()
        p.setClipPath(body)
        for dx, dy, r in puffs:
            hg = QRadialGradient(QPointF(dx - r * 0.25, dy - r * 0.45), r)
            hg.setColorAt(0, _c(lite.name(), 150 if not dark else 70))
            hg.setColorAt(1, _c(lite.name(), 0))
            p.setBrush(QBrush(hg))
            p.drawEllipse(QPointF(dx, dy), r, r)
        sg = QLinearGradient(0, bot - (bot - top) * 0.35, 0, bot)
        sg.setColorAt(0, _c(shade.name(), 0))
        sg.setColorAt(1, _c(shade.darker(125).name(), 150))
        p.fillRect(QRectF(-200, top, 600, bot - top + 10), sg)
        p.restore()

    def _clouds(self, p, sc, anim, scale):
        code, cloud = sc["code"], sc["cloud"]
        n_cl = 0 if (cloud < 15 and code < 2) else (
            1 if cloud < 40 else 2 if cloud < 70 else 3)
        if code >= 3:
            n_cl = max(n_cl, 3)
        if sc["overcast"]:
            n_cl = 5
        for i in range(n_cl):
            s = (1.15, 0.95, 0.8, 1.05, 0.7)[i]
            dark = sc["rainy"] or code >= 95 or (sc["overcast"] and i % 2 == 0)
            pm, x0, y0 = self._cloud_sprite(i % 3, dark, sc["night"],
                                            scale * s)
            span = (_X1 - _X0) + 260
            cx = _X0 + (560 - _X0 - i * 150 + anim * (4 + 1.6 * i)) % span \
                - 130
            cy = (46, 84, 30, 118, 70)[i]
            p.drawPixmap(QRectF(cx + x0 * s, cy + y0 * s,
                                pm.width() / pm.devicePixelRatio() * s,
                                pm.height() / pm.devicePixelRatio() * s),
                         pm, QRectF())

    # ----------------------------------------------- небо
    def _sky(self, p, alt, overcast):
        if alt > 12:
            c = ("#2f6fbf", "#5b97d8", "#b7d8f2")
        elif alt > 2:
            c = ("#35609f", "#6f94c4", "#f4c48a")
        elif alt > -4:
            c = ("#243a72", "#6a5487", "#f08a4b")
        elif alt > -10:
            c = ("#101a3a", "#2b2c55", "#6b3e5c")
        else:
            c = ("#050814", "#0b1228", "#172342")
        top, mid, bot = QColor(c[0]), QColor(c[1]), QColor(c[2])
        if overcast:
            f = 0.6 if alt > -2 else 0.35
            top = _mix(top, QColor("#6e7680"), f)
            mid = _mix(mid, QColor("#8c939c"), f)
            bot = _mix(bot, QColor("#aab0b6"), f)
        g = QLinearGradient(0, 0, 0, HORIZON)
        g.setColorAt(0, top)
        g.setColorAt(0.55, mid)
        g.setColorAt(1, bot)
        p.fillRect(QRectF(_X0, 0, _X1 - _X0, SCENE_H), g)
        hz = QLinearGradient(0, HORIZON - 70, 0, HORIZON)
        hz.setColorAt(0, _c("#ffffff", 0))
        hz.setColorAt(1, _c("#ffffff", 40 if alt > -2 else 12))
        p.fillRect(QRectF(_X0, HORIZON - 70, _X1 - _X0, 70), hz)

    def _stars_draw(self, p, anim, k):
        p.setPen(Qt.NoPen)
        sx = (_X1 - _X0) / BASE_W
        for x, y, r, ph in self._stars:
            tw = 0.55 + 0.45 * math.sin(anim * 1.7 + ph)
            p.setBrush(_c("#ffffff", 210 * k * tw))
            p.drawEllipse(QPointF(_X0 + x * sx, y), r * 0.8, r * 0.8)

    def _star_xy(self, lat, lon, now):
        """Позиции звёзд каталога (пересчёт раз в минуту)."""
        key = (round(lat, 3), round(lon, 3),
               int(now.timestamp() // 60), round(_X0))
        if key != self._sky_key:
            jd = A.jd_local(now, self._zone())
            pos = {}
            for n, (ra, dec, mag, _l) in SC.STARS.items():
                a, z = A.radec_altaz(ra, dec, lat, lon, jd)
                q = self._xy(a, z)
                if a > 1 and _X0 + 4 <= q.x() <= _X1 - 4 and \
                        (_X0 < 0 or 50 <= z <= 310):
                    pos[n] = (q, mag)
            self._sky_pos = pos
            self._sky_key = key
        return self._sky_pos

    # Галактический экватор (l, b) -> RA/Dec J2000: северный полюс Галактики
    # RA 192.85948°, Dec 27.12825°, долгота полюса мира l = 122.93192°.
    _MW = None

    @classmethod
    def _mw_points(cls):
        if cls._MW is None:
            rnd = random.Random(11)
            ag, dg, ln = (math.radians(192.85948), math.radians(27.12825),
                          math.radians(122.93192))
            pts = []
            for i in range(360):
                l_deg = float(i)
                bright = 0.45 + 0.55 * (1 + math.cos(math.radians(l_deg))) / 2
                for _j in range(6):
                    b_deg = rnd.gauss(0, 5.5)
                    lr, br = math.radians(l_deg + rnd.random()), \
                        math.radians(b_deg)
                    sd = (math.sin(br) * math.sin(dg) + math.cos(br)
                          * math.cos(dg) * math.cos(ln - lr))
                    dec = math.asin(max(-1.0, min(1.0, sd)))
                    ra = ag + math.atan2(
                        math.cos(br) * math.sin(ln - lr),
                        math.sin(br) * math.cos(dg)
                        - math.cos(br) * math.sin(dg) * math.cos(ln - lr))
                    pts.append((math.degrees(ra) % 360 / 15.0,
                                math.degrees(dec),
                                bright * (1 - min(1.0, abs(b_deg) / 14.0)),
                                3 + rnd.random() * 7))
            cls._MW = pts
        return cls._MW

    def _milky_way(self, p, lat, lon, now, k):
        """Млечный Путь: мягкая полоса по галактическому экватору (реальное
        положение на небе), ярче к центру Галактики (Стрелец)."""
        if k <= 0.02:
            return
        # мягкая полоса — рисуем раз в 2 мин в свою картинку (2 точки на
        # базовую), дальше только растягиваем: на 4K иначе пересборка фона
        # заметно дёргала бы анимацию
        key = (round(lat, 3), round(lon, 3), int(now.timestamp() // 120),
               round(_X0), round(k, 2))
        if key != getattr(self, "_mw_key", None):
            jd = A.jd_local(now, self._zone())
            sc2 = 2.0
            wd = _X1 - _X0
            img = QImage(int(wd * sc2) + 1, int(HORIZON * sc2) + 1,
                         QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            q2 = QPainter(img)
            try:
                q2.setRenderHint(QPainter.Antialiasing)
                q2.scale(sc2, sc2)
                q2.translate(-_X0, 0)
                q2.setPen(Qt.NoPen)
                for ra, dec, br, rr in self._mw_points():
                    a, z = A.radec_altaz(ra, dec, lat, lon, jd)
                    if a < 2:
                        continue
                    q = self._xy(a, z)
                    if not (_X0 - 20 <= q.x() <= _X1 + 20):
                        continue
                    al = 17 * br * k * min(1.0, a / 12.0)   # у горизонта — дымка
                    if al < 1:
                        continue
                    g = QRadialGradient(q, rr)
                    g.setColorAt(0, _c("#c9d6f2", al))
                    g.setColorAt(1, _c("#c9d6f2", 0))
                    q2.setBrush(QBrush(g))
                    q2.drawEllipse(q, rr, rr * 0.8)
            finally:
                q2.end()
            self._mw_img, self._mw_key = img, key
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(_X0, 0, _X1 - _X0, HORIZON), self._mw_img)
        p.restore()

    def _real_stars(self, p, lat, lon, now, k):
        pos = self._star_xy(lat, lon, now)
        if not pos:
            return
        # линии созвездий (выключаются вместе с названиями)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(_c("#9fb8e8", 70 * k), 0.8))
        names = []
        for _key, (title, segs) in (SC.FIGURES.items() if SHOW_NAMES
                                    else ()):
            pts = []
            for a, b in segs:
                if a in pos and b in pos:
                    # широкая сцена: север (азимут 0/360) — на обоих краях;
                    # отрезок через этот «шов» не рисуем (линия через всё небо)
                    if abs(pos[a][0].x() - pos[b][0].x()) > 240:
                        continue
                    p.drawLine(pos[a][0], pos[b][0])
                    pts += [pos[a][0], pos[b][0]]
            if len(pts) >= 4:
                names.append((title, pts))
        # звёзды: размер/яркость по звёздной величине, цвет по классу
        p.setPen(Qt.NoPen)
        for n, (q, mag) in pos.items():
            r = max(0.55, 2.3 - 0.45 * mag)
            a = min(255, (255 - 30 * max(0.0, mag)) * k)
            col = ("#ffd2a8" if n in SC.WARM else
                   "#cfe0ff" if n in SC.BLUE else "#fff8ec")
            if mag < 1.2:
                g = QRadialGradient(q, r * 3.2)
                g.setColorAt(0, _c(col, a * 0.5))
                g.setColorAt(1, _c(col, 0))
                p.setBrush(g)
                p.drawEllipse(q, r * 3.2, r * 3.2)
            p.setBrush(_c(col, a))
            p.drawEllipse(q, r, r)
        if not SHOW_NAMES:
            return
        # подписи: созвездия (курсив, приглушённо) и яркие звёзды
        f = QFont(FONT, 7)
        f.setItalic(True)
        p.setFont(f)
        p.setPen(_c("#a9c0ea", 150 * k))
        for title, pts in names:
            cx = sum(q.x() for q in pts) / len(pts)
            cy = max(q.y() for q in pts) + 11
            if cy < HORIZON - 30:
                p.drawText(QRectF(cx - 60, cy - 6, 120, 12), Qt.AlignCenter,
                           title)
        p.setFont(QFont(FONT, 7))
        p.setPen(_c("#e8e2d0", 170 * k))
        for n, (q, _mag) in pos.items():
            lab = SC.STARS[n][3]
            if lab and q.y() < HORIZON - 26:
                p.drawText(QPointF(q.x() + 4, q.y() - 3), lab)

    @staticmethod
    def _path(p, pts, col, width=0.6, dash=False, glow=False):
        if len(pts) < 2:
            return
        path = QPainterPath(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        p.setBrush(Qt.NoBrush)
        if glow:
            gc = QColor(col)
            gc.setAlpha(32)
            p.setPen(QPen(gc, width + 2.2, Qt.SolidLine, Qt.RoundCap))
            p.drawPath(path)
        pen = QPen(col, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        if dash:
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern([8, 9])     # в толщинах линии
        p.setPen(pen)
        p.drawPath(path)

    @staticmethod
    def _sun(p, c, anim, overcast):
        a = 110 if overcast else 200
        for r, al in ((70, a * 0.25), (44, a * 0.5)):
            g = QRadialGradient(c, r)
            g.setColorAt(0, _c("#fff3b0", al))
            g.setColorAt(1, _c("#fff3b0", 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(c, r, r)
        if not overcast:
            for i in range(16):
                ang = anim * 0.25 + i * math.pi / 8
                ln = 26 + (6 if i % 2 else 0) + 2.5 * math.sin(anim * 2.2 + i)
                pen = QPen(_c("#ffd24d", 210), 2.2 if i % 2 == 0 else 1.4,
                           Qt.SolidLine, Qt.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(c.x() + 19 * math.cos(ang),
                                   c.y() + 19 * math.sin(ang)),
                           QPointF(c.x() + ln * math.cos(ang),
                                   c.y() + ln * math.sin(ang)))
        g = QRadialGradient(QPointF(c.x() - 4, c.y() - 4), 17)
        g.setColorAt(0, QColor("#fffdf0"))
        g.setColorAt(0.55, QColor("#ffe27a"))
        g.setColorAt(1, QColor("#ffb62e"))
        p.setPen(QPen(_c("#ffa21a", 200), 1))
        p.setBrush(QBrush(g))
        p.drawEllipse(c, 15, 15)

    @staticmethod
    def _moon(p, c, phase, overcast):
        """Луна: моря, кратеры, лучи Тихо, потемнение к краю, пепельный
        свет; рисуется в картинку в ПИКСЕЛЯХ экрана (без растяжения)."""
        r = 15.0
        # ореол — плавное (почти экспоненциальное) затухание
        a0 = 64 if not overcast else 26
        glow = QRadialGradient(c, 46)
        for t, f in ((0.0, 1.0), (0.2, 0.62), (0.35, 0.36), (0.5, 0.19),
                     (0.65, 0.09), (0.8, 0.035), (1.0, 0.0)):
            glow.setColorAt(t, _c("#dfe8ff", a0 * f))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(c, 46, 46)
        try:
            dpr = float(p.device().devicePixelRatioF())
        except Exception:                               # noqa: BLE001
            dpr = 1.0
        scale = max(1.0, abs(p.worldTransform().m11()) * dpr)
        img = _moon_sprite(phase, bool(overcast), int(math.ceil(2 * r * scale)))
        p.save()
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawImage(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), img)
        p.restore()

    # ----------------------------------------------- земля
    @staticmethod
    def _hills(p, night, winter):
        layers = (("#7f95a8", "#6d8699", 34, 0.013, 12),
                  ("#4f6e5a", "#3e5a48", 22, 0.021, 7),
                  ("#3c5a3e", "#2d4630", 12, 0.031, 3))
        for top, bot, h, fr, amp in layers:
            if winter:
                top, bot = ("#c9d3dc", "#aebbc6") if h > 20 else \
                    ("#dde5ec", "#c3cfd8")
            path = QPainterPath(QPointF(_X0, HORIZON))
            for x in range(int(_X0) - 8, int(_X1) + 10, 8):
                yy = HORIZON - h * 0.55 - amp * math.sin(x * fr) \
                    - amp * 0.6 * math.sin(x * fr * 2.7 + h)
                path.lineTo(QPointF(x, yy))
            path.lineTo(QPointF(_X1 + 8, HORIZON + 4))
            path.lineTo(QPointF(_X0 - 8, HORIZON + 4))
            g = QLinearGradient(0, HORIZON - h - amp, 0, HORIZON)
            g.setColorAt(0, _mix(QColor(top), QColor("#0a0f1c"), night * 0.75))
            g.setColorAt(1, _mix(QColor(bot), QColor("#0a0f1c"), night * 0.75))
            p.setPen(Qt.NoPen)
            p.fillPath(path, QBrush(g))

    def _ground(self, p, now, night, winter):
        m = now.month
        field = {12: "#e3e9ee", 1: "#e8edf1", 2: "#dce3e9", 3: "#7c8a4e",
                 4: "#5f9a42", 5: "#4f933b", 6: "#4a8a36", 7: "#6f8f38",
                 8: "#8f8c3f", 9: "#9a8440", 10: "#8a6a38", 11: "#72603f"}[m]
        top = _mix(QColor(field), QColor("#0a0f1c"), night * 0.8)
        bot = _mix(QColor(field).darker(150), QColor("#05070d"), night * 0.8)
        g = QLinearGradient(0, HORIZON, 0, SCENE_H)
        g.setColorAt(0, top)
        g.setColorAt(1, bot)
        p.fillRect(QRectF(_X0, HORIZON, _X1 - _X0, SCENE_H - HORIZON), g)
        if not winter:
            gc = _mix(QColor(field).darker(125), QColor("#0a0f1c"), night * 0.8)
            p.setPen(QPen(gc, 1))
            sx = (_X1 - _X0) / BASE_W
            for x, y, r in self._grass:
                for x0 in ((x,) if sx <= 1 else (x, _X0 + x * sx)):
                    p.drawLine(QPointF(x0, y),
                               QPointF(x0 + 1.5 * r - 0.7, y - 3 - 2 * r))

    # ------------------------------------------------ дерево (крона из листьев)
    _TREE_X, _TREE_Y = 66, HORIZON + 30          # основание ствола
    _CLUSTERS = ((0, -118, 30), (-30, -100, 26), (30, -102, 27),
                 (-44, -74, 22), (44, -76, 22), (-16, -80, 24),
                 (18, -84, 24), (-2, -140, 20), (-26, -128, 18),
                 (26, -130, 18))
    _PAL = {
        "autumn": ("#9c3514", "#c6501a", "#e2701f", "#f19227", "#f7b632",
                   "#fcd650"),
        "summer": ("#1f5a22", "#2d7a2c", "#3f9638", "#57ad47", "#79c35a",
                   "#9ad873"),
        "spring": ("#3f8c35", "#5aa845", "#7cc25a", "#a2d878", "#f3c6d6",
                   "#fbe3ec"),
    }

    def _tree_leaves(self):
        """Листья кроны: (x, y, угол, размер, светлота 0..1, кластер).
        Мелкие и густые; в кроне — «окна», сквозь которые видны ветви."""
        if getattr(self, "_leaves", None) is None:
            rnd = random.Random(11)
            holes = [(rnd.uniform(-40, 40), rnd.uniform(-130, -70),
                      rnd.uniform(4, 7)) for _ in range(9)]
            out = []
            for ci, (cx, cy, r) in enumerate(self._CLUSTERS):
                for _ in range(int(r * 9.0)):
                    a = rnd.random() * 6.283
                    d = r * math.sqrt(rnd.random())
                    lx, ly = cx + d * math.cos(a), cy + d * 0.85 * math.sin(a)
                    if any(math.hypot(lx - hx, ly - hy) < hr
                           for hx, hy, hr in holes):
                        continue
                    # свет сверху-справа, тень снизу-слева; край кластера
                    # светлее (листья на свету), середина — в тени
                    sh = 0.3 + (lx * 0.5 - (ly + 100) * 0.85) / 120.0 \
                        + 0.22 * (d / r) * (0.5 + 0.5 * math.cos(a + 0.9)) \
                        + (rnd.random() - 0.5) * 0.3
                    out.append((lx, ly, rnd.random() * 360,
                                2.0 + rnd.random() * 1.6,
                                max(0.0, min(0.999, sh)), ci))
            out.sort(key=lambda t: t[4])          # тёмные — снизу
            self._leaves = out
        return self._leaves

    def _tree_skel(self):
        """Скелет кроны: ветви 3 порядков к кластерам (a, b, w0, w1, ярус)."""
        if getattr(self, "_skel", None) is None:
            rnd = random.Random(7)
            segs = []

            def grow(a, ang, ln, w, depth):
                bend = rnd.uniform(-0.12, 0.12)
                b = QPointF(a.x() + ln * math.cos(ang + bend),
                            a.y() + ln * math.sin(ang + bend))
                segs.append((a, b, w, max(0.5, w * 0.6), depth))
                if depth >= 4:
                    return
                kids = ((-rnd.uniform(0.25, 0.55), 0.74),
                        (rnd.uniform(0.25, 0.55), 0.7))
                if depth >= 2 and rnd.random() < 0.6:
                    kids += ((rnd.uniform(-0.12, 0.12), 0.6),)
                for da, lk in kids:
                    grow(b, ang + da, ln * lk * rnd.uniform(0.88, 1.05),
                         w * 0.6, depth + 1)
            fork = QPointF(0, -54)
            for cx, cy, _r in self._CLUSTERS[:7]:
                tx, ty = cx * 0.85, cy * 0.9
                ang = math.atan2(ty - fork.y(), tx - fork.x())
                ln = math.hypot(tx - fork.x(), ty - fork.y()) * 0.55
                grow(fork, ang, ln, 5.2 if abs(cx) < 20 else 4.4, 1)
            self._skel = segs
        return self._skel

    @staticmethod
    def _limb(p, a, b, w0, w1, col):
        """Сужающаяся ветка от a к b (ширина w0 -> w1)."""
        dx, dy = b.x() - a.x(), b.y() - a.y()
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        mid = QPointF(a.x() + dx * 0.5 + nx * ln * 0.06,
                      a.y() + dy * 0.5 + ny * ln * 0.06)
        path = QPainterPath(QPointF(a.x() + nx * w0 / 2, a.y() + ny * w0 / 2))
        path.quadTo(QPointF(mid.x() + nx * (w0 + w1) / 4,
                            mid.y() + ny * (w0 + w1) / 4),
                    QPointF(b.x() + nx * w1 / 2, b.y() + ny * w1 / 2))
        path.lineTo(QPointF(b.x() - nx * w1 / 2, b.y() - ny * w1 / 2))
        path.quadTo(QPointF(mid.x() - nx * (w0 + w1) / 4,
                            mid.y() - ny * (w0 + w1) / 4),
                    QPointF(a.x() - nx * w0 / 2, a.y() - ny * w0 / 2))
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawPath(path)

    def _tree(self, p, now, night):
        m = now.month
        x, y = self._TREE_X, self._TREE_Y
        dk = night * 0.78
        nightc = QColor("#0a0f1c")
        winter = m in (12, 1, 2)
        season = ("autumn" if m in (9, 10, 11) else
                  "spring" if m in (3, 4) else "summer")

        def dc(h, extra=0.0):
            return _mix(QColor(h), nightc, min(1.0, dk + extra))
        # тень на земле (мягкая)
        p.setPen(Qt.NoPen)
        sg = QRadialGradient(QPointF(x + 14, y + 3), 56)
        sg.setColorAt(0, _c("#000000", 70 * (1 - night * 0.5)))
        sg.setColorAt(1, _c("#000000", 0))
        p.setBrush(QBrush(sg))
        p.save()
        p.translate(x + 14, y + 3)
        p.scale(1.0, 0.16)
        p.drawEllipse(QPointF(0, 0), 56, 56)
        p.restore()
        # ствол с корневыми наплывами
        trunk = QPainterPath(QPointF(x - 17, y + 3))
        trunk.quadTo(QPointF(x - 9, y + 1), QPointF(x - 7, y - 8))
        trunk.quadTo(QPointF(x - 4.5, y - 30), QPointF(x - 5, y - 56))
        trunk.lineTo(QPointF(x + 5, y - 56))
        trunk.quadTo(QPointF(x + 5, y - 30), QPointF(x + 8, y - 8))
        trunk.quadTo(QPointF(x + 10, y + 1), QPointF(x + 18, y + 3))
        trunk.closeSubpath()
        tg = QLinearGradient(x - 10, 0, x + 10, 0)
        tg.setColorAt(0, dc("#3b2413"))
        tg.setColorAt(0.55, dc("#7a4f2c"))
        tg.setColorAt(0.85, dc("#a8743f"))
        tg.setColorAt(1, dc("#6e4526"))
        p.setBrush(QBrush(tg))
        p.drawPath(trunk)
        # кора: продольные трещины
        p.save()
        p.setClipPath(trunk)
        rnd = random.Random(3)
        for i in range(14):
            bx = x - 8 + i * 1.2 + rnd.uniform(-0.4, 0.4)
            y0 = y + 2 - rnd.uniform(0, 10)
            y1 = y0 - rnd.uniform(10, 26)
            path = QPainterPath(QPointF(bx, y0))
            path.cubicTo(QPointF(bx + rnd.uniform(-1.2, 1.2), (y0 * 2 + y1) / 3),
                         QPointF(bx + rnd.uniform(-1.2, 1.2), (y0 + y1 * 2) / 3),
                         QPointF(bx + rnd.uniform(-0.8, 0.8), y1))
            p.setPen(QPen(dc("#2a180c"), 0.55))
            p.drawPath(path)
            if i % 3 == 0 and i > 6:
                p.setPen(QPen(_c("#ffffff", 26 * (1 - night)), 0.4))
                p.drawPath(path.translated(0.7, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(dc("#2a180c"))                 # сучок
        p.drawEllipse(QPointF(x + 1.5, y - 34), 0.9, 1.3)
        p.restore()
        # ветви (скелет)
        segs = self._tree_skel()
        for a, b, w0, w1, dep in segs:
            if not winter and dep >= 4:
                continue                          # тонкие — под листвой
            a2 = QPointF(x + a.x(), y + a.y())
            b2 = QPointF(x + b.x(), y + b.y())
            self._limb(p, a2, b2, w0, w1,
                       QBrush(dc("#5e3b20" if dep < 3 else "#6d4a2c")))
        if winter:
            snow = _mix(QColor("#f4f7fa"), QColor("#8a93a6"), night * 0.6)
            for a, b, w0, _w1, dep in segs:       # снег сверху веток
                if dep > 3:
                    continue
                dxs, dys = b.x() - a.x(), b.y() - a.y()
                ang = math.degrees(math.atan2(dys, dxs))
                if abs(abs(ang) - 90) < 22:       # почти вертикальные — нет
                    continue
                ln = math.hypot(dxs, dys)
                p.save()
                p.translate(x + (a.x() + b.x()) / 2,
                            y + (a.y() + b.y()) / 2 - w0 * 0.45)
                p.rotate(ang if abs(ang) < 90 else ang - 180)
                p.setBrush(snow)
                p.drawRoundedRect(QRectF(-ln * 0.38, -0.9 - w0 * 0.12,
                                         ln * 0.76, 1.2 + w0 * 0.12),
                                  0.8, 0.8)
                p.restore()
            p.setBrush(snow)                      # снег у корней
            p.drawEllipse(QPointF(x, y + 2.5), 20, 2.4)
            self._tuft(p, x, y, night, winter=True)
            return
        pal = [dc(h) for h in self._PAL[season]]
        # листья
        leaf = QPainterPath(QPointF(-1, 0))
        leaf.quadTo(QPointF(0, -1.1), QPointF(1, 0))
        leaf.quadTo(QPointF(0, 1.1), QPointF(-1, 0))
        n = len(pal)
        leaves = self._tree_leaves()
        # нижний слой: крупные тёмные листья — глубина кроны без «шаров»
        deep = QColor(pal[0])
        for k, (lx, ly, ang, sz, sh, _ci) in enumerate(leaves):
            if k % 2 or sh > 0.75:
                continue
            p.save()
            p.translate(x + lx, y + ly + 1.6)
            p.rotate(ang + 40)
            p.scale(sz * 1.7, sz * 1.05)
            p.setBrush(deep)
            p.drawPath(leaf)
            p.restore()
        for lx, ly, ang, sz, sh, _ci in leaves:
            p.save()
            p.translate(x + lx, y + ly)
            p.rotate(ang)
            p.scale(sz, sz * 0.6)
            p.setBrush(pal[min(n - 1, int(sh * n))])
            p.drawPath(leaf)
            p.restore()
        self._tuft(p, x, y, night, winter=False, season=season)

    _TREE_RECT = QRectF(0, HORIZON - 150, 150, 200)

    _LEAF = None

    def _falling(self, p, now, night, anim):
        """Осенью — падающие листья (живые, поверх кэша)."""
        if now.month not in (9, 10, 11):
            return
        if SkyView._LEAF is None:
            leaf = QPainterPath(QPointF(-1, 0))
            leaf.quadTo(QPointF(0, -1.1), QPointF(1, 0))
            leaf.quadTo(QPointF(0, 1.1), QPointF(-1, 0))
            SkyView._LEAF = leaf
        pal = self._PAL["autumn"]
        x, y = self._TREE_X, self._TREE_Y
        p.setPen(Qt.NoPen)
        for i in range(5):
            t = (anim * 0.11 + i * 0.23) % 1.0
            fx = x - 40 + i * 22 + 18 * math.sin(anim * 1.4 + i) + t * 30
            fy = y - 70 + t * 78
            p.save()
            p.translate(fx, fy)
            p.rotate(anim * 90 + i * 70)
            p.scale(3.4, 2.1)
            p.setBrush(_mix(QColor(pal[2 + i % 3]), QColor("#0a0f1c"),
                            night * 0.78))
            p.drawPath(SkyView._LEAF)
            p.restore()

    @staticmethod
    def _tuft(p, x, y, night, winter, season="summer"):
        """Пучок травы у корней."""
        col = ("#e7eef4" if winter else "#d9b23a" if season == "autumn"
               else "#6fbf4a")
        c = _mix(QColor(col), QColor("#0a0f1c"), night * 0.75)
        p.setPen(QPen(c, 0.7, Qt.SolidLine, Qt.RoundCap))
        for i in range(34):
            bx = x - 26 + i * 1.6
            h = 3 + (i * 7) % 5 * (1.0 - abs(bx - x) / 40)
            p.drawLine(QPointF(bx, y + 3), QPointF(bx + (i % 3 - 1) * 1.6,
                                                   y + 3 - h))

    def _panels(self, p, tilt, alt, az, night, snow, paz=180.0):
        n, x0, w, gap = 9, 108, 38, 4          # 10-е место — под щитовую
        if _TS or _HS:                           # широкая сцена — ряд длиннее
            left, right = x0 + _TS + 18, 490 + _HS - 8
            n = max(9, int((right - left + gap) // (w + gap)))
            x0 = left + ((right - left) - (n * (w + gap) - gap)) / 2.0
        top_y = HORIZON + 10
        h = 50 * max(0.35, math.cos(math.radians(tilt)) ** 0.5)
        skew = 7
        sun_k = 0.0
        if alt > 0:
            sun_k = max(0.0, 1 - incidence(alt, az, tilt, paz) / 90.0)
        dk = night * 0.7
        p.setPen(Qt.NoPen)
        p.setBrush(_c("#000000", 60))
        p.drawPolygon(QPolygonF([QPointF(x0 - 4, top_y + h + 10),
                                 QPointF(x0 + n * (w + gap) + 6, top_y + h + 10),
                                 QPointF(x0 + n * (w + gap) - 10, top_y + h + 20),
                                 QPointF(x0 - 20, top_y + h + 20)]))
        for i in range(n):
            x = x0 + i * (w + gap)
            p.setPen(QPen(_mix(QColor("#7d8793"), QColor("#0a0f1c"), dk), 2.5))
            p.drawLine(QPointF(x + w * 0.3, top_y + h),
                       QPointF(x + w * 0.3, top_y + h + 12))
            p.drawLine(QPointF(x + w * 0.7, top_y + h * 0.2),
                       QPointF(x + w * 0.7, top_y + h + 12))
            poly = QPolygonF([QPointF(x + skew, top_y),
                              QPointF(x + w + skew, top_y),
                              QPointF(x + w, top_y + h), QPointF(x, top_y + h)])
            g = QLinearGradient(x, top_y, x + w, top_y + h)
            g.setColorAt(0, _mix(QColor("#274f9e"), QColor("#060a18"), dk))
            g.setColorAt(1, _mix(QColor("#132c63"), QColor("#03060f"), dk))
            p.setPen(QPen(_mix(QColor("#c9d1da"), QColor("#1a1f28"), dk), 1.6))
            p.setBrush(QBrush(g))
            p.drawPolygon(poly)
            p.setPen(QPen(_c("#9fb8e8", 110 * (1 - dk)), 0.7))
            for r in range(1, 5):
                yy = top_y + h * r / 5
                xs = skew * (1 - r / 5)
                p.drawLine(QPointF(x + xs + 1, yy), QPointF(x + w + xs - 1, yy))
            for c in range(1, 3):
                xx = x + w * c / 3
                p.drawLine(QPointF(xx + skew, top_y + 1),
                           QPointF(xx, top_y + h - 1))
            gl = QLinearGradient(x, top_y, x + w, top_y + h)
            gl.setColorAt(0, _c("#ffffff", (40 + 90 * sun_k) * (1 - dk)))
            gl.setColorAt(0.5, _c("#ffffff", 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(gl))
            p.drawPolygon(poly)
            if snow:
                p.setBrush(_c("#f5f8fb", 235))
                p.drawPolygon(QPolygonF([QPointF(x + skew, top_y),
                                         QPointF(x + w + skew, top_y),
                                         QPointF(x + w + skew - 1, top_y + 6),
                                         QPointF(x + skew - 1, top_y + 5)]))
        # щитовая (инвертор/АКБ) слева от дома + кабель от всех панелей
        bx0, bw_, bh_ = 494 + _HS, 22, 34
        gy = top_y + h + 12                      # уровень земли у стоек
        box = QRectF(bx0, gy - bh_, bw_, bh_)
        cab_y = gy + 3
        nc = QColor("#0a0f1c")
        p.setPen(Qt.NoPen)
        p.setBrush(_c("#000000", 70))
        p.drawRect(QRectF(bx0 - 2, gy - 1, bw_ + 10, 4))  # тень
        bg = QLinearGradient(bx0, 0, bx0 + bw_, 0)
        bg.setColorAt(0, _mix(QColor("#a9b1ba"), nc, dk))
        bg.setColorAt(1, _mix(QColor("#7d868f"), nc, dk))
        p.setBrush(QBrush(bg))
        p.drawRect(box)
        p.setBrush(_mix(QColor("#5f666e"), nc, dk))            # козырёк
        p.drawRect(QRectF(bx0 - 2, gy - bh_ - 3, bw_ + 4, 3))
        p.setPen(QPen(_mix(QColor("#4c535a"), nc, dk), 0.8))
        p.drawRect(box.adjusted(2.5, 3, -2.5, -2.5))            # дверца
        for vy in (6, 8.5, 11):                                 # решётка
            p.drawLine(QPointF(bx0 + 6, gy - bh_ + vy),
                       QPointF(bx0 + bw_ - 6, gy - bh_ + vy))
        p.setPen(Qt.NoPen)
        cx_, ty_ = bx0 + bw_ / 2, gy - bh_ + 14         # знак ⚡ (треугольник)
        p.setBrush(_mix(QColor("#ffcc33"), nc, dk * 0.6))
        p.drawPolygon(QPolygonF([QPointF(cx_, ty_), QPointF(cx_ + 5.5, ty_ + 9.5),
                                 QPointF(cx_ - 5.5, ty_ + 9.5)]))
        p.setBrush(QColor("#1d1d1d"))                    # молния-зигзаг
        p.drawPolygon(QPolygonF([QPointF(cx_ + 0.9, ty_ + 2.6),
                                 QPointF(cx_ - 1.6, ty_ + 6.0),
                                 QPointF(cx_ - 0.1, ty_ + 6.0),
                                 QPointF(cx_ - 0.9, ty_ + 8.6),
                                 QPointF(cx_ + 1.7, ty_ + 5.0),
                                 QPointF(cx_ + 0.2, ty_ + 5.0)]))
        # кабель: от середины низа КАЖДОЙ панели вниз и по земле в щитовую
        cab = _mix(QColor("#1b1d20"), nc, dk * 0.5)
        p.setPen(QPen(cab, 1.6, Qt.SolidLine, Qt.RoundCap))
        xs = [x0 + i * (w + gap) + w * 0.5 for i in range(n)]
        for xx in xs:
            p.drawLine(QPointF(xx, top_y + h), QPointF(xx, cab_y))
        p.drawLine(QPointF(xs[0], cab_y), QPointF(bx0, cab_y))
        p.drawLine(QPointF(bx0, cab_y), QPointF(bx0, gy))    # в левый низ. угол
        # кабель щитовая → дом: ровно из нижнего правого угла шкафа
        hx = 540 + _HS                           # левый угол фасада дома
        p.drawLine(QPointF(bx0 + bw_, gy), QPointF(bx0 + bw_, cab_y))
        p.drawLine(QPointF(bx0 + bw_, cab_y), QPointF(hx + 2, cab_y))
        p.drawLine(QPointF(hx + 2, cab_y), QPointF(hx + 2, cab_y - 6))
        p.setPen(Qt.NoPen)
        # геометрия для живых «протонов» (сцена, базовые координаты)
        self._pv_geo = {"panels": [(x0 + i * (w + gap), top_y, w, h, skew)
                                   for i in range(n)],
                        "cab_y": cab_y, "box": box, "sun_k": sun_k,
                        "house_x": hx + 2}
        # подписи сторон света (В/Ю/З) убраны — по просьбе

    # ------------------------------------------------ дом (2.5D: фронтон + бок)
    @staticmethod
    def _quad(p, rect_w, rect_h, quad):
        """Перевести локальные координаты 0..w×0..h в четырёхугольник."""
        t = QTransform()
        ok = QTransform.quadToQuad(
            QPolygonF([QPointF(0, 0), QPointF(rect_w, 0),
                       QPointF(rect_w, rect_h), QPointF(0, rect_h)]),
            QPolygonF(quad), t)
        if ok:
            p.setTransform(t, True)
        return ok

    def _house(self, p, night, winter, month, temp=None):
        nc = QColor("#10131a")
        dk = night * 0.72

        def c(h, extra=0.0):
            return _mix(QColor(h), nc, min(1.0, dk + extra))

        lit = night > 0.45
        dim = lit and self._when().hour < 6        # после полуночи — спят
        base = HORIZON + 74                        # низ цоколя (фасад)
        fx0, fx1 = 540, 600                        # фронтон
        wall_top = base - 62
        apex = QPointF((fx0 + fx1) / 2, wall_top - 34)
        dx, dy = 48, -7                            # уход бока вглубь
        # опора ЛЭП за домом справа: бетонная стойка, стальная траверса,
        # фарфоровые изоляторы. Чуть дальше дома — лёгкая дымка, но плотная
        px, ptop = fx1 + dx + 26, wall_top - 46
        pgy = base - 6                           # земля у опоры (дальше дома)
        haze = QColor("#9fb3c7") if night < 0.5 else QColor("#1a2233")

        def pc(h, extra=0.0):                    # цвет опоры: ночь + дымка
            return _mix(c(h, extra), haze, 0.18)
        # тень от стойки на земле
        p.setPen(Qt.NoPen)
        p.setBrush(_c("#000000", 45 * (1 - night * 0.6)))
        p.drawPolygon(QPolygonF([QPointF(px - 2, pgy), QPointF(px + 2, pgy),
                                 QPointF(px + 16, pgy + 3),
                                 QPointF(px + 11, pgy + 3)]))
        # стойка (сужается кверху), свет слева, тень справа
        pole = QPolygonF([QPointF(px - 2.3, pgy), QPointF(px + 2.3, pgy),
                          QPointF(px + 1.4, ptop), QPointF(px - 1.4, ptop)])
        pg = QLinearGradient(px - 2.3, 0, px + 2.3, 0)
        pg.setColorAt(0, pc("#d8dad4"))
        pg.setColorAt(0.45, pc("#b9bcb6"))
        pg.setColorAt(1, pc("#7f837e"))
        p.setBrush(QBrush(pg))
        p.drawPolygon(pole)
        p.setBrush(pc("#6f736e"))                # оголовок
        p.drawRect(QRectF(px - 1.6, ptop - 1.2, 3.2, 1.6))
        # траверсы (уголок) и подкосы
        steel, steel_d = pc("#6d7278"), pc("#4a4f55")
        for yy, half in ((ptop + 6, 12.0), (ptop + 14, 8.0)):
            p.setBrush(steel)
            p.drawRect(QRectF(px - half, yy - 0.9, 2 * half, 1.8))
            p.setBrush(steel_d)
            p.drawRect(QRectF(px - half, yy + 0.5, 2 * half, 0.6))
        p.setPen(QPen(steel_d, 0.7))
        p.drawLine(QPointF(px - 1.5, ptop + 11), QPointF(px - 9, ptop + 6.6))
        p.drawLine(QPointF(px + 1.5, ptop + 11), QPointF(px + 9, ptop + 6.6))
        p.setPen(Qt.NoPen)
        # изоляторы: фарфоровые «юбки» с бликом
        ins = []
        for xx, yy in ((px - 11, ptop + 6), (px + 11, ptop + 6),
                       (px - 7, ptop + 14), (px + 7, ptop + 14)):
            for k3 in range(3):
                p.setBrush(pc("#e9e4d8") if k3 % 2 == 0 else pc("#cfc8b8"))
                p.drawRoundedRect(QRectF(xx - 1.5 + k3 * 0.2, yy - 2.2 - k3 * 1.3,
                                         3 - k3 * 0.4, 1.3), 0.6, 0.6)
            p.setBrush(_c("#ffffff", 150 * (1 - night)))
            p.drawEllipse(QPointF(xx - 0.6, yy - 4.4), 0.4, 0.4)
            ins.append(QPointF(xx, yy - 5.2))
        wire = pc("#2b2f35", -0.1)
        p.setBrush(Qt.NoBrush)
        # линия уходит вдаль вправо, к соседней опоре за холмом
        for a in (ins[1], ins[3]):
            path = QPainterPath(a)
            path.quadTo(QPointF(a.x() + 60, a.y() + 20),
                        QPointF(a.x() + 180, HORIZON - 30))
            p.setPen(QPen(wire, 0.75))
            p.drawPath(path)
        # ввод в дом — к ЗАДНЕЙ стене: конец проводов скрыт домом
        for k2, a in enumerate((ins[0], ins[2])):
            b = QPointF(fx1 + dx - 10, wall_top + dy + 14 + k2 * 4)
            path = QPainterPath(a)
            path.quadTo(QPointF((a.x() + b.x()) / 2, max(a.y(), b.y()) + 6), b)
            p.setPen(QPen(wire, 0.75))
            p.drawPath(path)
        p.setPen(Qt.NoPen)
        # тень на земле
        p.setPen(Qt.NoPen)
        p.setBrush(_c("#000000", 60 * (1 - night * 0.5)))
        p.drawPolygon(QPolygonF([QPointF(fx0 - 6, base + 2),
                                 QPointF(fx1 + dx + 8, base + dy + 2),
                                 QPointF(fx1 + dx + 20, base + 8),
                                 QPointF(fx0 - 14, base + 9)]))
        # --- боковая стена (в тени)
        side = [QPointF(fx1, wall_top), QPointF(fx1 + dx, wall_top + dy),
                QPointF(fx1 + dx, base + dy), QPointF(fx1, base)]
        sg = QLinearGradient(fx1, 0, fx1 + dx, 0)
        sg.setColorAt(0, c("#c9b48f", 0.12))
        sg.setColorAt(1, c("#a8946f", 0.12))
        p.setBrush(QBrush(sg))
        p.drawPolygon(QPolygonF(side))
        p.save()
        if self._quad(p, 100, 100, side):
            # обшивка (доска внахлёст): тень под каждой доской + блик
            for yk in range(6, 88, 6):
                p.setBrush(c("#8a7755", 0.12))
                p.drawRect(QRectF(0, yk, 100, 0.9))
                p.setBrush(_c("#ffffff", 22 * (1 - night)))
                p.drawRect(QRectF(0, yk + 0.9, 100, 0.6))
            # тень под свесом крыши и затемнение к земле
            og = QLinearGradient(0, 0, 0, 22)
            og.setColorAt(0, _c("#000000", 110))
            og.setColorAt(1, _c("#000000", 0))
            p.setBrush(QBrush(og))
            p.drawRect(QRectF(0, 0, 100, 22))
            ag = QLinearGradient(0, 64, 0, 88)
            ag.setColorAt(0, _c("#000000", 0))
            ag.setColorAt(1, _c("#000000", 60))
            p.setBrush(QBrush(ag))
            p.drawRect(QRectF(0, 64, 100, 24))
            # цоколь (камень) с швами
            p.setBrush(c("#6b625a", 0.1))
            p.drawRect(QRectF(0, 88, 100, 12))
            p.setPen(QPen(c("#4f4841", 0.1), 0.6))
            p.drawLine(QPointF(0, 94), QPointF(100, 94))
            for i in range(1, 9):
                xo = i * 11.0 + (5 if i % 2 else 0)
                p.drawLine(QPointF(xo, 88), QPointF(xo, 94))
                p.drawLine(QPointF(xo - 5, 94), QPointF(xo - 5, 100))
            p.setPen(Qt.NoPen)
            # окно на боку
            self._window(p, QRectF(22, 26, 40, 40), dk, lit, winter,
                         side=True, dim=dim)
        p.restore()
        p.setBrush(c("#9c8a66", 0.12))          # угол бока (тень)
        p.drawPolygon(QPolygonF([QPointF(fx1, wall_top), QPointF(fx1 + 3, wall_top - 0.4),
                                 QPointF(fx1 + 3, base - 8.4), QPointF(fx1, base - 8)]))
        # --- фасад (фронтон)
        front = QPolygonF([QPointF(fx0, base), QPointF(fx0, wall_top),
                           apex, QPointF(fx1, wall_top), QPointF(fx1, base)])
        fg = QLinearGradient(fx0, wall_top - 30, fx1, base)
        fg.setColorAt(0, c("#f1e4c8"))
        fg.setColorAt(1, c("#d9c6a0"))
        p.setBrush(QBrush(fg))
        p.drawPolygon(front)
        for yk in range(int(wall_top) + 4, int(base) - 8, 4):
            p.setBrush(c("#b9a47c"))
            p.drawRect(QRectF(fx0, yk, fx1 - fx0, 0.6))
            p.setBrush(_c("#ffffff", 40 * (1 - night)))
            p.drawRect(QRectF(fx0, yk + 0.6, fx1 - fx0, 0.4))
        eg = QLinearGradient(0, wall_top, 0, wall_top + 9)   # тень от свеса
        eg.setColorAt(0, _c("#000000", 80))
        eg.setColorAt(1, _c("#000000", 0))
        p.setBrush(QBrush(eg))
        p.drawRect(QRectF(fx0, wall_top, fx1 - fx0, 9))
        ag2 = QLinearGradient(0, base - 24, 0, base - 8)
        ag2.setColorAt(0, _c("#000000", 0))
        ag2.setColorAt(1, _c("#000000", 45))
        p.setBrush(QBrush(ag2))
        p.drawRect(QRectF(fx0, base - 24, fx1 - fx0, 16))
        p.setBrush(c("#f8f1e2"))                 # угловые доски
        p.drawRect(QRectF(fx0, wall_top, 2.2, base - 8 - wall_top))
        p.setBrush(c("#e6d8bb"))
        p.drawRect(QRectF(fx1 - 2.2, wall_top, 2.2, base - 8 - wall_top))
        # обшивка фронтона (доска)
        p.setBrush(c("#8a5a36"))
        gable = QPolygonF([QPointF(fx0, wall_top), apex,
                           QPointF(fx1, wall_top)])
        p.drawPolygon(gable)
        p.setPen(QPen(c("#6d4428"), 0.8))
        for i in range(1, 7):
            xx = fx0 + (fx1 - fx0) * i / 7
            h = (1 - abs(xx - apex.x()) / ((fx1 - fx0) / 2)) * 34
            p.drawLine(QPointF(xx, wall_top), QPointF(xx, wall_top - h))
        p.setPen(Qt.NoPen)
        # круглое чердачное окно
        cw = QPointF(apex.x(), wall_top - 13)
        p.setBrush(c("#f4f1ea"))
        p.drawEllipse(cw, 6, 6)
        p.setBrush(QColor("#ffcf6a") if lit and month in (11, 12, 1, 2)
                   else c("#7fa7c9", 0.1))
        p.drawEllipse(cw, 4.3, 4.3)
        # цоколь фасада (камень)
        p.setBrush(c("#7a7068"))
        p.drawRect(QRectF(fx0, base - 8, fx1 - fx0, 8))
        p.setPen(QPen(c("#5c544d"), 0.7))
        for i in range(1, 6):
            xx = fx0 + (fx1 - fx0) * i / 6 + (3 if i % 2 else 0)
            p.drawLine(QPointF(xx, base - 8), QPointF(xx, base))
        p.drawLine(QPointF(fx0, base - 4), QPointF(fx1, base - 4))
        p.setPen(Qt.NoPen)
        # отмостка (бетон) вдоль фасада и бока
        p.setBrush(c("#8c8d8a" if not winter else "#e9eef4", 0.05))
        p.drawPolygon(QPolygonF([QPointF(fx0 - 4, base), QPointF(fx1, base),
                                 QPointF(fx1 + dx + 3, base + dy),
                                 QPointF(fx1 + dx + 6, base + dy + 2.2),
                                 QPointF(fx1 + 2, base + 3),
                                 QPointF(fx0 - 6, base + 3)]))
        p.setBrush(_c("#000000", 40))
        p.drawRect(QRectF(fx0 - 6, base + 2.6, fx1 - fx0 + 8, 0.6))
        # окно и дверь фасада
        self._window(p, QRectF(fx0 + 7, wall_top + 14, 22, 24), dk, lit,
                     winter, dim=dim)
        dr = QRectF(fx0 + 37, wall_top + 20, 16, 34)
        p.setBrush(c("#e8dcc2"))
        p.drawRect(dr.adjusted(-2, -2, 2, 0))
        dg = QLinearGradient(dr.left(), 0, dr.right(), 0)
        dg.setColorAt(0, c("#6b3f24"))
        dg.setColorAt(1, c("#4d2c18"))
        p.setBrush(QBrush(dg))
        p.drawRect(dr)
        p.setPen(QPen(c("#3a2011"), 0.8))
        p.drawRect(dr.adjusted(3, 4, -3, -18))
        p.drawRect(dr.adjusted(3, 19, -3, -3))
        p.setPen(Qt.NoPen)
        p.setBrush(c("#d9b44a"))
        p.drawEllipse(QPointF(dr.right() - 3, dr.center().y() + 2), 1.1, 1.1)
        # козырёк над дверью (с тенью на стену)
        cy0 = dr.top() - 8
        sh = QLinearGradient(0, cy0 + 3, 0, cy0 + 9)
        sh.setColorAt(0, _c("#000000", 90))
        sh.setColorAt(1, _c("#000000", 0))
        p.setBrush(QBrush(sh))
        p.drawRect(QRectF(dr.left() - 5, cy0 + 3, dr.width() + 10, 6))
        p.setBrush(c("#7a2a1e"))
        p.drawPolygon(QPolygonF([QPointF(dr.left() - 6, cy0 + 3),
                                 QPointF(dr.center().x(), cy0 - 3),
                                 QPointF(dr.right() + 6, cy0 + 3)]))
        p.setBrush(c("#f0ece4"))
        p.drawRect(QRectF(dr.left() - 6, cy0 + 2.4, dr.width() + 12, 1.2))
        # крыльцо: две ступени
        p.setBrush(c("#a39a92"))
        p.drawRect(QRectF(dr.left() - 5, base - 5, dr.width() + 10, 2.4))
        p.setBrush(c("#8d847c"))
        p.drawRect(QRectF(dr.left() - 8, base - 2.6, dr.width() + 16, 2.6))
        p.setBrush(_c("#ffffff", 50 * (1 - night)))
        p.drawRect(QRectF(dr.left() - 5, base - 5, dr.width() + 10, 0.5))
        if lit:                                  # свет из окон и фонаря на землю
            wl = 70 if not dim else 30
            for gx, gw in ((fx0 + 18, 16), (dr.center().x(), 20)):
                gg = QRadialGradient(QPointF(gx, base + 5), gw)
                gg.setColorAt(0, _c("#ffc766", wl))
                gg.setColorAt(1, _c("#ffc766", 0))
                p.setBrush(QBrush(gg))
                p.save()
                p.translate(gx, base + 5)
                p.scale(1.0, 0.28)
                p.translate(-gx, -(base + 5))
                p.drawEllipse(QPointF(gx, base + 5), gw, gw)
                p.restore()
        # фонарь над дверью
        lamp = QPointF(dr.center().x(), dr.top() - 3)
        if lit:
            g = QRadialGradient(lamp, 26)
            g.setColorAt(0, _c("#ffd27a", 120))
            g.setColorAt(1, _c("#ffd27a", 0))
            p.setBrush(QBrush(g))
            p.drawEllipse(lamp, 26, 26)
        if lit:                                  # конус света на крыльцо
            cg = QLinearGradient(0, lamp.y(), 0, base)
            cg.setColorAt(0, _c("#ffd27a", 55 if not dim else 25))
            cg.setColorAt(1, _c("#ffd27a", 0))
            p.setBrush(QBrush(cg))
            p.drawPolygon(QPolygonF([QPointF(lamp.x() - 2, lamp.y() + 1),
                                     QPointF(lamp.x() + 2, lamp.y() + 1),
                                     QPointF(lamp.x() + 17, base),
                                     QPointF(lamp.x() - 17, base)]))
        p.setBrush(QColor("#ffe08a") if lit else c("#d8d2c4"))   # стекло
        p.drawRoundedRect(QRectF(lamp.x() - 1.6, lamp.y() - 1.6, 3.2, 3.6),
                          0.8, 0.8)
        p.setBrush(c("#2d2f33"))                  # колпак плафона
        p.drawPolygon(QPolygonF([QPointF(lamp.x() - 2.6, lamp.y() - 1.4),
                                 QPointF(lamp.x() + 2.6, lamp.y() - 1.4),
                                 QPointF(lamp.x() + 1.2, lamp.y() - 3),
                                 QPointF(lamp.x() - 1.2, lamp.y() - 3)]))
        p.drawRect(QRectF(lamp.x() - 1.6, lamp.y() + 1.9, 3.2, 0.7))
        if winter:                               # снег на козырьке
            p.setBrush(c("#f7f9fb"))
            p.drawPolygon(QPolygonF([QPointF(dr.left() - 6, cy0 + 2.4),
                                     QPointF(dr.center().x(), cy0 - 4.2),
                                     QPointF(dr.right() + 6, cy0 + 2.4),
                                     QPointF(dr.center().x(), cy0 - 2.2)]))
            p.drawRect(QRectF(dr.left() - 8, base - 3.3, dr.width() + 16, 1))
        # --- скат крыши (металл, фальцы)
        ov = 5                                        # свес
        e0 = QPointF(fx1 + ov * 0.9, wall_top + ov * 0.9)
        roof = [apex, QPointF(apex.x() + dx + 4, apex.y() + dy),
                QPointF(e0.x() + dx + 4, e0.y() + dy), e0]
        rg = QLinearGradient(apex, e0)
        rg.setColorAt(0, c("#9a3b2c"))
        rg.setColorAt(1, c("#6f2419"))
        p.setBrush(QBrush(rg))
        p.drawPolygon(QPolygonF(roof))
        p.save()
        if self._quad(p, 100, 100, roof):
            p.setPen(QPen(c("#5a1d14"), 0.9))
            for i in range(1, 12):
                p.drawLine(QPointF(i * 100 / 12, 0), QPointF(i * 100 / 12, 100))
            p.setPen(QPen(_c("#ffffff", 40 * (1 - night)), 0.6))
            for i in range(1, 12):
                p.drawLine(QPointF(i * 100 / 12 + 1.5, 0),
                           QPointF(i * 100 / 12 + 1.5, 100))
            for j in range(1, 8):                    # ряды «волны» черепицы
                yj = j * 100 / 8
                p.setPen(QPen(c("#4a160f"), 1.1))
                p.drawLine(QPointF(0, yj), QPointF(100, yj))
                p.setPen(QPen(_c("#ffffff", 30 * (1 - night)), 0.6))
                p.drawLine(QPointF(0, yj - 1.4), QPointF(100, yj - 1.4))
            fg2 = QLinearGradient(0, 0, 14, 0)       # тень у ветровой доски
            fg2.setColorAt(0, _c("#000000", 70))
            fg2.setColorAt(1, _c("#000000", 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(fg2))
            p.drawRect(QRectF(0, 0, 14, 100))
            p.setPen(Qt.NoPen)
            if winter:                               # снег, нижний край — волной
                sn = QPainterPath(QPointF(0, 0))
                sn.lineTo(QPointF(100, 0))
                sn.lineTo(QPointF(100, 74))
                for i in range(5, 0, -1):          # плавные «подушки» снега
                    x1 = (i - 1) * 20
                    sn.quadTo(QPointF(x1 + 10, 86 + (i % 2) * 3),
                              QPointF(x1, 74))
                sn.closeSubpath()
                sg2 = QLinearGradient(0, 0, 0, 80)
                sg2.setColorAt(0, c("#ffffff"))
                sg2.setColorAt(1, c("#dfe7f0"))
                p.setBrush(QBrush(sg2))
                p.drawPath(sn)
        p.restore()
        # кромки крыши фронтона (ветровая доска) и конёк
        p.setPen(QPen(c("#f0ece4"), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(fx0 - ov, wall_top + ov), apex)
        p.drawLine(apex, e0)
        p.setPen(QPen(c("#5a1d14"), 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(apex, QPointF(apex.x() + dx + 4, apex.y() + dy))
        # водосток
        p.setPen(QPen(c("#b8bec4"), 2))
        p.drawLine(e0, QPointF(e0.x() + dx + 4, e0.y() + dy))
        p.setPen(Qt.NoPen)
        # труба (кирпич) на скате
        # труба ночью темнеет меньше стен (иначе сливалась с небом —
        # «призрак»), кромки и шапка подсвечены луной/небом
        chx, chy = apex.x() + 30, apex.y() + 10
        p.setBrush(c("#9a5037", -0.4))
        p.drawRect(QRectF(chx, chy - 18, 9, 22))
        p.setBrush(c("#6e3624", -0.35))
        p.drawRect(QRectF(chx + 9, chy - 18, 4, 21))
        p.setPen(QPen(c("#5e2c1c", -0.35), 0.55))
        for k in range(1, 5):                      # швы кирпича
            yk = chy - 18 + k * 4.4
            p.drawLine(QPointF(chx, yk), QPointF(chx + 13, yk))
            xo = chx + (4.5 if k % 2 else 2.2)
            p.drawLine(QPointF(xo, yk - 4.4), QPointF(xo, yk))
        p.setPen(Qt.NoPen)
        p.setBrush(c("#6a6460", -0.35))          # оголовок
        p.drawRect(QRectF(chx - 1.5, chy - 21, 16, 3.5))
        p.setBrush(_c("#1a1614", 230))           # закопчённое устье
        p.drawRect(QRectF(chx + 1.5, chy - 22.2, 10, 1.4))
        rim = _c("#c8d4e6", 70 + 90 * night)      # кромка (лунный свет)
        p.setPen(QPen(rim, 0.7))
        p.drawLine(QPointF(chx, chy - 18), QPointF(chx, chy + 3))
        p.drawLine(QPointF(chx - 1.5, chy - 21), QPointF(chx + 14.5, chy - 21))
        p.setPen(Qt.NoPen)
        if winter:
            p.setBrush(c("#f7f9fb"))
            p.drawRoundedRect(QRectF(chx - 2, chy - 24, 16, 4), 2, 2)
        self._chim = (chx, chy)
        # сосульки по водостоку и козырьку — при морозе
        if winter and temp is not None and temp < -2:
            n_ic = 9
            ice = _c("#dff1ff", 210)
            for i in range(n_ic):
                t0 = (i + 0.5) / n_ic
                x = e0.x() + (dx + 4) * t0
                y = e0.y() + dy * t0 + 1
                ln = 2.5 + ((i * 7) % 5) * 1.3 + min(4.0, -temp / 6)
                p.setBrush(ice)
                p.drawPolygon(QPolygonF([QPointF(x - 0.8, y), QPointF(x + 0.8, y),
                                         QPointF(x, y + ln)]))
            for x in (dr.left() - 3, dr.center().x() - 5, dr.right() + 3):
                p.drawPolygon(QPolygonF([QPointF(x - 0.6, cy0 + 3.6),
                                         QPointF(x + 0.6, cy0 + 3.6),
                                         QPointF(x, cy0 + 7)]))
        # штакетник вправо от дома (перед опорой)
        fx_a, fx_b = fx1 + dx + 6, fx1 + dx + 44
        rail = c("#8b6a47", 0.1)
        p.setBrush(rail)
        for yy in (base + dy - 3.5, base + dy - 7.5):
            p.drawRect(QRectF(fx_a, yy, fx_b - fx_a, 1.1))
        x = fx_a + 1
        while x < fx_b:
            p.setBrush(c("#b8926a", 0.1))
            p.drawPolygon(QPolygonF([QPointF(x, base + dy + 1), QPointF(x + 2, base + dy + 1),
                                     QPointF(x + 2, base + dy - 10),
                                     QPointF(x + 1, base + dy - 11.5),
                                     QPointF(x, base + dy - 10)]))
            if winter:
                p.setBrush(c("#f7f9fb"))
                p.drawEllipse(QPointF(x + 1, base + dy - 11.3), 1.4, 0.8)
            x += 4

    def _protons(self, p, sc, anim):
        """Днём по контурам панелей вниз, по кабелю и в щитовую бегут
        жёлтые «протоны»; чем больше выработка — тем быстрее и гуще."""
        g = getattr(self, "_pv_geo", None)
        if not g:
            return
        self._protons_house(p, g, anim)
        if sc["alt"] <= 0:
            return
        gen = g["sun_k"] * (1.0 - 0.75 * min(100, sc["cloud"]) / 100.0)
        if sc["rainy"] or sc["snowy"]:
            gen *= 0.5
        if gen < 0.03:
            return
        v = 14 + 80 * gen                          # px/с
        box = g["box"]
        cab_y = g["cab_y"]
        p.setPen(Qt.NoPen)
        for i, (x, ty, w, h, sk) in enumerate(g["panels"]):
            mid = x + w * 0.5
            # два пути: по левому и по правому краю вниз, к середине низа,
            # вниз к кабелю и по кабелю в щитовую
            for side in (0, 1):
                ex = (x + sk, x) if side == 0 else (x + w + sk, x + w)
                pts = [QPointF(ex[0], ty), QPointF(ex[1], ty + h),
                       QPointF(mid, ty + h), QPointF(mid, cab_y),
                       QPointF(box.left(), cab_y),
                       QPointF(box.left(), box.bottom())]
                seg = []
                tot = 0.0
                for a, b in zip(pts, pts[1:]):
                    L = math.hypot(b.x() - a.x(), b.y() - a.y())
                    seg.append((a, b, L))
                    tot += L
                nd = 2 + int(3 * gen)
                for k in range(nd):
                    d = (anim * v + k * tot / nd + i * 13 + side * 7) % tot
                    for a, b, L in seg:
                        if d <= L:
                            t = d / L if L else 0
                            q = QPointF(a.x() + (b.x() - a.x()) * t,
                                        a.y() + (b.y() - a.y()) * t)
                            break
                        d -= L
                    rg = QRadialGradient(q, 1.7)
                    rg.setColorAt(0, _c("#fff6b0", 240))
                    rg.setColorAt(0.5, _c("#ffd23a", 150))
                    rg.setColorAt(1, _c("#ffb000", 0))
                    p.setBrush(QBrush(rg))
                    p.drawEllipse(q, 1.7, 1.7)
        # огонёк на щитовой — приём энергии
        p.setBrush(_c("#7dff8a", 160 + 90 * math.sin(anim * 5)))
        p.drawEllipse(QPointF(box.right() - 4, box.top() + 5), 1.3, 1.3)

    @staticmethod
    def _protons_house(p, g, anim):
        """Щитовая → дом: ровный поток протонов по кабелю (дом потребляет
        всегда — днём от панелей, ночью от АКБ)."""
        box, cab_y = g["box"], g["cab_y"]
        hx = g.get("house_x")
        if hx is None:
            return
        pts = [QPointF(box.right(), box.bottom()), QPointF(box.right(), cab_y),
               QPointF(hx, cab_y), QPointF(hx, cab_y - 6)]
        seg, tot = [], 0.0
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b.x() - a.x(), b.y() - a.y())
            seg.append((a, b, L))
            tot += L
        if tot <= 0:
            return
        step = 4.5                                   # сплошной поток
        nd = max(2, int(tot / step))
        p.setPen(Qt.NoPen)
        for k in range(nd):
            d = (anim * 22 + k * tot / nd) % tot
            for a, b, L in seg:
                if d <= L:
                    t = d / L if L else 0
                    q = QPointF(a.x() + (b.x() - a.x()) * t,
                                a.y() + (b.y() - a.y()) * t)
                    break
                d -= L
            rg = QRadialGradient(q, 1.5)
            rg.setColorAt(0, _c("#fff6b0", 230))
            rg.setColorAt(0.5, _c("#ffd23a", 140))
            rg.setColorAt(1, _c("#ffb000", 0))
            p.setBrush(QBrush(rg))
            p.drawEllipse(q, 1.5, 1.5)

    @staticmethod
    def smoke_strength(temp, month):
        """0..1 — сколько топят: по температуре (тепло ≥ +12° — не топят,
        −15° и ниже — вовсю). Нет погоды — по месяцу, как раньше."""
        try:
            t = float(temp)
        except (TypeError, ValueError):
            return 0.5 if month in (10, 11, 12, 1, 2, 3) else 0.0
        if t >= 12:
            return 0.0
        return max(0.15, min(1.0, (12.0 - t) / 27.0))

    def _smoke(self, p, night, anim, month, temp=None, wind=None):
        """Дым из трубы: чем сильнее мороз, тем гуще, выше и крупнее;
        ветер сносит его вбок (живой, поверх кэша)."""
        s = self.smoke_strength(temp, month)
        if s <= 0 or not getattr(self, "_chim", None):
            return
        try:
            wv = max(0.0, min(12.0, float(wind or 0)))
        except (TypeError, ValueError):
            wv = 2.0
        chx, chy = self._chim
        n = int(5 + 13 * s)                    # клубов
        rise = 36 + 70 * s                     # высота столба
        drift = 10 + wv * 7                    # снос ветром (влево)
        speed = 0.10 + 0.05 * s
        col_d, col_n = "#e6e9ee", "#9aa3b6"
        p.setPen(Qt.NoPen)
        for i in range(n):
            t = (anim * speed + i / float(n)) % 1.0
            r = (2.6 + t * (7 + 9 * s)) * (0.85 + 0.3 * ((i * 37) % 7) / 6)
            # чем выше — тем сильнее сносит (ветер у земли слабее)
            q = QPointF(chx + 6 - drift * t * t * 1.4 - drift * 0.3 * t
                        + (2 + 3 * s) * math.sin(anim * 1.3 + i * 1.7),
                        chy - 23 - t * rise)
            a = (70 + 110 * s) * (1 - t) ** 1.2
            g = QRadialGradient(q, r)
            base = col_d if night < 0.5 else col_n
            g.setColorAt(0, _c(base, a))
            g.setColorAt(0.6, _c(base, a * 0.55))
            g.setColorAt(1, _c(base, 0))
            p.setBrush(QBrush(g))
            p.drawEllipse(q, r, r * 0.82)

    @staticmethod
    def _window(p, r, dk, lit, winter, side=False, dim=False):
        nc = QColor("#10131a")
        p.setPen(Qt.NoPen)
        t = 1.6 if side else 1.0                 # толщина деталей на боку
        p.setBrush(_c("#000000", 60))            # тень наличника на стене
        p.drawRect(r.adjusted(-2.5 * t + 1, -4.5 * t + 1.2, 2.5 * t + 1,
                              2.5 * t + 1.2))
        p.setBrush(_mix(QColor("#f7f5f0"), nc, dk))
        p.drawRect(r.adjusted(-2.5 * t, -2.5 * t, 2.5 * t, 2.5 * t))
        p.setBrush(_mix(QColor("#fbfaf6"), nc, dk))   # «шапка» наличника
        p.drawRect(QRectF(r.left() - 4 * t, r.top() - 5 * t,
                          r.width() + 8 * t, 2.6 * t))
        if lit and dim:          # после 00:00 — спят: ночник, свет приглушён
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, QColor("#8f6a32"))
            g.setColorAt(1, QColor("#5c3f1c"))
        elif lit:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, QColor("#ffe29a"))
            g.setColorAt(1, QColor("#f0a93e"))
        else:
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, _mix(QColor("#cfe6f7"), nc, dk))
            g.setColorAt(0.5, _mix(QColor("#6f9cc4"), nc, dk))
            g.setColorAt(1, _mix(QColor("#3d5f85"), nc, dk))
        p.setBrush(QBrush(g))
        p.drawRect(r)
        if not lit:                                  # блик на стекле
            p.setBrush(_c("#ffffff", 70 * (1 - dk)))
            p.drawPolygon(QPolygonF([
                QPointF(r.left() + r.width() * 0.15, r.bottom()),
                QPointF(r.left() + r.width() * 0.55, r.top()),
                QPointF(r.left() + r.width() * 0.75, r.top()),
                QPointF(r.left() + r.width() * 0.35, r.bottom())]))
        else:                                        # штора
            p.setBrush(_c("#c9782e", 90))
            p.drawRect(QRectF(r.left(), r.top(), r.width() * 0.22,
                              r.height()))
        p.setBrush(_c("#000000", 70))            # откосы: тень сверху/слева
        p.drawRect(QRectF(r.left(), r.top(), r.width(), 1.3 * t))
        p.drawRect(QRectF(r.left(), r.top(), 1.1 * t, r.height()))
        fr = _mix(QColor("#f7f5f0"), nc, dk)
        p.setPen(QPen(fr, 1.4 if not side else 2.4))
        p.drawLine(QPointF(r.center().x(), r.top()),
                   QPointF(r.center().x(), r.bottom()))
        p.drawLine(QPointF(r.left(), r.top() + r.height() * 0.38),
                   QPointF(r.right(), r.top() + r.height() * 0.38))
        p.setPen(Qt.NoPen)
        p.setBrush(_mix(QColor("#b9b2a6"), nc, dk))   # отлив
        p.drawRect(QRectF(r.left() - 4, r.bottom() + 2.5,
                          r.width() + 8, 2.5 if not side else 5))
        if winter:
            p.setBrush(_mix(QColor("#ffffff"), nc, dk * 0.6))
            p.drawRoundedRect(QRectF(r.left() - 4, r.bottom() + 0.5,
                                     r.width() + 8, 2.2 if not side else 4),
                              1, 1)

    def _precip(self, p, anim, snowy, code):
        heavy = code in (65, 67, 82) or code >= 95
        drizzle = 51 <= code <= 57
        n = len(self._drops) if heavy else (len(self._drops) // 3 if drizzle
                                            else len(self._drops) * 2 // 3)
        if snowy:
            p.setPen(Qt.NoPen)
            near, far = _c("#ffffff", 235), _c("#e8f0ff", 150)
            for i, (fx, fy, sp) in enumerate(self._drops[:n]):
                y = (fy * SCENE_H + anim * 24 * sp) % SCENE_H
                wd = _X1 - _X0
                x = _X0 + (fx * wd + 10 * math.sin(anim * 0.9 + i)) % wd
                p.setBrush(near if sp > 1.0 else far)   # мелкие снежинки
                r = 0.4 + 0.3 * sp
                p.drawEllipse(QPointF(x, y), r, r)
            return
        near, far = [], []
        for fx, fy, sp in self._drops[:n]:
            y = (fy * SCENE_H + anim * 220 * sp) % SCENE_H
            x = _X0 + (fx * (_X1 - _X0) - y * 0.18) % (_X1 - _X0)
            ln = 6 + 6 * sp if not drizzle else 4
            line = (QPointF(x, y), QPointF(x - ln * 0.18, y + ln))
            (near if sp > 1.0 else far).append(line)
        for lines, al, w in ((far, 130, 1.0), (near, 200, 1.3)):
            if lines:
                p.setPen(QPen(_c("#b4d0f5", al), w, Qt.SolidLine,
                              Qt.RoundCap))
                p.drawLines([q for ln in lines for q in ln])

    # ----------------------------------------------- текстовая панель
    def _panel_text(self, p, st, ok, now, lat, lon, tilt, alt, az, malt, maz,
                    illum, phase, code, paz=180.0, zone=(2, True)):
        top = SCENE_H
        g = QLinearGradient(0, top, 0, BASE_H)
        g.setColorAt(0, QColor("#161a20"))
        g.setColorAt(1, QColor("#0d1014"))
        p.fillRect(QRectF(_X0, top, _X1 - _X0, BASE_H - top), g)
        p.setPen(QPen(QColor("#2a3038"), 1))
        p.drawLine(QPointF(_X0, top), QPointF(_X1, top))

        def txt(x, y, s, col="#e8eaed", size=13, w=300, align=Qt.AlignLeft,
                bold=False):
            f = QFont(FONT)
            f.setPixelSize(size)
            f.setBold(bold)
            p.setFont(f)
            p.setPen(QColor(col))
            p.drawText(QRectF(x, y, w, size + 6), align | Qt.AlignVCenter, s)

        y = top + 5
        sl, sr = _X0, _X1 - BASE_W               # к левому / правому краю
        sm = sl * 0.5                            # средняя колонка
        # 4 компактных строки высотой с карточку погоды (справа)
        rs = A.sun_rise_set(lat, lon, now.date(), zone)
        if rs:
            r, s = rs
            dl = s - r
            r, s = r % 1440, s % 1440            # пояс города ≠ пояс ПК
            txt(12 + sl, y, "☀  восход %02d:%02d    закат %02d:%02d"
                % (r // 60, r % 60, s // 60, s % 60), "#ffc93c", 15, 330,
                bold=True)
            day_s = "день %d ч %02d мин" % (dl // 60, dl % 60)
        else:
            txt(12 + sl, y, "☀  полярный день / ночь", "#ffc93c", 15, 330,
                bold=True)
            day_s = ""
        if alt > 0:
            beam = "Солнце %d° · луч к панели %d°" % (
                round(alt), round(max(0, 90 - incidence(alt, az, tilt, paz))))
        else:
            beam = "Солнце под горизонтом"
        txt(12 + sl, y + 21, day_s, "#c6ccd2", 13, 150)
        txt(160 + sm, y + 21, beam, "#c6ccd2", 13, 260)
        txt(12 + sl, y + 41, "☾  Луна %d%%  %s" % (round(illum * 100),
                                              A.phase_name(phase)),
            "#c9d4f0", 13, 250)
        txt(262 + sm, y + 41, "высота %d°  азимут %d°"
            % (round(malt), round(maz)),
            "#8a94a6", 12, 170)
        yy = y + 62
        p.setPen(QPen(QColor("#ffc93c"), 1.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(14 + sl, yy + 8), QPointF(30 + sl, yy + 8))
        txt(36 + sl, yy, "сегодня", "#8a9099", 11, 60)
        for x0, lab in ((104 + sl, "22 июня"), (190 + sl, "22 декабря")):
            pen = QPen(QColor("#b8c0c8"), 0.8, Qt.CustomDashLine)
            pen.setDashPattern([5, 5])
            p.setPen(pen)
            p.drawLine(QPointF(x0, yy + 8), QPointF(x0 + 16, yy + 8))
            txt(x0 + 22, yy, lab, "#8a9099", 11, 80)
        # дата/координаты/город — справа от легенды, до карточки погоды;
        # в узком кадре (4:3, регистратор 704×576) — короче, без наезда
        x_l, x_r = 296 + sl, 434 + sr
        city = st.get("city") or ""
        fnt = QFont(FONT)
        fnt.setPixelSize(11)
        fm = QFontMetrics(fnt)
        for cand in ("%s   %.2f°, %.2f°   %s" % (
                now.strftime("%d.%m.%Y  %H:%M"), lat, lon, city),
                "%s   %s" % (now.strftime("%d.%m.%Y  %H:%M"), city),
                now.strftime("%d.%m.%Y  %H:%M"), now.strftime("%d.%m %H:%M")):
            if fm.horizontalAdvance(cand.strip()) <= x_r - x_l:
                break
        txt(x_l, yy + 1, cand.strip(), "#6b737c", 11, x_r - x_l,
            Qt.AlignRight)
        card = QRectF(440 + sr, top + 7, 190, 78)  # над строкой даты
        p.setPen(QPen(QColor("#262c34"), 1))
        p.setBrush(QColor("#12161b"))
        p.drawRoundedRect(card, 8, 8)
        if not ok:
            txt(card.x(), card.y() + 34, "нет данных о погоде", "#8a9099",
                12, card.width(), Qt.AlignCenter)
            return
        try:
            wx_icon(p, card.x() + 38, card.y() + 38, 24, code, alt < -1)
        except Exception:                               # noqa: BLE001
            pass
        t = st.get("temp")
        if t is not None:
            f = QFont(FONT)
            f.setPixelSize(34)
            f.setBold(True)
            p.setFont(f)
            p.setPen(W.temp_color(t))
            p.drawText(QRectF(card.x() + 76, card.y() + 2, 106, 40),
                       Qt.AlignRight | Qt.AlignVCenter, "%+d°" % round(t))
        txt(card.x() + 70, card.y() + 40, W.wx_word(code) or "—", "#c6ccd2",
            13, 112, Qt.AlignRight)
        wind = st.get("wind")
        parts = []
        if wind is not None:
            parts.append("ветер %d м/с" % round(wind))
        if st.get("pop"):
            parts.append("осадки %d%%" % st.get("pop"))
        txt(card.x() + 6, card.y() + 58, "  ·  ".join(parts), "#8a9099", 11,
            card.width() - 14, Qt.AlignRight)
