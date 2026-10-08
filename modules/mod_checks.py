"""mod_checks.py  v1.3.0
проверки схемы, проводов, MPPT, АКБ, инвертора

Журнал:
v1.3.0: вынесено из solar_calc.pyw v1.2.1; проверки на один вход MPPT (k входов/контроллеров),
        встроенный MPPT гибрида (предел мощности PV, ток заряда), напряжение АКБ инвертора.
"""

from .mod_base import MONTHS_S, DAYS
from .mod_model import wire_r, year_kwh, ampacity


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
        ch.append(("warn", f"{np_} параллельных цепочки{per} — нужен предохранитель на каждую (обратный ток при КЗ)."))
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
                ch.append(("warn", f"Упор в предел мощности PV инвертора {pv / 1000:g} кВт: теряется ≈{clip_y:.0f} кВт·ч/год ({clip_pct:.1f}%)."))
            else:
                ch.append(("ok", f"Мощность PV: пик ≈{peak_w / 1000:.1f} кВт из {pv / 1000:g} кВт по паспорту инвертора."))
            if c["pstc_tot"] > 1.3 * pv:
                ch.append(("warn", f"Панелей {c['pstc_tot'] / 1000:.1f} кВт — больше предела PV инвертора {pv / 1000:g} кВт на "
                                   f"{(c['pstc_tot'] / pv - 1) * 100:.0f}%. Проверьте паспорт (Max PV input power)."))
    else:
        peak_all = max(res[(m, 'clear')]["peak_i"] for m in range(12))
        who = "MPPT" if c["ilim"] >= c["iout_tot"] else f"АКБ ({c['bank_ah']:.0f} А·ч × {float(s['bat_c']):g}C)"
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


def bat_checks(s, c, res, bal):
    ch = []
    sv = int(s["bat_v"])
    iv = int(float(s.get("inv_bat_v", 0) or 0))
    if iv and iv != sv:
        ch.append(("err", f"Инвертор рассчитан на АКБ {iv} В, а выбрана система {sv} В."))
    if c["mismatch_v"]:
        ch.append(("err", f"АКБ по {float(s['bat_unit_v']):g} В не собрать в систему {sv} В."))
    if c["npar"] == 0:
        ch.append(("err", f"Мало АКБ: для {sv} В нужно {c['nser']} шт последовательно, а указано {int(s['bat_count'])}."))
    else:
        ch.append(("ok", f"Банк: {c['nser']}S{c['npar']}P = {c['bank_v']:.1f} В {c['bank_ah']:.0f} А·ч = "
                         f"{c['bank_wh'] / 1000:.1f} кВт·ч, полезно {c['usable_wh'] / 1000:.1f} кВт·ч."))
    if c["extra"] > 0:
        ch.append(("warn", f"{c['extra']} АКБ лишние: собираются группами по {c['nser']} шт последовательно."))
    if s["chem"] == "lfp" and float(s["t_bat"]) < 0:
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
        who = "инвертор" if ib >= c["iout_tot"] else f"АКБ ({c['bank_ah']:.0f} А·ч × {float(s['bat_c']):g}C)"
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
