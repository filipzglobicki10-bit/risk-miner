"""Automatyczne budowanie bazy przypadków.

import_records()  — rekordy z pliku XLS(X)/CSV organizatora (lub innego, o podobnych nagłówkach)
enrich_project()  — wyszukanie i powiązanie ogłoszeń BZP (+ TED), ekstrakcja faktów, wyliczenie zdarzeń
add_document()    — dokument (PDF/DOCX/XLSX/CSV/HTML) -> tekst ze stronami -> fakty, zdarzenia, porównanie z dotychczasową wiedzą
project_metrics() — koszty i terminy liczone na bieżąco z faktów niezaodrzuconych przez eksperta
"""
import datetime as dt
import json
import re
import traceback

from . import bzp, config, db, extract, knowledge, llm, rules, ted
from .util import (
    add_duration, classify_identifier, days_between, extract_length_km, find_bzp_numbers, fold, nip_valid, normalize_bzp,
    fmt_pln, normalize_nip, now_iso, parse_amount, ratio_similarity, sha256, year_from_identifier,
)

HEADER_MAP = {
    "lp": "lp",
    "identyfikator rekordu": "record_id",
    "rodzaj identyfikatora odbiorcy": "beneficiary_id_type",
    "identyfikator odbiorcy": "beneficiary_id",
    "nazwa odbiorcy": "beneficiary_name",
    "typ odbiorcy": "beneficiary_type",
    "kraj": "country",
    "kod wojewodztwa (teryt)": "teryt",
    "wojewodztwo": "voivodeship",
    "siedziba odbiorcy": "city",
    "nazwa przedsiewziecia": "name",
    "zakres rekordu": "scope",
    "rodzaj identyfikatora publicznego": "public_id_type",
    "identyfikator publiczny": "public_id",
    "obszar tematyczny": "theme",
    "rodzaj zamowienia": "order_type",
    "rezim prawny": "legal_regime",
    "waluta rozliczen": "currency",
    "status przedsiewziecia": "status",
    "zrodlo rekordu": "record_source",
    "data sporzadzenia rekordu": "record_date",
    "wersja rekordu": "record_version",
    "adnotacja instytucji": "annotation",
    # aliasy (inne pliki wsadowe)
    "nazwa projektu": "name", "tytul projektu": "name", "numer projektu": "public_id", "beneficjent": "beneficiary_name",
    "nip": "beneficiary_id", "opis": "description", "opis projektu": "description", "numer ogloszenia": "public_id",
}


# ---------------------------------------------------------------- import rekordów

def _rows_from_file(filename, data):
    fl = filename.lower()
    if fl.endswith((".xlsx", ".xlsm")):
        sheets = extract.read_xlsx(data)
        for name, rows in sheets.items():
            for i, r in enumerate(rows):
                hdr = [fold(str(c or "")).strip() for c in r]
                if sum(1 for h in hdr if h in HEADER_MAP) >= 2:
                    return name, i, hdr, rows[i + 1:]
        raise ValueError("Nie znaleziono arkusza z nagłówkami rekordów (np. 'Nazwa przedsięwzięcia', 'Identyfikator publiczny').")
    if fl.endswith((".csv", ".tsv", ".txt")):
        import csv
        import io
        txt = data.decode("utf-8-sig", "ignore")
        dialect = csv.Sniffer().sniff(txt[:3000], delimiters=";,\t")
        rows = list(csv.reader(io.StringIO(txt), dialect))
        hdr = [fold(c).strip() for c in rows[0]]
        return "csv", 0, hdr, rows[1:]
    if fl.endswith(".xls"):
        raise ValueError("Stary format .xls — zapisz plik jako .xlsx lub .csv.")
    raise ValueError("Nieobsługiwany format pliku rekordów.")


def parse_annotation(text):
    """Adnotacja instytucji (KPO): wartość, dofinansowanie, opis w cudzysłowie."""
    out = {}
    if not text:
        return out
    m = re.search(r"Warto\w+ przedsi\w+:\s*([\d\s .,]+)\s*z", text)
    if m:
        out["project_value"] = parse_amount(m.group(1))
    m = re.search(r"dofinansowanie:\s*([\d\s .,]+)\s*z", text)
    if m:
        out["funding"] = parse_amount(m.group(1))
    m = re.search(r"Opis:\s*[„\"](.+?)[”\"]\s*$", text, re.S)
    if m:
        out["description"] = m.group(1).strip()
    m = re.search(r"(KPO, inwestycja [A-Z0-9.]+|Program [^.]+\(\w+\))", text)
    if m:
        out["programme"] = m.group(1)
    return out


def import_records(filename, data, actor="system"):
    sheet, hdr_row, hdr, rows = _rows_from_file(filename, data)
    src_file = db.add_source("xlsx", title=filename, ref=filename, sha=sha256(data), meta={"sheet": sheet})
    created, updated, skipped = 0, 0, 0
    ids = []
    for i, r in enumerate(rows):
        rec = {}
        for j, h in enumerate(hdr):
            f = HEADER_MAP.get(h)
            if f and j < len(r) and r[j] not in (None, ""):
                rec[f] = str(r[j]).strip() if not isinstance(r[j], (int, float)) else r[j]
        if not rec.get("name"):
            skipped += 1
            continue
        excel_row = hdr_row + i + 2
        src = db.add_source("xlsx", title=f"{filename} — {sheet}, wiersz {excel_row}", ref=f"{filename}:{sheet}!{excel_row}",
                            sha=sha256(json.dumps(rec, ensure_ascii=False, default=str)), meta={"file_source_id": src_file})
        rec.pop("lp", None)
        for k in ("teryt", "record_version", "beneficiary_id"):
            if k in rec:
                v = rec[k]
                rec[k] = str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
        if isinstance(rec.get("record_date"), (int, float)):
            rec["record_date"] = extract.excel_date(rec["record_date"])
        ann = parse_annotation(rec.get("annotation"))
        if ann.get("description") and not rec.get("description"):
            rec["description"] = ann["description"]
        id_type, id_norm = classify_identifier(rec.get("public_id"))
        rec["public_id_normalized"] = id_norm
        if rec.get("beneficiary_id_type", "NIP").upper() == "NIP" or not rec.get("beneficiary_id_type"):
            rec["nip_valid"] = nip_valid(rec.get("beneficiary_id"))
        text = " ".join(str(rec.get(k) or "") for k in ("name", "description"))
        main, extra = rules.classify_subsectors(text)
        rec.update({"subsector_main": main, "subsectors_extra": extra, "work_type": rules.work_type(text),
                    "formula": rules.formula(text), "length_km": extract_length_km(text), "source_id": src})
        if not rec.get("record_id"):
            rec["record_id"] = "IMP-" + sha256(rec["name"] + str(rec.get("public_id")))[:8]
        existing = db.get("projects", rec["record_id"], key="record_id")
        if existing:
            before = {k: existing.get(k) for k in rec}
            db.update("projects", existing["id"], rec)
            pid = existing["id"]
            updated += 1
            db.audit("project.update", "project", pid, before=before, after=rec, actor=actor, comment=f"import {filename}")
        else:
            rec["created_at"] = now_iso()
            rec["enrich_status"] = "nowy"
            pid = db.insert("projects", rec)
            created += 1
            db.audit("project.create", "project", pid, after=rec, actor=actor, comment=f"import {filename}")
        ids.append(pid)
        for key in ("project_value", "funding"):
            if ann.get(key):
                _add_fact(pid, key, value_num=ann[key], unit="PLN", vat="brutto", source_id=src,
                          quote=(rec.get("annotation") or "")[:300], confidence=0.95, method="xlsx")
        if not rec.get("nip_valid") and rec.get("beneficiary_id"):
            db.insert("monitor_events", {"project_id": pid, "kind": "walidacja",
                                         "message": f"NIP {rec.get('beneficiary_id')} nie przechodzi walidacji sumy kontrolnej."})
    return {"created": created, "updated": updated, "skipped": skipped, "project_ids": ids, "sheet": sheet}


