"""mod_page_results.py  v1.9.2
страницы «Прогноз», «Покрытие дома», «Горсеть», отчёт

Журнал:
v1.9.2: «Поле 1: …» — панели и мощность только поля 1 (раньше — всех полей); при нескольких полях — «всего …».
v1.8.0: «Поле: … · 2 входа MPPT × по 9 панелей (9 посл. × 1 пар.)» — сколько панелей на каждый вход.
v1.7.0: банк из разных сборок: состав «16S1P LF280K + 16S2P LF105», вес по всем сборкам, в отчёте — состав.
v1.5.1: АКБ сборками: «4 сборки × 16 последовательно = 64 шт»; совет «докупить» — в сборках.
v1.3.0: вынесено из solar_calc.pyw v1.2.1; поле на k входов MPPT, встроенный MPPT гибрида (нет провода
        MPPT→АКБ, упор в предел мощности PV), отчёт с инвертором и MPPT.
"""

import csv
import math
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QGridLayout, QFileDialog

from .mod_base import MONTHS, MONTHS_S, DAYS, WEATHER, W_KEYS, WEATHER_ADJ, MONTHS_IN, log
from .mod_equipment import CELL_INFO, INVERTER_PRESETS, MPPT_PRESETS
from .mod_sun import DT
from .mod_fields import WIRE_S_KEYS, s2d
from .mod_model import wire_r, sim_point, load_day_wh, soc_series, grid_times, fmt_t, LOSS_ROWS, bank_desc, layout_text
from .mod_theme import _OK, _ERR, _WARN, SERIES_COL
from .mod_widgets import (app_name, app_version, Segmented, Stepper, _lab, _card, _btn, _save_failed, _fmt,
                          Chart, make_table, _item)


def _packs(n):
    """1 сборка, 2 сборки, 5 сборок."""
    n = int(n)
    w = "сборка" if n % 10 == 1 and n % 100 != 11 else ("сборки" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "сборок")
    return f"{n} {w}"


