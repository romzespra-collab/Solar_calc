"""mod_model.py  v1.7.0
физика станции: панели → провод → MPPT → АКБ → инвертор; заряд АКБ по 10 минутам

Журнал:
v1.7.0: разные сборки АКБ параллельно (bank_groups): основная + до 5 других из базы (s["bat_extra"]);
        ёмкость, полезная энергия и ток заряда складываются, у каждой сборки — своя последовательность.
v1.5.1: АКБ задаются сборками (bat_packs, 1–10): в сборке последовательно — по напряжению системы
        (bank_series), всего штук = последовательно × сборок; лишних штук больше не бывает.
v1.3.0: вынесено из solar_calc.pyw v1.2.1; поле из k одинаковых частей (входы MPPT / контроллеры);
        встроенный MPPT гибрида: предел мощности PV, ток заряда ограничивается при заряде АКБ (излишек
        солнца пропадает), нет провода MPPT→АКБ; раскладки панелей (layouts, layout_status, best_layout).
"""

import math

from .mod_base import DAYS, W_KEYS
from .mod_equipment import load_profile, CONTACT_MOHM, MAT, AMP_CU, AMP_AL, BATTERY_DB
from .mod_sun import DT, irr_day


LN5 = math.log(5.0)


def bank_series(s):
    """→ (номинал системы В, сколько АКБ/ячеек последовательно в одной сборке)."""
    lfp = s["chem"] == "lfp"
    sys_nom = int(s["bat_v"]) * (12.8 / 12.0 if lfp else 1.0)
    return sys_nom, max(1, int(round(sys_nom / max(0.5, float(s["bat_unit_v"])))))


def bank_groups(s):
    """Сборки АКБ параллельно: основная (поля s) + другие из базы (s["bat_extra"] = [{preset, n}]).
    → [dict(key, chem, unit_v, ah, c, dod, n, nser, v)] — v: напряжение одной сборки."""
    out = [dict(key=s.get("bat_preset", "custom"), chem=s["chem"], unit_v=float(s["bat_unit_v"]), ah=float(s["bat_ah"]),
                c=float(s["bat_c"]), dod=float(s["bat_dod"]), n=max(1, int(s["bat_packs"])))]
    for it in s.get("bat_extra") or []:
        d = BATTERY_DB.get(it.get("preset")) if isinstance(it, dict) else None
        if d:
            p = d[2]
            out.append(dict(key=it["preset"], chem=p["chem"], unit_v=float(p["bat_unit_v"]), ah=float(p["bat_ah"]),
                            c=float(p["bat_c"]), dod=float(p["bat_dod"]), n=max(1, int(it.get("n", 1)))))
    for gr in out:
        nom = int(s["bat_v"]) * (12.8 / 12.0 if gr["chem"] == "lfp" else 1.0)
        gr["nser"] = max(1, int(round(nom / max(0.5, gr["unit_v"]))))
        gr["v"] = gr["nser"] * gr["unit_v"]
        gr["bad_v"] = abs(gr["v"] - nom) / nom > 0.1
    return out


def group_name(gr):
    """Короткое имя сборки: «LF280K 280 А·ч», «Pylontech US5000», «свои АКБ»."""
    d = BATTERY_DB.get(gr["key"])
    if not d:
        return "свои АКБ"
    generic = d[0].startswith(("Ячейки", "Свинец", "LiFePO4"))          # бренд-«тип»: модель и так понятна
    return f"{d[0]} {d[1]}" if d[1][:1].isdigit() or not generic else d[1]


def bank_desc(c):
    """«16S1P LF280K 280 А·ч + 16S2P LF105 105 А·ч» — состав банка."""
    return " + ".join(f"{gr['nser']}S{gr['n']}P {group_name(gr)}" for gr in c["groups"])


