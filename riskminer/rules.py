"""Silnik reguł: wykrywa w tekście sygnały zdarzeń i ryzyk wg katalogu eksperckiego.

Każde trafienie ma postać: sygnał w dokumencie -> możliwe zdarzenie -> możliwy wpływ, ze wskazaniem
strony i cytatu. Pewność reguły jest korygowana decyzjami ekspertów (zatwierdzone/odrzucone trafienia
tej samej reguły) — system uczy się bez zmian w kodzie.
"""
import re

from . import db, knowledge
from .util import find_amounts, fold, sentences, sha256

CAUSE_RE = re.compile(r"(z powodu|w zwiazku z|ze wzgledu na|spowodowan\w*|z przyczyn|wskutek|na skutek|w wyniku)\s+([^.;]{5,180})")
MITIG_RE = re.compile(r"(w celu [^.;]{5,160}|zastosowano [^.;]{5,160}|podjeto [^.;]{5,160}|zaradcz[^.;]{0,160}|wprowadzono [^.;]{5,160})")
DAYS_RE = re.compile(r"(?:o|do|przez|okres)\s*(\d{1,4})\s*(dni|dzien|tygodn\w*|miesi\w*)")
NEG_RE = re.compile(r"\b(nie (dotyczy|przewiduje sie|wystapil\w*|stwierdzono)|brak (zmian|kar|odwolan)|nie bylo)\b")


def _rule_precision(rule_id):
    """Laplace: (zatwierdzone+1)/(decyzje+2). Zwraca (mnożnik, n_decyzji)."""
    rows = db.q("SELECT decision, COUNT(*) n FROM rule_feedback WHERE rule_id=? GROUP BY decision", (rule_id,))
    a = sum(r["n"] for r in rows if r["decision"] == "approved")
    r_ = sum(r["n"] for r in rows if r["decision"] == "rejected")
    return (a + 1) / (a + r_ + 2) * 2, a + r_  # 1.0 bez decyzji


def _rejected_fingerprints():
    return {r["fingerprint"] for r in db.q("SELECT fingerprint FROM rule_feedback WHERE decision='rejected'")}


def fingerprint(rule_id, text):
    return sha256(rule_id + "|" + re.sub(r"\W+", " ", fold(text))[:300])[:24]


