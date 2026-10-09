"""mod_weather.py  v1.4.0
Погода Open-Meteo (бесплатно, без ключа) для места станции: сейчас, по часам, по дням — и радиация по
часам на 6 дней (глобальная + рассеянная) для прогноза выработки тем же расчётом, что и вся программа.
Ночь/день у значков — по реальной высоте Солнца (mod_astro). Поиск города — геокодер Open-Meteo.

Журнал:
v1.4.0: перенесено из Smart_BMS 4.81 (weather.py) и согласовано со станцией: место — из настроек
        станции, время — UTC по ответу сервиса, + радиация и снег по часам, + поиск города.
"""

import datetime as dt
import json
import math
import threading
import time
import urllib.parse
import urllib.request

from .mod_astro import sun_altaz_utc

MODELS = (("best_match", "Авто"), ("ecmwf_ifs025", "ECMWF"), ("icon_seamless", "ICON"),
          ("gfs_seamless", "GFS"), ("meteofrance_seamless", "Météo-France"), ("ukmo_seamless", "UKMO"))
POLLS = (15, 30, 60, 120)


# ─────────────── подписи ───────────────
def wx_word(c):
    c = int(c or 0)
    if c == 0:
        return "ясно"
    if c in (1, 2):
        return "малооблачно"
    if c == 3:
        return "пасмурно"
    if c in (45, 48):
        return "туман"
    if 51 <= c <= 57:
        return "морось"
    if (61 <= c <= 65) or c in (80, 81):
        return "дождь"
    if c in (66, 67, 82):
        return "ливень"
    if (71 <= c <= 77) or c in (85, 86):
        return "снег"
    if c >= 95:
        return "гроза"
    return ""


