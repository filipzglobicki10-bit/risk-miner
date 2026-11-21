"""Prognoza referencyjna (Reference Class Forecasting) i rejestr ryzyk z wyceną.

Zamiast pytać „ile może kosztować ten projekt?”, pytamy „jak naprawdę skończyły się podobne umowy?”.
Metoda (Flyvbjerg / HM Treasury „optimism bias uplift”), dopasowana do małej próby:

1. Klasa referencyjna = wszystkie umowy z bazy, dla których BZP podaje wynik realizacji
   (ogłoszenie o wykonaniu umowy: kwota wypłacona, faktyczny termin). Rekordy bez wyniku nie są liczone.
2. Każdy projekt waży tyle, ile jest podobny do planowanej inwestycji (waga = podobieństwo²),
   ale żaden nie jest odrzucany — mała próba nie znosi dalszego dzielenia. Raportujemy efektywną liczebność n_eff.
3. Z ważonego rozkładu odchyleń liczymy P50 / P80 / P90: „rezerwa P80” to narzut, przy którym w 80%
   podobnych przypadków budżet (termin) by wystarczył.
4. Niepewność samego P80 pokazujemy przedziałem bootstrap (500 losowań, stałe ziarno — wynik powtarzalny).

Rejestr ryzyk: prawdopodobieństwo = ważony udział podobnych projektów, w których ryzyko się zmaterializowało
(zdarzenie przyczynowe z formularza BZP / dokumentu / eksperta), skutek = mediana kosztu zmian w % wartości umowy
i mediana opóźnienia. Wartość oczekiwana (EMV) = prawdopodobieństwo × skutek — porządkuje ryzyka według tego,
ile realnie kosztują, a nie jak często się o nich pisze.
"""
import random
from collections import Counter
from datetime import date, timedelta

from . import bzp, db, knowledge


def wquantile(pairs, q):
    """Kwantyl ważony (interpolacja po skumulowanej wadze, środek masy każdej obserwacji)."""
    pts = sorted((v, w) for v, w in pairs if v is not None and w > 0)
    if not pts:
        return None
    if len(pts) == 1:
        return pts[0][0]
    tot = sum(w for _, w in pts)
    cum, xs, ys = 0.0, [], []
    for v, w in pts:
        xs.append((cum + w / 2) / tot)
        ys.append(v)
        cum += w
    if q <= xs[0]:
        return ys[0]
    if q >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if q <= xs[i]:
            t = (q - xs[i - 1]) / ((xs[i] - xs[i - 1]) or 1)
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def n_eff(weights):
    s, s2 = sum(weights), sum(w * w for w in weights)
    return (s * s / s2) if s2 else 0.0


def _bootstrap(pairs, q, iters=500, seed=2026):
    if len(pairs) < 4:
        return None
    rnd = random.Random(seed)
    out = []
    for _ in range(iters):
        sample = [pairs[rnd.randrange(len(pairs))] for _ in pairs]
        v = wquantile(sample, q)
        if v is not None:
            out.append(v)
    out.sort()
    return [out[int(0.1 * (len(out) - 1))], out[int(0.9 * (len(out) - 1))]] if out else None


def _dist(rows, key, label):
    pairs = [(r[key], r["weight"]) for r in rows if r.get(key) is not None]
    if not pairs:
        return {"n": 0, "label": label}
    w = [p[1] for p in pairs]
    tot = sum(w)
    d = {
        "label": label, "n": len(pairs), "n_eff": round(n_eff(w), 1),
        "p50": wquantile(pairs, 0.5), "p80": wquantile(pairs, 0.8), "p90": wquantile(pairs, 0.9),
        "p80_ci": _bootstrap(pairs, 0.8),
        "share_over": sum(wi for v, wi in pairs if v > 0.005) / tot,
        "share_over_raw": [sum(1 for v, _ in pairs if v > 0.005), len(pairs)],
        "points": sorted(({"record_id": r["record_id"], "value": r[key], "weight": round(r["weight"], 3), "score": r["score"],
                           "verified": r.get("verified", True)}
                          for r in rows if r.get(key) is not None), key=lambda x: x["value"]),
    }
    return d


