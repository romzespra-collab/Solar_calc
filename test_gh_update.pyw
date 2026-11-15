"""Тесты общего модуля обновления gh_update 1.5.3 (без сети). Запуск:
    python test_gh_update.pyw  [папка_с_модулями]"""
import io, json, os, shutil, sys, tempfile, threading, time, zipfile
_HERE = os.path.dirname(os.path.abspath(__file__))


def _mod_dir():
    """Папка с gh_update.py: аргумент; рядом с тестом или в его подпапке (app/,
    modules/ …); тест в tests/ — ещё корень проекта и его подпапки. Выше
    корня проекта не ищем (там чужие программы)."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    roots = [_HERE]
    if os.path.basename(_HERE).lower() in ("tests", "test"):
        roots.append(os.path.dirname(_HERE))
    first = ("app", "modules", "system")
    for r in roots:
        subs = sorted(os.listdir(r), key=lambda x: (x not in first, x.lower()))
        for d in (r,) + tuple(os.path.join(r, x) for x in subs):
            if os.path.isfile(os.path.join(d, "gh_update.py")):
                return d
    return _HERE


sys.path.insert(0, _mod_dir())
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import gh_update as gu

_KEEP = []                       # QApplication живёт до os._exit


class R(io.BytesIO):
    headers = {}
    def __enter__(self): return self
    def __exit__(self, *a): return False


def t_changelog():
    log = "История\n\n4.92:\n  б\n\n4.91 (= мини 1):\n  а\n\n4.90:\n  старое\n"
    new = gu.changelog_since(log, "4.90")
    assert "4.92" in new and "4.91" in new and "старое" not in new, new
    pyw = '"""prog\n\nv1.2.0: новое\n  деталь\nv1.1.0: старое\n"""\nimport os\n'
    assert gu.changelog_since(pyw, "1.1.0") == "v1.2.0: новое\n  деталь"
    tail = '"""prog\nv1.0.0: старое\nv1.1.0: новое\n"""\nimport os\nx = 1\n'
    assert gu.changelog_since(tail, "1.0.0") == "v1.1.0: новое", gu.changelog_since(tail, "1.0.0")
    md = "# Журнал\n\n## v2.0.1 — фикс\n- а\n\n## v2.0.0\n- б\n"
    assert gu.changelog_since(md, "2.0.0").startswith("## v2.0.1")
    ru = "Версия 3.1 — новое\n  а\nВерсия 3.0 — старое\n"
    assert gu.changelog_since(ru, "3.0") == "Версия 3.1 — новое\n  а"
    one = "v436: плеер\n  а\nv435: старое\n"
    assert gu.changelog_since(one, "435") == "v436: плеер\n  а"
    assert gu.changelog_since("436 строк кода:\n", "1") == ""
    assert gu.changelog_since("Изменения 2.2:\n  а\nИзменения 2.1:\n  б\n", "2.1") == "Изменения 2.2:\n  а"
    body = "1.2:\n  поднял порт 8080 до 1.2.3 мегабит\n"
    assert "8080" in gu.changelog_since(body, "1.1")


def t_versions():
    assert gu.newer("4.10", "4.9") and not gu.newer("4.88", "4.88")
    assert gu.newer("6.63.44", "6.63.4") and not gu.newer("4.8", "4.80")
    assert gu._blob_sha1(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def _install(layout, ver_in_zip, ver_name):
    root = tempfile.mkdtemp(prefix="t_upd_")
    try:
        app_dir = os.path.join(root, "prog")
        os.makedirs(app_dir)
        for fn, txt in (("Demo.pyw", "old"), ("cfg.json", "мои")):
            open(os.path.join(app_dir, fn), "w", encoding="utf-8").write(txt)
        zb = io.BytesIO()
        with zipfile.ZipFile(zb, "w") as z:
            z.writestr("demo/Demo.pyw", "new" if layout != "main" else 'VERSION = "%s"\n' % ver_in_zip)
            z.writestr("demo/cfg.json", "чужие")
            if layout == "VERSION":
                z.writestr("demo/VERSION", ver_in_zip + "\n")
            if layout == "custom":
                z.writestr("demo/pkg/__init__.py", '__version__ = "v%s"\n' % ver_in_zip)
        p = os.path.join(root, "a.zip")
        open(p, "wb").write(zb.getvalue())
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw",
                            version_files=("pkg/__init__.py",) if layout == "custom" else ())
        gu.install(t, p, ver_name)
        assert open(os.path.join(app_dir, "cfg.json"), encoding="utf-8").read() == "мои"
        # ★ 1.2.0: backup/ больше не ведётся — старый файл просто заменён
        assert not os.path.exists(os.path.join(app_dir, "backup"))
        assert open(os.path.join(app_dir, "Demo.pyw"), encoding="utf-8").read() != "old"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_install():
    for lay in ("VERSION", "custom", "main"):
        _install(lay, "1.1", "1.1")
        for ver_in, ver_name in (("1.1", "2.0"), ("1.1", "1.2"), ("1.1.1", "1.1")):   # 1.4.5: и близкие номера
            try:
                _install(lay, ver_in, ver_name)
                raise AssertionError(f"чужая версия принята: {lay} {ver_in} / {ver_name}")
            except gu.UpdateError:
                pass
        _install(lay, "12.21.0", "12.21")           # 1.4.5: «12.21» = «12.21.0» (как в newer)
        _install(lay, "12.21", "12.21.0")


def _zip(root, files):
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        for fn, txt in files.items():
            z.writestr("demo/" + fn, txt)
    p = os.path.join(root, "a.zip")
    open(p, "wb").write(zb.getvalue())
    return p


def t_cleanup():
    """1.2.0: старое стирается, настройки и данные — нет."""
    root = tempfile.mkdtemp(prefix="t_upd_")
    try:
        app_dir = os.path.join(root, "prog")
        old = {"Demo.pyw": "old", "Old.pyw": "старый главный", "my.bat": "свой",
               "cfg.json": "мои", "notes.txt": "заметки",
               "app/__init__.py": "", "app/old.py": "x", "app/keep.py": "x",
               "app/__pycache__/old.cpython-313.pyc": "pyc",
               "app/__pycache__/keep.cpython-313.pyc": "pyc",
               "app/user.json": "данные", "logs/x.py": "журнал",
               "Rec/a.mp4": "видео", "venvx/pyvenv.cfg": "", "venvx/m.py": "",
               "backup/v1.0/Demo.pyw": "копия"}
        for fn, txt in old.items():
            f = os.path.join(app_dir, fn)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w", encoding="utf-8").write(txt)
        ex = lambda fn: os.path.exists(os.path.join(app_dir, fn))
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        new1 = {"Demo.pyw": 'VERSION = "1.1"\n', "app/__init__.py": "",
                "app/keep.py": "y", "app/new.py": "y", "pics/a.png": "png",
                "cfg.json": "чужие"}
        gu.install(t, _zip(root, new1), "1.1")
        # первый раз (списка нет): старый код в папках архива (корень — нет)
        for fn in ("app/old.py", "app/__pycache__/old.cpython-313.pyc",
                   "backup"):
            assert not ex(fn), "не стёрто: " + fn
        # 1.5.1: стёрто, а не перенесено — папки .gh_update_old нет
        assert not ex(".gh_update_old") and t.moved_to == ""
        for fn in ("Old.pyw", "my.bat", "cfg.json", "notes.txt", "app/user.json", "logs/x.py",
                   "Rec/a.mp4", "venvx/m.py", "app/keep.py", "app/new.py"):
            assert ex(fn), "стёрто лишнее: " + fn
        assert open(os.path.join(app_dir, "cfg.json"), encoding="utf-8").read() == "мои"
        man = gu.read_manifest(app_dir)
        assert man == {"Demo.pyw", "app/__init__.py", "app/keep.py", "app/new.py",
                       "pics/a.png"}, man
        # второй раз — по списку: стёрто то, что ставили, свой файл цел
        open(os.path.join(app_dir, "app/mine.py"), "w").write("свой модуль")
        t.current = "1.1"
        new2 = {"Demo.pyw": 'VERSION = "1.2"\n', "app/__init__.py": "",
                "app/keep.py": "z", "cfg.json": "чужие"}
        gu.install(t, _zip(root, new2), "1.2")
        assert not ex("app/new.py") and not ex("pics/a.png") and not ex("pics"), \
            "по списку не стёрто"
        assert set(t.removed) == {"app/new.py", "pics/a.png"}, t.removed
        # 1.5.1: убранное по списку стёрто, папки .gh_update_old нет
        assert not ex(".gh_update_old")
        for fn in ("app/mine.py", "my.bat", "cfg.json", "notes.txt", "Rec/a.mp4"):
            assert ex(fn), "стёрто лишнее (по списку): " + fn
        # 1.2.1: user_dirs — без списка свои файлы там не трогаем
        os.remove(os.path.join(app_dir, gu.MANIFEST))
        os.makedirs(os.path.join(app_dir, "modules"), exist_ok=True)
        open(os.path.join(app_dir, "modules/src_mine.py"), "w").write("свой")
        t2 = gu.UpdateTarget("o", "r", "demo", "1.2", app_dir, "Demo.pyw", user_dirs=("modules",))
        gu.install(t2, _zip(root, dict(new2, **{"Demo.pyw": 'VERSION = "1.3"\n', "modules/mod_a.py": "a"})), "1.3")
        assert ex("modules/src_mine.py"), "user_dirs: свой модуль стёрт"
        # разовая чистка старых версий
        os.makedirs(os.path.join(app_dir, "backup", "v1.1"))
        open(os.path.join(app_dir, "app", "gone.py"), "w").write("x")
        got = gu.drop_leftovers(app_dir, ("app/gone.py",))
        assert not ex("app/gone.py") and not ex("backup"), got
        os.makedirs(os.path.join(app_dir, "backup"))
        open(os.path.join(app_dir, "backup", "чужое.txt"), "w").write("x")
        assert not gu.drop_old_backup(app_dir) and ex("backup/чужое.txt")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _prog(root, files, name="prog"):
    app_dir = os.path.join(root, name)
    for fn, txt in files.items():
        f = os.path.join(app_dir, fn)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        open(f, "w", encoding="utf-8").write(txt)
    return app_dir


def t_token():
    """1.5.0: пробельные символы в токене вычищаются; значение токена не попадает в текст ошибки."""
    assert gu.clean_token(" github_pat_AAA\r\n BBB\t\n") == "github_pat_AAABBB"
    assert gu.clean_token(None) == ""
    r = gu._req("https://api.github.com/x", "github_pat_AAA\nBBB ")
    assert r.get_header("Authorization") == "Bearer github_pat_AAABBB"
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw")
    for tok in ("github_pat_СЕКРЕТ123", "github_pat_SECRET\x00\x7f456"):
        try:
            gu.check(t, tok)
            raise AssertionError("кривой токен принят")
        except gu.UpdateError as e:
            assert "недопустимые символы" in str(e), e
            assert "СЕКРЕТ" not in str(e) and "SECRET" not in str(e) and "Bearer" not in str(e), e
    # что бы ни бросил http.client (ValueError со значением заголовка) — наружу без него
    old = gu.urllib.request.urlopen

    def boom(*a, **k):
        raise ValueError("Invalid header value b'Bearer github_pat_SECRET'")
    gu.urllib.request.urlopen = boom
    try:
        gu.check(t, "github_pat_SECRET")
        raise AssertionError("ValueError не превращён в понятную ошибку")
    except gu.UpdateError as e:
        assert "SECRET" not in str(e) and e.__cause__ is None, e
    finally:
        gu.urllib.request.urlopen = old


def t_git_copy():
    """1.5.0: копия из git (.git рядом) — install() отказывает, ничего не меняя."""
    root = tempfile.mkdtemp(prefix="t_git_")
    try:
        app_dir = _prog(root, {"Demo.pyw": "моя правка", "app/a.py": "x", "app/old.py": "x",
                               ".git/HEAD": "ref"})
        gu.write_manifest(app_dir, {"Demo.pyw", "app/a.py", "app/old.py"})
        before = sorted(os.listdir(os.path.join(app_dir, "app")))
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        z = _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', "app/a.py": "y"})
        try:
            gu.install(t, z, "1.1")
            raise AssertionError("копия из git обновилась")
        except gu.UpdateError as e:
            assert "git pull" in str(e), e
        assert open(os.path.join(app_dir, "Demo.pyw"), encoding="utf-8").read() == "моя правка"
        assert sorted(os.listdir(os.path.join(app_dir, "app"))) == before
        assert not os.path.exists(os.path.join(app_dir, gu.OLD_DIR)) and not os.path.exists(z)
        assert gu.is_git_copy(app_dir)
        t.git_ok = True                              # явное разрешение — ставится
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', "app/a.py": "y"}), "1.1")
        assert open(os.path.join(app_dir, "app/a.py"), encoding="utf-8").read() == "y"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_incomplete():
    """1.5.0: неполный архив не ставится (доля убираемого, ключевые файлы); ALLOW_DROP — снимает."""
    root = tempfile.mkdtemp(prefix="t_inc_")
    try:
        old = {"Demo.pyw": "old", "app/__init__.py": ""}
        old.update({"app/m%d.py" % i: "x" for i in range(10)})
        app_dir = _prog(root, old)
        gu.write_manifest(app_dir, set(old))
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")

        def refused(files, why):
            try:
                gu.install(t, _zip(root, files), "1.1")
                raise AssertionError("неполный архив поставлен: " + why)
            except gu.UpdateError as e:
                assert "неполный" in str(e), e
            assert open(os.path.join(app_dir, "Demo.pyw"), encoding="utf-8").read() == "old", why
            assert all(os.path.exists(os.path.join(app_dir, f)) for f in old), why
            assert not os.path.exists(os.path.join(app_dir, gu.OLD_DIR)), why
        new = {"Demo.pyw": 'VERSION = "1.1"\n'}
        refused(new, "один главный файл")
        refused(dict(new, **{"app/m0.py": "y"}), "пакет без __init__.py")
        full = dict(old, **new)
        t.must_have = ("app/core.py",)
        refused(full, "нет файла из must_have")
        t.must_have = ()
        part = {k: v for k, v in full.items() if k not in ("app/m1.py", "app/m2.py")}
        gu.install(t, _zip(root, part), "1.1")          # 2 из 12 — обычное обновление
        assert not os.path.exists(os.path.join(app_dir, "app/m1.py"))
        t.current = "1.1"
        small = dict(new, **{"Demo.pyw": 'VERSION = "1.2"\n', "app/__init__.py": "", gu.ALLOW_DROP: ""})
        gu.install(t, _zip(root, small), "1.2")         # так и задумано — ставится
        assert not os.path.exists(os.path.join(app_dir, "app/m5.py"))
        assert not os.path.exists(os.path.join(app_dir, gu.OLD_DIR))    # 1.5.1: стёрто, не перенесено
        assert not os.path.exists(os.path.join(app_dir, gu.ALLOW_DROP))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_move_unknown():
    """1.5.1: старый код стирается, а не переносится: первое обновление без списка убирает незнакомые
    файлы кода из папок программы (как до 1.5.0); свои папки и данные — на месте; папка
    .gh_update_old — след 1.5.0 — стирается при обновлении и из архива не ставится."""
    root = tempfile.mkdtemp(prefix="t_mv_")
    try:
        app_dir = _prog(root, {
            "Demo.pyw": "old", "app/__init__.py": "", "app/a.py": "x",
            "app/my_plugin.py": "мой модуль", "app/TODO.md": "заметки", "app/data.json": "данные",
            "app/__pycache__/my_plugin.cpython-313.pyc": "pyc",
            "tools/root_tool.py": "свой", "my_script.py": "свой", "backup/v0.9/мои.txt": "копия",
            ".gh_update_old/v0.9/app/was.py": "след 1.5.0",
        })
        logs = []
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', "app/__init__.py": "",
                                  "app/a.py": "y"}), "1.1", log=logs.append)
        ex = lambda fn: os.path.exists(os.path.join(app_dir, fn))  # noqa: E731
        for fn in ("app/my_plugin.py", "app/TODO.md", gu.OLD_DIR):
            assert not ex(fn), "не стёрто: " + fn
        assert t.moved_to == "" and not any("перенесены" in x for x in logs), logs
        assert any(gu.OLD_DIR in x and "стёрта" in x for x in logs), logs
        for fn in ("app/data.json", "tools/root_tool.py", "my_script.py", "backup/v0.9/мои.txt"):
            assert ex(fn), "тронуто лишнее: " + fn
        # служебная папка из архива не ставится
        t.current = "1.1"
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.2"\n', "app/__init__.py": "", "app/a.py": "z",
                                  gu.OLD_DIR + "/v1.0/app/x.py": "подмена"}), "1.2")
        assert not ex(gu.OLD_DIR)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_unsafe_paths():
    """Опасные пути в архиве (.., абсолютные) — отказ, вне папки программы ничего не появляется."""
    root = tempfile.mkdtemp(prefix="t_slip_")
    try:
        app_dir = _prog(root, {"Demo.pyw": "old"})
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        for bad in ("../evil.py", "demo/../../evil.py", "/abs_evil_gh_update.py", "a/../../evil.py"):
            p = os.path.join(root, "a.zip")
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("Demo.pyw", 'VERSION = "1.1"\n')
                z.writestr(bad, "evil")
            try:
                gu.install(t, p, "1.1")
                raise AssertionError("опасный путь принят: " + bad)
            except gu.UpdateError as e:
                assert "опасный путь" in str(e), e
            assert sorted(os.listdir(root)) == ["prog"], os.listdir(root)
            assert not os.path.exists("/abs_evil_gh_update.py")
            assert open(os.path.join(app_dir, "Demo.pyw"), encoding="utf-8").read() == "old"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_rollback():
    """Сбой посреди замены файлов — возвращаются старые, *.upd не остаётся, новые файлы убраны."""
    root = tempfile.mkdtemp(prefix="t_rb_")
    real, n = gu._replace, [0]

    def flaky(src, dst, tries=6):
        n[0] += 1
        if n[0] == 3:
            raise PermissionError(5, "занят")
        return real(src, dst, tries)
    try:
        old = {"Demo.pyw": "OLD", "app/__init__.py": "OLD", "app/a.py": "OLD", "app/b.py": "OLD"}
        app_dir = _prog(root, old)
        gu.write_manifest(app_dir, set(old))
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        new = {"Demo.pyw": 'VERSION = "1.1"\n', "app/__init__.py": "N", "app/a.py": "N", "app/b.py": "N",
               "app/c.py": "N", "app/d.py": "N"}
        gu._replace = flaky
        try:
            gu.install(t, _zip(root, new), "1.1")
            raise AssertionError("сбой замены не дал ошибку")
        except gu.UpdateError as e:
            assert "оставлена прежняя версия" in str(e), e
        finally:
            gu._replace = real
        left = []
        for dp, _dn, fns in os.walk(app_dir):
            left += [os.path.relpath(os.path.join(dp, f), app_dir).replace(os.sep, "/") for f in fns]
        assert sorted(left) == sorted([*old, gu.MANIFEST]), left
        assert all(open(os.path.join(app_dir, f), encoding="utf-8").read() == "OLD" for f in old)
        assert gu.read_manifest(app_dir) == set(old)
    finally:
        gu._replace = real
        shutil.rmtree(root, ignore_errors=True)


def t_backup_user():
    """1.5.0: backup/ пользователя (есть список MANIFEST либо внутри не только копии программы) — на месте."""
    root = tempfile.mkdtemp(prefix="t_bk_")
    try:
        app_dir = _prog(root, {"Demo.pyw": "old", "app/__init__.py": "", "backup/v1.0/Demo.pyw": "моя копия"})
        gu.write_manifest(app_dir, {"Demo.pyw", "app/__init__.py"})
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', "app/__init__.py": ""}), "1.1")
        assert os.path.exists(os.path.join(app_dir, "backup/v1.0/Demo.pyw")), "backup пользователя убрана"
        assert gu.drop_old_backup(app_dir, known={"Demo.pyw"})                  # одни копии программы — можно
        os.makedirs(os.path.join(app_dir, "backup", "v1.0"))
        open(os.path.join(app_dir, "backup", "v1.0", "заметки.txt"), "w").write("x")
        assert not gu.drop_old_backup(app_dir, known={"Demo.pyw"})
        assert not gu.drop_old_backup(app_dir)
        assert os.path.exists(os.path.join(app_dir, "backup/v1.0/заметки.txt"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_leftover_masks():
    """1.4.3: gone с масками — старые файлы прежних версий в корне; данные — нет."""
    root = tempfile.mkdtemp(prefix="t_mask_")
    try:
        names = ("CHANGELOG_v5_12_1.md", "CHANGELOG_v5_12_3.md", "CHANGELOG.md",
                 "README.txt", "README.md", "cfg.json", "CHANGELOG_v1.json", "x.log")
        for fn in names:
            open(os.path.join(root, fn), "w").write("x")
        os.makedirs(os.path.join(root, "docs"))
        open(os.path.join(root, "docs", "CHANGELOG_v1.md"), "w").write("x")
        got = gu.drop_leftovers(root, ("CHANGELOG_v*.md", "README.txt", "*", "*.log"))
        ex = lambda fn: os.path.exists(os.path.join(root, fn))
        assert not ex("CHANGELOG_v5_12_1.md") and not ex("CHANGELOG_v5_12_3.md"), got
        assert not ex("README.txt"), got
        for fn in ("CHANGELOG.md", "README.md", "cfg.json", "CHANGELOG_v1.json", "x.log",
                   "docs/CHANGELOG_v1.md"):
            assert ex(fn), "стёрто лишнее: " + fn
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_replace_retry():
    """1.4.3: файл на миг занят (WinError 5 / 32) — замена с повтором."""
    real, calls = os.replace, []

    def busy(src, dst, n=2):
        calls.append(src)
        if len(calls) <= n:
            raise PermissionError(32, "занят")
        return real(src, dst)
    root = tempfile.mkdtemp(prefix="t_repl_")
    try:
        a, b = os.path.join(root, "a"), os.path.join(root, "b")
        open(a, "w").write("new")
        open(b, "w").write("old")
        gu.os.replace = busy
        gu._replace(a, b)
        assert open(b).read() == "new" and len(calls) == 3, calls
        open(a, "w").write("x")
        calls.clear()
        gu.os.replace = lambda s, d: busy(s, d, n=99)
        try:
            gu._replace(a, b, tries=3)
            raise AssertionError("занятый файл не дал ошибку")
        except PermissionError:
            pass
    finally:
        gu.os.replace = real
        shutil.rmtree(root, ignore_errors=True)


def t_own():
    """1.2.1: свои файлы пользователя (own) при первой чистке не стираются; старое — без учёта регистра."""
    root = tempfile.mkdtemp(prefix="t_own_")
    try:
        app_dir = os.path.join(root, "prog")
        for fn in ("Demo.pyw", "functions/fn_a.py", "functions/fn_mine.py", "functions/old.py"):
            f = os.path.join(app_dir, fn)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w", encoding="utf-8").write("x")
        ex = lambda fn: os.path.exists(os.path.join(app_dir, fn))  # noqa: E731
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw", own=("functions/fn_*.py",))
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', "functions/fn_a.py": "y"}), "1.1")
        assert ex("functions/fn_mine.py"), "стёрта своя функция пользователя"
        assert not ex("functions/old.py"), "старый код не стёрт"
        assert open(os.path.join(app_dir, "functions/fn_a.py"), encoding="utf-8").read() == "y", "fn_a не обновлён"
        gu.write_manifest(app_dir, {"Demo.pyw", "functions/FN_A.py"})
        t.current = "1.1"
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.2"\n', "functions/fn_a.py": "z"}), "1.2")
        assert ex("functions/fn_a.py") or os.path.normcase("A") == "A", "стёрт файл, переименованный регистром"
        # MANIFEST в архиве (для модуля 1.2.0) не ставится и свой список не подменяет
        open(os.path.join(app_dir, "functions/mine.py"), "w").write("x")
        t.current = "1.2"
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.3"\n', "functions/fn_a.py": "z",
                                  gu.MANIFEST: "Demo.pyw\nfunctions/fn_a.py\nfunctions/mine.py\n"}), "1.3")
        assert ex("functions/mine.py"), "MANIFEST из архива подменил свой список"
        assert gu.MANIFEST not in gu.read_manifest(app_dir)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_user_dirs_manifest():
    """1.4.4: по списку MANIFEST свои папки (modules/, tools/) не чистятся; прочее — как раньше."""
    root = tempfile.mkdtemp(prefix="t_udm_")
    try:
        app_dir = os.path.join(root, "prog")
        for fn in ("Demo.pyw", "modules/src_mine.py", "Tools/x.py", "app/old.py"):
            f = os.path.join(app_dir, fn)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w", encoding="utf-8").write("x")
        ex = lambda fn: os.path.exists(os.path.join(app_dir, fn))  # noqa: E731
        gu.write_manifest(app_dir, {"Demo.pyw", "modules/src_mine.py", "Tools/x.py", "app/old.py"})
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', "modules/mod_a.py": "a"}), "1.1")
        assert ex("modules/src_mine.py"), "по списку стёрт файл из modules/"
        assert ex("Tools/x.py"), "по списку стёрт файл из tools/ (регистр папки не важен)"   # 1.4.5
        assert not ex("app/old.py"), "по списку не стёрто старое вне своих папок"
        assert "modules/src_mine.py" not in t.removed, t.removed
        # 1.4.5: свои папки программы (user_dirs), в том числе вложенные, — по списку тоже не чистятся
        mine = ("plugins/p.py", "app/plugins/mine.py", "app/Plugins2/m.py")
        for fn in mine + ("app/pluginsx.py", "app/gone.py"):
            f = os.path.join(app_dir, fn)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w", encoding="utf-8").write("x")
        gu.write_manifest(app_dir, {"Demo.pyw"} | set(mine) | {"app/pluginsx.py", "app/gone.py"})
        t2 = gu.UpdateTarget("o", "r", "demo", "1.1", app_dir, "Demo.pyw",
                             user_dirs=("plugins", "app/plugins/", "app\\plugins2"))
        gu.install(t2, _zip(root, {"Demo.pyw": 'VERSION = "1.2"\n'}), "1.2")
        for fn in mine:
            assert ex(fn), "по списку стёрт файл из своей папки (user_dirs): " + fn
        assert not ex("app/pluginsx.py") and not ex("app/gone.py"), "не стёрто старое рядом со своей папкой"
        # без списка (stale_files) вложенная своя папка — тоже мимо
        os.remove(os.path.join(app_dir, gu.MANIFEST))
        open(os.path.join(app_dir, "app/old2.py"), "w").write("x")
        t2.current = "1.2"
        gu.install(t2, _zip(root, {"Demo.pyw": 'VERSION = "1.3"\n', "app/a.py": "a"}), "1.3")
        assert ex("app/plugins/mine.py") and ex("app/Plugins2/m.py"), "без списка стёрта вложенная своя папка"
        assert not ex("app/old2.py"), "без списка не стёрт старый код"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_example_json():
    """1.4.4: шаблоны *.example.json обновляются; настройки *.json — никогда."""
    root = tempfile.mkdtemp(prefix="t_exj_")
    try:
        app_dir = os.path.join(root, "prog")
        os.makedirs(app_dir)
        old = {"Demo.pyw": "old", "accounts.json": "мои", "config.json": "мои", "profiles.json": "мои",
               "accounts.example.json": "старый шаблон",
               "modules/my.example.json": "моё", "data/x.example.json": "моё"}
        for fn, txt in old.items():
            f = os.path.join(app_dir, fn)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w", encoding="utf-8").write(txt)
        new = {"Demo.pyw": 'VERSION = "1.1"\n', "accounts.json": "чужие", "config.json": "чужие",
               "profiles.json": "чужие", "accounts.example.json": "новый шаблон",
               "config.example.json": "новый шаблон",
               "modules/my.example.json": "чужое", "data/x.example.json": "чужое"}
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        gu.install(t, _zip(root, new), "1.1")
        rd = lambda fn: open(os.path.join(app_dir, fn), encoding="utf-8").read()  # noqa: E731
        for fn in ("accounts.json", "config.json", "profiles.json"):
            assert rd(fn) == "мои", "перезаписаны настройки: " + fn
        for fn in ("accounts.example.json", "config.example.json"):
            assert rd(fn) == "новый шаблон", "шаблон не обновлён: " + fn
        for fn in ("modules/my.example.json", "data/x.example.json"):     # 1.4.5: шаблоны — только из корня
            assert rd(fn) == "моё", "перезаписан *.example.json в подпапке: " + fn
        assert gu._kept("data/x.json", gu.KEEP_DEFAULT) and not gu._kept("a.example.json", gu.KEEP_DEFAULT)
        assert gu._kept("data/x.example.json", gu.KEEP_DEFAULT) and gu._kept("a\\b.example.json", gu.KEEP_DEFAULT)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_rollback_retry():
    """1.4.4: ошибка посреди установки — откат старых файлов тем же повтором замены (файл на миг занят)."""
    root = tempfile.mkdtemp(prefix="t_rb_")
    real, state = os.replace, {"n": 0}
    try:
        app_dir = os.path.join(root, "prog")
        os.makedirs(app_dir)
        for fn in ("Demo.pyw", "a.py", "b.py"):
            open(os.path.join(app_dir, fn), "w", encoding="utf-8").write("old")

        def flaky(src, dst):
            state["n"] += 1
            if os.path.basename(dst) == "b.py" and not state.get("rb"):
                state["rb"] = True                      # установка b.py — ошибка → откат
                raise OSError(22, "сломалось")
            if state.get("rb"):
                state.setdefault("calls", []).append((os.path.basename(src), os.path.basename(dst)))
            if state.get("rb") and state["n"] % 2:       # откат: каждая вторая замена — «занят»
                state["busy"] = state.get("busy", 0) + 1
                raise PermissionError(32, "занят")
            return real(src, dst)
        gu.os.replace, slp = flaky, gu.time.sleep
        gu.time.sleep = lambda s: None
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        try:
            gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', "a.py": "new", "b.py": "new"}), "1.1")
            raise AssertionError("ошибка установки не поднялась")
        except gu.UpdateError as e:
            assert "прежняя версия" in str(e), e
        finally:
            gu.os.replace, gu.time.sleep = real, slp
        for fn in ("Demo.pyw", "a.py", "b.py"):
            assert open(os.path.join(app_dir, fn), encoding="utf-8").read() == "old", "не откатился " + fn
        assert not [x for x in os.listdir(app_dir) if x.endswith(".upd")], os.listdir(app_dir)
        # 1.4.5: откат — именно копия рядом (*.upd) + замена с повтором, а не copy2 поверх занятого файла
        calls = state.get("calls", [])
        for fn in ("Demo.pyw", "a.py"):
            assert (fn + ".upd", fn) in calls, f"откат {fn} — не через замену с повтором: {calls}"
        assert state.get("busy"), "откат ни разу не наткнулся на «занят» — повтор не проверен"
    finally:
        gu.os.replace = real
        shutil.rmtree(root, ignore_errors=True)


def _raises(fn, text=""):
    try:
        fn()
    except gu.UpdateError as e:
        assert text in str(e), e
        return True
    return False


def t_zip_guard():
    """1.4.5: опасные пути в архиве (zip-slip) и битый архив — понятная ошибка, ничего не поставлено."""
    root = tempfile.mkdtemp(prefix="t_zg_")
    evil = f"evil_{os.getpid()}.py"                 # своё имя на запуск: след прошлого запуска тест не ломает
    try:
        app_dir = os.path.join(root, "prog")
        os.makedirs(app_dir)
        open(os.path.join(app_dir, "Demo.pyw"), "w", encoding="utf-8").write("old")
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        tmpd = tempfile.gettempdir()
        for bad in (f"../{evil}", f"x/../../{evil}"):
            p = _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n', bad: "x"})
            assert _raises(lambda: gu.install(t, p, "1.1"), "опасный путь"), "опасный путь принят: " + bad
            assert not os.path.exists(p), "архив после отказа не удалён"
            for dp, _dns, fns in os.walk(root):
                assert evil not in fns, "файл записан мимо папки распаковки: " + dp
            assert not os.path.exists(os.path.join(tmpd, evil)), "файл записан мимо папки распаковки: " + tmpd
        assert open(os.path.join(app_dir, "Demo.pyw"), encoding="utf-8").read() == "old"
        root_abs = os.path.abspath(root)
        assert gu._safe(root_abs, "a/b.py") == os.path.join(root_abs, "a", "b.py")
        assert _raises(lambda: gu._safe(root_abs, "../" + os.path.basename(root_abs) + "x/a.py"), "опасный путь")
        # битый архив: испорчен байт данных (CRC) — testzip() до распаковки
        zb = io.BytesIO()
        with zipfile.ZipFile(zb, "w", zipfile.ZIP_STORED) as z:
            z.writestr("demo/Demo.pyw", 'VERSION = "1.1"\n')
            z.writestr("demo/big.py", "# " + "ABCDEFGH" * 200)
        raw = bytearray(zb.getvalue())
        i = raw.index(b"ABCDEFGH" * 4) + 100
        raw[i] ^= 0xFF
        p = os.path.join(root, "bad.zip")
        open(p, "wb").write(bytes(raw))
        assert _raises(lambda: gu.install(t, p, "1.1"), "архив повреждён"), "битый архив принят"
        assert open(os.path.join(app_dir, "Demo.pyw"), encoding="utf-8").read() == "old"
    finally:
        shutil.rmtree(root, ignore_errors=True)
        try:
            os.remove(os.path.join(tempfile.gettempdir(), evil))
        except OSError:
            pass


def t_manifest_unreadable():
    """1.4.1 / 1.4.5: список MANIFEST есть, но не читается (занят / мусор не в UTF-8) — пустой set:
    установка проходит и ничего не стирает (None означало бы чистку «по архиву»)."""
    root = tempfile.mkdtemp(prefix="t_mu_")
    try:
        app_dir = os.path.join(root, "prog")
        for fn in ("Demo.pyw", "app/old.py"):
            f = os.path.join(app_dir, fn)
            os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w", encoding="utf-8").write("x")
        assert gu.read_manifest(app_dir) is None                # списка нет
        man = os.path.join(app_dir, gu.MANIFEST)
        os.mkdir(man)                                           # open() → OSError (Linux: IsADirectory, Windows: Permission)
        got = gu.read_manifest(app_dir)
        assert got == set() and got is not None, got
        os.rmdir(man)
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        for n, junk in enumerate((b"\xff\xfe\x80garbage\n", b"app/old.py\n\x80\x81\n"), 1):
            open(man, "wb").write(junk)
            got = gu.read_manifest(app_dir)
            assert got == set() and got is not None, got
            gu.install(t, _zip(root, {"Demo.pyw": f'VERSION = "1.{n}"\n', "app/a.py": "a"}), f"1.{n}")
            assert os.path.exists(os.path.join(app_dir, "app/old.py")), "нечитаемый список — а старое стёрто"
            assert t.removed == [], t.removed
            assert gu.read_manifest(app_dir) == {"Demo.pyw", "app/a.py"}     # новый список записан
            t.current = f"1.{n}"
        real = open

        def busy(f, *a, **k):
            if str(f).endswith(gu.MANIFEST):
                raise PermissionError(13, "занят")
            return real(f, *a, **k)
        gu.open = busy
        try:
            got = gu.read_manifest(app_dir)
        finally:
            del gu.open
        assert got == set() and got is not None, got
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_download_guards():
    """1.4.5: архив скачался не целиком (размер) — ошибка и без sha; на GitHub уже версия новее — понятная ошибка."""
    data = b"zipdata-zipdata"
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw")
    old, slp = gu._open, gu.time.sleep
    gu.time.sleep = lambda s: None
    made = []
    real_mk = gu.tempfile.mkstemp

    def mk(*a, **k):
        fd, p = real_mk(*a, **k)
        made.append(p)
        return fd, p
    gu.tempfile.mkstemp = mk
    try:
        # размер в списке GitHub больше, чем пришло байт; sha нет — ловит только сверка размера
        items = [{"name": "demo_v1.1.zip", "path": "release/demo_v1.1.zip", "type": "file",
                  "sha": "", "size": len(data) + 7}]
        gu._open = lambda url, token, accept=None, timeout=0, headers=None: R(
            json.dumps(items).encode() if "raw" not in str(accept)
            else (b"" if (headers or {}).get("Range") else data))
        rel, new = gu.check(t, "tok")
        assert new and rel.size == len(data) + 7 and not rel.sha, rel
        assert _raises(lambda: gu.download(t, "tok", rel), "не целиком"), "неполный архив принят"
        assert not made, "неполный архив сохранён: %s" % made
        # пока окно было открыто, в release/ появилась версия новее (прежнего архива уже нет)
        items[:] = [{"name": "demo_v1.1.zip", "path": "release/demo_v1.1.zip", "type": "file",
                     "sha": gu._blob_sha1(data), "size": len(data)}]
        gu._open = lambda url, token, accept=None, timeout=0, headers=None: R(
            json.dumps(items).encode() if "raw" not in str(accept) else data)
        rel, new = gu.check(t, "tok")
        items[:] = [{"name": "demo_v1.2.zip", "path": "release/demo_v1.2.zip", "type": "file",
                     "sha": gu._blob_sha1(data), "size": len(data)}]
        assert _raises(lambda: gu.download(t, "tok", rel), "уже версия 1.2"), "скачан архив, которого уже нет"
        assert not made, made
    finally:
        gu._open, gu.time.sleep, gu.tempfile.mkstemp = old, slp, real_mk
        for p in made:
            try:
                os.remove(p)
            except OSError:
                pass


def t_check_download():
    data = b"zipdata"
    items = [{"name": "demo_v1.1.zip", "path": "release/demo_v1.1.zip", "type": "file",
              "sha": gu._blob_sha1(data), "size": len(data)},
             {"name": "demo_v1.0.9.zip", "path": "x", "type": "file"},
             {"name": "other_v9.zip", "path": "y", "type": "file"}]
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw")
    old = gu._open
    gu._open = lambda url, token, accept=None, timeout=0, headers=None: R(
        json.dumps(items).encode() if "raw" not in str(accept) else data)
    try:
        rel, new = gu.check(t, "tok")
        assert new and rel.version == "1.1"
        p = gu.download(t, "tok", rel)
        os.remove(p)
        rel.sha = "0" * 40
        try:
            gu.download(t, "tok", rel)
            raise AssertionError("испорченный архив принят")
        except gu.UpdateError:
            pass
    finally:
        gu._open = old
    t_resume()
    assert gu.wait_previous(["x", "--after-update", "999999999"], 1)


def t_resume():
    """★ 1.1.2: по ссылке на файл; ответ рвётся — докачка с места (Range)."""
    data = bytes(range(256)) * 400
    items = [{"name": "demo_v1.2.zip", "path": "release/demo_v1.2.zip",
              "type": "file", "sha": gu._blob_sha1(data), "size": len(data),
              "download_url": "https://raw.example/demo_v1.2.zip?token=x"}]
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw")
    calls = []

    def fake(url, token, accept=None, timeout=0, headers=None):
        if "raw.example" not in url:
            if "raw" in str(accept):
                raise AssertionError("качаю через API, а есть ссылка")
            return R(json.dumps(items).encode())
        rng = (headers or {}).get("Range", "")
        start = int(rng[6:-1]) if rng else 0
        calls.append(start)
        r = R(data[start:start + 30000])         # каждый ответ — обрыв
        r.status = 206 if start else 200
        return r
    old, slp = gu._open, gu.time.sleep
    gu._open, gu.time.sleep = fake, lambda s: None
    try:
        rel, new = gu.check(t, "tok")
        p = gu.download(t, "tok", rel)
        with open(p, "rb") as fh:
            assert fh.read() == data
        os.remove(p)
        assert calls[0] == 0 and calls[1] == 30000 and len(calls) == 4, calls
    finally:
        gu._open, gu.time.sleep = old, slp


def t_python_only():
    """★ 1.4.0: обновление только Python — exe-части модуля нет, у собранного
    exe check() — понятная ошибка, а не скачивание сборки."""
    for name in ("check_exe", "latest_exe", "download_exe", "stage_exe",
                 "staged_exe", "launch_swap", "swap_failed", "swap_script",
                 "finish_exe_update", "exe_name", "EXE_NEW", "EXE_SWAP"):
        assert not hasattr(gu, name), name
    assert gu.run_kind() == "python" and not gu.is_frozen()
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw")
    sys.frozen = True
    try:
        gu.check(t, "tok")
        raise AssertionError("собранный exe пошёл обновляться")
    except gu.UpdateError as e:
        assert "exe" in str(e), e
    finally:
        del sys.frozen
    assert gu.wait_previous(["x"]) is False


def t_qt(shots=None):
    from PySide6.QtWidgets import QApplication
    _KEEP.append(QApplication.instance() or QApplication([]))
    import gh_update_qt as q
    from gh_update_help import TokenHelpDialog, step_for_error
    q.set_colors(lambda: {"accent": "#2f81f7", "text": "#e6edf3", "dim": "#8b949e",
                          "panel": "#161b22", "border": "#30363d"})
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw", where="⋯ → Обновление")
    pg = q.UpdatePage(t, lambda: {"token": "", "auto": False}, lambda c: None)
    assert pg.box.restart_ask and not pg.box.busy()          # ★ 1.3.3 / 1.3.2
    pg2 = q.UpdatePage(t, lambda: {"token": "", "auto": False}, lambda c: None,
                       restart_ask=False, can_install=lambda: "идёт работа")
    assert not pg2.box.restart_ask and pg2.box.can_install() == "идёт работа"
    pg.resize(900, 420)
    for ph, d in (("checking", {}), ("available", {"ver": "1.1", "size": 5 << 20, "new": "1.1:\n  а"}),
                  ("download", {"got": 1 << 20, "total": 5 << 20, "ver": "1.1"}),
                  ("install", {"ver": "1.1"}), ("done", {"ver": "1.1"}),
                  ("building", {"ver": "1.2"}), ("done", {"ver": "1.2", "exe": True}),
                  ("error", {"text": "x"})):
        pg.box.phase.emit(ph, d)
        assert not pg.anim.grab().isNull()
    pg.box.phase.emit("available", {"ver": "1.1", "size": 5 << 20, "new": "1.1:\n  а"})
    if shots:
        pg.grab().save(os.path.join(shots, "page.png"))
    d = TokenHelpDialog(None, "o", "r", "Demo", 0, t)
    for i in range(len(d.steps)):
        if shots:
            d.grab().save(os.path.join(shots, "help_%d.png" % (i + 1)))
        d.go(+1)
    assert d.btn_next.text().startswith("Готово")
    assert step_for_error("токен не видит репозиторий o/r") == 2
    saved = {}
    b = q.UpdateBox(t, lambda: {"token": " tok\nen ", "auto": True, "every_h": 24}, saved.update)
    left = b._timer.remainingTime()
    b.cb_every.setCurrentIndex(b.cb_every.findData(3))
    assert saved.get("every_h") == 3
    # 1.5.0: токен чистится; смена «Каждые» до первой автопроверки её не откладывает
    assert saved.get("token") == "token" and b.ed_token.text() == "token"
    # грубый таймер Qt округляет срок до ±5 % — сравниваем с запасом
    assert 0 < b._timer.remainingTime() <= q.AUTO_FIRST_MS * 1.06, (left, b._timer.remainingTime())
    b._first_done = True
    b.cb_every.setCurrentIndex(b.cb_every.findData(6))
    assert b._timer.remainingTime() > q.AUTO_FIRST_MS
    assert b._err_text(ValueError("b'Bearer token'"), "token") == "b'Bearer ***'"
    # 1.5.0: копия из git — «Обновить» отказывает до скачивания
    gd = tempfile.mkdtemp(prefix="t_qgit_")
    try:
        os.makedirs(os.path.join(gd, ".git"))
        tg = gu.UpdateTarget("o", "r", "demo", "1.0", gd, "Demo.pyw")
        bg = q.UpdateBox(tg, lambda: {"token": "tok", "auto": False}, lambda c: None)
        bg._rel = gu.Release("1.1", "release/demo_v1.1.zip", "", 1)
        bg.update_now()
        assert not bg.busy() and "git pull" in bg.lbl.text(), bg.lbl.text()
    finally:
        shutil.rmtree(gd, ignore_errors=True)


def t_old_dir_listed():
    """1.5.2: папка .gh_update_old/ (след 1.5.0) стирается, но перед этим в журнал
    пишется, что в ней лежало (там могли быть свои скрипты пользователя)."""
    root = tempfile.mkdtemp(prefix="t_old_")
    try:
        assert gu.VERSION == "1.5.3", gu.VERSION
        app_dir = os.path.join(root, "demo")
        old = os.path.join(app_dir, gu.OLD_DIR, "1.0", "app")
        os.makedirs(old)
        for fn in ("my_script.py", "gone.py"):
            with open(os.path.join(old, fn), "w") as fh:
                fh.write("x")
        with open(os.path.join(app_dir, "Demo.pyw"), "w") as fh:
            fh.write('VERSION = "1.0"\n')
        logs = []
        t = gu.UpdateTarget("o", "r", "demo", "1.0", app_dir, "Demo.pyw")
        gu.install(t, _zip(root, {"Demo.pyw": 'VERSION = "1.1"\n'}), "1.1", log=logs.append)
        assert not os.path.exists(os.path.join(app_dir, gu.OLD_DIR))
        text = "\n".join(logs)
        assert "1.0/app/my_script.py" in text and "1.0/app/gone.py" in text, text
        assert "файлов: 2" in text, text
        assert gu._drop_old_dir(app_dir, logs.append) is False      # папки уже нет
    finally:
        shutil.rmtree(root, ignore_errors=True)


def t_qt_install():
    """1.4.4: скачано → can_install ещё раз (GUI-поток) → установка; отказ — архив удалён, «Обновить» снова
    доступна; двойной щелчок — одно скачивание."""
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    _KEEP.append(app)
    import gh_update_qt as q
    dl, inst, paths, boxes, asks = [], [], [], [], []
    main_thr = threading.current_thread()

    def fake_dl(t, token, rel, progress=None, cancel=None):   # 1.5.0: cancel
        dl.append(threading.current_thread())
        time.sleep(0.15)
        fd, p = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        paths.append(p)
        return p

    def fake_inst(t, path, ver, log=None):
        inst.append((threading.current_thread(), os.path.exists(path), ver))
        time.sleep(0.15)
        os.remove(path)
        return ["a"]

    def pump(cond, limit=5.0):
        end = time.time() + limit
        while time.time() < end and not cond():
            app.processEvents()
            time.sleep(0.01)
        app.processEvents()
        return cond()
    saved = (gu.download, gu.install, QMessageBox.information, QMessageBox.question)
    gu.download, gu.install = fake_dl, fake_inst
    QMessageBox.information = staticmethod(lambda *a, **k: boxes.append(a[-1]))
    QMessageBox.question = staticmethod(lambda *a, **k: asks.append(a[-1]) or QMessageBox.No)
    try:
        state = {"why": "", "thr": []}

        def can():
            state["thr"].append(threading.current_thread())
            return state["why"]
        # 1.5.3: своя пустая папка, а не «.» — тест запускают и из копии git (там отказ до скачивания)
        t = gu.UpdateTarget("o", "r", "demo", "1.0", tempfile.mkdtemp(prefix="ghu_qt_"), "Demo.pyw")
        b = q.UpdateBox(t, lambda: {"token": "tok", "auto": False}, lambda c: None, can_install=can)
        b._rel = gu.Release("1.1", "release/demo_v1.1.zip", "", 10)
        # двойной щелчок — одно скачивание
        b.update_now()
        b.update_now()
        assert b.busy() and not b.btn_update.isEnabled()
        # пока качали, началась работа → отказ: архив удалён, кнопка снова доступна, установки не было
        state["why"] = "идёт заливка"
        assert pump(lambda: not b.busy()), "после отказа окно осталось «занято»"
        assert len(dl) == 1, "двойной щелчок — %d скачивания" % len(dl)
        assert dl[0] is not main_thr, "скачивание в GUI-потоке"
        assert not inst, "установлено, хотя идёт работа"
        assert paths and not os.path.exists(paths[0]), "архив после отказа не удалён"
        assert b.btn_update.isEnabled() and b.btn_check.isEnabled(), "после отказа «Обновить» недоступна"
        assert "идёт заливка" in b.lbl.text(), b.lbl.text()
        assert len(state["thr"]) == 2 and all(x is main_thr for x in state["thr"]), \
            "can_install: до скачивания и после, оба — в GUI-потоке"
        assert t.current == "1.0"
        # работа ещё идёт — щелчок: сообщение, скачивания нет
        b.update_now()
        assert len(dl) == 1 and len(boxes) == 1 and not b.busy(), (len(dl), boxes)
        # работа кончилась — скачивание → повторная проверка → установка
        state["why"] = ""
        b.update_now()
        assert pump(lambda: bool(inst)), "установка не началась"
        assert b.busy(), "во время установки окно можно закрыть"
        b.update_now()                                      # щелчок во время установки — ничего
        assert pump(lambda: not b.busy()), "установка не закончилась"
        assert len(dl) == 2 and len(inst) == 1, (len(dl), len(inst))
        assert inst[0][1] and inst[0][2] == "1.1" and inst[0][0] is not main_thr, inst
        assert t.current == "1.1" and len(asks) == 1, (t.current, asks)
        assert not b.btn_restart.isHidden() and b.btn_update.isHidden()
        # can_install упал после скачивания — как отказ (не ставим, архив удалён)
        t.current = "1.0"
        b.btn_update.show()
        n = {"n": 0}

        def boom():
            n["n"] += 1
            if n["n"] > 1:
                raise RuntimeError("сломалась проверка")
            return ""
        b.can_install = boom
        b.update_now()
        assert pump(lambda: not b.busy() and len(dl) == 3)
        assert len(inst) == 1 and not os.path.exists(paths[-1]) and "сломалась проверка" in b.lbl.text()
    finally:
        gu.download, gu.install, QMessageBox.information, QMessageBox.question = saved
        for p in paths:
            try:
                os.remove(p)
            except OSError:
                pass


if __name__ == "__main__":
    shots = os.environ.get("SHOTS")
    bad = 0
    for f in (t_changelog, t_versions, t_install, t_cleanup, t_leftover_masks,
              t_replace_retry, t_own, t_user_dirs_manifest, t_example_json, t_rollback_retry,
              t_zip_guard, t_manifest_unreadable, t_download_guards,
              t_check_download, t_resume, t_python_only,
              t_token, t_git_copy, t_incomplete, t_move_unknown, t_unsafe_paths,
              t_rollback, t_backup_user, t_old_dir_listed,
              lambda: t_qt(shots), t_qt_install):
        try:
            f(); print("OK  ", getattr(f, "__name__", "qt"))
        except Exception as e:
            bad += 1; print("FAIL", getattr(f, "__name__", "qt"), repr(e))
    sys.stdout.flush()
    os._exit(1 if bad else 0)        # без разрушения Qt-объектов при выходе (segfault)