def scan_pages(pages, context=None):
    """Zwraca listę propozycji zdarzeń/ryzyk dla stron dokumentu.

    context: dict z kluczami doc_type (wpływa na pewność), source_weight.
    """
    context = context or {}
    risks = knowledge.risks()
    events = knowledge.event_types()
    rejected = _rejected_fingerprints()
    compiled = []
    for et in events:
        for i, p in enumerate(et["patterns"]):
            try:
                compiled.append(("event", et["code"], et["name"], et["risk_codes"], f"{et['code']}.{i}", re.compile(p)))
            except re.error:
                continue
    for rk in risks:
        for i, p in enumerate(rk["patterns"]):
            try:
                compiled.append(("risk", None, rk["name"], [rk["code"]], f"{rk['code']}.{i}", re.compile(p)))
            except re.error:
                continue

    doc_weight = {
        "Ogłoszenie o zmianie umowy": 0.9, "Ogłoszenie o wykonaniu umowy": 0.9, "Aneks do umowy": 0.9,
        "Wystąpienie pokontrolne / NIK": 0.85, "Orzeczenie KIO": 0.85, "Protokół konieczności": 0.85,
        "Ogłoszenie o wyniku postępowania": 0.75, "Umowa": 0.6, "PPU / wzór umowy": 0.45, "SWZ": 0.45,
        "PFU": 0.45, "OPZ": 0.45, "Opis inwestycji": 0.5, "Ogłoszenie o zamówieniu": 0.45,
    }.get(context.get("doc_type"), 0.6)
    # dokumenty przygotowawcze opisują ryzyko potencjalne, nie zdarzenie
    potential = context.get("doc_type") in ("PPU / wzór umowy", "SWZ", "PFU", "OPZ", "STWiORB", "Opis inwestycji", "Ogłoszenie o zamówieniu")

    found = {}
    for page in pages:
        for sent in sentences(page["text"]):
            fs = fold(sent)
            if len(fs) < 15:
                continue
            for kind, ev_code, name, risk_codes, rule_id, rx in compiled:
                m = rx.search(fs)
                if not m:
                    continue
                fp = fingerprint(rule_id, sent)
                if fp in rejected:
                    continue
                negated = bool(NEG_RE.search(fs[max(0, m.start() - 40): m.end() + 40]))
                mult, n_dec = _rule_precision(rule_id)
                conf = doc_weight * (0.55 if kind == "risk" else 0.7) * mult
                if negated:
                    conf *= 0.35
                conf = round(min(0.97, conf), 2)
                key = (ev_code or risk_codes[0], page["page"], fs[:120])
                if key in found and found[key]["confidence"] >= conf:
                    continue
                cause = CAUSE_RE.search(fs)
                mitig = MITIG_RE.search(fs)
                days = DAYS_RE.search(fs)
                delay = None
                if days and ev_code in ("E01", "E04", "E13"):
                    n = int(days.group(1))
                    unit = days.group(2)
                    delay = n * (7 if unit.startswith("tygod") else 30 if unit.startswith("miesi") else 1)
                amounts = [a for a, _, _ in find_amounts(sent) if a]
                cost = max(amounts) if amounts and ev_code in ("E02", "E03", "E05") else None
                found[key] = {
                    "risk_code": risk_codes[0] if risk_codes else None,
                    "event_type": ev_code,
                    "title": name + (" (sygnał potencjalny)" if potential or kind == "risk" else ""),
                    "snippet": sent.strip()[:600],
                    "quote": sent.strip()[:600],
                    "page": page["page"],
                    "cause": _restore(sent, cause.group(2)) if cause else None,
                    "mitigation": _restore(sent, mitig.group(1)) if mitig else None,
                    "delay_days": delay,
                    "cost_impact": cost,
                    "confidence": conf,
                    "method": "rule",
                    "rule_id": rule_id,
                    "fingerprint": fp,
                    "negated": negated,
                    "rule_decisions": n_dec,
                }
    # ogranicz szum: na stronę maks. 6 sygnałów tej samej kategorii
    out, per = [], {}
    for v in sorted(found.values(), key=lambda r: -r["confidence"]):
        k = (v["risk_code"], v["page"])
        per[k] = per.get(k, 0) + 1
        if per[k] <= 6:
            out.append(v)
    return out


def _restore(original, folded_part):
    """Odtwarza fragment z polskimi znakami: szuka pozycji w tekście złożonym."""
    fo = fold(original)
    i = fo.find(folded_part[:40])
    if i < 0:
        return folded_part
    return original[i:i + len(folded_part)].strip()


def classify_subsectors(text):
    subs = knowledge.get("subsectors", [])
    ft = fold(text)
    scores = []
    for s in subs:
        n = sum(len(re.findall(p, ft)) for p in s.get("patterns", []))
        if n:
            scores.append((n, s["name"]))
    scores.sort(reverse=True)
    if not scores:
        return "Inne obiekty wod-kan", []
    main = scores[0][1]
    # podsektor w nazwie/początku tekstu ma pierwszeństwo
    head = fold(text[:200])
    for s in subs:
        if any(re.search(p, head) for p in s.get("patterns", [])):
            main = s["name"]
            break
    extra = [n for _, n in scores if n != main]
    return main, extra


def work_type(text):
    ft = fold(text)
    if re.search(r"przebudow|moderniz|remont|wymian|renowac", ft):
        if re.search(r"\bbudow|rozbudow", ft):
            return "budowa i modernizacja"
        return "przebudowa/modernizacja"
    if re.search(r"rozbudow", ft):
        return "rozbudowa"
    return "budowa"


def formula(text):
    ft = fold(text)
    if re.search(r"zaprojektuj i (wybuduj|zbuduj)|projektuj i buduj|zaprojektowanie i (wykonanie|wybudowanie)", ft):
        return "zaprojektuj i wybuduj"
    return "tradycyjna (wg dokumentacji zamawiającego)"


def checklist_coverage(text):
    ft = fold(text)
    out = []
    for item in knowledge.get("checklist", []):
        hits = [p for p in item.get("patterns", []) if re.search(p, ft)]
        out.append({**{k: item[k] for k in ("id", "text", "ref")}, "covered": bool(hits), "evidence": hits[:3]})
    return out
