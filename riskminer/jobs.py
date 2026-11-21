"""Zadania w tle (wzbogacanie wielu projektów, monitoring) i harmonogram cyklicznego monitoringu."""
import threading
import time
import traceback

from . import config, db
from .util import now_iso


# zadania zapisujące do bazy (wzbogacanie, monitoring) wykonują się po kolei — dwa równoległe wzbogacenia
# (np. podwójne kliknięcie „Wczytaj”) dublowałyby ogłoszenia przed deduplikacją
_work_lock = threading.Lock()


def start(kind, fn, *args, **kwargs):
    jid = db.insert("jobs", {"kind": kind, "status": "w toku", "progress": 0, "message": "start", "log": ""})

    def progress(frac, msg=None):
        row = db.get("jobs", jid)
        log = (row.get("log") or "")
        if msg:
            log = (log + "\n" + f"{now_iso()[11:19]} {msg}")[-20000:]
        db.update("jobs", jid, {"progress": round(frac, 3), "message": msg or row.get("message"), "log": log})

    def run():
        try:
            if _work_lock.locked():
                progress(0, "czeka na zakończenie poprzedniego zadania")
            with _work_lock:
                res = fn(*args, progress=progress, **kwargs)
            db.update("jobs", jid, {"status": "zakończone", "progress": 1, "message": str(res)[:500] if res else "zakończone", "finished_at": now_iso()})
        except Exception as e:
            db.update("jobs", jid, {"status": "błąd", "message": str(e), "log": traceback.format_exc()[-4000:], "finished_at": now_iso()})

    threading.Thread(target=run, daemon=True).start()
    return jid


def enrich_many(project_ids, progress):
    from . import pipeline
    tot = {"projekty": 0, "postępowania": 0, "ogłoszenia": 0, "fakty": 0, "zdarzenia": 0, "do_weryfikacji": 0, "błędy": 0}
    n = len(project_ids)
    for i, pid in enumerate(project_ids):
        p = db.get("projects", pid)
        progress(i / max(1, n), f"[{i+1}/{n}] {p['record_id']} {p['name'][:60]}")
        st = pipeline.enrich_project(pid, log=lambda m: progress(i / max(1, n), "   " + m))
        tot["projekty"] += 1
        tot["postępowania"] += st["procurements"]
        tot["ogłoszenia"] += st["notices"]
        tot["fakty"] += st["facts"]
        tot["zdarzenia"] += st["events"]
        tot["do_weryfikacji"] += st["links_proposed"]
        tot["błędy"] += st["errors"]
    progress(1, f"Gotowe: {tot}")
    return tot


_scheduler_started = False


def start_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    interval = config.get()["monitor"].get("interval_minutes") or 0
    if interval <= 0:
        return
    _scheduler_started = True

    def loop():
        from . import monitor
        while True:
            time.sleep(interval * 60)
            try:
                monitor.check_all(progress=lambda *a, **k: None)
            except Exception:
                pass

    threading.Thread(target=loop, daemon=True).start()
