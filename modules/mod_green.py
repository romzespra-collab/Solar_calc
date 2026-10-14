"""mod_green.py  v1.10.0
Зелёный тариф для домашней СЭС (Украина) — без Qt: ставки и правила, смета (оборудование, монтаж, документы,
платежи ОСР за присоединение по ставкам НКРЭКУ 2026), помесячный взаимозачёт по часам (1-/2-/3-зонный учёт,
налог), окупаемость (средний и худший год по погоде за 5 лет), проверки, памятка и шаги, отчёт HTML.
Станция (панели, инвертор, АКБ, выработка по часам, потребление дома) — из расчёта программы (mod_model).

Журнал:
v1.10.0: перенесено из «Калькулятора зелёного тарифа» v1.2.0 (green_tariff_calc.pyw) и связано со станцией:
         выработка — почасовая из модели станции (погода «📍 Регион 5 лет» или «⛅ Средний»), разброс по годам —
         по погоде региона; потребление — дом из настроек + холостой ход инвертора; цена для населения —
         тариф станции; смета — по составу станции (панели всех полей, инвертор, отдельные MPPT, АКБ).
"""

import html as htmlmod
import math
import time

from .mod_base import DAYS
from .mod_model import load_day_wh, plural
from .mod_sun import DT

GREEN_TARIFF = 6.134    # грн/кВт·ч без НДС — НКРЭКУ № 1613, с 01.10.2026
GREEN_LAST_YEAR = 2029  # зелёный тариф — до 01.01.2030
TAX_PCT = 23.0          # 18 % НДФЛ + 5 % военный сбор
POST_PRICE = 2.50       # грн/кВт·ч — оценка продажи после 2029 (самопроизводство ≈ РДН)
DEGRADATION = 0.5       # % в год
VAT = 1.20              # НДС к ставкам присоединения

URL_NERC = "https://www.nerc.gov.ua/"
URL_CONN_CALC = ("https://www.google.com/search?q=%D0%9D%D0%9A%D0%A0%D0%95%D0%9A%D0%9F+"
                 "%D0%BA%D0%B0%D0%BB%D1%8C%D0%BA%D1%83%D0%BB%D1%8F%D1%82%D0%BE%D1%80+"
                 "%D1%81%D1%82%D0%B0%D0%BD%D0%B4%D0%B0%D1%80%D1%82%D0%BD%D0%BE%D0%B3%D0%BE+"
                 "%D0%BF%D1%80%D0%B8%D1%94%D0%B4%D0%BD%D0%B0%D0%BD%D0%BD%D1%8F")
URL_TARIFF_NEWS = ("https://biz.ligazakon.net/news/246535_nov-zelen-tarifi-dlya-domogospodarstv--stantsy-do-150-"
                   "kvt-zalezhat-vd-vidu-generats-potuzhnost-ta-roku-vvedennya-stants")

MONTHS_S = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
NIGHT_H = {23, 0, 1, 2, 3, 4, 5, 6}           # ночная зона 23:00–07:00
PEAK_H = {8, 9, 10, 20, 21}                    # пик 08:00–11:00 и 20:00–22:00

# ставки стандартного присоединения 2026, тыс. грн/кВт без НДС (НКРЭКУ № 2230 от 30.12.2025)
# (город I, II, III, IV), (село I, II, III, IV);  I — до 16 кВт, II — 16–50 кВт, III — 50–160 кВт
OSR_RATES = {
    "Вінницяобленерго": ((2.214, 2.767, 3.321, 4.151), (1.821, 2.276, 2.732, 3.415)),
    "Волиньобленерго": ((2.140, 2.675, 3.210, 4.012), (1.761, 2.201, 2.641, 3.302)),
    "ДТЕК Дніпровські електромережі": ((2.364, 2.955, 3.546, 4.433), (1.945, 2.431, 2.917, 3.647)),
    "ДТЕК Донецькі електромережі": ((2.603, 3.253, 3.904, 4.880), (2.142, 2.677, 3.213, 4.016)),
    "ДТЕК Київські електромережі": ((2.101, 2.626, 3.152, 3.940), (1.728, 2.160, 2.592, 3.240)),
    "ДТЕК Київські регіональні електромережі": ((2.107, 2.634, 3.161, 3.951), (1.734, 2.168, 2.601, 3.251)),
    "ДТЕК Одеські електромережі": ((2.514, 3.142, 3.770, 4.713), (2.068, 2.586, 3.103, 3.878)),
    "ДП «Регіональні електричні мережі»": ((2.174, 2.718, 3.262, 4.077), (1.790, 2.237, 2.684, 3.355)),
    "Житомиробленерго": ((2.170, 2.713, 3.256, 4.069), (1.786, 2.232, 2.678, 3.348)),
    "Закарпаттяобленерго": ((2.434, 3.042, 3.650, 4.563), (2.002, 2.503, 3.003, 3.754)),
    "Запоріжжяобленерго": ((2.392, 2.990, 3.588, 4.485), (1.969, 2.461, 2.953, 3.691)),
    "Кіровоградобленерго": ((2.418, 3.022, 3.627, 4.533), (1.989, 2.487, 2.984, 3.730)),
    "Луганське енергетичне об'єднання": ((2.521, 3.151, 3.781, 4.726), (2.073, 2.592, 3.110, 3.888)),
    "Львівобленерго": ((2.425, 3.031, 3.637, 4.546), (1.995, 2.494, 2.993, 3.741)),
    "Миколаївобленерго": ((2.257, 2.822, 3.386, 4.233), (1.857, 2.321, 2.785, 3.481)),
    "ПЕЕМ «ЦЕК»": ((2.364, 2.955, 3.546, 4.433), (1.945, 2.431, 2.917, 3.647)),
    "Полтаваобленерго": ((2.155, 2.693, 3.232, 4.040), (1.773, 2.216, 2.659, 3.324)),
    "Прикарпаттяобленерго": ((2.927, 3.659, 4.391, 5.488), (2.409, 3.011, 3.613, 4.516)),
    "Рівнеобленерго": ((2.194, 2.743, 3.291, 4.114), (1.805, 2.257, 2.708, 3.385)),
    "Сумиобленерго": ((2.127, 2.659, 3.190, 3.988), (1.750, 2.187, 2.625, 3.281)),
    "Тернопільобленерго": ((2.307, 2.884, 3.460, 4.325), (1.898, 2.373, 2.848, 3.559)),
    "Харківобленерго": ((2.261, 2.827, 3.392, 4.240), (1.861, 2.326, 2.791, 3.489)),
    "Херсонобленерго": ((2.519, 3.148, 3.778, 4.722), (2.071, 2.589, 3.107, 3.884)),
    "Хмельницькобленерго": ((2.303, 2.879, 3.454, 4.318), (1.894, 2.368, 2.842, 3.552)),
    "Черкасиобленерго": ((2.168, 2.711, 3.253, 4.066), (1.784, 2.229, 2.675, 3.344)),
    "Чернівціобленерго": ((2.510, 3.137, 3.765, 4.706), (2.065, 2.581, 3.097, 3.871)),
    "Чернігівобленерго": ((2.068, 2.586, 3.103, 3.878), (1.701, 2.127, 2.552, 3.190)),
}

