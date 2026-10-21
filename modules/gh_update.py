# -*- coding: utf-8 -*-
"""gh_update — обновление программы из приватного репозитория GitHub.

ОБЩИЙ модуль для всех наших приложений (только стандартная библиотека):
вставить файл в проект, задать UpdateTarget — и всё работает одинаково.

Откуда берётся версия. В репозитории лежит release/<имя>_vX.Y.Z.zip
(правило выдачи: внутри архива папка <имя>/ со всеми файлами проекта).
Программа спрашивает GitHub API, какой архив лежит в release/ нужной
ветки, сравнивает номер со своей версией, скачивает, сверяет контрольную
сумму (git blob sha1 из ответа GitHub), ставит поверх и перезапускается.

Доступ — токен GitHub «только чтение» (fine-grained PAT, Contents: Read)
на выбранные репозитории. Хранится в настройках программы.

Что делает install():
  * распаковывает во временную папку и проверяет, что внутри — та самая
    программа (есть главный файл и номер версии совпадает с именем архива);
  * старые файлы, которые заменяются, копирует в backup/<старая версия>/;
  * НИКОГДА не трогает настройки, журналы и скачанное (KEEP — маски);
  * при ошибке посреди копирования возвращает всё из резервной копии.

Перезапуск: restart() запускает программу заново с ключом
--after-update <pid> и закрывает текущую. Новая копия в самом начале зовёт
wait_previous(sys.argv) — ждёт, пока старая завершится (иначе защита от
второго запуска приняла бы её за «уже запущено»).

1.1.1: «Что нового» понимает и заголовки «v1.2.3: …», «## v1.2.3», «Версия
1.2.3 — …»; инструкция показывает настоящий файл с номером версии.
1.1.0: version_files — где искать номер версии в архиве (кроме
app/version.py, version.py, VERSION и главного файла); where — где в
программе вкладка (для инструкции); работает и как пакет (app/), и как
отдельные файлы рядом с главным .pyw.

Собранный .exe этим способом не обновляется (exe не перезаписать, пока он
работает, и в архиве — исходники): для exe — только уведомление.
"""
import fnmatch
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field

VERSION = "1.1.1"
API = "https://api.github.com"
TIMEOUT = 30

# что не трогаем при обновлении никогда (маски путей относительно папки программы)
KEEP_DEFAULT = (
    "*.json", "*.log", "*.log.*", "*.bak*", "*.tmp*",
    "libs/*", "logs/*", ".runtime/*", "backup/*", "firmware/*",
    "cloud_history/*", "*.exe", "*.dll", "release/*", ".git/*",
)


class UpdateError(Exception):
    """Ошибка обновления; текст — по-русски, для пользователя.
    code — HTTP-код ответа GitHub (0 — не HTTP)."""

    def __init__(self, text, code=0):
        super().__init__(text)
        self.code = code


@dataclass
class UpdateTarget:
    """Что и откуда обновлять — своё у каждого приложения."""
    owner: str                    # romzespra-collab
    repo: str                     # Smart_BMS
    name: str                     # smart_bms — префикс архива и папка внутри
    current: str                  # текущая версия программы, «4.88»
    app_dir: str                  # куда ставить (папка программы)
    main_file: str                # главный файл внутри архива: Smart_BMS.pyw
    subdir: str = ""              # если в репозитории проект лежит в подпапке
    branch: str = "main"
    changelog: str = ""           # путь к CHANGELOG в репозитории — «Что нового»
    keep: tuple = field(default_factory=lambda: KEEP_DEFAULT)
    version_files: tuple = ()     # где ещё искать VERSION = "…" в архиве
    where: str = "Настройки → 🔄 Обновление"   # где вкладка (для инструкции)


@dataclass
class Release:
    version: str
    path: str                     # release/smart_bms_v4.89.zip
    sha: str                      # git blob sha1 (сверка после скачивания)
    size: int


# ---------------- версии ----------------

def vtuple(v):
    """«4.88» / «v6.63.44» -> (4, 88) / (6, 63, 44); мусор -> ()."""
    nums = re.findall(r"\d+", str(v or ""))
    return tuple(int(x) for x in nums)


def newer(a, b):
    """a новее b? (сравнение по числам; «4.9» < «4.10»)."""
    ta, tb = vtuple(a), vtuple(b)
    n = max(len(ta), len(tb))
    return ta + (0,) * (n - len(ta)) > tb + (0,) * (n - len(tb))


