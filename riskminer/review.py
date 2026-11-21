"""Człowiek w procesie: decyzje eksperta (zatwierdź / popraw / odrzuć) z pełną historią zmian."""
import json

from . import db, pipeline
from .util import now_iso

EVENT_EDITABLE = ("risk_code", "event_type", "title", "cause", "mitigation", "mitigation_effective", "cost_impact", "delay_days",
                  "quote", "page")


def decide_event(eid, decision, actor="ekspert", comment=None, changes=None):
    ev = db.get("events", eid)
    if not ev:
        raise ValueError("Brak zdarzenia")
    upd = {"status": decision, "reviewer": actor, "review_comment": comment, "reviewed_at": now_iso()}
    if changes:
        for k in EVENT_EDITABLE:
            if k in changes:
                upd[k] = changes[k]
        if decision == "approved":
            upd["status"] = "edited"
    db.update("events", eid, upd)
    db.audit(f"event.{decision}", "event", eid, before={k: ev.get(k) for k in upd}, after=upd, comment=comment, actor=actor)
    if ev.get("rule_id") and decision in ("approved", "rejected"):
        db.insert("rule_feedback", {"rule_id": ev["rule_id"], "fingerprint": ev["fingerprint"], "decision": decision, "created_at": now_iso()})
    return db.get("events", eid)


def set_exemplar(entity, eid, value, actor="ekspert"):
    table = {"event": "events", "project": "projects", "document": "documents"}[entity]
    db.update(table, eid, {"is_exemplar": 1 if value else 0})
    db.audit(f"{entity}.exemplar", entity, eid, after={"is_exemplar": bool(value)}, actor=actor)


def decide_fact(fid, decision, actor="ekspert", comment=None, value=None):
    f = db.get("facts", fid)
    upd = {"status": decision}
    if value is not None:
        if f.get("value_num") is not None or isinstance(value, (int, float)):
            try:
                upd["value_num"] = float(value)
            except ValueError:
                upd["value_text"] = str(value)
        else:
            upd["value_text"] = str(value)
        upd["method"] = "manual"
    db.update("facts", fid, upd)
    db.audit(f"fact.{decision}", "fact", fid, before={k: f.get(k) for k in upd}, after=upd, comment=comment, actor=actor)
    if f.get("procurement_id"):
        p = db.get("projects", f["project_id"])
        pr = db.get("procurements", f["procurement_id"])
        if p and pr:
            pipeline._build_contract(p, pr, None)
    return db.get("facts", fid)


def decide_link(lid, decision, actor="ekspert", comment=None):
    link = db.get("links", lid)
    if not link:
        raise ValueError("Brak powiązania")
    db.update("links", lid, {"status": decision, "reviewer": actor, "review_comment": comment, "reviewed_at": now_iso()})
    db.audit(f"link.{decision}", "link", lid, before={"status": link["status"]}, after={"status": decision}, comment=comment, actor=actor)
    pid = link["project_id"]
    if decision == "rejected":
        if link["from_type"] == "project" and link["to_type"] == "bzp":
            for pr in db.q("SELECT * FROM procurements WHERE link_id=?", (lid,)):
                _remove_procurement(pr["id"])
        if link["to_type"] == "bzp":
            for n in db.q("SELECT * FROM notices WHERE link_id=?", (lid,)):
                _remove_notice(n["id"])
    elif decision == "approved" and link["from_type"] == "project" and link["to_type"] == "bzp":
        if not db.q1("SELECT id FROM procurements WHERE link_id=?", (lid,)):
            payload = (db.jload(link["basis"], {}) or {}).get("payload") or {}
            p = db.get("projects", pid)
            n = dict(payload)
            row = db.q1("SELECT text FROM notices WHERE project_id=? AND notice_number=?", (pid, link["to_ref"]))
            n["text"] = row["text"] if row else ""
            stats = {"notices": 0, "procurements": 0, "facts": 0, "events": 0, "links_proposed": 0, "errors": 0}
            prid = db.insert("procurements", {
                "project_id": pid, "bzp_number": n.get("bzp_number"), "tender_id": n.get("tender_id"), "title": n.get("title"),
                "cpv": n.get("cpv"), "organization_name": n.get("organization_name"), "organization_nip": n.get("organization_nip"),
                "organization_id": n.get("organization_id"), "publication_date": n.get("publication_date"), "link_id": lid,
                "source_id": db.add_source("bzp", title=f"Ogłoszenie o zamówieniu {n.get('notice_number')}", url=n.get("url"), ref=n.get("notice_number")),
            })
            pipeline._store_notice(p, n, n.get("url"), now_iso(), procurement_id=prid, link_id=lid)
            pr = db.get("procurements", prid)
            pipeline._facts_from_notice(p, prid, db.q1("SELECT id FROM notices WHERE procurement_id=? ORDER BY id LIMIT 1", (prid,))["id"], n)
            pipeline._related_notices(p, pr, stats, lambda m: None)
            pipeline._assign_parts(p, pr)
            pipeline._build_contract(p, pr, None)
            pipeline._computed_events(p, None)
    return db.get("links", lid)


