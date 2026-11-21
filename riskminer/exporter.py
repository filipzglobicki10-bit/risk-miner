"""Eksport rekordów (JSON/CSV) i raport z testu łączenia baz."""
import csv
import io
import json

from . import db, pipeline
from .util import now_iso

TABLES = {
    "projects": "SELECT * FROM projects",
    "procurements": "SELECT * FROM procurements",
    "notices": "SELECT id, procurement_id, project_id, notice_type, notice_number, bzp_number, object_id, tender_id, publication_date, title, url, link_id, source_id FROM notices",
    "contracts": "SELECT * FROM contracts",
    "contract_changes": "SELECT * FROM contract_changes",
    "facts": "SELECT * FROM facts",
    "events": "SELECT * FROM events",
    "links": "SELECT * FROM links",
    "documents": "SELECT id, project_id, analysis_id, filename, doc_type, phase, n_pages, ocr_used, is_exemplar, source_id, created_at FROM documents",
    "sources": "SELECT * FROM sources",
    "risk_catalog": "SELECT * FROM risk_catalog",
    "event_types": "SELECT * FROM event_types",
    "audit_log": "SELECT * FROM audit_log",
    "analyses": "SELECT id, title, status, created_at, result_json FROM analyses",
}


def table_rows(name, where=None, params=()):
    sql = TABLES[name]
    if where:
        sql = f"SELECT * FROM ({sql}) WHERE {where}"
    return db.q(sql, params)


def to_csv(rows):
    buf = io.StringIO()
    if not rows:
        return ""
    cols = list(rows[0].keys())
    w = csv.DictWriter(buf, fieldnames=cols, delimiter=";")
    w.writeheader()
    for r in rows:
        w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items()})
    return "﻿" + buf.getvalue()


def project_bundle(pid):
    """Pełny przypadek: projekt + postępowania + ogłoszenia + umowy + zmiany + fakty + zdarzenia + źródła + historia."""
    p = db.get("projects", pid)
    srcs = {}

    def src(sid):
        if sid and sid not in srcs:
            srcs[sid] = db.get("sources", sid)
        return sid

    out = {"exported_at": now_iso(), "project": p, "metrics": pipeline.project_metrics(pid), "procurements": []}
    src(p.get("source_id"))
    for pr in db.q("SELECT * FROM procurements WHERE project_id=?", (pid,)):
        src(pr.get("source_id"))
        pr["link"] = db.get("links", pr["link_id"]) if pr.get("link_id") else None
        pr["notices"] = [dict(n, text=None) for n in db.q("SELECT * FROM notices WHERE procurement_id=?", (pr["id"],))]
        for n in pr["notices"]:
            src(n.get("source_id"))
        pr["contracts"] = db.q("SELECT * FROM contracts WHERE procurement_id=?", (pr["id"],))
        for c in pr["contracts"]:
            c["changes"] = db.q("SELECT * FROM contract_changes WHERE contract_id=?", (c["id"],))
        out["procurements"].append(pr)
    out["facts"] = db.q("SELECT * FROM facts WHERE project_id=?", (pid,))
    out["events"] = db.q("SELECT * FROM events WHERE project_id=?", (pid,))
    out["links"] = db.q("SELECT * FROM links WHERE project_id=?", (pid,))
    out["documents"] = db.q("SELECT id, filename, doc_type, phase, n_pages, source_id FROM documents WHERE project_id=?", (pid,))
    for coll in ("facts", "events", "documents"):
        for r in out[coll]:
            src(r.get("source_id"))
    out["completeness"] = pipeline.completeness(pid)
    out["sources"] = list(srcs.values())
    out["history"] = db.q("SELECT * FROM audit_log WHERE (entity='project' AND entity_id=?) ORDER BY id", (str(pid),))
    return out


def link_report():
    """Raport z testu: poprawne (zatwierdzone/auto), niepewne (do weryfikacji) i błędne (odrzucone) połączenia."""
    rows = db.q("SELECT l.*, p.record_id, p.name FROM links l JOIN projects p ON p.id=l.project_id ORDER BY p.record_id, l.confidence DESC")
    groups = {"poprawne": [], "niepewne": [], "błędne": []}
    for r in rows:
        basis = db.jload(r["basis"], {}) or {}
        item = {"project": r["record_id"], "name": r["name"], "from": f"{r['from_type']}#{r['from_id']}", "to": f"{r['to_type']}:{r['to_ref']}",
                "confidence": r["confidence"], "method": r["method"], "reasons": basis.get("reasons"), "status": r["status"],
                "reviewer": r["reviewer"], "comment": r["review_comment"]}
        if r["status"] in ("approved", "auto"):
            groups["poprawne"].append(item)
        elif r["status"] == "rejected":
            groups["błędne"].append(item)
        else:
            groups["niepewne"].append(item)
    projects = db.q("SELECT id, record_id, name, enrich_status, public_id_type, public_id FROM projects ORDER BY record_id")
    per_project = []
    for p in projects:
        m = pipeline.project_metrics(p["id"])
        per_project.append({
            "record_id": p["record_id"], "name": p["name"], "identyfikator": f"{p['public_id_type']}: {p['public_id']}",
            "status_wzbogacenia": p["enrich_status"],
            "postepowania": db.q1("SELECT COUNT(*) n FROM procurements WHERE project_id=?", (p["id"],))["n"],
            "ogloszenia": db.q1("SELECT COUNT(*) n FROM notices WHERE project_id=?", (p["id"],))["n"],
            "zdarzenia": db.q1("SELECT COUNT(*) n FROM events WHERE project_id=? AND status!='rejected'", (p["id"],))["n"],
            "wartosc_umowy": m.get("contract_value"), "odchylenie_kosztu": m.get("cost_dev_pct"), "opoznienie_dni": m.get("delay_days"),
        })
    return {"generated_at": now_iso(), "summary": {k: len(v) for k, v in groups.items()}, "links": groups, "projects": per_project,
            "analyses": [{"id": a["id"], "title": a["title"], "created_at": a["created_at"]} for a in db.q("SELECT id,title,created_at FROM analyses ORDER BY id DESC LIMIT 20")]}