def make_ctx(s):
    """Предрасчёт констант системы для быстрой симуляции."""
    f = lambda k: float(s[k])
    ns, np_ = max(1, int(s["ns"])), max(1, int(s["np"]))
    k = max(1, int(s.get("n_in", 1)))                 # входов MPPT / контроллеров, на каждом ns × np
    builtin = s.get("mppt_mode") == "builtin"
    rho, a = MAT.get(s["wire_mat"], MAT["cu"])
    rc = CONTACT_MOHM.get(s["contact"], 1.0) / 1000.0
    gam = f("gamma") / 100.0
    c = dict(
        ns=ns, np=np_, k=k, builtin=builtin, npan=k * ns * np_, pmax=f("pmax"), vmp=f("vmp"), imp=f("imp"), voc=f("voc"),
        isc=f("isc"), gam=gam, bvmp=gam - 0.0004, bvoc=f("bvoc") / 100.0,
        noctk=(f("noct") - 20.0) / 800.0, llk=(1 - f("lowlight") / 100.0) / LN5,
        soil=f("soiling") / 100.0, mmk=(1 - f("mismatch") / 100.0) * f("calib") / 100.0,
        rw20=rho * 2 * f("wire_len") / max(0.1, f("wire_s")), walpha=a,
        rconst=f("n_main") * rc + (ns + 1) * rc / np_,
        vin_min=max(f("vmpp_min"), f("bat_ch") + f("headroom")),
        vmpp_max=f("vmpp_max"), v_max=f("v_max"), iin_max=f("iin_max"),
        eta=f("eta") / 100.0, etak=f("eta_k") / 100.0, own=f("own_w") * (1 if builtin else k), vbat=max(1.0, f("bat_ch")),
        eta_bat=f("eta_bat") / 100.0, inv_eta=f("inv_eta") / 100.0, inv_idle=f("inv_idle"),
    )
    c["pstc_tot"] = c["pmax"] * c["npan"]
    # провода со стороны АКБ: 4 контакта на линию (наконечники + автомат/предохранитель);
    # опрессованный силовой наконечник ≈ в 3 раза лучше разъёма MC4 того же «качества»
    rcb = rc * 0.3
    c["rb"] = MAT.get(s["bw_mat"], MAT["cu"])[0] * 2 * f("bw_len") / max(0.1, f("bw_s")) + 4 * rcb
    c["ri"] = MAT.get(s["iw_mat"], MAT["cu"])[0] * 2 * f("iw_len") / max(0.1, f("iw_s")) + 4 * rcb
    # банк АКБ
    sys_nom, nser = bank_series(s)
    groups = bank_groups(s)                           # сборки параллельно: основная + другие
    tf = lambda chem: 1 + (0.004 if chem == "lfp" else 0.008) * min(0.0, f("t_bat") - 25)
    main = groups[0]
    c.update(sys_nom=sys_nom, nser=nser, npar=sum(gr["n"] for gr in groups), groups=groups,
             units=sum(gr["n"] * gr["nser"] for gr in groups), bank_v=main["v"],
             bank_ah=sum(gr["n"] * gr["ah"] for gr in groups), mismatch_v=any(gr["bad_v"] for gr in groups))
    c["bank_wh"] = sum(gr["n"] * gr["ah"] * gr["v"] for gr in groups)
    c["usable_wh"] = sum(gr["n"] * gr["ah"] * gr["v"] * gr["dod"] / 100.0 * tf(gr["chem"]) for gr in groups)
    c["bank_ich"] = sum(gr["n"] * gr["ah"] * gr["c"] for gr in groups)
    iout = f("iout_max") * (1 if builtin else k)          # у отдельных контроллеров токи складываются
    c["iout_tot"] = iout
    c["ilim"] = min(iout, c["bank_ich"]) if c["bank_ich"] > 0 else iout
    if builtin:
        # гибрид: MPPT кормит и дом, и АКБ — режет только предел мощности PV; ток заряда — при заряде АКБ
        c["rb"] = 0.0
        c["pv_pmax"] = f("pv_pmax")
        c["pout_max"] = c["pv_pmax"] if c["pv_pmax"] > 0 else 1e12
        c["pch_max"] = c["ilim"] * c["vbat"]
    else:
        c["pv_pmax"] = 0.0
        c["pout_max"] = c["ilim"] * c["vbat"]
        c["pch_max"] = 1e12
    lm = f("load_kwh") if s.get("load_mode", "m") == "m" else f("load_kwh") / 12.0
    c.update(inv_p=f("inv_p"), inv_hours=f("inv_hours"), load_month=lm,
             load_winter=f("load_winter") / 100.0, back_soc=f("back_soc") / 100.0, tariff=f("tariff"),
             grid_mode=s.get("grid_mode", "backup"), profile=load_profile(s.get("load_profile", "typ")))
    c["night"] = sum(c["profile"][h] for h in list(range(0, 7)) + list(range(18, 24)))
    return c


