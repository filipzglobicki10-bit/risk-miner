"""Serwer HTTP (biblioteka standardowa) — REST API + statyczny interfejs."""
import io
import json
import mimetypes
import os
import re
import traceback
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import analysis, bzp, config, db, exporter, extract, jobs, knowledge, llm, monitor, pipeline, review

# Tryb demonstracyjny online (RISKMINER_DEMO=1): baza sama wczytuje dane organizatora przy starcie
# i po wyczyszczeniu, a interfejs pokazuje baner o wspólnych danych.
DEMO = os.environ.get("RISKMINER_DEMO") == "1"
from . import forecast as refclass
from .util import now_iso

STATIC = os.path.join(config.BASE_DIR, "static")
SAMPLES = os.path.join(config.BASE_DIR, "samples")
ROUTES = []


def route(method, pattern):
    rx = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn
    return deco


class Req:
    def __init__(self, handler, params, query, body, headers):
        self.h, self.params, self.query, self.body, self.headers = handler, params, query, body, headers

    def json(self):
        if not self.body:
            return {}
        return json.loads(self.body.decode("utf-8"))

    @property
    def actor(self):
        return urllib.parse.unquote(self.headers.get("X-User") or "ekspert")[:60]

    @property
    def filename(self):
        return urllib.parse.unquote(self.headers.get("X-Filename") or "plik")


class Raw:
    def __init__(self, data, ctype, filename=None):
        self.data, self.ctype, self.filename = data, ctype, filename


# ---------------------------------------------------------------- status / konfiguracja

@route("GET", "/api/status")
def status(r):
    c = lambda t, w="": db.q1(f"SELECT COUNT(*) n FROM {t} {w}")["n"]
    return {
        "counts": {"projects": c("projects"), "procurements": c("procurements"), "notices": c("notices"), "contracts": c("contracts"),
                   "events": c("events", "WHERE status!='rejected'"), "events_proposed": c("events", "WHERE status='proposed'"),
                   "events_approved": c("events", "WHERE status IN ('approved','edited')"),
                   "links_proposed": c("links", "WHERE status='proposed'"), "documents": c("documents"), "facts": c("facts"),
                   "monitor_open": c("monitor_events", "WHERE acknowledged=0"), "analyses": c("analyses"),
                   "changes": c("contract_changes", "WHERE status!='rejected'"),
                   "categories_proposed": c("risk_catalog", "WHERE status='proposed'")},
        "capabilities": extract.capabilities(), "llm": llm.info(), "bzp_url": config.get()["bzp"]["base_url"],
        "bzp_local": os.path.exists(os.path.join(config.get()["data_dir"], "bzp_local.json")),
        "bzp_fallback_active": bzp.fallback_active(),
        "demo": DEMO,
        "recent": db.q("SELECT * FROM audit_log ORDER BY id DESC LIMIT 12"),
        "by_risk": db.q("SELECT risk_code, COUNT(*) n, SUM(CASE WHEN status IN ('approved','edited') THEN 1 ELSE 0 END) approved FROM events WHERE status!='rejected' AND risk_code IS NOT NULL GROUP BY risk_code ORDER BY risk_code"),
        "risk_names": knowledge.risk_names(),
    }


@route("GET", "/api/insights")
def insights(r):
    """Wnioski z całej bazy: jak naprawdę kończą się umowy (koszt, czas, cena vs szacunek), co je zmienia i jak."""
    sims = []
    for p in db.q("SELECT id, record_id, name FROM projects ORDER BY record_id"):
        sims.append({"project_id": p["id"], "record_id": p["record_id"], "name": p["name"], "score": 1.0,
                     "metrics": pipeline.project_metrics(p["id"])})
    ref = refclass.rcf(sims)
    reg = refclass.risk_register(sims)
    return {"rcf": ref, "register": reg, "bases": refclass.change_bases([s["project_id"] for s in sims]),
            "data_issues": db.q("SELECT m.id, m.project_id, p.record_id, m.message FROM monitor_events m JOIN projects p ON p.id=m.project_id "
                                "WHERE m.kind='jakość danych' ORDER BY p.record_id")}