# область, центр, широта, долгота, ОСР по умолчанию
REGIONS = [
    ("Город Киев", "Киев", 50.450, 30.523, "ДТЕК Київські електромережі"),
    ("Винницкая обл.", "Винница", 49.233, 28.468, "Вінницяобленерго"),
    ("Волынская обл.", "Луцк", 50.747, 25.325, "Волиньобленерго"),
    ("Днепропетровская обл.", "Днепр", 48.465, 35.046, "ДТЕК Дніпровські електромережі"),
    ("Донецкая обл.", "Краматорск", 48.723, 37.556, "ДТЕК Донецькі електромережі"),
    ("Житомирская обл.", "Житомир", 50.254, 28.658, "Житомиробленерго"),
    ("Закарпатская обл.", "Ужгород", 48.621, 22.288, "Закарпаттяобленерго"),
    ("Запорожская обл.", "Запорожье", 47.838, 35.139, "Запоріжжяобленерго"),
    ("Ивано-Франковская обл.", "Ивано-Франковск", 48.922, 24.711, "Прикарпаттяобленерго"),
    ("Киевская обл.", "Белая Церковь", 49.795, 30.131, "ДТЕК Київські регіональні електромережі"),
    ("Кировоградская обл.", "Кропивницкий", 48.508, 32.262, "Кіровоградобленерго"),
    ("Луганская обл.", "Северодонецк", 48.948, 38.493, "Луганське енергетичне об'єднання"),
    ("Львовская обл.", "Львов", 49.839, 24.029, "Львівобленерго"),
    ("Николаевская обл.", "Николаев", 46.975, 31.995, "Миколаївобленерго"),
    ("Одесская обл.", "Одесса", 46.482, 30.723, "ДТЕК Одеські електромережі"),
    ("Полтавская обл.", "Полтава", 49.588, 34.551, "Полтаваобленерго"),
    ("Ровенская обл.", "Ровно", 50.619, 26.251, "Рівнеобленерго"),
    ("Сумская обл.", "Сумы", 50.907, 34.798, "Сумиобленерго"),
    ("Тернопольская обл.", "Тернополь", 49.553, 25.594, "Тернопільобленерго"),
    ("Харьковская обл.", "Харьков", 49.993, 36.230, "Харківобленерго"),
    ("Херсонская обл.", "Херсон", 46.635, 32.616, "Херсонобленерго"),
    ("Хмельницкая обл.", "Хмельницкий", 49.422, 26.987, "Хмельницькобленерго"),
    ("Черкасская обл.", "Черкассы", 49.444, 32.060, "Черкасиобленерго"),
    ("Черновицкая обл.", "Черновцы", 48.292, 25.935, "Чернівціобленерго"),
    ("Черниговская обл.", "Чернигов", 51.498, 31.289, "Чернігівобленерго"),
]
REGION_MAP = {r[0]: r for r in REGIONS}

CONN_OPTIONS = (("ok", "Дом подключён, мощности хватает"), ("increase", "Нужно увеличить разрешённую мощность"),
                ("new", "Нового подключения ещё нет"))
PHASES = (("3", "3 фазы, 380 В"), ("1", "1 фаза, 220 В"), ("?", "Не знаю"))
AREAS = (("village", "Село"), ("city", "Город"))
MOUNTS = (("roof", "Крыша / фасад — до 50 кВт"), ("ground", "На земле (участок) — до 30 кВт"))
METER_TYPES = (("2", "День / ночь"), ("1", "Однозонный"), ("3", "Ночь / полупик / пик"))
NET_MODES = (("total", "Суммарно за месяц"), ("zones", "По каждой зоне"))
EXPORT_MODES = (("auto", "По модели"), ("yes", "Да"), ("no", "Нет"))
GEN_WEATHER = (("reg", "📍 Регион 5 лет"), ("avg", "⛅ Средний"))

# key, позиция, ед., мин, макс, знаков
PRICE_DEFS = [
    ("panel_w", "Солнечные панели", "грн/Вт", 7.0, 10.0, 2),
    ("inv_base", "Инвертор — база", "грн", 12000, 25000, 0),
    ("inv_kw", "Инвертор — за 1 кВт", "грн/кВт", 1500, 2200, 0),
    ("hybrid_k", "Гибридный инвертор (с АКБ) — множитель к сетевому", "×", 1.4, 1.7, 2),
    ("mppt_pc", "Отдельный MPPT-контроллер", "грн/шт", 3000, 9000, 0),
    ("bat_kwh", "Аккумулятор LiFePO4", "грн/кВт·ч", 13000, 18000, 0),
    ("mount_pc", "Крепления на крышу", "грн/панель", 800, 1800, 0),
    ("mount_ground_pc", "Наземная конструкция (сваи, профиль)", "грн/панель", 1500, 2800, 0),
    ("field_cable_m", "Кабель поле → щит + траншея", "грн/м", 400, 800, 0),
    ("cable_base", "Кабели и защита — база", "грн", 4000, 8000, 0),
    ("cable_kw", "Кабели и защита — за 1 кВт·п", "грн/кВт·п", 800, 2400, 0),
    ("install_kw", "Монтаж и пусконаладка", "грн/кВт·п", 3000, 6000, 0),
    ("docs", "Проект, документы, сопровождение", "грн", 5000, 15000, 0),
    ("meter", "Счётчик 1-фазный двунаправленный + работы ОСР", "грн", 2000, 4000, 0),
    ("meter3", "Счётчик 3-фазный двунаправленный + работы ОСР", "грн", 4000, 8000, 0),
    ("reserve", "Резерв на доп. работы", "грн", 10000, 20000, 0),
]
OWN_KEYS = (("panels", "Панели (все)"), ("inverter", "Инвертор"), ("battery", "Аккумуляторы"),
            ("mount", "Конструкция под панели"))
GEAR_ROWS = ("panels", "inverter", "mppt", "battery", "mount", "fieldcable", "cable", "install")

MARKET = [
    ("Сетевая СЭС 5 кВт", 5, "grid", 125000, 215000),
    ("Гибридная СЭС 5 кВт", 5, "hybrid", 240000, 340000),
    ("Сетевая СЭС 10 кВт", 10, "grid", 230000, 280000),
    ("Сетевая СЭС 30 кВт", 30, "grid", 580000, 700000),
]