# ---------------------------------------------------------------- pomocnicze zapisy

def _add_fact(pid, key, value_num=None, value_text=None, unit=None, vat="nd", source_id=None, notice_id=None,
              document_id=None, page=None, quote=None, confidence=0.8, method="notice-parser", procurement_id=None, contract_id=None,
              part=None):
    dup = db.q1(
        "SELECT id FROM facts WHERE project_id=? AND key=? AND IFNULL(value_num,-1)=IFNULL(?,-1) AND IFNULL(value_text,'')=IFNULL(?,'') "
        "AND IFNULL(notice_id,0)=IFNULL(?,0) AND IFNULL(document_id,0)=IFNULL(?,0) AND IFNULL(part,0)=IFNULL(?,0)",
        (pid, key, value_num, value_text, notice_id, document_id, part),
    )
    if dup:
        return dup["id"], False
    fid = db.insert("facts", {
        "project_id": pid, "procurement_id": procurement_id, "contract_id": contract_id, "key": key, "value_num": value_num,
        "value_text": value_text, "unit": unit, "vat": vat, "source_id": source_id, "notice_id": notice_id,
        "document_id": document_id, "page": page, "quote": quote, "confidence": confidence, "method": method, "part": part,
        "status": "approved" if method == "xlsx" else "proposed",
    })
    return fid, True


def _add_event(pid, ev, **refs):
    fp = ev.get("fingerprint") or sha256(f"{pid}|{ev.get('event_type')}|{ev.get('risk_code')}|{ev.get('quote') or ev.get('title')}")[:24]
    if db.q1("SELECT id FROM events WHERE project_id IS ? AND fingerprint=?", (pid, fp)):
        return None
    data = {k: ev.get(k) for k in ("risk_code", "event_type", "title", "snippet", "quote", "page", "cost_impact", "delay_days",
                                   "cause", "mitigation", "mitigation_effective", "confidence", "method", "rule_id")}
    data.update({k: v for k, v in refs.items() if v is not None})
    data.update({"project_id": pid, "fingerprint": fp, "status": "proposed"})
    eid = db.insert("events", data)
    return eid


def _add_link(pid, from_type, from_id, to_type, to_ref, reasons, confidence, method, payload=None):
    existing = db.q1("SELECT * FROM links WHERE project_id=? AND from_type=? AND IFNULL(from_id,0)=IFNULL(?,0) AND to_type=? AND to_ref=?",
                     (pid, from_type, from_id, to_type, to_ref))
    if existing:
        return existing["id"], existing["status"]
    auto = config.get().get("link_auto_accept_confidence", 0.95)
    status = "auto" if confidence >= auto and method == "identifier" else "proposed"
    lid = db.insert("links", {"project_id": pid, "from_type": from_type, "from_id": from_id, "to_type": to_type, "to_ref": to_ref,
                              "basis": {"reasons": reasons, "payload": payload}, "confidence": round(confidence, 2),
                              "method": method, "status": status})
    return lid, status


# ---------------------------------------------------------------- BZP: dopasowanie i wzbogacenie


def _window_for(p):
    t, norm = classify_identifier(p.get("public_id"))
    year = year_from_identifier(t, norm) or dt.date.today().year - 2
    years_after = config.get()["bzp"].get("search_window_years_after", 4)
    return t, norm, year, f"{year - 1}-01-01T00:00:00Z", f"{min(year + years_after, dt.date.today().year + 1)}-12-31T23:59:59Z"


def org_core_name(name, city=None):
    """„Gmina Kartuzy – Urząd Miejski w Kartuzach” -> „Kartuzy” (API BZP filtruje po fragmencie nazwy zamawiającego)."""
    n = re.split(r"\s[–-]\s", name or "")[0]
    n = re.sub(r"(?i)^(gmina miasto|miasto i gmina|gmina miejska|gmina wiejska|gmina|miasto|urz[aą]d miejski w|urz[aą]d gminy w?)\s+", "", n.strip())
    n = n.strip(" ,.")
    if len(n) < 3 and city:
        n = city
    return n


def scope_part(p):
    m = re.search(r"cz[eę]ść\s*(\d+)", (p.get("scope") or ""), re.I)
    return int(m.group(1)) if m else None


def _score_candidate(p, n):
    reasons, score = [], 0.0
    nip = normalize_nip(p.get("beneficiary_id"))
    if nip and n.get("organization_nip") == nip:
        score += 0.45
        reasons.append(f"NIP zamawiającego zgodny ({nip})")
    elif n.get("organization_name") and ratio_similarity(n["organization_name"], p.get("beneficiary_name") or "") > 0.6:
        score += 0.25
        reasons.append(f"nazwa zamawiającego podobna: „{n['organization_name']}”")
    sim = ratio_similarity(n.get("title") or "", (p.get("name") or "") + " " + (p.get("description") or "")[:300])
    sim_name = ratio_similarity(n.get("title") or "", p.get("name") or "")
    s = max(sim, sim_name)
    score += 0.5 * s
    reasons.append(f"podobieństwo przedmiotu zamówienia do nazwy przedsięwzięcia: {s:.0%}")
    if p.get("city") and p["city"].lower() in (n.get("title") or "").lower() + (n.get("organization_city") or "").lower():
        score += 0.05
        reasons.append(f"miejscowość „{p['city']}” w danych ogłoszenia")
    return min(score, 0.94), reasons