def reference_class(sims):
    """sims: wynik similarity.find_similar (z metrykami). Zwraca umowy z wynikiem realizacji i wagami."""
    rows = []
    for s in sims:
        m = s.get("metrics") or {}
        cost = m.get("cost_dev_pct") if m.get("final_paid") else None
        tr = None
        if m.get("actual_end_date") and m.get("planned_duration_days") and m.get("delay_days") is not None:
            tr = m["delay_days"] / m["planned_duration_days"]
        if cost is None and tr is None:
            continue
        sc = max(0.05, float(s.get("score") or 0))
        verified = bool(db.q1("SELECT pr.id FROM procurements pr JOIN links l ON l.id=pr.link_id WHERE pr.project_id=? "
                              "AND l.status IN ('auto','approved')", (s["project_id"],)))
        pve = m.get("price_vs_estimate")
        est_suspect = pve is not None and abs(pve) < 0.001
        total = None
        if m.get("final_paid") and m.get("estimated_value_net") and not est_suspect and not m.get("scope_part"):
            total = m["final_paid"] / (m["estimated_value_net"] * 1.23) - 1
        elif m.get("final_paid") and m.get("estimated_value_net") and not est_suspect and m.get("price_vs_estimate") is not None and cost is not None:
            total = (1 + m["price_vs_estimate"]) * (1 + cost) - 1   # część postępowania: szacunek części × wynik części
        tender_days = None
        pr = db.q1("SELECT publication_date FROM procurements WHERE project_id=? AND publication_date IS NOT NULL ORDER BY publication_date LIMIT 1",
                   (s["project_id"],))
        if pr and m.get("signed_date"):
            try:
                tender_days = (date.fromisoformat(m["signed_date"][:10]) - date.fromisoformat(pr["publication_date"][:10])).days
                tender_days = tender_days if 0 < tender_days < 730 else None
            except ValueError:
                tender_days = None
        rows.append({"project_id": s["project_id"], "record_id": s["record_id"], "name": s["name"], "score": sc,
                     "total_dev": total, "est_suspect": est_suspect, "tender_days": tender_days,
                     # dopasowanie niezweryfikowane (np. numer z rekordu nie istnieje w BZP) waży 4× mniej
                     "weight": sc * sc * (1.0 if verified else 0.25), "verified": verified, "cost_dev": cost, "time_dev": tr, "delay_days": m.get("delay_days"),
                     "price_vs_estimate": None if est_suspect else pve, "contract_value": m.get("contract_value"),
                     "planned_duration_days": m.get("planned_duration_days")})
    return rows


