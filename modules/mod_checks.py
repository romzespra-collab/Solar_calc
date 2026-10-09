"""mod_checks.py  v1.9.9
проверки схемы, проводов, MPPT, АКБ, инвертора

Журнал:
v1.9.9: общий вход MPPT (shared_checks): поля параллельно — напряжение входа за год, потери против отдельных
        входов (кВт·ч, %), срезка током входа, обратный ток в поле, предохранители при 3+ цепочках, Isc входа,
        разные панели; поле — «Поле N → вход 1 ∥ поле 1»; полей больше, чем входов, — совет «параллельно».
v1.9.7: гибрид + отдельные MPPT: проверка кабеля контроллер → АКБ (раньше не проверялся), заряд — «инвертор
        до N А + отдельные MPPT до M А», упор в пределы — «инвертора и отдельных MPPT»; «цепочки» — по числу.
v1.9.0: проверки каждого поля на своём входе MPPT / контроллере; полей больше, чем входов у инвертора, — ошибка.
v1.7.0: разные сборки АКБ: состав банка, разная химия — ошибка, разное напряжение сборок — предупреждение.
v1.5.1: АКБ задаются сборками — проверок «мало АКБ» и «лишние АКБ» больше нет.
v1.3.0: вынесено из solar_calc.pyw v1.2.1; проверки на один вход MPPT (k входов/контроллеров),
        встроенный MPPT гибрида (предел мощности PV, ток заряда), напряжение АКБ инвертора.
"""

from .mod_base import MONTHS_S, DAYS
from .mod_model import (wire_r, year_kwh, ampacity, bank_desc, group_name, field_label, field_status, inv_inputs_used,
                        plural, shared_status, dir_word, fmt_t, field_mates)
from .mod_panels import PANEL_DB