@route("GET", "/api/changes")
def all_changes(r):
    """Biblioteka zmian umów: każda zmiana z BZP z przyczyną, kategorią ryzyka, podstawą prawną, kosztem i źródłem."""
    names = knowledge.risk_names()
    out = []
    for c in db.q("SELECT cc.*, p.record_id, p.name pname, p.city, p.beneficiary_name, p.voivodeship, n.url, n.notice_number, n.publication_date npub, "
                  "k.value_gross, k.contractor_name FROM contract_changes cc JOIN projects p ON p.id=cc.project_id "
                  "LEFT JOIN notices n ON n.id=cc.notice_id LEFT JOIN contracts k ON k.id=cc.contract_id "
                  "WHERE cc.status!='rejected' ORDER BY p.record_id, cc.change_date"):
        fp_key = c.get("fingerprint") or c.get("quote")
        ev = db.q1("SELECT * FROM events WHERE project_id=? AND fingerprint=? ", (c["project_id"], fp_key)) if fp_key else None
        key, meaning = bzp.basis_meaning(c.get("legal_basis"))
        cost = ev["cost_impact"] if ev else None
        out.append({
            "id": c["id"], "project_id": c["project_id"], "record_id": c["record_id"], "project": c["pname"], "city": c["city"],
            "beneficiary": c["beneficiary_name"], "voivodeship": c["voivodeship"], "contractor": c["contractor_name"],
            "date": c["change_date"], "basis": key or c.get("legal_basis"), "basis_meaning": meaning,
            "foreseen": key == "art. 455 ust. 1 pkt 1",
            "risk_code": ev["risk_code"] if ev else None, "risk_name": names.get(ev["risk_code"]) if ev else None,
            "cause": (ev["cause"] if ev and ev["cause"] else None), "description": c["description"],
            "cost": cost, "cost_pct": (cost / c["value_gross"]) if (cost and c.get("value_gross")) else None,
            "delay_days": c.get("term_change_days") or (ev["delay_days"] if ev else None),
            "notice_number": c["notice_number"], "notice_date": (c["npub"] or "")[:10], "url": c["url"], "part": c["part"],
        })
    return out


@route("GET", "/api/config")
def get_config(r):
    return config.public_view(config.get())


# ---------------------------------------------------------------- import i wzbogacanie

@route("POST", "/api/import")
def import_file(r):
    res = pipeline.import_records(r.filename, r.body, actor=r.actor)
    if r.query.get("enrich") == "1":
        res["job_id"] = jobs.start("enrich", jobs.enrich_many, res["project_ids"])
    return res


@route("POST", "/api/import-sample")
def import_sample(r):
    if r.query.get("bzp") == "1":
        # prawdziwa kopia ogłoszeń BZP dla 22 projektów (pobrana z API organizatora) — praca bez sieci, wynik powtarzalny
        with open(os.path.join(SAMPLES, "bzp_kopia_22_projekty.json"), encoding="utf-8") as f:
            bzp.import_local(bzp.items_of(json.load(f)))
    elif r.query.get("bzp") == "0":
        # tryb „BZP na żywo” — usuwamy lokalną kopię offline, żeby zapytania szły do API
        bzp.clear_local()
    path = os.path.join(SAMPLES, "Risk_Miner_dane_projekty.xlsx")
    with open(path, "rb") as f:
        res = pipeline.import_records(os.path.basename(path), f.read(), actor=r.actor)
    if r.query.get("enrich") == "1":
        res["job_id"] = jobs.start("enrich", jobs.enrich_many, res["project_ids"])
    return res


@route("POST", "/api/enrich")
def enrich(r):
    ids = r.json().get("project_ids") or [p["id"] for p in db.q("SELECT id FROM projects ORDER BY id")]
    return {"job_id": jobs.start("enrich", jobs.enrich_many, ids)}


@route("GET", "/api/jobs/(\\d+)")
def job(r):
    return db.get("jobs", int(r.params[0]))


@route("GET", "/api/jobs")
def jobs_list(r):
    return db.q("SELECT id, kind, status, progress, message, created_at, finished_at FROM jobs ORDER BY id DESC LIMIT 20")


# ---------------------------------------------------------------- projekty