def rcf(sims, value=None, duration_days=None, stage="kosztorys"):
    """Prognoza P50/P80/P90 kosztu i czasu dla planowanej inwestycji na tle klasy referencyjnej.

    stage = „kosztorys” — wartość z opisu to szacunek inwestora (przed przetargiem): narzut łączy ryzyko ceny ofert
            (oferta vs wartość szacunkowa) i ryzyko realizacji (rozliczenie vs umowa);
    stage = „umowa”     — wartość to cena z umowy: liczy się tylko ryzyko realizacji.
    """
    rows = reference_class(sims)
    cost = _dist(rows, "cost_dev", "rozliczenie vs wartość umowy")
    time = _dist(rows, "time_dev", "faktyczny vs umowny czas realizacji")
    tender = _dist(rows, "price_vs_estimate", "cena umowy (brutto) vs wartość szacunkowa (netto + 23% VAT)")
    total = _dist(rows, "total_dev", "rozliczenie vs wartość szacunkowa (netto + 23% VAT)")
    suspect = [r["record_id"] for r in rows if r.get("est_suspect")]
    out = {"n_class": len(rows), "cost": cost, "time": time, "tender": tender, "total": total, "stage": stage,
           "estimate_suspect": suspect,
           "method": ("Klasa referencyjna: umowy z bazy z wynikiem realizacji w BZP (ogłoszenie o wykonaniu umowy). "
                      "Waga projektu = podobieństwo² do planowanej inwestycji (dopasowania do weryfikacji ×0,25); n_eff = efektywna liczebność próby. "
                      "P80 = narzut, przy którym budżet/termin wystarczyłby w 80% ważonych przypadków; przedział P80 z bootstrapu (500 losowań). "
                      "Wartość szacunkowa z ogłoszenia o wyniku (pole 4.3, netto) ×1,23." +
                      (f" Pominięto szacunek równy co do grosza cenie umowy netto (pole wypełnione wartością umowy): {', '.join(suspect)}." if suspect else ""))}
    res = {}
    # etap 1 — dziś znamy tylko szacunek inwestora: ile ostatecznie zapłacimy względem szacunku?
    est_basis = total if total.get("n", 0) >= 5 else cost
    res["estimate_basis"] = "rozliczenie vs wartość szacunkowa" if est_basis is total else "rozliczenie vs wartość umowy (za mało danych o szacunkach)"
    if value and est_basis.get("n"):
        for q in ("p50", "p80", "p90"):
            res[q] = {"uplift": est_basis[q], "budget": value * (1 + max(0.0, est_basis[q])), "budget_raw": value * (1 + est_basis[q])}
        res["reserve_p80"] = max(0.0, est_basis["p80"]) * value
    # etap 2 — po podpisaniu umowy: rezerwa liczona od ceny umowy
    if cost.get("n"):
        res["contract"] = {q: cost[q] for q in ("p50", "p80", "p90")}
        if value and tender.get("n"):
            exp_price = value * (1 + tender["p50"])
            res["contract"]["expected_price"] = exp_price
            res["contract"]["reserve_p80_pln"] = max(0.0, cost["p80"]) * exp_price
    if tender.get("n"):
        res["tender_note"] = (f"Ceny umów względem wartości szacunkowej: mediana {_pp(tender['p50'])}, P80 {_pp(tender['p80'])} (n={tender['n']}). "
                              f"Oszczędność przetargowa nie jest jednak „wolnymi środkami”: po podpisaniu umowy rozliczenie rośnie o {_pp(cost['p50']) if cost.get('n') else '—'} "
                              f"(mediana), a w 20% umów o ponad {_pp(cost['p80']) if cost.get('n') else '—'}.")
    if duration_days and time.get("n"):
        for q in ("p50", "p80", "p90"):
            res.setdefault("time_" + q, {"uplift": time[q], "days": duration_days * (1 + max(0.0, time[q]))})
        res["time_reserve_p80_days"] = max(0.0, time["p80"]) * duration_days
    out["result"] = res
    ne = max(cost.get("n_eff", 0), time.get("n_eff", 0))
    out["confidence"] = ("niska — mała efektywna próba" if ne < 6 else "umiarkowana — przedziały szerokie, traktować jako rząd wielkości" if ne < 20 else "dobra")
    return out


