"""mod_config.py  v1.9.3
параметры станции по умолчанию, config.json: загрузка, проверка, сохранение

Журнал:
v1.9.3: места «＋»-узлов (add_*) больше не хранятся — этих узлов нет.
v1.9.2: mppt_mode — «есть свои MPPT» / «нет MPPT» (только для своего инвертора; у гибрида из базы — всегда свои).
v1.9.1: cons_pos — места узлов конструктора, переставленные мышью {ключ: [x, y]} (с проверкой).
v1.9.0: pv_extra — поля на других входах MPPT инвертора [{preset, ns, np, tilt, aspect}] (до 11);
        ctl_extra — отдельные MPPT-контроллеры на АКБ со своим полем [{mppt, preset, ns, np, tilt, aspect}] (до 6).
v1.7.0: bat_extra — другие сборки АКБ параллельно: [{preset, n}], до 5, модель — из базы, n 1–10.
v1.5.1: АКБ — bat_packs (сборок 1–10); старое bat_count (всего штук) переводится в сборки.
v1.4.0: place (город), fc_soc0 (заряд АКБ для прогноза по погоде); настройки погоды и неба
        (cfg["weather"], cfg["sky"]) с проверкой типов.
v1.3.0: вынесено из solar_calc.pyw v1.2.1; новые параметры станции: n_pan (панелей всего), n_in (занято
        входов MPPT), mppt_mode (встроенный/отдельный), n_mppt_max, pv_pmax, inv_bat_v; старые config
        без mppt_mode считаются «отдельный контроллер» — расчёт как в v1.2.
"""

import json
import math
import re
import os

from .mod_base import CONFIG_PATH, WEATHER, log
from .mod_sun import BUILTIN_SUN
from .mod_fields import ALL_FIELDS, INT_KEYS, WIRE_RANGE
from .mod_model import bank_series
from .mod_equipment import BATTERY_DB, MPPT_DB
from .mod_panels import PANEL_DB

BAT_EXTRA_MAX = 5           # других сборок АКБ (кроме основной)
PV_EXTRA_MAX = 11           # полей на других входах MPPT инвертора (входов до 12)
CTL_EXTRA_MAX = 6           # отдельных MPPT-контроллеров на АКБ со своим полем


def _field_item(it, s, ctl=False):
    """Поле из config/профиля → проверенный dict или None."""
    if not isinstance(it, dict) or str(it.get("preset")) not in PANEL_DB:
        return None
    if ctl and str(it.get("mppt")) not in MPPT_DB:
        return None
    try:
        lim = lambda v, lo, hi, d: min(hi, max(lo, float(v if v is not None else d)))
        out = dict(preset=str(it["preset"]), ns=int(lim(it.get("ns"), 1, 40, 1)), np=int(lim(it.get("np"), 1, 30, 1)),
                   tilt=lim(it.get("tilt"), 0, 90, s["tilt"]), aspect=lim(it.get("aspect"), -180, 180, s["aspect"]))
    except (TypeError, ValueError):
        return None
    if ctl:
        out["mppt"] = str(it["mppt"])
    return out


DEFAULT_SYS = dict(
    place="Киев", lat=50.45, lon=30.52, tilt=15, aspect=0, horizon=5, tz=2, dst=True,
    month=11, weather="over", overcast_k=35,
    p_preset="p670", pmax=670, vmp=38.3, imp=17.5, voc=45.9, isc=18.6, gamma=-0.34, bvoc=-0.26,
    noct=45, lowlight=97,
    n_pan=6, n_in=1, ns=2, np=3, mismatch=2, soiling=2, calib=100,
    wire_len=15, wire_s=16, wire_mat="al", contact="norm", n_main=6,
    m_preset="cn60", v_max=150, vmpp_min=0, vmpp_max=145, iin_max=0, iout_max=60, eta=96, eta_k=3,
    own_w=4, headroom=3, mppt_mode="separate", n_mppt_max=1, pv_pmax=0,
    wire_mode="s", bw_len=1.5, bw_s=25, bw_mat="cu", iw_len=1.5, iw_s=35, iw_mat="cu",
    bat_preset="eve_lf280k", bat_v="48", chem="lfp", bat_unit_v=3.2, bat_ah=280, bat_packs=1, bat_extra=[], pv_extra=[], ctl_extra=[], cons_pos={}, bat_dod=90,
    bat_c=0.5, t_bat=15, bat_ch=56.8, eta_bat=97,
    inv_preset="hyb5", inv_p=6000, inv_eta=92, inv_idle=50, inv_hours=24, inv_bat_v=48,
    load_mode="m", load_kwh=250, load_winter=30, night_share=50, load_profile="typ",
    grid_mode="backup", back_soc=40, tariff=4.32, ser_days=4, ser_weather="over", ser_soc0=100,
    t_min=-25, t_max=35, pt_g=100, pt_t=0, fc_soc0=70,
)


DEFAULT_CONFIG = {"theme": "dark", "geometry": "", "sys": dict(DEFAULT_SYS),
                  "builtin": [list(x) for x in BUILTIN_SUN], "pvgis": None, "use_pvgis": True,
                  "last_dir": "", "weather": {"on": True, "model": "best_match", "poll": 30},
                  "sky": {"names": True, "stars": True, "anim": True}}


_POS_KEY = re.compile(r"inv|house|grid|bat:\d{1,2}|(field|ctl):(m|[pc]\d{1,2})")


