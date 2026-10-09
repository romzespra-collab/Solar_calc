"""mod_sun.py  v1.9.4
Положение Солнца (одна формула на всю программу: расчёт, небо, восход/закат), часовой пояс станции
с летним временем ЕС, облучённость плоскости панелей, данные солнца (встроенные / PVGIS).

Журнал:
v1.9.4: погода «reg» — средний день месяца по реальной погоде региона за 5 лет (SunData.reg, архив
        Open-Meteo); нет данных для этой точки — как «средний».
v1.4.0: формула Солнца — NOAA с дробным днём (как в Smart_BMS), разница с v1.3 < 0.1%; правило
        летнего времени ЕС (zone_offset); облучённость панели вынесена в poa() — её же использует
        прогноз выработки по погоде.
v1.3.0: вынесено из solar_calc.pyw v1.2.1 (программа была одним файлом)
"""

import datetime
import math
import threading

from .mod_base import MID_DOY


# ≈ Киев: глобальная горизонтальная, кВт·ч/м²·день, и средняя t воздуха, °C
BUILTIN_SUN = [[0.95, -4.0], [1.70, -3.0], [2.80, 2.0], [4.00, 9.5], [5.30, 15.5], [5.50, 19.0],
               [5.40, 21.0], [4.80, 20.0], [3.30, 14.5], [2.00, 8.5], [1.00, 2.5], [0.70, -2.0]]


DT = 1.0 / 6.0          # шаг 10 минут


N_STEPS = 144


def decl_eot(doy, t_utc):
    """Склонение Солнца (рад) и уравнение времени (мин), NOAA/Spencer, дробный день года."""
    B = 2 * math.pi * (doy - 1 + (t_utc - 12.0) / 24.0) / 365.0
    decl = (0.006918 - 0.399912 * math.cos(B) + 0.070257 * math.sin(B) - 0.006758 * math.cos(2 * B)
            + 0.000907 * math.sin(2 * B) - 0.002697 * math.cos(3 * B) + 0.00148 * math.sin(3 * B))
    eot = 229.18 * (0.000075 + 0.001868 * math.cos(B) - 0.032077 * math.sin(B)
                    - 0.014615 * math.cos(2 * B) - 0.040849 * math.sin(2 * B))
    return decl, eot


def sun(lat, lon, doy, t_utc):
    """→ (cos зенита, зенит рад, азимут от юга рад (+запад), внеатм. облучённость).
    NOAA: склонение и уравнение времени по дробному дню года; t_utc — часы UTC."""
    decl, eot = decl_eot(doy, t_utc)
    st = t_utc + lon / 15.0 + eot / 60.0
    w = math.radians(15.0 * (st - 12.0))
    phi = math.radians(lat)
    cosz = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(w)
    cosz = max(-1.0, min(1.0, cosz))
    zen = math.acos(cosz)
    az = math.atan2(math.sin(w), math.cos(w) * math.sin(phi) - math.tan(decl) * math.cos(phi))
    g0 = 1367.0 * (1 + 0.033 * math.cos(2 * math.pi * doy / 365.0))
    return cosz, zen, az, g0


def _last_sunday(year, month):
    d = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1) if month < 12 else datetime.date(year, 12, 31)
    return d - datetime.timedelta(days=(d.weekday() + 1) % 7)


def dst_on(utc):
    """Летнее время ЕС/Украина: с последнего воскресенья марта 01:00 UTC до последнего воскресенья октября."""
    y = utc.year
    a = datetime.datetime.combine(_last_sunday(y, 3), datetime.time(1))
    b = datetime.datetime.combine(_last_sunday(y, 10), datetime.time(1))
    return a <= utc.replace(tzinfo=None) < b


def zone_offset(tz, dst, utc):
    """Смещение местного времени станции от UTC, часы (зимний пояс + летнее время)."""
    return float(tz) + (1.0 if dst and dst_on(utc) else 0.0)


def poa(G, D, cosz, zen, az, g0, geom):
    """Облучённость плоскости панелей, Вт/м². G — глобальная горизонтальная, D — рассеянная (None —
    по Erbs), geom = (cos наклона, sin наклона, азимут панели рад, горизонт °, альбедо)."""
    if cosz <= 0.0 or G <= 0.0:
        return 0.0
    cb, sb, asp, hor, alb = geom
    if D is None:
        D = G * erbs_kd(min(1.0, G / (g0 * cosz)))
    B = max(0.0, G - D)
    elev = 90.0 - math.degrees(zen)
    beam = 0.0
    if B > 0 and cosz > 0.035 and elev > hor:
        dni = min(B / cosz, 1050.0)
        ct = cosz * cb + math.sin(zen) * sb * math.cos(az - asp)
        if ct > 0:
            iam = max(0.0, 1 - 0.05 * (1 / max(ct, 0.05) - 1))
            beam = dni * ct * iam
    return beam + D * (1 + cb) / 2 * 0.95 + G * alb * (1 - cb) / 2


def panel_geom(s, alb):
    tilt = math.radians(float(s["tilt"]))
    return math.cos(tilt), math.sin(tilt), math.radians(float(s["aspect"])), float(s["horizon"]), alb


def haurwitz(cosz):
    return 1098.0 * cosz * math.exp(-0.057 / cosz) if cosz > 0.01 else 0.0