@route("GET", "/api/projects")
def projects(r):
    rows = db.q("SELECT * FROM projects ORDER BY record_id")
    qtxt = (r.query.get("q") or "").lower()
    out = []
    for p in rows:
        if qtxt and qtxt not in (p["name"] + " " + (p["beneficiary_name"] or "") + " " + (p["record_id"] or "")).lower():
            continue
        m = pipeline.project_metrics(p["id"])
        p["metrics"] = m
        p["n_events"] = db.q1("SELECT COUNT(*) n FROM events WHERE project_id=? AND status!='rejected'", (p["id"],))["n"]
        p["n_proposed"] = db.q1("SELECT COUNT(*) n FROM events WHERE project_id=? AND status='proposed'", (p["id"],))["n"]
        p["n_links_proposed"] = db.q1("SELECT COUNT(*) n FROM links WHERE project_id=? AND status='proposed'", (p["id"],))["n"]
        p["n_notices"] = db.q1("SELECT COUNT(*) n FROM notices WHERE project_id=?", (p["id"],))["n"]
        p.pop("enrich_log", None)
        out.append(p)
    return out


@route("GET", "/api/projects/(\\d+)")
def project(r):
    pid = int(r.params[0])
    p = db.get("projects", pid)
    if not p:
        raise KeyError("Brak projektu")
    p["subsectors_extra"] = db.jload(p.get("subsectors_extra"), [])
    sources = {}

    def s(sid):
        if sid and sid not in sources:
            sources[sid] = db.get("sources", sid)
    s(p.get("source_id"))
    procs = db.q("SELECT * FROM procurements WHERE project_id=? ORDER BY publication_date", (pid,))
    for pr in procs:
        s(pr.get("source_id"))
        pr["link"] = _link_view(db.get("links", pr["link_id"])) if pr.get("link_id") else None
        pr["notices"] = db.q("SELECT id, notice_type, notice_number, publication_date, title, url, link_id, source_id FROM notices WHERE procurement_id=? ORDER BY publication_date", (pr["id"],))
        for n in pr["notices"]:
            n["label"] = bzp.NOTICE_TYPE_LABELS.get(n["notice_type"], n["notice_type"])
            n["link"] = _link_view(db.get("links", n["link_id"])) if n.get("link_id") else None
            s(n.get("source_id"))
        pr["contracts"] = db.q("SELECT * FROM contracts WHERE procurement_id=?", (pr["id"],))
        for c in pr["contracts"]:
            c["changes"] = db.q("SELECT * FROM contract_changes WHERE contract_id=? AND status!='rejected' ORDER BY change_date", (c["id"],))
    facts = db.q("SELECT * FROM facts WHERE project_id=? ORDER BY key, confidence DESC", (pid,))
    events = db.q("SELECT * FROM events WHERE project_id=? ORDER BY CASE status WHEN 'proposed' THEN 0 ELSE 1 END, confidence DESC", (pid,))
    for coll in (facts, events):
        for x in coll:
            s(x.get("source_id"))
            if x.get("notice_id") and not x.get("source_id"):
                n = db.get("notices", x["notice_id"])
                if n:
                    x["source_id"] = n["source_id"]
                    s(n["source_id"])
    docs = db.q("SELECT id, filename, doc_type, phase, n_pages, ocr_used, is_exemplar, source_id, created_at FROM documents WHERE project_id=?", (pid,))
    for d in docs:
        s(d.get("source_id"))
    links = [_link_view(l) for l in db.q("SELECT * FROM links WHERE project_id=? ORDER BY status, confidence DESC", (pid,))]
    return {
        "project": p, "metrics": pipeline.project_metrics(pid), "procurements": procs, "facts": facts, "events": events,
        "documents": docs, "links": links, "completeness": pipeline.completeness(pid), "sources": sources,
        "monitor": db.q("SELECT * FROM monitor_events WHERE project_id=? ORDER BY id DESC LIMIT 50", (pid,)),
        "risk_names": knowledge.risk_names(), "history": review.history("project", pid, 50),
    }


def _link_view(l):
    if not l:
        return None
    basis = db.jload(l.get("basis"), {}) or {}
    l = dict(l)
    l["reasons"] = basis.get("reasons") or []
    pay = basis.get("payload") or {}
    l["candidate"] = {k: pay.get(k) for k in ("notice_number", "title", "organization_name", "publication_date", "url", "notice_type", "buyer", "publication_number")} if pay else None
    l.pop("basis", None)
    return l


@route("POST", "/api/projects/(\\d+)/update")
def project_update(r):
    review.update_project(int(r.params[0]), r.json(), actor=r.actor)
    return {"ok": True}


