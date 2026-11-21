"""Analiza planowanej inwestycji: grupa porównawcza, prognoza kosztu i czasu, czerwone flagi, rekomendacje.

Wynik rozdziela trzy warstwy:
  dane_zrodlowe — fakty z bazy przypadków (z linkami do źródeł),
  obliczenia    — statystyki z liczebnością próby i metodą,
  wnioski       — flagi i rekomendacje (reguły katalogu + opcjonalnie narracja LLM, oznaczona).
"""
import re

from . import clauses, config, db, knowledge, llm, pipeline, rules, similarity
from . import forecast as refclass
from .util import find_amounts, fold, now_iso, percentile

VOIVODESHIPS = ["dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie", "małopolskie", "mazowieckie", "opolskie",
                "podkarpackie", "podlaskie", "pomorskie", "śląskie", "świętokrzyskie", "warmińsko-mazurskie", "wielkopolskie", "zachodniopomorskie"]
# Rdzeń przymiotnika ("wielkopolsk") łapie każdą odmianę: „w województwie wielkopolskim”, „wielkopolskiego”…
# Nie może go poprzedzać litera ani łącznik, więc „pomorsk” nie trafia w „zachodniopomorskim” ani „kujawsko-pomorskim”.
_VOIV_RE = [(v, re.compile(r"(?<![\w-])" + re.escape(v[:-2]) + r"\w*", re.IGNORECASE)) for v in VOIVODESHIPS]


def detect_voivodeship(text):
    found = [(m.start(), v) for v, rx in _VOIV_RE for m in [rx.search(text or "")] if m]
    return min(found)[1] if found else None


def _stats(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "min": min(vals), "p25": percentile(vals, 0.25), "median": percentile(vals, 0.5),
            "p75": percentile(vals, 0.75), "max": max(vals), "mean": sum(vals) / len(vals)}


def _confidence_label(n, spread=None):
    if n >= 6 and (spread is None or spread < 0.5):
        return "średnia"
    if n >= 3:
        return "niska–średnia"
    return "niska (mała próba)"


def detect_value(text):
    """Szacowana wartość inwestycji z opisu: kwota przy słowach wartość/koszt/budżet, inaczej największa kwota."""
    ft = fold(text)
    best = None
    for val, s, e in find_amounts(text):
        ctx = ft[max(0, s - 80): s]
        if re.search(r"wartos|koszt|budzet|szacun|kwot|naklad", ctx):
            if val and (best is None or val > best):
                best = val
    if best is None:
        vals = [v for v, _, _ in find_amounts(text) if v and v > 10000]
        best = max(vals) if vals else None
    return best


MONTHS = [("stycz", 1), ("lut", 2), ("marz", 3), ("marc", 3), ("kwie", 4), ("maj", 5), ("czerw", 6), ("lip", 7), ("sierp", 8),
          ("wrze", 9), ("pazdz", 10), ("listop", 11), ("grud", 12)]
DATE_RX = re.compile(r"(\d{4})-(\d{2})-(\d{2})|(\d{1,2})\.(\d{1,2})\.(\d{4})|\b(stycz\w*|lut\w*|marz\w*|marc\w*|kwie\w*|maj\w*|czerw\w*|lip\w*|sierp\w*|wrze\w*|pazdz\w*|listop\w*|grud\w*)\s+(\d{4})")


def _parse_date(m, end_of_month=False):
    from datetime import date
    import calendar
    try:
        if m.group(1):
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if m.group(4):
            return date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
        mon = next(n for k, n in MONTHS if m.group(7).startswith(k))
        y = int(m.group(8))
        return date(y, mon, calendar.monthrange(y, mon)[1] if end_of_month else 1)
    except (ValueError, StopIteration):
        return None


def detect_schedule(text):
    """Termin z umowy o dofinansowanie i planowany start przetargu — z opisu (zdania z datą i słowem-kluczem)."""
    ft = fold(text)
    deadline = start = None
    for sent in re.split(r"(?<=[.;])\s+|\n", ft):
        for m in DATE_RX.finditer(sent):
            if deadline is None and re.search(r"zakoncz|kwalifikow|dofinansow|rozlicz|termin\w* (koncow|finansow)", sent) and not re.search(r"ogloszeni\w* (przetarg|postepowan)", sent[:m.start()]):
                deadline = _parse_date(m, end_of_month=True)
            elif start is None and re.search(r"ogloszeni\w* (przetarg|postepowan)|wszczeci\w* postepowan|przetarg\w* (planowan|zostanie)", sent):
                start = _parse_date(m)
    return deadline, start