STEPS = [
    ("Подготовка", [
        "Узнать разрешённую мощность и тип ввода (договор с ОСР / личный кабинет облэнерго)",
        "Рассчитать станцию: мощность инвертора не больше разрешённой",
        "Для поля: участок в собственности, кадастровый номер, место для траншеи к щиту",
        "Получить 2–3 предложения «под ключ» и сравнить, что входит в цену",
    ]),
    ("ОСР (РЭС / облэнерго)", [
        "Онлайн-заявка в личном кабинете ОСР + однолинейная схема",
        "Если мощности не хватает — заявка на увеличение (можно одновременно), оплата по счёту ОСР",
        "Купить у ОСР двунаправленный счётчик, установка и проверка схемы",
        "Получить паспорт точки распределения с данными о генерирующей установке",
    ]),
    ("Монтаж", [
        "Монтаж панелей, инвертора, защиты и заземления",
        "Пусконаладка и акт выполненных работ",
    ]),
    ("Договор зелёного тарифа (поставщик универсальных услуг)", [
        "Заявление-уведомление о продаже электроэнергии по зелёному тарифу",
        "Документы о праве собственности / пользования домом и участком",
        "Паспорт точки распределения (генерация + коммерческий учёт)",
        "Техпаспорт дома и кадастровый номер участка",
        "Банковские реквизиты (IBAN) для выплат",
        "Согласие членов домохозяйства и копии их РНОКПП (если требуется)",
        "Подписать договор: выплаты ежемесячно, налог удерживает поставщик",
    ]),
]
STEP_KEYS = [t for _s, items in STEPS for t in items]

NOTES_HTML = (
    "<p style='margin:0 0 6px 0'><b>Главное о деньгах</b></p>"
    "<p style='margin:4px 0'>• Тариф <b>6,134 грн/кВт·ч</b> без НДС (НКРЭКУ № 1613, с 01.10.2026), "
    "меняется каждый квартал. <b>Действует до 01.01.2030</b>, дальше — продажа как самопроизводство "
    "(≈ цена РДН, не выше тарифа для населения).</p>"
    "<p style='margin:4px 0'>• На земле (участок) — до <b>30 кВт</b>, на крыше/фасаде — до 50 кВт.</p>"
    "<p style='margin:4px 0'>• Платят за <b>сальдо месяца</b> (отдано − взято). Налог 18 % НДФЛ + 5 % "
    "военный сбор удерживает поставщик.</p>"
    "<p style='margin:4px 0'>• Население: 4,32 грн. Двухзонный: ночь 23–07 — 50 %. Трёхзонный: "
    "ночь 40 %, пик 08–11 и 20–22 — 150 %.</p>"
    "<p style='margin:4px 0'>• Ночные окна зелёного тарифа (апр–окт 23–04, ноя–мар 21–06) — по меньшей "
    "из цен: тариф или РДН. Солнце в это время не светит — для СЭС без отдачи из АКБ не влияет.</p>"
    "<p style='margin:4px 0'>• Инвертор должен уметь отдавать в сеть (on-grid / гибрид с экспортом). "
    "Автономные (off-grid) — только для себя.</p>"
    "<p style='margin:4px 0'>• В ОСР — только по официальному счёту. Стандартное присоединение: I ступень "
    "до 16 кВт, II — 16–50 кВт (НКРЭКУ № 2230, ставки 2026 без НДС).</p>"
)

GREEN_DEFAULT = dict(
    region="", osr="", area="village", conn="ok", phase="3", permitted=15.0, grid_auto=True, grid_cost=0.0,
    mount="roof", field_dist=30.0, meter_paid=True, export="auto",
    meter_zones="2", net_mode="total", weather="reg",
    green=GREEN_TARIFF, tax=TAX_PCT, start_year=2027, post_price=POST_PRICE, degr=DEGRADATION, years=25,
    prices={k: [float(mn), float(mx)] for k, _l, _u, mn, mx, _d in PRICE_DEFS},
    own={k: 0.0 for k, _t in OWN_KEYS}, extra_mat=0.0, extra_note="",
    excluded=[], checklist={}, notes="",
)
_LIMITS = dict(permitted=(0, 150), grid_cost=(0, 5e6), field_dist=(0, 1000), green=(0, 50), tax=(0, 60),
               start_year=(2024, 2040), post_price=(0, 20), degr=(0, 5), years=(5, 40), extra_mat=(0, 1e7))
_CHOICES = dict(area=AREAS, conn=CONN_OPTIONS, phase=PHASES, mount=MOUNTS, meter_zones=METER_TYPES,
                net_mode=NET_MODES, export=EXPORT_MODES, weather=GEN_WEATHER)


def green_clean(d):
    """Настройки зелёного тарифа из профиля / config → типы и пределы; негодное — по умолчанию."""
    g = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
         for k, v in GREEN_DEFAULT.items()}
    g["prices"] = {k: list(v) for k, v in GREEN_DEFAULT["prices"].items()}
    if not isinstance(d, dict):
        return g
    for k, v in d.items():
        if k not in g:
            continue
        dv = g[k]
        try:
            if k == "prices" and isinstance(v, dict):
                for pk, pv in v.items():
                    try:
                        if pk in g["prices"] and isinstance(pv, (list, tuple)) and len(pv) == 2:
                            a, b = float(pv[0]), float(pv[1])
                            if math.isfinite(a) and math.isfinite(b):
                                g["prices"][pk] = [max(0.0, min(a, 1e7)), max(0.0, min(b, 1e7))]
                    except (TypeError, ValueError, OverflowError):
                        pass
            elif k == "own" and isinstance(v, dict):
                for ok, ov in v.items():
                    try:
                        if ok in g["own"]:
                            ov = float(ov)
                            g["own"][ok] = max(0.0, min(ov, 1e8)) if math.isfinite(ov) else 0.0
                    except (TypeError, ValueError, OverflowError):
                        pass
            elif k == "excluded" and isinstance(v, list):
                g[k] = [str(x) for x in v][:50]
            elif k == "checklist" and isinstance(v, dict):
                g[k] = {str(a): bool(b) for a, b in v.items() if str(a) in STEP_KEYS}
            elif k in _CHOICES:
                if str(v) in dict(_CHOICES[k]):
                    g[k] = str(v)
            elif k in ("region", "osr"):
                v = str(v)
                if v == "" or v in (REGION_MAP if k == "region" else OSR_RATES):
                    g[k] = v
            elif isinstance(dv, bool):
                g[k] = bool(v)
            elif isinstance(dv, (int, float)):
                v = float(v)
                if not math.isfinite(v):
                    continue
                lo, hi = _LIMITS.get(k, (-1e9, 1e9))
                v = min(max(v, lo), hi)
                g[k] = int(round(v)) if isinstance(dv, int) else v
            elif isinstance(dv, str):
                g[k] = str(v)[:4000 if k == "notes" else 200]
        except (TypeError, ValueError, OverflowError):
            pass
    return g


# ───────────────────────────── формат ─────────────────────────────
def fnum(x, d=0):
    try:
        s = f"{float(x):,.{d}f}"
    except (TypeError, ValueError):
        return "—"
    return s.replace(",", " ").replace(".", ",").replace("-", "−")


def fkw(x):
    s = fnum(x, 2)
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


def fk(x):
    return fkw(round(x / 1000.0, 0 if abs(x) >= 10000 else 1))


