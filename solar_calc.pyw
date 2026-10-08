#!/usr/bin/env python3
"""solar_calc.pyw  v1.2.0
Калькулятор выработки солнечной станции:
солнце → угол/азимут → панели → схема Ns×Np → провод и контакты → окно MPPT → КПД MPPT →
ток заряда → АКБ → инвертор. Данные солнца: встроенные (≈Киев) или PVGIS для любой точки.

Журнал:
v1.2.0: отдельные страницы — Настройки, Прогноз, Покрытие дома, Горсеть; моделирование заряда АКБ
        по 10 минутам (во сколько переход на сеть и обратно, кВт·ч из сети, стоимость), профиль
        потребления по часам, серия дней подряд, тариф, режим «есть сеть / нет сети».
v1.1.0: инвертор (модели, холостой ход, часы работы), провода MPPT→АКБ и АКБ→инвертор,
        ввод провода сечением или диаметром, аккумуляторы (тип, количество, сборка S×P, ёмкость,
        лимит тока заряда, холод), потребление дома за месяц, баланс по месяцам, автономия.
v1.0.0: первая версия — модель солнца (встроенная + PVGIS), схемы Ns×Np, провод/контакты,
        окно MPPT, лимит тока заряда, потери по этапам, сравнение схем, подбор угла и сечения.
"""
APP_NAME = "Солнечный калькулятор"
VERSION = "1.2.0"

import sys
import os
import importlib
import importlib.util
import subprocess
from pathlib import Path

# ───────────────────────── авто-установка библиотек ─────────────────────────
REQUIRED = (("PySide6", "PySide6>=6.5"),)


def _missing():
    return [pip for mod, pip in REQUIRED if importlib.util.find_spec(mod) is None]


def _python_exe():
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            return str(cand)
    return str(exe)


def pip_install(pips, console=True):
    py = _python_exe()
    hidden = 0x08000000 if os.name == "nt" else 0
    flags = (0x10 if console else 0x08000000) if os.name == "nt" else 0
    try:
        has_pip = subprocess.call([py, "-m", "pip", "--version"], creationflags=hidden,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    except Exception:
        has_pip = False
    if not has_pip:
        try:
            subprocess.call([py, "-m", "ensurepip", "--upgrade"], creationflags=flags)
        except Exception:
            pass

    def run(extra):
        try:
            return subprocess.call([py, "-m", "pip", "install", "--disable-pip-version-check",
                                    *extra, *pips], creationflags=flags) == 0
        except Exception:
            return False

    ok = run([]) or run(["--user"])
    importlib.invalidate_caches()
    return ok


def ensure_packages():
    if getattr(sys, "frozen", False) or "--selftest" in sys.argv:
        return
    miss = _missing()
    if not miss:
        return
    pip_install(miss)
    try:
        import site
        up = site.getusersitepackages()
        if up not in sys.path:
            sys.path.append(up)
    except Exception:
        pass
    importlib.invalidate_caches()
    miss = _missing()
    if miss:
        msg = ("Не удалось установить: " + ", ".join(miss) +
               "\n\nУстановите вручную командой:\npip install " + " ".join(miss))
        if os.name == "nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, APP_NAME, 0x10)
        else:
            print(msg)
        sys.exit(1)


ensure_packages()

import json
import math
import queue
import threading
import logging
import logging.handlers
import time
import base64
import csv
import urllib.request
import urllib.error

from PySide6.QtCore import Qt, QTimer, Signal, QByteArray, QRectF, QPointF, QSize, QTranslator, QLibraryInfo, QLocale
from PySide6.QtGui import (QPainter, QColor, QPen, QFont, QFontMetrics,
                           QGuiApplication, QPainterPath)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QToolButton, QButtonGroup,
    QHBoxLayout, QVBoxLayout, QGridLayout, QStackedWidget, QSplitter, QScrollArea,
    QDoubleSpinBox, QComboBox, QAbstractButton, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QMessageBox, QFileDialog, QSizePolicy)

APP_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG_PATH = APP_ROOT / "config.json"
LOG_PATH = APP_ROOT / "solar_calc.log"

# ───────────────────────────── данные по умолчанию ─────────────────────────────
MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
          "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
MONTHS_S = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
MID_DOY = (17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344)
WEATHER = (("clear", "☀ Ясно"), ("avg", "⛅ Средний"), ("over", "☁ Пасмурно"))
W_KEYS = [w for w, _ in WEATHER]
WEATHER_ADJ = {"clear": "ясный", "avg": "средний", "over": "пасмурный"}
MONTHS_IN = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре",
             "ноябре", "декабре"]

# ≈ Киев: глобальная горизонтальная, кВт·ч/м²·день, и средняя t воздуха, °C
BUILTIN_SUN = [[0.95, -4.0], [1.70, -3.0], [2.80, 2.0], [4.00, 9.5], [5.30, 15.5], [5.50, 19.0],
               [5.40, 21.0], [4.80, 20.0], [3.30, 14.5], [2.00, 8.5], [1.00, 2.5], [0.70, -2.0]]

PANEL_PRESETS = {
    "custom": ("Своя панель", None),
    "p100": ("100 Вт, 36 ячеек (12 В)", dict(pmax=100, vmp=18.0, imp=5.56, voc=21.6, isc=6.0, gamma=-0.40, bvoc=-0.30, noct=47, lowlight=96)),
    "p300": ("Поли 300 Вт, 60 ячеек", dict(pmax=300, vmp=32.6, imp=9.20, voc=39.8, isc=9.70, gamma=-0.40, bvoc=-0.30, noct=45, lowlight=96)),
    "p410": ("Моно 410 Вт, 108 полуяч.", dict(pmax=410, vmp=31.4, imp=13.06, voc=37.6, isc=13.90, gamma=-0.35, bvoc=-0.27, noct=45, lowlight=97)),
    "p550": ("Моно 550 Вт, 144 полуяч.", dict(pmax=550, vmp=41.96, imp=13.11, voc=49.9, isc=13.98, gamma=-0.34, bvoc=-0.27, noct=45, lowlight=97)),
    "p670": ("Моно 670 Вт, 132 яч. 210 мм", dict(pmax=670, vmp=38.3, imp=17.50, voc=45.9, isc=18.60, gamma=-0.34, bvoc=-0.26, noct=45, lowlight=97)),
    "jinko590": ("Jinko Tiger Neo JKM590N-72HL4-BDV 590 Вт", dict(pmax=590, vmp=44.17, imp=13.36, voc=52.90, isc=14.07, gamma=-0.29, bvoc=-0.25, noct=45, lowlight=97.5)),
    "ja585": ("JA Solar JAM72D40-585/GB 585 Вт", dict(pmax=585, vmp=44.22, imp=13.23, voc=52.16, isc=13.89, gamma=-0.29, bvoc=-0.25, noct=45, lowlight=97.5)),
    "longi585": ("LONGi Hi-MO X6 LR5-72HTH-585M 585 Вт", dict(pmax=585, vmp=44.21, imp=13.24, voc=52.36, isc=14.27, gamma=-0.29, bvoc=-0.23, noct=45, lowlight=97.5)),
    "longi480": ("LONGi Hi-MO X10 LR7-54HVH-480M 480 Вт", dict(pmax=480, vmp=33.28, imp=14.43, voc=40.29, isc=15.13, gamma=-0.26, bvoc=-0.20, noct=45, lowlight=97.5)),
    "trina575": ("Trina Vertex TSM-DE19R 575 Вт (210 мм)", dict(pmax=575, vmp=38.80, imp=14.83, voc=46.10, isc=16.00, gamma=-0.34, bvoc=-0.25, noct=45, lowlight=97)),
}
MPPT_PRESETS = {
    "custom": ("Свой контроллер", None),
    "cn60": ("Китайский MPPT 60 А / 150 В", dict(v_max=150, vmpp_min=0, vmpp_max=145, iin_max=0, iout_max=60, eta=96, eta_k=3, own_w=4, headroom=3)),
    "cn40": ("Китайский MPPT 40 А / 100 В", dict(v_max=100, vmpp_min=0, vmpp_max=95, iin_max=0, iout_max=40, eta=95, eta_k=3, own_w=3, headroom=3)),
    "vic150_35": ("Victron 150/35", dict(v_max=150, vmpp_min=0, vmpp_max=145, iin_max=40, iout_max=35, eta=98, eta_k=1, own_w=1, headroom=2)),
    "vic250_60": ("Victron 250/60", dict(v_max=250, vmpp_min=0, vmpp_max=245, iin_max=35, iout_max=60, eta=98, eta_k=1, own_w=1, headroom=2)),
    "hyb48": ("Гибрид 48 В, MPPT 120–450 В", dict(v_max=500, vmpp_min=120, vmpp_max=450, iin_max=22, iout_max=100, eta=97, eta_k=0, own_w=5, headroom=0)),
}
# относительное потребление по часам 0..23 (нормируется)
LOAD_PROFILES = {
    "typ": ("Утро + вечер (типовой)", [0.55, 0.45, 0.42, 0.42, 0.45, 0.6, 0.95, 1.35, 1.25, 1.0, 0.9, 0.9, 0.95, 0.9,
                                       0.85, 0.9, 1.05, 1.4, 1.75, 1.95, 1.85, 1.5, 1.1, 0.75]),
    "day": ("Днём дома (удалёнка)", [0.55, 0.45, 0.42, 0.42, 0.45, 0.6, 0.9, 1.2, 1.3, 1.3, 1.35, 1.4, 1.45, 1.4,
                                     1.35, 1.3, 1.3, 1.4, 1.6, 1.7, 1.6, 1.3, 1.0, 0.7]),
    "flat": ("Ровно круглые сутки", [1.0] * 24),
    "night": ("Ночью больше (бойлер, отопление)", [1.6, 1.6, 1.6, 1.6, 1.5, 1.3, 1.0, 0.9, 0.8, 0.7, 0.7, 0.7, 0.7, 0.7,
                                                   0.7, 0.7, 0.8, 1.0, 1.2, 1.3, 1.3, 1.3, 1.4, 1.5]),
}


def load_profile(key):
    p = LOAD_PROFILES.get(key, LOAD_PROFILES["typ"])[1]
    t = sum(p)
    return [x / t for x in p]