def wind_word(deg):
    return ("С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ")[((int(deg or 0) + 22) // 45) & 7]


def dow_word(wd):
    return ("Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб")[((wd % 7) + 7) % 7]


_TCP = [(-20, 40, 90, 210), (-8, 90, 165, 235), (2, 200, 225, 245), (10, 238, 244, 246),
        (18, 245, 235, 140), (26, 250, 190, 70), (34, 245, 130, 45), (50, 235, 45, 35)]


def temp_rgb(t):
    """Цвет температуры: тёмно-голубой (−20) → красный (+50), (r, g, b)."""
    if t is None or (isinstance(t, float) and math.isnan(t)):
        return 230, 230, 230
    if t <= _TCP[0][0]:
        return _TCP[0][1:]
    if t >= _TCP[-1][0]:
        return _TCP[-1][1:]
    for i in range(1, len(_TCP)):
        if t <= _TCP[i][0]:
            f = (t - _TCP[i - 1][0]) / float(_TCP[i][0] - _TCP[i - 1][0])
            return tuple(int(_TCP[i - 1][j] + (_TCP[i][j] - _TCP[i - 1][j]) * f) for j in (1, 2, 3))
    return 230, 230, 230


def temp_color(t):
    from PySide6.QtGui import QColor
    return QColor(*temp_rgb(t))


# ─────────────── состояние ───────────────
class WeatherState:
    """Последний ответ сервиса. Пишет фоновая задача, читает интерфейс (snapshot)."""

    def __init__(self):
        self.lock = threading.Lock()
        self.on = True
        self.city, self.lat, self.lon, self.model = "", 50.45, 30.52, "best_match"
        self.ok, self.err, self.updated = False, "", 0.0
        self.cur = {}            # temp, feels, code, cloud, hum, press, wind, wind_dir, is_day, ghi, dhi
        self.hourly = []         # ближайшие 8 ч: {hh, t, code, pop, night}
        self.daily = []          # 6 дней: {date, dow, dd, mm, code, max, min, pop}
        self.fc = []             # по часам на 6 дней: {u — конец часа UTC, ghi, dhi, t, cloud, code, snow}

    def apply(self, d):
        with self.lock:
            for k, v in d.items():
                setattr(self, k, v)

    def snapshot(self):
        with self.lock:
            c = dict(self.cur)
            return dict(on=self.on, ok=self.ok, err=self.err, city=self.city, lat=self.lat, lon=self.lon,
                        updated=self.updated, hourly=list(self.hourly), daily=list(self.daily),
                        temp=c.get("temp"), feels=c.get("feels"), code=c.get("code", 0), cloud=c.get("cloud", 0),
                        hum=c.get("hum"), press=c.get("press"), wind=c.get("wind"), wind_dir=c.get("wind_dir", 0),
                        is_day=c.get("is_day", True), ghi=c.get("ghi"), dhi=c.get("dhi"),
                        pop=max((h["pop"] for h in self.hourly), default=0))


# ─────────────── запросы ───────────────
_CUR = ("temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,cloud_cover,surface_pressure,"
        "wind_speed_10m,wind_direction_10m,is_day,shortwave_radiation,diffuse_radiation")
_HOUR = ("temperature_2m,weather_code,precipitation_probability,cloud_cover,shortwave_radiation,"
         "diffuse_radiation,snow_depth")
_DAY = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"


def build_url(lat, lon, model):
    q = dict(latitude=f"{lat:.4f}", longitude=f"{lon:.4f}", current=_CUR, hourly=_HOUR, daily=_DAY,
             wind_speed_unit="ms", forecast_days=6, timezone="auto")
    if model and model != "best_match":
        q["models"] = model
    return "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q, safe=",")


def _get(url, ua, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _f(v):
    try:
        x = float(v)
        return None if math.isnan(x) else x
    except (TypeError, ValueError):
        return None


def parse(doc, lat, lon, now_utc=None):
    """Ответ Open-Meteo → словарь для WeatherState.apply(). Время — в UTC (по utc_offset_seconds)."""
    if not isinstance(doc, dict) or not isinstance(doc.get("current"), dict):
        raise RuntimeError("в ответе нет текущей погоды")
    now_utc = now_utc or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    off = dt.timedelta(seconds=int(doc.get("utc_offset_seconds") or 0))
    c = doc["current"]
    cur = dict(temp=_f(c.get("temperature_2m")), feels=_f(c.get("apparent_temperature")),
               code=int(_f(c.get("weather_code")) or 0), cloud=int(_f(c.get("cloud_cover")) or 0),
               hum=None if _f(c.get("relative_humidity_2m")) is None else int(_f(c.get("relative_humidity_2m"))),
               press=_f(c.get("surface_pressure")), wind=_f(c.get("wind_speed_10m")),
               wind_dir=int(_f(c.get("wind_direction_10m")) or 0), is_day=bool(_f(c.get("is_day")) or 0),
               ghi=_f(c.get("shortwave_radiation")), dhi=_f(c.get("diffuse_radiation")))
    h = doc.get("hourly") or {}
    times = h.get("time") or []

    def col(name):
        a = h.get(name) or []
        return [(_f(a[i]) if i < len(a) else None) for i in range(len(times))]
    T, CODE, POP, CL, GHI, DHI, SNOW = (col(n) for n in ("temperature_2m", "weather_code", "precipitation_probability",
                                                         "cloud_cover", "shortwave_radiation", "diffuse_radiation",
                                                         "snow_depth"))
    fc, hourly = [], []
    for i, ts in enumerate(times):
        try:
            u = dt.datetime.fromisoformat(ts[:16]) - off
        except ValueError:
            continue
        fc.append(dict(u=u, ghi=GHI[i], dhi=DHI[i], t=T[i], cloud=CL[i], code=int(CODE[i] or 0), snow=SNOW[i]))
        if u >= now_utc - dt.timedelta(minutes=59) and len(hourly) < 8 and T[i] is not None:
            alt, _ = sun_altaz_utc(lat, lon, u)
            hourly.append(dict(hh=(u + off).hour, t=int(round(T[i])), code=int(CODE[i] or 0),
                               pop=int(POP[i] or 0), night=alt < -0.833))
    d = doc.get("daily") or {}
    daily = []
    for i, ds in enumerate((d.get("time") or [])[:6]):
        try:
            day = dt.date.fromisoformat(ds[:10])
        except ValueError:
            continue

        def dv(name, i=i):
            a = d.get(name) or []
            return _f(a[i]) if i < len(a) else None
        daily.append(dict(date=day, dow=day.isoweekday() % 7, dd=day.day, mm=day.month,
                          code=int(dv("weather_code") or 0), max=int(round(dv("temperature_2m_max") or 0)),
                          min=int(round(dv("temperature_2m_min") or 0)),
                          pop=int(dv("precipitation_probability_max") or 0)))
    if not fc:
        raise RuntimeError("в ответе нет прогноза по часам")
    return dict(ok=True, err="", updated=time.time(), cur=cur, hourly=hourly, daily=daily, fc=fc)


def fetch(lat, lon, model, ua="solar_calc"):
    return parse(_get(build_url(lat, lon, model), ua), lat, lon)


def geocode(name, ua="solar_calc"):
    """Город → [(подпись, широта, долгота)] (до 8 вариантов)."""
    q = urllib.parse.urlencode(dict(name=name, count=8, language="ru", format="json"))
    doc = _get("https://geocoding-api.open-meteo.com/v1/search?" + q, ua)
    out = []
    for r in (doc.get("results") or []) if isinstance(doc, dict) else []:
        la, lo = _f(r.get("latitude")), _f(r.get("longitude"))
        if la is None or lo is None:
            continue
        lab = ", ".join(x for x in (r.get("name"), r.get("admin1"), r.get("country")) if x)
        out.append((lab, la, lo))
    return out