class ResultsPages:
    """Часть главного окна App (миксин)."""

    def _page_forecast(self):
        rin = QWidget()
        rv = QVBoxLayout(rin)
        rv.setContentsMargins(16, 16, 16, 16)
        rv.setSpacing(12)
        self.kpi = {}
        rv.addLayout(self._mw_bar("Прогноз выработки", [_btn("📋 Отчёт", "chip", "Скопировать текстовый отчёт", self.copy_report)]))
        rv.addLayout(self._kpi_grid((("clear", "☀ Ясный день, в АКБ"), ("avg", "⛅ Средний день"),
                                     ("over", "☁ Пасмурный день"), ("peak", "Пик мощности (ясно)"),
                                     ("year", "За год (средняя погода)"), ("wire", "Провод + контакты"))))
        fr, v = _card("Мощность по часам — средний день месяца (в АКБ)")
        self.ch_hour = Chart("line", "Вт")
        self.ch_hour.setMinimumHeight(260)
        v.addWidget(self.ch_hour)
        self.charts.append(self.ch_hour)
        rv.addWidget(fr)
        fr, v = _card("По месяцам — кВт·ч в сутки")
        self.ch_month = Chart("bar", "кВт·ч")
        self.ch_month.ydec = 2
        v.addWidget(self.ch_month)
        self.charts.append(self.ch_month)
        rv.addWidget(fr)
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        fr, v = _card("Куда уходит энергия (сутки)")
        self.tb_loss = make_table(["Этап", "Вт·ч", "%"])
        self.tb_loss.setMinimumHeight(440)
        v.addWidget(self.tb_loss)
        row2.addWidget(fr, 3)
        fr, v = _card("Мгновенно — при заданном солнце")
        g = QGridLayout()
        g.setHorizontalSpacing(8)
        g.addWidget(_lab("Солнце на панель", "fieldLab"), 0, 0)
        self.st_g = Stepper(0, 1300, 25, 0, "Вт/м²")
        self.st_g.setToolTip("Облучённость плоскости панелей: ясный полдень летом ~1000, зимой ~400, пасмурно 50–150")
        self.st_g.changed.connect(lambda v: self._on_field("pt_g", v))
        g.addWidget(self.st_g, 0, 1)
        g.addWidget(_lab("Воздух", "fieldLab"), 1, 0)
        self.st_t = Stepper(-40, 50, 1, 0, "°C")
        self.st_t.changed.connect(lambda v: self._on_field("pt_t", v))
        g.addWidget(self.st_t, 1, 1)
        v.addLayout(g)
        self.pt_lab = self._rich()
        v.addWidget(self.pt_lab)
        v.addStretch(1)
        row2.addWidget(fr, 2)
        rv.addLayout(row2)
        fr, v = _card("Проверки")
        self.chk_box = QVBoxLayout()
        self.chk_box.setSpacing(4)
        v.addLayout(self.chk_box)
        rv.addWidget(fr)
        rv.addStretch(1)
        return self._results_scroll(rin)

    def _page_home(self):
        rin = QWidget()
        rv = QVBoxLayout(rin)
        rv.setContentsMargins(16, 16, 16, 16)
        rv.setSpacing(12)
        rv.addLayout(self._mw_bar("Покрытие дома"))
        fr, v = _card("Вывод")
        self.home_verdict = self._rich()
        v.addWidget(self.home_verdict)
        rv.addWidget(fr)
        rv.addLayout(self._kpi_grid((("cov", "Покрытие потребления за год"), ("ygrid", "Из сети за год"),
                                     ("ycost", "Платить за сеть в год"), ("need", "Нужно дому в сутки"),
                                     ("bal", "Баланс дня"), ("bank", "АКБ без солнца"))))
        fr, v = _card("Потребление дома по месяцам — кВт·ч в сутки")
        self.ch_cover = Chart("bar", "кВт·ч")
        self.ch_cover.ydec = 2
        self.ch_cover.setMinimumHeight(240)
        v.addWidget(self.ch_cover)
        self.charts.append(self.ch_cover)
        rv.addWidget(fr)
        fr, v = _card("По месяцам: покрытие, сеть, деньги")
        self.tb_cover = make_table(["Месяц", "Дому, кВт·ч/мес", "Покрыто ⛅", "Покрыто ☁", "Покрыто ☀",
                                    "Из сети ⛅, кВт·ч", "За сеть ⛅, грн", "Лишнее ⛅, кВт·ч", "Панелей для 100%"])
        self.tb_cover.setMinimumHeight(360)
        v.addWidget(self.tb_cover)
        rv.addWidget(fr)
        fr, v = _card("Что добавить, чтобы перекрыть потребление")
        self.home_advice = self._rich()
        v.addWidget(self.home_advice)
        rv.addWidget(fr)
        fr, v = _card("Баланс энергии — выработка и потребность, кВт·ч в сутки")
        self.bal_lab = self._rich()
        v.addWidget(self.bal_lab)
        self.tb_bal = make_table(["Месяц", "Дому", "Хол. ход", "Нужно", "Выработка ⛅",
                                  "Баланс ⛅", "Баланс ☁", "Баланс ☀", "За месяц ⛅"])
        self.tb_bal.setMinimumHeight(360)
        v.addWidget(self.tb_bal)
        rv.addWidget(fr)
        rv.addStretch(1)
        return self._results_scroll(rin)

    def _page_grid(self):
        rin = QWidget()
        rv = QVBoxLayout(rin)
        rv.setContentsMargins(16, 16, 16, 16)
        rv.setSpacing(12)
        rv.addLayout(self._mw_bar("Когда на горсеть"))
        fr, v = _card("Типовой день")
        self.grid_sum = self._rich()
        v.addWidget(self.grid_sum)
        rv.addWidget(fr)
        fr, v = _card("Мощность за сутки — солнце, расход, сеть")
        self.ch_gpow = Chart("line", "Вт")
        self.ch_gpow.setMinimumHeight(240)
        v.addWidget(self.ch_gpow)
        self.charts.append(self.ch_gpow)
        rv.addWidget(fr)
        fr, v = _card("Заряд АКБ за сутки")
        self.ch_gsoc = Chart("line", "%")
        self.ch_gsoc.ymax_fixed = 100
        self.ch_gsoc.setMinimumHeight(200)
        v.addWidget(self.ch_gsoc)
        self.charts.append(self.ch_gsoc)
        rv.addWidget(fr)
        fr, v = _card("По месяцам: переход на сеть и обратно, кВт·ч из сети в сутки")
        self.tb_grid = make_table(["Месяц", "⛅ на сеть", "⛅ на АКБ", "⛅ из сети", "☁ на сеть", "☁ на АКБ",
                                   "☁ из сети", "☀ на сеть", "☀ на АКБ", "☀ из сети"])
        self.tb_grid.setMinimumHeight(360)
        v.addWidget(self.tb_grid)
        rv.addWidget(fr)
        fr, v = _card("Серия дней подряд — например, неделя пасмурной погоды")
        ctl = QHBoxLayout()
        ctl.addWidget(_lab("Дней", "fieldLab"))
        self.st_ser_days = Stepper(1, 10, 1, 0, "")
        self.st_ser_days.setMaximumWidth(150)
        self.st_ser_days.changed.connect(lambda v: self._on_field("ser_days", int(v)))
        ctl.addWidget(self.st_ser_days)
        ctl.addSpacing(10)
        self.seg_ser_w = Segmented(WEATHER)
        self.seg_ser_w.changed.connect(lambda k: self._on_field("ser_weather", k))
        ctl.addWidget(self.seg_ser_w)
        ctl.addSpacing(10)
        ctl.addWidget(_lab("Заряд АКБ в начале", "fieldLab"))
        self.st_ser_soc = Stepper(0, 100, 10, 0, "%")
        self.st_ser_soc.setMaximumWidth(150)
        self.st_ser_soc.changed.connect(lambda v: self._on_field("ser_soc0", v))
        ctl.addWidget(self.st_ser_soc)
        ctl.addStretch(1)
        v.addLayout(ctl)
        self.ch_ser = Chart("line", "%")
        self.ch_ser.ymax_fixed = 100
        self.ch_ser.setMinimumHeight(220)
        v.addWidget(self.ch_ser)
        self.charts.append(self.ch_ser)
        self.tb_ser = make_table(["День", "Солнце, кВт·ч", "Расход, кВт·ч", "Из сети, кВт·ч", "Мин. заряд", "На сеть", "На АКБ"])
        self.tb_ser.setMinimumHeight(200)
        v.addWidget(self.tb_ser)
        rv.addWidget(fr)
        rv.addStretch(1)
        return self._results_scroll(rin)

    def _show_results(self):
        R = self.R
        s = self.s
        res, c = R["res"], R["ctx"]
        m = int(s["month"])
        wsel = s["weather"]
        self.src_lab.setText("Солнце: " + self.sd.label(float(s["lat"]), float(s["lon"])))
        pk = c["pstc_tot"]                                  # все поля
        lay = layout_text(c["k"], c["ns"], c["np"], not c["builtin"])
        nf = len(c["fields"])
        self.lab_total.setText(f"Поле 1: {c['main_npan']} панелей × {c['pmax']:.0f} Вт = {c['main_pstc'] / 1000:.2f} кВт · {lay} · "
                               f"цепочка Vmp {c['ns'] * c['vmp']:.1f} В / Voc {c['ns'] * c['voc']:.1f} В · "
                               f"ток {c['np'] * c['imp']:.1f} А на вход"
                               + (f" · всего {nf} поля: {c['npan']} панелей, {c['pstc_tot'] / 1000:.2f} кВт" if nf > 1 else ""))
        for w in W_KEYS:
            d = res[(m, w)]
            val, sub = self.kpi[w]
            val.setText(f"{_fmt(d['wh'][8] / 1000, 2)} кВт·ч")
            sub.setText(f"{dict(WEATHER)[w]} · {MONTHS[m].lower()} · пик {_fmt(d['peak'])} Вт")
        dclear = res[(m, "clear")]
        self.kpi["peak"][0].setText(f"{_fmt(dclear['peak'])} Вт")
        self.kpi["peak"][1].setText(f"Пик (ясно, {MONTHS_S[m]}) · {'ток на шине АКБ' if c['builtin'] else 'ток заряда'} {dclear['peak_i']:.1f} А")
        self.kpi["year"][0].setText(f"{_fmt(R['year']['avg'])} кВт·ч")
        self.kpi["year"][1].setText(f"За год · {R['year']['avg'] / max(pk / 1000, 1e-9):.0f} кВт·ч/кВт · ясно всегда {_fmt(R['year']['clear'])}")
        dw = res[(m, wsel)]["wh"]
        wl = (dw[4] - dw[5]) / dw[4] * 100 if dw[4] > 0 else 0
        self.kpi["wire"][0].setText(f"{wl:.2f} %")
        self.kpi["wire"][1].setText(f"Провод + контакты · {_fmt(dw[4] - dw[5])} Вт·ч/сут · R={wire_r(c, 20) * 1000:.0f} мОм")
        br = R["bal"][m]
        self.kpi["need"][0].setText(f"{_fmt(br['need'] / 1000, 2)} кВт·ч")
        self.kpi["need"][1].setText(f"Нужно в сутки · дом {_fmt(br['load'] / 1000, 2)} + холостой ход {_fmt(br['idle'] / 1000, 2)}")
        bv = br["bal"][wsel]
        self.kpi["bal"][0].setText(f"{'+' if bv >= 0 else '−'}{_fmt(abs(bv) / 1000, 2)} кВт·ч")
        self.kpi["bal"][0].setStyleSheet(f"color: {_OK if bv >= 0 else _ERR};")
        self.kpi["bal"][1].setText(f"Баланс · {WEATHER_ADJ[wsel]} день · {MONTHS_S[m]}")
        if c["usable_wh"] > 0:
            hrs = c["usable_wh"] * c["eta_bat"] / max(1.0, br["need_dc"]) * 24
            self.kpi["bank"][0].setText(f"{hrs:.0f} ч")
            self.kpi["bank"][1].setText(f"АКБ без солнца · {c['bank_wh'] / 1000:.1f} кВт·ч, полезно {c['usable_wh'] / 1000:.1f}")
        else:
            self.kpi["bank"][0].setText("нет АКБ")
            self.kpi["bank"][1].setText("Проверьте количество и напряжение АКБ")
        if len(c["groups"]) > 1:
            head = f"{len(c['groups'])} разные сборки параллельно: {bank_desc(c)} = {c['units']} шт"
        elif c["nser"] > 1:
            head = f"{_packs(c['npar'])} × {c['nser']} шт последовательно ({c['nser']}S{c['npar']}P) = {c['units']} шт"
        else:
            head = f"{c['npar']} шт параллельно"
        self.lab_bank.setText(
            head + f" · {c['bank_v']:.1f} В, {c['bank_ah']:.0f} А·ч, {c['bank_wh'] / 1000:.1f} кВт·ч "
              f"(полезно {c['usable_wh'] / 1000:.1f}) · ток заряда до {c['bank_ich']:.0f} А" + self._cell_info(c))
        # потери в кабелях словами: при полном солнце (STC) и при полной мощности инвертора
        i_pv = c["np"] * c["imp"]
        r_pv = wire_r(c, 20)
        p_in = c["ns"] * c["np"] * c["pmax"]
        loss_pv = i_pv ** 2 * r_pv
        i_inv = c["inv_p"] / max(0.5, c["inv_eta"]) / (c["sys_nom"] * 0.95)
        dest = "контроллера" if not c["builtin"] else "инвертора"
        self.lab_wire.setText(
            f"Кабель панелей: {float(s['wire_len']):g} м до {dest} → провода «+» и «−» = {2 * float(s['wire_len']):g} м, "
            f"{float(s['wire_s']):g} мм² {'медь' if s['wire_mat'] == 'cu' else 'алюминий'}; с разъёмами {r_pv * 1000:.0f} мОм. "
            f"При полном солнце ток {i_pv:.1f} А → теряется ≈{loss_pv:.0f} Вт ({loss_pv / max(1.0, p_in) * 100:.1f}%)"
            + (f" на каждом из {c['k']} полей" if c["k"] > 1 else "") + ". "
            + ("" if c["builtin"] else f"Контроллер→АКБ {c['rb'] * 1000:.1f} мОм. ")
            + f"АКБ→инвертор: {c['ri'] * 1000:.1f} мОм, на {c['inv_p'] / 1000:g} кВт ток {i_inv:.0f} А → "
              f"{i_inv ** 2 * c['ri']:.0f} Вт. Диаметр жилы: "
            + " · ".join(f"{float(s[k]):g} мм² = ⌀{s2d(s[k]):.1f} мм" for k in WIRE_S_KEYS
                         if not (c["builtin"] and k == "bw_s")))           # у гибрида кабеля контроллер→АКБ нет
        # график по часам
        xs = [t for t, _ in res[(m, "clear")]["curve"]]
        series = []
        for w, name in WEATHER:
            col = SERIES_COL[w] or self._p()["accent"]
            series.append((name, col, [v for _, v in res[(m, w)]["curve"]]))
        nz = [t for t, v in res[(m, "clear")]["curve"] if v > 0]
        x0, x1 = (math.floor(min(nz)) - 1, math.ceil(max(nz)) + 1) if nz else (4, 22)
        self.ch_hour.title = MONTHS[m]
        self.ch_hour.set_data(series, xs=xs, xmin=max(0, x0), xmax=min(24, x1))
        # по месяцам
        ms = []
        for w, name in WEATHER:
            col = SERIES_COL[w] or self._p()["accent"]
            ms.append((name, col, [res[(mm, w)]["wh"][8] / 1000 for mm in range(12)]))
        self.ch_month.set_data(ms, labels=MONTHS_S, ydec=2)
        self._show_balance()
        self._show_home()
        self._show_grid()
        # потери
        t = self.tb_loss
        t.setRowCount(0)
        pot = dw[0]

        def add(name, wh, pct, color=None, bold=False):
            r = t.rowCount()
            t.insertRow(r)
            t.setItem(r, 0, _item(name, color=color, bold=bold))
            t.setItem(r, 1, _item(_fmt(wh), True, color, bold))
            t.setItem(r, 2, _item(pct, True, color, bold))

        add(f"Солнце на панели ({_fmt(res[(m, wsel)]['poa_wh'] / 1000, 2)} кВт·ч/м²) × {pk / 1000:.2f} кВт", pot, "100 %", bold=True)
        for name, a, b in LOSS_ROWS:
            if c["builtin"] and a == 7:
                continue                          # у гибрида нет провода MPPT → АКБ
            if c["builtin"] and a == 6:
                name = "Упор в предел мощности PV инвертора"
            loss = dw[a] - dw[b]
            pct = loss / pot * 100 if pot > 0 else 0
            if abs(loss) < 0.5:
                loss, pct = 0.0, 0.0
            col = _ERR if pct >= 5 else _WARN if pct >= 2 else _OK if pct < -0.05 else None
            sign = "+" if pct < -0.05 else "−" if pct > 0.05 else ""
            add(("  + " if sign == "+" else "  − ") + name, -loss + 0.0, f"{sign}{abs(pct):.1f} %", col)
        out = dw[8]
        add("= На шину АКБ / дом" if c["builtin"] else "= В АКБ (на клеммах)", out, f"{out / pot * 100:.1f} %" if pot else "—", _OK, True)
        add("  Запасено в АКБ", out * c["eta_bat"], f"{out * c['eta_bat'] / pot * 100:.1f} %" if pot else "—")
        add("  На 230 В, если тратить сразу", out * c["inv_eta"], f"{out * c['inv_eta'] / pot * 100:.1f} %" if pot else "—")
        idle = c["inv_idle"] * c["inv_hours"]
        add(f"  Холостой ход инвертора ({c['inv_idle']:.0f} Вт × {c['inv_hours']:.0f} ч)", -idle, "")
        add("  Баланс: на 230 В минус холостой ход", out * c["inv_eta"] - idle, "", bold=True)
        # проверки
        while self.chk_box.count():
            it = self.chk_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        icon = {"ok": ("✓", _OK), "warn": ("⚠", _WARN), "err": ("✗", _ERR), "info": ("ℹ", self._p()["accent"])}
        cnt = {k: sum(1 for l, _ in R["checks"] if l == k) for k in ("ok", "warn", "err")}
        self.chk_summary.setText(f"<span style='color:{_OK}'>✓ {cnt['ok']}</span>&nbsp;&nbsp;"
                                 f"<span style='color:{_WARN}'>⚠ {cnt['warn']}</span>&nbsp;&nbsp;"
                                 f"<span style='color:{_ERR}'>✗ {cnt['err']}</span>")
        self.chk_summary.setToolTip("\n".join(f"{icon[l][0]} {t}" for l, t in R["checks"]) + "\n\nПодробно — на странице «Прогноз»")
        for lvl, text in R["checks"]:
            ic, col = icon[lvl]
            l = QLabel(f"<span style='color:{col};font-weight:600'>{ic}</span>&nbsp;&nbsp;{text}")
            l.setTextFormat(Qt.RichText)
            l.setWordWrap(True)
            l.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.chk_box.addWidget(l)
        self._update_point()

    @staticmethod
    def _month_ranges(ms):
        """[0,1,2,10,11] → «Ноя–Мар»; учитывает переход через год."""
        if not ms:
            return "—"
        if len(ms) == 12:
            return "весь год"
        st = set(ms)
        starts = [m for m in ms if (m - 1) % 12 not in st]
        parts = []
        for a in starts:
            b = a
            while (b + 1) % 12 in st:
                b = (b + 1) % 12
            parts.append(MONTHS_S[a] if a == b else f"{MONTHS_S[a]}–{MONTHS_S[b]}")
        return ", ".join(parts)

    def _show_home(self):
        R, s = self.R, self.s
        c, G, yg, bal = R["ctx"], R["grid"], R["ygrid"], R["bal"]
        m_sel, wsel = int(s["month"]), s["weather"]
        off = c["grid_mode"] == "off"
        tar = c["tariff"]
        mute = self._p()["muted"]
        cov = {w: (1 - yg[w]["grid_load"] / yg[w]["load"]) * 100 if yg[w]["load"] > 0 else 100 for w in W_KEYS}
        self.kpi["cov"][0].setText(f"{cov['avg']:.0f} %")
        self.kpi["cov"][1].setText(f"Покрытие за год · ⛅ средняя погода · ☁ {cov['over']:.0f}% · ☀ {cov['clear']:.0f}%")
        self.kpi["ygrid"][0].setText(f"{_fmt(yg['avg']['grid'])} кВт·ч")
        self.kpi["ygrid"][1].setText("Без света за год (не покрыто)" if off else "Из сети за год · средняя погода")
        save = (yg["avg"]["load"] - yg["avg"]["grid_load"]) * tar
        self.kpi["ycost"][0].setText("—" if off else f"{_fmt(yg['avg']['grid'] * tar)} грн")
        self.kpi["ycost"][1].setText(f"За сеть в год · экономия ≈ {_fmt(save)} грн при {tar:g} грн/кВт·ч")
        full = [m for m in range(12) if G[(m, "avg")]["grid_wh"] < 0.03 * G[(m, "avg")]["load"]]
        need_grid = [m for m in range(12) if m not in full]
        g = G[(m_sel, wsel)]
        cov_m = (1 - g["grid_load"] / g["load"]) * 100 if g["load"] > 0 else 100
        word = "без света" if off else "из сети"
        if not need_grid:
            head = f"<b style='color:{_OK}'>✓ Станция перекрывает дом в средний день круглый год.</b>"
        elif not full:
            head = f"<b style='color:{_ERR}'>✗ Ни в одном месяце средний день не обходится без сети.</b>"
        else:
            head = (f"<b style='color:{_OK}'>Без сети (средняя погода): {self._month_ranges(full)}</b> · "
                    f"<b style='color:{_ERR}'>{'Отключения' if off else 'Сеть нужна'}: {self._month_ranges(need_grid)}</b>")
        self.home_verdict.setText(
            f"<span style='font-size:12pt'>{head}</span><br>"
            f"За год станция закрывает <b>{cov['avg']:.0f}%</b> потребления дома "
            f"<span style='color:{mute}'>(пасмурный год {cov['over']:.0f}%, всегда ясно {cov['clear']:.0f}%)</span>. "
            f"{'Не покрыто' if off else 'Из сети'} ≈ <b>{_fmt(yg['avg']['grid'])} кВт·ч/год</b>"
            + ("" if off else f" ≈ <b>{_fmt(yg['avg']['grid'] * tar)} грн</b>") + ". "
            f"Летом лишнее ≈ <b>{_fmt(yg['avg']['wasted'])} кВт·ч</b> (АКБ полная — пропадает).<br>"
            f"<b>{MONTHS[m_sel]}, {WEATHER_ADJ[wsel]} день:</b> покрыто {cov_m:.0f}%, "
            f"{word} {_fmt(g['grid_wh'] / 1000, 1)} кВт·ч в сутки.")
        # график
        cols = {"need": self._p()["muted"], "cov": _OK, "grid": _ERR}
        self.ch_cover.title = dict(WEATHER)[wsel]
        self.ch_cover.set_data([
            ("Нужно дому", cols["need"], [G[(m, wsel)]["load"] / 1000 for m in range(12)]),
            ("Закрыто станцией", cols["cov"], [(G[(m, wsel)]["load"] - G[(m, wsel)]["grid_load"]) / 1000 for m in range(12)]),
            ("Без света" if off else "Из сети", cols["grid"], [G[(m, wsel)]["grid_load"] / 1000 for m in range(12)]),
        ], labels=MONTHS_S, ydec=2)
        # таблица
        t = self.tb_cover
        t.setRowCount(0)
        pk = c["pstc_tot"] / 1000
        for m in range(12):
            i = t.rowCount()
            t.insertRow(i)
            t.setItem(i, 0, _item(MONTHS[m], bold=(m == m_sel)))
            t.setItem(i, 1, _item(_fmt(G[(m, 'avg')]["load"] * DAYS[m] / 1000), True))
            for col, w in ((2, "avg"), (3, "over"), (4, "clear")):
                gg = G[(m, w)]
                pc = (1 - gg["grid_load"] / gg["load"]) * 100 if gg["load"] > 0 else 100
                t.setItem(i, col, _item(f"{pc:.0f} %", True, _OK if pc >= 97 else _WARN if pc >= 60 else _ERR))
            ga = G[(m, "avg")]
            t.setItem(i, 5, _item(_fmt(ga["grid_wh"] * DAYS[m] / 1000), True))
            t.setItem(i, 6, _item("—" if off else _fmt(ga["grid_wh"] * DAYS[m] / 1000 * tar), True))
            t.setItem(i, 7, _item(_fmt(ga["wasted"] * DAYS[m] / 1000), True))
            gen = bal[m]["gen"]["avg"]
            kw = pk * bal[m]["need"] / gen if gen > 0 else 0
            t.setItem(i, 8, _item(f"{kw:.1f} кВт" if gen > 0 else "—", True, _WARN if kw > pk * 1.01 else _OK))
        # советы
        adv = []
        dec = 11
        for mm in sorted({dec, m_sel}):
            gen = bal[mm]["gen"]["avg"]
            if gen > 0:
                kw = pk * bal[mm]["need"] / gen
                if kw > pk * 1.01:
                    n = math.ceil(kw * 1000 / c["pmax"])
                    adv.append(f"☀ Чтобы средний день в <b>{MONTHS_IN[mm]}</b> обходился без сети, нужно ≈<b>{kw:.1f} кВт</b> панелей "
                               f"(≈{n} шт по {c['pmax']:.0f} Вт; сейчас {pk:.2f} кВт). MPPT и провода — пересчитать.")
        night = max(sum(max(0.0, ldc - pv) * DT for _, pv, ldc, _, _ in G[(m, "avg")]["pts"])
                    for m in range(12) if bal[m]["bal"]["avg"] >= 0) if any(bal[m]["bal"]["avg"] >= 0 for m in range(12)) else 0
        if night > 0:
            unit = float(s["bat_unit_v"]) * float(s["bat_ah"]) * float(s["bat_dod"]) / 100
            if night > c["usable_wh"] * 1.02 and unit > 0:
                n = math.ceil(night / unit / c["nser"])
                what = f"{_packs(n)} по {c['nser']} шт" if c["nser"] > 1 else f"{n} шт"
                adv.append(f"🔋 Чтобы в солнечные месяцы пережить вечер и ночь без сети, полезная ёмкость нужна ≈<b>{night / 1000:.1f} кВт·ч</b> "
                           f"(у вас {c['usable_wh'] / 1000:.1f}) → ≈<b>{what}</b> выбранных АКБ"
                           + (" — больше 10, нужны АКБ покрупнее." if n > 10 else "."))
            else:
                adv.append(f"🔋 Ёмкости хватает на вечер и ночь в солнечные месяцы (нужно ≈{night / 1000:.1f} кВт·ч, есть {c['usable_wh'] / 1000:.1f}).")
        idle_y = c["inv_idle"] * c["inv_hours"] * 365 / 1000
        if c["inv_idle"] > 20:
            adv.append(f"🔌 Холостой ход инвертора съедает ≈<b>{idle_y:.0f} кВт·ч/год</b>. Инвертор с режимом экономии (10–15 Вт) "
                       f"сэкономит ≈{(c['inv_idle'] - 12) * c['inv_hours'] * 365 / 1000:.0f} кВт·ч/год.")
        if yg["avg"]["wasted"] > 100:
            adv.append(f"♨ Летом пропадает ≈<b>{_fmt(yg['avg']['wasted'])} кВт·ч</b> — переведите бойлер, стирку, кондиционер на день.")
        adv.append("📐 Зимой помогает больший угол наклона — проверьте на странице подбора угла.")
        self.home_advice.setText("<br>".join(adv))

    def _show_grid(self):
        R, s = self.R, self.s
        c, G = R["ctx"], R["grid"]
        m_sel, wsel = int(s["month"]), s["weather"]
        off = c["grid_mode"] == "off"
        r = G[(m_sel, wsel)]
        tg, tb = grid_times(r)
        mute = self._p()["muted"]
        back = c["back_soc"] * 100
        to_g, to_b = ("отключение", "свет снова от АКБ") if off else ("переход на сеть", "обратно на АКБ")
        wname = WEATHER_ADJ[wsel]
        lines = []
        if c["usable_wh"] <= 1:
            lines.append(f"<b style='color:{_ERR}'>АКБ нет</b> — ночью и в пасмурные часы дом {'без света' if off else 'на сети'}.")
        if r["grid_wh"] < 1:
            lines.append(f"<b style='color:{_OK}'>✓ {MONTHS[m_sel]}, {wname} день: сеть не нужна.</b> "
                         f"Заряд АКБ не опускается ниже {r['soc_min']:.0f}%.")
        else:
            if tg is not None and tb is not None:
                lines.append(f"<span style='font-size:12pt'><b>{MONTHS[m_sel]}, {wname} день:</b> АКБ садится в "
                             f"<b style='color:{_ERR}'>{fmt_t(tg)}</b> → {to_g}; {to_b} в "
                             f"<b style='color:{_OK}'>{fmt_t(tb)}</b></span>"
                             f"<span style='color:{mute}'> (когда солнце дозарядит АКБ до {back:.0f}%)</span>")
            elif tg is not None:
                lines.append(f"<b>{MONTHS[m_sel]}, {wname} день:</b> {to_g} в <b style='color:{_ERR}'>{fmt_t(tg)}</b>.")
            else:
                lines.append(f"<b>{MONTHS[m_sel]}, {wname} день:</b> дом весь день {'без света' if off else 'на сети'}, "
                             f"солнце только подзаряжает АКБ.")
            if r.get("cycle") == 2:
                lines.append(f"↻ Режим через день: за день АКБ не успевает зарядиться до {back:.0f}%, поэтому "
                             f"≈{r.get('full_grid_days', 0)} из 6 дней дом целиком {'без света' if off else 'на сети'}. "
                             f"Ниже «Вернуться на АКБ при заряде» — чаще от АКБ, но глубже разряд.")
            day_grid = r["grid_wh"] / 1000
            txt = f"{'Без света' if off else 'Из сети'} ≈ <b>{_fmt(day_grid, 1)} кВт·ч в сутки</b>"
            if not off:
                txt += f" ≈ <b>{_fmt(day_grid * DAYS[m_sel] * c['tariff'])} грн за {MONTHS[m_sel].lower()}</b>"
            lines.append(txt + f" · минимальный заряд {r['soc_min']:.0f}%.")
        if r["wasted"] > 50:
            lines.append(f"<span style='color:{mute}'>АКБ полная — пропадает ≈{_fmt(r['wasted'] / 1000, 1)} кВт·ч в сутки.</span>")
        self.grid_sum.setText("<br>".join(lines))
        pts = r["pts"]
        xs = [p[0] for p in pts]
        marks = [(t, ("→ " + ("откл." if off else "сеть")) if k == "grid" else "→ АКБ", _ERR if k == "grid" else _OK)
                 for t, k in r["events"]]
        acc = self._p()["accent"]
        self.ch_gpow.title = f"{MONTHS[m_sel]} · {dict(WEATHER)[wsel]}"
        self.ch_gpow.set_data([("Солнце", SERIES_COL["clear"], [p[1] for p in pts]),
                               ("Расход дома (с инвертором)", acc, [p[2] for p in pts]),
                               ("Без света" if off else "Из сети", _ERR, [p[3] for p in pts])],
                              xs=xs, xmin=0, xmax=24, markers=marks)
        base = (1 - c["usable_wh"] / max(1.0, c["bank_wh"])) * 100
        self.ch_gsoc.set_data([("Заряд АКБ", _OK, [p[4] for p in pts]),
                               (f"Возврат на АКБ {back:.0f}%", self._p()["muted"], [back] * len(pts)),
                               (f"Минимум {base:.0f}%", _ERR, [base] * len(pts))],
                              xs=xs, xmin=0, xmax=24, ydec=0, markers=marks)
        t = self.tb_grid
        t.setRowCount(0)
        for m in range(12):
            i = t.rowCount()
            t.insertRow(i)
            t.setItem(i, 0, _item(MONTHS[m], bold=(m == m_sel)))
            for k, w in enumerate(("avg", "over", "clear")):
                gg = G[(m, w)]
                a, b = grid_times(gg)
                cyc = "↻ " if gg.get("cycle") == 2 else ""
                if gg["grid_wh"] < 1:
                    t.setItem(i, 1 + k * 3, _item("не нужна", color=_OK))
                    t.setItem(i, 2 + k * 3, _item(""))
                    t.setItem(i, 3 + k * 3, _item("0", True, _OK))
                else:
                    t.setItem(i, 1 + k * 3, _item(cyc + (fmt_t(a) if a is not None else "весь день"), color=_ERR))
                    t.setItem(i, 2 + k * 3, _item(fmt_t(b) if b is not None else "—", color=_OK if b is not None else None))
                    t.setItem(i, 3 + k * 3, _item(_fmt(gg["grid_wh"] / 1000, 1), True))
        self._show_series()

    def _show_series(self):
        R, s = self.R, self.s
        c, res = R["ctx"], R["res"]
        m = int(s["month"])
        w = s["ser_weather"]
        n = max(1, int(s["ser_days"]))
        out = soc_series(c, [res[(m, w)]["curve"]] * n, load_day_wh(c, m), c["profile"], float(s["ser_soc0"]))
        xs, soc = [], []
        marks = [(24.0 * d, f"День {d + 1}", self._p()["muted"]) for d in range(1, n)]
        off = c["grid_mode"] == "off"
        for d, r in enumerate(out):
            for p in r["pts"]:
                xs.append(p[0] + 24 * d)
                soc.append(p[4])
            for tt, k in r["events"]:
                if k == "grid":
                    marks.append((tt + 24 * d, "откл." if off else "сеть", _ERR))
        self.ch_ser.title = f"{MONTHS[m]} · {dict(WEATHER)[w]} × {n}"
        self.ch_ser.set_data([("Заряд АКБ", _OK, soc)], xs=xs, xmin=0, xmax=24 * n, markers=marks)
        t = self.tb_ser
        t.setRowCount(0)
        for d, r in enumerate(out):
            a, b = grid_times(r)
            i = t.rowCount()
            t.insertRow(i)
            t.setItem(i, 0, _item(f"День {d + 1}"))
            t.setItem(i, 1, _item(_fmt(r["pv"] / 1000, 1), True))
            t.setItem(i, 2, _item(_fmt(r["load_dc"] / 1000, 1), True))
            t.setItem(i, 3, _item(_fmt(r["grid_wh"] / 1000, 1), True, _ERR if r["grid_wh"] > 1 else _OK))
            t.setItem(i, 4, _item(f"{r['soc_min']:.0f} %", True))
            t.setItem(i, 5, _item(fmt_t(a) if a is not None else ("весь день" if r["start_grid"] and r["grid_wh"] > 1 else "—"),
                                  color=_ERR if a is not None else None))
            t.setItem(i, 6, _item(fmt_t(b), color=_OK if b is not None else None))

    def _cell_info(self, c):
        """Ресурс и вес: у одной сборки — подробно, у разных — общий вес по тем, где он известен."""
        groups = c["groups"]
        if len(groups) == 1:
            inf = CELL_INFO.get(groups[0]["key"])
            if not inf:
                return ""
            cyc, kg, dims, ir = inf
            txt = f"<br>Ресурс ≈{cyc} циклов (паспорт, 25°C)"
            if kg:
                txt += f" · {kg:g} кг/шт → {kg * c['units']:.0f} кг · {dims} мм · R {ir} мОм"
            return txt
        kg = [CELL_INFO[gr["key"]][1] * gr["n"] * gr["nser"] for gr in groups
              if gr["key"] in CELL_INFO and CELL_INFO[gr["key"]][1]]
        return f"<br>Вес ячеек ≈{sum(kg):.0f} кг" + ("" if len(kg) == len(groups) else " (не у всех сборок известен)") if kg else ""

    def _show_balance(self):
        R, s = self.R, self.s
        bal, c = R["bal"], R["ctx"]
        t = self.tb_bal
        t.setRowCount(0)
        m_sel = int(s["month"])
        for m, r in enumerate(bal):
            i = t.rowCount()
            t.insertRow(i)
            t.setItem(i, 0, _item(MONTHS[m], bold=(m == m_sel)))
            t.setItem(i, 1, _item(_fmt(r["load"] / 1000, 2), True))
            t.setItem(i, 2, _item(_fmt(r["idle"] / 1000, 2), True))
            t.setItem(i, 3, _item(_fmt(r["need"] / 1000, 2), True, bold=True))
            t.setItem(i, 4, _item(_fmt(r["gen"]["avg"] / 1000, 2), True))
            for col, w in ((5, "avg"), (6, "over"), (7, "clear")):
                b = r["bal"][w] / 1000
                t.setItem(i, col, _item(("+" if b >= 0 else "−") + _fmt(abs(b), 2), True, _OK if b >= 0 else _ERR))
            mb = r["bal"]["avg"] * DAYS[m] / 1000
            t.setItem(i, 8, _item(("+" if mb >= 0 else "−") + _fmt(abs(mb), 0), True, _OK if mb >= 0 else _ERR))
        y_load = sum(r["load"] * DAYS[m] for m, r in enumerate(bal)) / 1000
        y_need = sum(r["need"] * DAYS[m] for m, r in enumerate(bal)) / 1000
        y_gen = R["year"]["avg"]
        y_def = sum(-min(0.0, r["bal"]["avg"]) * DAYS[m] for m, r in enumerate(bal)) / 1000
        y_sur = sum(max(0.0, r["bal"]["avg"]) * DAYS[m] for m, r in enumerate(bal)) / 1000
        lm = c["load_month"]
        mute = self._p()["muted"]
        self.bal_lab.setText(
            f"<span style='color:{mute}'>Дом:</span> <b>{_fmt(lm)} кВт·ч/мес</b> в среднем = <b>{_fmt(y_load)} кВт·ч/год</b> · "
            f"<span style='color:{mute}'>с инвертором и АКБ нужно</span> <b>{_fmt(y_need)}</b> · "
            f"<span style='color:{mute}'>станция даёт</span> <b>{_fmt(y_gen)}</b> кВт·ч/год<br>"
            f"<span style='color:{mute}'>Не хватает за год (средняя погода):</span> <b style='color:{_ERR}'>{_fmt(y_def)} кВт·ч</b> · "
            f"<span style='color:{mute}'>лишнее летом:</span> <b style='color:{_OK}'>{_fmt(y_sur)} кВт·ч</b> "
            f"<span style='color:{mute}'>(АКБ не переносит лето на зиму)</span>")

    def _update_point(self):
        if self.R is None:
            return
        c = self.R["ctx"]
        G, Ta = float(self.s["pt_g"]), float(self.s["pt_t"])
        r = sim_point(c, G, Ta)
        pot, soil, cell, mm, arr, pin, conv, out0, out, vin, I, vp, tc, R = r
        du = I * R
        dup = du / vp * 100 if vp > 0 else 0
        mute = self._p()["muted"]
        note = ""
        if out <= 0 and G > 0:
            note = f"<br><span style='color:{_WARN}'>⚠ MPPT не стартует: напряжения не хватает (нужно {c['vin_min']:.1f} В)</span>"
        elif mm > 0 and arr < mm * 0.98:
            note = f"<br><span style='color:{_WARN}'>⚠ Работа вне точки MPP: −{_fmt(mm - arr)} Вт (окно MPPT / лимит тока)</span>"
        if conv > out0 + 0.5:
            what = "предел мощности PV инвертора" if c["builtin"] else "ток заряда"
            note += f"<br><span style='color:{_WARN}'>⚠ Упор в {what}: −{_fmt(conv - out0)} Вт</span>"
        k = c["k"]
        per = f" × {k} вх." if k > 1 else ""
        bw_row = ("" if c["builtin"] else
                  f"<tr><td style='color:{mute}'>Провод MPPT→АКБ</td><td align=right><b>{_fmt(out0 - out)} Вт</b> · "
                  f"{out0 / c['vbat'] * c['rb']:.2f} В</td></tr>")
        dest = "На шину АКБ / дом" if c["builtin"] else "В АКБ"
        self.pt_lab.setText(
            f"<table cellspacing=3>"
            f"<tr><td style='color:{mute}'>Панели нагреты до</td><td align=right><b>{tc:.0f} °C</b></td></tr>"
            f"<tr><td style='color:{mute}'>Поле выдаёт</td><td align=right><b>{_fmt(arr)} Вт</b> ({vp:.1f} В × {I:.2f} А{per})</td></tr>"
            f"<tr><td style='color:{mute}'>Падение на проводе</td><td align=right><b>{du:.2f} В</b> ({dup:.2f} %) · {_fmt(arr - pin)} Вт</td></tr>"
            f"<tr><td style='color:{mute}'>На входе MPPT</td><td align=right><b>{_fmt(pin)} Вт</b> при {vin:.1f} В</td></tr>"
            f"{bw_row}"
            f"<tr><td style='color:{mute}'>{dest}</td><td align=right><b style='color:{_OK}'>{_fmt(out)} Вт</b> · {out0 / c['vbat']:.1f} А</td></tr>"
            f"<tr><td style='color:{mute}'>От паспорта поля</td><td align=right><b>{out / c['pstc_tot'] * 100:.1f} %</b></td></tr>"
            f"</table>{note}")

    def report_text(self):
        R, s = self.R, self.s
        c, res = R["ctx"], R["res"]
        m = int(s["month"])
        L = [f"{app_name()} v{app_version()} — отчёт",
             f"Поле 1: {c['main_npan']} шт = {(str(c['k']) + '×') if c['k'] > 1 else ''}{c['ns']}S{c['np']}P × {c['pmax']:.0f} Вт = {c['main_pstc'] / 1000:.2f} кВт; угол {s['tilt']}°, азимут {s['aspect']}°"
             + (f"; всего полей {len(c['fields'])}: {c['npan']} шт, {c['pstc_tot'] / 1000:.2f} кВт" if len(c["fields"]) > 1 else ""),
             f"Провод: {s['wire_len']} м, {s['wire_s']} мм² {'Al' if s['wire_mat'] == 'al' else 'Cu'}, R линии {wire_r(c, 20) * 1000:.0f} мОм",
             (f"MPPT встроен в инвертор ({INVERTER_PRESETS.get(s['inv_preset'], ('свой',))[0]}): {s['n_in']} вх. из {s['n_mppt_max']}, "
              f"окно {s['vmpp_min']}–{s['vmpp_max']} В, заряд до {s['iout_max']} А" if c["builtin"] else
              f"MPPT: {MPPT_PRESETS.get(s['m_preset'], ('свой',))[0]} × {s['n_mppt_max']}, заряд {s['bat_ch']} В, ток до {s['iout_max']} А")
             + f"; солнце: {self.sd.label(float(s['lat']), float(s['lon']))}", "",
             f"{'Месяц':<10}{'Ясно':>10}{'Средне':>10}{'Пасмурно':>10}  кВт·ч/сутки"]
        for mm in range(12):
            L.append(f"{MONTHS[mm]:<10}" + "".join(f"{res[(mm, w)]['wh'][8] / 1000:>10.2f}" for w in W_KEYS))
        bal = R["bal"]
        L += ["", f"АКБ: {bank_desc(c)} · {c['bank_v']:.1f} В {c['bank_ah']:.0f} А·ч = {c['bank_wh'] / 1000:.1f} кВт·ч (полезно {c['usable_wh'] / 1000:.1f})",
              f"Инвертор: {c['inv_p']:.0f} Вт, КПД {c['inv_eta'] * 100:.0f}%, холостой ход {c['inv_idle']:.0f} Вт × {c['inv_hours']:.0f} ч",
              f"Провода: MPPT→АКБ {s['bw_len']} м {s['bw_s']} мм², АКБ→инвертор {s['iw_len']} м {s['iw_s']} мм²", "",
              f"{'Месяц':<10}{'Нужно':>10}{'Средне':>10}{'Баланс':>10}  кВт·ч/сутки"]
        for mm in range(12):
            r = bal[mm]
            L.append(f"{MONTHS[mm]:<10}{r['need'] / 1000:>10.2f}{r['gen']['avg'] / 1000:>10.2f}{r['bal']['avg'] / 1000:>+10.2f}")
        yg = R["ygrid"]["avg"]
        L += ["", f"Покрытие дома за год (средняя погода): {(1 - yg['grid_load'] / max(yg['load'], 1e-9)) * 100:.0f}%, "
                  f"из сети {yg['grid']:.0f} кВт·ч ≈ {yg['grid'] * c['tariff']:.0f} грн"]
        L += [f"{'Месяц':<10}{'на сеть':>10}{'на АКБ':>10}{'кВт·ч/сут':>11}  (средняя погода)"]
        for mm in range(12):
            gg = R["grid"][(mm, "avg")]
            a, b = grid_times(gg)
            L.append(f"{MONTHS[mm]:<10}{fmt_t(a) if gg['grid_wh'] >= 1 else '—':>10}{fmt_t(b) if gg['grid_wh'] >= 1 else '—':>10}{gg['grid_wh'] / 1000:>11.1f}")
        L += ["", f"За год (средняя погода): {R['year']['avg']:.0f} кВт·ч", "",
              f"{MONTHS[m]}, пик в ясный день: {res[(m, 'clear')]['peak']:.0f} Вт", "", "Проверки:"]
        L += [f"  {({'ok': '✓', 'warn': '⚠', 'err': '✗', 'info': 'ℹ'})[l]} {t}" for l, t in R["checks"]]
        return "\n".join(L)

    def copy_report(self):
        if self.R is None:
            return
        QGuiApplication.clipboard().setText(self.report_text())
        log.info("✓ Отчёт скопирован в буфер")
        self._status("отчёт скопирован")

    def export_months(self):
        if self.R is None:
            return
        fn, _ = QFileDialog.getSaveFileName(self, "Экспорт CSV", str(Path(self._dir()) / "выработка_по_месяцам.csv"),
                                            "CSV (*.csv)", options=QFileDialog.DontUseNativeDialog)
        if not fn:
            return
        res = self.R["res"]
        try:
            with open(fn, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["Месяц", "Ясно, Вт·ч/сут", "Средне, Вт·ч/сут", "Пасмурно, Вт·ч/сут", "Средне за месяц, кВт·ч"])
                for m in range(12):
                    w.writerow([MONTHS[m]] + [f"{res[(m, k)]['wh'][8]:.0f}" for k in W_KEYS] +
                               [f"{res[(m, 'avg')]['wh'][8] * DAYS[m] / 1000:.1f}".replace(".", ",")])
        except OSError as e:
            _save_failed(self, fn, e)
            return
        log.info(f"✓ CSV сохранён: {fn}")
