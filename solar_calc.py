"""solar_calc.py  v1.9.0
Солнечный калькулятор — точка входа: авто-установка библиотек, запуск окна, --selftest.
Расчёт: солнце → угол/азимут → панели → схема Ns×Np → провод и контакты → MPPT (встроенный в инвертор
или отдельный) → ток заряда → АКБ → инвертор. Данные солнца: встроенные (≈Киев) или PVGIS.

Структура:
  solar_calc.pyw        запуск двойным щелчком (без консоли)
  solar_calc.py         этот файл: версия, библиотеки, main(), --selftest
  solar_calc_qt.py      главное окно
  modules/mod_*.py      расчёт, данные, оборудование, виджеты, страницы
  modules/panels_db.tsv.gz  полная база панелей (CEC + паспорта серий)

Журнал:
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
VERSION = "1.9.0"

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
           "modules.mod_page_sky", "modules.mod_constructor", "solar_calc_qt")


def _excepthook(tp, val, tb):
    """Необработанная ошибка (в т.ч. в слотах Qt): под pythonw консоли нет — пишем в лог."""
    log.error(f"✗ Ошибка программы: {tp.__name__}: {val}")
    try:
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