def funding_deadline(sims, planned_days, tender_start=None, deadline=None):
    """Czy inwestycja zdąży przed terminem z umowy o dofinansowanie?

    Dla każdej umowy z klasy referencyjnej składamy jej własną ścieżkę: czas od ogłoszenia przetargu do podpisania
    umowy (BZP: ogłoszenie o zamówieniu → data zawarcia) + planowany czas realizacji × (1 + jej faktyczne wydłużenie).
    Łączenie po projekcie (a nie osobnych kwantyli) zachowuje zależność między etapami. Wynik: daty zakończenia
    P50/P80/P90 i ważony odsetek ścieżek, które przekraczają termin."""
    rows = [r for r in reference_class(sims) if r.get("time_dev") is not None]
    if not rows or not planned_days:
        return None
    start = tender_start or date.today()
    tender = _dist(rows, "tender_days", "od ogłoszenia przetargu do podpisania umowy (dni)")
    med_t = tender.get("p50") or 45
    paths = []
    for r in rows:
        t = r["tender_days"] if r.get("tender_days") is not None else med_t
        paths.append({"record_id": r["record_id"], "weight": r["weight"], "score": r["score"], "verified": r.get("verified", True),
                      "days": t + planned_days * (1 + max(-0.5, r["time_dev"])), "tender_days": t})
    pairs = [(x["days"], x["weight"]) for x in paths]
    q = {k: wquantile(pairs, v) for k, v in (("p50", 0.5), ("p80", 0.8), ("p90", 0.9))}
    out = {"start": start.isoformat(), "planned_days": planned_days, "tender": {k: tender.get(k) for k in ("n", "p50", "p80", "p90")},
           "finish": {k: (start + timedelta(days=round(v))).isoformat() for k, v in q.items()}, "days": q,
           "naive_finish": (start + timedelta(days=round(med_t + planned_days))).isoformat(),
           "n": len(paths), "n_eff": round(n_eff([x["weight"] for x in paths]), 1),
           "paths": sorted(({"record_id": x["record_id"], "days": round(x["days"]), "weight": round(x["weight"], 3), "score": x["score"],
                             "verified": x["verified"], "tender_days": x["tender_days"]} for x in paths), key=lambda x: x["days"]),
           "method": ("Ścieżka każdej podobnej umowy: jej czas przetargu (ogłoszenie o zamówieniu → zawarcie umowy, BZP) + planowany "
                      "czas realizacji × (1 + jej faktyczne wydłużenie). Uwaga: przetargi unieważnione i powtórzone nie są tu liczone — "
                      "realne ryzyko jest raczej wyższe.")}
    if deadline:
        avail = (deadline - start).days
        tot = sum(w for _, w in pairs) or 1
        p_miss = sum(w for d, w in pairs if d > avail) / tot
        latest = deadline - timedelta(days=round(q["p80"]))
        out.update({"deadline": deadline.isoformat(), "available_days": avail, "p_miss": p_miss,
                    "k_miss": [sum(1 for d, _ in pairs if d > avail), len(pairs)],
                    "latest_start_p80": latest.isoformat(), "start_too_late": latest < start,
                    "max_planned_days_p80": None})
        # jaki planowany czas realizacji daje 80% szans? (szukanie po siatce co 15 dni)
        for pd in range(int(planned_days), 30, -15):
            pp_ = [((r["tender_days"] if r.get("tender_days") is not None else med_t) + pd * (1 + max(-0.5, r["time_dev"])), r["weight"]) for r in rows]
            if wquantile(pp_, 0.8) <= avail:
                out["max_planned_days_p80"] = pd
                break
    return out


CAUSAL_METHODS = ("formularz BZP", "rule", "llm", "manual")