@route("POST", "/api/projects/(\\d+)/enrich")
def project_enrich(r):
    return {"job_id": jobs.start("enrich", jobs.enrich_many, [int(r.params[0])])}


@route("POST", "/api/projects/(\\d+)/documents")
def project_doc(r):
    return pipeline.add_document(r.filename, r.body, project_id=int(r.params[0]), actor=r.actor)


@route("POST", "/api/projects/(\\d+)/fetch-url")
def project_fetch(r):
    return pipeline.fetch_url_document(r.json()["url"], project_id=int(r.params[0]))


@route("POST", "/api/projects/(\\d+)/events")
def project_event(r):
    return {"event_id": review.add_manual_event(int(r.params[0]), r.json(), actor=r.actor)}


@route("POST", "/api/projects/(\\d+)/check")
def project_check(r):
    return monitor.check_project(int(r.params[0]))


@route("GET", "/api/projects/(\\d+)/export")
def project_export(r):
    b = exporter.project_bundle(int(r.params[0]))
    if r.query.get("format") == "csv":
        return Raw(exporter.to_csv(b["events"]).encode("utf-8"), "text/csv; charset=utf-8", f"zdarzenia_{b['project']['record_id']}.csv")
    return Raw(json.dumps(b, ensure_ascii=False, indent=2, default=str).encode("utf-8"), "application/json", f"przypadek_{b['project']['record_id']}.json")


@route("GET", "/api/documents/(\\d+)")
def document(r):
    d = db.get("documents", int(r.params[0]))
    d["pages"] = db.jload(d.pop("pages_json"), [])
    d["source"] = db.get("sources", d["source_id"]) if d.get("source_id") else None
    return d


@route("GET", "/api/notices/(\\d+)")
def notice(r):
    n = db.get("notices", int(r.params[0]))
    n["raw_json"] = db.jload(n.get("raw_json"), {})
    n["source"] = db.get("sources", n["source_id"]) if n.get("source_id") else None
    n["label"] = bzp.NOTICE_TYPE_LABELS.get(n["notice_type"], n["notice_type"])
    return n


@route("GET", "/api/sources/(\\d+)")
def source(r):
    return db.get("sources", int(r.params[0]))


# ---------------------------------------------------------------- panel eksperta

@route("GET", "/api/review/queue")
def queue(r):
    ev = db.q("SELECT e.*, p.record_id, p.name pname FROM events e LEFT JOIN projects p ON p.id=e.project_id WHERE e.status='proposed' AND e.project_id IS NOT NULL ORDER BY e.confidence DESC LIMIT 400")
    for e in ev:
        if not e.get("source_id") and e.get("notice_id"):
            n = db.get("notices", e["notice_id"])
            e["source_id"] = n["source_id"] if n else None
        e["source"] = db.get("sources", e["source_id"]) if e.get("source_id") else None
    links = [dict(_link_view(l), record_id=l["record_id"], pname=l["pname"]) for l in
             db.q("SELECT l.*, p.record_id, p.name pname FROM links l JOIN projects p ON p.id=l.project_id WHERE l.status='proposed' ORDER BY l.confidence DESC")]
    cats = db.q("SELECT * FROM risk_catalog WHERE status='proposed'")
    contr = db.q("SELECT m.*, p.record_id FROM monitor_events m JOIN projects p ON p.id=m.project_id WHERE m.kind='sprzeczność' AND m.acknowledged=0")
    facts = db.q("SELECT f.*, p.record_id, p.name pname FROM facts f JOIN projects p ON p.id=f.project_id WHERE f.status='proposed' ORDER BY f.project_id, f.key LIMIT 400")
    for f in facts:
        if not f.get("source_id") and f.get("notice_id"):
            n = db.get("notices", f["notice_id"])
            f["source_id"] = n["source_id"] if n else None
        f["source"] = db.get("sources", f["source_id"]) if f.get("source_id") else None
    return {"events": ev, "links": links, "categories": cats, "contradictions": contr, "facts": facts, "risk_names": knowledge.risk_names()}


@route("POST", "/api/events/(\\d+)/decide")
def ev_decide(r):
    b = r.json()
    return review.decide_event(int(r.params[0]), b["decision"], actor=r.actor, comment=b.get("comment"), changes=b.get("changes"))


