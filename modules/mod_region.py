"""mod_region.py  v1.9.4
Погода «по региону»: реальная погода за последние 5 полных лет для точки станции (архив Open-Meteo, без ключа)
→ средний день каждого месяца по часам (солнце на горизонт, рассеянное, температура) и сумма солнца по годам.

Журнал:
v1.9.4: первая версия.
"""

import datetime
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from .mod_base import log

URL = "https://archive-api.open-meteo.com/v1/archive"
YEARS = 5


def region_years(today=None, n=YEARS):
    """Последние n полных лет: (первый, последний)."""
    y = (today or datetime.date.today()).year - 1
    return y - n + 1, y


def parse_region(data, lat, lon, y0, y1):
    """Ответ Open-Meteo (hourly, время UTC) → {lat, lon, years, days, stamp, months: [{ghi, dhi, t (24 ч), H, T,
    shift}], year_h: {год: кВт·ч/м²}}. Солнце в архиве — среднее за ПРЕДЫДУЩИЙ час: значение на T:00 кладётся
    в час T−1 (интервал [T−1, T]), shift = 0.5 — расчёт берёт середину часа."""
    hr = (data or {}).get("hourly") or {}
    times = hr.get("time") or []
    ghi, dhi, tmp = hr.get("shortwave_radiation") or [], hr.get("diffuse_radiation") or [], hr.get("temperature_2m") or []
    if not times or len(ghi) != len(times):
        raise RuntimeError("в ответе нет почасового солнца")
    acc = [{"g": [0.0] * 24, "d": [0.0] * 24, "t": [0.0] * 24, "ng": [0] * 24, "nd": [0] * 24, "nt": [0] * 24}
           for _ in range(12)]
    year_h, days = {}, set()
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
            a["g"][h] += float(g)
            a["ng"][h] += 1
            year_h[start.year] = year_h.get(start.year, 0.0) + float(g) / 1000.0
            days.add(start.date())
        x = dhi[i] if i < len(dhi) and g is not None else None
        if x is not None:
            a["d"][h] += float(x)
            a["nd"][h] += 1
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
    return {"lat": round(lat, 4), "lon": round(lon, 4), "years": f"{y0}–{y1}", "days": len(days),
            "stamp": time.strftime("%Y-%m-%d %H:%M"), "months": months, "year_h": {str(k): v for k, v in full.items()}}


def fetch_region(lat, lon, ua="solar_calc"):
    """Скачать погоду за последние 5 полных лет для точки и посчитать средние дни месяцев."""
    y0, y1 = region_years()
    q = urllib.parse.urlencode({"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": f"{y0}-01-01",
                                "end_date": f"{y1}-12-31", "hourly": "shortwave_radiation,diffuse_radiation,temperature_2m",
                                "timezone": "GMT"})
    log.info(f"⏳ Погода региона за {y0}–{y1} ({lat:.2f}, {lon:.2f}): запрос к архиву Open-Meteo…")
    last = "нет ответа"
    for attempt in range(2):
        try:
            req = urllib.request.Request(f"{URL}?{q}", headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            if data.get("error"):
                raise RuntimeError(data.get("reason") or "ошибка архива")
            return parse_region(data, lat, lon, y0, y1)
        except urllib.error.HTTPError as e:
            try:
                last = f"HTTP {e.code} {json.loads(e.read().decode('utf-8', 'replace')).get('reason', '')}".strip()
            except Exception:
                last = f"HTTP {e.code}"
        except urllib.error.URLError as e:
            last = f"нет связи ({e.reason})"
        except Exception as e:
            last = str(e)
        log.warning(f"⚠ Погода региона: {last}" + (" — ещё попытка" if attempt == 0 else ""))
    raise RuntimeError(last)


def region_ok(rg):
    """Проверка сохранённых данных (config.json)."""
    try:
        float(rg["lat"]), float(rg["lon"])
        return len(rg["months"]) == 12 and all(
            len(m[k]) == 24 for m in rg["months"] for k in ("ghi", "dhi", "t")) and \
            all(isinstance(m["H"], (int, float)) and isinstance(m["T"], (int, float)) for m in rg["months"])
    except Exception:
        return False