def analyze(text, title=None, analysis_id=None, extra=None):
    cfg = config.get()["analysis"]
    docs_text = ""
    doc_rows = []
    audit_pages = [{"page": None, "doc": "opis inwestycji", "text": text or ""}]
    if analysis_id:
        for d in db.q("SELECT * FROM documents WHERE analysis_id=?", (analysis_id,)):
            pages = db.jload(d["pages_json"], [])
            docs_text += "\n" + "\n".join(p["text"] for p in pages)
            doc_rows.append({"id": d["id"], "filename": d["filename"], "doc_type": d["doc_type"], "pages": d["n_pages"]})
            audit_pages += [{"page": p.get("page"), "doc": d["filename"], "text": p["text"]} for p in pages]
    full = (text or "") + "\n" + docs_text
    extra = dict(extra or {})
    if not extra.get("value"):
        extra["value"] = detect_value(full)
    if not extra.get("voivodeship"):
        extra["voivodeship"] = detect_voivodeship(full)
    feats = similarity.features_from_text(full, extra)

    sims = similarity.find_similar(full, feats, metrics_fn=pipeline.project_metrics)
    group = [s for s in sims if s["score"] >= cfg.get("min_similarity", 0.15)][: cfg.get("top_k", 6)]
    completed = [s for s in group if (s.get("metrics") or {}).get("completed") or (s["status"] or "").lower().startswith("zako")]

    # ---------------- obliczenia
    calc = {}
    calc["cost_dev_pct"] = _stats([s["metrics"].get("cost_dev_pct") for s in completed])
    calc["delay_days"] = _stats([s["metrics"].get("delay_days") for s in completed])
    calc["planned_duration_days"] = _stats([s["metrics"].get("planned_duration_days") for s in group])
    calc["cost_per_km"] = _stats([s["metrics"].get("cost_per_km") for s in group])
    calc["contract_value"] = _stats([s["metrics"].get("contract_value") for s in group])
    calc["value_for_comparison"] = _stats([s["metrics"].get("value_for_comparison") for s in group])
    calc["n_offers"] = _stats([s["metrics"].get("n_offers") for s in group])
    for k, st in calc.items():
        st["projects"] = [s["record_id"] for s in group if s["metrics"].get(k) is not None]

    forecast = {"value_input": feats.get("value"), "length_km": feats.get("length_km")}
    cd = calc["cost_dev_pct"]
    if feats.get("value") and cd["n"]:
        forecast["cost_range"] = [feats["value"] * (1 + cd["p25"]), feats["value"] * (1 + cd["median"]), feats["value"] * (1 + cd["p75"])]
        forecast["cost_method"] = f"wartość z opisu × (1 + odchylenie kosztu podobnych zakończonych: p25 / mediana / p75), n={cd['n']}"
    cpk = calc["cost_per_km"]
    if feats.get("length_km") and cpk["n"]:
        forecast["cost_by_length"] = [feats["length_km"] * cpk["p25"], feats["length_km"] * cpk["median"], feats["length_km"] * cpk["p75"]]
        forecast["cost_by_length_method"] = f"długość {feats['length_km']:.2f} km × koszt na km w grupie (p25 / mediana / p75), n={cpk['n']}"
    dd, pdur = calc["delay_days"], calc["planned_duration_days"]
    if pdur["n"]:
        base = pdur["median"]
        if dd["n"]:
            forecast["duration_range_days"] = [base + max(0, dd["p25"]), base + max(0, dd["median"]), base + max(0, dd["p75"])]
            forecast["duration_method"] = f"mediana terminu umownego ({base:.0f} dni, n={pdur['n']}) + opóźnienia podobnych (p25/mediana/p75, n={dd['n']})"
        else:
            forecast["duration_range_days"] = [pdur["p25"], base, pdur["p75"]]
            forecast["duration_method"] = f"rozkład terminów umownych w grupie (n={pdur['n']}); brak danych o faktycznych opóźnieniach"
    forecast["confidence"] = _confidence_label(max(cd["n"], dd["n"], pdur["n"]))
    forecast["sample_note"] = (f"Grupa porównawcza: {len(group)} projektów (w tym {len(completed)} zakończonych z danymi o realizacji). "
                               "Przedziały to rozrzut obserwacji, nie przedział ufności — przy małej próbie traktować orientacyjnie.")

    # ---------------- prognoza referencyjna (cała baza ważona podobieństwem) i rejestr ryzyk z wyceną
    months = clauses.detect_months(full)
    duration_days = months * 30.4 if months else (pdur["median"] if pdur["n"] else None)
    ref = refclass.rcf(sims, value=feats.get("value"), duration_days=duration_days, stage="kosztorys")
    register = refclass.risk_register(sims, value=feats.get("value"), duration_days=duration_days)
    bases = refclass.change_bases([s["project_id"] for s in sims])
    audit = clauses.audit(audit_pages, doc_types=[d["doc_type"] for d in doc_rows], register=register, bases=bases,
                          months=months, formula=feats.get("formula"))
    from datetime import date as _date
    dl, st = detect_schedule(full)
    for key, cur in (("deadline", dl), ("tender_start", st)):
        v = (extra or {}).get(key)
        if v:
            try:
                cur = _date.fromisoformat(str(v)[:10])
            except ValueError:
                pass
        if key == "deadline":
            dl = cur
        else:
            st = cur
    funding = refclass.funding_deadline(sims, duration_days, tender_start=st, deadline=dl) if duration_days else None
    forecast_ref = {"rcf": ref, "months_input": months, "duration_days_input": duration_days, "funding": funding,
                    "deadline_detected": dl.isoformat() if dl else None, "tender_start_detected": st.isoformat() if st else None}

    # ---------------- ryzyka w grupie porównawczej
    risk_names = knowledge.risk_names()
    catalog = {r["code"]: r for r in knowledge.risks(include_proposed=True)}
    by_risk = {}
    ids = [s["project_id"] for s in group]
    if ids:
        qs = ",".join("?" for _ in ids)
        evs = db.q(f"SELECT e.*, p.record_id, p.name pname, s.url src_url, s.title src_title FROM events e JOIN projects p ON p.id=e.project_id "
                   f"LEFT JOIN sources s ON s.id=e.source_id WHERE e.project_id IN ({qs}) AND e.status!='rejected'", ids)
        for e in evs:
            if not e["risk_code"]:
                continue
            r = by_risk.setdefault(e["risk_code"], {"code": e["risk_code"], "name": risk_names.get(e["risk_code"], e["risk_code"]),
                                                    "projects": set(), "approved": 0, "proposed": 0, "examples": [], "cost": 0.0, "delay": 0})
            r["projects"].add(e["record_id"])
            r["approved" if e["status"] in ("approved", "edited") else "proposed"] += 1
            r["cost"] += e["cost_impact"] or 0
            r["delay"] += e["delay_days"] or 0
            if len(r["examples"]) < 4:
                src_url = e["src_url"]
                if not src_url and e["notice_id"]:
                    nrow = db.q1("SELECT url FROM notices WHERE id=?", (e["notice_id"],))
                    src_url = nrow["url"] if nrow else None
                r["examples"].append({"event_id": e["id"], "project": e["record_id"], "title": e["title"], "quote": (e["quote"] or "")[:300],
                                      "status": e["status"], "source_url": src_url, "page": e["page"]})
    risk_freq = []
    for code, r in by_risk.items():
        r["n_projects"] = len(r["projects"])
        r["share"] = r["n_projects"] / max(1, len(group))
        r["projects"] = sorted(r["projects"])
        risk_freq.append(r)
    risk_freq.sort(key=lambda r: (-r["share"], -r["approved"]))

    # ---------------- sygnały w opisie nowej inwestycji
    signals = []
    for ev in rules.scan_pages([{"page": 1, "text": full}], {"doc_type": "Opis inwestycji"}):
        if not ev.get("negated"):
            signals.append({"risk_code": ev["risk_code"], "name": risk_names.get(ev["risk_code"]), "quote": ev["quote"][:300]})
    checklist = rules.checklist_coverage(full)

    # ---------------- czerwone flagi
    flags = []
    for r in risk_freq:
        if r["share"] >= 0.34 or r["approved"] >= 2:
            flags.append({"risk_code": r["code"], "name": r["name"], "level": "wysoki" if r["share"] >= 0.5 else "podwyższony",
                          "why": f"wystąpiło w {r['n_projects']} z {len(group)} podobnych projektów ({r['approved']} zatwierdzonych, {r['proposed']} do weryfikacji)",
                          "basis": "grupa porównawcza"})
    for code in sorted({s["risk_code"] for s in signals if s["risk_code"]}):
        if not any(f["risk_code"] == code for f in flags):
            flags.append({"risk_code": code, "name": risk_names.get(code), "level": "do sprawdzenia",
                          "why": "sygnał w opisie/dokumentach planowanej inwestycji", "basis": "opis inwestycji"})
    if feats.get("formula") == "zaprojektuj i wybuduj":
        for code in ("R04", "R09"):
            if not any(f["risk_code"] == code for f in flags):
                flags.append({"risk_code": code, "name": risk_names.get(code), "level": "do sprawdzenia",
                              "why": "formuła „zaprojektuj i wybuduj” przenosi decyzje i projekt na wykonawcę — kluczowe są PFU i podział odpowiedzialności",
                              "basis": "reguła ekspercka"})
    cv = calc["value_for_comparison"]
    if feats.get("value") and cv["n"] >= 2 and feats.get("length_km") and calc["cost_per_km"]["n"] >= 2:
        implied = feats["value"] / feats["length_km"]
        if implied < calc["cost_per_km"]["p25"]:
            flags.append({"risk_code": "R13", "name": risk_names.get("R13"), "level": "podwyższony",
                          "why": f"budżet na km ({implied:,.0f} zł) poniżej 1. kwartyla podobnych ({calc['cost_per_km']['p25']:,.0f} zł) — ryzyko ofert powyżej budżetu".replace(",", " "),
                          "basis": "obliczenia"})
    one_offer = [s for s in group if s["metrics"].get("n_offers") == 1]
    if len(one_offer) >= 2:
        flags.append({"risk_code": "R11", "name": risk_names.get("R11"), "level": "podwyższony",
                      "why": f"w {len(one_offer)} podobnych postępowaniach wpłynęła tylko jedna oferta", "basis": "obliczenia"})

    # ---------------- rekomendacje i zagadnienia
    recs = []
    for f in flags:
        c = catalog.get(f["risk_code"]) or {}
        recs.append({"risk_code": f["risk_code"], "name": f["name"], "mitigations": c.get("mitigations", []),
                     "clauses": c.get("clauses", []), "checks": c.get("checks", [])})
    for a in audit["rows"]:
        if a["legal_gap"]:
            flags.insert(0, {"risk_code": (a["risks"] or [None])[0], "name": a["name"], "level": "wysoki",
                             "why": f"{a['ref']}: {a['required_text']} — w projekcie umowy: {a['status']}" + (f" ({a['note']})" if a.get("note") else ""),
                             "basis": "audyt klauzul"})
    rres = ref.get("result") or {}
    c80 = (rres.get("contract") or {}).get("p80")
    if c80 is not None and c80 > 0.1:
        flags.append({"risk_code": "R07", "name": risk_names.get("R07"), "level": "podwyższony",
                      "why": (f"w klasie referencyjnej {ref['cost']['share_over_raw'][0]} z {ref['cost']['share_over_raw'][1]} umów rozliczono powyżej wartości umowy; "
                              f"po podpisaniu umowy utrzymaj rezerwę P80 ≈ {c80 * 100:+.0f}% ceny umowy"
                              + (f" (≈ {rres['contract']['reserve_p80_pln']:,.0f} zł przy typowej cenie ofert)" if rres["contract"].get("reserve_p80_pln") else "")
                              + " — oszczędności przetargowych nie zwalniaj w całości").replace(",", " "),
                      "basis": "prognoza referencyjna"})
    if funding and funding.get("deadline") and funding["p_miss"] >= 0.2:
        flags.insert(0, {"risk_code": "R13", "name": "Ryzyko utraty dofinansowania (termin zakończenia)", "level": "wysoki" if funding["p_miss"] >= 0.5 else "podwyższony",
                         "why": (f"w {funding['k_miss'][0]} z {funding['k_miss'][1]} podobnych przebiegów inwestycja nie zdążyłaby przed {funding['deadline']} "
                                 f"(ważone prawdopodobieństwo {funding['p_miss']:.0%}); realny termin zakończenia P80: {funding['finish']['p80']}"),
                         "basis": "prognoza referencyjna"})
    issues = [{"id": c["id"], "text": c["text"], "ref": c["ref"],
               "note": "Brak informacji w opisie — uzupełnić przed uruchomieniem projektu."} for c in checklist if not c["covered"]]

    result = {
        "title": title or "Analiza nowej inwestycji",
        "created_at": now_iso(),
        "input": {"text": text, "documents": doc_rows, "features": feats},
        "dane_zrodlowe": {
            "similar": group,
            "all_ranked": [{k: s[k] for k in ("project_id", "record_id", "name", "score")} for s in sims[:15]],
            "risk_examples": risk_freq,
        },
        "obliczenia": {"stats": calc, "forecast": forecast, "reference": forecast_ref, "register": register, "change_bases": bases},
        "wnioski": {"flags": flags, "recommendations": recs, "clause_audit": audit, "issues_to_check": issues, "signals_in_input": signals,
                    "checklist": checklist, "method_note": "Wnioski generowane regułami katalogu eksperckiego na podstawie danych i obliczeń powyżej. Wymagają oceny eksperta."},
        "llm": llm.info(),
    }
    if llm.enabled():
        result["wnioski"]["narrative_llm"] = llm.narrative({"features": feats, "forecast": forecast, "flags": flags, "stats": calc})
    if analysis_id:
        db.update("analyses", analysis_id, {"result_json": result, "title": result["title"], "input_text": text, "status": "gotowa"})
    return result