@route("POST", "/api/events/bulk")
def ev_bulk(r):
    b = r.json()
    for eid in b.get("ids", []):
        review.decide_event(int(eid), b["decision"], actor=r.actor, comment=b.get("comment"))
    return {"ok": True, "n": len(b.get("ids", []))}


@route("POST", "/api/links/(\\d+)/decide")
def link_decide(r):
    b = r.json()
    return _link_view(review.decide_link(int(r.params[0]), b["decision"], actor=r.actor, comment=b.get("comment")))


@route("POST", "/api/facts/(\\d+)/decide")
def fact_decide(r):
    b = r.json()
    return review.decide_fact(int(r.params[0]), b["decision"], actor=r.actor, comment=b.get("comment"), value=b.get("value"))


@route("POST", "/api/exemplar")
def exemplar(r):
    b = r.json()
    review.set_exemplar(b["entity"], int(b["id"]), b.get("value", True), actor=r.actor)
    return {"ok": True}


@route("GET", "/api/history")
def history(r):
    return review.history(r.query.get("entity"), r.query.get("id"), int(r.query.get("limit", 300)))


# ---------------------------------------------------------------- wiedza ekspercka

@route("GET", "/api/knowledge")
def get_knowledge(r):
    return {"risks": knowledge.risks(include_proposed=True), "event_types": knowledge.event_types(),
            "subsectors": knowledge.get("subsectors"), "checklist": knowledge.get("checklist"),
            "doc_expectations": knowledge.get("doc_expectations"), "sector_description": knowledge.get("sector_description"),
            "weights": config.get()["analysis"]["weights"]}


@route("POST", "/api/knowledge/risk")
def save_risk(r):
    review.save_risk(r.json(), actor=r.actor)
    return {"ok": True}


@route("POST", "/api/knowledge/risk/([A-Z0-9]+)/decide")
def risk_decide(r):
    b = r.json()
    review.decide_category(r.params[0], b["decision"], actor=r.actor, changes=b.get("changes"))
    return {"ok": True}


@route("POST", "/api/knowledge/event-type")
def save_et(r):
    review.save_event_type(r.json(), actor=r.actor)
    return {"ok": True}


@route("POST", "/api/knowledge/(subsectors|checklist|doc_expectations|sector_description)")
def save_k(r):
    knowledge.put(r.params[0], r.json()["value"], actor=r.actor)
    return {"ok": True}


@route("POST", "/api/knowledge/reset")
def reset_k(r):
    knowledge.seed(force=True)
    db.audit("knowledge.reset", "knowledge", None, actor=r.actor)
    return {"ok": True}


# ---------------------------------------------------------------- nowa inwestycja

@route("POST", "/api/analyses")
def new_analysis(r):
    b = r.json()
    aid = db.insert("analyses", {"title": b.get("title") or "Nowa inwestycja", "input_text": b.get("text") or "", "status": "szkic"})
    return {"analysis_id": aid}


@route("POST", "/api/analyses/(\\d+)/documents")
def analysis_doc(r):
    return pipeline.add_document(r.filename, r.body, analysis_id=int(r.params[0]), actor=r.actor)


@route("POST", "/api/analyses/(\\d+)/run")
def analysis_run(r):
    aid = int(r.params[0])
    b = r.json()
    a = db.get("analyses", aid)
    text = b.get("text", a.get("input_text"))
    extra = {k: b.get(k) for k in ("value", "length_km", "voivodeship", "deadline", "tender_start") if b.get(k) not in (None, "")}
    if "value" in extra:
        extra["value"] = float(str(extra["value"]).replace(" ", "").replace(",", "."))
    if "length_km" in extra:
        extra["length_km"] = float(str(extra["length_km"]).replace(",", "."))
    res = analysis.analyze(text, title=b.get("title") or a.get("title"), analysis_id=aid, extra=extra)
    db.audit("analysis.run", "analysis", aid, after={"flags": len(res["wnioski"]["flags"]), "similar": len(res["dane_zrodlowe"]["similar"])}, actor=r.actor)
    return {"analysis_id": aid, "result": res}


@route("GET", "/api/analyses")
def analyses(r):
    return db.q("SELECT id, title, status, created_at FROM analyses ORDER BY id DESC")


