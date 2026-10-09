"""mod_forecast.py  v1.9.7
Прогноз выработки по погоде: радиация Open-Meteo по часам → та же цепочка, что и весь расчёт
(положение Солнца mod_sun → плоскость панелей → панели/провод/MPPT → АКБ → дом). По дням:
кВт·ч в АКБ, на какой «типовой день» месяца похоже (ясно/средне/пасмурно), заряд АКБ по 10 минутам,
переход на сеть.

Журнал:
v1.9.7: заряд по прогнозу — гибрид и отдельные MPPT раздельно (своим током); убрана неиспользуемая kwh().
v1.9.4: «на какой день похоже» — только ясно / средне / пасмурно (погода региона — не типовой день).
v1.9.0: разные поля панелей — облучённость считается для каждого поля (свой угол и азимут).
v1.4.0: первая версия.
"""

import datetime as dt

from .mod_astro import to_utc, to_local, sun_altaz_utc
from .mod_base import W_KEYS
from .mod_model import make_ctx, sim_point, load_day_wh, soc_run, NST, pv_fields, field_sun
from .mod_sun import sun, poa, panel_geom, DT, N_STEPS

H = dt.timedelta(hours=1)


def _series(fc, key, shift):
    """[(секунды UTC, значение)] — радиация: среднее за прошедший час (центр — на полчаса раньше)."""
    out = []
    for r in fc:
        v = r.get(key)
        if v is not None:
            out.append(((r["u"] - shift - dt.datetime(1970, 1, 1)).total_seconds(), float(v)))
    return out


def _interp(ser, x, edge=None):
    if not ser:
        return edge
    if x <= ser[0][0]:
        return ser[0][1] if edge is None else (edge if x < ser[0][0] - 3600 else ser[0][1])
    if x >= ser[-1][0]:
        return ser[-1][1] if edge is None else (edge if x > ser[-1][0] + 3600 else ser[-1][1])
    lo, hi = 0, len(ser) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ser[mid][0] <= x:
            lo = mid
        else:
            hi = mid
    (x0, y0), (x1, y1) = ser[lo], ser[hi]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 > x0 else y0


def run(s, fc, res=None, soc0=70.0, days=None):
    """→ dict(days=[...], start=дата первого дня). fc — WeatherState.fc, res — средние дни (для сравнения)."""
    if not fc:
        return dict(days=[], start=None)
    c = make_ctx(s)
    specs = [field_sun(s, fl) for fl in pv_fields(s)]                 # у каждого поля свой угол и азимут
    wts = [f["pstc_tot"] / max(1.0, c["pstc_tot"]) for f in c["fields"]]
    lat, lon = float(s["lat"]), float(s["lon"])
    zone = (s["tz"], s["dst"])
    ghi = _series(fc, "ghi", H / 2)
    dhi = _series(fc, "dhi", H / 2)
    tmp = _series(fc, "t", dt.timedelta(0))
    snow = _series(fc, "snow", dt.timedelta(0))
    if not ghi or not tmp:
        return dict(days=[], start=None)
    first = to_local(fc[0]["u"], zone).date()        # первая отметка — 00:00 первых суток
    last = to_local(fc[-1]["u"], zone).date()
    n = (last - first).days + 1
    if days:
        n = min(n, days)
    cap = max(1.0, c["bank_wh"])
    e = max(0.0, min(c["usable_wh"], soc0 / 100.0 * cap - (cap - c["usable_wh"])))
    og = False
    out = []
    for di in range(n):
        day = first + dt.timedelta(days=di)
        m = day.month - 1
        pts, pctl, acc, g_wh, p_wh, cover = [], [], [0.0] * NST, 0.0, 0.0, 0
        for i in range(N_STEPS):
            local = dt.datetime(day.year, day.month, day.day) + dt.timedelta(hours=(i + 0.5) * DT)
            u = to_utc(local, zone)
            x = (u - dt.datetime(1970, 1, 1)).total_seconds()
            G = _interp(ghi, x, edge=-1.0)
            if G is None or G < 0:
                pts.append(((i + 0.5) * DT, 0.0))
                pctl.append(0.0)
                continue
            cover += 1
            G = max(0.0, G)
            D = _interp(dhi, x, edge=None) if dhi else None
            D = None if D is None else max(0.0, min(G, D))
            ta = _interp(tmp, x)
            sd = _interp(snow, x) if snow else None
            alb = 0.6 if (sd or 0) > 0.02 else (0.35 if m in (0, 1, 11) else 0.2)
            cosz, zen, az, g0 = sun(lat, lon, u.timetuple().tm_yday, u.hour + u.minute / 60.0 + u.second / 3600.0)
            irrs = [poa(G, D, cosz, zen, az, g0, panel_geom(sp, alb)) for sp in specs]
            irr = sum(w * x for w, x in zip(wts, irrs))
            r = sim_point(c, irrs, ta)
            for k in range(NST):
                acc[k] += r[k] * DT
            g_wh += G * DT
            p_wh += irr * DT
            pts.append(((i + 0.5) * DT, r[8]))
            pctl.append(r[14])
        full = cover >= N_STEPS * 0.9
        if cover < N_STEPS * 0.1:
            continue                                      # суток нет в прогнозе
        load = load_day_wh(c, m)
        rr, e, og_new = soc_run(c, pts, load, c["profile"], e, og, pctl if c["mixed"] else None)
        rr["start_grid"] = og
        og = og_new
        like = None
        if res is not None and full:
            like = min((w for w in W_KEYS if w != "reg"), key=lambda w: abs(res[(m, w)]["wh"][8] - acc[8]))
        out.append(dict(date=day, full=full, wh=acc, out=acc[8], ghi=g_wh, poa=p_wh, curve=pts, like=like,
                        peak=max((p for _, p in pts), default=0.0), soc=rr, load=load))
    return dict(days=out, start=first)


def now_power(s, cur, utc=None):
    """Сколько станция даёт сейчас по текущей радиации: → (Вт в АКБ, POA Вт/м²) или None."""
    G, D, ta = cur.get("ghi"), cur.get("dhi"), cur.get("temp")
    if G is None or ta is None:
        return None
    utc = utc or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    lat, lon = float(s["lat"]), float(s["lon"])
    m = to_local(utc, (s["tz"], s["dst"])).month - 1
    cosz, zen, az, g0 = sun(lat, lon, utc.timetuple().tm_yday, utc.hour + utc.minute / 60.0)
    c = make_ctx(s)
    alb = 0.35 if m in (0, 1, 11) else 0.2
    irrs = [poa(max(0.0, G), None if D is None else max(0.0, min(G, D)), cosz, zen, az, g0, panel_geom(field_sun(s, fl), alb))
            for fl in pv_fields(s)]
    irr = sum(f["pstc_tot"] / max(1.0, c["pstc_tot"]) * x for f, x in zip(c["fields"], irrs))
    return sim_point(c, irrs, ta)[8], irr


def sun_now(s, utc=None):
    utc = utc or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    return sun_altaz_utc(float(s["lat"]), float(s["lon"]), utc)