def enrich_project(pid, log=None, include_ted=True):
    """Wyszukuje dane w BZP/TED i buduje strukturę: postępowania, ogłoszenia, umowy (z częściami), zmiany, fakty, zdarzenia.

    Strategia dopasowana do faktycznego zachowania API BZP (sprawdzone na kopii organizatora): filtry działają dla
    NoticeType, NoticeNumber, PublicationDateFrom/To i OrganizationName (fragment nazwy, bez względu na wielkość liter);
    OrganizationId, TenderId i NIP są ignorowane — dlatego powiązane ogłoszenia pobieramy po nazwie zamawiającego,
    a łączymy lokalnie po tenderId / numerze ogłoszenia w treści.
    """
    logs = []

    def L(msg):
        logs.append(f"{now_iso()} {msg}")
        if log:
            log(msg)

    p = db.get("projects", pid)
    if not p:
        raise ValueError("Brak projektu")
    db.update("projects", pid, {"enrich_status": "w toku"})
    stats = {"notices": 0, "procurements": 0, "facts": 0, "events": 0, "links_proposed": 0, "errors": 0, "data_issues": 0}
    try:
        id_type, id_norm, year, dfrom, dto = _window_for(p)
        part = scope_part(p)
        L(f"Projekt {p['record_id']}: identyfikator {id_type} {id_norm}, zakres: {p.get('scope') or '—'}, okno {dfrom[:10]}–{dto[:10]}")
        base_notices = []
        nip = normalize_nip(p.get("beneficiary_id"))
        if id_type == "BZP":
            items, url, fetched = _safe_search(L, stats, "ContractNotice", NoticeNumber=id_norm)
            match = [n for n in map(bzp.normalize_notice, items) if n["notice_number"] == id_norm or n["bzp_number"] == normalize_bzp(id_norm)[1]]
            for n in match[:1]:
                reasons = [f"identyfikator: numer ogłoszenia BZP {id_norm}"]
                conf = 0.99
                if nip and n.get("organization_nip") and n["organization_nip"] != nip:
                    reasons.append(f"UWAGA: NIP w ogłoszeniu ({n['organization_nip']}) różni się od NIP odbiorcy ({nip})")
                    conf = 0.7
                    _data_issue(p, f"NIP odbiorcy w rekordzie ({nip}) różni się od NIP zamawiającego w ogłoszeniu {id_norm} ({n['organization_nip']}).", stats)
                elif nip and n.get("organization_nip") == nip:
                    reasons.append("NIP zamawiającego zgodny z rekordem")
                sim = ratio_similarity(n.get("title") or "", p.get("name") or "")
                if sim < 0.35:
                    reasons.append(f"UWAGA: przedmiot zamówienia mało podobny do nazwy przedsięwzięcia ({sim:.0%})")
                    conf = min(conf, 0.75)
                    _data_issue(p, f"Ogłoszenie {id_norm} dotyczy „{(n.get('title') or '')[:90]}” — nazwa przedsięwzięcia w rekordzie jest inna (podobieństwo {sim:.0%}).", stats)
                base_notices.append((n, url, fetched, reasons, conf, "identifier"))
            if not match and not stats["errors"]:
                L(f"Numer {id_norm} nie występuje w BZP — szukam postępowania po zamawiającym i przedmiocie.")
                _data_issue(p, f"Numer ogłoszenia {id_norm} z rekordu nie występuje w BZP (możliwy błąd w danych wejściowych). Zaproponowano kandydatów po NIP i przedmiocie.", stats)
                base_notices += _candidates(p, nip, dfrom, dto, stats, L, prefix=f"numer {id_norm} z rekordu nie istnieje w BZP")
        else:
            base_notices += _candidates(p, nip, dfrom, dto, stats, L, prefix=f"brak wspólnego identyfikatora ({id_type}) — dopasowanie przybliżone")
        for n, url, fetched, reasons, conf, method in base_notices:
            _attach_procurement(p, n, url, fetched, reasons, conf, method, stats, L)
        for pr in db.q("SELECT * FROM procurements WHERE project_id=?", (pid,)):
            _related_notices(p, pr, stats, L)
            _assign_parts(p, pr)
            _reconcile(p, pr, L, stats)
            _build_contract(p, pr, L)
        if include_ted and config.get()["ted"].get("enabled") and nip:
            try:
                items, turl, tfetched = ted.search(nip=nip, log=L)
                for it in items[:10]:
                    s_ = ratio_similarity(it.get("title") or "", p["name"])
                    if s_ >= 0.35:
                        _add_link(pid, "project", pid, "ted", it["publication_number"],
                                  ["NIP zamawiającego w treści ogłoszenia TED", f"podobieństwo tytułu {s_:.0%}"],
                                  0.4 + 0.5 * s_, "text-match", payload=it)
                        stats["links_proposed"] += 1
            except Exception as e:
                L(f"TED niedostępny: {e}")
        stats["events"] += _computed_events(p, L)
        status = "wzbogacony" if db.q1("SELECT id FROM procurements WHERE project_id=?", (pid,)) else (
            "błąd źródła" if stats["errors"] else "brak dopasowania")
        db.update("projects", pid, {"enrich_status": status, "last_checked": now_iso(), "needs_review": 1,
                                    "enrich_log": "\n".join(logs[-300:])})
        db.audit("project.enrich", "project", pid, after=stats)
    except Exception as e:
        L("Błąd: " + str(e))
        db.update("projects", pid, {"enrich_status": "błąd", "enrich_log": "\n".join(logs[-300:]) + "\n" + traceback.format_exc()[-2000:]})
        stats["errors"] += 1
    return stats


def _data_issue(p, message, stats=None):
    if not db.q1("SELECT id FROM monitor_events WHERE project_id=? AND kind='jakość danych' AND message=?", (p["id"], message)):
        db.insert("monitor_events", {"project_id": p["id"], "kind": "jakość danych", "message": message})
        if stats is not None:
            stats["data_issues"] = stats.get("data_issues", 0) + 1


def _candidates(p, nip, dfrom, dto, stats, L, prefix):
    core = org_core_name(p.get("beneficiary_name"), p.get("city"))
    items, url, fetched = _safe_search(L, stats, "ContractNotice", OrganizationName=core, PublicationDateFrom=dfrom, PublicationDateTo=dto)
    cands = []
    for n in map(bzp.normalize_notice, items):
        if nip and n.get("organization_nip") and n["organization_nip"] != nip:
            continue  # inny zamawiający o podobnej nazwie
        sc, reasons = _score_candidate(p, n)
        if sc >= 0.55:
            cands.append((sc, n, reasons))
    cands.sort(key=lambda c: -c[0])
    L(f"Kandydaci (zamawiający „{core}”, {len(items)} ogłoszeń w oknie): {len(cands)} powyżej progu")
    return [(n, url, fetched, [prefix] + reasons, sc, "text-match") for sc, n, reasons in cands[:4]]


def _safe_search(L, stats, notice_type, **f):
    try:
        items, url, fetched = bzp.search(notice_type, log=L, **f)
        return items, url, fetched
    except Exception as e:
        stats["errors"] += 1
        L(f"BZP niedostępne ({notice_type}): {e}")
        return [], None, None


def _store_notice(p, n, url, fetched, procurement_id=None, link_id=None):
    existing = None
    if n.get("object_id"):
        existing = db.q1("SELECT id FROM notices WHERE project_id=? AND object_id=?", (p["id"], n["object_id"]))
    if not existing and n.get("notice_number"):
        existing = db.q1("SELECT id FROM notices WHERE project_id=? AND notice_number=? AND IFNULL(notice_type,'')=IFNULL(?,'')",
                         (p["id"], n["notice_number"], n.get("notice_type")))
    if existing:
        return existing["id"], False
    src = db.add_source("bzp", title=f"{bzp.NOTICE_TYPE_LABELS.get(n.get('notice_type'), n.get('notice_type'))} {n.get('notice_number') or ''}",
                        url=n.get("url") or url, ref=n.get("notice_number") or n.get("object_id"), fetched_at=fetched,
                        sha=sha256(n.get("text") or ""), meta={"api_url": url})
    nid = db.insert("notices", {
        "procurement_id": procurement_id, "project_id": p["id"], "notice_type": n.get("notice_type"),
        "notice_number": n.get("notice_number"), "bzp_number": n.get("bzp_number"), "object_id": n.get("object_id"),
        "tender_id": n.get("tender_id"), "publication_date": n.get("publication_date"), "title": n.get("title"),
        "url": n.get("url"), "text": n.get("text"), "raw_json": {k: v for k, v in n.items() if k != "text"}, "link_id": link_id,
        "source_id": src,
    })
    return nid, True


def _attach_procurement(p, n, url, fetched, reasons, conf, method, stats, L):
    pid = p["id"]
    lid, status = _add_link(pid, "project", pid, "bzp", n.get("notice_number"), reasons, conf, method,
                            payload={k: v for k, v in n.items() if k != "text"})
    if status == "proposed":
        stats["links_proposed"] += 1
    if status == "rejected":
        return None
    # tworzymy postępowanie tylko dla dopasowania najlepszego lub pewnego (pozostałe kandydatury czekają na eksperta)
    existing = db.q1("SELECT * FROM procurements WHERE project_id=? AND bzp_number=?", (pid, n.get("bzp_number")))
    if existing:
        return existing["id"]
    if method == "text-match":
        best = db.q1("SELECT MAX(confidence) c FROM links WHERE project_id=? AND to_type='bzp' AND status!='rejected'", (pid,))
        if best and best["c"] and conf < best["c"] - 1e-6:
            return None
    src = db.add_source("bzp", title=f"Ogłoszenie o zamówieniu {n.get('notice_number')}", url=n.get("url") or url,
                        ref=n.get("notice_number"), fetched_at=fetched)
    prid = db.insert("procurements", {
        "project_id": pid, "bzp_number": n.get("bzp_number"), "tender_id": n.get("tender_id"), "title": n.get("title"),
        "cpv": n.get("cpv"), "order_type": n.get("order_type"), "organization_name": n.get("organization_name"),
        "organization_nip": n.get("organization_nip"), "organization_id": n.get("organization_id"),
        "publication_date": n.get("publication_date"), "result": n.get("procedure_result"), "link_id": lid, "source_id": src,
    })
    stats["procurements"] += 1
    nid, new = _store_notice(p, n, url, fetched, procurement_id=prid, link_id=lid)
    if new:
        stats["notices"] += 1
        stats["facts"] += _facts_from_notice(p, prid, nid, n)
    L(f"Postępowanie {n.get('bzp_number')} ({conf:.0%}, {method}): {n.get('title')}")
    return prid