@route("GET", "/api/analyses/(\\d+)")
def get_analysis(r):
    a = db.get("analyses", int(r.params[0]))
    a["result"] = db.jload(a.pop("result_json"), None)
    a["documents"] = db.q("SELECT id, filename, doc_type, n_pages FROM documents WHERE analysis_id=?", (a["id"],))
    return a


@route("GET", "/api/analyses/(\\d+)/export")
def export_analysis(r):
    a = get_analysis(r)
    res = a.get("result") or {}
    if r.query.get("format") == "csv":
        rows = []
        for s in res.get("dane_zrodlowe", {}).get("similar", []):
            m = s.get("metrics", {})
            rows.append({"typ": "podobny_projekt", "kod": s["record_id"], "nazwa": s["name"], "wynik": s["score"],
                         "wartosc": m.get("value_for_comparison"), "odchylenie_kosztu": m.get("cost_dev_pct"), "opoznienie_dni": m.get("delay_days"),
                         "uzasadnienie": " | ".join(e["why"] for e in s["explanation"][:4])})
        for f in res.get("wnioski", {}).get("flags", []):
            rows.append({"typ": "czerwona_flaga", "kod": f["risk_code"], "nazwa": f["name"], "wynik": f["level"], "uzasadnienie": f["why"]})
        for rec in res.get("wnioski", {}).get("recommendations", []):
            rows.append({"typ": "rekomendacja", "kod": rec["risk_code"], "nazwa": rec["name"],
                         "uzasadnienie": " | ".join(rec["mitigations"] + rec["clauses"])})
        for i in res.get("wnioski", {}).get("issues_to_check", []):
            rows.append({"typ": "zagadnienie", "kod": i["id"], "nazwa": i["text"], "uzasadnienie": i["note"]})
        return Raw(exporter.to_csv(rows).encode("utf-8"), "text/csv; charset=utf-8", f"analiza_{a['id']}.csv")
    return Raw(json.dumps(a, ensure_ascii=False, indent=2, default=str).encode("utf-8"), "application/json", f"analiza_{a['id']}.json")


# ---------------------------------------------------------------- monitoring

@route("GET", "/api/monitor/events")
def monitor_events(r):
    return db.q("SELECT m.*, p.record_id, p.name pname FROM monitor_events m LEFT JOIN projects p ON p.id=m.project_id ORDER BY m.id DESC LIMIT 300")


@route("POST", "/api/monitor/check-all")
def monitor_all(r):
    return {"job_id": jobs.start("monitor", monitor.check_all)}


@route("POST", "/api/monitor/events/(\\d+)/ack")
def monitor_ack(r):
    db.update("monitor_events", int(r.params[0]), {"acknowledged": 1})
    db.audit("monitor.ack", "monitor_event", r.params[0], actor=r.actor)
    return {"ok": True}


# ---------------------------------------------------------------- eksport, raporty, BZP

@route("GET", "/api/export/([a-z_]+)")
def export_table(r):
    name = r.params[0]
    if name not in exporter.TABLES:
        raise KeyError("Nieznana tabela")
    rows = exporter.table_rows(name)
    if r.query.get("format") == "csv":
        return Raw(exporter.to_csv(rows).encode("utf-8"), "text/csv; charset=utf-8", f"{name}.csv")
    return Raw(json.dumps(rows, ensure_ascii=False, indent=2, default=str).encode("utf-8"), "application/json", f"{name}.json")


@route("GET", "/api/report/links")
def report(r):
    rep = exporter.link_report()
    if r.query.get("format") == "csv":
        rows = []
        for status, items in rep["links"].items():
            for i in items:
                rows.append({"ocena": status, **{k: (" | ".join(v) if isinstance(v, list) else v) for k, v in i.items()}})
        return Raw(exporter.to_csv(rows).encode("utf-8"), "text/csv; charset=utf-8", "raport_polaczen.csv")
    return rep


