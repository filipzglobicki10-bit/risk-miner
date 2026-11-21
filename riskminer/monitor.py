"""Moduł monitorowania: dla trwających inwestycji wykrywa nowe ogłoszenia w BZP i zmiany istotne dla realizacji."""
from . import bzp, config, db, pipeline
from .util import now_iso


def check_project(pid, log=None):
    p = db.get("projects", pid)
    before = {r["object_id"] or r["notice_number"] for r in db.q("SELECT object_id, notice_number FROM notices WHERE project_id=?", (pid,))}
    ev_before = db.q1("SELECT COUNT(*) n FROM events WHERE project_id=?", (pid,))["n"]
    stats = {"notices": 0, "procurements": 0, "facts": 0, "events": 0, "links_proposed": 0, "errors": 0}
    if not db.q1("SELECT id FROM procurements WHERE project_id=?", (pid,)):
        stats = pipeline.enrich_project(pid, log=log)
    else:
        for pr in db.q("SELECT * FROM procurements WHERE project_id=?", (pid,)):
            pipeline._related_notices(p, pr, stats, log or (lambda m: None))
            pipeline._assign_parts(p, pr)
            pipeline._build_contract(p, pr, None)
        pipeline._computed_events(p, None)
    after = db.q("SELECT id, object_id, notice_number, notice_type, title FROM notices WHERE project_id=?", (pid,))
    new = [n for n in after if (n["object_id"] or n["notice_number"]) not in before]
    ev_after = db.q1("SELECT COUNT(*) n FROM events WHERE project_id=?", (pid,))["n"]
    for n in new:
        label = bzp.NOTICE_TYPE_LABELS.get(n["notice_type"], n["notice_type"])
        important = n["notice_type"] in ("AgreementUpdateNotice", "ContractModificationNotice", "ContractPerformingNotice", "TenderResultNotice")
        db.insert("monitor_events", {"project_id": pid, "kind": "istotna zmiana" if important else "nowe ogłoszenie", "notice_id": n["id"],
                                     "message": f"{label} {n['notice_number']}: {n['title'] or ''}"})
    if new or ev_after > ev_before:
        db.update("projects", pid, {"needs_review": 1})
    db.update("projects", pid, {"last_checked": now_iso()})
    return {"new_notices": len(new), "new_events": ev_after - ev_before, "errors": stats.get("errors", 0)}


def check_all(progress):
    only_unfinished = config.get()["monitor"].get("only_unfinished", True)
    rows = db.q("SELECT id, record_id, status FROM projects")
    if only_unfinished:
        rows = [r for r in rows if not (r["status"] or "").lower().startswith("zako") and not pipeline.project_metrics(r["id"]).get("completed")] or rows
    tot = {"projekty": 0, "nowe_ogłoszenia": 0, "nowe_zdarzenia": 0, "błędy": 0}
    for i, r in enumerate(rows):
        progress(i / max(1, len(rows)), f"monitoring {r['record_id']}")
        s = check_project(r["id"])
        tot["projekty"] += 1
        tot["nowe_ogłoszenia"] += s["new_notices"]
        tot["nowe_zdarzenia"] += s["new_events"]
        tot["błędy"] += s["errors"]
    progress(1, f"Monitoring zakończony: {tot}")
    return tot