def wire_r(c, ta):
    return c["rw20"] * (1 + c["walpha"] * (ta - 10.0)) + c["rconst"]


def sim_point(c, poa, ta):
    """→ (pot, soil, cell, mm, arr, pin, conv, out, outb, vin, I, vp, tc, R).
    Мощности — по всему полю (k входов), vin / I / vp / R — на один вход MPPT."""
    pot = c["pstc_tot"] * poa / 1000.0
    if poa < 1.0:
        return (pot, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ta, wire_r(c, ta))
    G = poa * (1 - c["soil"])
    soil = c["pstc_tot"] * G / 1000.0
    tc = ta + c["noctk"] * G
    lnG = math.log(max(G, 5.0) / 1000.0)
    ll = min(1.01, max(0.6, 1 + c["llk"] * lnG))
    dT = tc - 25.0
    pmp = max(0.0, c["pmax"] * G / 1000.0 * (1 + c["gam"] * dT) * ll)
    vmp = max(0.3 * c["vmp"], c["vmp"] * (1 + c["bvmp"] * dT) * (1 + 0.035 * lnG))
    voc = max(vmp * 1.02, c["voc"] * (1 + c["bvoc"] * dT) * (1 + 0.028 * lnG))
    cell = pmp * c["npan"]
    R = wire_r(c, ta)
    if pmp <= 0:
        return (pot, soil, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, tc, R)
    imp = pmp / vmp
    Va = c["ns"] * vmp
    Ia = c["np"] * imp * c["mmk"]
    Vo = c["ns"] * voc
    k = c["k"]
    mm = Va * Ia * k
    dV = max(0.5, Vo - Va)
    vreq = c["vin_min"]
    vtop = c["vmpp_max"]
    # Vmp выше окна MPPT: контроллер держит верх окна, рабочая точка левее MPP (ток ≈ Imp)
    top = vtop > 0 and Va - Ia * R > vtop
    I = Ia
    if top:
        if vtop < vreq:
            I = 0.0
    elif Va - Ia * R < vreq:
        I = Ia * (Vo - vreq) / (dV + Ia * R)
    if c["iin_max"] > 0 and I > c["iin_max"]:
        I = c["iin_max"]
    if I <= 0 or Ia <= 0:
        return (pot, soil, cell, mm, 0, 0, 0, 0, 0, 0, 0, Vo, tc, R)
    I = min(I, Ia)
    Vp = vtop + I * R if top else Va + (Ia - I) / Ia * dV
    arr = Vp * I * k
    vin = Vp - I * R
    pin = arr - k * I * I * R
    eta = c["eta"] - c["etak"] * max(0.0, vin / c["vbat"] - 1)
    conv = max(0.0, pin * eta - c["own"])
    out = min(conv, c["pout_max"])
    ich = out / c["vbat"]
    outb = max(0.0, out - ich * ich * c["rb"])
    return (pot, soil, cell, mm, arr, pin, conv, out, outb, vin, I, Vp, tc, R)


NST = 9   # число этапов мощности в кортеже sim_point


def run_day(c, pts):
    acc = [0.0] * NST
    curve = []
    peak = 0.0
    peak_i = 0.0
    vin_lo, vin_hi = 1e9, 0.0
    for tl, poa, ta in pts:
        r = sim_point(c, poa, ta)
        for k in range(NST):
            acc[k] += r[k] * DT
        curve.append((tl, r[8]))
        if r[8] > peak:
            peak = r[8]
            peak_i = r[7] / c["vbat"]
        if r[8] > 0:
            vin_lo, vin_hi = min(vin_lo, r[9]), max(vin_hi, r[9])
    return {"wh": acc, "curve": curve, "peak": peak, "peak_i": peak_i,
            "vin": (vin_lo if vin_hi > 0 else 0.0, vin_hi), "poa_wh": sum(p for _, p, _ in pts) * DT}