def frange(a, b):
    if max(abs(a), abs(b)) < 1000:
        return f"{fnum(a)} грн" if round(a) == round(b) else f"{fnum(a)}–{fnum(b)} грн"
    if round(a, -2) == round(b, -2):
        return f"{fk(a)} тыс. грн"
    return f"{fk(a)}–{fk(b)} тыс. грн"


def fpb(x, years):
    return f"> {years} лет" if x is None else f"{fnum(x, 1)}"


# ───────────────────────────── место и инвертор ─────────────────────────────
def region_nearest(lat, lon):
    """Область по координатам станции — ближайший областной центр."""
    k = math.cos(math.radians(float(lat)))
    return min(REGIONS, key=lambda r: (r[2] - lat) ** 2 + ((r[3] - lon) * k) ** 2)[0]


def place_of(g, s):
    """→ (область, ОСР, авто?) — из настроек, а пусто — по координатам станции."""
    auto = not g.get("region")
    reg = region_nearest(float(s["lat"]), float(s["lon"])) if auto else g["region"]
    osr = g.get("osr") or REGION_MAP[reg][4]
    return reg, osr, auto


def inv_export(key, name="", note=""):
    """Умеет ли инвертор отдавать в сеть (по серии): True / False / None (не знаю) + пояснение."""
    k, t = str(key).lower(), f"{name} {note}".lower()
    if k.startswith("deye_"):
        if "og0" in k:
            return False, "Deye OG — автономный (off-grid)"
        return True, "Deye SG — гибрид с отдачей в сеть"
    if k.startswith(("solis_", "sofar_")):
        return True, "гибрид с отдачей в сеть"
    if k.startswith("luxpower_"):
        return ("lxp" in k), ("LXP-LB — гибрид с отдачей в сеть" if "lxp" in k else "SNA — автономный (off-grid)")
    if k.startswith("victron_"):
        if any(x in t for x in ("multiplus-ii", "multiplus ii", "quattro", "easysolar-ii")):
            return True, "Victron ESS — отдача в сеть после настройки и сертификации"
        return None, "Victron — уточните, поддерживает ли модель ESS с отдачей в сеть"
    if k.startswith("axioma_"):
        return ("isgrid" in k), ("ISGRID — сетевой гибрид" if "isgrid" in k else "Axioma ISMPPT/AXEN — автономный")
    if k.startswith(("must_", "easun_", "srne_", "powmr_", "felicity_", "logicpower_", "luxeon_", "meanwell_",
                     "voltpolska_", "growatt_")):
        return False, "автономный (off-grid) — для себя, без продажи"
    if k.startswith("voltronic_"):
        return (None, "Axpert MAX/Ultra — уточните функцию «grid-tie»") if ("max" in k or "ultra" in k) \
            else (False, "Axpert VM — автономный (off-grid)")
    return None, "не знаю — в паспорте ищите «grid-tie», «on-grid», «export to grid»"


def inv_three_phase(key, note=""):
    k = str(key).lower()
    return "lp3" in k or "hp3" in k or "3 фаз" in str(note).lower()


# ───────────────────────────── смета ─────────────────────────────
def conn_estimate(g, inv_kw, osr):
    """Оценка платы ОСР за стандартное присоединение / увеличение мощности (НКРЭКУ № 2230, 2026)."""
    if g["conn"] == "ok":
        return {"cost": 0.0, "add": 0.0, "stage": 0, "rate": 0.0, "text": "не нужно"}
    target = max(float(math.ceil(inv_kw - 1e-9)), 1.0)
    add = target if g["conn"] == "new" else max(0.0, target - g["permitted"])
    stage = 1 if target <= 16 else 2 if target <= 50 else 3 if target <= 160 else 4
    rates = OSR_RATES.get(osr) or OSR_RATES["ДТЕК Київські електромережі"]
    rate = rates[0 if g["area"] == "city" else 1][stage - 1] * 1000.0 * VAT
    cost = add * rate
    st = ["", "I", "II", "III", "IV"][stage]
    if add <= 0:
        text = (f"инвертор {fkw(inv_kw)} кВт вписывается в разрешённые {fkw(g['permitted'])} кВт — "
                f"увеличивать мощность не нужно (0 грн)")
    else:
        text = (f"{fkw(add)} кВт × {fnum(rate)} грн/кВт ({st} ступень, "
                f"{'город' if g['area'] == 'city' else 'село'}, с НДС) = {fnum(cost)} грн")
    return {"cost": cost, "add": add, "stage": stage, "rate": rate, "text": text}


def station_info(c, s):
    """Состав станции для сметы и отчёта — из контекста расчёта (все поля, инвертор, контроллеры, АКБ)."""
    fields = c["fields"]
    keys = {f["key"] for f in fields}
    pm = {f["pmax"] for f in fields}
    n_ctl = sum(1 for f in fields if f["ctl"])                  # отдельные MPPT у линии АКБ
    if not c["builtin"]:                                         # инвертор без MPPT: контроллеры на всех полях
        n_ctl += max(len(c["slots"]), int(s.get("n_mppt_max", 1)))
    return dict(npan=int(c["npan"]), kwp=c["pstc_tot"] / 1000.0, pmax=(next(iter(pm)) if len(pm) == 1 else None),
                one_model=len(keys) == 1, inv_kw=c["inv_p"] / 1000.0, hybrid=c["builtin"], n_ctl=n_ctl,
                bat_kwh=c["bank_wh"] / 1000.0, chem=s.get("chem", "lfp"))


def price_estimates(g, st):
    """Оценки (мин, макс) по ценам рынка: панели, инвертор, АКБ, конструкция — всего."""
    p = g["prices"]
    w = st["kwp"] * 1000.0
    inv = [p["inv_base"][i] + p["inv_kw"][i] * st["inv_kw"] for i in (0, 1)]
    if st["bat_kwh"] > 0:
        inv = [inv[i] * p["hybrid_k"][i] for i in (0, 1)]
    mk = "mount_ground_pc" if g["mount"] == "ground" else "mount_pc"
    return {"panels": (w * p["panel_w"][0], w * p["panel_w"][1]), "inverter": tuple(inv),
            "battery": (st["bat_kwh"] * p["bat_kwh"][0], st["bat_kwh"] * p["bat_kwh"][1]),
            "mount": (st["npan"] * p[mk][0], st["npan"] * p[mk][1])}