@route("POST", "/api/bzp/test")
def bzp_test(r):
    b = r.json()
    try:
        items, url, fetched = bzp.search(b.get("notice_type") or "ContractNotice", force_live=True,
                                         NoticeNumber=b.get("notice_number"),
                                         PublicationDateFrom=b.get("date_from"), PublicationDateTo=b.get("date_to"))
        return {"ok": True, "url": url, "fetched_at": fetched, "count": len(items),
                "sample": [{k: v for k, v in bzp.normalize_notice(i).items() if k != "text"} for i in items[:5]]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@route("POST", "/api/bzp/import-local")
def bzp_import(r):
    data = r.body
    items = []
    if r.filename.lower().endswith(".zip"):
        z = zipfile.ZipFile(io.BytesIO(data))
        for name in z.namelist():
            if name.lower().endswith(".json"):
                try:
                    items += bzp.items_of(json.loads(z.read(name).decode("utf-8")))
                except Exception:
                    continue
    else:
        items = bzp.items_of(json.loads(data.decode("utf-8")))
    n, total = bzp.import_local(items)
    db.audit("bzp.import_local", "bzp", None, after={"added": n, "total": total, "file": r.filename}, actor=r.actor)
    return {"added": n, "total": total}


@route("POST", "/api/bzp/clear-local")
def bzp_clear(r):
    bzp.clear_local()
    return {"ok": True}


@route("POST", "/api/admin/reset")
def admin_reset(r):
    if r.json().get("confirm") != "USUŃ":
        raise ValueError("Potwierdź wpisując USUŃ")
    for t in ("projects", "procurements", "notices", "contracts", "contract_changes", "facts", "documents", "events", "links",
              "rule_feedback", "analyses", "monitor_events", "jobs", "sources"):
        db.x(f"DELETE FROM {t}")
    db.audit("admin.reset", "database", None, actor=r.actor)
    if DEMO:
        _demo_seed()
        return {"ok": True, "reseeded": True}
    return {"ok": True}


def _demo_seed():
    """Wersja online: pusta baza → wczytaj 22 projekty organizatora i wyszukaj ich ogłoszenia w BZP (w tle)."""
    if db.q1("SELECT COUNT(*) n FROM projects")["n"]:
        return
    path = os.path.join(SAMPLES, "Risk_Miner_dane_projekty.xlsx")
    with open(path, "rb") as f:
        res = pipeline.import_records(os.path.basename(path), f.read(), actor="demo")
    jobs.start("enrich", jobs.enrich_many, res["project_ids"])
    print("Tryb demo: wczytano dane organizatora, trwa wyszukiwanie ogłoszeń w BZP.")


# ---------------------------------------------------------------- handler

class Handler(BaseHTTPRequestHandler):
    server_version = "RiskMiner/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("RISKMINER_QUIET"):
            return
        super().log_message(fmt, *args)

    def _send(self, code, body, ctype="application/json; charset=utf-8", filename=None):
        if isinstance(body, (dict, list)) or body is None:
            body = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if filename:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}")
        self.end_headers()
        self.wfile.write(body)

    def _dispatch(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if method == "GET" and not path.startswith("/api/"):
            return self._static(path)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        length = int(self.headers.get("Content-Length") or 0)
        if length > 200 * 1024 * 1024:
            return self._send(413, {"error": "Plik zbyt duży (limit 200 MB)"})
        body = self.rfile.read(length) if length else b""
        for m, rx, fn in ROUTES:
            mm = rx.match(path)
            if m == method and mm:
                try:
                    res = fn(Req(self, mm.groups(), query, body, self.headers))
                    if isinstance(res, Raw):
                        return self._send(200, res.data, res.ctype, res.filename)
                    return self._send(200, res)
                except KeyError as e:
                    return self._send(404, {"error": str(e)})
                except (ValueError, json.JSONDecodeError) as e:
                    return self._send(400, {"error": str(e)})
                except Exception as e:
                    traceback.print_exc()
                    return self._send(500, {"error": f"{type(e).__name__}: {e}"})
        return self._send(404, {"error": "Nie znaleziono"})

    def _static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
        if not fp.startswith(STATIC) or not os.path.isfile(fp):
            fp = os.path.join(STATIC, "index.html")
        with open(fp, "rb") as f:
            data = f.read()
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        self._send(200, data, ctype)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


def serve():
    cfg = config.get()
    db.conn()
    knowledge.seed()
    jobs.start_scheduler()
    if DEMO:
        _demo_seed()
    host, port = cfg["server"]["host"], cfg["server"]["port"]
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Risk Miner działa: http://{host}:{port}  (dane: {cfg['data_dir']}, BZP: {cfg['bzp']['base_url']}, LLM: {llm.info()['provider']})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Zatrzymano.")