def make_checks(s, c, res):
    """→ [(уровень 'ok'|'warn'|'err'|'info', текст)]."""
    ch = []
    ns, np_, k = c["ns"], c["np"], c["k"]
    per = f" (на каждый из {k} входов)" if k > 1 else ""
    tmin, tmax = float(s["t_min"]), float(s["t_max"])
    voc_cold = ns * c["voc"] * (1 + c["bvoc"] * (tmin - 25))
    if voc_cold > c["v_max"]:
        ch.append(("err", f"Voc на морозе {tmin:.0f}°C = {voc_cold:.1f} В > {c['v_max']:.0f} В — MPPT может сгореть. Меньше панелей последовательно."))
    elif voc_cold > 0.95 * c["v_max"]:
        ch.append(("warn", f"Voc на морозе {tmin:.0f}°C = {voc_cold:.1f} В — впритык к {c['v_max']:.0f} В."))
    else:
        ch.append(("ok", f"Voc на морозе {tmin:.0f}°C = {voc_cold:.1f} В (лимит {c['v_max']:.0f} В)."))
    vmp_cold = ns * c["vmp"] * (1 + c["bvmp"] * (tmin - 25))
    if c["vmpp_max"] > 0 and vmp_cold > c["vmpp_max"]:
        ch.append(("warn", f"Vmp на морозе {vmp_cold:.0f} В выше окна MPPT ({c['vmpp_max']:.0f} В)."))
    tc_hot = tmax + c["noctk"] * 1000
    istc = np_ * c["imp"]
    R_hot = wire_r(c, tmax)
    vin_hot = ns * c["vmp"] * (1 + c["bvmp"] * (tc_hot - 25)) - istc * R_hot
    if vin_hot < c["vin_min"]:
        ch.append(("warn", f"В жару (панели ≈{tc_hot:.0f}°C) на входе MPPT ≈{vin_hot:.1f} В < нужных {c['vin_min']:.1f} В — летом часть мощности теряется. Больше панелей последовательно."))
    else:
        ch.append(("ok", f"В жару на входе MPPT ≈{vin_hot:.1f} В — запас над нужными {c['vin_min']:.1f} В есть."))
    R20 = wire_r(c, 20)
    du = istc * R20 / (ns * c["vmp"]) * 100
    ploss = istc * istc * R20
    lvl = "ok" if du <= 2 else "warn" if du <= 5 else "err"
    ch.append((lvl, f"Падение на проводе и контактах при полном солнце{per}: {du:.2f}% ({istc * R20:.2f} В, {ploss:.0f} Вт). Норма ≤ 2%, зимой ток меньше — и потери меньше."))
    isc_arr = np_ * c["isc"]
    amp = ampacity(float(s["wire_s"]), s["wire_mat"])
    if isc_arr * 1.25 > amp:
        ch.append(("err", f"Провод {s['wire_s']} мм² ({'Al' if s['wire_mat'] == 'al' else 'Cu'}) держит ≈{amp:.0f} А (открыто, ПУЭ), а нужно Isc×1.25 = {isc_arr * 1.25:.0f} А."))
    else:
        ch.append(("ok", f"Провод по току: Isc×1.25 = {isc_arr * 1.25:.0f} А при допустимых ≈{amp:.0f} А."))
    if c["iin_max"] > 0 and isc_arr > c["iin_max"]:
        ch.append(("warn", f"Isc на вход {isc_arr:.1f} А > макс. входного тока MPPT {c['iin_max']:.0f} А — MPPT будет срезать."))
    if np_ >= 3:
        ch.append(("warn", f"{np_} {plural(np_, 'параллельная цепочка', 'параллельные цепочки', 'параллельных цепочек')}{per}"
                           f" — нужен предохранитель на каждую (обратный ток при КЗ)."))
    # другие поля: каждое на своём входе MPPT / своём контроллере
    for i, fc in enumerate(c["fields"][1:], 1):
        lvl, msg, n = field_status(fc, tmin, tmax)
        lab = field_label(c, i)
        mates = field_mates(c, i)
        if mates:
            lab += " ∥ " + ", ".join(f"поле {j + 1}" for j in mates)
        what = (f"Поле {i + 1} → {lab}: {n['npan']} {plural(n['npan'], 'панель', 'панели', 'панелей')} "
                f"({fc['ns']} посл. × {fc['np']} пар.), "
                f"Vmp {n['vmp']:.0f} В, Voc на морозе {n['voc_cold']:.0f} В, ток {n['i']:.1f} А")
        ch.append((lvl, what + (f" — {msg}." if msg else " — в норме.")))
    ch += shared_checks(c, res, tmin, tmax)
    used = inv_inputs_used(c)
    nmax = int(float(s["n_mppt_max"]))
    if used > nmax:
        ch.insert(0, ("err", (f"Полей на {used} входов MPPT, а у инвертора {nmax}." if c["builtin"] else
                              f"Полей на {used} контроллеров, а указано {nmax} шт.")
                      + " Уберите поле или подключите его параллельно на занятый вход (правый клик по полю → "
                        "«На вход …») — лучше к полю с тем же числом таких же панелей последовательно."))
    if year_kwh(res, "clear") < 0.02 * c["pstc_tot"] / 1000 * 365:
        ch.insert(0, ("err", f"MPPT почти не запускается: Vmp цепочки {ns * c['vmp']:.1f} В, а нужно больше {c['vin_min']:.1f} В. Больше панелей последовательно."))
    clip_y = sum((res[(m, 'avg')]['wh'][6] - res[(m, 'avg')]['wh'][7]) * DAYS[m] for m in range(12)) / 1000
    y = year_kwh(res, "avg")
    clip_pct = clip_y / max(y + clip_y, 1e-9) * 100
    if c["builtin"]:
        pv = c["pv_pmax"]
        if pv > 0:
            peak_w = max(res[(m, 'clear')]["peak"] for m in range(12))
            if clip_y > 0.01 * max(y, 1e-9):
                who = f"инвертора {pv / 1000:g} кВт" + (" и отдельных MPPT (их ток заряда)" if c["mixed"] else "")
                ch.append(("warn", f"Упор в предел мощности PV {who}: теряется ≈{clip_y:.0f} кВт·ч/год ({clip_pct:.1f}%)."))
            else:
                ch.append(("ok", f"Мощность PV: пик ≈{peak_w / 1000:.1f} кВт из {pv / 1000:g} кВт по паспорту инвертора."))
            if c["pstc_tot"] > 1.3 * pv:
                ch.append(("warn", f"Панелей {c['pstc_tot'] / 1000:.1f} кВт — больше предела PV инвертора {pv / 1000:g} кВт на "
                                   f"{(c['pstc_tot'] / pv - 1) * 100:.0f}%. Проверьте паспорт (Max PV input power)."))
    else:
        peak_all = max(res[(m, 'clear')]["peak_i"] for m in range(12))
        who = "MPPT" if c["ilim"] >= c["iout_tot"] else f"АКБ (до {c['bank_ich']:.0f} А)"
        if clip_y > 0.01 * max(y, 1e-9):
            ch.append(("warn", f"Упор в ток заряда {c['ilim']:.0f} А (ограничивает {who}): теряется ≈{clip_y:.0f} кВт·ч/год ({clip_pct:.1f}%)."))
        else:
            ch.append(("ok", f"Ток заряда: пик ≈{peak_all:.1f} А из {c['ilim']:.0f} А (ограничивает {who})."))
    ratio = ns * c["vmp"] / c["vbat"]
    if c["etak"] > 0 and ratio > 2.5:
        ch.append(("warn", f"Vmp/Vакб = {ratio:.1f} — дешёвые MPPT теряют КПД при большом отношении."))
    if s["wire_mat"] == "al":
        ch.append(("info", "Алюминий: только клеммы Al/Cu и контактная паста, иначе контакты окисляются и греются."))
    if float(s["horizon"]) > 0:
        ch.append(("info", f"Прямое солнце ниже {float(s['horizon']):.0f}° над горизонтом не учитывается (деревья, дома)."))
    return ch