def _related_notices(p, pr, stats, L):
    cfg = config.get()["bzp"]
    pub = (pr.get("publication_date") or "")[:10] or f"{dt.date.today().year - 3}-01-01"
    dto = f"{min(int(pub[:4]) + cfg.get('search_window_years_after', 4), dt.date.today().year + 1)}-12-31T23:59:59Z"
    org = pr.get("organization_name") or org_core_name(p.get("beneficiary_name"), p.get("city"))
    for nt in cfg.get("related_notice_types", []):
        items, url, fetched = _safe_search(L, stats, nt, OrganizationName=org, PublicationDateFrom=pub + "T00:00:00Z", PublicationDateTo=dto)
        for n in map(bzp.normalize_notice, items):
            reasons, conf, method = [], 0.0, "text-match"
            if pr.get("tender_id") and n.get("tender_id") == pr["tender_id"]:
                reasons.append(f"wspólny identyfikator postępowania (tenderId {pr['tender_id']})")
                conf, method = 0.99, "identifier"
            elif pr.get("bzp_number") and pr["bzp_number"] in find_bzp_numbers(n.get("text")):
                reasons.append(f"numer ogłoszenia o zamówieniu {pr['bzp_number']} przywołany w treści")
                conf, method = 0.96, "identifier"
            else:
                same_org = (pr.get("organization_nip") and n.get("organization_nip") == pr["organization_nip"])
                if not same_org:
                    continue
                s_ = ratio_similarity(n.get("title") or "", pr.get("title") or "")
                if s_ < 0.6:
                    continue
                reasons += ["ten sam zamawiający (NIP)", f"podobieństwo przedmiotu zamówienia {s_:.0%}", "brak wspólnego tenderId — do weryfikacji"]
                conf = 0.35 + 0.5 * s_
            if n.get("publication_date") and pr.get("publication_date") and n["publication_date"] < pr["publication_date"]:
                continue
            lid, st = _add_link(p["id"], "procurement", pr["id"], "bzp", n.get("notice_number") or n.get("object_id"), reasons, conf, method,
                                payload={k: v for k, v in n.items() if k != "text"})
            if st == "rejected":
                continue
            if st == "proposed":
                stats["links_proposed"] += 1
            nid, new = _store_notice(p, n, url, fetched, procurement_id=pr["id"], link_id=lid)
            if new:
                stats["notices"] += 1
                stats["facts"] += _facts_from_notice(p, pr["id"], nid, n, link_conf=conf)
                label = bzp.NOTICE_TYPE_LABELS.get(n.get("notice_type"), "Ogłoszenie")
                # formularze BZP czytamy strukturalnie (pola zmian, unieważnień) — skanowanie całego formularza regułami
                # dawało fałszywe alarmy na etykietach pól (np. „…zawarciem umowy albo unieważnieniem postępowania”)
                stats["events"] += _structured_events(p, pr, nid)
                L(f"  + {label} {n.get('notice_number')} ({conf:.0%})")



def _facts_from_notice(p, prid, nid, n, link_conf=0.99):
    """Fakty z formularza BZP (parser strukturalny) — każdy z cytatem pola formularza i numerem części."""
    cnt = 0
    nrow = db.get("notices", nid)
    src = nrow["source_id"]
    nt = n.get("notice_type")
    conf = round(0.9 * min(1.0, link_conf + 0.01), 2)
    if nt in ("ContractNotice", "TenderResultNotice", "ContractPerformingNotice", "AgreementUpdateNotice"):
        st = bzp.extract_structured(nt, n.get("text") or "")
        db.update("notices", nid, {"raw_json": {**(db.jload(nrow["raw_json"], {}) or {}), "structured": {"changes": st["changes"], "info": st["info"]}}})
        for f in st["facts"]:
            _, new = _add_fact(p["id"], f["key"], value_num=f.get("value_num"), value_text=f.get("value_text"), unit=f.get("unit"),
                               vat=f.get("vat"), source_id=src, notice_id=nid, quote=f.get("quote"), confidence=conf,
                               procurement_id=prid, part=f.get("part"), method="formularz BZP")
            cnt += new
    else:
        for f in bzp.parse_notice_facts(n.get("text") or ""):
            _, new = _add_fact(p["id"], f["key"], value_num=f.get("value_num"), value_text=f.get("value_text"), unit=f.get("unit"),
                               vat=f.get("vat"), source_id=src, notice_id=nid, quote=f.get("quote"), confidence=round(0.8 * link_conf, 2),
                               procurement_id=prid)
            cnt += new
    for c in n.get("contractors") or []:
        if c.get("name") and nt == "TenderResultNotice" and not db.q1("SELECT id FROM facts WHERE notice_id=? AND key='contractor'", (nid,)):
            _, new = _add_fact(p["id"], "contractor", value_text=c["name"], source_id=src, notice_id=nid,
                               quote="pole contractors w danych API BZP", confidence=0.9, procurement_id=prid, method="formularz BZP")
            cnt += new
    return cnt


def _assign_parts(p, pr):
    """Ogłoszenia o wykonaniu/zmianie umowy dotyczą jednej umowy (części) — przypisujemy część po wartości umowy lub wykonawcy."""
    parts = {}
    for f in db.q("SELECT * FROM facts WHERE procurement_id=? AND key IN ('contract_value','contractor') AND part IS NOT NULL", (pr["id"],)):
        parts.setdefault(f["part"], {})[f["key"]] = f["value_num"] if f["key"] == "contract_value" else fold(f["value_text"] or "")
    if not parts:
        return
    for n in db.q("SELECT id, notice_type FROM notices WHERE procurement_id=? AND notice_type IN ('ContractPerformingNotice','AgreementUpdateNotice')", (pr["id"],)):
        if db.q1("SELECT id FROM facts WHERE notice_id=? AND part IS NOT NULL", (n["id"],)):
            continue
        cv = db.q1("SELECT value_num FROM facts WHERE notice_id=? AND key='contract_value'", (n["id"],))
        ct = db.q1("SELECT value_text FROM facts WHERE notice_id=? AND key='contractor'", (n["id"],))
        part = None
        if cv and cv["value_num"]:
            hits = [k for k, v in parts.items() if v.get("contract_value") and abs(v["contract_value"] - cv["value_num"]) <= 1.0]
            if len(hits) == 1:
                part = hits[0]
        if part is None and ct and ct["value_text"]:
            hits = [k for k, v in parts.items() if v.get("contractor") and ratio_similarity(v["contractor"], ct["value_text"]) > 0.8]
            if len(hits) == 1:
                part = hits[0]
        if part is not None:
            db.x("UPDATE facts SET part=? WHERE notice_id=?", (part, n["id"]))
            db.x("UPDATE contract_changes SET part=? WHERE notice_id=?", (part, n["id"]))
            db.x("UPDATE events SET title=title || ' [część ' || ? || ']' WHERE notice_id=? AND title NOT LIKE '%[część%'", (part, n["id"]))


def _notice_part(nid):
    r = db.q1("SELECT part FROM facts WHERE notice_id=? AND part IS NOT NULL", (nid,))
    return r["part"] if r else None