def _remove_notice(nid):
    db.x("DELETE FROM facts WHERE notice_id=?", (nid,))
    db.x("UPDATE events SET status='rejected', review_comment='usunięte: odrzucone powiązanie ogłoszenia' WHERE notice_id=? AND status='proposed'", (nid,))
    db.x("DELETE FROM contract_changes WHERE notice_id=?", (nid,))
    db.x("DELETE FROM notices WHERE id=?", (nid,))


def _remove_procurement(prid):
    for n in db.q("SELECT id FROM notices WHERE procurement_id=?", (prid,)):
        _remove_notice(n["id"])
    db.x("DELETE FROM facts WHERE procurement_id=?", (prid,))
    db.x("UPDATE events SET status='rejected', review_comment='usunięte: odrzucone powiązanie postępowania' WHERE procurement_id=? AND status='proposed'", (prid,))
    db.x("DELETE FROM contracts WHERE procurement_id=?", (prid,))
    db.x("DELETE FROM procurements WHERE id=?", (prid,))


def decide_category(code, decision, actor="ekspert", changes=None):
    row = db.get("risk_catalog", code, key="code")
    upd = {"status": decision}
    for k in ("name", "description", "effects", "patterns", "mitigations", "clauses", "checks"):
        if changes and k in changes:
            upd[k] = changes[k]
    db.update("risk_catalog", code, upd, key="code")
    db.audit(f"risk.{decision}", "risk_catalog", code, before={k: row.get(k) for k in upd} if row else None, after=upd, actor=actor)


def save_risk(data, actor="ekspert"):
    code = data["code"].strip().upper()
    row = db.get("risk_catalog", code, key="code")
    payload = {k: data.get(k) for k in ("name", "description", "effects", "patterns", "mitigations", "clauses", "checks") if k in data}
    for k in ("patterns", "mitigations", "clauses", "checks"):
        if isinstance(payload.get(k), str):
            payload[k] = [s.strip() for s in payload[k].split("\n") if s.strip()]
    if row:
        db.update("risk_catalog", code, payload, key="code")
        db.audit("risk.update", "risk_catalog", code, before={k: row.get(k) for k in payload}, after=payload, actor=actor)
    else:
        payload.update({"code": code, "status": data.get("status", "approved"), "proposed_by": actor, "updated_at": now_iso()})
        db.insert("risk_catalog", payload)
        db.audit("risk.create", "risk_catalog", code, after=payload, actor=actor)


def save_event_type(data, actor="ekspert"):
    code = data["code"].strip().upper()
    row = db.get("event_types", code, key="code")
    payload = {"name": data["name"], "risk_codes": data.get("risk_codes") or [], "patterns": data.get("patterns") or []}
    for k in ("patterns", "risk_codes"):
        if isinstance(payload[k], str):
            payload[k] = [s.strip() for s in payload[k].replace(",", "\n").split("\n") if s.strip()]
    if row:
        db.update("event_types", code, payload, key="code")
    else:
        payload.update({"code": code, "status": "approved", "updated_at": now_iso()})
        db.insert("event_types", payload)
    db.audit("event_type.save", "event_types", code, before=row, after=payload, actor=actor)


def add_manual_event(pid, data, actor="ekspert"):
    ev = {k: data.get(k) for k in ("risk_code", "event_type", "title", "quote", "cause", "mitigation", "mitigation_effective", "cost_impact", "delay_days", "page")}
    ev.update({"method": "manual", "confidence": 1.0, "snippet": data.get("quote")})
    src = db.add_source("manual", title=data.get("source_title") or f"wpis eksperta ({actor})", url=data.get("source_url"), ref=f"manual:{now_iso()}")
    eid = pipeline._add_event(pid, ev, source_id=src, document_id=data.get("document_id"))
    if eid:
        db.update("events", eid, {"status": "approved", "reviewer": actor, "reviewed_at": now_iso()})
        db.audit("event.manual", "event", eid, after=ev, actor=actor)
    return eid


def update_project(pid, data, actor="ekspert"):
    allowed = ("name", "description", "subsector_main", "subsectors_extra", "work_type", "formula", "length_km", "status", "voivodeship")
    p = db.get("projects", pid)
    upd = {k: data[k] for k in allowed if k in data}
    if "length_km" in upd and upd["length_km"] not in (None, ""):
        upd["length_km"] = float(str(upd["length_km"]).replace(",", "."))
    db.update("projects", pid, upd)
    db.audit("project.edit", "project", pid, before={k: p.get(k) for k in upd}, after=upd, actor=actor)


def history(entity=None, entity_id=None, limit=200):
    sql, params = "SELECT * FROM audit_log", []
    if entity:
        sql += " WHERE entity=?"
        params.append(entity)
        if entity_id is not None:
            sql += " AND entity_id=?"
            params.append(str(entity_id))
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    rows = db.q(sql, params)
    for r in rows:
        r["before"] = db.jload(r["before"], r["before"])
        r["after"] = db.jload(r["after"], r["after"])
    return rows
