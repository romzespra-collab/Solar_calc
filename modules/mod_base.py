"""mod_base.py  v1.9.7
пути (APP_ROOT), календарь, лог (очередь для интерфейса + файл), фоновый Worker

Журнал:
v1.9.7: папка только для чтения (лог не открыть) — программа запускается (_fh = None); Worker: та же задача,
        поданная во время работы, выполняется после неё с новыми данными (раньше терялась); ошибки задач — с
        трассировкой в файле лога.
v1.9.4: погода «📍 Регион 5 лет» (reg) — средний день по реальной погоде региона за 5 лет.
v1.3.0: вынесено из solar_calc.pyw v1.2.1 (программа была одним файлом); база оборудования
        «производитель → модель» (make_db, presets_of).
"""

import logging
import logging.handlers
import queue
import sys
import threading
import time
from pathlib import Path


APP_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


CONFIG_PATH = APP_ROOT / "config.json"


LOG_PATH = APP_ROOT / "solar_calc.log"


MONTHS = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
          "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]


MONTHS_S = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]


DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


MID_DOY = (17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344)


WEATHER = (("clear", "☀ Ясно"), ("avg", "⛅ Средний"), ("over", "☁ Пасмурно"), ("reg", "📍 Регион 5 лет"))


W_KEYS = [w for w, _ in WEATHER]


WEATHER_ADJ = {"clear": "ясный", "avg": "средний", "over": "пасмурный", "reg": "средний по региону (5 лет)"}


MONTHS_IN = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре", "октябре",
             "ноябре", "декабре"]


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


_fh = None                               # файл лога (нет прав на папку — без него)
try:
    _fh = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=1, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(_fh)
except Exception:
    pass


class Worker(threading.Thread):
    """Очередь задач, выполняются по одной."""

    def __init__(self):
        super().__init__(daemon=True)
        self.jobs = queue.Queue()
        self.pending = set()
        self.later = {}                       # та же задача подана, пока выполнялась: {имя: (fn, done)}
        self.running = set()
        self._lock = threading.Lock()
        self.start()

    def submit(self, name, fn, done):
        """В очередь. Такая же задача уже ждёт — False; уже выполняется — выполнится ещё раз после неё
        (с новыми данными), True."""
        with self._lock:
            if name in self.pending:
                if name in self.running:
                    self.later[name] = (fn, done)
                    return True
                return False
            self.pending.add(name)
        self.jobs.put((name, fn, done))
        return True

    def run(self):
        while True:
            name, fn, done = self.jobs.get()
            UIQ.put(("busy", name))
            with self._lock:
                self.running.add(name)
            try:
                res = fn()
                UIQ.put(lambda r=res, d=done: d(r))
            except Exception as e:
                log.error(f"✗ {name}: {e}", exc_info=True)       # трассировка — в файл лога
            finally:
                with self._lock:
                    self.running.discard(name)
                    nxt = self.later.pop(name, None)
                    if nxt is None:
                        self.pending.discard(name)
                if nxt is not None:
                    self.jobs.put((name,) + nxt)
                UIQ.put(_DONE)


def make_db(rows):
    """[(ключ, производитель, модель, параметры, описание)] → {ключ: (производитель, модель, параметры, описание)}."""
    return {k: (b, n, p, i) for k, b, n, p, i in rows}


def presets_of(db, custom):
    """База → {ключ: (подпись, параметры)}; «custom» — своё (параметры вручную)."""
    out = {"custom": (custom, None)}
    out.update({k: (n if b.startswith("Типов") else f"{b} {n}", p) for k, (b, n, p, _) in db.items()})
    return out