def risk_register(sims, value=None, duration_days=None):
    """Ryzyka, które zmaterializowały się w podobnych projektach — z prawdopodobieństwem, skutkiem i EMV."""
    names = knowledge.risk_names()
    sc = {s["project_id"]: max(0.05, float(s.get("score") or 0)) for s in sims}
    meta = {s["project_id"]: s for s in sims}
    if not sc:
        return {"rows": [], "n": 0}
    ids = list(sc)
    qs = ",".join("?" for _ in ids)
    evs = db.q(f"SELECT e.*, p.record_id FROM events e JOIN projects p ON p.id=e.project_id WHERE e.project_id IN ({qs}) "
               f"AND e.status!='rejected' AND e.risk_code IS NOT NULL AND e.method IN ({','.join('?' for _ in CAUSAL_METHODS)})",
               ids + list(CAUSAL_METHODS))
    # tylko projekty, dla których mamy jakiekolwiek ogłoszenia — brak danych ≠ brak ryzyka
    covered = {r["project_id"] for r in db.q(f"SELECT DISTINCT project_id FROM notices WHERE project_id IN ({qs})", ids)}
    covered |= {r["project_id"] for r in db.q(f"SELECT DISTINCT project_id FROM documents WHERE project_id IN ({qs})", ids)}
    wtot = sum(sc[i] ** 2 for i in covered) or 1
    by = {}
    for e in evs:
        if e["project_id"] not in covered:
            continue
        r = by.setdefault(e["risk_code"], {"code": e["risk_code"], "name": names.get(e["risk_code"], e["risk_code"]), "hits": {},
                                          "costs_pct": [], "delays": [], "bases": Counter(), "examples": []})
        r["hits"].setdefault(e["project_id"], e["record_id"])
        cv = (meta.get(e["project_id"], {}).get("metrics") or {}).get("contract_value")
        if e["cost_impact"] and cv:
            r["costs_pct"].append(e["cost_impact"] / cv)
        if e["delay_days"]:
            r["delays"].append(e["delay_days"])
        t = e["title"] or ""
        for key in bzp.LEGAL_BASIS_MEANING:
            if key in t:
                r["bases"][key] += 1
        if len(r["examples"]) < 3:
            r["examples"].append({"event_id": e["id"], "project": e["record_id"], "title": t[:160], "cause": (e["cause"] or e["quote"] or "")[:240]})
    rows = []
    for code, r in by.items():
        p = sum(sc[i] ** 2 for i in r["hits"]) / wtot
        c_med = _median(r["costs_pct"])
        d_med = _median(r["delays"])
        row = {"code": code, "name": r["name"], "probability": p, "k": len(r["hits"]), "n": len(covered),
               "projects": sorted(r["hits"].values()), "impact_cost_pct": c_med, "impact_delay_days": d_med,
               "n_cost_obs": len(r["costs_pct"]), "n_delay_obs": len(r["delays"]),
               "emv_pct": p * c_med if c_med is not None else None,
               "emv_pln": p * c_med * value if (c_med is not None and value) else None,
               "emv_days": p * d_med if d_med is not None else None,
               "bases": [{"basis": k, "meaning": bzp.LEGAL_BASIS_MEANING.get(k), "n": v} for k, v in r["bases"].most_common()],
               "examples": r["examples"]}
        rows.append(row)
    rows.sort(key=lambda r: (-(r["emv_pct"] or 0), -r["probability"]))
    return {"rows": rows, "n": len(covered),
            "method": ("Prawdopodobieństwo = ważony (podobieństwo²) udział projektów z danymi, w których ryzyko się zmaterializowało "
                       "(zdarzenie przyczynowe: zmiana umowy w BZP, dokument, wpis eksperta). Skutek = mediana kosztu zmian w % "
                       "wartości umowy i mediana wydłużenia. EMV = prawdopodobieństwo × skutek.")}


def change_bases(project_ids):
    """Jak zmieniano umowy w klasie referencyjnej — udział zmian przewidzianych w umowie (art. 455 ust. 1 pkt 1)."""
    if not project_ids:
        return {"n": 0, "rows": []}
    qs = ",".join("?" for _ in project_ids)
    c = Counter()
    for r in db.q(f"SELECT legal_basis FROM contract_changes WHERE project_id IN ({qs}) AND status!='rejected'", list(project_ids)):
        key, _ = bzp.basis_meaning(r["legal_basis"])
        c[key or "inna / nieokreślona"] += 1
    n = sum(c.values())
    rows = [{"basis": k, "meaning": bzp.LEGAL_BASIS_MEANING.get(k, "—"), "n": v, "share": v / n} for k, v in c.most_common()]
    foreseen = c.get("art. 455 ust. 1 pkt 1", 0)
    return {"n": n, "rows": rows, "foreseen_share": (foreseen / n) if n else None,
            "note": ("Zmiana „przewidziana” (art. 455 ust. 1 pkt 1 Pzp) jest możliwa tylko, gdy umowa zawiera jasną klauzulę. "
                     "Pozostałe podstawy (roboty dodatkowe, okoliczności nieprzewidziane, zmiana o niewielkiej wartości) mają limity "
                     "wartości i większe ryzyko zarzutów przy kontroli — duży ich udział oznacza, że umowy nie przewidziały, co się stanie.")}


def _pp(v):
    return ("+" if v >= 0 else "−") + f"{abs(v) * 100:.1f}".replace(".", ",") + "%"


def _median(vals):
    v = sorted(x for x in vals if x is not None)
    if not v:
        return None
    k = len(v) // 2
    return v[k] if len(v) % 2 else (v[k - 1] + v[k]) / 2