def compute_days(s, sd, months=range(12), weathers=W_KEYS):
    c = make_ctx(s)
    res = {}
    for m in months:
        for w in weathers:
            res[(m, w)] = run_day(c, irr_day(s, sd, m, w))
    return c, res


def year_kwh(res, w="avg", stage=8):
    return sum(res[(m, w)]["wh"][stage] * DAYS[m] for m in range(12) if (m, w) in res) / 1000.0


def ampacity(sec, mat):
    tab = AMP_AL if mat == "al" else AMP_CU
    keys = sorted(tab)
    if sec <= keys[0]:
        return tab[keys[0]] * sec / keys[0]
    for a, b in zip(keys, keys[1:]):
        if sec <= b:
            return tab[a] + (tab[b] - tab[a]) * (sec - a) / (b - a)
    return tab[keys[-1]] * sec / keys[-1]


def load_day_wh(c, m):
    """Потребление дома в средний день месяца m, Вт·ч на 230 В (зимой больше)."""
    return c["load_month"] * (1 + c["load_winter"] * math.cos(2 * math.pi * m / 12.0)) * 12.0 / 365.0 * 1000.0


def soc_run(c, curve, load_wh, prof, e, on_grid):
    """Один день шагами DT: солнце → дом, излишек → АКБ, нехватка → АКБ, АКБ пуста → сеть.
    e — запас над минимальным зарядом, Вт·ч. → (итог дня, e, on_grid)."""
    usable = c["usable_wh"]
    cap = max(1.0, c["bank_wh"])
    base = cap - usable
    # гистерезис ≥ 5% полезной ёмкости: иначе при «вернуться на АКБ» ≤ мин. заряда сеть/АКБ дёргаются каждый шаг
    e_back = max(0.05 * usable, min(usable, c["back_soc"] * cap - base))
    eta_b = c["eta_bat"]
    eta_i = max(0.5, c["inv_eta"])
    vb = max(1.0, c["sys_nom"])
    idle = c["inv_idle"] * min(24.0, c["inv_hours"]) / 24.0
    pch = c["pch_max"]          # предел заряда АКБ (гибрид); у отдельного MPPT уже срезано раньше
    pts, events = [], []
    grid_wh = grid_load = wasted = pv_sum = load_dc_sum = 0.0
    soc_min = 100.0
    for tl, pv in curve:
        lac = load_wh * prof[int(tl) % 24]
        ldc = lac / eta_i + idle
        ldc += (ldc / vb) ** 2 * c["ri"]
        gw = 0.0
        if not on_grid:
            net = pv - ldc
            if net >= 0:
                chg = min(net, pch)
                e += chg * eta_b * DT
                wasted += (net - chg) * DT
            else:
                need = -net * DT
                if e >= need:
                    e -= need
                else:
                    frac = (need - e) / need
                    e = 0.0
                    gw = (lac + idle) * frac
                    grid_load += lac * frac * DT
                    on_grid = True
                    events.append((tl, "grid"))
        else:
            gw = lac + idle
            grid_load += lac * DT
            chg = min(pv, pch)
            e += chg * eta_b * DT
            wasted += (pv - chg) * DT
        if e > usable:
            wasted += (e - usable) / eta_b
            e = usable
        if on_grid and ((usable > 1 and e >= e_back) or (usable <= 1 and pv >= ldc)):
            on_grid = False
            events.append((tl, "bat"))
        grid_wh += gw * DT
        pv_sum += pv * DT
        load_dc_sum += ldc * DT
        soc = (base + e) / cap * 100.0
        soc_min = min(soc_min, soc)
        pts.append((tl, pv, ldc, gw, soc))
    return (dict(pts=pts, events=events, grid_wh=grid_wh, grid_load=grid_load, wasted=wasted, pv=pv_sum,
                 load_dc=load_dc_sum, load=load_wh, soc_min=soc_min, start_grid=False), e, on_grid)