def shared_checks(c, res, tmin, tmax):
    """Общие входы MPPT (несколько полей параллельно): как ведут себя за год — напряжение входа, потери против
    отдельных входов, срезка током входа, обратный ток в поле, предохранители, разные панели."""
    ch = []
    fields = c["fields"]
    head = "Вход MPPT" if c["builtin"] else "Контроллер"       # «Вход MPPT 1» / «Контроллер 1»
    of = "входа MPPT" if c["builtin"] else "контроллера"
    for q, sh in enumerate(c["shared"]):
        mem = sh["members"]
        lvl, msg, n = shared_status(c, sh, tmin, tmax)
        names = " + ".join(f"поле {i + 1}" for i in mem)
        st = {(m, w): res[(m, w)]["shared"][q] for m in range(12) for w in ("avg", "clear") if (m, w) in res}
        y = {k: sum(st[(m, "avg")][k] * DAYS[m] for m in range(12) if (m, "avg") in st) / 1000 for k in ("comb", "free", "sep")}
        mis, clip = max(0.0, y["sep"] - y["free"]), max(0.0, y["free"] - y["comb"])
        pct = mis / max(y["sep"], 1e-9) * 100
        vs = [a for a in st.values() if a["vmax"] > 0]
        vr = f"{min(a['vmin'] for a in vs):.0f}–{max(a['vmax'] for a in vs):.0f} В" if vs else "—"
        sides = {(fields[i]["tilt"], fields[i]["aspect"]) for i in mem}
        dirs = ", ".join(f"{fields[i]['tilt']:g}° {dir_word(fields[i]['aspect'])}" for i in mem)
        why = ""
        if n["spread"] > 3:
            why = (f" Цепочки разного напряжения (Vmp {' / '.join(f'{v:.0f}' for v in n['vm'])} В), а MPPT держит одно "
                   f"на всех — уравняйте число панелей последовательно или поставьте поля на разные входы.")
        elif len(sides) > 1:
            why = (" Поля смотрят в разные стороны: токи складываются, а напряжение почти одно — так подключать "
                   "можно, пик входа ниже суммы полей.")
        lv = "ok" if pct <= 1 else "warn" if pct <= 4 else "err"
        ch.append((lv, f"{head} {sh['n']}: {names} параллельно ({dirs}) — напряжение {vr}; против "
                       f"отдельных входов теряется ≈{mis:.0f} кВт·ч/год ({pct:.1f}%).{why}"))
        clr = [(st[(m, "clear")]["imax"], st[(m, "clear")]["tmax"], m) for m in range(12) if (m, "clear") in st]
        if clr:
            ipk, tpk, mpk = max(clr)
            imax = fields[mem[0]]["iin_max"]
            cp = clip / max(y["free"], 1e-9) * 100
            if imax > 0 and (cp > 0.5 or ipk >= 0.99 * imax):
                ch.append(("warn" if cp > 0.5 else "info",
                           f"Ток {of} {sh['n']} упирается в предел {imax:g} А (сумма полей до {n['imp']:.1f} А, "
                           f"в ясный полдень): срезка ≈{clip:.0f} кВт·ч/год ({cp:.1f}%)."))
            else:
                ch.append(("ok", f"Ток {of} {sh['n']}: пик ≈{ipk:.1f} А в ясный день ({MONTHS_S[mpk]}, "
                                 f"{fmt_t(tpk)})" + (f" из {imax:g} А." if imax > 0 else ".")))
        for i in mem:
            rv = min((a["irev"].get(i, 0.0) for a in st.values()), default=0.0)
            if rv < -0.05:
                ch.append(("err", f"Поле {i + 1} на входе {sh['n']} забирает ток до {-rv:.1f} А — его Voc ниже "
                                  f"напряжения входа. Так подключать нельзя: одинаковое число панелей последовательно "
                                  f"или разные входы."))
        if n["nstr"] >= 3:
            ch.append(("warn", f"На входе {sh['n']} {n['nstr']} {plural(n['nstr'], 'цепочка', 'цепочки', 'цепочек')} "
                               f"параллельно — на каждую предохранитель (при КЗ в одной в неё идёт ток остальных)."))
        h = fields[mem[0]]
        if h["iin_max"] > 0 and n["isc"] > h["iin_max"]:
            ch.append(("info", f"Isc входа {sh['n']} — {n['isc']:.1f} А (больше рабочего {h['iin_max']:g} А): MPPT "
                               f"ограничит ток, но проверьте в паспорте «макс. ток КЗ входа» (Isc max)."))
        keys = {fields[i]["key"] for i in mem}
        if len(keys) > 1:
            pn = [PANEL_DB[k][1] if k in PANEL_DB else k for k in keys]
            ch.append(("info", f"На входе {sh['n']} разные панели ({'; '.join(pn)}): токи складываются — это "
                               f"нормально, если Vmp цепочек близки."))
        if msg and lvl == "err" and pct <= 4:
            ch.append(("warn", f"Вход {sh['n']}: {msg}."))
    return ch


