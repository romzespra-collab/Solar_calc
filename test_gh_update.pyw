# -*- coding: utf-8 -*-
"""Тесты общего модуля обновления gh_update (без сети). Запуск:
    python test_gh_update.pyw  [папка_с_модулями]"""
import io, json, os, shutil, sys, tempfile, zipfile
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
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
        try:
            _install(lay, "1.1", "2.0")
            raise AssertionError("чужая версия принята: " + lay)
        except gu.UpdateError:
            pass


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


def _exe_zip(path, ver, top="Demo/", exe="Demo.exe"):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(top + exe, b"MZ")
        z.writestr(top + "_internal/python312.dll", b"dll")
        z.writestr(top + "vendor/netsdk/dhnetsdk.dll", b"sdk")
        z.writestr(top + "README_RU.txt", "readme")
        z.writestr(top + "exe_version.txt", ver + "\n")


def t_exe():
    """★ 1.3.0: собранный exe — сборка из Releases, распаковка, помощник."""
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw")
    assert gu.exe_name(t) == "Demo.exe"
    assert gu.run_kind() == "python" and not gu.is_frozen()
    rels = [{"draft": False, "assets": [
                {"name": "demo_exe_v1.2.zip", "size": 9, "state": "uploaded",
                 "url": "https://api/x/assets/2", "digest": "sha256:AB"},
                {"name": "other_exe_v9.zip", "size": 1, "url": "u"}]},
            {"draft": True, "assets": [{"name": "demo_exe_v5.0.zip", "size": 1,
                                        "url": "u"}]},
            {"draft": False, "assets": [{"name": "demo_exe_v1.1.zip",
                                         "size": 1, "url": "u"}]}]
    src = [{"name": "demo_v1.3.zip", "path": "release/demo_v1.3.zip",
            "type": "file", "size": 5}]
    old = gu._open
    gu._open = lambda url, token, accept=None, timeout=0, headers=None: R(
        json.dumps(rels if "/releases" in url else src).encode())
    try:
        e = gu.latest_exe(t, "tok")
        assert e.version == "1.2" and e.kind == "exe" and e.sha256 == "ab", e
        rel, new = gu.check_exe(t, "tok")          # 1.2 новее 1.0 — её
        assert new and rel.version == "1.2"
        t.current = "1.2"                          # exe 1.2, а в main уже 1.3
        rel, new = gu.check_exe(t, "tok")
        assert not new and rel.kind == "wait" and rel.version == "1.3", rel
        t.current = "1.3"
        rel, new = gu.check_exe(t, "tok")
        assert not new and rel.kind != "wait"
    finally:
        gu._open = old
    # распаковка: папка Demo/ внутри снимается, метка «готово», версия сверяется
    root = tempfile.mkdtemp(prefix="t_exe_")
    try:
        t = gu.UpdateTarget("o", "r", "demo", "1.0", root, "Demo.pyw")
        z = os.path.join(root, gu.EXE_DL)
        _exe_zip(z, "1.2")
        items = gu.stage_exe(t, z, "1.2")
        assert items == ["Demo.exe", "README_RU.txt", "_internal",
                         "exe_version.txt", "vendor"], items
        assert gu.staged_exe(t) == "1.2" and not os.path.exists(z)
        _exe_zip(z, "1.2")
        try:
            gu.stage_exe(t, z, "1.3")
            raise AssertionError("чужая версия сборки принята")
        except gu.UpdateError:
            pass
        assert gu.staged_exe(t) == ""              # испорченное — стёрто
        _exe_zip(z, "1.2", exe="Other.exe")
        try:
            gu.stage_exe(t, z, "1.2")
            raise AssertionError("сборка без Demo.exe принята")
        except gu.UpdateError:
            pass
        # подмена прошлый раз не удалась — причина читается и файл стирается
        with open(os.path.join(root, gu.EXE_FAILED), "w") as fh:
            fh.write("busy: _internal \n")
        assert "_internal" in gu.swap_failed(root)
        assert gu.swap_failed(root) == ""
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # помощник: только ASCII, CRLF, ждёт pid, vendor дополняет, есть откат
    bat = gu.swap_script(["Demo.exe", "README_RU.txt", "_internal",
                          "exe_version.txt", "vendor", gu.EXE_READY],
                         "Demo.exe", 4321)
    bat.encode("ascii")
    assert "\r\n" in bat and "\n" not in bat.replace("\r\n", "")
    assert 'find " 4321 "' in bat and 'start "" "Demo.exe" --after-update 4321' in bat
    assert 'xcopy ".gh_update_new\\vendor" "vendor\\"' in bat
    assert 'move /y "vendor"' not in bat and gu.EXE_READY not in bat.split(":mainok")[1]
    assert ":rollback" in bat and 'move /y ".gh_update_old\\_internal" "_internal"' in bat
    assert "%%" not in bat                       # в bat «%%» — это буквальный «%»
    try:
        gu.swap_script(["a&b.exe"], "Demo.exe", 1)
        raise AssertionError("опасное имя пропущено")
    except gu.UpdateError:
        pass


def t_exe_download():
    """★ 1.3.0: сборка качается по временной ссылке без токена, обрыв —
    докачка, sha256 сверяется."""
    import hashlib
    data = bytes(range(256)) * 300
    root = tempfile.mkdtemp(prefix="t_exed_")
    seen = []

    def fake(url, token, accept=None, timeout=0, headers=None):
        assert url.startswith("https://store/") and not token, (url, token)
        rng = (headers or {}).get("Range", "")
        start = int(rng[6:-1]) if rng else 0
        seen.append(start)
        r = R(data[start:start + 25000])
        r.status = 206 if start else 200
        return r
    old = (gu._open, gu._asset_link, gu.time.sleep)
    gu._open = fake
    gu._asset_link = lambda url, token: ("https://store/f?sig=1", False)
    gu.time.sleep = lambda s: None
    try:
        t = gu.UpdateTarget("o", "r", "demo", "1.0", root, "Demo.pyw")
        rel = gu.Release("1.2", "demo_exe_v1.2.zip", "", len(data),
                         "https://api/assets/1", kind="exe",
                         sha256=hashlib.sha256(data).hexdigest())
        p = gu.download_exe(t, "tok", rel)
        with open(p, "rb") as fh:
            assert fh.read() == data
        assert seen[:2] == [0, 25000], seen
        os.remove(p)
        rel.sha256 = "0" * 64
        try:
            gu.download_exe(t, "tok", rel)
            raise AssertionError("испорченная сборка принята")
        except gu.UpdateError:
            pass
        assert not os.path.exists(os.path.join(root, gu.EXE_DL))
    finally:
        gu._open, gu._asset_link, gu.time.sleep = old
        shutil.rmtree(root, ignore_errors=True)


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
    b = q.UpdateBox(t, lambda: {"token": "", "auto": True, "every_h": 24}, saved.update)
    b.cb_every.setCurrentIndex(b.cb_every.findData(3))
    assert saved.get("every_h") == 3


if __name__ == "__main__":
    shots = os.environ.get("SHOTS")
    bad = 0
    for f in (t_changelog, t_versions, t_install, t_cleanup, t_own,
              t_check_download, t_exe, t_exe_download, lambda: t_qt(shots)):
        try:
            f(); print("OK  ", getattr(f, "__name__", "qt"))
        except Exception as e:
            bad += 1; print("FAIL", getattr(f, "__name__", "qt"), repr(e))
    sys.stdout.flush()
    os._exit(1 if bad else 0)        # без разрушения Qt-объектов при выходе (segfault)