def calc_budget(g, st, osr, phase3):
    p = g["prices"]
    n, kwp = st["npan"], st["kwp"]
    ground = g["mount"] == "ground"
    excl = set(g.get("excluded", []))
    est = price_estimates(g, st)
    rows = []

    def add(key, name, payee, mn, mx, own=False):
        rows.append({"key": key, "name": name + (" — ваша цена" if own else ""), "payee": payee,
                     "mn": float(mn), "mx": float(mx), "on": key not in excl, "own": own})

    def pick(key):
        v = g["own"].get(key, 0.0)
        if v > 0:
            return v, v, True
        return est[key][0], est[key][1], False

    pw = f" × {fnum(st['pmax'])} Вт" if st["pmax"] else " (разные поля)"
    add("panels", f"Панели {n} шт{pw} = {fkw(kwp)} кВт·п", "Магазин", *pick("panels"))
    add("inverter", f"{'Гибридный' if st['bat_kwh'] > 0 else 'Сетевой'} инвертор {fkw(st['inv_kw'])} кВт", "Магазин",
        *pick("inverter"))
    if st["n_ctl"]:
        add("mppt", f"Отдельные MPPT-контроллеры × {st['n_ctl']}", "Магазин",
            st["n_ctl"] * p["mppt_pc"][0], st["n_ctl"] * p["mppt_pc"][1])
    if st["bat_kwh"] > 0:
        chem = "LiFePO4" if st["chem"] == "lfp" else "свинец"
        add("battery", f"Аккумуляторы {fkw(round(st['bat_kwh'], 1))} кВт·ч ({chem})", "Магазин", *pick("battery"))
    add("mount", "Наземная конструкция (сваи, профиль)" if ground else "Крепления на крышу", "Магазин", *pick("mount"))
    if g.get("extra_mat", 0) > 0:
        note = (g.get("extra_note") or "").strip()
        add("extra", f"Доп. материалы{': ' + note if note else ''}", "Магазин", g["extra_mat"], g["extra_mat"])
    if ground:
        add("fieldcable", f"Кабель поле → щит, траншея ({fnum(g['field_dist'])} м)", "Установщик",
            g["field_dist"] * p["field_cable_m"][0], g["field_dist"] * p["field_cable_m"][1])
    add("cable", "Кабели, автоматы, УЗИП, заземление", "Магазин",
        p["cable_base"][0] + p["cable_kw"][0] * kwp, p["cable_base"][1] + p["cable_kw"][1] * kwp)
    add("install", "Монтаж и пусконаладка", "Установщик", p["install_kw"][0] * kwp, p["install_kw"][1] * kwp)
    add("docs", "Проект, документы, сопровождение", "Установщик", p["docs"][0], p["docs"][1])
    if g["meter_paid"]:
        three = g["phase"] == "3" or (g["phase"] == "?" and phase3)
        mk = "meter3" if three else "meter"
        add("meter", f"Двунаправленный счётчик ({'3' if three else '1'}-ф) + работы", "ОСР (РЭС)", p[mk][0], p[mk][1])
    ce = conn_estimate(g, st["inv_kw"], osr)
    if g["conn"] != "ok":
        cost = ce["cost"] if g["grid_auto"] else g["grid_cost"]
        lbl = "Увеличение мощности" if g["conn"] == "increase" else "Присоединение к сети"
        add("grid", f"{lbl}{' (оценка по ставкам 2026)' if g['grid_auto'] else ''}", "ОСР (РЭС)", cost, cost)
    add("reserve", "Резерв на доп. работы", "Резерв", p["reserve"][0], p["reserve"][1])
    on = [r for r in rows if r["on"]]
    mn, mx = sum(r["mn"] for r in on), sum(r["mx"] for r in on)
    osr_rows = [r for r in on if r["payee"].startswith("ОСР")]
    return {"rows": rows, "mn": mn, "mx": mx, "mid": (mn + mx) / 2.0, "kwp": kwp, "conn": ce, "est": est,
            "osr_mn": sum(r["mn"] for r in osr_rows), "osr_mx": sum(r["mx"] for r in osr_rows)}


# ───────────────────────────── выработка и потребление по часам ─────────────────────────────
def gen_bins(R, weather):
    """Выработка станции в сеть/дом (AC, кВт·ч) по месяцам × часам местного времени: средний день погоды из
    расчёта станции × КПД инвертора, не больше его мощности; × дней в месяце."""
    c, res = R["ctx"], R["res"]
    eta, pac_max = max(0.5, c["inv_eta"]), c["inv_p"]
    out = []
    for m in range(12):
        w = weather if (m, weather) in res else "avg"
        day = [0.0] * 24
        for tl, p in res[(m, w)]["curve"]:
            day[int(tl) % 24] += min(p * eta, pac_max) * DT / 1000.0
        out.append([v * DAYS[m] for v in day])
    return out


def year_factors(region, use):
    """Разброс по годам из погоды региона: [(год, [12 множителей к среднему году])]; нет — один средний год."""
    if not (use and region):
        return [("средний год", [1.0] * 12)]
    my = region.get("month_year") or {}
    if my:
        ys = sorted(my)
        mean = [sum(my[y][m] for y in ys) / len(ys) for m in range(12)]
        return [(y, [my[y][m] / mean[m] if mean[m] > 0 else 1.0 for m in range(12)]) for y in ys]
    yh = region.get("year_h") or {}
    if yh:
        ys = sorted(yh)
        mean = sum(yh[y] for y in ys) / len(ys)
        return [(y, [yh[y] / mean if mean > 0 else 1.0] * 12) for y in ys]
    return [("средний год", [1.0] * 12)]


def cons_bins(c):
    """Потребление (кВт·ч) по месяцам × часам: дом (настройки станции, профиль суток) + холостой ход инвертора."""
    prof = c["profile"]
    idle_kw = c["inv_idle"] * min(24.0, c["inv_hours"]) / 24.0 / 1000.0
    house, idle = [], []
    for m in range(12):
        day = load_day_wh(c, m) / 1000.0
        house.append([day * prof[h] * DAYS[m] for h in range(24)])
        idle.append([idle_kw * DAYS[m]] * 24)
    return house, idle


def zone_setup(meter, base):
    if meter == "2":
        return (["День 07–23", "Ночь 23–07"], [1 if h in NIGHT_H else 0 for h in range(24)], [base, base * 0.5])
    if meter == "3":
        return (["Полупик", "Ночь 23–07", "Пик 08–11, 20–22"],
                [1 if h in NIGHT_H else 2 if h in PEAK_H else 0 for h in range(24)], [base, base * 0.4, base * 1.5])
    return ["Круглосуточно"], [0] * 24, [base]


def settle(gen24, cons24, zh, prices, e_price, mode):
    """Месяц: сальдо по зонам или суммарно → отдано / куплено, счёт без СЭС и с СЭС, доход до налога."""
    nz = len(prices)
    gz, cz = [0.0] * nz, [0.0] * nz
    for h in range(24):
        gz[zh[h]] += gen24[h]
        cz[zh[h]] += cons24[h]
    G, C = sum(gz), sum(cz)
    bill0 = sum(cz[k] * prices[k] for k in range(nz))
    if mode == "zones" or nz == 1:
        exp = sum(max(0.0, gz[k] - cz[k]) for k in range(nz))
        buy = sum(max(0.0, cz[k] - gz[k]) for k in range(nz))
        bill = sum(max(0.0, cz[k] - gz[k]) * prices[k] for k in range(nz))
    elif G >= C:
        exp, buy, bill = G - C, 0.0, 0.0
    else:
        off = [min(gz[k], cz[k]) for k in range(nz)]
        left = sum(max(0.0, gz[k] - cz[k]) for k in range(nz))
        rem = [cz[k] - off[k] for k in range(nz)]
        tot = sum(rem)
        if left > 0 and tot > 0:
            off = [off[k] + rem[k] / tot * left for k in range(nz)]
        exp, buy = 0.0, C - G
        bill = sum((cz[k] - off[k]) * prices[k] for k in range(nz))
    return {"gen": G, "cons": C, "exp": exp, "buy": buy, "bill0": bill0, "bill": bill,
            "save": bill0 - bill, "gross": exp * e_price, "gz": gz, "cz": cz}