def _reconcile(p, pr, L=None, stats=None):
    """Porządkuje ogłoszenia jednego postępowania po przypisaniu części:
    1) ogłoszenie o wykonaniu umowy opublikowane ponownie dla tej samej umowy (ta sama część i to samo ogłoszenie o wyniku)
       — obowiązuje najnowsze; starsze fakty i zdarzenia są wyłączane, a rozbieżność trafia do „jakości danych”;
    2) zdarzenia z części postępowania spoza zakresu rekordu („część N”) są wyłączane z analizy."""
    def off(nid, why):
        db.x("UPDATE facts SET status='superseded' WHERE notice_id=? AND status='proposed'", (nid,))
        db.x("UPDATE events SET status='rejected', reviewer='system', review_comment=? WHERE notice_id=? AND status='proposed'", (why, nid))
        db.x("UPDATE contract_changes SET status='rejected' WHERE notice_id=? AND status='proposed'", (nid,))

    groups = {}
    for n in db.q("SELECT * FROM notices WHERE procurement_id=? AND notice_type='ContractPerformingNotice'", (pr["id"],)):
        st = (db.jload(n["raw_json"], {}) or {}).get("structured") or {}
        ref = (st.get("info") or {}).get("result_ref") or "?"
        groups.setdefault((ref, _notice_part(n["id"])), []).append(n)
    for (ref, part), ns in groups.items():
        if len(ns) < 2:
            continue
        ns.sort(key=lambda n: ((n.get("publication_date") or ""), n["id"]))
        newest = ns[-1]
        for old in ns[:-1]:
            diffs = []
            fo = {f["key"]: f for f in db.q("SELECT * FROM facts WHERE notice_id=?", (old["id"],))}
            fn = {f["key"]: f for f in db.q("SELECT * FROM facts WHERE notice_id=?", (newest["id"],))}
            for k in sorted(set(fo) & set(fn)):
                a = fo[k]["value_num"] if fo[k]["value_num"] is not None else fo[k]["value_text"]
                b = fn[k]["value_num"] if fn[k]["value_num"] is not None else fn[k]["value_text"]
                if a != b:
                    lab = {"planned_duration_days": "okres realizacji (dni)", "contract_value": "wartość umowy", "final_paid": "wypłacono",
                           "actual_end_date": "data wykonania", "signed_date": "data zawarcia", "n_changes": "liczba zmian",
                           "performed_on_time": "w terminie", "performed_properly": "należycie"}.get(k, k)
                    fa = lambda v: fmt_pln(v) if k in ("contract_value", "final_paid") else (f"{v:.0f}" if isinstance(v, float) else v)
                    diffs.append(f"{lab}: {fa(a)} → {fa(b)}")
            so = ((db.jload(old["raw_json"], {}) or {}).get("structured") or {}).get("changes") or []
            sn = ((db.jload(newest["raw_json"], {}) or {}).get("structured") or {}).get("changes") or []
            for a, b in zip(so, sn):
                if a.get("value") != b.get("value"):
                    diffs.append(f"wartość zmiany nr {a.get('no') or '?'}: {fmt_pln(a.get('value'))} → {fmt_pln(b.get('value'))}")
            off(old["id"], f"zastąpione nowszym ogłoszeniem {newest['notice_number']}")
            _data_issue(p, f"Dla tej samej umowy{f' (część {part})' if part else ''} opublikowano kilka ogłoszeń o wykonaniu: "
                           f"{old['notice_number']} i {newest['notice_number']} (przyjęto nowsze)."
                           + (f" Różnice: {'; '.join(diffs[:4])}." if diffs else ""), stats)
            if L:
                L(f"Ogłoszenie {old['notice_number']} zastąpione przez {newest['notice_number']}")
    sp = scope_part(p)
    if sp:
        for n in db.q("SELECT id, notice_number FROM notices WHERE procurement_id=?", (pr["id"],)):
            np_ = _notice_part(n["id"])
            if np_ is not None and np_ != sp:
                db.x("UPDATE events SET status='rejected', reviewer='system', review_comment=? WHERE notice_id=? AND status='proposed'",
                     (f"dotyczy części {np_}, a rekord obejmuje część {sp}", n["id"]))
                db.x("UPDATE contract_changes SET status='rejected' WHERE notice_id=? AND status='proposed'", (n["id"],))


def _classify_change(text):
    """Kategoria ryzyka dla przyczyny zmiany umowy — najczęstsza kategoria wskazana przez reguły katalogu."""
    votes = {}
    for ev in rules.scan_pages([{"page": 1, "text": text or ""}], {"doc_type": "Ogłoszenie o zmianie umowy"}):
        # liczy się przyczyna, nie skutek: „zmiana terminu / wynagrodzenia” opisuje efekt zmiany
        if ev.get("negated") or ev.get("event_type") in ("E01", "E02", "E04", "E05"):
            continue
        code = ev["risk_code"]
        votes[code] = votes.get(code, 0) + ev["confidence"]
    return max(votes, key=votes.get) if votes else None


def _structured_events(p, pr, nid):
    """Zdarzenia ze strukturalnych pól: każda zmiana umowy (podstawa prawna, przyczyna, wartość) i każde unieważnienie."""
    n = db.get("notices", nid)
    st = (db.jload(n["raw_json"], {}) or {}).get("structured") or {}
    added = 0
    part_row = db.q1("SELECT part FROM facts WHERE notice_id=? AND part IS NOT NULL", (nid,))
    part = part_row["part"] if part_row else None
    for c in st.get("changes", []):
        basis_key, meaning = bzp.basis_meaning(c.get("basis") or c.get("legal_basis"))
        text = " ".join(x for x in (c.get("reason"), c.get("description")) if x)
        ft = fold(text)
        about_time = bool(re.search(r"termin|przedluz|wydluz|czas realizacji", ft))
        risk = _classify_change(c.get("reason") or text)
        if not risk:
            risk = {"art. 455 ust. 1 pkt 3": "R07", "art. 455 ust. 1 pkt 4": "R07", "art. 455 ust. 1 pkt 2": "R12"}.get(basis_key) or ("R06" if about_time else "R07")
        cost = c.get("value") if (c.get("value") and c.get("price_increase") != "nie") else None
        note = None
        cvn = db.q1("SELECT value_num FROM facts WHERE notice_id=? AND key='contract_value'", (nid,))
        if cost and cvn and cvn["value_num"] and cost >= 0.9 * cvn["value_num"]:
            # w polu „Wartość zmiany” wpisano wartość umowy po zmianie (spotykane w BZP) — przeliczamy na przyrost
            delta = cost - cvn["value_num"]
            note = f"W polu „Wartość zmiany” podano {fmt_pln(cost)} ≈ wartość umowy; przyjęto przyrost {fmt_pln(delta)}."
            cost = round(delta, 2) if delta > 0 else None
        if basis_key == "art. 455 ust. 1 pkt 3":
            ev_type = "E03"
        elif cost:
            ev_type = "E02"
        elif about_time:
            ev_type = "E01"
        else:
            ev_type = "E03"
        delay = None
        m = re.search(r"o\s*(\d{1,4})\s*(dni|dzien|tygodn\w*|miesi\w*)", ft)
        if m:
            k = int(m.group(1))
            delay = k * (30 if m.group(2).startswith("miesi") else 7 if m.group(2).startswith("tygod") else 1)
        fp = sha256(f"{p['id']}|change|{pr['id']}|{part}|{basis_key}|{c.get('value')}|{fold(c.get('reason') or '')[:120]}")[:24]
        if not db.q1("SELECT id FROM contract_changes WHERE project_id=? AND quote=?", (p["id"], fp)):
            db.insert("contract_changes", {
                # data zmiany tylko, gdy podana w formularzu — data publikacji ogłoszenia o wykonaniu to nie data zmiany
                "project_id": p["id"], "change_date": c.get("date"), "legal_basis": basis_key or c.get("legal_basis"),
                "description": (text if c.get("date") else f"{text} [data zmiany niepodana; zmiana wykazana w ogłoszeniu {n.get('notice_number')} z {(n.get('publication_date') or '')[:10]}]")[:1600], "value_change": c.get("value"), "term_change_days": delay, "source_id": n["source_id"],
                "notice_id": nid, "quote": fp, "status": "proposed", "part": part,
            })
        ev = {"risk_code": risk, "event_type": ev_type,
              "title": f"Zmiana umowy nr {c.get('no') or '?'}: {meaning or 'zmiana'} ({basis_key or c.get('legal_basis') or 'podstawa nieokreślona'})" + (f" [część {part}]" if part else ""),
              "quote": c.get("quote") or text[:600], "cause": (c.get("reason") or "")[:600] or None,
              "mitigation": ((c.get("description") or "")[:600] + (f" [{note}]" if note else "")) or None, "cost_impact": cost, "delay_days": delay,
              "confidence": 0.9, "method": "formularz BZP", "fingerprint": fp}
        if _add_event(p["id"], ev, notice_id=nid, procurement_id=pr["id"], source_id=n["source_id"]):
            added += 1
    for cc in (st.get("info") or {}).get("cancel", []):
        if cc.get("part") and scope_part(p) and cc["part"] != scope_part(p):
            continue
        fp = sha256(f"{p['id']}|cancel|{nid}|{cc.get('part')}")[:24]
        reason = cc.get("reason") or ""
        risk = "R13" if re.search(r"przewyzsza kwote|kwot\w* .{0,40}sfinansowani", fold(reason)) else "R11"
        ev = {"risk_code": risk, "event_type": "E08", "title": "Unieważnienie postępowania" + (f" (część {cc['part']})" if cc.get("part") else ""),
              "quote": cc.get("line") or reason[:600], "cause": reason[:600] or None, "confidence": 0.9, "method": "formularz BZP",
              "fingerprint": fp}
        if _add_event(p["id"], ev, notice_id=nid, procurement_id=pr["id"], source_id=n["source_id"]):
            added += 1
    return added