INVERTER_PRESETS = {
    "custom": ("Свой инвертор", None),
    "sin1": ("Синус 1–2 кВт, 12 В", dict(inv_p=1500, inv_eta=88, inv_idle=15)),
    "hyb3": ("Гибрид 3–3.6 кВт, 24 В (китайский)", dict(inv_p=3600, inv_eta=90, inv_idle=35)),
    "hyb5": ("Гибрид 5–6.2 кВт, 48 В (китайский)", dict(inv_p=6000, inv_eta=92, inv_idle=50)),
    "hyb10": ("Гибрид 8–12 кВт, 48 В", dict(inv_p=10000, inv_eta=93, inv_idle=80)),
    "trans": ("Трансформаторный / ИБП 3 кВт", dict(inv_p=3000, inv_eta=85, inv_idle=60)),
    "eco": ("С режимом экономии (поиск нагрузки)", dict(inv_p=3000, inv_eta=93, inv_idle=12)),
}
BATTERY_PRESETS = {
    "custom": ("Свои АКБ", None),
    "lfp12_100": ("LiFePO4 12.8 В 100 А·ч", dict(chem="lfp", bat_unit_v=12.8, bat_ah=100, bat_c=0.5, bat_dod=90)),
    "lfp12_200": ("LiFePO4 12.8 В 200 А·ч", dict(chem="lfp", bat_unit_v=12.8, bat_ah=200, bat_c=0.5, bat_dod=90)),
    "lfp12_280": ("LiFePO4 12.8 В 280 А·ч", dict(chem="lfp", bat_unit_v=12.8, bat_ah=280, bat_c=0.5, bat_dod=90)),
    "eve_lf105": ("Ячейка EVE LF105 3.2 В 105 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=105, bat_c=0.5, bat_dod=90)),
    "eve_lf230": ("Ячейка EVE LF230 3.2 В 230 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=230, bat_c=0.5, bat_dod=90)),
    "eve_lf280k": ("Ячейка EVE LF280K 3.2 В 280 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=280, bat_c=0.5, bat_dod=90)),
    "eve_lf304": ("Ячейка EVE LF304 3.2 В 304 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=304, bat_c=0.5, bat_dod=90)),
    "eve_mb30": ("Ячейка EVE MB30 3.2 В 306 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=306, bat_c=0.5, bat_dod=90)),
    "eve_mb31": ("Ячейка EVE MB31 3.2 В 314 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=314, bat_c=0.5, bat_dod=90)),
    "rept_cb75": ("Ячейка REPT CB75 3.2 В 314 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=314, bat_c=0.5, bat_dod=90)),
    "eve_lf560k": ("Ячейка EVE LF560K 3.2 В 560 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=560, bat_c=0.5, bat_dod=90)),
    "eve_mb56": ("Ячейка EVE MB56 3.2 В 628 А·ч", dict(chem="lfp", bat_unit_v=3.2, bat_ah=628, bat_c=0.5, bat_dod=90)),
    "lfp48_100": ("Стойка LiFePO4 51.2 В 100 А·ч", dict(chem="lfp", bat_unit_v=51.2, bat_ah=100, bat_c=0.5, bat_dod=90)),
    "lfp48_200": ("Стойка LiFePO4 51.2 В 200 А·ч", dict(chem="lfp", bat_unit_v=51.2, bat_ah=200, bat_c=0.5, bat_dod=90)),
    "agm100": ("AGM 12 В 100 А·ч", dict(chem="lead", bat_unit_v=12.0, bat_ah=100, bat_c=0.2, bat_dod=50)),
    "agm200": ("AGM 12 В 200 А·ч", dict(chem="lead", bat_unit_v=12.0, bat_ah=200, bat_c=0.2, bat_dod=50)),
    "gel200": ("Гель 12 В 200 А·ч", dict(chem="lead", bat_unit_v=12.0, bat_ah=200, bat_c=0.15, bat_dod=50)),
    "car75": ("Автомобильный 12 В 75 А·ч (плохо для СЭС)", dict(chem="lead", bat_unit_v=12.0, bat_ah=75, bat_c=0.1, bat_dod=30)),
}
# циклы (по данным производителя, 25°C), вес кг, размеры мм, сопротивление мОм
CELL_INFO = {
    "eve_lf105": (4000, 1.98, "130.3×36.3×200.5", "≤0.32"),
    "eve_lf230": (4000, 4.14, "173.9×53.8×207.2", "≤0.25"),
    "eve_lf280k": (8000, 5.49, "173.7×71.7×207.2", "≤0.25"),
    "eve_lf304": (4000, 5.45, "173.7×71.7×207.2", "≤0.16"),
    "eve_mb30": (10000, 5.60, "173.7×71.7×207.2", "≤0.18"),
    "eve_mb31": (8000, 5.60, "173.7×71.7×207.2", "≤0.18"),
    "rept_cb75": (8000, None, "", ""),
    "eve_lf560k": (8000, 10.70, "352.3×71.7×207.2", "≤0.25"),
    "eve_mb56": (8000, 11.50, "352.3×71.7×205.1", "≈0.09"),
}
CONTACT_MOHM = {"good": 0.3, "norm": 1.0, "mid": 3.0, "bad": 10.0}
CONTACT_ITEMS = (("good", "Отлично"), ("norm", "Норма"), ("mid", "Средне"), ("bad", "Плохо"))
MAT = {"cu": (0.0175, 0.00393), "al": (0.0282, 0.00403)}
# допустимый ток, открытая прокладка (ПУЭ 1.3.4 / 1.3.5)
AMP_CU = {1.5: 23, 2.5: 30, 4: 41, 6: 50, 10: 80, 16: 100, 25: 140, 35: 170, 50: 215, 70: 270, 95: 330}
AMP_AL = {2.5: 24, 4: 32, 6: 39, 10: 60, 16: 75, 25: 105, 35: 130, 50: 165, 70: 210, 95: 255}
WIRE_SECTIONS = (4, 6, 10, 16, 25, 35, 50)

DEFAULT_SYS = dict(
    lat=50.45, lon=30.52, tilt=15, aspect=0, horizon=5, tz=2, dst=True,
    month=11, weather="over", overcast_k=35,
    p_preset="p670", pmax=670, vmp=38.3, imp=17.5, voc=45.9, isc=18.6, gamma=-0.34, bvoc=-0.26,
    noct=45, lowlight=97,
    ns=2, np=3, mismatch=2, soiling=2, calib=100,
    wire_len=15, wire_s=16, wire_mat="al", contact="norm", n_main=6,
    m_preset="cn60", v_max=150, vmpp_min=0, vmpp_max=145, iin_max=0, iout_max=60, eta=96, eta_k=3,
    own_w=4, headroom=3,
    wire_mode="s", bw_len=1.5, bw_s=25, bw_mat="cu", iw_len=1.5, iw_s=35, iw_mat="cu",
    bat_preset="eve_lf280k", bat_v="48", chem="lfp", bat_unit_v=3.2, bat_ah=280, bat_count=16, bat_dod=90,
    bat_c=0.5, t_bat=15, bat_ch=56.8, eta_bat=97,
    inv_preset="hyb5", inv_p=6000, inv_eta=92, inv_idle=50, inv_hours=24,
    load_mode="m", load_kwh=250, load_winter=30, night_share=50, load_profile="typ",
    grid_mode="backup", back_soc=40, tariff=4.32, ser_days=4, ser_weather="over", ser_soc0=100,
    t_min=-25, t_max=35, pt_g=100, pt_t=0,
)
DEFAULT_CONFIG = {"theme": "dark", "geometry": "", "sys": dict(DEFAULT_SYS),
                  "builtin": [list(x) for x in BUILTIN_SUN], "pvgis": None, "use_pvgis": True,
                  "last_dir": ""}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            sysd = dict(DEFAULT_SYS)
            sysd.update(data.get("sys") or {})
            cfg.update(data)
            cfg["sys"] = sysd
            if not isinstance(cfg.get("builtin"), list) or len(cfg["builtin"]) != 12:
                cfg["builtin"] = [list(x) for x in BUILTIN_SUN]
    except Exception as e:
        print("config:", e)
    return cfg


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.error(f"✗ Не удалось сохранить config.json: {e}")


# ─────────────────────────────────── лог ───────────────────────────────────
_DONE = object()
UIQ = queue.Queue()


class _QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            UIQ.put(("log", record.levelno, time.strftime("%H:%M:%S") + "  " + record.getMessage()))
        except Exception:
            pass


log = logging.getLogger("solar_calc")
log.setLevel(logging.INFO)
log.addHandler(_QueueHandler())
try:
    _fh = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=1, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(_fh)
except Exception:
    pass

# ═════════════════════════════════ ФИЗИКА ═════════════════════════════════
DT = 1.0 / 6.0          # шаг 10 минут
N_STEPS = 144
LN5 = math.log(5.0)


def sun(lat, lon, doy, t_utc):
    """→ (cos зенита, зенит рад, азимут от юга рад (+запад), внеатм. облучённость)."""
    B = 2 * math.pi * (doy - 1) / 365.0
    decl = (0.006918 - 0.399912 * math.cos(B) + 0.070257 * math.sin(B) - 0.006758 * math.cos(2 * B)
            + 0.000907 * math.sin(2 * B) - 0.002697 * math.cos(3 * B) + 0.00148 * math.sin(3 * B))
    eot = 229.18 * (0.000075 + 0.001868 * math.cos(B) - 0.032077 * math.sin(B)
                    - 0.014615 * math.cos(2 * B) - 0.040849 * math.sin(2 * B))
    st = t_utc + lon / 15.0 + eot / 60.0
    w = math.radians(15.0 * (st - 12.0))
    phi = math.radians(lat)
    cosz = math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(w)
    cosz = max(-1.0, min(1.0, cosz))
    zen = math.acos(cosz)
    az = math.atan2(math.sin(w), math.cos(w) * math.sin(phi) - math.tan(decl) * math.cos(phi))
    g0 = 1367.0 * (1 + 0.033 * math.cos(2 * math.pi * doy / 365.0))
    return cosz, zen, az, g0


def haurwitz(cosz):
    return 1098.0 * cosz * math.exp(-0.057 / cosz) if cosz > 0.01 else 0.0


def erbs_kd(kt):
    if kt <= 0.22:
        return 1 - 0.09 * kt
    if kt <= 0.8:
        return 0.9511 - 0.1604 * kt + 4.388 * kt ** 2 - 16.638 * kt ** 3 + 12.336 * kt ** 4
    return 0.165


def interp24(arr, x):
    x %= 24.0
    i = int(x)
    f = x - i
    return arr[i] * (1 - f) + arr[(i + 1) % 24] * f


class SunData:
    def __init__(self, cfg):
        self.builtin = [list(map(float, r)) for r in cfg.get("builtin") or BUILTIN_SUN]
        self.pv = cfg.get("pvgis")
        self.enabled = bool(cfg.get("use_pvgis", True))

    def use_pv(self, lat, lon):
        pv = self.pv
        return bool(self.enabled and pv and abs(pv.get("lat", 999) - lat) < 0.06
                    and abs(pv.get("lon", 999) - lon) < 0.06 and len(pv.get("months", [])) == 12)

    def tag(self, lat, lon):
        if self.use_pv(lat, lon):
            return ("pv", self.pv["lat"], self.pv["lon"], self.pv.get("stamp", ""))
        return ("bi", tuple(tuple(r) for r in self.builtin))

    def label(self, lat, lon):
        if self.use_pv(lat, lon):
            return f"PVGIS ({self.pv['lat']:.2f}, {self.pv['lon']:.2f})"
        return "встроенные (≈Киев)"


_IRR_CACHE = {}
_IRR_LOCK = threading.Lock()


def irr_day(s, sd, m, w):
    """Средний день месяца m при погоде w → [(час местный, POA Вт/м², t воздуха)]."""
    lat, lon = float(s["lat"]), float(s["lon"])
    key = (lat, lon, float(s["tilt"]), float(s["aspect"]), float(s["horizon"]), float(s["tz"]),
           bool(s["dst"]), float(s["overcast_k"]), m, w, sd.tag(lat, lon))
    with _IRR_LOCK:
        hit = _IRR_CACHE.get(key)
    if hit is not None:
        return hit
    tilt = math.radians(float(s["tilt"]))
    cb, sb = math.cos(tilt), math.sin(tilt)
    asp = math.radians(float(s["aspect"]))
    hor = float(s["horizon"])
    tz = float(s["tz"]) + (1 if s["dst"] and 3 <= m <= 9 else 0)
    ko = float(s["overcast_k"]) / 100.0
    alb = 0.35 if m in (0, 1, 11) else 0.2
    doy = MID_DOY[m]
    geo = [sun(lat, lon, doy, (i + 0.5) * DT) for i in range(N_STEPS)]
    ghi = [0.0] * N_STEPS
    dhi = [None] * N_STEPS
    ta = [0.0] * N_STEPS
    pv = sd.pv["months"][m] if sd.use_pv(lat, lon) else None
    if pv is None:
        H, Tm = sd.builtin[m]
        cs = [haurwitz(g[0]) for g in geo]
        if w == "avg":
            tot = sum(cs) * DT
            k = min(1.0, H * 1000.0 / tot) if tot > 0 else 0.0
            ghi = [c * k for c in cs]
        elif w == "clear":
            ghi = cs
        else:
            ghi = [c * ko for c in cs]
        amp = {"clear": 5.0, "avg": 3.5, "over": 1.5}[w]
        for i in range(N_STEPS):
            tl = (i + 0.5) * DT + tz
            ta[i] = Tm + amp * math.cos(2 * math.pi * (tl - 15.0) / 24.0)
    else:
        sh = pv.get("shift", 0.0)
        for i, g in enumerate(geo):
            x = (i + 0.5) * DT - sh
            ta[i] = interp24(pv["t"], x)
            if g[0] <= 0:
                continue
            if w == "avg":
                G = interp24(pv["ghi"], x)
                ghi[i] = G
                dhi[i] = min(G, interp24(pv["dhi"], x))
            elif w == "clear":
                ghi[i] = interp24(pv["gcs"], x)
            else:
                ghi[i] = interp24(pv["gcs"], x) * ko
    out = []
    for i, (cosz, zen, az, g0) in enumerate(geo):
        tl = ((i + 0.5) * DT + tz) % 24.0
        G = ghi[i]
        if cosz <= 0.0 or G <= 0.0:
            out.append((tl, 0.0, ta[i]))
            continue
        if w == "over":
            D = G
        elif dhi[i] is not None:
            D = dhi[i]
        else:
            kt = min(1.0, G / (g0 * cosz))
            D = G * erbs_kd(kt)
        B = max(0.0, G - D)
        elev = 90.0 - math.degrees(zen)
        beam = 0.0
        if B > 0 and cosz > 0.035 and elev > hor:
            dni = min(B / cosz, 1050.0)
            ct = cosz * cb + math.sin(zen) * sb * math.cos(az - asp)
            if ct > 0:
                iam = max(0.0, 1 - 0.05 * (1 / max(ct, 0.05) - 1))
                beam = dni * ct * iam
        diff = D * (1 + cb) / 2 * 0.95
        refl = G * alb * (1 - cb) / 2
        out.append((tl, beam + diff + refl, ta[i]))
    out.sort()
    with _IRR_LOCK:
        if len(_IRR_CACHE) > 4000:
            _IRR_CACHE.clear()
        _IRR_CACHE[key] = out
    return out


def make_ctx(s):
    """Предрасчёт констант системы для быстрой симуляции."""
    f = lambda k: float(s[k])
    ns, np_ = max(1, int(s["ns"])), max(1, int(s["np"]))
    rho, a = MAT.get(s["wire_mat"], MAT["cu"])
    rc = CONTACT_MOHM.get(s["contact"], 1.0) / 1000.0
    gam = f("gamma") / 100.0
    c = dict(
        ns=ns, np=np_, npan=ns * np_, pmax=f("pmax"), vmp=f("vmp"), imp=f("imp"), voc=f("voc"),
        isc=f("isc"), gam=gam, bvmp=gam - 0.0004, bvoc=f("bvoc") / 100.0,
        noctk=(f("noct") - 20.0) / 800.0, llk=(1 - f("lowlight") / 100.0) / LN5,
        soil=f("soiling") / 100.0, mmk=(1 - f("mismatch") / 100.0) * f("calib") / 100.0,
        rw20=rho * 2 * f("wire_len") / max(0.1, f("wire_s")), walpha=a,
        rconst=f("n_main") * rc + (ns + 1) * rc / np_,
        vin_min=max(f("vmpp_min"), f("bat_ch") + f("headroom")),
        vmpp_max=f("vmpp_max"), v_max=f("v_max"), iin_max=f("iin_max"),
        eta=f("eta") / 100.0, etak=f("eta_k") / 100.0, own=f("own_w"), vbat=max(1.0, f("bat_ch")),
        pout_max=f("iout_max") * f("bat_ch") if f("iout_max") > 0 else 1e12,
        eta_bat=f("eta_bat") / 100.0, inv_eta=f("inv_eta") / 100.0, inv_idle=f("inv_idle"),
    )
    c["pstc_tot"] = c["pmax"] * c["npan"]
    # провода со стороны АКБ: 4 контакта на линию (наконечники + автомат/предохранитель);
    # опрессованный силовой наконечник ≈ в 3 раза лучше разъёма MC4 того же «качества»
    rcb = rc * 0.3
    c["rb"] = MAT.get(s["bw_mat"], MAT["cu"])[0] * 2 * f("bw_len") / max(0.1, f("bw_s")) + 4 * rcb
    c["ri"] = MAT.get(s["iw_mat"], MAT["cu"])[0] * 2 * f("iw_len") / max(0.1, f("iw_s")) + 4 * rcb
    # банк АКБ
    lfp = s["chem"] == "lfp"
    sys_nom = int(s["bat_v"]) * (12.8 / 12.0 if lfp else 1.0)
    unit_v = max(0.5, f("bat_unit_v"))
    nser = max(1, int(round(sys_nom / unit_v)))
    cnt = max(0, int(s["bat_count"]))
    npar = cnt // nser
    tfac = 1 + (0.004 if lfp else 0.008) * min(0.0, f("t_bat") - 25)
    c.update(sys_nom=sys_nom, nser=nser, npar=npar, extra=cnt - npar * nser, bank_v=nser * unit_v,
             bank_ah=npar * f("bat_ah"), mismatch_v=abs(nser * unit_v - sys_nom) / sys_nom > 0.1)
    c["bank_wh"] = c["bank_v"] * c["bank_ah"]
    c["usable_wh"] = c["bank_wh"] * f("bat_dod") / 100.0 * tfac
    c["bank_ich"] = c["bank_ah"] * f("bat_c")
    c["ilim"] = min(f("iout_max"), c["bank_ich"]) if c["bank_ich"] > 0 else f("iout_max")
    c["pout_max"] = c["ilim"] * c["vbat"]
    lm = f("load_kwh") if s.get("load_mode", "m") == "m" else f("load_kwh") / 12.0
    c.update(inv_p=f("inv_p"), inv_hours=f("inv_hours"), load_month=lm,
             load_winter=f("load_winter") / 100.0, back_soc=f("back_soc") / 100.0, tariff=f("tariff"),
             grid_mode=s.get("grid_mode", "backup"), profile=load_profile(s.get("load_profile", "typ")))
    c["night"] = sum(c["profile"][h] for h in list(range(0, 7)) + list(range(18, 24)))
    return c


def wire_r(c, ta):
    return c["rw20"] * (1 + c["walpha"] * (ta - 10.0)) + c["rconst"]


def sim_point(c, poa, ta):
    """→ (pot, soil, cell, mm, arr, pin, conv, out, outb, vin, I, vp, tc, R)."""
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
    mm = Va * Ia
    dV = max(0.5, Vo - Va)
    vreq = c["vin_min"]
    I = Ia
    if Va - Ia * R < vreq:
        I = Ia * (Vo - vreq) / (dV + Ia * R)
    if c["iin_max"] > 0 and I > c["iin_max"]:
        I = c["iin_max"]
    if I <= 0 or Ia <= 0:
        return (pot, soil, cell, mm, 0, 0, 0, 0, 0, 0, 0, Vo, tc, R)
    I = min(I, Ia)
    Vp = Va + (Ia - I) / Ia * dV
    arr = Vp * I
    vin = Vp - I * R
    pin = arr - I * I * R
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


def make_checks(s, c, res):
    """→ [(уровень 'ok'|'warn'|'err'|'info', текст)]."""
    ch = []
    ns, np_ = c["ns"], c["np"]
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
    ch.append((lvl, f"Падение на проводе и контактах при полном солнце: {du:.2f}% ({istc * R20:.2f} В, {ploss:.0f} Вт). Норма ≤ 2%, зимой ток меньше — и потери меньше."))
    isc_arr = np_ * c["isc"]
    amp = ampacity(float(s["wire_s"]), s["wire_mat"])
    if isc_arr * 1.25 > amp:
        ch.append(("err", f"Провод {s['wire_s']} мм² ({'Al' if s['wire_mat'] == 'al' else 'Cu'}) держит ≈{amp:.0f} А (открыто, ПУЭ), а нужно Isc×1.25 = {isc_arr * 1.25:.0f} А."))
    else:
        ch.append(("ok", f"Провод по току: Isc×1.25 = {isc_arr * 1.25:.0f} А при допустимых ≈{amp:.0f} А."))
    if c["iin_max"] > 0 and isc_arr > c["iin_max"]:
        ch.append(("warn", f"Isc поля {isc_arr:.1f} А > макс. входного тока MPPT {c['iin_max']:.0f} А — MPPT будет срезать."))
    if np_ >= 3:
        ch.append(("warn", f"{np_} параллельных цепочки — нужен предохранитель на каждую (обратный ток при КЗ)."))
    if year_kwh(res, "clear") < 0.02 * c["pstc_tot"] / 1000 * 365:
        ch.insert(0, ("err", f"MPPT почти не запускается: Vmp цепочки {ns * c['vmp']:.1f} В, а нужно больше {c['vin_min']:.1f} В. Больше панелей последовательно."))
    clip_y = sum((res[(m, 'avg')]['wh'][6] - res[(m, 'avg')]['wh'][7]) * DAYS[m] for m in range(12)) / 1000
    y = year_kwh(res, "avg")
    peak_all = max(res[(m, 'clear')]["peak_i"] for m in range(12))
    who = "MPPT" if c["ilim"] >= float(s["iout_max"]) else f"АКБ ({c['bank_ah']:.0f} А·ч × {float(s['bat_c']):g}C)"
    if clip_y > 0.01 * max(y, 1e-9):
        ch.append(("warn", f"Упор в ток заряда {c['ilim']:.0f} А (ограничивает {who}): теряется ≈{clip_y:.0f} кВт·ч/год ({clip_y / max(y + clip_y, 1e-9) * 100:.1f}%)."))
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


def load_day_wh(c, m):
    """Потребление дома в средний день месяца m, Вт·ч на 230 В (зимой больше)."""
    return c["load_month"] * (1 + c["load_winter"] * math.cos(2 * math.pi * m / 12.0)) * 12.0 / 365.0 * 1000.0


def soc_run(c, curve, load_wh, prof, e, on_grid):
    """Один день шагами DT: солнце → дом, излишек → АКБ, нехватка → АКБ, АКБ пуста → сеть.
    e — запас над минимальным зарядом, Вт·ч. → (итог дня, e, on_grid)."""
    usable = c["usable_wh"]
    cap = max(1.0, c["bank_wh"])
    base = cap - usable
    e_back = max(0.0, min(usable, c["back_soc"] * cap - base))
    eta_b = c["eta_bat"]
    eta_i = max(0.5, c["inv_eta"])
    vb = max(1.0, c["sys_nom"])
    idle = c["inv_idle"] * min(24.0, c["inv_hours"]) / 24.0
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
                e += net * eta_b * DT
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
            e += pv * eta_b * DT
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
                 load_dc=load_dc_sum, load=load_wh, soc_min=soc_min, start_grid=bool(pts) and False), e, on_grid)


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


def bat_checks(s, c, res, bal):
    ch = []
    sv = int(s["bat_v"])
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


def compute_all(s, sd):
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


LOSS_ROWS = (("Грязь / пыль / снег", 0, 1), ("Температура и слабый свет", 1, 2),
             ("Рассогласование + поправка", 2, 3), ("Окно MPPT / лимит входного тока", 3, 4),
             ("Провод и контакты", 4, 5), ("КПД MPPT + собственное потребление", 5, 6),
             ("Упор в макс. ток заряда", 6, 7), ("Провод MPPT → АКБ", 7, 8))


# ───────────────────────────────── PVGIS ─────────────────────────────────
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


def fetch_pvgis(lat, lon, builtin):
    params = (f"lat={lat:.4f}&lon={lon:.4f}&month=0&angle=0&aspect=0&global=1&clearsky=1"
              f"&showtemperatures=1&outputformat=json")
    last = "нет ответа"
    for ver in ("v5_3", "v5_2"):
        url = f"https://re.jrc.ec.europa.eu/api/{ver}/DRcalc?{params}"
        log.info(f"⏳ PVGIS {ver}: запрос…")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"solar_calc/{VERSION}"})
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


# ═════════════════════════════════ ИНТЕРФЕЙС ═════════════════════════════════
_QT_THEMES = {
    "dark": {"bg": "#1b1d23", "side": "#16181d", "panel": "#23262e", "panel2": "#2a2e38", "line": "#343946",
             "text": "#e6e8ee", "muted": "#8a91a3", "log_bg": "#111318", "log_fg": "#d5d8e0", "accent": "#4f8cff"},
    "light": {"bg": "#f3f4f7", "side": "#e9ebf0", "panel": "#ffffff", "panel2": "#f1f3f7", "line": "#dde1e8",
              "text": "#1c2230", "muted": "#6b7385", "log_bg": "#fbfbfd", "log_fg": "#1c2230", "accent": "#2f6fe4"}}
_OK, _ERR, _WARN = "#3ecf8e", "#ff5d6c", "#f5b545"
SERIES_COL = {"clear": "#f5b545", "avg": None, "over": "#8a91a3"}


def _qss(p):
    return f"""
* {{ font-family: "Segoe UI"; font-size: 10pt; color: {p['text']}; }}
QMainWindow, QWidget#root {{ background: {p['bg']}; }}
QDialog, QMessageBox, QFileDialog, QInputDialog {{ background: {p['panel']}; color: {p['text']}; }}
QMessageBox QLabel, QDialog QLabel, QFileDialog QLabel, QInputDialog QLabel {{ color: {p['text']}; background: transparent; }}
QDialog QPushButton, QMessageBox QPushButton, QFileDialog QPushButton, QInputDialog QPushButton {{ min-width: 80px; }}
QWidget#page, QWidget#scrollInner, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {p['bg']}; }}
QScrollArea {{ border: none; }}
QFrame#side {{ background: {p['side']}; border-right: 1px solid {p['line']}; }}
QFrame#side QToolButton {{ background: transparent; border: none; border-radius: 9px; font-size: 17pt; padding: 4px; }}
QFrame#side QToolButton:hover {{ background: {p['panel2']}; }}
QFrame#side QToolButton:checked {{ background: {p['panel2']}; border-left: 3px solid {p['accent']}; }}
QFrame#sideSep {{ background: {p['line']}; margin: 4px 6px; }}
QFrame#card {{ background: {p['panel']}; border: 1px solid {p['line']}; border-radius: 10px; }}
QFrame#kpi {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 9px; }}
QLabel {{ background: transparent; }}
QLabel#cardTitle {{ color: {p['muted']}; font-size: 8pt; font-weight: 600; letter-spacing: 1px; }}
QLabel#hint, QLabel#muted {{ color: {p['muted']}; font-size: 9pt; }}
QLabel#kpiVal {{ font-size: 16pt; font-weight: 600; }}
QLabel#kpiCap {{ color: {p['muted']}; font-size: 8pt; }}
QLabel#fieldLab {{ color: {p['muted']}; }}
QLabel#subHead {{ color: {p['text']}; font-weight: 600; padding-top: 6px; border-bottom: 1px solid {p['line']}; }}
QLabel#bigTitle {{ font-size: 13pt; font-weight: 600; }}
QFrame#statusbar {{ background: {p['side']}; border-top: 1px solid {p['line']}; }}
QLabel#pill {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 10px; padding: 1px 10px; font-size: 9pt; }}
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit {{
    background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 7px; padding: 4px 6px;
    selection-background-color: {p['accent']}; selection-color: #ffffff; }}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color: {p['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {p['panel']}; border: 1px solid {p['line']}; selection-background-color: {p['accent']}; selection-color: #fff; outline: 0; }}
QPushButton {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 7px; padding: 6px 12px; }}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:pressed {{ background: {p['line']}; }}
QPushButton:disabled {{ color: {p['muted']}; }}
QPushButton#primary {{ background: {p['accent']}; color: #ffffff; font-weight: 600; border: 1px solid {p['accent']}; }}
QPushButton#primary:hover {{ background: {p['accent']}; border-color: {p['text']}; }}
QPushButton#danger {{ background: transparent; color: {_ERR}; border: 1px solid {_ERR}; }}
QPushButton#chip {{ padding: 3px 10px; font-size: 9pt; border-radius: 11px; }}
QPushButton#seg {{ border-radius: 0; padding: 5px 10px; margin: 0; }}
QPushButton#seg[pos="l"] {{ border-top-left-radius: 7px; border-bottom-left-radius: 7px; }}
QPushButton#seg[pos="r"] {{ border-top-right-radius: 7px; border-bottom-right-radius: 7px; }}
QPushButton#seg[pos="s"] {{ border-radius: 7px; }}
QPushButton#seg:checked {{ background: {p['accent']}; color: #ffffff; border-color: {p['accent']}; }}
QToolButton#stepBtn {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 6px; min-width: 22px; max-width: 22px; min-height: 22px; font-weight: 600; }}
QToolButton#stepBtn:hover {{ border-color: {p['accent']}; }}
QAbstractItemView {{ background: {p['panel']}; alternate-background-color: {p['panel2']}; color: {p['text']};
    border: 1px solid {p['line']}; border-radius: 8px; selection-background-color: {p['accent']}; selection-color: #ffffff; }}
QTableWidget {{ gridline-color: transparent; }}
QHeaderView::section {{ background: {p['panel2']}; color: {p['muted']}; border: none; border-bottom: 1px solid {p['line']}; padding: 5px 6px; font-weight: 600; }}
QTableCornerButton::section {{ background: {p['panel2']}; border: none; }}
QPlainTextEdit#log {{ background: {p['log_bg']}; color: {p['log_fg']}; font-family: Consolas, monospace; font-size: 9pt; }}
QMenu {{ background: {p['panel']}; border: 1px solid {p['line']}; padding: 4px; }}
QMenu::item {{ padding: 5px 22px 5px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: {p['accent']}; color: #ffffff; }}
QMenu::item:disabled {{ color: {p['muted']}; }}
QMenu::separator {{ height: 1px; background: {p['line']}; margin: 4px 6px; }}
QToolTip {{ background: {p['panel2']}; color: {p['text']}; border: 1px solid {p['accent']}; padding: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle {{ background: {p['line']}; border-radius: 5px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: {p['bg']}; }}
QSplitter::handle:hover {{ background: {p['accent']}; }}
QFileDialog QListView, QFileDialog QTreeView {{ background: {p['panel2']}; }}
QFileDialog QToolButton {{ background: {p['panel2']}; border: 1px solid {p['line']}; border-radius: 6px; padding: 3px; }}
"""


# ──────────────────────────────── виджеты ────────────────────────────────
class Toggle(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 22)
        self._on, self._off, self._knob = QColor("#4f8cff"), QColor("#454b59"), QColor("#ffffff")

    def set_theme(self, on, off, knob):
        self._on, self._off, self._knob = QColor(on), QColor(off), QColor(knob)
        self.update()

    def sizeHint(self):
        return QSize(40, 22)

    def paintEvent(self, e):
        pa = QPainter(self)
        pa.setRenderHint(QPainter.Antialiasing)
        pa.setPen(Qt.NoPen)
        pa.setBrush(self._on if self.isChecked() else self._off)
        pa.drawRoundedRect(0, 0, 40, 22, 11, 11)
        pa.setBrush(QColor("#ffffff"))
        pa.drawEllipse(21 if self.isChecked() else 3, 3, 16, 16)


class Segmented(QWidget):
    changed = Signal(str)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.btns = {}
        n = len(items)
        for i, (k, t) in enumerate(items):
            b = QPushButton(t)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("pos", "s" if n == 1 else "l" if i == 0 else "r" if i == n - 1 else "m")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.group.addButton(b)
            self.btns[k] = b
            lay.addWidget(b)
            b.clicked.connect(lambda _=False, k=k: self.changed.emit(k))

    def value(self):
        for k, b in self.btns.items():
            if b.isChecked():
                return k
        return next(iter(self.btns))

    def setValue(self, k):
        b = self.btns.get(str(k))
        if b:
            b.setChecked(True)


class _Spin(QDoubleSpinBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class NoWheelCombo(QComboBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class Stepper(QWidget):
    changed = Signal(float)

    def __init__(self, lo, hi, step=1.0, dec=0, suffix="", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.sp = _Spin()
        self.sp.setRange(lo, hi)
        self.sp.setSingleStep(step)
        self.sp.setDecimals(dec)
        if suffix:
            self.sp.setSuffix(" " + suffix)
        self.sp.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.sp.setFocusPolicy(Qt.StrongFocus)
        self.sp.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sp.setKeyboardTracking(False)
        self.sp.setMinimumWidth(80)
        bm, bp = QToolButton(), QToolButton()
        for b, t in ((bm, "−"), (bp, "+")):
            b.setText(t)
            b.setObjectName("stepBtn")
            b.setAutoRepeat(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
        bm.clicked.connect(self.sp.stepDown)
        bp.clicked.connect(self.sp.stepUp)
        lay.addWidget(self.sp, 1)
        lay.addWidget(bm)
        lay.addWidget(bp)
        self.sp.valueChanged.connect(self.changed.emit)

    def value(self):
        return self.sp.value()

    def reconfigure(self, lo, hi, step, dec, suffix):
        self.sp.blockSignals(True)
        self.sp.setDecimals(dec)
        self.sp.setRange(lo, hi)
        self.sp.setSingleStep(step)
        self.sp.setSuffix(" " + suffix if suffix else "")
        self.sp.blockSignals(False)

    def setValue(self, v):
        self.sp.blockSignals(True)
        self.sp.setValue(float(v))
        self.sp.blockSignals(False)


def _lab(text, name=None, wrap=False):
    l = QLabel(text)
    if name:
        l.setObjectName(name)
    if wrap:
        l.setWordWrap(True)
    return l


def _card(title):
    fr = QFrame()
    fr.setObjectName("card")
    v = QVBoxLayout(fr)
    v.setContentsMargins(14, 10, 14, 12)
    v.setSpacing(8)
    if title:
        v.addWidget(_lab(title.upper(), "cardTitle"))
    return fr, v


def _btn(text, name=None, tip=None, slot=None):
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    if tip:
        b.setToolTip(tip)
    b.setCursor(Qt.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


def _menu_style(menu):
    return menu


def _nice(v):
    if v <= 0:
        return 1.0
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * e >= v:
            return m * e
    return 10 * e


def _fmt(v, dec=0):
    v = round(v, dec) + 0.0
    s = f"{v:,.{dec}f}".replace(",", " ").replace("-", "−")
    return s.replace(".", ",")


class Chart(QWidget):
    """Простой график: линии (x — числа) или сгруппированные столбцы (x — подписи)."""

    def __init__(self, kind="line", unit="Вт", title="", parent=None):
        super().__init__(parent)
        self.kind, self.unit, self.title = kind, unit, title
        self.series = []          # [(name, color, values)]
        self.xs, self.labels = [], []
        self.xmin, self.xmax = 0.0, 24.0
        self.hover = None
        self.p = _QT_THEMES["dark"]
        self.ydec = 0
        self.xfmt = "hour"
        self.markers = []        # [(x, подпись, цвет)]
        self.ymax_fixed = None
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def set_theme(self, p):
        self.p = p
        self.update()

    def set_data(self, series, xs=None, labels=None, xmin=None, xmax=None, ydec=0, markers=None):
        self.series = series
        self.markers = markers or []
        self.xs = xs or []
        self.labels = labels or []
        self.ydec = ydec
        if xmin is not None:
            self.xmin, self.xmax = xmin, xmax
        self.update()

    def _plot_rect(self):
        return QRectF(52, 54, max(10, self.width() - 64), max(10, self.height() - 84))

    def _ymax(self):
        if self.ymax_fixed:
            return self.ymax_fixed
        vals = [v for _, _, s in self.series for v in s]
        return _nice(max(vals) * 1.08) if vals and max(vals) > 0 else 1.0

    def paintEvent(self, e):
        p = self.p
        pa = QPainter(self)
        pa.setRenderHint(QPainter.Antialiasing)
        r = self._plot_rect()
        fnt = QFont("Segoe UI", 8)
        pa.setFont(fnt)
        fm = QFontMetrics(fnt)
        muted, line, text = QColor(p["muted"]), QColor(p["line"]), QColor(p["text"])
        # заголовок + легенда
        x = 8
        if self.title:
            f2 = QFont("Segoe UI", 9)
            f2.setBold(True)
            pa.setFont(f2)
            pa.setPen(text)
            pa.drawText(QPointF(x, 18), self.title)
            x += QFontMetrics(f2).horizontalAdvance(self.title) + 18
            pa.setFont(fnt)
        for name, col, _ in self.series:
            pa.setPen(Qt.NoPen)
            pa.setBrush(QColor(col))
            pa.drawRoundedRect(QRectF(x, 10, 10, 10), 3, 3)
            pa.setPen(muted)
            pa.drawText(QPointF(x + 14, 19), name)
            x += 14 + fm.horizontalAdvance(name) + 16
        ymax = self._ymax()
        # сетка
        for i in range(6):
            yv = ymax * i / 5
            yy = r.bottom() - r.height() * i / 5
            pa.setPen(QPen(line, 1, Qt.SolidLine if i == 0 else Qt.DotLine))
            pa.drawLine(QPointF(r.left(), yy), QPointF(r.right(), yy))
            pa.setPen(muted)
            lab = _fmt(yv, 1 if ymax < 5 else 0)
            pa.drawText(QRectF(0, yy - 8, r.left() - 6, 16), Qt.AlignRight | Qt.AlignVCenter, lab)
        pa.setPen(muted)
        pa.drawText(QRectF(0, r.top() - 28, r.left() - 6, 14), Qt.AlignRight | Qt.AlignVCenter, self.unit)
        if not self.series:
            pa.drawText(r, Qt.AlignCenter, "нет данных")
            return
        if self.kind == "line":
            span = max(1e-6, self.xmax - self.xmin)
            if self.xfmt == "deg":
                step = 10 if span > 40 else 5
            else:
                step = 1 if span <= 8 else 2 if span <= 16 else 3 if span <= 30 else 6 if span <= 80 else 12
            h = math.ceil(self.xmin)
            while h <= self.xmax:
                xx = r.left() + (h - self.xmin) / span * r.width()
                if int(h) % step == 0:
                    pa.setPen(muted)
                    lab = f"{int(h)}°" if self.xfmt == "deg" else f"{int(h) % 24}:00"
                    pa.drawText(QRectF(xx - 20, r.bottom() + 4, 40, 16), Qt.AlignCenter, lab)
                h += 1
            for name, col, vals in self.series:
                path = QPainterPath()
                fill = QPainterPath()
                started = False
                for xv, yv in zip(self.xs, vals):
                    if xv < self.xmin or xv > self.xmax:
                        continue
                    pt = QPointF(r.left() + (xv - self.xmin) / span * r.width(),
                                 r.bottom() - yv / ymax * r.height())
                    if not started:
                        path.moveTo(pt)
                        fill.moveTo(QPointF(pt.x(), r.bottom()))
                        fill.lineTo(pt)
                        started = True
                    else:
                        path.lineTo(pt)
                        fill.lineTo(pt)
                if started:
                    fill.lineTo(QPointF(path.currentPosition().x(), r.bottom()))
                    fill.closeSubpath()
                    fc = QColor(col)
                    fc.setAlpha(28)
                    pa.setPen(Qt.NoPen)
                    pa.setBrush(fc)
                    pa.drawPath(fill)
                    pa.setBrush(Qt.NoBrush)
                    pa.setPen(QPen(QColor(col), 2))
                    pa.drawPath(path)
            for mx, mlab, mcol in self.markers:
                if self.xmin <= mx <= self.xmax:
                    xx = r.left() + (mx - self.xmin) / span * r.width()
                    pa.setPen(QPen(QColor(mcol), 1.5, Qt.DashLine))
                    pa.drawLine(QPointF(xx, r.top()), QPointF(xx, r.bottom()))
                    pa.setPen(QColor(mcol))
                    pa.drawText(QPointF(xx + 4, r.top() + 12), mlab)
            if self.hover is not None and self.xs:
                xv = self.hover
                xx = r.left() + (xv - self.xmin) / span * r.width()
                pa.setPen(QPen(muted, 1, Qt.DashLine))
                pa.drawLine(QPointF(xx, r.top()), QPointF(xx, r.bottom()))
                idx = min(range(len(self.xs)), key=lambda i: abs(self.xs[i] - xv))
                hh = self.xs[idx]
                lines = [f"{hh:g}°" if self.xfmt == "deg" else
                         (f"день {int(hh // 24) + 1}, " if self.xmax > 25 else "") + fmt_t(hh)]
                lines += [f"{n}: {_fmt(v[idx], self.ydec)} {self.unit}" for n, _, v in self.series]
                self._tip_box(pa, xx, r, lines)
        else:
            n = len(self.labels)
            if n == 0:
                return
            gw = r.width() / n
            k = len(self.series)
            bw = min(16.0, gw * 0.8 / max(1, k))
            for i, lab in enumerate(self.labels):
                cx = r.left() + gw * (i + 0.5)
                pa.setPen(muted)
                pa.drawText(QRectF(cx - gw / 2, r.bottom() + 4, gw, 16), Qt.AlignCenter, lab)
                for j, (name, col, vals) in enumerate(self.series):
                    v = vals[i] if i < len(vals) else 0
                    hgt = v / ymax * r.height()
                    bx = cx - k * bw / 2 + j * bw
                    pa.setPen(Qt.NoPen)
                    c = QColor(col)
                    if self.hover is not None and self.hover != i:
                        c.setAlpha(150)
                    pa.setBrush(c)
                    pa.drawRoundedRect(QRectF(bx + 1, r.bottom() - hgt, bw - 2, hgt), 2.5, 2.5)
            if self.hover is not None and 0 <= self.hover < n:
                i = self.hover
                lines = [self.labels[i]] + [f"{nm}: {_fmt(v[i], self.ydec)} {self.unit}" for nm, _, v in self.series]
                self._tip_box(pa, r.left() + gw * (i + 0.5), r, lines)

    def _tip_box(self, pa, xx, r, lines):
        p = self.p
        fm = QFontMetrics(pa.font())
        w = max(fm.horizontalAdvance(s) for s in lines) + 16
        h = len(lines) * 16 + 8
        bx = xx + 10 if xx + 10 + w < r.right() else xx - 10 - w
        box = QRectF(bx, r.top() + 4, w, h)
        pa.setPen(QPen(QColor(p["accent"]), 1))
        pa.setBrush(QColor(p["panel2"]))
        pa.drawRoundedRect(box, 6, 6)
        pa.setPen(QColor(p["text"]))
        for i, s in enumerate(lines):
            pa.drawText(QPointF(bx + 8, r.top() + 20 + i * 16), s)

    def mouseMoveEvent(self, e):
        r = self._plot_rect()
        x = e.position().x()
        if not r.contains(e.position()):
            self.hover = None
        elif self.kind == "line":
            self.hover = self.xmin + (x - r.left()) / r.width() * (self.xmax - self.xmin)
        else:
            n = len(self.labels)
            self.hover = int((x - r.left()) / (r.width() / n)) if n else None
        self.update()

    def leaveEvent(self, e):
        self.hover = None
        self.update()

    def data_tsv(self):
        names = [n for n, _, _ in self.series]
        rows = []
        if self.kind == "line":
            rows.append("\t".join(["Время"] + names))
            for i, xv in enumerate(self.xs):
                if self.xmin <= xv <= self.xmax:
                    rows.append("\t".join([f"{int(xv):02d}:{int(round((xv % 1) * 60)) % 60:02d}"] +
                                          [f"{s[i]:.1f}".replace(".", ",") for _, _, s in self.series]))
        else:
            rows.append("\t".join([""] + names))
            for i, l in enumerate(self.labels):
                rows.append("\t".join([l] + [f"{s[i]:.2f}".replace(".", ",") for _, _, s in self.series]))
        return "\n".join(rows)

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction("📋 Копировать изображение", lambda: QGuiApplication.clipboard().setPixmap(self.grab()))
        m.addAction("📋 Копировать данные (для Excel)", lambda: QGuiApplication.clipboard().setText(self.data_tsv()))
        m.addSeparator()
        m.addAction("💾 Сохранить PNG…", self._save_png)
        m.exec(self.mapToGlobal(pos))

    def _save_png(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Сохранить график", str(APP_ROOT / "график.png"),
                                            "PNG (*.png)", options=QFileDialog.DontUseNativeDialog)
        if fn:
            self.grab().save(fn)
            log.info(f"✓ График сохранён: {fn}")


def make_table(headers, extra_actions=None):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setShowGrid(False)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(26)
    t.horizontalHeader().setStretchLastSection(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.setContextMenuPolicy(Qt.CustomContextMenu)
    t._extra = extra_actions or []

    def menu(pos):
        m = QMenu(t)
        row = t.rowAt(pos.y())
        for text, fn in t._extra:
            a = m.addAction(text, lambda fn=fn, row=row: fn(row))
            a.setEnabled(row >= 0)
        if t._extra:
            m.addSeparator()
        m.addAction("📋 Копировать строку", lambda: QGuiApplication.clipboard().setText(table_tsv(t, row)))
        m.addAction("📋 Копировать таблицу", lambda: QGuiApplication.clipboard().setText(table_tsv(t)))
        m.addAction("💾 Экспорт CSV…", lambda: export_table_csv(t))
        m.exec(t.viewport().mapToGlobal(pos))

    t.customContextMenuRequested.connect(menu)
    return t


def table_tsv(t, row=None):
    hdr = [t.horizontalHeaderItem(c).text() for c in range(t.columnCount())]
    rows = range(t.rowCount()) if row is None or row < 0 else [row]
    out = ["\t".join(hdr)] if row is None or row < 0 else []
    for r in rows:
        out.append("\t".join((t.item(r, c).text() if t.item(r, c) else "") for c in range(t.columnCount())))
    return "\n".join(out)


def export_table_csv(t):
    fn, _ = QFileDialog.getSaveFileName(t, "Экспорт CSV", str(APP_ROOT / "таблица.csv"), "CSV (*.csv)",
                                        options=QFileDialog.DontUseNativeDialog)
    if not fn:
        return
    with open(fn, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([t.horizontalHeaderItem(c).text() for c in range(t.columnCount())])
        for r in range(t.rowCount()):
            w.writerow([(t.item(r, c).text() if t.item(r, c) else "") for c in range(t.columnCount())])
    log.info(f"✓ CSV сохранён: {fn}")


def _item(text, align_right=False, color=None, bold=False):
    it = QTableWidgetItem(str(text))
    if align_right:
        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if color:
        it.setForeground(QColor(color))
    if bold:
        f = it.font()
        f.setBold(True)
        it.setFont(f)
    return it


# ──────────────────────────────── фоновые задачи ────────────────────────────────
class Worker(threading.Thread):
    """Очередь задач, выполняются по одной."""

    def __init__(self):
        super().__init__(daemon=True)
        self.jobs = queue.Queue()
        self.pending = set()
        self.start()

    def submit(self, name, fn, done):
        if name in self.pending:
            return False
        self.pending.add(name)
        self.jobs.put((name, fn, done))
        return True

    def run(self):
        while True:
            name, fn, done = self.jobs.get()
            UIQ.put(("busy", name))
            try:
                res = fn()
                UIQ.put(lambda r=res, d=done: d(r))
            except Exception as e:
                log.error(f"✗ {name}: {e}")
            finally:
                self.pending.discard(name)
                UIQ.put(_DONE)


# ──────────────────────────────── поля ввода ────────────────────────────────
# (ключ, подпись, тип, параметры, подсказка)
INPUT_CARDS = [
    ("Место и ориентация", [
        ("lat", "Широта", "num", (-70, 70, 0.1, 2, "°"), "Широта места, ° (Киев 50.45)"),
        ("lon", "Долгота", "num", (-180, 180, 0.1, 2, "°"), "Долгота места, ° (Киев 30.52)"),
        ("tilt", "Угол наклона", "num", (0, 90, 1, 0, "°"), "0° — лёжа, 90° — вертикально"),
        ("aspect", "Азимут", "num", (-180, 180, 5, 0, "°"), "0 — юг, −90 — восток, +90 — запад"),
        ("horizon", "Горизонт / тень", "num", (0, 30, 1, 0, "°"), "Ниже этой высоты солнца прямой свет закрыт (деревья, дома)"),
        ("tz", "Часовой пояс UTC+", "num", (-12, 14, 1, 0, "ч"), "Зимнее время. Для Украины 2"),
        ("dst", "Летнее время (+1 ч апр–окт)", "toggle", None, "Сдвиг часов летом"),
        ("overcast_k", "Пасмурный день", "num", (5, 80, 5, 0, "%"),
         "Какая доля от ясного неба доходит в пасмурный день (сплошная облачность 15–40%)"),
    ]),
    ("Панели", [
        ("p_preset", "Модель", "combo", PANEL_PRESETS, "Типовые панели — подставят паспорт, дальше правьте под свою"),
        ("pmax", "Pmax", "num", (5, 1000, 5, 0, "Вт"), "Мощность панели по паспорту (STC)"),
        ("vmp", "Vmp", "num", (1, 120, 0.1, 2, "В"), "Напряжение в точке макс. мощности"),
        ("imp", "Imp", "num", (0.1, 30, 0.05, 2, "А"), "Ток в точке макс. мощности"),
        ("voc", "Voc", "num", (1, 130, 0.1, 2, "В"), "Напряжение холостого хода"),
        ("isc", "Isc", "num", (0.1, 32, 0.05, 2, "А"), "Ток короткого замыкания"),
        ("gamma", "Темп. коэф. Pmax", "num", (-1, 0, 0.01, 2, "%/°C"), "Обычно −0.30…−0.45"),
        ("bvoc", "Темп. коэф. Voc", "num", (-1, 0, 0.01, 2, "%/°C"), "Обычно −0.25…−0.32"),
        ("noct", "NOCT", "num", (35, 60, 1, 0, "°C"), "Нагрев панели: при 800 Вт/м² и 20°C"),
        ("lowlight", "КПД при 200 Вт/м²", "num", (85, 100, 0.5, 1, "%"), "Относительный КПД на слабом свету (паспорт, обычно 95–98%)"),
    ]),
    ("Схема подключения", [
        ("ns", "Последовательно (S)", "num", (1, 30, 1, 0, "шт"), "Панелей в одной цепочке"),
        ("np", "Параллельно (P)", "num", (1, 20, 1, 0, "цеп."), "Цепочек параллельно"),
        ("mismatch", "Рассогласование", "num", (0, 15, 0.5, 1, "%"), "Разброс панелей, разные кабели цепочек"),
        ("soiling", "Грязь / пыль", "num", (0, 50, 0.5, 1, "%"), "Потери от загрязнения"),
        ("calib", "Поправка по факту", "num", (30, 130, 1, 0, "%"), "Подгоните, чтобы совпало с тем, что реально видите"),
    ]),
    ("Провода и соединения", [
        ("wire_mode", "Задавать провод", "seg", (("s", "Сечение"), ("d", "Диаметр")),
         "Сечение, мм² — как на маркировке. Диаметр — жилы по меди без изоляции (для многопроволочной — примерно)"),
        ("contact", "Качество контактов", "seg", CONTACT_ITEMS, "Отлично 0.3 мОм · Норма 1 · Средне 3 · Плохо 10 мОм на соединение"),
        ("_h1", "Панели → MPPT", "head", None, ""),
        ("wire_len", "Длина (в одну сторону)", "num", (0.5, 300, 0.5, 1, "м"), "От панелей до MPPT; считается туда и обратно"),
        ("wire_s", "Провод", "wire", None, "Одна жила"),
        ("wire_mat", "Материал", "seg", (("cu", "Медь"), ("al", "Алюминий")), "Алюминий ≈ в 1.6 раза хуже меди"),
        ("n_main", "Соединений в линии", "num", (0, 30, 1, 0, "шт"), "Клеммы автомата, предохранителя, MPPT, скрутки… (MC4 в цепочках считаются сами)"),
        ("_h2", "MPPT → АКБ", "head", None, ""),
        ("bw_len", "Длина (в одну сторону)", "num", (0.1, 50, 0.1, 1, "м"), "От контроллера до АКБ. Здесь ток большой — даже 1–2 м важны"),
        ("bw_s", "Провод", "wire", None, "Одна жила"),
        ("bw_mat", "Материал", "seg", (("cu", "Медь"), ("al", "Алюминий")), ""),
        ("_h3", "АКБ → инвертор", "head", None, ""),
        ("iw_len", "Длина (в одну сторону)", "num", (0.1, 50, 0.1, 1, "м"), "От АКБ до инвертора"),
        ("iw_s", "Провод", "wire", None, "Одна жила"),
        ("iw_mat", "Материал", "seg", (("cu", "Медь"), ("al", "Алюминий")), ""),
    ]),
    ("MPPT-контроллер", [
        ("m_preset", "Модель", "combo", MPPT_PRESETS, "Типовые контроллеры — правьте под свой"),
        ("v_max", "Макс. входное Voc", "num", (20, 1000, 5, 0, "В"), "Абсолютный предел по напряжению"),
        ("vmpp_min", "Мин. напряжение MPPT", "num", (0, 800, 5, 0, "В"), "Для гибридов (120 В и т.п.); 0 — считается от АКБ"),
        ("vmpp_max", "Макс. напряжение MPPT", "num", (10, 1000, 5, 0, "В"), "Верх окна слежения"),
        ("headroom", "Запас над АКБ", "num", (0, 15, 0.5, 1, "В"), "Понижающий MPPT работает, если Vвх > Vзаряда + запас"),
        ("iin_max", "Макс. входной ток", "num", (0, 200, 1, 0, "А"), "0 — без ограничения"),
        ("iout_max", "Макс. ток заряда", "num", (1, 300, 5, 0, "А"), "Номинал контроллера"),
        ("eta", "КПД пиковый", "num", (80, 99.5, 0.5, 1, "%"), "Китайские 94–96%, Victron 98%"),
        ("eta_k", "Потеря КПД на +1× Vвх/Vакб", "num", (0, 10, 0.5, 1, "%"), "Дешёвые понижающие MPPT теряют КПД при большом отношении напряжений"),
        ("own_w", "Собственное потребление", "num", (0, 50, 0.5, 1, "Вт"), "Съедает выработку на слабом свету"),
    ]),
    ("Аккумуляторы", [
        ("bat_preset", "Модель", "combo", BATTERY_PRESETS, "Типовые АКБ — правьте под свои"),
        ("bat_v", "Напряжение системы", "seg", (("12", "12 В"), ("24", "24 В"), ("48", "48 В")), "Номинал банка / инвертора"),
        ("chem", "Тип", "seg", (("lfp", "LiFePO4"), ("lead", "Свинец")), "Определяет напряжение заряда и КПД"),
        ("bat_unit_v", "Напряжение одной АКБ", "num", (2, 60, 0.1, 1, "В"), "12.8 — LiFePO4 «12 В», 12 — свинец, 3.2 — ячейка, 51.2 — стойка"),
        ("bat_ah", "Ёмкость одной АКБ", "num", (5, 1000, 5, 0, "А·ч"), "По паспорту"),
        ("bat_count", "Количество", "num", (0, 64, 1, 0, "шт"), "Всего штук; сборка S×P посчитается сама"),
        ("bat_dod", "Глубина разряда", "num", (20, 100, 5, 0, "%"), "Сколько ёмкости реально используете: LiFePO4 80–90%, свинец ≤ 50%"),
        ("bat_c", "Макс. ток заряда", "num", (0.05, 1.0, 0.05, 2, "C"), "Доля от ёмкости: LiFePO4 0.5C, AGM 0.2C, гель 0.15C"),
        ("t_bat", "Температура в помещении АКБ", "num", (-30, 45, 1, 0, "°C"), "Холод снижает ёмкость; LiFePO4 нельзя заряжать ниже 0°C"),
        ("bat_ch", "Напряжение заряда", "num", (5, 70, 0.1, 1, "В"), "Ставится по типу АКБ, можно править"),
        ("eta_bat", "КПД АКБ", "num", (60, 100, 1, 0, "%"), "LiFePO4 ~97%, свинец ~85%"),
    ]),
    ("Инвертор и потребление дома", [
        ("inv_preset", "Модель", "combo", INVERTER_PRESETS, "Типовые инверторы — главное отличие в холостом ходе"),
        ("inv_p", "Мощность", "num", (200, 30000, 100, 0, "Вт"), "Номинал инвертора"),
        ("inv_eta", "КПД", "num", (70, 99, 1, 0, "%"), "Средний КПД преобразования в 230 В"),
        ("inv_idle", "Холостой ход", "num", (0, 300, 1, 0, "Вт"),
         "Паспорт: «No-load consumption». Китайские гибриды 30–80 Вт, с режимом экономии 5–15 Вт. Съедает ×24 ч"),
        ("inv_hours", "Работает в сутки", "num", (0, 24, 1, 0, "ч"), "24 — включён всегда"),
        ("load_mode", "Потребление дома", "seg", (("m", "за месяц"), ("y", "за год")), "Как удобнее ввести — по счётчику"),
        ("load_kwh", "Сколько", "num", (0, 60000, 10, 0, "кВт·ч"), "Сколько дом берёт на 230 В за месяц / за год"),
        ("load_winter", "Зимой больше на", "num", (0, 100, 5, 0, "%"), "Свет, обогрев: январь +X%, июль −X% от среднего"),
        ("load_profile", "Когда потребляет", "combo", LOAD_PROFILES, "Распределение потребления по часам суток"),
    ]),
    ("Сеть и тариф", [
        ("grid_mode", "Горсеть", "seg", (("backup", "Есть"), ("off", "Нет / отключают")),
         "Есть — когда АКБ разрядилась, дом переходит на сеть. Нет — дом обесточивается"),
        ("back_soc", "Вернуться на АКБ при заряде", "num", (10, 100, 5, 0, "%"),
         "Режим SBU гибрида: обратно с сети на АКБ, когда солнце дозарядило АКБ до этого уровня"),
        ("tariff", "Тариф", "num", (0, 30, 0.01, 2, "грн/кВт·ч"), "Для населения 4,32 грн/кВт·ч (проверьте свой)"),
    ]),
    ("Пределы температур", [
        ("t_min", "Мин. температура", "num", (-50, 10, 1, 0, "°C"), "Для проверки Voc на морозе"),
        ("t_max", "Макс. температура воздуха", "num", (15, 55, 1, 0, "°C"), "Для проверки Vmp в жару"),
    ]),
]
PANEL_KEYS = ("pmax", "vmp", "imp", "voc", "isc", "gamma", "bvoc", "noct", "lowlight")
MPPT_KEYS = ("v_max", "vmpp_min", "vmpp_max", "iin_max", "iout_max", "eta", "eta_k", "own_w", "headroom")
INT_KEYS = ("ns", "np", "n_main", "month", "bat_count", "inv_hours")
BAT_KEYS = ("chem", "bat_unit_v", "bat_ah", "bat_c", "bat_dod")
INV_KEYS = ("inv_p", "inv_eta", "inv_idle")
WIRE_S_KEYS = ("wire_s", "bw_s", "iw_s")
WIRE_RANGE = {"s": (1, 240, 0.5, 1, "мм²"), "d": (1.0, 17.5, 0.1, 2, "мм ⌀")}
PRESET_GROUPS = (("p_preset", PANEL_PRESETS, PANEL_KEYS), ("m_preset", MPPT_PRESETS, MPPT_KEYS),
                 ("bat_preset", BATTERY_PRESETS, BAT_KEYS), ("inv_preset", INVERTER_PRESETS, INV_KEYS))


def s2d(sec):
    return math.sqrt(4 * max(0.01, float(sec)) / math.pi)


def d2s(d):
    return math.pi * float(d) ** 2 / 4


# ═══════════════════════════════ ГЛАВНОЕ ОКНО ═══════════════════════════════
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.s = self.cfg["sys"]
        self.sd = SunData(self.cfg)
        self.R = None
        self.gen = 0
        self.page_gen = {}
        self.w = {}
        self.toggles = []
        self.charts = []
        self.worker = Worker()
        self.setWindowTitle(f"{APP_NAME} — v{VERSION} · Qt6")
        self.resize(1380, 900)
        self.setMinimumSize(980, 640)
        self._build()
        self._load_fields()
        self._apply_theme()
        try:
            if self.cfg.get("geometry"):
                self.restoreGeometry(QByteArray(base64.b64decode(self.cfg["geometry"])))
        except Exception:
            pass
        self._recalc_timer = QTimer(self)
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.timeout.connect(self.recalc)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_log)
        self._timer.start(150)
        log.info(f"✓ {APP_NAME} v{VERSION} запущен")
        self.recalc()

    # ─────────────── каркас ───────────────
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        side = QFrame()
        side.setObjectName("side")
        side.setFixedWidth(62)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(7, 10, 7, 10)
        sv.setSpacing(6)
        self.stack = QStackedWidget()
        self.side_group = QButtonGroup(self)
        self.month_combos, self.weather_segs = [], []
        pages = [("📊", "Прогноз выработки", "forecast", self._page_forecast()),
                 ("🏠", "Покрытие дома: хватит ли станции", "home", self._page_home()),
                 ("🔌", "Когда переходить на горсеть", "grid", self._page_grid()),
                 ("⚙", "Настройки станции", "settings", self._page_settings()),
                 ("🔀", "Сравнение схем S×P", "schemes", self._page_schemes()),
                 ("📐", "Подбор угла и азимута", "tilt", self._page_tilt()),
                 ("🧵", "Подбор сечения провода", "wire", self._page_wire()),
                 ("🌐", "Данные солнца (PVGIS)", "data", self._page_data()),
                 ("🎨", "Цвета", "colors", self._page_colors())]
        self.page_names = [p[2] for p in pages]
        self.page_idx = {n: i for i, n in enumerate(self.page_names)}
        for i, (ico, tip, _name, page) in enumerate(pages):
            b = QToolButton()
            b.setText(ico)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setFixedSize(48, 46)
            b.setCursor(Qt.PointingHandCursor)
            self.side_group.addButton(b, i)
            if i == len(pages) - 1:
                sv.addStretch(1)
            if i == 4:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setObjectName("sideSep")
                sv.addWidget(sep)
            sv.addWidget(b)
            self.stack.addWidget(page)
        self.side_group.button(0).setChecked(True)
        self.side_group.idClicked.connect(self._go_page)
        h.addWidget(side)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.vsplit = QSplitter(Qt.Vertical)
        self.vsplit.addWidget(self.stack)
        self.vsplit.addWidget(self._log_card())
        self.vsplit.setStretchFactor(0, 1)
        self.vsplit.setSizes([780, 110])
        self.vsplit.setCollapsible(0, False)
        right.addWidget(self.vsplit, 1)
        sb = QFrame()
        sb.setObjectName("statusbar")
        sb.setFixedHeight(30)
        sh = QHBoxLayout(sb)
        sh.setContentsMargins(10, 0, 12, 0)
        self.pill = _lab("● готов", "pill")
        self.src_lab = _lab("", "muted")
        self.status_lab = _lab("", "muted")
        sh.addWidget(self.pill)
        sh.addSpacing(10)
        sh.addWidget(self.src_lab)
        sh.addStretch(1)
        sh.addWidget(self.status_lab)
        right.addWidget(sb)
        h.addLayout(right, 1)

    def _page(self):
        pg = QWidget()
        pg.setObjectName("page")
        v = QVBoxLayout(pg)
        v.setContentsMargins(16, 16, 16, 12)
        v.setSpacing(12)
        return pg, v

    def _scroll(self, inner):
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        inner.setObjectName("scrollInner")
        sa.setWidget(inner)
        return sa

    # ─────────────── общие куски страниц ───────────────
    def _mw_bar(self, title, extra=None):
        hdr = QHBoxLayout()
        hdr.addWidget(_lab(title, "bigTitle"))
        hdr.addSpacing(12)
        cb = NoWheelCombo()
        cb.addItems(MONTHS)
        cb.setToolTip("Месяц")
        cb.currentIndexChanged.connect(lambda i: self._on_field("month", i))
        self.month_combos.append(cb)
        hdr.addWidget(cb)
        seg = Segmented(WEATHER)
        seg.setToolTip("Погода")
        seg.changed.connect(lambda k: self._on_field("weather", k))
        self.weather_segs.append(seg)
        hdr.addWidget(seg)
        hdr.addStretch(1)
        for w in extra or []:
            hdr.addWidget(w)
        return hdr

    def _sync_mw(self):
        for cb in self.month_combos:
            cb.blockSignals(True)
            cb.setCurrentIndex(int(self.s["month"]))
            cb.blockSignals(False)
        for sg in self.weather_segs:
            sg.setValue(self.s["weather"])

    def _kpi_grid(self, items, cols=3):
        kp = QGridLayout()
        kp.setSpacing(10)
        for i, (k, cap) in enumerate(items):
            fr = QFrame()
            fr.setObjectName("kpi")
            fv = QVBoxLayout(fr)
            fv.setContentsMargins(12, 8, 12, 8)
            fv.setSpacing(0)
            val = _lab("—", "kpiVal")
            sub = _lab(cap, "kpiCap", True)
            fv.addWidget(val)
            fv.addWidget(sub)
            self.kpi[k] = (val, sub)
            kp.addWidget(fr, i // cols, i % cols)
        return kp

    def _results_scroll(self, inner):
        sa = self._scroll(inner)
        inner.setContextMenuPolicy(Qt.CustomContextMenu)
        inner.customContextMenuRequested.connect(lambda pos: self._results_menu(inner.mapToGlobal(pos)))
        return sa

    def _rich(self):
        l = QLabel()
        l.setTextFormat(Qt.RichText)
        l.setWordWrap(True)
        l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return l

    # ─────────────── страница: настройки ───────────────
    def _input_card(self, title, fields):
        fr, v = _card(title)
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(7)
        g.setColumnStretch(1, 1)
        for row, (key, label, kind, opt, tip) in enumerate(fields):
            if kind == "head":
                g.addWidget(_lab(label, "subHead"), row, 0, 1, 2)
                continue
            wdg = self._make_field(key, kind, opt)
            wdg.setToolTip(tip)
            l = _lab(label, "fieldLab", True)
            l.setMaximumWidth(150)
            l.setToolTip(tip)
            g.addWidget(l, row, 0)
            g.addWidget(wdg, row, 1)
        v.addLayout(g)
        if title == "Схема подключения":
            self.lab_total = _lab("", "hint", True)
            v.addWidget(self.lab_total)
        elif title == "Провода и соединения":
            self.lab_wire = _lab("", "hint", True)
            v.addWidget(self.lab_wire)
        elif title == "Аккумуляторы":
            self.lab_bank = _lab("", "hint", True)
            self.lab_bank.setTextFormat(Qt.RichText)
            v.addWidget(self.lab_bank)
        return fr

    SETTINGS_COLS = {"Место и ориентация": 0, "Панели": 0, "Схема подключения": 0,
                     "Провода и соединения": 1, "MPPT-контроллер": 1, "Пределы температур": 1,
                     "Аккумуляторы": 2, "Инвертор и потребление дома": 2, "Сеть и тариф": 2}

    def _page_settings(self):
        inner = QWidget()
        iv = QVBoxLayout(inner)
        iv.setContentsMargins(16, 16, 16, 16)
        iv.setSpacing(12)
        top = QHBoxLayout()
        top.addWidget(_lab("Настройки станции", "bigTitle"))
        top.addSpacing(14)
        self.chk_summary = self._rich()
        self.chk_summary.setWordWrap(False)
        top.addWidget(self.chk_summary)
        top.addStretch(1)
        top.addWidget(_btn("📂 Открыть", "chip", "Открыть профиль станции", self.load_profile))
        top.addWidget(_btn("💾 Сохранить", "chip", "Сохранить профиль станции", self.save_profile))
        top.addWidget(_btn("↺ По умолчанию", "chip", "Сбросить все параметры", self.reset_defaults))
        iv.addLayout(top)
        iv.addWidget(_lab("Все параметры здесь. Результаты — на страницах 📊 Прогноз, 🏠 Покрытие дома, 🔌 Горсеть; "
                          "пересчёт сразу при изменении. Наведите на поле — подсказка.", "hint", True))
        row = QHBoxLayout()
        row.setSpacing(12)
        cols = [QVBoxLayout() for _ in range(3)]
        for c in cols:
            c.setSpacing(12)
        for title, fields in INPUT_CARDS:
            cols[self.SETTINGS_COLS.get(title, 2)].addWidget(self._input_card(title, fields))
        for c in cols:
            c.addStretch(1)
            box = QWidget()
            box.setLayout(c)
            box.setMinimumWidth(330)
            row.addWidget(box, 1)
        iv.addLayout(row)
        iv.addStretch(1)
        sa = self._scroll(inner)
        inner.setContextMenuPolicy(Qt.CustomContextMenu)
        inner.customContextMenuRequested.connect(lambda pos: self._inputs_menu(inner.mapToGlobal(pos)))
        return sa

    # ─────────────── страница: прогноз ───────────────
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

    # ─────────────── страница: покрытие дома ───────────────
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

    # ─────────────── страница: горсеть ───────────────
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

    def _make_field(self, key, kind, opt):
        if kind == "wire":
            kind, opt = "num", WIRE_RANGE[self.s.get("wire_mode", "s")]
        if kind == "num":
            lo, hi, step, dec, suf = opt
            wdg = Stepper(lo, hi, step, dec, suf)
            wdg.changed.connect(lambda v, k=key: self._on_field(k, v))
        elif kind == "seg":
            wdg = Segmented(opt)
            wdg.changed.connect(lambda v, k=key: self._on_field(k, v))
        elif kind == "toggle":
            wdg = Toggle()
            self.toggles.append(wdg)
            wdg.toggled.connect(lambda v, k=key: self._on_field(k, bool(v)))
            box = QWidget()
            bl = QHBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.addWidget(wdg)
            bl.addStretch(1)
            self.w[key] = wdg
            return box
        else:
            wdg = NoWheelCombo()
            for k, (t, _) in opt.items():
                wdg.addItem(t, k)
            wdg.currentIndexChanged.connect(lambda i, k=key, wd=wdg: self._on_field(k, wd.itemData(i)))
        self.w[key] = wdg
        return wdg

    def _set_widget(self, key, val):
        wdg = self.w.get(key)
        if wdg is None:
            return
        wdg.blockSignals(True)
        try:
            if isinstance(wdg, Stepper):
                if key in WIRE_S_KEYS and self.s.get("wire_mode") == "d":
                    val = s2d(val)
                wdg.setValue(val)
            elif isinstance(wdg, Segmented):
                wdg.setValue(str(val))
            elif isinstance(wdg, Toggle):
                wdg.setChecked(bool(val))
            elif isinstance(wdg, QComboBox):
                i = wdg.findData(val)
                wdg.setCurrentIndex(i if i >= 0 else 0)
        finally:
            wdg.blockSignals(False)

    def _load_fields(self):
        for k in WIRE_S_KEYS:
            self.w[k].reconfigure(*WIRE_RANGE[self.s.get("wire_mode", "s")])
        for k in self.w:
            if k in self.s:
                self._set_widget(k, self.s[k])
        self._sync_mw()
        self.st_ser_days.setValue(self.s["ser_days"])
        self.seg_ser_w.setValue(self.s["ser_weather"])
        self.st_ser_soc.setValue(self.s["ser_soc0"])
        self.st_g.setValue(self.s["pt_g"])
        self.st_t.setValue(self.s["pt_t"])

    def _on_field(self, key, val):
        if key in INT_KEYS:
            val = int(round(val))
        if key in WIRE_S_KEYS and self.s.get("wire_mode") == "d":
            val = round(d2s(val), 2)
        if key == "load_mode" and val != self.s.get("load_mode"):
            k = 12.0 if val == "y" else 1 / 12.0
            self.s["load_kwh"] = round(float(self.s["load_kwh"]) * k)
            self._set_widget("load_kwh", self.s["load_kwh"])
        self.s[key] = val
        if key == "wire_mode":
            for k in WIRE_S_KEYS:
                self.w[k].reconfigure(*WIRE_RANGE[val])
                self._set_widget(k, self.s[k])
        for pkey, presets, keys in PRESET_GROUPS:
            if key == pkey:
                pr = presets.get(val, (None, None))[1]
                if pr:
                    for k, v in pr.items():
                        self.s[k] = v
                        self._set_widget(k, v)
                    if pkey == "bat_preset":
                        self._bat_auto()
            elif key in keys and self.s.get(pkey) != "custom":
                pr = presets.get(self.s[pkey], (None, None))[1]
                if pr and key in pr:
                    a = pr[key]
                    diff = (a != val) if isinstance(a, str) else abs(float(a) - float(val)) > 1e-9
                    if diff:
                        self.s[pkey] = "custom"
                        self._set_widget(pkey, "custom")
        if key in ("bat_v", "chem"):
            self._bat_auto()
        if key in ("pt_g", "pt_t"):
            self._update_point()
            return
        if key in ("month", "weather"):
            self._sync_mw()
            if self.R is not None:
                self._show_results()
            return
        if key in ("ser_days", "ser_weather", "ser_soc0"):
            if self.R is not None:
                self._show_series()
            return
        self._recalc_timer.start(200)

    def _bat_auto(self):
        n = int(self.s["bat_v"]) / 12
        self.s["bat_ch"] = round((14.2 if self.s["chem"] == "lfp" else 14.4) * n, 1)
        self.s["eta_bat"] = 97 if self.s["chem"] == "lfp" else 85
        self._set_widget("bat_ch", self.s["bat_ch"])
        self._set_widget("eta_bat", self.s["eta_bat"])

    # ─────────────── пересчёт ───────────────
    def recalc(self):
        self.gen += 1
        self.sd = SunData(self.cfg)
        t0 = time.perf_counter()
        try:
            self.R = compute_all(dict(self.s), self.sd)
        except Exception as e:
            log.error(f"✗ Ошибка расчёта: {e}")
            return
        dt = (time.perf_counter() - t0) * 1000
        self._show_results()
        self._status(f"расчёт {dt:.0f} мс")
        cur = self.page_names[self.stack.currentIndex()]
        if cur in ("schemes", "tilt", "wire"):
            self._refresh_page(cur)
        elif cur == "data":
            self._fill_data_table()

    def _show_results(self):
        R = self.R
        s = self.s
        res, c = R["res"], R["ctx"]
        m = int(s["month"])
        wsel = s["weather"]
        self.src_lab.setText("Солнце: " + self.sd.label(float(s["lat"]), float(s["lon"])))
        pk = c["pstc_tot"]
        self.lab_total.setText(f"Поле: {c['npan']} панелей × {c['pmax']:.0f} Вт = {pk / 1000:.2f} кВт · "
                               f"цепочка Vmp {c['ns'] * c['vmp']:.1f} В / Voc {c['ns'] * c['voc']:.1f} В · "
                               f"ток {c['np'] * c['imp']:.1f} А")
        for w in W_KEYS:
            d = res[(m, w)]
            val, sub = self.kpi[w]
            val.setText(f"{_fmt(d['wh'][8] / 1000, 2)} кВт·ч")
            sub.setText(f"{dict(WEATHER)[w]} · {MONTHS[m].lower()} · пик {_fmt(d['peak'])} Вт")
        dclear = res[(m, "clear")]
        self.kpi["peak"][0].setText(f"{_fmt(dclear['peak'])} Вт")
        self.kpi["peak"][1].setText(f"Пик (ясно, {MONTHS_S[m]}) · ток заряда {dclear['peak_i']:.1f} А")
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
        self.lab_bank.setText(
            f"Сборка: {c['nser']} послед. × {c['npar']} паралл. = {c['bank_v']:.1f} В, {c['bank_ah']:.0f} А·ч, "
            f"{c['bank_wh'] / 1000:.1f} кВт·ч (полезно {c['usable_wh'] / 1000:.1f}) · ток заряда до {c['bank_ich']:.0f} А"
            + (f" · ⚠ лишние {c['extra']} шт" if c["extra"] else "") + self._cell_info(c))
        self.lab_wire.setText(
            f"Сопротивление линий с контактами: панели→MPPT {wire_r(c, 20) * 1000:.0f} мОм · MPPT→АКБ {c['rb'] * 1000:.1f} мОм · "
            f"АКБ→инвертор {c['ri'] * 1000:.1f} мОм. Сечения: "
            + " · ".join(f"{float(s[k]):g} мм² = ⌀{s2d(s[k]):.1f} мм" for k in WIRE_S_KEYS))
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
            loss = dw[a] - dw[b]
            pct = loss / pot * 100 if pot > 0 else 0
            if abs(loss) < 0.5:
                loss, pct = 0.0, 0.0
            col = _ERR if pct >= 5 else _WARN if pct >= 2 else _OK if pct < -0.05 else None
            sign = "+" if pct < -0.05 else "−" if pct > 0.05 else ""
            add(("  + " if sign == "+" else "  − ") + name, -loss + 0.0, f"{sign}{abs(pct):.1f} %", col)
        out = dw[8]
        add("= В АКБ (на клеммах)", out, f"{out / pot * 100:.1f} %" if pot else "—", _OK, True)
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

    # ─────────────── покрытие дома ───────────────
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
                n = math.ceil(night / unit / c["nser"]) * c["nser"]
                adv.append(f"🔋 Чтобы в солнечные месяцы пережить вечер и ночь без сети, полезная ёмкость нужна ≈<b>{night / 1000:.1f} кВт·ч</b> "
                           f"(у вас {c['usable_wh'] / 1000:.1f}) → ≈<b>{n} шт</b> выбранных АКБ.")
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

    # ─────────────── горсеть ───────────────
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
        inf = CELL_INFO.get(self.s.get("bat_preset"))
        if not inf:
            return ""
        cyc, kg, dims, ir = inf
        n = int(self.s["bat_count"])
        txt = f"<br>Ресурс ≈{cyc} циклов (паспорт, 25°C)"
        if kg:
            txt += f" · {kg:g} кг/шт → {kg * n:.0f} кг · {dims} мм · R {ir} мОм"
        return txt

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
            note += f"<br><span style='color:{_WARN}'>⚠ Упор в ток заряда: −{_fmt(conv - out0)} Вт</span>"
        self.pt_lab.setText(
            f"<table cellspacing=3>"
            f"<tr><td style='color:{mute}'>Панели нагреты до</td><td align=right><b>{tc:.0f} °C</b></td></tr>"
            f"<tr><td style='color:{mute}'>Поле выдаёт</td><td align=right><b>{_fmt(arr)} Вт</b> ({vp:.1f} В × {I:.2f} А)</td></tr>"
            f"<tr><td style='color:{mute}'>Падение на проводе</td><td align=right><b>{du:.2f} В</b> ({dup:.2f} %) · {_fmt(arr - pin)} Вт</td></tr>"
            f"<tr><td style='color:{mute}'>На входе MPPT</td><td align=right><b>{_fmt(pin)} Вт</b> при {vin:.1f} В</td></tr>"
            f"<tr><td style='color:{mute}'>Провод MPPT→АКБ</td><td align=right><b>{_fmt(out0 - out)} Вт</b> · {out0 / c['vbat'] * c['rb']:.2f} В</td></tr>"
            f"<tr><td style='color:{mute}'>В АКБ</td><td align=right><b style='color:{_OK}'>{_fmt(out)} Вт</b> · {out0 / c['vbat']:.1f} А</td></tr>"
            f"<tr><td style='color:{mute}'>От паспорта поля</td><td align=right><b>{out / c['pstc_tot'] * 100:.1f} %</b></td></tr>"
            f"</table>{note}")

    # ─────────────── страница: схемы ───────────────
    def _page_schemes(self):
        pg, v = self._page()
        top = QHBoxLayout()
        top.addWidget(_lab("Сравнение схем при том же числе панелей", "bigTitle"))
        top.addStretch(1)
        top.addWidget(_btn("🔄 Пересчитать", "primary", "Пересчитать таблицу", lambda: self._refresh_page("schemes", force=True)))
        v.addLayout(top)
        v.addWidget(_lab("Все варианты S×P для вашего числа панелей: ясный / средний / пасмурный день выбранного месяца и год. "
                         "Лучший вариант в каждом столбце — зелёный. Частичную тень модель не учитывает: при тени "
                         "длинные цепочки теряют больше.", "hint", True))
        fr, cv = _card("Варианты")
        self.tb_sch = make_table(["Схема", "Vmp, В", "Ток, А", "Voc мороз, В", "Провод, %", "Ясно, Вт·ч",
                                  "Средне, Вт·ч", "Пасмурно, Вт·ч", "Год, кВт·ч", "Проверки"],
                                 [("✔ Применить эту схему", self._apply_scheme)])
        cv.addWidget(self.tb_sch)
        v.addWidget(fr, 1)
        return pg

    def _apply_scheme(self, row):
        it = self.tb_sch.item(row, 0)
        if not it:
            return
        ns, np_ = it.data(Qt.UserRole)
        self.s["ns"], self.s["np"] = ns, np_
        self._set_widget("ns", ns)
        self._set_widget("np", np_)
        log.info(f"✓ Схема {ns}S{np_}P применена")
        self.recalc()

    def _job_schemes(self, s, sd):
        n = int(s["ns"]) * int(s["np"])
        m = int(s["month"])
        rows = []
        for ns in range(1, n + 1):
            if n % ns:
                continue
            np_ = n // ns
            s2 = dict(s, ns=ns, np=np_)
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
            rows.append(dict(ns=ns, np=np_, vmp=ns * c["vmp"], i=istc,
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
            cur = r["ns"] == int(self.s["ns"]) and r["np"] == int(self.s["np"])
            it = _item(f"{r['ns']}S{r['np']}P" + ("  ← сейчас" if cur else ""), bold=cur)
            it.setData(Qt.UserRole, (r["ns"], r["np"]))
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

    # ─────────────── страница: угол ───────────────
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

    # ─────────────── страница: провод ───────────────
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
        name, kl, ks, km, secs, ok_lim, warn_lim = self.WIRE_SEGS[seg]
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
                R, I, V = c["rb"], c["ilim"], c["vbat"]
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

    # ─────────────── страница: данные ───────────────
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
        fr, cv = _card("Помесячно: горизонтальная облучённость и температура")
        top = QHBoxLayout()
        top.addWidget(_lab("Встроенные значения можно править двойным щелчком.", "hint"))
        top.addStretch(1)
        top.addWidget(_btn("♻ Встроенные по умолчанию", "chip", "Вернуть значения ≈Киев", self.reset_builtin))
        cv.addLayout(top)
        self.tb_data = make_table(["Месяц", "Встроенные, кВт·ч/м²·день", "Встроенные, °C", "PVGIS, кВт·ч/м²·день",
                                   "PVGIS, °C", "Сдвиг времени PVGIS, ч"])
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
                             (5, f"{pv['months'][m].get('shift', 0):+.2f}" if pv else "—")):
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

    def _data_edited(self, it):
        r, c = it.row(), it.column()
        if c not in (1, 2):
            return
        try:
            val = float(it.text().replace(",", ".").strip())
        except ValueError:
            log.warning(f"⚠ Не число: «{it.text()}»")
            self._fill_data_table()
            return
        self.cfg["builtin"][r][c - 1] = val
        save_config(self.cfg)
        log.info(f"✓ {MONTHS[r]}: встроенное значение изменено на {val}")
        self.recalc()

    def reset_builtin(self):
        if QMessageBox.question(self, APP_NAME, "Вернуть встроенные значения (≈Киев)?") != QMessageBox.Yes:
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
        if QMessageBox.question(self, APP_NAME, "Удалить загруженные данные PVGIS?") != QMessageBox.Yes:
            return
        self.cfg["pvgis"] = None
        save_config(self.cfg)
        log.info("🗑 Данные PVGIS удалены")
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

    # ─────────────── страница: цвета ───────────────
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
            f"{APP_NAME} v{VERSION}\n\nМодель: положение солнца → ясное небо (Haurwitz) / средний день (встроенные или PVGIS) → "
            "разделение на прямую и рассеянную (Erbs) → плоскость панелей (изотропная модель, отражение земли, потери на угле падения) → "
            "нагрев панелей (NOCT) → температурный коэффициент и КПД на слабом свету → схема S×P и рассогласование → "
            "провод (ρ с учётом температуры) и контакты (MC4 в цепочках + клеммы общей линии) → окно MPPT и лимит входного тока → "
            "КПД MPPT (зависит от Vвх/Vакб) и собственное потребление → лимит тока заряда → АКБ → инвертор.\n\n"
            "Не учитывается: частичная тень по панелям, снег на панелях, полный заряд АКБ (контроллер сбрасывает ток), "
            "деградация панелей. Для подгонки под реальность — «Поправка по факту».", "hint", True))
        v.addWidget(fr)
        v.addStretch(1)
        return pg

    def _set_theme(self, k):
        self.cfg["theme"] = k
        self._apply_theme()
        if self.R is not None:
            self._show_results()

    def _p(self):
        return _QT_THEMES.get(self.cfg.get("theme", "dark"), _QT_THEMES["dark"])

    def _apply_theme(self):
        p = self._p()
        app = QApplication.instance()
        app.setStyleSheet(_qss(p))
        off = "#454b59" if self.cfg.get("theme", "dark") == "dark" else "#c3c8d2"
        for t in self.toggles:
            t.set_theme(p["accent"], off, p["text"])
        for c in self.charts:
            c.set_theme(p)

    # ─────────────── лог ───────────────
    def _log_card(self):
        fr, v = _card("Лог")
        v.setContentsMargins(14, 8, 14, 8)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_view.customContextMenuRequested.connect(self._log_menu)
        v.addWidget(self.log_view)
        return fr

    def _log_menu(self, pos):
        lv = self.log_view
        m = QMenu(self)
        a = m.addAction("📋 Копировать", lv.copy)
        a.setEnabled(lv.textCursor().hasSelection())
        m.addAction("📋 Копировать всё", lambda: QGuiApplication.clipboard().setText(lv.toPlainText()))
        m.addAction("Выделить всё", lv.selectAll)
        m.addSeparator()
        m.addAction("💾 Сохранить в файл…", self._save_log)
        m.addAction("🗑 Очистить", lv.clear)
        m.exec(lv.mapToGlobal(pos))

    def _save_log(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Сохранить лог", str(APP_ROOT / "лог.txt"), "Текст (*.txt)",
                                            options=QFileDialog.DontUseNativeDialog)
        if fn:
            Path(fn).write_text(self.log_view.toPlainText(), encoding="utf-8")

    def _append_log(self, level, text):
        lv = self.log_view
        sb = lv.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        col = None
        if "✗" in text or "⛔" in text or level >= logging.ERROR:
            col = _ERR
        elif "⚠" in text or level >= logging.WARNING:
            col = _WARN
        elif "✓" in text or "✅" in text:
            col = _OK
        esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lv.appendHtml(f"<span style='color:{col}'>{esc}</span>" if col else esc)
        if at_bottom:
            sb.setValue(sb.maximum())

    def _drain_log(self):
        for _ in range(200):
            try:
                item = UIQ.get_nowait()
            except queue.Empty:
                break
            if item is _DONE:
                if self.worker.jobs.empty() and not self.worker.pending:
                    self.pill.setText("● готов")
                    self.btn_pv.setEnabled(True)
            elif callable(item):
                try:
                    item()
                except Exception as e:
                    log.error(f"✗ Ошибка интерфейса: {e}")
            elif isinstance(item, tuple) and item[0] == "log":
                self._append_log(item[1], item[2])
            elif isinstance(item, tuple) and item[0] == "busy":
                self.pill.setText(f"● {item[1]}…")

    def _status(self, text):
        self.status_lab.setText(text)

    # ─────────────── фоновые страницы ───────────────
    def _go_page(self, i):
        self.stack.setCurrentIndex(i)
        name = self.page_names[i]
        if name in ("schemes", "tilt", "wire"):
            self._refresh_page(name)
        elif name == "data":
            self._fill_data_table()

    def _refresh_page(self, i, force=False):
        if not force and self.page_gen.get(i) == self.gen:
            return
        s, sd, gen = dict(self.s), self.sd, self.gen
        name, job, fill = {"schemes": ("сравнение схем", self._job_schemes, self._fill_schemes),
                           "tilt": ("подбор угла", self._job_tilt, self._fill_tilt),
                           "wire": ("подбор провода", self._job_wire, self._fill_wire)}[i]

        def done(res):
            fill(res)
            self.page_gen[i] = gen
            if gen != self.gen and self.page_names[self.stack.currentIndex()] == i:
                QTimer.singleShot(0, lambda: self._refresh_page(i))

        extra = (self.seg_wire.value(),) if i == "wire" else ()
        self.worker.submit(name, lambda: job(s, sd, *extra), done)

    # ─────────────── профили, отчёт ───────────────
    def _inputs_menu(self, gpos):
        m = QMenu(self)
        m.addAction("📂 Открыть профиль…", self.load_profile)
        m.addAction("💾 Сохранить профиль…", self.save_profile)
        m.addAction("📋 Копировать параметры (JSON)",
                    lambda: QGuiApplication.clipboard().setText(json.dumps(self.s, ensure_ascii=False, indent=2)))
        m.addSeparator()
        m.addAction("↺ Сбросить к умолчанию…", self.reset_defaults)
        m.exec(gpos)

    def _results_menu(self, gpos):
        m = QMenu(self)
        m.addAction("📋 Копировать отчёт", self.copy_report)
        m.addAction("💾 Экспорт CSV по месяцам…", self.export_months)
        m.addAction("🔄 Пересчитать", self.recalc)
        m.exec(gpos)

    def reset_defaults(self):
        if QMessageBox.question(self, APP_NAME, "Сбросить все параметры станции к значениям по умолчанию?") != QMessageBox.Yes:
            return
        self.s.clear()
        self.s.update(DEFAULT_SYS)
        self._load_fields()
        log.info("↺ Параметры сброшены")
        self.recalc()

    def _dir(self):
        d = self.cfg.get("last_dir") or str(APP_ROOT)
        return d if Path(d).exists() else str(APP_ROOT)

    def save_profile(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Сохранить профиль", str(Path(self._dir()) / "моя_станция.json"),
                                            "Профиль (*.json)", options=QFileDialog.DontUseNativeDialog)
        if not fn:
            return
        Path(fn).write_text(json.dumps({"solar_calc": VERSION, "sys": self.s}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.cfg["last_dir"] = str(Path(fn).parent)
        log.info(f"✓ Профиль сохранён: {fn}")

    def load_profile(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Открыть профиль", self._dir(), "Профиль (*.json)",
                                            options=QFileDialog.DontUseNativeDialog)
        if not fn:
            return
        try:
            data = json.loads(Path(fn).read_text(encoding="utf-8"))
            sysd = data.get("sys", data)
            new = dict(DEFAULT_SYS)
            new.update({k: v for k, v in sysd.items() if k in DEFAULT_SYS})
            self.s.clear()
            self.s.update(new)
            self.cfg["last_dir"] = str(Path(fn).parent)
            self._load_fields()
            log.info(f"✓ Профиль загружен: {fn}")
            self.recalc()
        except Exception as e:
            log.error(f"✗ Не удалось открыть профиль: {e}")
            QMessageBox.warning(self, APP_NAME, f"Не удалось открыть профиль:\n{e}")

    def report_text(self):
        R, s = self.R, self.s
        c, res = R["ctx"], R["res"]
        m = int(s["month"])
        L = [f"{APP_NAME} v{VERSION} — отчёт",
             f"Поле: {c['ns']}S{c['np']}P × {c['pmax']:.0f} Вт = {c['pstc_tot'] / 1000:.2f} кВт; угол {s['tilt']}°, азимут {s['aspect']}°",
             f"Провод: {s['wire_len']} м, {s['wire_s']} мм² {'Al' if s['wire_mat'] == 'al' else 'Cu'}, R линии {wire_r(c, 20) * 1000:.0f} мОм",
             f"MPPT: заряд {s['bat_ch']} В, ток до {s['iout_max']} А; солнце: {self.sd.label(float(s['lat']), float(s['lon']))}", "",
             f"{'Месяц':<10}{'Ясно':>10}{'Средне':>10}{'Пасмурно':>10}  кВт·ч/сутки"]
        for mm in range(12):
            L.append(f"{MONTHS[mm]:<10}" + "".join(f"{res[(mm, w)]['wh'][8] / 1000:>10.2f}" for w in W_KEYS))
        bal = R["bal"]
        L += ["", f"АКБ: {c['nser']}S{c['npar']}P {c['bank_v']:.1f} В {c['bank_ah']:.0f} А·ч = {c['bank_wh'] / 1000:.1f} кВт·ч (полезно {c['usable_wh'] / 1000:.1f})",
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
        with open(fn, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["Месяц", "Ясно, Вт·ч/сут", "Средне, Вт·ч/сут", "Пасмурно, Вт·ч/сут", "Средне за месяц, кВт·ч"])
            for m in range(12):
                w.writerow([MONTHS[m]] + [f"{res[(m, k)]['wh'][8]:.0f}" for k in W_KEYS] +
                           [f"{res[(m, 'avg')]['wh'][8] * DAYS[m] / 1000:.1f}".replace(".", ",")])
        log.info(f"✓ CSV сохранён: {fn}")

    def _save_all(self):
        self.cfg["geometry"] = base64.b64encode(bytes(self.saveGeometry())).decode()
        save_config(self.cfg)
        log.info("💾 Настройки сохранены")
        self._status("сохранено")

    def closeEvent(self, e):
        self._save_all()
        super().closeEvent(e)


# ═════════════════════════════════ запуск ═════════════════════════════════
def selftest():
    lines, ok = [], True
    try:
        import PySide6
        lines.append(f"PySide6 {PySide6.__version__}: OK")
    except Exception as e:
        ok = False
        lines.append(f"PySide6: ОШИБКА {e}")
    try:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        R = compute_all(dict(DEFAULT_SYS), SunData(cfg))
        lines.append(f"Расчёт: год {R['year']['avg']:.0f} кВт·ч, декабрь средне {R['res'][(11, 'avg')]['wh'][8]:.0f} Вт·ч/сут: OK")
    except Exception as e:
        ok = False
        lines.append(f"Расчёт: ОШИБКА {e}")
    lines.append("ИТОГ: " + ("OK" if ok else "ОШИБКА"))
    txt = "\n".join(lines)
    print(txt)
    try:
        (APP_ROOT / "selftest.txt").write_text(txt, encoding="utf-8")
    except Exception:
        pass
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("solar_calc")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    QLocale.setDefault(QLocale(QLocale.Russian, QLocale.Ukraine))
    tr = QTranslator(app)
    if tr.load(QLocale(QLocale.Russian), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
    w = App()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
