"""solar_calc.py  v1.12.0
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
  app_icon*.py, app_icon_pack.dat  значок программы (общий модуль app_icon): окно выбора — «🎨 Цвета»

Журнал:
v1.12.0: значок программы: окно выбора (общий модуль app_icon 1.2.0) — «🎨 Цвета» → «Тема» →
        «🎨 Значок программы…»; встроенная база ~370 значков, поиск в интернете, своя картинка; .ico и
        ярлыки. Выбор — в app_icon.json рядом с программой; не выбирали — всё как раньше. --selftest
        проверяет модуль и окно выбора.
v1.11.10: порядок в modules/ после обновления: код программы лежит в modules/, а модуль обновления эту
        папку не чистит (у других программ она — своя у пользователя), и файлы, убранные из программы,
        оставались навсегда. Теперь при запуске они переносятся в _other/modules/ (mod_cleanup.py) —
        не стираются. Работает только после обновления с GitHub, не в копии из git и не в EXE.
v1.11.9: обновление с GitHub: общий модуль gh_update 1.5.3 (один на все программы) — неполный архив
        не ставится (раньше мог стереть по списку почти всю программу); копия из git не обновляется (в ней —
        git pull); «можно ли ставить» проверяется ещё раз после скачивания; скачивание при выходе из
        программы бросается; кривой токен не попадает в журнал; свои папки tools/ и modules/ не чистятся и
        по списку файлов. test_gh_update.pyw — общий тест 1.5.3.
v1.11.8: порядок: журнал — последние 10 версий (здесь, в шапке solar_calc.py); одно описание README.md
        (README.txt слит и убран, у пользователя стирается при запуске); модуль обновления gh_update 1.4.3
        (замена файла с повтором, если он на миг занят антивирусом; маски в разовой чистке);
        test_gh_update.pyw — общий тест 1.4.3 (сам находит modules/).
v1.11.7: обновление с GitHub: общий модуль gh_update 1.4.2 — свои папки tools/ и modules/ никогда не чистятся;
        копия из git (.git рядом) старый код не чистит;
        занятый список файлов — не повод чистить;
        исчерпан лимит запросов GitHub — понятное сообщение, а не «токен не видит репозиторий»;
        вышла новая версия, пока окно было открыто, — понятное сообщение вместо 404;
        окно во время простой проверки версии закрывается (держит только скачивание/установка).
v1.11.6: Python 3.12+: убрана совместимость со старым Python (README, build_exe.bat — нужен
        Python 3.12+, было 3.10+), код очищен автоправкой (кодировка в шапке, datetime.UTC),
        PySide6 ≥ 6.10.1 (было ≥ 6.5), gh_update 1.4.1.
v1.11.5: обновление — только Python: убрано обновление собранного exe (gh_update 1.4.0),
        GitHub больше не собирает exe.
v1.11.4: обновление с GitHub: общий модуль gh_update 1.3.3 (обрыв ответа GitHub — понятная ошибка,
        при сбое замены не остаётся *.upd, свои файлы пользователя не стираются, та же версия
        после установки не предлагается снова).
v1.11.3: обновление с GitHub (gh_update 1.2.0): старый код, которого нет в новой версии, стирается;
        резервной папки backup больше нет; настройки не трогает.
v1.11.2: Обновление: модуль gh_update 1.1.3 — в облаке анимации значок GitHub над надписью; архив
        докачивается при обрыве.
Более ранние версии — в истории git.
"""
APP_NAME = "Солнечный калькулятор"
VERSION = "1.12.0"

import sys
import os
import importlib
import importlib.util
import subprocess
from pathlib import Path

REQUIRED = (("PySide6", "PySide6>=6.10.1"),)


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
           "modules.mod_page_green", "modules.mod_cleanup", "solar_calc_qt")


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
        lines.append(_selftest_cleanup())
    except Exception as e:
        ok = False
        lines.append(f"Обновление с GitHub: ОШИБКА {e}")
    try:
        lines.append(_selftest_icon())
    except Exception as e:
        ok = False
        lines.append(f"Значок программы (app_icon): ОШИБКА {e}")
    lines.append("ИТОГ: " + ("OK" if ok else "ОШИБКА"))
    txt = "\n".join(lines)
    print(txt)
    try:
        (APP_ROOT / "selftest.txt").write_text(txt, encoding="utf-8")
    except Exception:
        pass
    return 0 if ok else 1


