"""mod_region.py  v1.10.0
Погода «по региону»: реальная погода за 5 полных лет для точки станции → средний день каждого месяца по часам
(солнце на горизонт, рассеянное, температура), сумма солнца по годам и по месяцам каждого года, сколько было
ясных / переменных / пасмурных дней и часов солнца. Источники: архив Open-Meteo (ERA5, последние 5 лет) или
PVGIS-SARAH3 (спутник, 2019–2023) — оба без ключа.

Журнал:
v1.10.0: статистика дней (stats): ясный день — пришло ≥ 70 % от ясного неба, пасмурный — < 35 %, час солнца —
         прямое > 120 Вт/м² (как у метеостанций), дни с солнцем ≥ 1 ч, кВт·ч/м² по месяцам; month_year —
         кВт·ч/м² по месяцам каждого года (разброс выработки по годам); источник PVGIS-SARAH3 (seriescalc).
v1.9.7: проверка сохранённых данных — в mod_config.profile_ok (строже: числа, без null).
v1.9.4: первая версия.
"""

import datetime
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .mod_base import log
from .mod_sun import sun, haurwitz

URL = "https://archive-api.open-meteo.com/v1/archive"
URL_PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc"
YEARS = 5
PVGIS_LAST = 2023                                       # последний год PVGIS-SARAH3
SOURCES = (("om", "Open-Meteo (ERA5)"), ("pvgis", "PVGIS-SARAH3"))
SRC_NAMES = dict(SOURCES)
STAT_KEYS = ("sunny", "partly", "cloudy", "sunday", "sun_h", "ghi")


def region_years(today=None, n=YEARS, src="om"):
    """Последние n полных лет: (первый, последний); у PVGIS-SARAH3 — по 2023."""
    y = PVGIS_LAST if src == "pvgis" else (today or datetime.date.today()).year - 1
    return y - n + 1, y


def parse_region(data, lat, lon, y0, y1, src="om"):
    """Ответ в виде Open-Meteo (hourly, время UTC — конец часа) → {lat, lon, years, days, stamp, src, months:
    [{ghi, dhi, t (24 ч), H, T, shift}], year_h: {год: кВт·ч/м²}, month_year: {год: [12 × кВт·ч/м²]}, stats:
    {sunny, partly, cloudy, sunday, sun_h, ghi: [12 — среднее за годы]}}. Солнце — среднее за ПРЕДЫДУЩИЙ час:
    значение на T:00 кладётся в час T−1 (интервал [T−1, T]), shift = 0.5 — расчёт берёт середину часа."""
    hr = (data or {}).get("hourly") or {}
    times = hr.get("time") or []
    ghi, dhi, tmp = hr.get("shortwave_radiation") or [], hr.get("diffuse_radiation") or [], hr.get("temperature_2m") or []
    if not times or len(ghi) != len(times):
        raise RuntimeError("в ответе нет почасового солнца")
    acc = [{"g": [0.0] * 24, "d": [0.0] * 24, "t": [0.0] * 24, "ng": [0] * 24, "nd": [0] * 24, "nt": [0] * 24}
           for _ in range(12)]
    year_h, days = {}, set()
    month_year = {}
    daily = {}                                          # день (UTC) → [Σ ghi, Σ ясное небо, часов солнца]
    for i, ts in enumerate(times):
        try:
            d = datetime.datetime.strptime(ts[:13], "%Y-%m-%dT%H")
        except (TypeError, ValueError):
            continue
        start = d - datetime.timedelta(hours=1)                 # солнце: среднее за час [T−1, T]
        a = acc[start.month - 1]
        h = start.hour
        g = ghi[i] if y0 <= start.year <= y1 else None          # первый час 1 января — ещё прошлый год
        if g is not None:
            g = float(g)
            a["g"][h] += g
            a["ng"][h] += 1
            year_h[start.year] = year_h.get(start.year, 0.0) + g / 1000.0
            my = month_year.setdefault(start.year, [0.0] * 12)
            my[start.month - 1] += g / 1000.0
            days.add(start.date())
        x = dhi[i] if i < len(dhi) and g is not None else None
        if x is not None:
            a["d"][h] += float(x)
            a["nd"][h] += 1
        if g is not None:                                       # ясный / пасмурный день, часы солнца
            cz = sun(lat, lon, start.timetuple().tm_yday, h + 0.5)[0]
            dd = daily.setdefault(start.date(), [0.0, 0.0, 0.0])
            dd[0] += g
            dd[1] += haurwitz(cz)
            dif = float(x) if x is not None else g * 0.5
            if cz > 0.1 and (g - dif) / cz > 120.0:
                dd[2] += 1.0
        t0 = tmp[i] if i < len(tmp) else None                  # температура — мгновенная: середина часа
        t1 = tmp[i + 1] if i + 1 < len(tmp) else None          # [T, T+1] = среднее двух замеров
        if t0 is not None:
            tv = (float(t0) + float(t1)) / 2 if t1 is not None else float(t0)
            b = acc[d.month - 1]
            b["t"][d.hour] += tv
            b["nt"][d.hour] += 1
    months = []
    for m, a in enumerate(acc):
        if not any(a["ng"]):
            raise RuntimeError(f"нет данных за месяц {m + 1}")
        g = [a["g"][h] / a["ng"][h] if a["ng"][h] else 0.0 for h in range(24)]
        dd = [min(g[h], a["d"][h] / a["nd"][h]) if a["nd"][h] else g[h] * 0.5 for h in range(24)]
        known = [a["t"][h] / a["nt"][h] for h in range(24) if a["nt"][h]]
        tm = sum(known) / len(known) if known else 10.0
        t = [a["t"][h] / a["nt"][h] if a["nt"][h] else tm for h in range(24)]
        months.append({"ghi": [round(v, 1) for v in g], "dhi": [round(v, 1) for v in dd], "t": [round(v, 2) for v in t],
                       "H": round(sum(g) / 1000.0, 3), "T": round(sum(t) / 24.0, 2), "shift": 0.5})
    full = {y: round(v, 1) for y, v in sorted(year_h.items()) if y0 <= y <= y1}
    # статистика дней: сначала по каждому году-месяцу, потом среднее за годы (неполные годы не в счёт)
    per = {}
    for day, (gs, css, sh) in daily.items():
        if day.year not in full:
            continue
        r = per.setdefault((day.year, day.month - 1), {k: 0.0 for k in STAT_KEYS})
        kc = gs / css if css > 0 else 0.0
        r["sunny" if kc >= 0.7 else "partly" if kc >= 0.35 else "cloudy"] += 1
        if sh >= 1:
            r["sunday"] += 1
        r["sun_h"] += sh
        r["ghi"] += gs / 1000.0
    stats = {k: [0.0] * 12 for k in STAT_KEYS}
    for m in range(12):
        rows = [per[(y, m)] for y in full if (y, m) in per]
        for k in STAT_KEYS:
            stats[k][m] = round(sum(r[k] for r in rows) / len(rows), 2) if rows else 0.0
    my = {str(y): [round(v, 2) for v in month_year[y]] for y in full if y in month_year}
    return {"lat": round(lat, 4), "lon": round(lon, 4), "years": f"{y0}–{y1}", "days": len(days), "src": src,
            "stamp": time.strftime("%Y-%m-%d %H:%M"), "months": months, "year_h": {str(k): v for k, v in full.items()},
            "month_year": my, "stats": stats}