def _change_from_notice(p, pr, nid, n):
    """Zachowane dla zgodności — zmiany umów są teraz czytane strukturalnie (_structured_events)."""
    return None


def _rule_events_for_text(p, text, context, **refs):
    if not text:
        return 0
    pages = [{"page": 1, "text": text}]
    n = 0
    for ev in rules.scan_pages(pages, context):
        # ogłoszenia mają wiele pól formularza — liczą się tylko sygnały zdarzeń (nie ogólne słowa kluczowe ryzyk)
        if context.get("doc_type", "").startswith("Ogłoszenie") and not ev.get("event_type"):
            continue
        if ev.get("negated"):
            continue
        if _add_event(p["id"], ev, **refs):
            n += 1
    return n


def _best_fact(pid, key, procurement_id=None, part="any"):
    sql = "SELECT * FROM facts WHERE project_id=? AND key=? AND status IN ('approved','proposed')"
    params = [pid, key]
    if procurement_id:
        sql += " AND procurement_id=?"
        params.append(procurement_id)
    if part != "any":
        if part is None:
            sql += " AND part IS NULL"
        else:
            sql += " AND (part=? OR part IS NULL)"
            params.append(part)
    # dane planistyczne — najwcześniejsze źródło (ogłoszenie/umowa); dane wykonawcze — najnowsze
    order = "id ASC" if key in ("planned_end_date", "planned_duration_days", "signed_date", "estimated_value_net", "budget_amount") else "id DESC"
    part_first = "CASE WHEN part IS NULL THEN 1 ELSE 0 END, " if part not in ("any", None) else ""
    # warunki umowy: najpierw ogłoszenie o wyniku (sekcja UMOWA), potem ogłoszenia o umowie, na końcu ogłoszenie o zamówieniu
    src_rank = ("CASE (SELECT notice_type FROM notices WHERE notices.id=facts.notice_id) WHEN 'TenderResultNotice' THEN 0 "
                "WHEN 'ContractPerformingNotice' THEN 1 WHEN 'AgreementUpdateNotice' THEN 2 ELSE 3 END, ") if key in ("planned_end_date", "planned_duration_days", "signed_date", "contract_value") else ""
    sql += f" ORDER BY CASE status WHEN 'approved' THEN 0 ELSE 1 END, CASE method WHEN 'manual' THEN 0 ELSE 1 END, {part_first}{src_rank}confidence DESC, {order} LIMIT 1"
    return db.q1(sql, params)


def _contract_parts(pr_id):
    parts = [r["part"] for r in db.q("SELECT DISTINCT part FROM facts WHERE procurement_id=? AND part IS NOT NULL AND key IN ('contract_value','signed_date','contractor') ORDER BY part", (pr_id,))]
    return parts or [None]


def _build_contract(p, pr, L=None):
    """Umowa = złożenie faktów z ogłoszeń (wynik, zmiany, wykonanie) — osobno dla każdej części postępowania."""
    cids = []
    for part in _contract_parts(pr["id"]):
        g = lambda k: _best_fact(p["id"], k, pr["id"], part=part if part is not None else "any")
        cv, sd, pe, pdur, ae, fp = g("contract_value"), g("signed_date"), g("planned_end_date"), g("planned_duration_days"), g("actual_end_date"), g("final_paid")
        pp, ch, ctr, ot = g("performed_properly"), g("n_changes"), g("contractor"), g("performed_on_time")
        if not any([cv, ctr, fp]):
            continue
        planned = pe["value_text"] if pe else None
        if not planned and sd and pdur and sd.get("value_text"):
            planned = add_duration(sd["value_text"], pdur["value_num"], pdur.get("value_text"))
        data = {
            "procurement_id": pr["id"], "project_id": p["id"], "part": str(part) if part is not None else None,
            "contractor_name": ctr["value_text"] if ctr else None, "value_gross": cv["value_num"] if cv else None,
            "signed_date": sd["value_text"] if sd else None, "planned_end_date": planned,
            "actual_end_date": ae["value_text"] if ae else None, "final_paid": fp["value_num"] if fp else None,
            "performed_properly": pp["value_text"] if pp else None,
            "changed": (f"tak ({int(ch['value_num'])})" if ch and ch["value_num"] else "nie") if ch else None,
            "status": "wykonana" + (" w terminie" if ot and ot["value_text"] == "tak" else " po terminie" if ot and ot["value_text"] == "nie" else "") if (fp or ae) else "w realizacji / brak ogłoszenia o wykonaniu",
            "source_id": (cv or ctr or fp)["source_id"], "quote": (cv or ctr or fp).get("quote"),
        }
        existing = db.q1("SELECT id FROM contracts WHERE procurement_id=? AND IFNULL(part,'')=IFNULL(?,'')", (pr["id"], data["part"]))
        if existing:
            db.update("contracts", existing["id"], data)
            cid = existing["id"]
        else:
            cid = db.insert("contracts", data)
        db.x("UPDATE contract_changes SET contract_id=? WHERE project_id=? AND notice_id IN (SELECT id FROM notices WHERE procurement_id=?) AND IFNULL(CAST(part AS TEXT),'')=IFNULL(?,'')",
             (cid, p["id"], pr["id"], data["part"]))
        cids.append(cid)
    return cids[0] if cids else None


