"""solar_calc.py  v1.11.3
Солнечный калькулятор — точка входа: авто-установка библиотек, запуск окна, --selftest.
Расчёт: солнце → угол/азимут → панели → схема Ns×Np → провод и контакты → MPPT (встроенный в инвертор
или отдельный) → ток заряда → АКБ → инвертор. Данные солнца: встроенные (≈Киев) или PVGIS.

Структура:
  solar_calc.pyw        запуск двойным щелчком (без консоли)
  solar_calc.py         этот файл: версия, библиотеки, main(), --selftest
  solar_calc_qt.py      главное окно
  modules/mod_*.py      расчёт, данные, оборудование, виджеты, страницы
  modules/panels_db.tsv.gz  полная база панелей (CEC + паспорта серий)
  modules/mod_region.py погода региона за 5 лет (Open-Meteo / PVGIS-SARAH3)
  modules/mod_green.py  зелёный тариф (Украина): смета, ОСР, взаимозачёт, окупаемость; страница — mod_page_green
  modules/gh_update*.py обновление с GitHub (общий модуль gh_update): страница «🔄 Обновление»

Журнал:
v1.11.3: обновление с GitHub (gh_update 1.2.0): старый код, которого нет в новой версии, стирается;
        резервной папки backup больше нет; настройки не трогает.
v1.11.2: Обновление: модуль gh_update 1.1.3 — в облаке анимации значок GitHub над надписью; архив
        докачивается при обрыве.
v1.11.1: обновление модуля gh_update 1.1.1: «Что нового» из журнала проекта (шапка solar_calc.py); инструкция
        «Как получить токен» — шаги 7 и 8 без обрезки и с настоящим файлом версии.
v1.11.0: обновление с GitHub (общий модуль gh_update 1.1.0): страница «🔄 Обновление» на боковой панели — токен
        «только чтение», ветка, автопроверка (через 30 с и раз в 12 ч), анимация скачивания, резервная копия в
        backup/, перезапуск; нашлась новая версия — «⬆» на боковой панели и «⬆ X.Y.Z» в строке состояния;
        инструкция «Как получить токен» с картинками. Настройки, профили и журналы при обновлении не трогаются.
v1.10.0: страница «💰 Зелёный тариф» — из «Калькулятора зелёного тарифа» v1.2.0, связана со станцией: панели,
        инвертор, АКБ, часовая выработка и потребление дома — из ⚙ Настроек (не вводятся второй раз). Вкладки:
        подключение и проверки (область/ОСР авто по координатам, ставки НКРЭКУ 2026, экспорт по модели
        инвертора), окупаемость (зоны 1/2/3, взаимозачёт, налог, тариф до 2030, деградация, худший год погоды,
        без продажи), смета, цены, солнце за 5 лет, документы и шаги; отчёт HTML, CSV. Погода региона:
        источник PVGIS-SARAH3, ясные / пасмурные дни, часы солнца, солнце по месяцам каждого года.
        Раскладка — одна страница: настройки группами слева, результат лентой справа, без пустых окон.
        Страница «🔀 Сравнение схем S×P» убрана.
v1.9.16: инверторы Deye — 50 моделей (+35): однофазные 3–10 кВт (SG04LP1, SG05LP1, SG05LP1-SM2, SG02LP1),
        3K на 24 В, автономные OG01LP1, трёхфазные SG05LP3-SM2 3–20 кВт.
v1.9.15: в базе панелей — Jinko 48HL4M-DB 450–475, Resun RSM180M; Trina NEG19RC.20 595–625 по паспорту 2024B.
v1.9.14: Trina Vertex N TSM-NEG21C.20 700–725 Вт сверены с паспортом 2025 (γ, NOCT, 725 Вт).
v1.9.13: в базе панелей — Risen RSM132-11-605…630BNDG (TOPCon) по паспорту.
v1.9.12: в базе панелей — LONGi Hi-MO X10 LR7-72HVD 640–665 Вт; Jinko 72HL4-BDV 595/600 — по паспорту.
v1.9.11: Risen RSM144-9-xxxM сверены с паспортом (535–555 Вт — все значения, γ −0.34 %/°C).
v1.9.10: в базе панелей — серия Risen RSM144-9-535M…560M (Titan, 144 полуячейки PERC).
v1.9.9: несколько полей на один вход MPPT инвертора (или один контроллер) — разные панели, стороны и углы:
        правый клик по полю → «⇄ Вход MPPT» / «＋ Поле параллельно»; расчёт по вольт-амперным характеристикам
        цепочек при общем напряжении, проверки «как поведут себя» за год (потери, срезка током, обратный ток).
v1.9.8: база дополнена топом продаж в Украине (hotline, ek.ua, prom, OLX, Rozetka — осень 2026): +6 панелей
        (LONGi Hi-MO 7 LR8-66HGD 615, Hi-MO X6 LR7-72HTH 615, Hi-MO 5m 410; JA JAM54D41-460/LR; Jinko
        JKM380N-6TL3-V; ReneSola RS6-580N) и +6 инверторов (Deye SUN-8K-SG05LP1-EU, Anern EVO-6200 и
        FGI-S12000, EASun SMH-III-6.2KW, Must PH18-5048 PRO, PV18-2012 PRO).
v1.9.7: полная проверка кода (pyflakes, pylint, vulture, ручной разбор, тесты на каждый баг). Исправлено:
        «🗑 Убрать» на боковой панели убирал не то; схема падала при узлах впритык; запуск из папки без прав на
        запись (лог) и с битым config.json (Infinity, объекты, null в данных солнца) падал; config/профиль с BOM
        не открывались; колесо мыши над списками меняло значения при прокрутке; заряд гибрида + отдельного MPPT
        складывался (гибрид заряжал сверх своего тока); потери кабелей контроллеров — через один общий кабель;
        кабель отдельного MPPT → АКБ у гибрида не проверялся; Voc 158 панелей базы обрезался после перезапуска;
        допустимый ток кабелей > 95 мм² завышен; копия поля, инвертор без MPPT, «занято k из N», провод
        MPPT → АКБ на странице «Провода», сохранение без расширения, окно неба и поиска не освобождались.
        Убран мёртвый код (неиспользуемые функции, константы, ключи, ветки).
v1.9.6: станция по умолчанию: поля 1 и 2 — 20°, точно на юг (поле 3 на отдельном MPPT — 15°).
v1.9.5: схема по умолчанию — точно как на скриншоте пользователя: поле 2 (MPPT 2) слева, поле 1 (MPPT 1) справа
        рядом с отдельным MPPT; дом и АКБ на одной высоте под инвертором.
v1.9.4: погода «📍 Регион 5 лет» — реальная погода за последние 5 полных лет для точки станции (архив Open-Meteo):
        средний день каждого месяца, карточка и линия на графиках, год по региону; загрузка сама при выборе.
        Схема по умолчанию: поля над инвертором, отдельные MPPT справа, сеть и дом слева, АКБ под инвертором.
v1.9.3: на схеме нет пунктирных «＋»: добавлять (поле на вход MPPT, отдельный MPPT, сборку АКБ, копию поля) —
        только правым кликом на схеме. Линии схемы аккуратнее: напротив стоящий блок — прямой линией, дорожки
        не перекрещиваются, отдельные MPPT подходят к линии АКБ каждый своей точкой, не сквозь соседей.
v1.9.2: убран переключатель «MPPT встроенный / отдельный»: у гибрида свои входы MPPT — поля подключаются к ним,
        отдельный MPPT — отдельный прибор на линии АКБ (что куда — выбирается на схеме). Старые настройки «гибрид +
        отдельный» переводятся сами. Правый клик → «🗑 Убрать» у отдельного MPPT, поля 1 и сборки 1. Линии схемы —
        по правилам Smart_BMS: сторона входа по зазору между блоками, свои дорожки, обход чужих блоков, без
        перекрёстков; входы MPPT отмечены там, где входит линия; подписи кабелей не прячутся под блоки. Поля ввода
        справа различимы (светлее фона, с рамкой).
v1.9.1: схему конструктора можно расставить мышью — узлы перетаскиваются, линии идут следом, места
        запоминаются (в настройках и профиле); меню «↺ Вернуть на место» / «↺ Расставить всё автоматически».
v1.9.0: «Моя станция» — конструктор: во главе инвертор; поля панелей на его входах MPPT (разные панели, схема,
        угол и азимут у каждого поля); отдельные MPPT-контроллеры со своими полями — к линии АКБ → инвертор
        (до 6); до 6 сборок АКБ на шине; дом и горсеть. Клик по узлу — его настройки справа, «＋» — добавить,
        правый клик — меню (копия поля, убрать, картинка/текст схемы). Расчёт и прогноз — по всем полям.
v1.8.0: входы MPPT видны везде (сколько панелей на каждый вход, занято/свободно); +27 инверторов 8–16 кВт
        (11 кВт с 2 MPPT); понятная карточка кабелей; профиль станции «моя_станция_Краматорск.json».
v1.7.0: разные сборки АКБ параллельно («＋ Другая сборка», до 5); поля «Моя станция» не растягиваются на всё окно.
v1.6.0: инверторы на 12 и 24 В — +126 моделей (гибриды и без MPPT); выбор инвертора по напряжению АКБ.
v1.5.1: АКБ задаются сборками (1–10): в сборке последовательно — по напряжению системы; старые настройки
        «всего штук» переводятся в сборки.
v1.5.0: полная база панелей — 21,7 тыс. моделей, 260 производителей (CEC/NREL + паспорта популярных серий);
        выбор панели «производитель → серия → мощность», 🔎 поиск по базе; самопроверка базы.
v1.4.0: погода (Open-Meteo), небо (Солнце, Луна, звёзды, созвездия) и прогноз выработки по погоде —
        из Smart_BMS 4.81, согласовано со станцией: одна формула Солнца (NOAA) для расчёта и неба,
        место и пояс (с летним временем ЕС) — из настроек, наклон и азимут панелей — станции.
v1.3.0: программа разбита на модули; карточка «Моя станция» (панели × шт, инвертор, MPPT встроенный
        или отдельный — карточка MPPT только для отдельного), гибридные инверторы с MPPT-входами,
        расширенная база панелей, инверторов, MPPT-контроллеров и АКБ.
v1.2.1: исправления по полной проверке — пустые числовые поля на PySide6 6.12, верх окна MPPT,
        гистерезис возврата на АКБ, проверка config/профилей, ошибки записи файлов, excepthook.
v1.2.0: страницы Настройки, Прогноз, Покрытие дома, Горсеть; заряд АКБ по 10 минутам, тариф, серия дней.
v1.1.0: инвертор, провода к АКБ и инвертору, аккумуляторы, потребление дома, баланс, автономия.
v1.0.0: первая версия — солнце (встроенное + PVGIS), схемы Ns×Np, провод, окно MPPT, потери по этапам.
"""
APP_NAME = "Солнечный калькулятор"
VERSION = "1.11.3"

