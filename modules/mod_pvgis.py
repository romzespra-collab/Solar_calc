"""mod_pvgis.py  v1.3.0
загрузка и разбор данных PVGIS (Еврокомиссия)

Журнал:
v1.3.0: вынесено из solar_calc.pyw v1.2.1 (программа была одним файлом)
"""

import json
import time
import urllib.request
import urllib.error

from .mod_base import MID_DOY, log
from .mod_sun import DT, N_STEPS, sun, haurwitz


def _find_rows(o):
    if isinstance(o, list) and o and isinstance(o[0], dict) and "time" in o[0]:
        return o
    if isinstance(o, dict):
        for v in o.values():
            r = _find_rows(v)
            if r:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find_rows(v)
            if r:
                return r
    return None


def _num(row, *names):
    for n in names:
        if n in row and row[n] is not None:
            try:
                return float(row[n])
            except (TypeError, ValueError):
                pass
    return None


def parse_pvgis(data, lat, lon, builtin):
    rows = _find_rows(data)
    if not rows:
        raise RuntimeError("в ответе PVGIS нет daily_profile")
    months = [{"ghi": [0.0] * 24, "dhi": [0.0] * 24, "gcs": [0.0] * 24, "t": [None] * 24} for _ in range(12)]
    for r in rows:
        mo = int(_num(r, "month") or 0)
        if not 1 <= mo <= 12:
            continue
        try:
            h = int(str(r.get("time", "0")).split(":")[0]) % 24
        except ValueError:
            continue
        d = months[mo - 1]
        g = _num(r, "G(i)", "G(h)", "G") or 0.0
        gb = _num(r, "Gb(i)", "Gb(n)", "Gb")
        gd = _num(r, "Gd(i)", "Gd")
        d["ghi"][h] = g
        d["dhi"][h] = gd if gd is not None else (max(0.0, g - gb) if gb is not None else g * 0.5)
        d["gcs"][h] = _num(r, "Gcs(i)", "Gcs") or 0.0
        d["t"][h] = _num(r, "T2m")
    if not any(sum(d["ghi"]) > 0 for d in months):
        raise RuntimeError("в ответе PVGIS нет данных облучённости")
    for m, d in enumerate(months):
        if all(v is None for v in d["t"]):
            d["t"] = [builtin[m][1]] * 24
        else:
            known = [v for v in d["t"] if v is not None]
            d["t"] = [v if v is not None else sum(known) / len(known) for v in d["t"]]
        if sum(d["gcs"]) <= 0:
            d["gcs"] = [max(g, 0.0) * 1.4 for g in d["ghi"]]
        ref = d["gcs"] if sum(d["gcs"]) > 0 else d["ghi"]
        tot = sum(ref)
        if tot > 0:
            c_pv = sum(h * v for h, v in enumerate(ref)) / tot
            cs = [haurwitz(sun(lat, lon, MID_DOY[m], (i + 0.5) * DT)[0]) for i in range(N_STEPS)]
            ct = sum(cs)
            c_me = sum((i + 0.5) * DT * v for i, v in enumerate(cs)) / ct if ct > 0 else c_pv
            d["shift"] = max(-1.5, min(1.5, c_me - c_pv))
        else:
            d["shift"] = 0.0
        d["H"] = sum(d["ghi"]) / 1000.0
        d["T"] = sum(d["t"]) / 24.0
    return {"lat": round(lat, 4), "lon": round(lon, 4), "months": months,
            "stamp": time.strftime("%Y-%m-%d %H:%M")}


def fetch_pvgis(lat, lon, builtin, ua="solar_calc"):
    params = (f"lat={lat:.4f}&lon={lon:.4f}&month=0&angle=0&aspect=0&global=1&clearsky=1"
              f"&showtemperatures=1&outputformat=json")
    last = "нет ответа"
    for ver in ("v5_3", "v5_2"):
        url = f"https://re.jrc.ec.europa.eu/api/{ver}/DRcalc?{params}"
        log.info(f"⏳ PVGIS {ver}: запрос…")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read().decode("utf-8", "replace"))
            return parse_pvgis(data, lat, lon, builtin)
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8", "replace")).get("message", "")
            except Exception:
                msg = ""
            last = f"HTTP {e.code} {msg}".strip()
        except urllib.error.URLError as e:
            last = f"нет связи ({e.reason})"
        except Exception as e:
            last = str(e)
        log.warning(f"⚠ PVGIS {ver}: {last}")
    raise RuntimeError(last)