def _computed_events(p, L):
    """Zdarzenia wyliczone z danych strukturalnych (odchylenia kosztu i czasu, jedna oferta, cena vs budżet).

    Każde zdarzenie wskazuje źródło (ogłoszenie, z którego pochodzi wartość rozstrzygająca) i cytuje oba fakty.
    Uwzględnia zakres rekordu (np. „część 1”) — liczy tylko umowę tej części.
    """
    n = 0
    sp = scope_part(p)

    def ref(f):
        if not f:
            return "brak źródła"
        src = db.get("sources", f["source_id"]) if f.get("source_id") else None
        return f"{(src or {}).get('title') or 'źródło'}: „{(f.get('quote') or '').strip()[:160]}”"

    for c in db.q("SELECT * FROM contracts WHERE project_id=?", (p["id"],)):
        part = int(c["part"]) if c.get("part") else None
        if sp and part and part != sp:
            continue
        prid = c["procurement_id"]
        g = lambda k: _best_fact(p["id"], k, prid, part=part if part is not None else "any")
        cvf, fpf, aef = g("contract_value"), g("final_paid"), g("actual_end_date")
        pef = g("planned_end_date") or g("planned_duration_days")
        tag = f" [część {part}]" if part else ""
        if c.get("value_gross") and c.get("final_paid") and c["final_paid"] > c["value_gross"] * 1.005:
            diff = c["final_paid"] - c["value_gross"]
            ev = {"risk_code": "R07", "event_type": "E05", "title": f"Wypłata wyższa niż wartość umowy o {diff/c['value_gross']:.1%}".replace(".", ",") + tag,
                  "quote": f"Wartość umowy {fmt_pln(c['value_gross'])} ({ref(cvf)}); łącznie wypłacono {fmt_pln(c['final_paid'])} ({ref(fpf)}).",
                  "cost_impact": diff, "confidence": 0.95, "method": "computed"}
            n += bool(_add_event(p["id"], ev, contract_id=c["id"], procurement_id=prid, source_id=(fpf or {}).get("source_id"),
                                 notice_id=(fpf or {}).get("notice_id")))
        if c.get("value_gross") and c.get("final_paid") and c["final_paid"] < c["value_gross"] * 0.9:
            diff = c["value_gross"] - c["final_paid"]
            ev = {"risk_code": "R01", "event_type": None, "title": f"Wypłata niższa niż wartość umowy o {diff/c['value_gross']:.1%} — możliwe ograniczenie zakresu".replace(".", ",") + tag,
                  "quote": f"Wartość umowy {fmt_pln(c['value_gross'])} ({ref(cvf)}); łącznie wypłacono {fmt_pln(c['final_paid'])} ({ref(fpf)}).",
                  "cost_impact": -diff, "confidence": 0.8, "method": "computed"}
            n += bool(_add_event(p["id"], ev, contract_id=c["id"], procurement_id=prid, source_id=(fpf or {}).get("source_id"),
                                 notice_id=(fpf or {}).get("notice_id")))
        if c.get("planned_end_date") and c.get("actual_end_date"):
            d = days_between(c["planned_end_date"], c["actual_end_date"])
            if d and d > 0:
                ev = {"risk_code": "R06", "event_type": "E04", "title": f"Wykonanie po pierwotnym terminie (+{d} dni)" + tag,
                      "quote": f"Termin umowny {c['planned_end_date']} ({ref(pef)}); wykonanie {c['actual_end_date']} ({ref(aef)}).",
                      "delay_days": d, "confidence": 0.9, "method": "computed"}
                n += bool(_add_event(p["id"], ev, contract_id=c["id"], procurement_id=prid, source_id=(aef or {}).get("source_id"),
                                     notice_id=(aef or {}).get("notice_id")))
        if (c.get("performed_properly") or "").lower() == "nie":
            ppf = g("performed_properly")
            ev = {"risk_code": "R12", "event_type": "E06", "title": "Umowa niewykonana należycie (wg ogłoszenia o wykonaniu umowy)" + tag,
                  "quote": ref(ppf), "confidence": 0.9, "method": "computed"}
            n += bool(_add_event(p["id"], ev, contract_id=c["id"], procurement_id=prid, source_id=(ppf or {}).get("source_id"),
                                 notice_id=(ppf or {}).get("notice_id")))
    for f in db.q("SELECT * FROM facts WHERE project_id=? AND key='n_offers' AND status!='rejected'", (p["id"],)):
        if sp and f.get("part") and f["part"] != sp:
            continue
        if f["value_num"] == 1:
            ev = {"risk_code": "R11", "event_type": None, "title": "Tylko jedna oferta w postępowaniu (ograniczona konkurencja)" + (f" [część {f['part']}]" if f.get("part") else ""),
                  "quote": f["quote"], "confidence": 0.85, "method": "computed"}
            n += bool(_add_event(p["id"], ev, notice_id=f["notice_id"], procurement_id=f["procurement_id"], source_id=f["source_id"]))
    return n


def add_document(filename, data, project_id=None, analysis_id=None, source_url=None, actor="system"):
    pages, meta = extract.extract(filename, data)
    full = "\n".join(pg["text"] for pg in pages)
    doc_type = extract.guess_doc_type(filename, full)
    src = db.add_source("url" if source_url else "upload", title=filename, url=source_url, ref=filename, sha=sha256(data),
                        meta={"bytes": len(data), **meta})
    dup = db.q1("SELECT d.id FROM documents d JOIN sources s ON s.id=d.source_id WHERE s.sha256=? AND IFNULL(d.project_id,0)=IFNULL(?,0) AND IFNULL(d.analysis_id,0)=IFNULL(?,0)",
                (sha256(data), project_id, analysis_id))
    if dup:
        return {"document_id": dup["id"], "duplicate": True, "doc_type": doc_type}
    did = db.insert("documents", {"project_id": project_id, "analysis_id": analysis_id, "filename": filename, "doc_type": doc_type,
                                  "phase": extract.PHASES.get(doc_type, "—"), "pages_json": pages, "n_pages": len(pages),
                                  "ocr_used": int(meta.get("ocr_used", False)), "source_id": src})
    db.audit("document.add", "document", did, after={"filename": filename, "doc_type": doc_type, "pages": len(pages)}, actor=actor)
    result = {"document_id": did, "doc_type": doc_type, "pages": len(pages), "ocr_used": meta.get("ocr_used"), "warning": meta.get("warning"),
              "new_events": 0, "new_facts": 0, "confirmed": [], "contradictions": [], "bzp_numbers": []}
    if project_id is None:
        return result
    p = db.get("projects", project_id)
    # fakty
    for pg in pages:
        for f in bzp.parse_notice_facts(pg["text"]):
            prev = db.q("SELECT * FROM facts WHERE project_id=? AND key=? AND status!='rejected' AND IFNULL(document_id,0)!=?",
                        (project_id, f["key"], did))
            fid, new = _add_fact(project_id, f["key"], value_num=f.get("value_num"), value_text=f.get("value_text"), unit=f.get("unit"),
                                 vat=f.get("vat"), source_id=src, document_id=did, page=pg["page"], quote=f.get("quote"),
                                 confidence=0.7, method="rule")
            result["new_facts"] += new
            for o in prev:
                same = (o["value_num"] == f.get("value_num")) and (o["value_text"] == f.get("value_text"))
                item = {"key": f["key"], "new": f.get("value_num") or f.get("value_text"), "old": o["value_num"] or o["value_text"],
                        "old_fact_id": o["id"], "new_fact_id": fid}
                if same:
                    result["confirmed"].append(item)
                else:
                    result["contradictions"].append(item)
    # zdarzenia: reguły + (opcjonalnie) LLM
    ctx = {"doc_type": doc_type}
    for ev in rules.scan_pages(pages, ctx):
        if _add_event(project_id, ev, document_id=did, source_id=src):
            result["new_events"] += 1
    if llm.enabled():
        try:
            for ev in llm.extract_events(pages, doc_type):
                if ev.get("risk_code") == "NOWA" and ev.get("new_category_name"):
                    code = "P" + sha256(ev["new_category_name"])[:5].upper()
                    if not db.get("risk_catalog", code, key="code"):
                        db.insert("risk_catalog", {"code": code, "name": ev["new_category_name"], "status": "proposed",
                                                   "proposed_by": "LLM", "patterns": [], "mitigations": [], "clauses": [], "checks": [],
                                                   "effects": ev.get("title"), "updated_at": now_iso()})
                    ev["risk_code"] = code
                if _add_event(project_id, ev, document_id=did, source_id=src):
                    result["new_events"] += 1
        except Exception as e:
            result["llm_error"] = str(e)
    # numery BZP w dokumencie -> propozycje powiązań
    known = {r["bzp_number"] for r in db.q("SELECT bzp_number FROM procurements WHERE project_id=?", (project_id,))}
    for num in find_bzp_numbers(full):
        result["bzp_numbers"].append(num)
        if num not in known:
            _add_link(project_id, "document", did, "bzp", num, [f"numer ogłoszenia {num} występuje w dokumencie {filename}"], 0.8, "text-match")
    for c in result["contradictions"]:
        db.insert("monitor_events", {"project_id": project_id, "kind": "sprzeczność", "document_id": did,
                                     "message": f"{c['key']}: nowy dokument podaje {c['new']}, wcześniej {c['old']} — wymaga rozstrzygnięcia."})
    db.insert("monitor_events", {"project_id": project_id, "kind": "nowy dokument", "document_id": did,
                                 "message": f"Dodano {doc_type} „{filename}”: {result['new_events']} nowych sygnałów, {len(result['confirmed'])} potwierdzeń, {len(result['contradictions'])} sprzeczności."})
    for c in db.q("SELECT * FROM procurements WHERE project_id=?", (project_id,)):
        _build_contract(p, c, None)
    _computed_events(p, None)
    db.update("projects", project_id, {"needs_review": 1})
    return result