def soc_steady(c, curve, load_wh, prof):
    """Повторяет одинаковый день до установившегося режима. Если режим циклический
    (день от АКБ / день от сети), итоги усредняются по 6 дням, график — показательный день."""
    e, og = c["usable_wh"] * 0.5, False
    for _ in range(10):
        e0, og0 = e, og
        r, e, og = soc_run(c, curve, load_wh, prof, e, og)
        if abs(e - e0) < 0.002 * max(1.0, c["bank_wh"]) and og == og0:
            r["start_grid"] = og0
            r["cycle"] = 1
            return r
    days = []
    for _ in range(6):
        sg = og
        r, e, og = soc_run(c, curve, load_wh, prof, e, og)
        r["start_grid"] = sg
        days.append(r)
    rep = next((d for d in reversed(days) if any(k == "grid" for _, k in d["events"])), days[-1])
    out = dict(rep)
    for k in ("grid_wh", "grid_load", "wasted", "pv", "load_dc"):
        out[k] = sum(d[k] for d in days) / len(days)
    out["soc_min"] = min(d["soc_min"] for d in days)
    out["cycle"] = 2
    out["full_grid_days"] = sum(1 for d in days if d["start_grid"] and not d["events"])
    return out


def soc_series(c, curves, load_wh, prof, soc0):
    cap = max(1.0, c["bank_wh"])
    e = max(0.0, min(c["usable_wh"], soc0 / 100.0 * cap - (cap - c["usable_wh"])))
    og = False
    out = []
    for curve in curves:
        sg = og
        r, e, og = soc_run(c, curve, load_wh, prof, e, og)
        r["start_grid"] = sg
        out.append(r)
    return out


def grid_times(r):
    """→ (время перехода на сеть, время возврата на АКБ) или None."""
    tg = next((t for t, k in r["events"] if k == "grid"), None)
    tb = next((t for t, k in r["events"] if k == "bat"), None)
    return tg, tb


def fmt_t(t):
    if t is None:
        return "—"
    mins = int(round((t % 24) * 60)) % 1440
    return f"{mins // 60:02d}:{mins % 60:02d}"


def balance(c, res):
    """Помесячно: потребление дома → потребность на шине DC → баланс с выработкой."""
    rows = []
    vb = max(1.0, c["sys_nom"])
    for m in range(12):
        load_day = load_day_wh(c, m)                                         # Вт·ч на 230 В
        idle = c["inv_idle"] * c["inv_hours"]
        p_dc = load_day / 24.0 / max(0.5, c["inv_eta"]) + idle / 24.0       # средняя мощность из DC
        cable = (p_dc / vb) ** 2 * c["ri"] * 24.0
        need_dc = load_day / max(0.5, c["inv_eta"]) + idle + cable
        night = need_dc * c["night"]
        need = need_dc + night * (1 / max(0.5, c["eta_bat"]) - 1)
        g = {w: (res[(m, w)]["wh"][8] if (m, w) in res else 0.0) for w in W_KEYS}
        rows.append(dict(load=load_day, idle=idle, cable=cable, need=need, need_dc=need_dc, night=night,
                         gen=g, bal={w: g[w] - need for w in W_KEYS}))
    return rows


def compute_all(s, sd):
    from .mod_checks import make_checks, bat_checks   # здесь: mod_checks сам импортирует mod_model
    c, res = compute_days(s, sd)
    bal = balance(c, res)
    grid = {}
    for m in range(12):
        lw = load_day_wh(c, m)
        for w in W_KEYS:
            grid[(m, w)] = soc_steady(c, res[(m, w)]["curve"], lw, c["profile"])
    ygrid = {}
    for w in W_KEYS:
        ygrid[w] = dict(load=sum(grid[(m, w)]["load"] * DAYS[m] for m in range(12)) / 1000,
                        grid_load=sum(grid[(m, w)]["grid_load"] * DAYS[m] for m in range(12)) / 1000,
                        grid=sum(grid[(m, w)]["grid_wh"] * DAYS[m] for m in range(12)) / 1000,
                        wasted=sum(grid[(m, w)]["wasted"] * DAYS[m] for m in range(12)) / 1000)
    return {"ctx": c, "res": res, "bal": bal, "grid": grid, "ygrid": ygrid,
            "checks": make_checks(s, c, res) + bat_checks(s, c, res, bal),
            "year": {w: year_kwh(res, w) for w in W_KEYS}}