import sys
import os
import importlib
import importlib.util
import subprocess
from pathlib import Path

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
import logging
import traceback

from modules.mod_base import APP_ROOT, log, _fh
from modules.mod_config import DEFAULT_CONFIG, DEFAULT_SYS
from modules.mod_sun import SunData
from modules.mod_model import compute_all

MODULES = ("modules.mod_base", "modules.mod_panels", "modules.mod_equipment", "modules.mod_sun",
           "modules.mod_fields", "modules.mod_config", "modules.mod_model", "modules.mod_checks",
           "modules.mod_pvgis", "modules.mod_theme", "modules.mod_widgets", "modules.mod_page_settings",
           "modules.mod_page_results", "modules.mod_page_tools", "modules.mod_astro", "modules.mod_stars",
           "modules.mod_weather", "modules.mod_forecast", "modules.mod_wx_draw", "modules.mod_sky",
           "modules.mod_page_sky", "modules.mod_constructor", "modules.mod_region", "modules.mod_green",
           "modules.mod_page_green", "solar_calc_qt")


def _excepthook(tp, val, tb):
    """Необработанная ошибка (в т.ч. в слотах Qt): под pythonw консоли нет — пишем в лог."""
    log.error(f"✗ Ошибка программы: {tp.__name__}: {val}")
    try:
        if _fh is not None:
            _fh.emit(logging.makeLogRecord({"msg": "".join(traceback.format_exception(tp, val, tb)).rstrip(),
                                            "levelno": logging.ERROR, "levelname": "ERROR"}))
    except Exception:
        pass