def pvgis_to_hourly(data):
    """Ответ PVGIS seriescalc (angle=0, components=1; время «YYYYMMDD:HHMM» UTC) → вид Open-Meteo: время — конец
    часа, солнце на горизонт = Gb + Gd, рассеянное = Gd, температура T2m."""
    rows = ((data or {}).get("outputs") or {}).get("hourly") or []
    if not rows:
        raise RuntimeError((data or {}).get("message") or "в ответе PVGIS нет почасовых данных")
    times, gh, dh, tt = [], [], [], []
    for r in rows:
        s = str(r.get("time", ""))
        try:
            t = datetime.datetime(int(s[0:4]), int(s[4:6]), int(s[6:8]), int(s[9:11])) + datetime.timedelta(hours=1)
        except (TypeError, ValueError):
            continue
        try:
            if "Gb(i)" in r:
                gb, gd = float(r.get("Gb(i)") or 0.0), float(r.get("Gd(i)") or 0.0)
                g, d = gb + gd, gd
            else:
                g, d = float(r.get("G(i)") or 0.0), None
            tv = r.get("T2m")
            tv = float(tv) if tv is not None else None
        except (TypeError, ValueError):
            continue
        times.append(t.strftime("%Y-%m-%dT%H:00"))
        gh.append(max(0.0, g))
        dh.append(d)
        tt.append(tv)
    return {"hourly": {"time": times, "shortwave_radiation": gh, "diffuse_radiation": dh, "temperature_2m": tt}}


def _get_json(url, ua, timeout=150):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_region(lat, lon, ua="solar_calc", src="om"):
    """Скачать погоду за 5 полных лет для точки и посчитать средние дни месяцев и статистику дней."""
    src = src if src in SRC_NAMES else "om"
    y0, y1 = region_years(src=src)
    if src == "pvgis":
        q = urllib.parse.urlencode({"lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "startyear": y0, "endyear": y1,
                                    "angle": 0, "aspect": 0, "components": 1, "outputformat": "json"})
        url = f"{URL_PVGIS}?{q}"
    else:
        q = urllib.parse.urlencode({"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": f"{y0}-01-01",
                                    "end_date": f"{y1}-12-31", "hourly": "shortwave_radiation,diffuse_radiation,temperature_2m",
                                    "timezone": "GMT"})
        url = f"{URL}?{q}"
    log.info(f"⏳ Погода региона за {y0}–{y1} ({lat:.2f}, {lon:.2f}): запрос к {SRC_NAMES[src]}…")
    last = "нет ответа"
    for attempt in range(2):
        try:
            data = _get_json(url, ua)
            if src == "pvgis":
                data = pvgis_to_hourly(data)
            elif data.get("error"):
                raise RuntimeError(data.get("reason") or "ошибка архива")
            return parse_region(data, lat, lon, y0, y1, src)
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8", "replace"))
                last = f"HTTP {e.code} {body.get('reason') or body.get('message') or ''}".strip()
            except Exception:
                last = f"HTTP {e.code}"
        except urllib.error.URLError as e:
            last = f"нет связи ({e.reason})"
        except Exception as e:
            last = str(e)
        log.warning(f"⚠ Погода региона: {last}" + (" — ещё попытка" if attempt == 0 else ""))
    raise RuntimeError(last)