def calc_econ(g, home_price, budget, gen_avg, factors, cons):
    """Окупаемость: средний год (по погоде) и «каждый год как худший»; зелёный тариф до 2029, дальше — продажа
    по цене после 2029; деградация панелей; налог с дохода."""
    names, zh, prices = zone_setup(g["meter_zones"], home_price)
    keep = max(0.0, 1.0 - g["tax"] / 100.0)
    H, start = max(1, int(g["years"])), int(g["start_year"])
    years = [(lab, [[v * f[m] for v in gen_avg[m]] for m in range(12)]) for lab, f in factors]
    totals = [sum(sum(r) for r in b) for _l, b in years]
    worst = years[totals.index(min(totals))][1]

    def price_for(year):
        return g["green"] if year <= GREEN_LAST_YEAR else g["post_price"]

    def year_rows(bins, f, e):
        return [settle([v * f for v in bins[m]], cons[m], zh, prices, e, g["net_mode"]) for m in range(12)]

    def benefit(rows):
        return sum(r["save"] for r in rows) + sum(r["gross"] for r in rows) * keep

    rows1 = year_rows(gen_avg, 1.0, price_for(start))
    for m, r in enumerate(rows1):
        r["month"] = MONTHS_S[m]
        r["inc"] = r["gross"] * keep
        r["tax"] = r["gross"] - r["inc"]

    def tot(key):
        return sum(r[key] for r in rows1)

    cum, cum_bad, acc, accb = [], [], 0.0, 0.0
    for i in range(H):
        f = (1.0 - g["degr"] / 100.0) ** i
        e = price_for(start + i)
        acc += benefit(year_rows(gen_avg, f, e))
        accb += benefit(year_rows(worst, f, e))
        cum.append(acc)
        cum_bad.append(accb)

    def payback(inv, series):
        if inv <= 0:
            return 0.0
        prev = 0.0
        for i, v in enumerate(series):
            if v >= inv:
                step = v - prev
                return i + ((inv - prev) / step if step > 0 else 1.0)
            prev = v
        return None

    green_years = max(0, min(H, GREEN_LAST_YEAR - start + 1))
    return {
        "rows": rows1, "gen": tot("gen"), "cons": tot("cons"), "exp": tot("exp"), "buy": tot("buy"),
        "save": tot("save"), "inc": tot("inc"), "gross": tot("gross"), "tax": tot("tax"),
        "benefit": benefit(rows1), "bill_without": tot("bill0"), "bill_with": tot("bill"),
        "cum": cum, "cum_bad": cum_bad, "years": H, "start": start, "green_years": green_years,
        "b_green": benefit(year_rows(gen_avg, 1.0, g["green"])), "b_post": benefit(year_rows(gen_avg, 1.0, g["post_price"])),
        "zones": names, "zprices": prices,
        "zgen": [sum(r["gz"][k] for r in rows1) for k in range(len(names))],
        "zcons": [sum(r["cz"][k] for r in rows1) for k in range(len(names))],
        "year_totals": [(lab, t) for (lab, _b), t in zip(years, totals)],
        "gen_lo": [min(sum(b[m]) for _l, b in years) for m in range(12)],
        "gen_hi": [max(sum(b[m]) for _l, b in years) for m in range(12)],
        "pb_min": payback(budget["mn"], cum), "pb_mid": payback(budget["mid"], cum),
        "pb_max": payback(budget["mx"], cum), "pb_bad": payback(budget["mid"], cum_bad),
        "profit": (cum[-1] if cum else 0.0) - budget["mid"],
    }


def green_checks(g, s, st, b, exp, phase3, has_reg):
    out = []
    kwp, kw = b["kwp"], st["inv_kw"]
    ground = g["mount"] == "ground"
    cap = 30.0 if ground else 50.0
    ok_exp, why = exp
    if ok_exp is False:
        out.append(("err", f"Инвертор не отдаёт в сеть ({why}). Для зелёного тарифа нужен сетевой или гибридный "
                           f"инвертор с экспортом — или поменяйте «Отдаёт в сеть» на «Да», если в паспорте он есть."))
    elif ok_exp is None:
        out.append(("warn", f"Отдаёт ли инвертор в сеть — {why}. Укажите «Да» / «Нет» на вкладке «Подключение»."))
    else:
        out.append(("ok", f"Инвертор отдаёт в сеть: {why}."))
    if kw > cap:
        out.append(("err", f"Инвертор {fkw(kw)} кВт — больше {fkw(cap)} кВт: "
                           f"{'на земле зелёный тариф только до 30 кВт' if ground else 'вне категории домохозяйства'}."))
    elif kwp > cap:
        out.append(("warn", f"Панелей {fkw(kwp)} кВт·п — больше {fkw(cap)} кВт. Уточните у ОСР, как считается "
                            f"установленная мощность (по инвертору или по панелям)."))
    elif not ground and max(kwp, kw) > 30:
        out.append(("warn", "30–50 кВт — отдельная категория (только крыша/фасад). Проверьте её ставку "
                            "в постановлении НКРЭКУ."))
    if ground:
        out.append(("info", "СЭС на земле: до 30 кВт, участок в собственности/пользовании, кадастровый номер."))
    start = int(g["start_year"])
    if start > GREEN_LAST_YEAR:
        out.append(("err", "После 2029 г. зелёный тариф не назначается — только самопроизводство."))
    else:
        n = GREEN_LAST_YEAR - start + 1
        out.append(("warn" if n <= 3 else "info",
                    f"Зелёный тариф действует до 01.01.2030: при вводе в {start} г. — {n} "
                    f"{plural(n, 'год', 'года', 'лет')} по тарифу, дальше ≈ {fnum(g['post_price'], 2)} грн/кВт·ч."))
    ratio = kwp / kw if kw else 0.0
    if ratio < 0.9:
        out.append(("warn", f"Панелей мало для инвертора (DC/AC = {fnum(ratio, 2)}). Обычно 1,0–1,3."))
    elif ratio > 1.35:
        out.append(("warn", f"Панелей много для инвертора (DC/AC = {fnum(ratio, 2)}): в ясный полдень отдача "
                            f"упрётся в {fkw(kw)} кВт. Обычно 1,0–1,3."))
    else:
        out.append(("ok", f"Соотношение панелей и инвертора DC/AC = {fnum(ratio, 2)} — нормально."))
    perm = g["permitted"]
    if perm <= 0:
        out.append(("info" if g["conn"] == "new" else "warn",
                    "Разрешённая мощность не указана — посмотрите договор с ОСР или личный кабинет облэнерго."))
    elif kw > perm:
        if g["conn"] == "ok":
            out.append(("err", f"Инвертор {fkw(kw)} кВт больше разрешённой мощности {fkw(perm)} кВт — нужно "
                               f"увеличение мощности (выберите это в «Подключение») или инвертор поменьше."))
        else:
            out.append(("info", f"Увеличение мощности {fkw(perm)} → {fkw(math.ceil(kw))} кВт: "
                                f"≈ {fnum(b['conn']['cost'])} грн по ставкам 2026."))
    else:
        out.append(("ok", f"Инвертор {fkw(kw)} кВт вписывается в разрешённую мощность {fkw(perm)} кВт."))
    if g["phase"] == "1" and phase3:
        out.append(("err", "Инвертор трёхфазный, а ввод в дом однофазный — нужен однофазный инвертор или 3 фазы."))
    elif g["phase"] == "1" and kw > 8:
        out.append(("warn", "Однофазные инверторы обычно до 6–8 кВт. Для большей мощности нужен трёхфазный ввод."))
    elif g["phase"] == "?":
        out.append(("info", "Тип ввода неизвестен — от него зависит выбор инвертора (1- или 3-фазный)."))
    if g["conn"] != "ok" and not g["grid_auto"] and g["grid_cost"] <= 0:
        out.append(("warn", "Впишите плату ОСР за присоединение или включите оценку по ставкам 2026."))
    if s.get("grid_mode") == "off":
        out.append(("info", "В настройках станции горсеть «Нет / отключают» — для зелёного тарифа нужна сеть; "
                            "на этот расчёт не влияет (страницы «Покрытие дома» и «Горсеть» считают без неё)."))
    if not has_reg:
        out.append(("info", "Выработка — по среднему году. Загрузите «📍 Погоду региона за 5 лет» (вкладка «Солнце») — "
                            "будут реальная погода и разброс по годам."))
    if st["bat_kwh"] > 0:
        out.append(("info", "АКБ для зелёного тарифа не обязателен. Отдача из АКБ ночью оплачивается "
                            "по меньшей из цен: тариф или РДН (в расчёте не учтена)."))
    return out