def layouts(n, kmax):
    """Все раскладки n панелей: [(входов k, последовательно ns, параллельно np)], k ≤ kmax."""
    out = []
    for k in range(1, max(1, int(kmax)) + 1):
        if n % k:
            continue
        m = n // k
        for ns in range(1, min(m, 40) + 1):
            if m % ns == 0 and m // ns <= 30:
                out.append((k, ns, m // ns))
    return out


def layout_status(s, k, ns, np_):
    """Быстрая проверка раскладки без расчёта дня → ('ok'|'warn'|'err', пояснение)."""
    c = make_ctx(dict(s, n_in=k, ns=ns, np=np_))
    tmin, tmax = float(s["t_min"]), float(s["t_max"])
    voc_cold = ns * c["voc"] * (1 + c["bvoc"] * (tmin - 25))
    if voc_cold > c["v_max"]:
        return "err", f"Voc на морозе {voc_cold:.0f} В > {c['v_max']:.0f} В — MPPT сгорит"
    if ns * c["vmp"] < c["vin_min"]:
        return "err", f"Vmp {ns * c['vmp']:.0f} В < {c['vin_min']:.0f} В — MPPT не запустится"
    msgs = []
    tc_hot = tmax + c["noctk"] * 1000
    vmp_hot = ns * c["vmp"] * (1 + c["bvmp"] * (tc_hot - 25))
    if vmp_hot < c["vin_min"]:
        msgs.append(f"в жару Vmp ≈{vmp_hot:.0f} В < {c['vin_min']:.0f} В")
    vmp_cold = ns * c["vmp"] * (1 + c["bvmp"] * (tmin - 25))
    if c["vmpp_max"] > 0 and vmp_cold > c["vmpp_max"]:
        msgs.append(f"на морозе Vmp {vmp_cold:.0f} В выше окна {c['vmpp_max']:.0f} В")
    if c["iin_max"] > 0 and np_ * c["imp"] > c["iin_max"]:
        msgs.append(f"ток {np_ * c['imp']:.1f} А > {c['iin_max']:.0f} А на вход — срезка")
    if voc_cold > 0.95 * c["v_max"]:
        msgs.append(f"Voc на морозе {voc_cold:.0f} В — впритык к {c['v_max']:.0f} В")
    return ("warn" if msgs else "ok"), "; ".join(msgs)


def best_layout(s, sd, opts):
    """Лучшая раскладка: без ошибок, больше выработки (июнь + декабрь, средняя погода), меньше параллелей."""
    cand = []
    for k, ns, np_ in opts:
        lvl, _ = layout_status(s, k, ns, np_)
        if lvl == "err":
            continue
        _, res = compute_days(dict(s, n_in=k, ns=ns, np=np_), sd, months=(5, 11), weathers=("avg",))
        cand.append(((k, ns, np_), lvl, res[(5, "avg")]["wh"][8] * 30 + res[(11, "avg")]["wh"][8] * 31))
    if not cand:
        return None
    emax = max(1.0, max(e for _, _, e in cand))
    # в пределах 3% от лучшей выработки: сначала без замечаний, потом больше энергии, меньше параллелей и входов
    sc = lambda x: (x[2] >= 0.97 * emax, x[1] == "ok", round(x[2] / emax * 100), -x[0][2], -x[0][0])
    return max(cand, key=sc)[0]


LOSS_ROWS = (("Грязь / пыль / снег", 0, 1), ("Температура и слабый свет", 1, 2),
             ("Рассогласование + поправка", 2, 3), ("Окно MPPT / лимит входного тока", 3, 4),
             ("Провод и контакты", 4, 5), ("КПД MPPT + собственное потребление", 5, 6),
             ("Упор в макс. ток заряда", 6, 7), ("Провод MPPT → АКБ", 7, 8))