def bat_checks(s, c, res, bal):
    ch = []
    sv = int(s["bat_v"])
    iv = int(float(s.get("inv_bat_v", 0) or 0))
    if iv and iv != sv:
        ch.append(("err", f"Инвертор рассчитан на АКБ {iv} В, а выбрана система {sv} В."))
    groups = c["groups"]
    for gr in groups:
        if gr["bad_v"]:
            ch.append(("err", f"{group_name(gr)}: АКБ по {gr['unit_v']:g} В не собрать в систему {sv} В."))
    ch.append(("ok", f"Банк: {bank_desc(c)} ({c['units']} шт) = {c['bank_ah']:.0f} А·ч, "
                     f"{c['bank_wh'] / 1000:.1f} кВт·ч, полезно {c['usable_wh'] / 1000:.1f} кВт·ч."))
    if len({gr["chem"] for gr in groups}) > 1:
        ch.append(("err", "В параллель стоят литий и свинец — так нельзя: разные напряжения заряда, свинец недозаряжен "
                          "или литий перезаряжен. Разнесите на разные системы."))
    elif len(groups) > 1:
        vs = [gr["v"] for gr in groups]
        if (max(vs) - min(vs)) / max(vs) > 0.015:
            ch.append(("warn", f"Сборки разного напряжения в параллель ({', '.join(f'{v:.1f}' for v in vs)} В): "
                               f"ток делится неравномерно, одна сборка недозаряжается. Лучше одинаковое число последовательно."))
        else:
            ch.append(("info", "Разные сборки в параллель: ток делится по ёмкости и сопротивлению — поставьте каждой "
                               "свой предохранитель/автомат и одинаковой длины провода до общей шины."))
    if any(gr["chem"] == "lfp" for gr in groups) and float(s["t_bat"]) < 0:
        ch.append(("err", f"LiFePO4 нельзя заряжать ниже 0°C (у вас {float(s['t_bat']):.0f}°C) — BMS отключит заряд. Нужно тёплое место или подогрев."))
    if s["chem"] == "lead" and float(s["bat_dod"]) > 50:
        ch.append(("warn", f"Свинец при разряде глубже 50% быстро умирает (у вас {float(s['bat_dod']):.0f}%)."))
    # ток разряда на инвертор
    if c["npar"] > 0:
        i_inv = c["inv_p"] / max(0.5, c["inv_eta"]) / (c["sys_nom"] * 0.95)
        c_rate = i_inv / max(1.0, c["bank_ah"])
        lim = 1.0 if s["chem"] == "lfp" else 0.5
        if c_rate > lim:
            ch.append(("warn", f"Инвертор на полной мощности тянет {i_inv:.0f} А = {c_rate:.2f}C — больше, чем банк держит ({lim:g}C)."))
        amp = ampacity(float(s["iw_s"]), s["iw_mat"])
        du = i_inv * c["ri"] / c["sys_nom"] * 100
        if i_inv * 1.25 > amp:
            ch.append(("err", f"Провод АКБ→инвертор {float(s['iw_s']):g} мм² держит ≈{amp:.0f} А, а на полной мощности {i_inv:.0f} А."))
        lvl = "ok" if du <= 1 else "warn" if du <= 2 else "err"
        ch.append((lvl, f"Провод АКБ→инвертор: на {c['inv_p'] / 1000:.1f} кВт ток {i_inv:.0f} А, падение {du:.2f}% "
                        f"({i_inv * c['ri']:.2f} В, {i_inv ** 2 * c['ri']:.0f} Вт). Норма ≤ 1%."))
    ib = c["ilim"]
    if c["builtin"]:
        i_inv = c["pch_inv"] / c["vbat"]
        i_ctl = sum(fc["iout"] for fc in c["fields"] if fc["ctl"])
        if i_ctl:
            ch.append(("info", f"Заряд АКБ от солнца: инвертор до {i_inv:.0f} А + отдельные MPPT до {i_ctl:.0f} А, "
                               f"вместе до {ib:.0f} А (АКБ берёт до {c['bank_ich']:.0f} А); лишнее солнце инвертора пропадает."))
            i1 = max(fc["iout"] for fc in c["fields"] if fc["ctl"])          # у каждого контроллера свой кабель
            amp = ampacity(float(s["bw_s"]), s["bw_mat"])
            dub = i1 * c["rb_ctl"] / c["vbat"] * 100
            if i1 * 1.25 > amp:
                ch.append(("err", f"Провод MPPT→АКБ {float(s['bw_s']):g} мм² держит ≈{amp:.0f} А, а ток отдельного MPPT до {i1:.0f} А."))
            lvl = "ok" if dub <= 1 else "warn" if dub <= 2 else "err"
            ch.append((lvl, f"Провод отдельного MPPT→АКБ: при {i1:.0f} А падение {dub:.2f}% ({i1 * c['rb_ctl']:.2f} В). Норма ≤ 1%."))
        else:
            who = "инвертор" if ib >= c["iout_tot"] else f"АКБ (до {c['bank_ich']:.0f} А)"
            ch.append(("info", f"Заряд АКБ от солнца до {ib:.0f} А (ограничивает {who}); пока АКБ не берёт больше — "
                               f"солнце идёт в дом, остальное пропадает."))
    else:
        dub = ib * c["rb"] / c["vbat"] * 100
        amp = ampacity(float(s["bw_s"]), s["bw_mat"])
        if ib * 1.25 > amp:
            ch.append(("err", f"Провод MPPT→АКБ {float(s['bw_s']):g} мм² держит ≈{amp:.0f} А, а ток заряда до {ib:.0f} А."))
        lvl = "ok" if dub <= 1 else "warn" if dub <= 2 else "err"
        ch.append((lvl, f"Провод MPPT→АКБ: при {ib:.0f} А падение {dub:.2f}% ({ib * c['rb']:.2f} В). Норма ≤ 1%."))
    # холостой ход
    idle = c["inv_idle"] * c["inv_hours"]
    dec = res[(11, "avg")]["wh"][8]
    share = idle / dec * 100 if dec > 0 else 999
    lvl = "warn" if share > 30 else "info"
    ch.append((lvl, f"Холостой ход инвертора {c['inv_idle']:.0f} Вт × {c['inv_hours']:.0f} ч = {idle / 1000:.2f} кВт·ч/сут "
                    f"— это {share:.0f}% средней выработки декабря."))
    # ночь и автономия
    worst = max(bal, key=lambda r: r["need"])
    if c["usable_wh"] > 0:
        if c["usable_wh"] * c["eta_bat"] < worst["night"]:
            ch.append(("warn", f"На вечер/ночь зимой нужно ≈{worst['night'] / 1000:.1f} кВт·ч, а полезная ёмкость {c['usable_wh'] / 1000:.1f} кВт·ч."))
        days = c["usable_wh"] * c["eta_bat"] / max(1.0, worst["need_dc"])
        ch.append(("info", f"Полный банк без солнца зимой продержится ≈{days * 24:.0f} ч ({days:.1f} сут)."))
    y_load = sum(r["load"] * DAYS[m] for m, r in enumerate(bal)) / 1000
    y_need = sum(r["need"] * DAYS[m] for m, r in enumerate(bal)) / 1000
    y_gen = year_kwh(res, "avg")
    ch.append(("info", f"За год: дом потребляет ≈{y_load:.0f} кВт·ч, с учётом инвертора и АКБ нужно ≈{y_need:.0f} кВт·ч, "
                       f"станция даёт ≈{y_gen:.0f} кВт·ч ({y_gen / max(y_need, 1e-9) * 100:.0f}% от нужного; летние излишки не переносятся на зиму)."))
    deficit = [MONTHS_S[m] for m, r in enumerate(bal) if r["bal"]["avg"] < 0]
    if deficit:
        ch.append(("warn", "В средний день выработки не хватает: " + ", ".join(deficit) + " — нужна сеть/генератор или больше панелей."))
    else:
        ch.append(("ok", "Средний день каждого месяца покрывает потребление."))
    return ch
