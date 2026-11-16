"""mod_cleanup.py  v1.11.10
Порядок в папке modules/ после обновления с GitHub.

Журнал:
v1.11.10: новый модуль. Код программы лежит в modules/, а общий модуль обновления считает эту папку
        своей у пользователя и старые файлы в ней не убирает. sweep_modules() при запуске переносит
        в _other/modules/ файлы кода, которых нет в установленной версии. Ничего не стирает.

Правила (осторожно, чтобы не сломать программу):
  - только после обновления с GitHub (есть список .gh_update_files.txt), не в EXE и не в копии из git;
  - список должен знать все модули запущенной версии — иначе он устарел (архив распаковали руками),
    и ничего не трогаем;
  - модули запущенной версии, __init__.py и данные (не код) не трогаем никогда;
  - файл не стирается, а переносится в _other/modules/; там уже лежит такой же — лишний убираем,
    лежит другой с тем же именем — кладём рядом под именем с номером (оба остаются).
"""
import filecmp
import os

OTHER = "_other"


def _free_name(dst):
    """Свободное имя рядом с dst: mod_x.py -> mod_x_1.py, mod_x_2.py …"""
    stem, ext = os.path.splitext(dst)
    i = 1
    while os.path.exists(f"{stem}_{i}{ext}"):
        i += 1
    return f"{stem}_{i}{ext}"


def sweep_modules(app_dir, needed, log=None, sub="modules"):
    """Перенести из <app_dir>/<sub>/ в _other/<sub>/ файлы кода, которых нет в установленной версии.
    needed — имена файлов запущенной версии в этой папке («mod_base.py» …): их не трогаем, и все они
    должны быть в списке установленного. -> что перенесено (пути через «/»)."""
    from modules import gh_update as gu
    app_dir = os.path.abspath(app_dir)
    root = os.path.join(app_dir, sub)
    if gu.is_frozen() or gu.is_git_copy(app_dir) or not os.path.isdir(root):
        return []
    known = gu.read_manifest(app_dir)
    if not known:                                    # списка нет или он не прочитался
        return []
    low = {k.replace("\\", "/").lower() for k in known}
    keep = {n.lower() for n in needed} | {"__init__.py"}
    if any(f"{sub}/{n}".lower() not in low for n in needed):
        return []                                    # список старее программы — не верим ему
    out = []
    for fn in sorted(os.listdir(root)):
        src = os.path.join(root, fn)
        if not os.path.isfile(src) or fn.lower() in keep:
            continue
        if os.path.splitext(fn)[1].lower() not in (".py", ".pyw"):
            continue                                 # данные и прочее — не наше дело
        if f"{sub}/{fn}".lower() in low:
            continue
        try:
            ddir = os.path.join(app_dir, OTHER, sub)
            os.makedirs(ddir, exist_ok=True)
            dst = os.path.join(ddir, fn)
            if os.path.exists(dst):
                if filecmp.cmp(src, dst, shallow=False):
                    os.remove(src)                   # такой же уже перенесён
                    out.append(f"{sub}/{fn}")
                    continue
                dst = _free_name(dst)                # другой с тем же именем — оставить оба
            os.replace(src, dst)
            out.append(f"{sub}/{fn}")
        except OSError:
            continue                                 # занят — в следующий запуск
        pyc = os.path.join(root, "__pycache__")
        if os.path.isdir(pyc):                       # кэш Python перенесённого модуля
            stem = os.path.splitext(fn)[0]
            for x in os.listdir(pyc):
                if x.split(".", 1)[0] == stem and x.endswith((".pyc", ".pyo")):
                    try:
                        os.remove(os.path.join(pyc, x))
                    except OSError:
                        pass
    if out and log:
        log(f"обновление: старые файлы перенесены в {OTHER}/{sub}/: " + ", ".join(out))
    return out