def fetch_url_document(url, project_id=None):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "RiskMiner/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        ctype = r.headers.get("Content-Type", "")
    name = url.rstrip("/").split("/")[-1] or "strona"
    if "pdf" in ctype and not name.lower().endswith(".pdf"):
        name += ".pdf"
    elif "html" in ctype and not re.search(r"\.html?$", name.lower()):
        name += ".html"
    return add_document(name, data, project_id=project_id, source_url=url)


# ---------------------------------------------------------------- metryki projektu

def project_metrics(pid):
    """Koszt i czas liczone z umów złożonych z faktów (bez odrzuconych), z uwzględnieniem zakresu rekordu (część N)."""
    p = db.get("projects", pid)
    sp = scope_part(p)
    ok_procs = [r["id"] for r in db.q(
        "SELECT pr.id FROM procurements pr LEFT JOIN links l ON l.id=pr.link_id WHERE pr.project_id=? AND IFNULL(l.status,'auto') IN ('auto','approved','proposed')",
        (pid,))]
    m = {"basis": {}, "n_procurements": len(ok_procs), "scope_part": sp}
    contracts = [c for c in db.q("SELECT * FROM contracts WHERE project_id=?", (pid,)) if c["procurement_id"] in ok_procs]
    if sp and any(c.get("part") for c in contracts):
        contracts = [c for c in contracts if c.get("part") == str(sp)]
        m["scope_note"] = f"rekord obejmuje część {sp} postępowania — liczone tylko dla tej części"
    m["n_contracts"] = len(contracts)
    cvs = [c["value_gross"] for c in contracts if c.get("value_gross")]
    fps = [c["final_paid"] for c in contracts if c.get("final_paid")]
    m["contract_value"] = sum(cvs) if cvs else None
    m["final_paid"] = sum(fps) if fps and len(fps) == len(cvs) else None
    m["basis"]["contract_value"] = [c["id"] for c in contracts if c.get("value_gross")]
    m["basis"]["final_paid"] = [c["id"] for c in contracts if c.get("final_paid")]
    by_quote = {}
    for e in db.q("SELECT quote, cost_impact FROM events WHERE project_id=? AND status IN ('approved','edited') AND event_type IN ('E02','E03') AND cost_impact IS NOT NULL", (pid,)):
        by_quote[e["quote"]] = max(by_quote.get(e["quote"], 0), e["cost_impact"])
    ev_cost = sum(by_quote.values()) or None
    by_quote = {}
    for e in db.q("SELECT quote, delay_days FROM events WHERE project_id=? AND status IN ('approved','edited') AND event_type='E01' AND delay_days IS NOT NULL", (pid,)):
        by_quote[e["quote"]] = max(by_quote.get(e["quote"], 0), e["delay_days"])
    ev_delay = sum(by_quote.values()) or None
    if m["contract_value"] and m["final_paid"]:
        m["cost_dev_pct"] = (m["final_paid"] - m["contract_value"]) / m["contract_value"]
        m["cost_dev_method"] = "wypłacono vs wartość umowy (ogłoszenie o wykonaniu umowy)"
    elif m["contract_value"] and ev_cost:
        m["cost_dev_pct"] = ev_cost / m["contract_value"]
        m["cost_dev_method"] = "suma skutków kosztowych zatwierdzonych zmian umowy (realizacja w toku)"
    else:
        m["cost_dev_pct"] = None
    sd = min((c["signed_date"] for c in contracts if c.get("signed_date")), default=None)
    pe = max((c["planned_end_date"] for c in contracts if c.get("planned_end_date")), default=None)
    ae = max((c["actual_end_date"] for c in contracts if c.get("actual_end_date")), default=None) if all(c.get("actual_end_date") for c in contracts) else None
    m.update({"signed_date": sd, "planned_end_date": pe, "actual_end_date": ae})
    m["planned_duration_days"] = days_between(sd, pe) if sd and pe else None
    if pe and ae:
        m["delay_days"] = days_between(pe, ae)
        m["delay_method"] = "data wykonania vs termin umowny"
    elif ev_delay:
        m["delay_days"] = int(ev_delay)
        m["delay_method"] = "suma przedłużeń z zatwierdzonych zmian"
    else:
        m["delay_days"] = None
    m["actual_duration_days"] = days_between(sd, ae) if sd and ae else None
    m["completed"] = bool(contracts) and all(c.get("final_paid") or c.get("actual_end_date") for c in contracts)
    part_arg = sp if sp else "any"
    n_off = _best_fact(pid, "n_offers", part=part_arg)
    m["n_offers"] = int(n_off["value_num"]) if n_off and n_off["value_num"] is not None else None
    est = _best_fact(pid, "part_value_net", part=sp) if sp else None
    est = est or _best_fact(pid, "estimated_value_net")
    m["estimated_value_net"] = est["value_num"] if est else None
    if m["estimated_value_net"] and m["contract_value"]:
        m["price_vs_estimate"] = m["contract_value"] / (m["estimated_value_net"] * 1.23) - 1  # założenie: VAT 23%
    m["n_changes"] = db.q1("SELECT COUNT(*) n FROM contract_changes WHERE project_id=? AND status!='rejected'" + (" AND (part IS NULL OR part=?)" if sp else ""),
                           (pid, sp) if sp else (pid,))["n"]
    pv = _best_fact(pid, "project_value")
    m["project_value"] = pv["value_num"] if pv else None
    m["funding"] = (_best_fact(pid, "funding") or {}).get("value_num")
    base_value = m["contract_value"] or m["project_value"]
    m["value_for_comparison"] = base_value
    m["cost_per_km"] = base_value / p["length_km"] if base_value and p.get("length_km") else None
    return m


def completeness(pid):
    """Które typy dokumentów/ogłoszeń są w paczce — braku pliku nie utożsamiamy z nieistnieniem dokumentu."""
    exp = knowledge.get("doc_expectations", [])
    types = {r["notice_type"] for r in db.q("SELECT notice_type FROM notices WHERE project_id=?", (pid,))}
    dtypes = {r["doc_type"] for r in db.q("SELECT doc_type FROM documents WHERE project_id=?", (pid,))}
    out = []
    for e in exp:
        k = e["key"]
        present = False
        if k in types:
            present = True
        elif k == "contract_terms":
            present = bool(dtypes & {"Umowa", "PPU / wzór umowy"})
        elif k == "change_info":
            present = bool(types & {"AgreementUpdateNotice", "ContractModificationNotice"}) or bool(dtypes & {"Aneks do umowy", "Ogłoszenie o zmianie umowy"})
        elif k == "control":
            present = bool(dtypes & {"Wystąpienie pokontrolne / NIK", "Orzeczenie KIO"})
        elif k == "ContractPerformingNotice":
            present = "ContractPerformingNotice" in types or "Ogłoszenie o wykonaniu umowy" in dtypes
        elif k == "TenderResultNotice":
            present = "TenderResultNotice" in types or "Ogłoszenie o wyniku postępowania" in dtypes
        elif k == "ContractNotice":
            present = "ContractNotice" in types or "Ogłoszenie o zamówieniu" in dtypes
        out.append({**e, "status": "jest w paczce" if present else "nie ma w paczce",
                    "note": None if present else "Brak w zebranym materiale nie oznacza, że dokument nie istnieje. " + e["why"]})
    return out
