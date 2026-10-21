# -*- coding: utf-8 -*-
"""Тесты общего модуля обновления gh_update (без сети). Запуск:
    python test_gh_update.pyw  [папка_с_модулями]"""
import io, json, os, shutil, sys, tempfile, zipfile
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import gh_update as gu


class R(io.BytesIO):
    headers = {}
    def __enter__(self): return self
    def __exit__(self, *a): return False


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
        assert os.path.exists(os.path.join(app_dir, "backup", "v1.0", "Demo.pyw"))
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


def t_check_download():
    data = b"zipdata"
    items = [{"name": "demo_v1.1.zip", "path": "release/demo_v1.1.zip", "type": "file",
              "sha": gu._blob_sha1(data), "size": len(data)},
             {"name": "demo_v1.0.9.zip", "path": "x", "type": "file"},
             {"name": "other_v9.zip", "path": "y", "type": "file"}]
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw")
    old = gu._open
    gu._open = lambda url, token, accept=None, timeout=0: R(
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
    assert gu.wait_previous(["x", "--after-update", "999999999"], 1)


def t_qt(shots=None):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    import gh_update_qt as q
    from gh_update_help import TokenHelpDialog, step_for_error
    q.set_colors(lambda: {"accent": "#2f81f7", "text": "#e6edf3", "dim": "#8b949e",
                          "panel": "#161b22", "border": "#30363d"})
    t = gu.UpdateTarget("o", "r", "demo", "1.0", ".", "Demo.pyw", where="⋯ → Обновление")
    pg = q.UpdatePage(t, lambda: {"token": "", "auto": False}, lambda c: None)
    pg.resize(900, 420)
    for ph, d in (("checking", {}), ("available", {"ver": "1.1", "size": 5 << 20, "new": "1.1:\n  а"}),
                  ("download", {"got": 1 << 20, "total": 5 << 20, "ver": "1.1"}),
                  ("install", {"ver": "1.1"}), ("done", {"ver": "1.1"}), ("error", {"text": "x"})):
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
    for f in (t_versions, t_install, t_check_download, lambda: t_qt(shots)):
        try:
            f(); print("OK  ", getattr(f, "__name__", "qt"))
        except Exception as e:
            bad += 1; print("FAIL", getattr(f, "__name__", "qt"), repr(e))
    sys.exit(1 if bad else 0)