# ---------------- GitHub ----------------

def _ctx():
    if os.environ.get("SSL_CERT_FILE"):           # свой корневой (прокси/фирма)
        return ssl.create_default_context()
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:                                  # noqa: BLE001
        return ssl.create_default_context()


def _req(url, token, accept="application/vnd.github+json"):
    h = {"Accept": accept, "User-Agent": "gh_update/" + VERSION,
         "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = "Bearer " + token.strip()
    return urllib.request.Request(url, headers=h)


def _open(url, token, accept="application/vnd.github+json", timeout=TIMEOUT):
    try:
        return urllib.request.urlopen(_req(url, token, accept),
                                      timeout=timeout, context=_ctx())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise UpdateError("токен GitHub не подошёл (401): проверь, что он "
                              "вставлен целиком и не истёк", 401) from e
        if e.code == 403:
            raise UpdateError("GitHub не дал доступ (403): у токена нет права "
                              "Contents: Read на этот репозиторий, или лимит "
                              "запросов — попробуй позже", 403) from e
        if e.code == 404:
            raise UpdateError("не найдено (404): репозиторий/ветка/папка release "
                              "не те, или токен не видит приватный репозиторий",
                              404) from e
        raise UpdateError("GitHub ответил %s" % e.code, e.code) from e
    except (urllib.error.URLError, OSError) as e:
        raise UpdateError("нет связи с GitHub (%s)" % getattr(e, "reason", e)) from e


def latest(t, token):
    """Последний архив в release/ ветки -> Release или None (архивов нет)."""
    folder = (t.subdir.strip("/") + "/release") if t.subdir else "release"
    url = "%s/repos/%s/%s/contents/%s?ref=%s" % (
        API, t.owner, t.repo, urllib.parse.quote(folder),
        urllib.parse.quote(t.branch))
    try:
        with _open(url, token) as r:
            items = json.loads(r.read().decode("utf-8"))
    except UpdateError as e:
        if e.code in (403, 404):
            raise UpdateError(diagnose(t, token, folder), e.code) from e
        raise
    if not isinstance(items, list):
        raise UpdateError("GitHub вернул не список файлов папки release")
    pat = re.compile(r"^%s_v?(\d+(?:\.\d+)*)\.zip$" % re.escape(t.name), re.I)
    best = None
    for it in items:
        m = pat.match(str(it.get("name") or ""))
        if not m or it.get("type") != "file":
            continue
        rel = Release(m.group(1), it["path"], it.get("sha") or "",
                      int(it.get("size") or 0))
        if best is None or newer(rel.version, best.version):
            best = rel
    return best


def _code(url, token):
    """HTTP-код запроса (200/401/403/404…), 0 — нет связи."""
    try:
        with _open(url, token):
            return 200
    except UpdateError as e:
        return e.code


def diagnose(t, token, folder="release"):
    """После 403/404: по шагам выяснить, ЧТО не так, и сказать, как
    исправить (GitHub на приватный репозиторий без доступа отвечает 404 —
    по одному коду не понять)."""
    q = urllib.parse.quote
    full = "%s/%s" % (t.owner, t.repo)
    c = _code("%s/user" % API, token)
    if c == 401:
        return ("токен GitHub недействителен (удалён, истёк или вставлен не "
                "целиком) — сделайте новый, кнопка «?»")
    c = _code("%s/repos/%s" % (API, full), token)
    if c in (403, 404):
        return ("токен не видит репозиторий %s. На GitHub: токен → Edit → "
                "Repository access → Only select repositories → добавьте %s "
                "(и Resource owner — %s)" % (full, full, t.owner))
    if c != 200:
        return "GitHub не отвечает на запрос репозитория (код %s)" % c
    c = _code("%s/repos/%s/branches/%s" % (API, full, q(t.branch)), token)
    if c == 404:
        return ("в репозитории %s нет ветки «%s» — впишите в поле «Ветка» "
                "правильную (обычно main)" % (full, t.branch))
    c = _code("%s/repos/%s/contents/?ref=%s" % (API, full, q(t.branch)), token)
    if c in (403, 404):
        return ("у токена нет права читать файлы. На GitHub: токен → Edit → "
                "Permissions → Repositories → Add permissions → Contents → "
                "Read-only → Update")
    return ("в ветке «%s» нет папки %s с архивами программы" % (t.branch, folder))


def check(t, token):
    """-> (Release, есть_новее). Release=None — архивов в release/ нет."""
    rel = latest(t, token)
    return rel, bool(rel and newer(rel.version, t.current))


def whats_new(t, token, upto=None, limit=6000):
    """Разделы CHANGELOG новее установленной версии (до upto включительно).
    Раздел начинается строкой «4.90:» или «6.63.45 (= полная 4.90):».
    -> текст или "" (нет файла/разделов — не ошибка)."""
    if not t.changelog:
        return ""
    url = "%s/repos/%s/%s/contents/%s?ref=%s" % (
        API, t.owner, t.repo, urllib.parse.quote(t.changelog),
        urllib.parse.quote(t.branch))
    try:
        with _open(url, token, accept="application/vnd.github.raw") as r:
            text = r.read().decode("utf-8", errors="replace")
    except UpdateError:
        return ""
    return changelog_since(text, t.current, upto, limit)


def changelog_since(text, current, upto=None, limit=6000):
    # «4.90:», «6.63.45 (= полная 4.90):», «v1.2.3: текст», «## v1.2.3 — …»,
    # «# v1.2.3: …» (журнал в шапке .pyw), «Версия 1.2.3 — …»
    # одно число («v436:») — только с «v»/«Версия» впереди
    head = re.compile(r"^(?:#{1,4}\s*|\[)?(?:(?:[vV]|(?:[Вв]ерсия|[Ии]зменения(?:\s+в)?)\s+v?)(\d+(?:\.\d+)*)|"
                      r"(\d+(?:\.\d+)+))\b"
                      r"(?:[^\n]*:\s*$|\]?\s*(?:[:—–(-]|\s*$))")
    out, take = [], False
    stop = re.compile(r'^\s*("""|\'\'\'|import |from \S+ import |def |class )')
    for line in text.splitlines():
        if take and stop.match(line):          # журнал в шапке .pyw — дальше код
            break
        m = head.match(line)
        if m:
            v = m.group(1) or m.group(2)
            take = newer(v, current) and (upto is None or not newer(v, upto))
        if take:
            out.append(line.rstrip())
    res = "\n".join(out).strip()
    return res[:limit] + ("\n…" if len(res) > limit else "")


def _blob_sha1(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def download(t, token, rel, progress=None):
    """Скачать архив во временный файл, сверить размер и sha. -> путь."""
    url = "%s/repos/%s/%s/contents/%s?ref=%s" % (
        API, t.owner, t.repo, urllib.parse.quote(rel.path),
        urllib.parse.quote(t.branch))
    buf = bytearray()
    with _open(url, token, accept="application/vnd.github.raw",
               timeout=120) as r:
        total = int(r.headers.get("Content-Length") or rel.size or 0)
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            buf += chunk
            if progress:
                progress(len(buf), total)
    data = bytes(buf)
    if rel.size and len(data) != rel.size:
        raise UpdateError("архив скачался не целиком (%d из %d байт)"
                          % (len(data), rel.size))
    if rel.sha and _blob_sha1(data) != rel.sha:
        raise UpdateError("контрольная сумма архива не совпала — "
                          "скачивание испорчено, обновление отменено")
    fd, path = tempfile.mkstemp(prefix=t.name + "_", suffix=".zip")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return path


# ---------------- установка ----------------

def _kept(rel_path, keep):
    p = rel_path.replace("\\", "/")
    return any(fnmatch.fnmatch(p, k) for k in keep)


def _safe(root, rel):
    dst = os.path.normpath(os.path.join(root, rel))
    if not (dst == root or dst.startswith(root + os.sep)):
        raise UpdateError("в архиве опасный путь: %s" % rel)
    return dst


def install(t, zip_path, rel_version, log=None):
    """Поставить архив поверх t.app_dir. -> список заменённых файлов."""
    log = log or (lambda *_a: None)
    app_dir = os.path.abspath(t.app_dir)
    stage = tempfile.mkdtemp(prefix=t.name + "_upd_")
    try:
        with zipfile.ZipFile(zip_path) as z:
            bad = z.testzip()
            if bad:
                raise UpdateError("архив повреждён: %s" % bad)
            names = [n for n in z.namelist() if not n.endswith("/")]
            prefix = t.name + "/"
            if names and all(n.startswith(prefix) for n in names):
                strip = len(prefix)
            else:
                strip = 0
            files = []
            for n in names:
                rel = n[strip:]
                if not rel or "__pycache__" in rel:
                    continue
                dst = _safe(stage, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with z.open(n) as src, open(dst, "wb") as out:
                    shutil.copyfileobj(src, out)
                files.append(rel)
        if t.main_file not in files:
            raise UpdateError("в архиве нет %s — это не та программа" % t.main_file)
        # номер версии внутри архива должен совпасть с именем архива
        found = ""
        for cand in tuple(t.version_files) + ("app/version.py", "version.py",
                                               "VERSION", t.main_file):
            pth = os.path.join(stage, cand)
            if os.path.exists(pth):
                with open(pth, encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
                if os.path.basename(cand) == "VERSION":
                    m = re.match(r"\s*v?(\d+(?:\.\d+)*)\s*$", txt)
                else:
                    m = re.search(r'(?:APP_)?(?:VERSION|__version__)\s*=\s*'
                                  r'["\']v?(\d+(?:\.\d+)*)', txt)
                if m:
                    found = m.group(1)
                    break
        if found and vtuple(found) != vtuple(rel_version):
            raise UpdateError("внутри архива версия %s, а не %s — обновление "
                              "отменено" % (found, rel_version))
        # резервная копия того, что заменим
        bdir = os.path.join(app_dir, "backup", "v" + t.current)
        todo = [f for f in files if not _kept(f, t.keep)]
        replaced = []
        try:
            for rel in todo:
                dst = _safe(app_dir, rel)
                if os.path.exists(dst):
                    b = _safe(bdir, rel)
                    os.makedirs(os.path.dirname(b), exist_ok=True)
                    shutil.copy2(dst, b)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                tmp = dst + ".upd"
                shutil.copy2(os.path.join(stage, rel), tmp)
                os.replace(tmp, dst)
                replaced.append(rel)
        except Exception as exc:                       # noqa: BLE001
            log("обновление: ошибка (%s) — возвращаю старые файлы" % exc)
            for rel in replaced:
                b = os.path.join(bdir, rel)
                dst = os.path.join(app_dir, rel)
                try:
                    if os.path.exists(b):
                        shutil.copy2(b, dst)
                    else:
                        os.remove(dst)
                except OSError:
                    pass
            raise UpdateError("не удалось заменить файлы (%s) — оставлена "
                              "прежняя версия" % exc) from exc
        log("обновление: заменено файлов %d, резервная копия — %s"
            % (len(replaced), bdir))
        return replaced
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        try:
            os.remove(zip_path)
        except OSError:
            pass


# ---------------- перезапуск ----------------

def is_frozen():
    return bool(getattr(sys, "frozen", False))


def restart(argv=None):
    """Запустить программу заново (с --after-update <pid>). Закрыть текущую
    — дело вызывающего (обычно QApplication.quit() сразу после)."""
    argv = list(sys.argv if argv is None else argv)
    clean, skip = [], False
    for a in argv[1:]:
        if skip:
            skip = False
            continue
        if a == "--after-update":
            skip = True
            continue
        clean.append(a)
    exe = sys.executable
    if os.name == "nt" and exe.lower().endswith("python.exe"):
        w = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(w):
            exe = w
    cmd = [exe] + ([] if is_frozen() else [os.path.abspath(argv[0])]) + clean \
        + ["--after-update", str(os.getpid())]
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200        # DETACHED_PROCESS | NEW_PROCESS_GROUP
    subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(argv[0])),
                     creationflags=flags, close_fds=True)
    return cmd


def wait_previous(argv=None, timeout=20.0):
    """Звать В САМОМ НАЧАЛЕ программы: если запущены после обновления —
    подождать, пока старая копия завершится. -> True, если ждали."""
    argv = sys.argv if argv is None else argv
    if "--after-update" not in argv:
        return False
    try:
        pid = int(argv[argv.index("--after-update") + 1])
    except (ValueError, IndexError):
        return False
    end = time.monotonic() + timeout
    while time.monotonic() < end and _alive(pid):
        time.sleep(0.25)
    return True


def _alive(pid):
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x00100000 | 0x1000, False, pid)   # SYNCHRONIZE | QUERY_LIMITED
        if not h:
            return False
        try:
            return k32.WaitForSingleObject(h, 0) == 0x102            # WAIT_TIMEOUT
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