def selftest():
    lines, ok = [f"{APP_NAME} v{VERSION}"], True
    try:
        import PySide6
        lines.append(f"PySide6 {PySide6.__version__}: OK")
    except Exception as e:
        ok = False
        lines.append(f"PySide6: ОШИБКА {e}")
    for name in MODULES:
        try:
            mod = importlib.import_module(name)
            ver = (mod.__doc__ or "").split("\n", 1)[0].split()[-1:] or ["?"]
            lines.append(f"{name} {ver[0]}: OK")
        except Exception as e:
            ok = False
            lines.append(f"{name}: ОШИБКА {e}")
    try:
        from modules.mod_panels import PANEL_DB, DB_FILE
        n = len(PANEL_DB)
        if n < 1000:
            raise RuntimeError(f"всего {n} моделей — файл {DB_FILE.name} не прочитан")
        lines.append(f"База панелей: {n} моделей, {len({v[0] for v in PANEL_DB.values()})} производителей: OK")
    except Exception as e:
        ok = False
        lines.append(f"База панелей: ОШИБКА {e}")
    try:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        R = compute_all(dict(DEFAULT_SYS), SunData(cfg))
        lines.append(f"Расчёт: год {R['year']['avg']:.0f} кВт·ч, декабрь средне {R['res'][(11, 'avg')]['wh'][8]:.0f} Вт·ч/сут: OK")
        from modules import mod_green as G
        s = dict(DEFAULT_SYS)
        g = G.green_clean(None)
        st = G.station_info(R["ctx"], s)
        b = G.calc_budget(g, st, G.place_of(g, s)[1], False)
        house, idle = G.cons_bins(R["ctx"])
        cons = [[house[m][h] + idle[m][h] for h in range(24)] for m in range(12)]
        e = G.calc_econ(g, float(s["tariff"]), b, G.gen_bins(R, "avg"), G.year_factors(None, False), cons)
        if not (b["mn"] > 0 and e["gen"] > 0 and len(e["cum"]) == g["years"]):
            raise RuntimeError("пустой расчёт")
        pb = f"{G.fnum(e['pb_mid'], 1)} г." if e["pb_mid"] is not None else f"> {e['years']} лет"
        lines.append(f"Зелёный тариф: бюджет {G.frange(b['mn'], b['mx'])}, окупаемость {pb}: OK")
    except Exception as e:
        ok = False
        lines.append(f"Расчёт: ОШИБКА {e}")
    try:
        from modules import gh_update, gh_update_qt, gh_update_help
        if not (gh_update.newer("1.10.0", "1.9.16") and gh_update_qt.UpdatePage and gh_update_help.TokenHelpDialog):
            raise RuntimeError("сравнение версий")
        lines.append(f"Обновление с GitHub (gh_update {gh_update.VERSION}): OK")
    except Exception as e:
        ok = False
        lines.append(f"Обновление с GitHub: ОШИБКА {e}")
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
    sys.excepthook = _excepthook
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("solar_calc")
        except Exception:
            pass
    from PySide6.QtCore import QTranslator, QLibraryInfo, QLocale
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    # после обновления: подождать, пока старая копия закроется
    from modules import gh_update
    gh_update.wait_previous(sys.argv)
    app.setStyle("Fusion")
    QLocale.setDefault(QLocale(QLocale.Russian, QLocale.Ukraine))
    tr = QTranslator(app)
    if tr.load(QLocale(QLocale.Russian), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
    from solar_calc_qt import App
    w = App()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
