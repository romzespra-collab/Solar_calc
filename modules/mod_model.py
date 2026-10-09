"""mod_model.py  v1.9.9
физика станции: панели → провод → MPPT → АКБ → инвертор; заряд АКБ по 10 минутам

Журнал:
v1.9.9: несколько полей на один вход MPPT (pv_extra[…]["par"] — параллельно с полем №): входы нумеруются сами
        (поле → slots, хозяин → host), make_ctx → slots / solo / shared. Общий вход (_sim_shared): у каждого
        поля своё солнце, нагрев, панели и кабель, напряжение одно; ВАХ цепочки I = B·(E − e^((V−Vm)/a)) через
        (Vm, Im) и (Voc, 0) с максимумом ровно в Vm (одинаковые поля — без потерь, как раньше); MPPT — максимум
        ΣV·I − ΣR·I² (Ньютон с вилкой), окно MPPT, предел тока входа; цепочка с Voc ниже напряжения забирает
        ток. run_day → "shared": за день мощность входа, без предела тока, если бы поля стояли отдельно, пик тока,
        диапазон напряжения, обратный ток. shared_status, field_mates, dir_word; inv_inputs_used — по входам.
        Без параллельных полей расчёт прежний (год станции по умолчанию тот же).
v1.9.7: гибрид + отдельные MPPT: заряд АКБ раздельно — инвертор своим током (pch_inv), контроллеры своим, всё
        вместе — до предела АКБ (pch_bank); раньше токи складывались и гибрид «заряжал» сверх своего предела.
        sim_point → + outb_ctl, run_day → curve_ctl, soc_run(…, ctl). Потери на кабелях контроллер → АКБ — у
        каждого контроллера свой кабель (раньше общий ток через один). Убраны k_tot и «vin» дня (не читались).
v1.9.0: разные поля панелей (pv_fields): основное + другие на входах инвертора (s["pv_extra"]) + отдельные
        MPPT-контроллеры на АКБ со своим полем (s["ctl_extra"], до 6) — у каждого поля своя панель, схема,
        угол и азимут; солнце считается по каждому полю, мощности складываются; пределы: мощность PV гибрида —
        на его входы, ток заряда — у каждого контроллера свой, кабель контроллер→АКБ — у каждого свой.
v1.8.0: подписи раскладки с входами MPPT (layout_text, inputs_word, plural) — сколько панелей на каждый вход.
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
from .mod_equipment import load_profile, CONTACT_MOHM, MAT, AMP_CU, AMP_AL, BATTERY_DB, MPPT_DB
from .mod_panels import PANEL_DB
from .mod_sun import DT, irr_day


LN5 = math.log(5.0)


def bank_series(s):
    """→ (номинал системы В, сколько АКБ/ячеек последовательно в одной сборке)."""
    lfp = s["chem"] == "lfp"
    sys_nom = int(s["bat_v"]) * (12.8 / 12.0 if lfp else 1.0)
    return sys_nom, max(1, int(round(sys_nom / max(0.5, float(s["bat_unit_v"])))))


def plural(n, one, few, many):
    """1 вход, 2 входа, 5 входов."""
    n = abs(int(n))
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def inputs_word(k, sep=False):
    """«2 входа MPPT» / «2 контроллера»."""
    return f"{k} {plural(k, 'контроллер', 'контроллера', 'контроллеров')}" if sep else \
        f"{k} {plural(k, 'вход', 'входа', 'входов')} MPPT"


def layout_text(k, ns, np_, sep=False):
    """Раскладка словами: «1 вход MPPT: 18 панелей (9 посл. × 2 пар.)» /
    «2 входа MPPT × по 9 панелей (9 посл. × 1 пар.)» — сколько панелей на каждый вход."""
    m = ns * np_
    pan = f"{m} {plural(m, 'панель', 'панели', 'панелей')} ({ns} посл. × {np_} пар.)"
    return f"{inputs_word(k, sep)}: {pan}" if k == 1 else f"{inputs_word(k, sep)} × по {pan}"


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


PANEL_KEYS = ("pmax", "vmp", "imp", "voc", "isc", "gamma", "bvoc", "noct", "lowlight")


def pv_fields(s):
    """Поля панелей: основное (паспорт и схема из s, на n_in входов) + другие (s["pv_extra"]) — каждое на свой
    вход MPPT (или свой контроллер) либо параллельно с другим полем на его вход (par = № поля), со своей
    панелью, схемой, углом и азимутом. → [dict(key, p=паспорт, ns, np, k=входов, tilt, aspect, host, slots)]:
    host — индекс поля, на чей вход подключено (None — свой вход), slots — номера занятых входов (1…)."""
    grp = "inv" if s.get("mppt_mode") == "builtin" else "ctl"     # входы инвертора / контроллеры из s
    out = [dict(key=s.get("p_preset", "custom"), p={k: float(s[k]) for k in PANEL_KEYS},
                ns=max(1, int(s["ns"])), np=max(1, int(s["np"])), k=max(1, int(s.get("n_in", 1))),
                tilt=float(s["tilt"]), aspect=float(s["aspect"]), grp=grp, mp=None, ctl=None, par=0)]
    pos = {}                                        # № в pv_extra → индекс поля
    for src, g in ((s.get("pv_extra") or [], grp), (s.get("ctl_extra") or [], "ext")):
        for j, it in enumerate(src):
            d = PANEL_DB.get(it.get("preset")) if isinstance(it, dict) else None
            if not d:
                continue
            mp = None
            if g == "ext":                          # отдельный MPPT-контроллер на АКБ со своим полем
                md = MPPT_DB.get(it.get("mppt"))
                if not md:
                    continue
                mp = md[2]
            else:
                pos[j] = len(out)
            try:
                par = int(it.get("par") or 0) if g != "ext" else 0
            except (TypeError, ValueError):
                par = 0
            out.append(dict(key=it["preset"], p={k: float(d[2][k]) for k in PANEL_KEYS},
                            ns=max(1, int(it.get("ns", 1))), np=max(1, int(it.get("np", 1))), k=1,
                            tilt=float(it.get("tilt", s["tilt"])), aspect=float(it.get("aspect", s["aspect"])),
                            grp="ctl" if g == "ext" else g, mp=mp, ctl=it.get("mppt") if g == "ext" else None, par=par))
    # параллельно с полем №par (1 — поле 1, 2… — другие поля на входах) → индекс поля-хозяина входа
    for i, fl in enumerate(out):
        n = fl.pop("par")
        h = 0 if n == 1 else pos.get(n - 2) if n >= 2 else None
        fl["host"] = h if (h is not None and h != i and not fl["ctl"]) else None
    for i, fl in enumerate(out):                    # цепочка «с полем, которое само с другим» — к первому
        h, seen = fl["host"], {i}
        while h is not None and out[h]["host"] is not None and h not in seen:
            seen.add(h)
            h = out[h]["host"]
        fl["host"] = None if h in seen else h
    n = 0
    for fl in out:                                  # свои входы — по порядку полей
        if fl["ctl"] or fl["host"] is not None:
            fl["slots"] = []
        else:
            fl["slots"] = list(range(n + 1, n + 1 + fl["k"]))
            n += fl["k"]
    for fl in out:
        if fl["host"] is not None:
            fl["slots"] = out[fl["host"]]["slots"][:1]
    return out


def field_sun(s, fl):
    """Параметры станции для расчёта солнца на плоскости поля (свой угол и азимут)."""
    return s if (fl["tilt"], fl["aspect"]) == (float(s["tilt"]), float(s["aspect"])) else \
        dict(s, tilt=fl["tilt"], aspect=fl["aspect"])


def _field_ctx(s, fl, first):
    """Константы одного поля (на fl["k"] одинаковых входов) для sim_point. MPPT — инвертора / контроллера из s
    или своего контроллера поля (fl["mp"])."""
    f = lambda k: float(s[k])
    mp = fl["mp"]
    m = (lambda k: float(mp.get(k, 0) or 0)) if mp else f
    inv = fl["grp"] == "inv"
    p = fl["p"]
    ns, np_, k = fl["ns"], fl["np"], fl["k"]
    rho, a = MAT.get(s["wire_mat"], MAT["cu"])
    rc = CONTACT_MOHM.get(s["contact"], 1.0) / 1000.0
    gam = p["gamma"] / 100.0
    fc = dict(
        key=fl["key"], tilt=fl["tilt"], aspect=fl["aspect"], grp=fl["grp"], ctl=fl["ctl"],
        host=fl["host"], slots=fl["slots"],
        ns=ns, np=np_, k=k, npan=k * ns * np_, pmax=p["pmax"], vmp=p["vmp"], imp=p["imp"], voc=p["voc"],
        isc=p["isc"], gam=gam, bvmp=gam - 0.0004, bvoc=p["bvoc"] / 100.0,
        noctk=(p["noct"] - 20.0) / 800.0, llk=(1 - p["lowlight"] / 100.0) / LN5,
        soil=f("soiling") / 100.0, mmk=(1 - f("mismatch") / 100.0) * f("calib") / 100.0,
        rw20=rho * 2 * f("wire_len") / max(0.1, f("wire_s")), walpha=a,
        rconst=f("n_main") * rc + (ns + 1) * rc / np_,
        vin_min=max(m("vmpp_min"), f("bat_ch") + m("headroom")),
        vmpp_max=m("vmpp_max"), v_max=m("v_max"), iin_max=m("iin_max"),
        eta=m("eta") / 100.0, etak=m("eta_k") / 100.0, vbat=max(1.0, f("bat_ch")),
        # свой расход: у гибрида — один раз на весь инвертор, у отдельных контроллеров — каждый
        own=m("own_w") * ((1 if first else 0) if inv else k),
        # предел выхода поля: контроллер — его ток заряда (× k шт); входы инвертора — общий предел (ниже)
        cap=1e12 if inv else m("iout_max") * k * max(1.0, f("bat_ch")),
        iout=0.0 if inv else m("iout_max") * k,
    )
    fc["pstc_tot"] = fc["pmax"] * fc["npan"]
    return fc


def make_ctx(s):
    """Предрасчёт констант системы для быстрой симуляции. Ключи поля верхнего уровня — основного поля;
    c["fields"] — все поля (по входам MPPT), npan / pstc_tot — по всем полям."""
    f = lambda k: float(s[k])
    builtin = s.get("mppt_mode") == "builtin"
    rc = CONTACT_MOHM.get(s["contact"], 1.0) / 1000.0
    fields = [_field_ctx(s, fl, i == 0) for i, fl in enumerate(pv_fields(s))]
    mixed = builtin and any(fc["grp"] == "ctl" for fc in fields)   # гибрид + отдельные контроллеры на АКБ
    c = dict(fields[0])
    c.update(builtin=builtin, mixed=mixed, fields=fields, main_npan=c["npan"], main_pstc=c["pstc_tot"],
             npan=sum(fc["npan"] for fc in fields),
             eta_bat=f("eta_bat") / 100.0, inv_eta=f("inv_eta") / 100.0, inv_idle=f("inv_idle"))
    c["pstc_tot"] = sum(fc["pstc_tot"] for fc in fields)
    # входы MPPT: поле на своём входе (или на k одинаковых) считается само (solo); на общем входе несколько
    # полей параллельно — одно напряжение на всех, общая ВАХ (shared → _sim_shared)
    slots = {}
    for i, fc in enumerate(fields):
        for n in fc["slots"]:
            slots.setdefault(n, []).append(i)
    multi = {n for n, mem in slots.items() if len(mem) > 1}
    solo, shared = [], []
    for i, fc in enumerate(fields):
        if fc["host"] is not None:
            continue                                  # считается на входе своего хозяина
        k_sh = sum(1 for n in fc["slots"] if n in multi)
        if not k_sh:
            solo.append((i, fc))
            continue
        k1 = fc["k"] - k_sh                           # входы хозяина, где он один
        inv = fc["grp"] == "inv"
        if k1 > 0:
            part = dict(fc, k=k1, npan=k1 * fc["ns"] * fc["np"])
            part["pstc_tot"] = part["pmax"] * part["npan"]
            if not inv:
                part.update(cap=fc["cap"] / fc["k"] * k1, iout=fc["iout"] / fc["k"] * k1, own=fc["own"] / fc["k"] * k1)
            solo.append((i, part))
        for n in fc["slots"]:
            if n in multi:                            # свой расход: гибрид — один на инвертор, контроллер — свой
                shared.append(dict(n=n, members=slots[n], grp=fc["grp"],
                                   own=(fc["own"] if k1 == 0 else 0.0) if inv else fc["own"] / fc["k"],
                                   cap=1e12 if inv else fc["cap"] / fc["k"]))
    c.update(slots=slots, solo=solo, shared=shared)
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
    # ток заряда: встроенный MPPT инвертора + все контроллеры (у отдельных контроллеров токи складываются)
    iout = (f("iout_max") if builtin else 0.0) + sum(fc["iout"] for fc in fields if fc["host"] is None)
    c["iout_tot"] = iout
    c["ilim"] = min(iout, c["bank_ich"]) if c["bank_ich"] > 0 else iout
    c["rb_ctl"] = c["rb"]                             # кабель отдельного контроллера до АКБ
    if builtin:
        # гибрид: MPPT кормит и дом, и АКБ — режет только предел мощности PV; ток заряда — при заряде АКБ
        c["rb"] = 0.0
        c["pv_pmax"] = f("pv_pmax")
        c["pout_max"] = c["pv_pmax"] if c["pv_pmax"] > 0 else 1e12
        c["pch_max"] = c["ilim"] * c["vbat"]
        # гибрид + отдельные MPPT: инвертор заряжает своим током, контроллеры — своим, всё вместе — до предела АКБ
        inv_i = f("iout_max")
        c["pch_inv"] = (min(inv_i, c["bank_ich"]) if c["bank_ich"] > 0 else inv_i) * c["vbat"]
        c["pch_bank"] = c["bank_ich"] * c["vbat"] if c["bank_ich"] > 0 else 1e12
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


def _sim_field(c, poa, ta):
    """Одно поле (c — его константы) → (pot, soil, cell, mm, arr, pin, conv, vin, I, vp, tc, R).
    Мощности — по всему полю (k входов), vin / I / vp / R — на один вход MPPT."""
    pot = c["pstc_tot"] * poa / 1000.0
    if poa < 1.0:
        return (pot, 0, 0, 0, 0, 0, 0, 0, 0, 0, ta, wire_r(c, ta))
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
        return (pot, soil, 0, 0, 0, 0, 0, 0, 0, 0, tc, R)
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
        return (pot, soil, cell, mm, 0, 0, 0, 0, 0, Vo, tc, R)
    I = min(I, Ia)
    Vp = vtop + I * R if top else Va + (Ia - I) / Ia * dV
    arr = Vp * I * k
    vin = Vp - I * R
    pin = arr - k * I * I * R
    eta = c["eta"] - c["etak"] * max(0.0, vin / c["vbat"] - 1)
    conv = max(0.0, pin * eta - c["own"])
    return (pot, soil, cell, mm, arr, pin, conv, vin, I, Vp, tc, R)


_U = {}


def _iv_u(x):
    """ВАХ цепочки для общего входа: I(V) = B·(E − e^((V − Vm)/a)), a = Vm·u. Проходит через (Vm, Im) и (Voc, 0),
    максимум мощности — ровно в (Vm, Im) (как у _sim_field), ток при 0 В ≈ Isc паспорта. Условие максимума:
    u·(e^(x/u) − 1) = 1, x = Voc/Vm − 1 → u (простая итерация, кэш)."""
    x = round(min(0.6, max(0.02, x)), 4)
    u = _U.get(x)
    if u is None:
        u = 0.07
        for _ in range(60):
            un = x / math.log(1 + 1 / u)
            if abs(un - u) < 1e-10:
                break
            u = un
        _U[x] = u
    return u


def _sim_shared(c, sh, poa, ta, det=None, nolim=False):
    """Несколько полей параллельно на одном входе MPPT (sh — из c["shared"]): у каждого поля своё солнце (угол,
    азимут), нагрев, панели и кабель до входа, а напряжение одно на всех. MPPT ищет напряжение, где сумма
    мощностей после кабелей наибольшая (кривая выпуклая — Ньютон с вилкой), потом окно MPPT и предел входного
    тока. Цепочка с Voc ниже рабочего напряжения не отдаёт, а забирает ток (минус в сумме).
    → как _sim_field на один вход; det (dict) — заполнить: напряжение V и ток каждого поля I {индекс: А};
    nolim — без предела входного тока (сколько он срезает)."""
    fields = c["fields"]
    h = fields[sh["members"][0]]
    pot = soil = cell = mm = 0.0
    tc0 = ta
    S = []                                          # (индекс, B, E, Vm, a, R, Voc, Im)
    for i in sh["members"]:
        fc = fields[i]
        per = fc["pmax"] * fc["ns"] * fc["np"]
        g = poa[i]
        pot += per * g / 1000.0
        if g < 1.0:
            continue
        G = g * (1 - fc["soil"])
        soil += per * G / 1000.0
        tc = ta + fc["noctk"] * G
        if i == sh["members"][0]:
            tc0 = tc
        lnG = math.log(max(G, 5.0) / 1000.0)
        ll = min(1.01, max(0.6, 1 + fc["llk"] * lnG))
        dT = tc - 25.0
        pmp = max(0.0, fc["pmax"] * G / 1000.0 * (1 + fc["gam"] * dT) * ll)
        if pmp <= 0:
            continue
        vmp = max(0.3 * fc["vmp"], fc["vmp"] * (1 + fc["bvmp"] * dT) * (1 + 0.035 * lnG))
        voc = max(vmp * 1.02, fc["voc"] * (1 + fc["bvoc"] * dT) * (1 + 0.028 * lnG))
        cell += pmp * fc["ns"] * fc["np"]
        Vm, Vo = fc["ns"] * vmp, fc["ns"] * voc
        Im = fc["np"] * pmp / vmp * fc["mmk"]
        mm += Vm * Im
        u = _iv_u(Vo / Vm - 1)
        a = Vm * u
        S.append((i, Im * u, math.exp((Vo - Vm) / a), Vm, a, wire_r(fc, ta), Vo, Im))
    zero = (pot, soil, cell, mm, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, tc0, wire_r(h, ta))
    if not S:
        return zero

    def cur(V):
        return [B * (E - math.exp(min(600.0, (V - Vm) / a))) for _, B, E, Vm, a, _, _, _ in S]

    vo_max = max(t[6] for t in S)
    lo, hi = 0.0, vo_max
    V = sum(t[3] * t[7] for t in S) / sum(t[7] for t in S)
    for _ in range(60):                             # максимум ΣV·I − ΣR·I²: производная = 0
        f1 = f2 = 0.0
        for _, B, E, Vm, a, R, _, _ in S:
            e = math.exp(min(600.0, (V - Vm) / a))
            I, I1 = B * (E - e), -B * e / a
            I2 = I1 / a
            f1 += I + V * I1 - 2 * R * I * I1
            f2 += 2 * I1 + V * I2 - 2 * R * (I1 * I1 + I * I2)
        if f1 > 0:
            lo = V
        else:
            hi = V
        Vn = V - f1 / f2 if f2 < 0 else 0.5 * (lo + hi)
        if not lo < Vn < hi:
            Vn = 0.5 * (lo + hi)
        done = abs(Vn - V) < 1e-3 or hi - lo < 1e-3
        V = Vn
        if done:
            break
    I = cur(V)
    It = sum(I)
    if It <= 0:
        return zero
    drop = sum(t[5] * x * x for t, x in zip(S, I)) / It    # падение на кабелях до входа
    vlo = h["vin_min"] + drop
    vhi = h["vmpp_max"] + drop if h["vmpp_max"] > 0 else vo_max
    if vhi < vlo or vlo >= vo_max:                  # окно MPPT недостижимо — вход стоит
        return zero
    V = min(max(V, vlo), vhi, vo_max)
    I = cur(V)
    It = sum(I)
    sc = 1.0
    imax = 0.0 if nolim else h["iin_max"]
    if imax > 0 and It > imax:                      # предел тока входа: MPPT уходит вправо, ток падает
        top = min(vhi, vo_max)
        if sum(cur(top)) > imax:
            V = top
            I = cur(V)
            sc = imax / sum(I)
        else:
            x0, x1 = V, top
            for _ in range(40):
                xm = 0.5 * (x0 + x1)
                if sum(cur(xm)) > imax:
                    x0 = xm
                else:
                    x1 = xm
            V = x1
            I = cur(V)
    I = [x * sc for x in I]
    It = sum(I)
    if It <= 0:
        return zero
    arr = V * It
    wl = sum(t[5] * x * x for t, x in zip(S, I))
    pin = arr - wl
    vin = V - wl / It
    eta = h["eta"] - h["etak"] * max(0.0, vin / h["vbat"] - 1)
    conv = max(0.0, pin * eta - sh["own"])
    if det is not None:
        det["V"] = V
        det["I"] = {t[0]: x for t, x in zip(S, I)}
    return (pot, soil, cell, mm, arr, pin, conv, vin, It, V, tc0, wl / (It * It))


def sim_point(c, poa, ta):
    """→ (pot, soil, cell, mm, arr, pin, conv, out, outb, vin, I, vp, tc, R, outb_ctl) по всем полям.
    poa — облучённость плоскости (Вт/м²): число (все поля одинаково) или список по полям c["fields"].
    vin / I / vp / tc / R — основного поля (на один его вход MPPT; на общем входе — всего входа). outb_ctl —
    сколько из outb дали отдельные MPPT у гибрида (они заряжают АКБ своим током, мимо предела заряда инвертора)."""
    fields = c["fields"]
    if not isinstance(poa, (list, tuple)):
        poa = [poa] * len(fields)
    vb = c["vbat"]
    if len(fields) == 1:
        fc = fields[0]
        r = _sim_field(fc, poa[0], ta)
        out = min(r[6], fc["cap"], c["pout_max"])
        loss = (out / vb) ** 2 * c["rb"] / max(1, fc["k"])      # у каждого из k контроллеров свой кабель до АКБ
        return r[:7] + (out, max(0.0, out - loss)) + r[7:] + (0.0,)
    acc, inv, ctl, sep = [0.0] * 7, 0.0, 0.0, []
    parts = [(i, fc["grp"], fc["cap"], max(1, fc["k"]), _sim_field(fc, poa[i], ta)) for i, fc in c["solo"]]
    parts += [(sh["members"][0], sh["grp"], sh["cap"], 1, _sim_shared(c, sh, poa, ta)) for sh in c["shared"]]
    for i, grp, cap, k, rf in parts:
        for q in range(7):
            acc[q] += rf[q]
        if grp == "inv":
            inv += rf[6]
        else:
            o = min(rf[6], cap)                     # контроллер режет свой ток заряда
            ctl += o
            sep.append((o, k))
    r = tuple(acc) + next((rf for i, *_, rf in parts if i == 0), parts[0][4])[7:]
    ctl_b = 0.0
    if c["mixed"]:
        loss = sum((o / vb) ** 2 * c["rb_ctl"] / k for o, k in sep)   # у каждого контроллера свой кабель
        ctl_b = max(0.0, ctl - loss)
        inv_out = min(inv, c["pout_max"])          # предел PV гибрида — только на его входы
        out, outb = inv_out + ctl, inv_out + ctl_b
    elif c["builtin"]:
        out = outb = min(inv, c["pout_max"])
    else:
        out = min(ctl, c["pout_max"])               # только контроллеры: общий предел — ток заряда АКБ
        sc = out / ctl if ctl > 0 else 0.0
        loss = sum((o * sc / vb) ** 2 * c["rb"] / k for o, k in sep)
        outb = max(0.0, out - loss)
    return r[:7] + (out, outb) + r[7:] + (ctl_b,)


NST = 9   # число этапов мощности в кортеже sim_point


def run_day(c, pts):
    """pts — [(час, POA, t воздуха)]; POA — число или список по полям."""
    acc = [0.0] * NST
    curve, cctl = [], []
    peak = 0.0
    peak_i = 0.0
    wts = [fc["pstc_tot"] / max(1.0, c["pstc_tot"]) for fc in c["fields"]]
    poa_sum = 0.0
    shs = c.get("shared") or []
    st = [dict(n=sh["n"], comb=0.0, free=0.0, sep=0.0, imax=0.0, tmax=0.0, vmin=1e9, vmax=0.0,
               irev={i: 0.0 for i in sh["members"]}) for sh in shs]
    for tl, poa, ta in pts:
        poa_sum += sum(w * g for w, g in zip(wts, poa)) if isinstance(poa, (list, tuple)) else poa
        r = sim_point(c, poa, ta)
        if shs:
            _shared_step(c, shs, st, poa, ta, tl)
        for k in range(NST):
            acc[k] += r[k] * DT
        curve.append((tl, r[8]))
        cctl.append(r[14])
        if r[8] > peak:
            peak = r[8]
            peak_i = r[7] / c["vbat"]
    return {"wh": acc, "curve": curve, "curve_ctl": cctl if c["mixed"] else None, "peak": peak, "peak_i": peak_i,
            "poa_wh": poa_sum * DT, "shared": st}


def _shared_step(c, shs, st, poa, ta, tl):
    """Общие входы MPPT за шаг: мощность входа (comb), без предела тока (free), если бы каждое поле стояло на
    своём входе (sep), пик тока входа, диапазон напряжения, обратный ток полей (минимум, А) — Вт·ч за шаг."""
    if not isinstance(poa, (list, tuple)):
        poa = [poa] * len(c["fields"])
    for sh, a in zip(shs, st):
        det = {}
        rc = _sim_shared(c, sh, poa, ta, det)
        a["comb"] += rc[5] * DT
        im = c["fields"][sh["members"][0]]["iin_max"]
        a["free"] += (_sim_shared(c, sh, poa, ta, nolim=True)[5] if im > 0 and rc[8] >= 0.999 * im else rc[5]) * DT
        a["sep"] += sum(_sim_shared(c, dict(sh, members=[i], own=0.0), poa, ta)[5] for i in sh["members"]) * DT
        if rc[8] > a["imax"]:
            a["imax"], a["tmax"] = rc[8], tl
        if rc[8] > 0:
            a["vmin"], a["vmax"] = min(a["vmin"], det["V"]), max(a["vmax"], det["V"])
        for i, x in det.get("I", {}).items():
            a["irev"][i] = min(a["irev"][i], x)


def day_pts(s, sd, m, w):
    """Солнце на плоскости панелей в средний день: одно поле — [(час, POA, t)], несколько — POA списком по полям."""
    fls = pv_fields(s)
    if len(fls) == 1:
        return irr_day(s, sd, m, w)
    days = [irr_day(field_sun(s, fl), sd, m, w) for fl in fls]
    return [(tl, [d[i][1] for d in days], ta) for i, (tl, _, ta) in enumerate(days[0])]


def compute_days(s, sd, months=range(12), weathers=W_KEYS):
    c = make_ctx(s)
    res = {}
    for m in months:
        for w in weathers:
            res[(m, w)] = run_day(c, day_pts(s, sd, m, w))
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


def _charge(c, pv, pc, ldc, pch):
    """Сколько идёт в АКБ при излишке солнца: (в АКБ, пропало). pc — часть pv от отдельных MPPT (гибрид +
    контроллеры): гибрид кормит дом и заряжает своим током, контроллеры — своим, всё вместе — до предела АКБ."""
    if pc is None:
        net = pv - ldc
        chg = min(net, pch)
        return chg, net - chg
    pi = pv - pc
    sur = pi - ldc                                  # излишек солнца гибрида после дома
    if sur >= 0:
        to_bat = min(sur, c["pch_inv"]) + pc
        lost = sur - min(sur, c["pch_inv"])
    else:
        to_bat, lost = pc + sur, 0.0                # контроллеры докрывают дом, остаток — в АКБ
    chg = min(to_bat, c["pch_bank"])
    return chg, lost + to_bat - chg


def soc_run(c, curve, load_wh, prof, e, on_grid, ctl=None):
    """Один день шагами DT: солнце → дом, излишек → АКБ, нехватка → АКБ, АКБ пуста → сеть.
    e — запас над минимальным зарядом, Вт·ч; ctl — часть солнца от отдельных MPPT по шагам (гибрид +
    контроллеры), иначе None. → (итог дня, e, on_grid)."""
    split = bool(ctl) and c.get("mixed")
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
    for j, (tl, pv) in enumerate(curve):
        pc = min(ctl[j], pv) if split else None
        lac = load_wh * prof[int(tl) % 24]
        ldc = lac / eta_i + idle
        ldc += (ldc / vb) ** 2 * c["ri"]
        gw = 0.0
        if not on_grid:
            net = pv - ldc
            if net >= 0:
                chg, lost = _charge(c, pv, pc, ldc, pch)
                e += chg * eta_b * DT
                wasted += lost * DT
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
            chg, lost = _charge(c, pv, pc, 0.0, pch)        # дом — от сети, всё солнце — в АКБ
            e += chg * eta_b * DT
            wasted += lost * DT
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


def soc_steady(c, curve, load_wh, prof, ctl=None):
    """Повторяет одинаковый день до установившегося режима. Если режим циклический
    (день от АКБ / день от сети), итоги усредняются по 6 дням, график — показательный день."""
    e, og = c["usable_wh"] * 0.5, False
    for _ in range(10):
        e0, og0 = e, og
        r, e, og = soc_run(c, curve, load_wh, prof, e, og, ctl)
        if abs(e - e0) < 0.002 * max(1.0, c["bank_wh"]) and og == og0:
            r["start_grid"] = og0
            r["cycle"] = 1
            return r
    days = []
    for _ in range(6):
        sg = og
        r, e, og = soc_run(c, curve, load_wh, prof, e, og, ctl)
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


def soc_series(c, curves, load_wh, prof, soc0, ctls=None):
    cap = max(1.0, c["bank_wh"])
    e = max(0.0, min(c["usable_wh"], soc0 / 100.0 * cap - (cap - c["usable_wh"])))
    og = False
    out = []
    for i, curve in enumerate(curves):
        sg = og
        r, e, og = soc_run(c, curve, load_wh, prof, e, og, ctls[i] if ctls else None)
        r["start_grid"] = sg
        out.append(r)
    return out


def grid_times(r):
    """→ (время перехода на сеть, время возврата на АКБ); нет события — None на его месте."""
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
            grid[(m, w)] = soc_steady(c, res[(m, w)]["curve"], lw, c["profile"], res[(m, w)]["curve_ctl"])
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


def field_label(c, i):
    """Подпись поля i: «вход 1», «входы 1–2», «контроллер 3», «доп. MPPT 1 (MPPT 60 А / 150 В)»."""
    fields = c["fields"]
    fc = fields[i]
    if fc["ctl"]:                                   # отдельный контроллер со своим полем
        j = sum(1 for f in fields[:i + 1] if f["ctl"])
        d = MPPT_DB.get(fc["ctl"])
        return f"доп. MPPT {j}" + (f" ({d[1]})" if d else "")
    word = "вход" if c["builtin"] else "контроллер"
    sl = fc["slots"] or [1]
    if len(sl) > 1:
        return f"{word}ы {sl[0]}–{sl[-1]}" if c["builtin"] else f"контроллеры {sl[0]}–{sl[-1]}"
    return f"{word} {sl[0]}"


def dir_word(aspect):
    """Азимут → «юг», «юго-запад», … (0 — юг, −90 — восток, +90 — запад)."""
    a = (float(aspect) + 360) % 360
    return ("юг", "юго-запад", "запад", "северо-запад", "север", "северо-восток", "восток", "юго-восток")[int((a + 22.5) // 45) % 8]


def field_mates(c, i):
    """Другие поля на том же входе MPPT, что и поле i (параллельно): [индексы]."""
    fc = c["fields"][i]
    if not fc["slots"]:
        return []
    return [j for j in c["slots"].get(fc["slots"][0], []) if j != i]


def shared_status(c, sh, tmin, tmax):
    """Общий вход: несколько полей параллельно → (уровень, пояснение, цифры). Напряжения цепочек должны быть
    близки (MPPT держит одно на всех), сумма токов — в пределе входа, 3+ цепочек — предохранители."""
    fields = c["fields"]
    mem = [fields[i] for i in sh["members"]]
    vm = [f["ns"] * f["vmp"] for f in mem]
    spread = (max(vm) - min(vm)) / max(vm) * 100
    isc = sum(f["np"] * f["isc"] for f in mem)
    imp = sum(f["np"] * f["imp"] for f in mem)
    nstr = sum(f["np"] for f in mem)
    h = mem[0]
    nums = dict(vm=vm, spread=spread, isc=isc, imp=imp, nstr=nstr)
    msgs, lvl = [], "ok"
    if spread > 15:
        lvl = "err"
        msgs.append(f"напряжения цепочек слишком разные ({' / '.join(f'{v:.0f}' for v in vm)} В) — большие потери")
    elif spread > 3:
        lvl = "warn"
        msgs.append(f"Vmp цепочек {' / '.join(f'{v:.0f}' for v in vm)} В — разница {spread:.0f}%, MPPT держит одно")
    if h["iin_max"] > 0 and imp > h["iin_max"]:
        lvl = "err" if lvl == "err" else "warn"
        msgs.append(f"ток входа до {imp:.1f} А > {h['iin_max']:g} А — срезка")
    if nstr >= 3:
        lvl = "err" if lvl == "err" else "warn"
        msgs.append(f"{nstr} цепочек параллельно — предохранитель на каждую")
    return lvl, "; ".join(msgs), nums


def field_status(fc, tmin, tmax):
    """Проверка поля на своём MPPT → (уровень, пояснение, цифры: vmp, voc, voc_cold, i, p)."""
    ns, np_ = fc["ns"], fc["np"]
    voc_cold = ns * fc["voc"] * (1 + fc["bvoc"] * (tmin - 25))
    nums = dict(vmp=ns * fc["vmp"], voc=ns * fc["voc"], voc_cold=voc_cold, i=np_ * fc["imp"], p=fc["pstc_tot"],
                npan=fc["npan"])
    if voc_cold > fc["v_max"]:
        return "err", f"Voc на морозе {voc_cold:.0f} В > {fc['v_max']:.0f} В — MPPT сгорит", nums
    if ns * fc["vmp"] < fc["vin_min"]:
        return "err", f"Vmp {ns * fc['vmp']:.0f} В < {fc['vin_min']:.0f} В — MPPT не запустится", nums
    msgs = []
    tc_hot = tmax + fc["noctk"] * 1000
    vmp_hot = ns * fc["vmp"] * (1 + fc["bvmp"] * (tc_hot - 25))
    if vmp_hot < fc["vin_min"]:
        msgs.append(f"в жару Vmp ≈{vmp_hot:.0f} В < {fc['vin_min']:.0f} В")
    vmp_cold = ns * fc["vmp"] * (1 + fc["bvmp"] * (tmin - 25))
    if fc["vmpp_max"] > 0 and vmp_cold > fc["vmpp_max"]:
        msgs.append(f"на морозе Vmp {vmp_cold:.0f} В выше окна {fc['vmpp_max']:.0f} В")
    if fc["iin_max"] > 0 and np_ * fc["imp"] > fc["iin_max"]:
        msgs.append(f"ток {np_ * fc['imp']:.1f} А > {fc['iin_max']:.0f} А на вход — срезка")
    if voc_cold > 0.95 * fc["v_max"]:
        msgs.append(f"Voc на морозе {voc_cold:.0f} В — впритык к {fc['v_max']:.0f} В")
    return ("warn" if msgs else "ok"), "; ".join(msgs), nums


def inv_inputs_used(c):
    """Сколько входов MPPT инвертора (или контроллеров основной модели) занято полями (общий вход — один)."""
    return len(c["slots"])


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
             ("Рассогласование + поправка", 2, 3), ("Окно MPPT / лимит тока / общий вход", 3, 4),
             ("Провод и контакты", 4, 5), ("КПД MPPT + собственное потребление", 5, 6),
             ("Упор в макс. ток заряда", 6, 7), ("Провод MPPT → АКБ", 7, 8))