def sun_summary(region, gen_avg, factors, kwp):
    """Погода региона за 5 лет: ясные / переменные / пасмурные дни, часы солнца, выработка на 1 кВт·п по годам."""
    st = (region or {}).get("stats")
    if not st:
        return None
    month = {k: list(st[k]) for k in ("sunny", "partly", "cloudy", "sunday", "sun_h", "ghi")}
    per_kwp = [sum(gen_avg[m]) / kwp if kwp > 0 else 0.0 for m in range(12)]
    by_year = [(lab, [per_kwp[m] * f[m] for m in range(12)]) for lab, f in factors]
    month["y_avg"] = per_kwp
    month["y_min"] = [min(v[m] for _l, v in by_year) for m in range(12)]
    month["y_max"] = [max(v[m] for _l, v in by_year) for m in range(12)]
    annual = {k: sum(month[k]) for k in month}
    totals = [sum(v) for _l, v in by_year]
    annual["y_min"], annual["y_max"] = min(totals), max(totals)
    return {"month": month, "annual": annual, "per_year": list(zip([lab for lab, _v in by_year], totals))}


# ───────────────────────────── отчёт ─────────────────────────────
def report_html(d):
    """Отчёт HTML (для печати / отправки): d — словарь страницы (g, s, st, b, e, checks, sun, reg, osr, place, ver)."""
    g, s, st, b, e = d["g"], d["s"], d["st"], d["b"], d["e"]
    esc = htmlmod.escape
    yrs = e["years"]
    conn = dict(CONN_OPTIONS).get(g["conn"], "")
    phase = dict(PHASES).get(g["phase"], "")
    mount = dict(MOUNTS).get(g["mount"], "")
    meter = dict(METER_TYPES).get(g["meter_zones"], "")
    brows = "".join(f"<tr><td>{esc(r['name'])}</td><td>{esc(r['payee'])}</td>"
                    f"<td class='n'>{fnum(r['mn'])}</td><td class='n'>{fnum(r['mx'])}</td></tr>"
                    for r in b["rows"] if r["on"])
    mrows = "".join(f"<tr><td>{r['month']}</td><td class='n'>{fnum(r['gen'])}</td><td class='n'>{fnum(r['cons'])}</td>"
                    f"<td class='n'>{fnum(r['exp'])}</td><td class='n'>{fnum(r['buy'])}</td>"
                    f"<td class='n'>{fnum(r['save'])}</td><td class='n'>{fnum(r['inc'])}</td></tr>" for r in e["rows"])
    chk = "".join(f"<li class='{lv}'>{esc(t)}</li>" for lv, t in d["checks"])
    pb = (f"{fpb(e['pb_min'], yrs)} – {fpb(e['pb_max'], yrs)} лет" if e["pb_min"] is not None
          else f"не окупается за {yrs} лет")
    steps = "".join(f"<h3>{esc(sec)}</h3><ul class='steps'>" +
                    "".join(f"<li>{'☑' if g['checklist'].get(t) else '☐'} {esc(t)}</li>" for t in items) + "</ul>"
                    for sec, items in STEPS)
    notes = f"<h2>Заметки</h2><p class='pre'>{esc(g['notes'])}</p>" if g.get("notes", "").strip() else ""
    sun = d.get("sun")
    if sun:
        a, mo = sun["annual"], sun["month"]
        srows = "".join(f"<tr><td>{MONTHS_S[m]}</td><td class='n'>{fnum(mo['sunny'][m])}</td>"
                        f"<td class='n'>{fnum(mo['partly'][m])}</td><td class='n'>{fnum(mo['cloudy'][m])}</td>"
                        f"<td class='n'>{fnum(mo['sun_h'][m])}</td><td class='n'>{fnum(mo['y_avg'][m])}</td>"
                        f"<td class='n'>{fnum(mo['y_min'][m])}–{fnum(mo['y_max'][m])}</td></tr>" for m in range(12))
        yrows = "".join(f"<tr><td>{esc(str(lab))}</td><td class='n'>{fnum(v)}</td></tr>" for lab, v in e["year_totals"])
        sun_html = (f"<h2>Солнце: погода {esc(d.get('reg_years', ''))}</h2>"
                    f"<p class='muted'>{esc(d.get('reg_src', ''))}, точка {s['lat']}, {s['lon']}.</p>"
                    f"<div class='kpi'><div>Дней с солнцем<b>{fnum(a['sunday'])}</b></div>"
                    f"<div>Ясных / пасмурных<b>{fnum(a['sunny'])} / {fnum(a['cloudy'])}</b></div>"
                    f"<div>Часов солнца<b>{fnum(a['sun_h'])}</b></div>"
                    f"<div>На 1 кВт·п<b>{fnum(a['y_avg'])} кВт·ч</b></div></div>"
                    f"<table><tr><th>Месяц</th><th class='n'>Ясных</th><th class='n'>Переменных</th>"
                    f"<th class='n'>Пасмурных</th><th class='n'>Часов солнца</th><th class='n'>На 1 кВт·п</th>"
                    f"<th class='n'>Мин–макс</th></tr>{srows}</table>"
                    f"<table><tr><th>Год</th><th class='n'>Выработка станции, кВт·ч</th></tr>{yrows}</table>")
    else:
        sun_html = ("<h2>Солнце</h2><p class='muted'>Погода региона за 5 лет не загружена — выработка по среднему "
                    "году из расчёта станции.</p>")
    zones = " · ".join(f"{esc(n)}: {fnum(v, 2)}" for n, v in zip(e["zones"], e["zprices"]))
    css = ("body{font-family:'Segoe UI',Arial,sans-serif;color:#18202e;max-width:920px;margin:32px auto;"
           "padding:0 16px;line-height:1.45}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}"
           "h3{font-size:14px;margin:14px 0 4px}.muted{color:#5c6779}table{border-collapse:collapse;width:100%;"
           "margin:8px 0 12px}th,td{padding:6px 8px;border-bottom:1px solid #e3e7ee;text-align:left}"
           "th{background:#f5f7fa;font-weight:600}.n{text-align:right;white-space:nowrap}"
           "tr.total td{font-weight:700;border-top:2px solid #18202e}.kpi{display:flex;gap:12px;flex-wrap:wrap;"
           "margin:18px 0}.kpi div{flex:1;min-width:170px;border:1px solid #e3e7ee;border-radius:10px;"
           "padding:10px 14px}.kpi b{display:block;font-size:20px;margin-top:2px}li.err{color:#dc2626}"
           "li.warn{color:#b45309}li.ok{color:#047857}li.info{color:#2563eb}ul.steps{list-style:none;"
           "padding-left:4px}.pre{white-space:pre-wrap}")
    return (
        f"<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Расчёт СЭС — зелёный тариф</title><style>{css}</style></head><body>"
        f"<h1>Домашняя СЭС под зелёный тариф</h1>"
        f"<p class='muted'>{esc(d['region'])} · {esc(str(s.get('place', '')))} · {fkw(b['kwp'])} кВт·п · "
        f"{esc(mount)} · тариф {fnum(g['green'], 3)} грн/кВт·ч до 2029 г. · Солнечный калькулятор v{esc(d['ver'])}, "
        f"{time.strftime('%d.%m.%Y')}</p>"
        f"<div class='kpi'><div>Бюджет<b>{frange(b['mn'], b['mx'])}</b></div>"
        f"<div>В ОСР (РЭС)<b>{frange(b['osr_mn'], b['osr_mx'])}</b></div>"
        f"<div>Польза в год до 2030<b>{fnum(e['b_green'])} грн</b></div>"
        f"<div>Окупаемость<b>{pb}</b></div></div>"
        f"<h2>Станция</h2><table>"
        f"<tr><td>Панели</td><td>{st['npan']} шт = {fkw(b['kwp'])} кВт·п, {esc(mount)}</td></tr>"
        f"<tr><td>Инвертор</td><td>{esc(d['inv_name'])}, {fkw(st['inv_kw'])} кВт</td></tr>"
        f"<tr><td>Аккумуляторы</td><td>{fkw(round(st['bat_kwh'], 1))} кВт·ч</td></tr>"
        f"<tr><td>Подключение</td><td>{esc(conn)}; {esc(phase)}; разрешено "
        f"{fkw(g['permitted']) + ' кВт' if g['permitted'] > 0 else 'не указано'}; ОСР: {esc(d['osr'])}</td></tr>"
        f"<tr><td>Плата ОСР (оценка)</td><td>{esc(b['conn']['text'])}</td></tr>"
        f"<tr><td>Учёт</td><td>{esc(meter)}: {zones} грн/кВт·ч</td></tr>"
        f"<tr><td>Выработка</td><td>{fnum(e['gen'])} кВт·ч в год ({esc(d['gen_src'])})</td></tr>"
        f"<tr><td>Потребление</td><td>{fnum(e['cons'])} кВт·ч в год (дом + холостой ход инвертора)</td></tr></table>"
        f"<h2>Проверки</h2><ul>{chk}</ul>{sun_html}"
        f"<h2>Смета</h2><table><tr><th>Статья</th><th>Кому платим</th><th class='n'>Мин, грн</th>"
        f"<th class='n'>Макс, грн</th></tr>{brows}<tr class='total'><td>ИТОГО</td><td></td>"
        f"<td class='n'>{fnum(b['mn'])}</td><td class='n'>{fnum(b['mx'])}</td></tr></table>"
        f"<p class='muted'>Цены — ориентиры рынка 2026 г. В ОСР платить только по официальному счёту.</p>"
        f"<h2>Окупаемость</h2><table>"
        f"<tr><td>Экономия на счетах</td><td class='n'>{fnum(e['save'])} грн</td></tr>"
        f"<tr><td>Доход от продажи до налога</td><td class='n'>{fnum(e['gross'])} грн</td></tr>"
        f"<tr><td>Налог {fkw(g['tax'])} %</td><td class='n'>−{fnum(e['tax'])} грн</td></tr>"
        f"<tr><td>Польза в год по зелёному тарифу ({e['green_years']} г.)</td>"
        f"<td class='n'>{fnum(e['b_green'])} грн</td></tr>"
        f"<tr><td>Польза в год после 2029 (продажа по {fnum(g['post_price'], 2)} грн)</td>"
        f"<td class='n'>{fnum(e['b_post'])} грн</td></tr>"
        + (f"<tr><td>Без продажи в сеть (только своё потребление)</td><td class='n'>{fnum(d['e_self']['benefit'])} "
           f"грн/год, окупаемость {fpb(d['e_self']['pb_mid'], yrs)}"
           f"{' г.' if d['e_self']['pb_mid'] is not None else ''}</td></tr>" if d.get("e_self") else "")
        + f"<tr class='total'><td>Чистая выгода за {yrs} лет (средний бюджет)</td>"
        f"<td class='n'>{fnum(e['profit'])} грн</td></tr></table>"
        f"<table><tr><th>Месяц</th><th class='n'>Выработка</th><th class='n'>Потребление</th>"
        f"<th class='n'>В сеть</th><th class='n'>Из сети</th><th class='n'>Экономия, грн</th>"
        f"<th class='n'>Доход, грн</th></tr>{mrows}</table>"
        f"<h2>Шаги и документы</h2>{steps}{notes}"
        f"<p class='muted'>Зелёный тариф: НКРЭКУ № 1613, с 01.10.2026; до 01.01.2030. Присоединение: НКРЭКУ "
        f"№ 2230 (2026). Налог: 18 % НДФЛ + 5 % военный сбор. Погода: Open-Meteo / PVGIS. "
        f"Расчёт ориентировочный.</p></body></html>")