def erbs_kd(kt):
    if kt <= 0.22:
        return 1 - 0.09 * kt
    if kt <= 0.8:
        return 0.9511 - 0.1604 * kt + 4.388 * kt ** 2 - 16.638 * kt ** 3 + 12.336 * kt ** 4
    return 0.165


def interp24(arr, x):
    x %= 24.0
    i = int(x)
    f = x - i
    return arr[i] * (1 - f) + arr[(i + 1) % 24] * f


class SunData:
    def __init__(self, cfg):
        self.builtin = [list(map(float, r)) for r in cfg.get("builtin") or BUILTIN_SUN]
        self.pv = cfg.get("pvgis")
        self.enabled = bool(cfg.get("use_pvgis", True))
        self.reg = cfg.get("region")                   # погода региона за 5 лет (mod_region)

    def use_reg(self, lat, lon):
        rg = self.reg
        return bool(rg and abs(rg.get("lat", 999) - lat) < 0.06 and abs(rg.get("lon", 999) - lon) < 0.06
                    and len(rg.get("months", [])) == 12)

    def use_pv(self, lat, lon):
        pv = self.pv
        return bool(self.enabled and pv and abs(pv.get("lat", 999) - lat) < 0.06
                    and abs(pv.get("lon", 999) - lon) < 0.06 and len(pv.get("months", [])) == 12)

    def tag(self, lat, lon):
        rg = ("rg", self.reg.get("stamp", "")) if self.use_reg(lat, lon) else ("rg-",)
        if self.use_pv(lat, lon):
            return ("pv", self.pv["lat"], self.pv["lon"], self.pv.get("stamp", "")) + rg
        return ("bi", tuple(tuple(r) for r in self.builtin)) + rg

    def label(self, lat, lon):
        if self.use_pv(lat, lon):
            return f"PVGIS ({self.pv['lat']:.2f}, {self.pv['lon']:.2f})"
        return "встроенные (≈Киев)"


_IRR_CACHE = {}


_IRR_LOCK = threading.Lock()


def irr_day(s, sd, m, w):
    """Средний день месяца m при погоде w → [(час местный, POA Вт/м², t воздуха)]."""
    lat, lon = float(s["lat"]), float(s["lon"])
    key = (lat, lon, float(s["tilt"]), float(s["aspect"]), float(s["horizon"]), float(s["tz"]),
           bool(s["dst"]), float(s["overcast_k"]), m, w, sd.tag(lat, lon))
    with _IRR_LOCK:
        hit = _IRR_CACHE.get(key)
    if hit is not None:
        return hit
    if w == "reg" and not sd.use_reg(lat, lon):
        return irr_day(s, sd, m, "avg")                # погоды региона нет — как «средний»
    tz = zone_offset(s["tz"], s["dst"], datetime.datetime(2025, m + 1, 15, 12))   # середина месяца
    ko = float(s["overcast_k"]) / 100.0
    geom = panel_geom(s, 0.35 if m in (0, 1, 11) else 0.2)
    doy = MID_DOY[m]
    geo = [sun(lat, lon, doy, (i + 0.5) * DT) for i in range(N_STEPS)]
    ghi = [0.0] * N_STEPS
    dhi = [None] * N_STEPS
    ta = [0.0] * N_STEPS
    pv = sd.pv["months"][m] if sd.use_pv(lat, lon) else None
    if w == "reg":
        pv = sd.reg["months"][m]                       # реальная погода региона — как «средний» по своему профилю
    if pv is None:
        H, Tm = sd.builtin[m]
        cs = [haurwitz(g[0]) for g in geo]
        if w == "avg":
            tot = sum(cs) * DT
            k = min(1.0, H * 1000.0 / tot) if tot > 0 else 0.0
            ghi = [c * k for c in cs]
        elif w == "clear":
            ghi = cs
        else:
            ghi = [c * ko for c in cs]
        amp = {"clear": 5.0, "avg": 3.5, "over": 1.5}[w]
        for i in range(N_STEPS):
            tl = (i + 0.5) * DT + tz
            ta[i] = Tm + amp * math.cos(2 * math.pi * (tl - 15.0) / 24.0)
    else:
        sh = pv.get("shift", 0.0)
        for i, g in enumerate(geo):
            x = (i + 0.5) * DT - sh
            ta[i] = interp24(pv["t"], x)
            if g[0] <= 0:
                continue
            if w in ("avg", "reg"):
                G = interp24(pv["ghi"], x)
                ghi[i] = G
                dhi[i] = min(G, interp24(pv["dhi"], x))
            elif w == "clear":
                ghi[i] = interp24(pv["gcs"], x)
            else:
                ghi[i] = interp24(pv["gcs"], x) * ko
    out = []
    for i, (cosz, zen, az, g0) in enumerate(geo):
        tl = ((i + 0.5) * DT + tz) % 24.0
        G = ghi[i]
        D = G if w == "over" else dhi[i]
        out.append((tl, poa(G, D, cosz, zen, az, g0, geom), ta[i]))
    out.sort()
    with _IRR_LOCK:
        if len(_IRR_CACHE) > 4000:
            _IRR_CACHE.clear()
        _IRR_CACHE[key] = out
    return out
