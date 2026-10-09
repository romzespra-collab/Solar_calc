"""mod_astro.py  v1.4.0
Астрономия для страниц «Погода» и «Небо» — согласована с расчётом станции:
Солнце — та же формула, что в расчёте выработки (mod_sun.sun), место и часовой пояс —
из настроек станции (пояс + летнее время ЕС), панели — наклон и азимут станции.
Луна — упрощённые формулы Meeus (≈1–5°), звёзды — mod_stars.

Журнал:
v1.4.0: перенесено из Smart_BMS 4.81 (weather.py, sky_view.py) и согласовано с mod_sun.
"""

import datetime as dt
import math

from .mod_sun import sun, decl_eot, zone_offset

UNIX0 = dt.datetime(1970, 1, 1)


# ─────────────── время станции ───────────────
def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def to_local(utc, zone):
    """UTC → местное время станции. zone = (пояс UTC+, летнее время да/нет)."""
    return utc + dt.timedelta(hours=zone_offset(zone[0], zone[1], utc))


def to_utc(local, zone):
    u = local - dt.timedelta(hours=float(zone[0]))
    return local - dt.timedelta(hours=zone_offset(zone[0], zone[1], u))


def station_now(zone):
    return to_local(utc_now(), zone)


def jd_utc(u):
    return (u - UNIX0).total_seconds() / 86400.0 + 2440587.5


def jd_local(local, zone):
    return jd_utc(to_utc(local, zone))


# ─────────────── Солнце ───────────────
def sun_altaz_utc(lat, lon, u):
    """(высота °, азимут ° от севера по часовой) на момент UTC — формула расчёта станции."""
    cosz, zen, az, _ = sun(lat, lon, u.timetuple().tm_yday, u.hour + u.minute / 60.0 + u.second / 3600.0)
    return 90.0 - math.degrees(zen), (math.degrees(az) + 180.0) % 360.0


def sun_pos(lat, lon, local, zone):
    return sun_altaz_utc(lat, lon, to_utc(local, zone))


def sun_rise_set(lat, lon, day, zone):
    """Восход и закат (минуты от местной полуночи станции) с рефракцией 0.833°. None — полярный день/ночь."""
    noon_u = to_utc(dt.datetime(day.year, day.month, day.day, 12), zone)
    off = zone_offset(zone[0], zone[1], noon_u)
    decl, eot = decl_eot(noon_u.timetuple().tm_yday, noon_u.hour + noon_u.minute / 60.0)
    la = math.radians(lat)
    try:
        cosha = math.cos(math.radians(90.833)) / (math.cos(la) * math.cos(decl)) - math.tan(la) * math.tan(decl)
    except ZeroDivisionError:
        return None
    if not -1.0 <= cosha <= 1.0:
        return None
    ha = math.degrees(math.acos(cosha))
    rise = int(round(720 - 4 * (lon + ha) - eot + off * 60))
    sset = int(round(720 - 4 * (lon - ha) - eot + off * 60))
    return rise, sset


def incidence(alt, az, tilt, panel_az=180.0):
    """Угол между лучом и нормалью панели, ° (0 — луч в лоб). panel_az — от севера по часовой."""
    a, z, t = math.radians(alt), math.radians(az - panel_az), math.radians(tilt)
    c = math.sin(a) * math.cos(t) + math.cos(a) * math.sin(t) * math.cos(z)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def panel_az(aspect):
    """Азимут станции (0 — юг, −90 — восток, +90 — запад) → от севера по часовой."""
    return (180.0 + float(aspect)) % 360.0


# ─────────────── Луна ───────────────
def _n360(a):
    a = math.fmod(a, 360.0)
    return a + 360.0 if a < 0 else a


def sun_ecl_lon(jd):
    d = jd - 2451545.0
    g = math.radians(_n360(357.528 + 0.9856003 * d))
    return _n360(280.460 + 0.9856474 * d + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))


def moon_ecl_lon(jd):
    T = (jd - 2451545.0) / 36525.0
    Lp = _n360(218.316 + 481267.881 * T)
    D = math.radians(_n360(297.850 + 445267.112 * T))
    M = math.radians(_n360(357.529 + 35999.050 * T))
    Mp = math.radians(_n360(134.963 + 477198.868 * T))
    F = math.radians(_n360(93.272 + 483202.018 * T))
    return _n360(Lp + 6.289 * math.sin(Mp) - 1.274 * math.sin(2 * D - Mp) + 0.658 * math.sin(2 * D)
                 - 0.214 * math.sin(2 * Mp) - 0.186 * math.sin(M) - 0.114 * math.sin(2 * F))


def moon_phase(jd):
    """(фаза 0..1, освещённость 0..1). 0 — новолуние, 0.5 — полнолуние."""
    e = _n360(moon_ecl_lon(jd) - sun_ecl_lon(jd))
    return e / 360.0, (1.0 - math.cos(math.radians(e))) / 2.0


def phase_name(p):
    for lim, name in ((0.03, "новолуние"), (0.22, "растущий серп"), (0.28, "первая четверть"),
                      (0.47, "растущая луна"), (0.53, "полнолуние"), (0.72, "убывающая луна"),
                      (0.78, "последняя четверть"), (0.97, "убывающий серп")):
        if p < lim:
            return name
    return "новолуние"


def radec_altaz(ra_h, dec_deg, lat, lon, jd):
    """RA (ч) / Dec (°) → (высота °, азимут ° от севера по часовой) на момент jd (UTC)."""
    gmst = (280.46061837 + 360.98564736629 * (jd - 2451545.0)) % 360
    ha = math.radians((gmst + lon - ra_h * 15.0) % 360)
    dec, la = math.radians(dec_deg), math.radians(lat)
    alt = math.asin(max(-1.0, min(1.0, math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))))
    az = math.atan2(-math.sin(ha) * math.cos(dec), math.cos(la) * math.sin(dec) - math.sin(la) * math.cos(dec) * math.cos(ha))
    return math.degrees(alt), math.degrees(az) % 360


def moon_pos(lat, lon, local, zone):
    """(высота °, азимут °) Луны — упрощённо (~5°)."""
    jd = jd_local(local, zone)
    lam, eps = math.radians(moon_ecl_lon(jd)), math.radians(23.44)
    ra = math.degrees(math.atan2(math.sin(lam) * math.cos(eps), math.cos(lam))) % 360 / 15.0
    dec = math.degrees(math.asin(max(-1.0, min(1.0, math.sin(eps) * math.sin(lam)))))
    return radec_altaz(ra, dec, lat, lon, jd)
