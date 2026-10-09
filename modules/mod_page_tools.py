"""mod_page_tools.py  v1.9.7
страницы «Схемы S×P», «Угол», «Провод», «Данные PVGIS», «Цвета»

Журнал:
v1.9.7: «Провода» → MPPT → АКБ у гибрида с отдельным MPPT: сопротивление и ток отдельного контроллера (было 0).
v1.9.4: «Данные солнца» — погода региона за 5 лет (архив Open-Meteo): загрузить / забыть, сумма солнца по
        годам, колонки в таблице; загрузка сама при выборе погоды «📍 Регион 5 лет».
v1.3.0: вынесено из solar_calc.pyw v1.2.1; сравнение схем — с разбивкой по входам MPPT / контроллерам.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QAbstractItemView, QMessageBox

from .mod_base import MONTHS, DAYS, log
from .mod_sun import BUILTIN_SUN
from .mod_fields import s2d
from .mod_config import save_config
from .mod_model import layouts, wire_r, compute_days, year_kwh, ampacity, balance
from .mod_checks import make_checks
from .mod_pvgis import fetch_pvgis
from .mod_region import fetch_region, region_years
from .mod_theme import _OK, _ERR, _WARN, SERIES_COL
from .mod_widgets import (app_name, app_version, Toggle, Segmented, _lab, _card, _btn, _fmt, Chart,
                          make_table, _item)


class ToolPages:
    """Часть главного окна App (миксин)."""

    def _page_schemes(self):
        pg, v = self._page()
        top = QHBoxLayout()
        top.addWidget(_lab("Сравнение схем при том же числе панелей", "bigTitle"))
        top.addStretch(1)
        top.addWidget(_btn("🔄 Пересчитать", "primary", "Пересчитать таблицу", lambda: self._refresh_page("schemes", force=True)))
        v.addLayout(top)
        v.addWidget(_lab("Все варианты S×P (и по входам MPPT / контроллерам) для вашего числа панелей: ясный / средний / пасмурный день выбранного месяца и год. "
                         "Лучший вариант в каждом столбце — зелёный. Частичную тень модель не учитывает: при тени "
                         "длинные цепочки теряют больше.", "hint", True))
        fr, cv = _card("Варианты")
        self.tb_sch = make_table(["Схема", "Vmp, В", "Ток на вход, А", "Voc мороз, В", "Провод, %", "Ясно, Вт·ч",
                                  "Средне, Вт·ч", "Пасмурно, Вт·ч", "Год, кВт·ч", "Проверки"],
                                 [("✔ Применить эту схему", self._apply_scheme)])
        cv.addWidget(self.tb_sch)
        v.addWidget(fr, 1)
        return pg

    def _apply_scheme(self, row):
        it = self.tb_sch.item(row, 0)
        if not it:
            return
        k, ns, np_ = it.data(Qt.UserRole)
        self.s["n_in"], self.s["ns"], self.s["np"] = k, ns, np_
        self.s["n_pan"] = k * ns * np_
        self._refresh_station()
        log.info(f"✓ Схема {ns}S{np_}P" + (f" на каждый из {k} входов" if k > 1 else "") + " применена")
        self.recalc()

    def _job_schemes(self, s, sd):
        m = int(s["month"])
        rows = []
        for k, ns, np_ in layouts(int(s["n_pan"]), int(s["n_mppt_max"])):
            s2 = dict(s, n_in=k, ns=ns, np=np_)
            c, res = compute_days(s2, sd)
            checks = make_checks(s2, c, res)
            worst = "ok"
            for lvl, _ in checks:
                if lvl == "err":
                    worst = "err"
                elif lvl == "warn" and worst == "ok":
                    worst = "warn"
            R20 = wire_r(c, 20)
            istc = np_ * c["imp"]
            rows.append(dict(k=k, ns=ns, np=np_, vmp=ns * c["vmp"], i=istc,
                             voc=ns * c["voc"] * (1 + c["bvoc"] * (float(s["t_min"]) - 25)),
                             du=istc * R20 / (ns * c["vmp"]) * 100,
                             clear=res[(m, "clear")]["wh"][8], avg=res[(m, "avg")]["wh"][8],
                             over=res[(m, "over")]["wh"][8], year=year_kwh(res, "avg"), worst=worst,
                             msg="; ".join(t for l, t in checks if l in ("err", "warn"))))
        return rows

    def _fill_schemes(self, rows):
        t = self.tb_sch
        t.setRowCount(0)
        best = {k: max((r[k] for r in rows if r["worst"] != "err"), default=None) for k in ("clear", "avg", "over", "year")}
        for r in rows:
            i = t.rowCount()
            t.insertRow(i)
            cur = (r["k"], r["ns"], r["np"]) == (int(self.s["n_in"]), int(self.s["ns"]), int(self.s["np"]))
            name = (f"{r['k']} × " if r["k"] > 1 else "") + f"{r['ns']}S{r['np']}P"
            it = _item(name + ("  ← сейчас" if cur else ""), bold=cur)
            it.setData(Qt.UserRole, (r["k"], r["ns"], r["np"]))
            t.setItem(i, 0, it)
            t.setItem(i, 1, _item(f"{r['vmp']:.1f}", True))
            t.setItem(i, 2, _item(f"{r['i']:.1f}", True))
            t.setItem(i, 3, _item(f"{r['voc']:.0f}", True, _ERR if r["voc"] > float(self.s["v_max"]) else None))
            t.setItem(i, 4, _item(f"{r['du']:.2f}", True, _ERR if r["du"] > 3 else _WARN if r["du"] > 2 else None))
            for col, k in ((5, "clear"), (6, "avg"), (7, "over")):
                good = best[k] is not None and abs(r[k] - best[k]) < 0.5 and r["worst"] != "err"
                t.setItem(i, col, _item(_fmt(r[k]), True, _OK if good else None, good))
            good = best["year"] is not None and abs(r["year"] - best["year"]) < 0.05 and r["worst"] != "err"
            t.setItem(i, 8, _item(_fmt(r["year"]), True, _OK if good else None, good))
            ic = {"ok": ("✓ норма", _OK), "warn": ("⚠ есть замечания", _WARN), "err": ("✗ нельзя", _ERR)}[r["worst"]]
            it = _item(ic[0], color=ic[1])
            it.setToolTip(r["msg"] or "Замечаний нет")
            t.setItem(i, 9, it)

    def _page_tilt(self):
        pg, v = self._page()
        top = QHBoxLayout()
        top.addWidget(_lab("Подбор угла наклона и азимута", "bigTitle"))
        top.addStretch(1)
        top.addWidget(_btn("🔄 Пересчитать", "primary", "Пересчитать", lambda: self._refresh_page("tilt", force=True)))
        v.addLayout(top)
        v.addWidget(_lab("Средняя погода. Зимой выгоднее круче, летом — положе; оптимум зависит от доли пасмурных дней (рассеянный свет "
                         "любит пологий угол). Крутой угол ещё и сбрасывает снег. Правый клик по строке — применить.", "hint", True))
        self.ch_tilt = Chart("line", "%")
        self.ch_tilt.xfmt = "deg"
        self.ch_tilt.setMinimumHeight(230)
        self.charts.append(self.ch_tilt)
        fr, cv = _card("% от лучшего угла")
        cv.addWidget(self.ch_tilt)
        v.addWidget(fr)
        row = QHBoxLayout()
        row.setSpacing(12)
        fr, cv = _card("Угол наклона (азимут как сейчас)")
        self.tb_tilt = make_table(["Угол", "Декабрь, Вт·ч", "Выбр. месяц, Вт·ч", "Июнь, Вт·ч", "Год, кВт·ч"],
                                  [("✔ Применить этот угол", self._apply_tilt)])
        cv.addWidget(self.tb_tilt)
        row.addWidget(fr, 3)
        fr, cv = _card("Азимут (угол как сейчас)")
        self.tb_az = make_table(["Азимут", "Декабрь, Вт·ч", "Год, кВт·ч", "% от юга"],
                                [("✔ Применить этот азимут", self._apply_az)])
        cv.addWidget(self.tb_az)
        row.addWidget(fr, 2)
        v.addLayout(row, 1)
        return pg

    def _apply_tilt(self, row):
        it = self.tb_tilt.item(row, 0)
        if it:
            self.s["tilt"] = it.data(Qt.UserRole)
            self._set_widget("tilt", self.s["tilt"])
            log.info(f"✓ Угол {self.s['tilt']}° применён")
            self.recalc()

    def _apply_az(self, row):
        it = self.tb_az.item(row, 0)
        if it:
            self.s["aspect"] = it.data(Qt.UserRole)
            self._set_widget("aspect", self.s["aspect"])
            log.info(f"✓ Азимут {self.s['aspect']}° применён")
            self.recalc()

    def _job_tilt(self, s, sd):
        m = int(s["month"])
        tilts = []
        for tl in range(0, 91, 5):
            s2 = dict(s, tilt=tl)
            _, res = compute_days(s2, sd, weathers=("avg",))
            tilts.append((tl, res[(11, "avg")]["wh"][8], res[(m, "avg")]["wh"][8], res[(5, "avg")]["wh"][8], year_kwh(res)))
        azs = []
        for az in range(-90, 91, 15):
            s2 = dict(s, aspect=az)
            _, res = compute_days(s2, sd, weathers=("avg",))
            azs.append((az, res[(11, "avg")]["wh"][8], year_kwh(res)))
        return tilts, azs

    def _fill_tilt(self, data):
        tilts, azs = data
        t = self.tb_tilt
        t.setRowCount(0)
        bests = [max(r[k] for r in tilts) for k in range(1, 5)]
        for r in tilts:
            i = t.rowCount()
            t.insertRow(i)
            cur = abs(r[0] - float(self.s["tilt"])) < 0.5
            it = _item(f"{r[0]}°" + ("  ← сейчас" if cur else ""), bold=cur)
            it.setData(Qt.UserRole, r[0])
            t.setItem(i, 0, it)
            for k in range(1, 5):
                good = abs(r[k] - bests[k - 1]) < 1e-6
                t.setItem(i, k, _item(_fmt(r[k], 1 if k == 4 else 0), True, _OK if good else None, good))
        a = self.tb_az
        a.setRowCount(0)
        south = next((r for r in azs if r[0] == 0), azs[len(azs) // 2])
        for r in azs:
            i = a.rowCount()
            a.insertRow(i)
            name = "юг" if r[0] == 0 else (f"{-r[0]}° к востоку" if r[0] < 0 else f"{r[0]}° к западу")
            cur = abs(r[0] - float(self.s["aspect"])) < 0.5
            it = _item(name + ("  ← сейчас" if cur else ""), bold=cur)
            it.setData(Qt.UserRole, r[0])
            a.setItem(i, 0, it)
            a.setItem(i, 1, _item(_fmt(r[1]), True))
            a.setItem(i, 2, _item(_fmt(r[2], 1), True))
            a.setItem(i, 3, _item(f"{r[2] / south[2] * 100:.1f} %" if south[2] else "—", True))
        xs = [r[0] for r in tilts]
        ser = []
        for k, name, col in ((4, "Год", self._p()["accent"]), (1, "Декабрь", SERIES_COL["over"]),
                             (3, "Июнь", SERIES_COL["clear"])):
            b = max(r[k] for r in tilts) or 1
            ser.append((name, col, [r[k] / b * 100 for r in tilts]))
        self.ch_tilt.title = ""
        self.ch_tilt.set_data(ser, xs=xs, xmin=0, xmax=90, ydec=1)

    WIRE_SEGS = {"pv": ("Панели → MPPT", "wire_len", "wire_s", "wire_mat", (4, 6, 10, 16, 25, 35, 50), 2.0, 3.0),
                 "bw": ("MPPT → АКБ", "bw_len", "bw_s", "bw_mat", (6, 10, 16, 25, 35, 50, 70), 1.0, 2.0),
                 "iw": ("АКБ → инвертор", "iw_len", "iw_s", "iw_mat", (10, 16, 25, 35, 50, 70, 95), 1.0, 2.0)}

    def _page_wire(self):
        pg, v = self._page()
        top = QHBoxLayout()
        top.addWidget(_lab("Подбор сечения провода", "bigTitle"))
        top.addSpacing(12)
        self.seg_wire = Segmented([(k, t[0]) for k, t in self.WIRE_SEGS.items()])
        self.seg_wire.setValue("pv")
        self.seg_wire.setToolTip("Какой участок подбирать")
        self.seg_wire.changed.connect(lambda k: self._refresh_page("wire", force=True))
        top.addWidget(self.seg_wire)
        top.addStretch(1)
        top.addWidget(_btn("🔄 Пересчитать", "primary", "Пересчитать", lambda: self._refresh_page("wire", force=True)))
        v.addLayout(top)
        self.wire_hint = _lab("", "hint", True)
        v.addWidget(self.wire_hint)
        fr, cv = _card("Варианты сечения (длина и контакты — как сейчас; правый клик — применить)")
        self.tb_wire = make_table(["Провод", "⌀ жилы, мм", "R линии, мОм", "Падение при макс. токе", "Потери, Вт",
                                   "Потери за год, кВт·ч", "Допустимый ток", "Итог"],
                                  [("✔ Применить это сечение", self._apply_wire)])
        cv.addWidget(self.tb_wire)
        v.addWidget(fr, 1)
        return pg

    def _apply_wire(self, row):
        it = self.tb_wire.item(row, 0)
        if it:
            seg, sec, mat = it.data(Qt.UserRole)
            _, _, ks, km, _, _, _ = self.WIRE_SEGS[seg]
            self.s[ks], self.s[km] = sec, mat
            self._set_widget(ks, sec)
            self._set_widget(km, mat)
            log.info(f"✓ {self.WIRE_SEGS[seg][0]}: {sec:g} мм² {'Al' if mat == 'al' else 'Cu'} применён")
            self.recalc()

    def _job_wire(self, s, sd, seg="pv"):
        kl, ks, km, secs = self.WIRE_SEGS[seg][1:5]
        tiny = dict(s, **{kl: 0.0001})
        if seg == "pv":
            tiny.update(contact="good", n_main=0)
        c0, base = compute_days(tiny, sd, weathers=("avg",))
        if seg == "iw":
            y0 = sum(r["cable"] * DAYS[m] for m, r in enumerate(balance(c0, base))) / 1000
        else:
            y0 = year_kwh(base)
        variants = [(sec, mat) for mat in ("cu", "al") for sec in secs]
        cur = (float(s[ks]), s[km])
        if cur not in variants:
            variants.append(cur)
        rows = []
        for sec, mat in variants:
            s2 = dict(s, **{ks: sec, km: mat})
            c, res = compute_days(s2, sd, weathers=("avg",))
            if seg == "pv":
                R = wire_r(c, 20)
                I = c["np"] * c["imp"]
                V = c["ns"] * c["vmp"]
                need = c["np"] * c["isc"] * 1.25
                yl = y0 - year_kwh(res)
            elif seg == "bw":
                if c["builtin"]:                            # гибрид: этот кабель — у отдельных MPPT (у каждого свой)
                    R = c["rb_ctl"]
                    I = max([fc["iout"] for fc in c["fields"] if fc["ctl"]] or [0.0])
                else:
                    R, I = c["rb"], c["ilim"]
                V = c["vbat"]
                need = I * 1.25
                yl = y0 - year_kwh(res)
            else:
                R = c["ri"]
                I = c["inv_p"] / max(0.5, c["inv_eta"]) / (c["sys_nom"] * 0.95)
                V = c["sys_nom"]
                need = I * 1.25
                yl = sum(r["cable"] * DAYS[m] for m, r in enumerate(balance(c, res))) / 1000 - y0
            rows.append(dict(sec=sec, mat=mat, R=R, du=I * R / V * 100, dv=I * R, pl=I * I * R, yl=yl,
                             amp=ampacity(sec, mat), need=need, I=I))
        return seg, rows

    def _fill_wire(self, data):
        seg, rows = data
        if seg != self.seg_wire.value():
            QTimer.singleShot(0, lambda: self._refresh_page("wire", force=True))
            return
        name, kl, ks, km, secs, ok_lim, warn_lim = self.WIRE_SEGS[seg]
        t = self.tb_wire
        t.setRowCount(0)
        cur = (float(self.s[ks]), self.s[km])
        for r in rows:
            i = t.rowCount()
            t.insertRow(i)
            is_cur = (float(r["sec"]), r["mat"]) == cur
            it = _item(f"{r['sec']:g} мм² {'алюминий' if r['mat'] == 'al' else 'медь'}" + ("  ← сейчас" if is_cur else ""), bold=is_cur)
            it.setData(Qt.UserRole, (seg, r["sec"], r["mat"]))
            t.setItem(i, 0, it)
            t.setItem(i, 1, _item(f"{s2d(r['sec']):.1f}", True))
            t.setItem(i, 2, _item(f"{r['R'] * 1000:.1f}", True))
            col = _OK if r["du"] <= ok_lim else _WARN if r["du"] <= warn_lim else _ERR
            t.setItem(i, 3, _item(f"{r['du']:.2f} % ({r['dv']:.2f} В)", True, col))
            t.setItem(i, 4, _item(_fmt(r["pl"]), True))
            t.setItem(i, 5, _item(_fmt(r["yl"], 1), True))
            okamp = r["amp"] >= r["need"]
            t.setItem(i, 6, _item(f"{r['amp']:.0f} А (нужно {r['need']:.0f})", True, None if okamp else _ERR))
            verdict = (("✗ мало по току", _ERR) if not okamp else ("✓ хорошо", _OK) if r["du"] <= ok_lim
                       else ("⚠ терпимо", _WARN) if r["du"] <= warn_lim else ("✗ большие потери", _ERR))
            t.setItem(i, 7, _item(verdict[0], color=verdict[1]))
        I = rows[0]["I"] if rows else 0
        what = {"pv": "ток поля при полном солнце", "bw": "макс. ток заряда", "iw": "ток инвертора на полной мощности"}[seg]
        self.wire_hint.setText(
            f"{name}: {float(self.s[kl]):g} м в одну сторону (считается туда и обратно) + контакты. "
            f"Расчётный ток — {what}: {I:.0f} А. Норма падения ≤ {ok_lim:g}%. "
            "Ток в квадрате → потери: на низком напряжении (12/24 В) провода к АКБ и инвертору нужны толстые.")

    def _page_data(self):
        pg, v = self._page()
        v.addWidget(_lab("Данные солнца", "bigTitle"))
        fr, cv = _card("PVGIS — база Еврокомиссии (спутниковые данные за много лет)")
        cv.addWidget(_lab("Загрузит средний суточный профиль солнца и температуры по месяцам для широты/долготы из параметров. "
                          "Нужен интернет. Сохраняется в config.json, дальше работает без сети.", "hint", True))
        row = QHBoxLayout()
        self.btn_pv = _btn("🌐 Загрузить из PVGIS", "primary", "Скачать данные для текущей точки", self.load_pvgis)
        row.addWidget(self.btn_pv)
        row.addSpacing(12)
        row.addWidget(_lab("Использовать PVGIS", "fieldLab"))
        self.tg_pv = Toggle()
        self.tg_pv.setToolTip("Выкл — встроенные данные (≈Киев)")
        self.toggles.append(self.tg_pv)
        self.tg_pv.setChecked(bool(self.cfg.get("use_pvgis", True)))
        self.tg_pv.toggled.connect(self._toggle_pv)
        row.addWidget(self.tg_pv)
        row.addStretch(1)
        row.addWidget(_btn("🗑 Забыть PVGIS", "danger", "Удалить загруженные данные PVGIS", self.forget_pvgis))
        cv.addLayout(row)
        self.pv_info = _lab("", "hint", True)
        cv.addWidget(self.pv_info)
        v.addWidget(fr)
        y0, y1 = region_years()
        fr, cv = _card(f"📍 Погода региона — реальная, за {y0}–{y1} (архив Open-Meteo)")
        cv.addWidget(_lab("Скачает погоду по часам за последние 5 полных лет для широты/долготы станции и посчитает средний "
                          "день каждого месяца — солнце, облака, температура как было на самом деле. Это погода «📍 Регион 5 лет» "
                          "в Прогнозе и на других страницах. Нужен интернет один раз, дальше — из config.json.", "hint", True))
        row = QHBoxLayout()
        self.btn_reg = _btn("📍 Загрузить погоду региона", "primary", "Скачать погоду за 5 лет для текущей точки",
                            lambda: self.load_region())
        row.addWidget(self.btn_reg)
        row.addStretch(1)
        row.addWidget(_btn("🗑 Забыть", "danger", "Удалить погоду региона", self.forget_region))
        cv.addLayout(row)
        self.reg_info = _lab("", "hint", True)
        self.reg_info.setTextFormat(Qt.RichText)
        cv.addWidget(self.reg_info)
        v.addWidget(fr)
        fr, cv = _card("Помесячно: горизонтальная облучённость и температура")
        top = QHBoxLayout()
        top.addWidget(_lab("Встроенные значения можно править двойным щелчком.", "hint"))
        top.addStretch(1)
        top.addWidget(_btn("♻ Встроенные по умолчанию", "chip", "Вернуть значения ≈Киев", self.reset_builtin))
        cv.addLayout(top)
        self.tb_data = make_table(["Месяц", "Встроенные, кВт·ч/м²·день", "Встроенные, °C", "PVGIS, кВт·ч/м²·день",
                                   "PVGIS, °C", "Сдвиг времени PVGIS, ч", "Регион 5 лет, кВт·ч/м²·день", "Регион 5 лет, °C"])
        self.tb_data.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tb_data.itemChanged.connect(self._data_edited)
        cv.addWidget(self.tb_data)
        v.addWidget(fr, 1)
        return pg

    def _fill_data_table(self):
        t = self.tb_data
        t.blockSignals(True)
        t.setRowCount(0)
        pv = self.cfg.get("pvgis")
        rg = self.cfg.get("region")
        for m in range(12):
            t.insertRow(m)
            it = _item(MONTHS[m])
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            t.setItem(m, 0, it)
            b = self.cfg["builtin"][m]
            t.setItem(m, 1, _item(f"{b[0]:.2f}", True))
            t.setItem(m, 2, _item(f"{b[1]:.1f}", True))
            for col, val in ((3, f"{pv['months'][m]['H']:.2f}" if pv else "—"),
                             (4, f"{pv['months'][m]['T']:.1f}" if pv else "—"),
                             (5, f"{pv['months'][m].get('shift', 0):+.2f}" if pv else "—"),
                             (6, f"{rg['months'][m]['H']:.2f}" if rg else "—"),
                             (7, f"{rg['months'][m]['T']:.1f}" if rg else "—")):
                it = _item(val, True)
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                t.setItem(m, col, it)
        t.blockSignals(False)
        s = self.s
        if pv:
            near = self.sd.use_pv(float(s["lat"]), float(s["lon"]))
            yh = sum(pv["months"][m]["H"] * DAYS[m] for m in range(12))
            self.pv_info.setText(f"Загружено {pv.get('stamp', '')} для ({pv['lat']}, {pv['lon']}) · за год {yh:.0f} кВт·ч/м² · "
                                 + ("используется ✓" if near else "⚠ не используется: точка в параметрах другая или выключено"))
        else:
            self.pv_info.setText("PVGIS не загружен — считаются встроенные данные (≈Киев).")
        if rg:
            near = self.sd.use_reg(float(s["lat"]), float(s["lon"]))
            yh = sum(rg["months"][m]["H"] * DAYS[m] for m in range(12))
            by = " · ".join(f"{y}: {v:.0f}" for y, v in (rg.get("year_h") or {}).items())
            self.reg_info.setText(f"Загружено {rg.get('stamp', '')} для ({rg['lat']}, {rg['lon']}) за {rg.get('years', '')} "
                                  f"({rg.get('days', 0)} дней) · в среднем {yh:.0f} кВт·ч/м² в год"
                                  + (f"<br>По годам, кВт·ч/м²: {by}" if by else "") + "<br>"
                                  + ("используется для «📍 Регион 5 лет» ✓" if near else
                                     "<span style='color:#f5b545'>⚠ точка в параметрах другая — загрузите заново</span>"))
        else:
            self.reg_info.setText("Не загружено — «📍 Регион 5 лет» пока считается как «⛅ Средний».")

    def _data_edited(self, it):
        r, c = it.row(), it.column()
        if c not in (1, 2):
            return
        try:
            val = float(it.text().replace(",", ".").strip())
        except ValueError:
            log.warning(f"⚠ Не число: «{it.text()}»")
            QTimer.singleShot(0, self._fill_data_table)
            return
        self.cfg["builtin"][r][c - 1] = val
        save_config(self.cfg)
        log.info(f"✓ {MONTHS[r]}: встроенное значение изменено на {val}")
        QTimer.singleShot(0, self.recalc)   # recalc перестраивает таблицу — не внутри itemChanged

    def reset_builtin(self):
        if QMessageBox.question(self, app_name(), "Вернуть встроенные значения (≈Киев)?") != QMessageBox.Yes:
            return
        self.cfg["builtin"] = [list(x) for x in BUILTIN_SUN]
        save_config(self.cfg)
        self._fill_data_table()
        self.recalc()

    def _toggle_pv(self, on):
        self.cfg["use_pvgis"] = bool(on)
        save_config(self.cfg)
        self.recalc()
        self._fill_data_table()

    def forget_pvgis(self):
        if not self.cfg.get("pvgis"):
            return
        if QMessageBox.question(self, app_name(), "Удалить загруженные данные PVGIS?") != QMessageBox.Yes:
            return
        self.cfg["pvgis"] = None
        save_config(self.cfg)
        log.info("🗑 Данные PVGIS удалены")
        self.recalc()
        self._fill_data_table()

    def load_region(self, auto=False):
        """Погода региона за 5 лет для точки станции — в фоне; auto — сама при выборе «📍 Регион 5 лет»
        (для одной точки — один раз за запуск, чтобы без сети не повторять)."""
        lat, lon = float(self.s["lat"]), float(self.s["lon"])
        if auto:
            if self.sd.use_reg(lat, lon) or (round(lat, 2), round(lon, 2)) in self._reg_tried:
                return
            self._reg_tried.add((round(lat, 2), round(lon, 2)))
        self.btn_reg.setEnabled(False)

        def done(rg):
            self.cfg["region"] = rg
            save_config(self.cfg)
            yh = sum(rg["months"][m]["H"] * DAYS[m] for m in range(12))
            by = ", ".join(f"{y} — {v:.0f}" for y, v in (rg.get("year_h") or {}).items())
            log.info(f"✓ Погода региона за {rg['years']} загружена ({rg['lat']}, {rg['lon']}): в среднем {yh:.0f} кВт·ч/м² "
                     f"в год" + (f" (по годам: {by})" if by else ""))
            self.recalc()
            self._fill_data_table()

        if not self.worker.submit("погода региона за 5 лет", lambda: fetch_region(lat, lon), done):
            self.btn_reg.setEnabled(True)

    def forget_region(self):
        if not self.cfg.get("region"):
            return
        if QMessageBox.question(self, app_name(), "Удалить погоду региона за 5 лет?") != QMessageBox.Yes:
            return
        self.cfg["region"] = None
        save_config(self.cfg)
        log.info("🗑 Погода региона удалена")
        self.recalc()
        self._fill_data_table()

    def load_pvgis(self):
        lat, lon = float(self.s["lat"]), float(self.s["lon"])
        builtin = [list(x) for x in self.cfg["builtin"]]
        self.btn_pv.setEnabled(False)

        def done(pv):
            self.cfg["pvgis"] = pv
            self.cfg["use_pvgis"] = True
            self.tg_pv.blockSignals(True)
            self.tg_pv.setChecked(True)
            self.tg_pv.blockSignals(False)
            save_config(self.cfg)
            yh = sum(pv["months"][m]["H"] * DAYS[m] for m in range(12))
            log.info(f"✓ PVGIS загружен: ({pv['lat']}, {pv['lon']}), {yh:.0f} кВт·ч/м² в год")
            self.recalc()
            self._fill_data_table()

        if not self.worker.submit("загрузка PVGIS", lambda: fetch_pvgis(lat, lon, builtin), done):
            self.btn_pv.setEnabled(True)

    def _page_colors(self):
        pg, v = self._page()
        v.addWidget(_lab("Цвета", "bigTitle"))
        fr, cv = _card("Тема")
        self.seg_theme = Segmented((("dark", "🌙 Тёмная"), ("light", "☀ Светлая")))
        self.seg_theme.setValue(self.cfg.get("theme", "dark"))
        self.seg_theme.changed.connect(self._set_theme)
        self.seg_theme.setMaximumWidth(320)
        cv.addWidget(self.seg_theme)
        cv.addWidget(_btn("💾 Сохранить настройки", "primary", "Сохранить config.json", self._save_all), 0, Qt.AlignLeft)
        v.addWidget(fr)
        fr, cv = _card("О программе")
        cv.addWidget(_lab(
            f"{app_name()} v{app_version()}\n\nМодель: положение солнца → ясное небо (Haurwitz) / средний день (встроенные или PVGIS) → "
            "разделение на прямую и рассеянную (Erbs) → плоскость панелей (изотропная модель, отражение земли, потери на угле падения) → "
            "нагрев панелей (NOCT) → температурный коэффициент и КПД на слабом свету → схема S×P и рассогласование → "
            "провод (ρ с учётом температуры) и контакты (MC4 в цепочках + клеммы общей линии) → окно MPPT и лимит входного тока → "
            "КПД MPPT (зависит от Vвх/Vакб) и собственное потребление → лимит тока заряда → АКБ → инвертор.\n\n"
            "Не учитывается: частичная тень по панелям, снег на панелях, полный заряд АКБ (контроллер сбрасывает ток), "
            "деградация панелей. Для подгонки под реальность — «Поправка по факту».", "hint", True))
        v.addWidget(fr)
        v.addStretch(1)
        return pg