def clean_sys(d):
    """Параметры станции из config.json / профиля → типы и пределы как у полей ввода; негодное — по умолчанию."""
    out = dict(DEFAULT_SYS)
    if not isinstance(d, dict):
        return out
    spec = {k: (kind, opt) for _, fields in ALL_FIELDS for k, _, kind, opt, _ in fields}
    spec.update(month=("num", (0, 11)), ser_days=("num", (1, 10)), ser_soc0=("num", (0, 100)),
                pt_g=("num", (0, 1300)), pt_t=("num", (-40, 50)), fc_soc0=("num", (0, 100)), weather=("seg", WEATHER), ser_weather=("seg", WEATHER))
    for k, v in d.items():
        if k not in out:
            continue
        kind, opt = spec.get(k, (None, None))
        try:
            if kind in ("num", "wire"):
                lo, hi = (opt if kind == "num" else WIRE_RANGE["s"])[:2]
                v = float(v)
                if not math.isfinite(v):
                    continue
                v = min(max(v, lo), hi)
                if k in INT_KEYS:
                    v = int(round(v))
            elif kind == "toggle":
                v = bool(v)
            elif kind == "text":
                v = str(v)[:60]
            elif kind in ("seg", "combo"):
                v = str(v)
                if v not in (opt if isinstance(opt, dict) else dict(opt)):
                    continue
        except (TypeError, ValueError):
            continue
        out[k] = v
    if "bat_packs" not in d and "bat_count" in d:          # config до v1.5.1: всего штук → сборок
        try:
            n = int(float(d["bat_count"])) // bank_series(out)[1]
            out["bat_packs"] = min(10, max(1, n))
        except (TypeError, ValueError, KeyError):
            pass
    ex = []
    for it in d.get("bat_extra") if isinstance(d.get("bat_extra"), list) else []:
        try:
            if isinstance(it, dict) and str(it.get("preset")) in BATTERY_DB and len(ex) < BAT_EXTRA_MAX:
                ex.append(dict(preset=str(it["preset"]), n=min(10, max(1, int(float(it.get("n", 1)))))))
        except (TypeError, ValueError):
            pass
    out["bat_extra"] = ex
    for key, mx, ctl in (("pv_extra", PV_EXTRA_MAX, False), ("ctl_extra", CTL_EXTRA_MAX, True)):
        src = d.get(key) if isinstance(d.get(key), list) else []
        out[key] = [x for x in (_field_item(it, out, ctl) for it in src) if x][:mx]
    pos = {}                                               # места узлов конструктора, переставленные мышью
    for k, v in (d.get("cons_pos") if isinstance(d.get("cons_pos"), dict) else {}).items():
        try:
            if isinstance(k, str) and _POS_KEY.fullmatch(k) and len(v) == 2:
                x, y = float(v[0]), float(v[1])
                if math.isfinite(x) and math.isfinite(y):
                    pos[k] = [int(min(max(x, 0), 4000)), int(min(max(y, 0), 4000))]
        except (TypeError, ValueError):
            pass
    out["cons_pos"] = pos
    out["n_in"] = min(out["n_in"], out["n_mppt_max"])
    out["n_pan"] = out["n_in"] * out["ns"] * out["np"]      # количество панелей = входы × S × P
    return out


def _pv_ok(pv):
    try:
        float(pv["lat"]), float(pv["lon"])
        return len(pv["months"]) == 12 and all(
            len(d[k]) == 24 for d in pv["months"] for k in ("ghi", "dhi", "gcs", "t")) and \
            all(isinstance(d["H"], (int, float)) and isinstance(d["T"], (int, float)) for d in pv["months"])
    except Exception:
        return False


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if not CONFIG_PATH.exists():
        return cfg
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("ожидался объект JSON")
    except Exception as e:
        bak = CONFIG_PATH.with_name("config.json.bak")
        try:
            CONFIG_PATH.replace(bak)
        except OSError:
            pass
        log.warning(f"⚠ config.json испорчен ({e}) — сохранён как {bak.name}, настройки по умолчанию")
        return cfg
    cfg.update(data)
    cfg["sys"] = clean_sys(data.get("sys"))
    try:
        cfg["builtin"] = [[float(r[0]), float(r[1])] for r in cfg["builtin"]]
        if len(cfg["builtin"]) != 12:
            raise ValueError
    except Exception:
        cfg["builtin"] = [list(x) for x in BUILTIN_SUN]
    if cfg.get("pvgis") is not None and not _pv_ok(cfg["pvgis"]):
        log.warning("⚠ Данные PVGIS в config.json повреждены — сброшены, загрузите заново")
        cfg["pvgis"] = None
    cfg["use_pvgis"] = bool(cfg.get("use_pvgis", True))
    for key, types in (("weather", {"on": bool, "model": str, "poll": int}), ("sky", {"names": bool, "stars": bool, "anim": bool})):
        got = cfg.get(key) if isinstance(cfg.get(key), dict) else {}
        d = dict(DEFAULT_CONFIG[key])
        for k, tp in types.items():
            try:
                d[k] = tp(got.get(k, d[k]))
            except (TypeError, ValueError):
                pass
        cfg[key] = d
    if cfg["weather"]["poll"] not in (15, 30, 60, 120):
        cfg["weather"]["poll"] = 30
    cfg["last_dir"] = str(cfg.get("last_dir") or "")
    return cfg


def save_config(cfg):
    try:
        tmp = CONFIG_PATH.with_name("config.json.tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, CONFIG_PATH)
    except Exception as e:
        log.error(f"✗ Не удалось сохранить config.json: {e}")