def _selftest_icon():
    """Общий модуль app_icon: рисунки и .ico; окно выбора открывается и закрывается (без экрана)."""
    import tempfile
    if os.name != "nt":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv[:1])
    import app_icon
    import app_icon_qt
    errs = app_icon.selftest()
    if errs:
        raise RuntimeError("; ".join(errs[:3]))
    with tempfile.TemporaryDirectory(prefix="solar_icon_") as d:
        dlg = app_icon_qt.IconDialog(app_icon.AppIcon("solar_calc", d))
        QTimer.singleShot(0, dlg.reject)
        dlg.exec()
    app.processEvents()
    return f"Значок программы (app_icon {app_icon.VERSION}): OK"


def own_modules():
    """Файлы запущенной версии в modules/ — их уборка не трогает."""
    names = [m.split(".", 1)[1] + ".py" for m in MODULES if m.startswith("modules.")]
    return names + ["gh_update.py", "gh_update_qt.py", "gh_update_help.py", "__init__.py"]


def _selftest_cleanup():
    """Уборка modules/ на временной папке: старое — в _other/, своё и данные — на месте."""
    import tempfile
    from modules import gh_update, mod_cleanup
    with tempfile.TemporaryDirectory(prefix="solar_st_") as d:
        m = os.path.join(d, "modules")
        os.makedirs(m)
        for fn in ("mod_base.py", "mod_old.py", "data.tsv.gz"):
            Path(m, fn).write_text("# " + fn, encoding="utf-8")
        need = ["mod_base.py"]
        if mod_cleanup.sweep_modules(d, need):                      # списка нет — не трогаем
            raise RuntimeError("уборка без списка установленного")
        gh_update.write_manifest(d, ["solar_calc.py"])
        if mod_cleanup.sweep_modules(d, need):                      # список старее программы
            raise RuntimeError("уборка по устаревшему списку")
        gh_update.write_manifest(d, ["solar_calc.py", "modules/mod_base.py"])
        got = mod_cleanup.sweep_modules(d, need)
        left = sorted(os.listdir(m))
        if got != ["modules/mod_old.py"] or left != ["data.tsv.gz", "mod_base.py"] \
                or not os.path.isfile(os.path.join(d, "_other", "modules", "mod_old.py")):
            raise RuntimeError(f"уборка modules/: {got}, осталось {left}")
        Path(m, "mod_old.py").write_text("# другой", encoding="utf-8")   # то же имя, другое содержимое
        mod_cleanup.sweep_modules(d, need)
        if sorted(os.listdir(os.path.join(d, "_other", "modules"))) != ["mod_old.py", "mod_old_1.py"]:
            raise RuntimeError("уборка modules/: одноимённый файл не сохранён")
        os.makedirs(os.path.join(d, ".git"))
        Path(m, "mod_dev.py").write_text("# dev", encoding="utf-8")
        if mod_cleanup.sweep_modules(d, need):                      # копия из git — не трогаем
            raise RuntimeError("уборка в копии из git")
    return "Уборка modules/ (в _other/): OK"


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
    try:                                   # v1.11.10: убранное из программы — из modules/ в _other/modules/
        from modules import mod_cleanup
        mod_cleanup.sweep_modules(str(APP_ROOT), own_modules(), log=log.info)
    except Exception as e:
        log.warning(f"⚠ уборка modules/: {e}")
    app.setStyle("Fusion")
    QLocale.setDefault(QLocale(QLocale.Russian, QLocale.Ukraine))
    tr = QTranslator(app)
    if tr.load(QLocale(QLocale.Russian), "qtbase", "_", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        app.installTranslator(tr)
    from solar_calc_qt import App, icon_chosen, make_icons
    try:                                   # свой значок (app_icon.json) → окно и solar_calc.ico
        app.app_icons = make_icons()
        if icon_chosen(app.app_icons):
            app.app_icons.ensure()
            app.setWindowIcon(app.app_icons.icon())
    except Exception as e:
        log.warning(f"⚠ Значок программы: {e}")
    w = App()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
