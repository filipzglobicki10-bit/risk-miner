"""Klient API BZP (platforma e-Zamówienia, endpoint /mo-board/api/v1/notice) oraz parser treści ogłoszeń.

- działa z oficjalnym API i z kopią organizatora (bzp.cytr.us — ten sam interfejs),
- limit zapytań (requests_per_minute) — od 6.10.2026 oficjalne API: 30/min z jednego IP,
- cache odpowiedzi na dysku (powtarzalność, ponowne uruchomienie bez ręcznego wpisywania),
- tolerancyjne mapowanie pól (nazwy pól w JSON mogą się różnić między wersjami API),
- import lokalnej kopii ogłoszeń (pliki JSON w formacie API) — tryb offline.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config
from .util import fold, normalize_bzp, normalize_nip, now_iso, parse_amount, parse_date, sha256, strip_html, AMOUNT_ANY_RE, DATE_RE

_rate_lock = threading.Lock()
_last_calls = []


class BZPError(Exception):
    pass


def _throttle(rpm):
    if not rpm:
        return
    with _rate_lock:
        now = time.time()
        while _last_calls and now - _last_calls[0] > 60:
            _last_calls.pop(0)
        if len(_last_calls) >= rpm:
            time.sleep(max(0, 60 - (now - _last_calls[0])) + 0.1)
        _last_calls.append(time.time())


def _cache_path(url):
    return os.path.join(config.get()["data_dir"], "cache", "bzp", sha256(url)[:32] + ".json")


def _local_store():
    """Lokalna kopia ogłoszeń (import paczki organizatora) — lista ogłoszeń."""
    p = os.path.join(config.get()["data_dir"], "bzp_local.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def get_json(params, log=None):
    """GET z listą adresów zapasowych. Zwraca (dane, url, fetched_at)."""
    cfg = config.get()["bzp"]
    urls = [cfg["base_url"]] + list(cfg.get("fallback_urls") or [])
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    last_err = None
    for base in urls:
        url = f"{base}?{qs}"
        cp = _cache_path(url)
        if cfg.get("cache") and os.path.exists(cp):
            with open(cp, encoding="utf-8") as f:
                c = json.load(f)
            return c["data"], url, c["fetched_at"]
        rpm = cfg.get("requests_per_minute") or (25 if "ezamowienia.gov.pl" in base else 0)
        _throttle(rpm)
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "RiskMiner/1.0 (HackNation 2026)"})
            with urllib.request.urlopen(req, timeout=cfg.get("timeout_s", 30)) as r:
                raw = r.read().decode("utf-8")
            data = json.loads(raw) if raw.strip() else []
            fetched = now_iso()
            if cfg.get("cache"):
                with open(cp, "w", encoding="utf-8") as f:
                    json.dump({"url": url, "fetched_at": fetched, "data": data}, f, ensure_ascii=False)
            if log:
                log(f"GET {url} -> {len(data) if isinstance(data, list) else 'obiekt'}")
            return data, url, fetched
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} dla {url}"
            if e.code == 400:  # zły parametr — nie próbujemy kolejnego hosta z tym samym zapytaniem
                break
            if e.code in (403, 429):
                time.sleep(2)
        except Exception as e:  # sieć, DNS, proxy
            last_err = f"{type(e).__name__}: {e} ({url})"
        if log:
            log("Błąd: " + str(last_err))
    raise BZPError(last_err or "nieznany błąd")


def items_of(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("items", "notices", "data", "results", "value"):
            if isinstance(data.get(k), list):
                return data[k]
        return [data]
    return []


def search(notice_type, log=None, **filters):
    """Pobiera ogłoszenia danego typu (z paginacją SearchAfter / przesuwaniem daty publikacji)."""
    local = _local_store()
    if local is not None:
        return _search_local(local, notice_type, **filters), "lokalna kopia BZP (data/bzp_local.json)", now_iso()
    cfg = config.get()["bzp"]
    params = {"NoticeType": notice_type, "PageSize": min(500, cfg.get("page_size", 500))}
    for k, v in filters.items():
        if v not in (None, ""):
            params[k] = v
    out, seen, first_url, fetched = [], set(), None, None
    for _ in range(cfg.get("max_pages", 30)):
        data, url, fetched = get_json(params, log=log)
        first_url = first_url or url
        batch = items_of(data)
        new = 0
        for it in batch:
            key = g(it, "objectId", "noticeNumber", "id") or json.dumps(it, sort_keys=True)[:200]
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
            new += 1
        if len(batch) < params["PageSize"] or new == 0:
            break
        last = batch[-1]
        if g(last, "objectId"):
            params["SearchAfter"] = g(last, "objectId")
        elif g(last, "publicationDate"):
            params["PublicationDateFrom"] = g(last, "publicationDate")
        else:
            break
    return out, first_url, fetched


def _search_local(items, notice_type, **f):
    out = []
    items = sorted(items, key=lambda it: g(it, "publicationDate") or "", reverse=True)  # jak w API: najnowsze najpierw
    for it in items:
        if notice_type and g(it, "noticeType") and g(it, "noticeType") != notice_type:
            continue
        if f.get("NoticeNumber") and normalize_bzp(g(it, "noticeNumber"))[0] != normalize_bzp(f["NoticeNumber"])[0]:
            continue
        if f.get("OrganizationName") and fold(f["OrganizationName"]) not in fold(g(it, "organizationName") or ""):
            continue  # jak w API: fragment nazwy, bez względu na wielkość liter
        pub = (g(it, "publicationDate") or "")[:10]
        if f.get("PublicationDateFrom") and pub and pub < f["PublicationDateFrom"][:10]:
            continue
        if f.get("PublicationDateTo") and pub and pub > f["PublicationDateTo"][:10]:
            continue
        out.append(it)
    return out


def import_local(items):
    p = os.path.join(config.get()["data_dir"], "bzp_local.json")
    existing = _local_store() or []
    keys = {g(i, "objectId") or g(i, "noticeNumber") for i in existing}
    n = 0
    for it in items:
        k = g(it, "objectId") or g(it, "noticeNumber")
        if k not in keys:
            existing.append(it)
            keys.add(k)
            n += 1
    with open(p, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False)
    return n, len(existing)


def clear_local():
    p = os.path.join(config.get()["data_dir"], "bzp_local.json")
    if os.path.exists(p):
        os.remove(p)


# ---------------------------------------------------------------- mapowanie pól

def g(obj, *keys):
    """Pobiera pierwszą niepustą wartość spośród kluczy (bez względu na wielkość liter)."""
    if not isinstance(obj, dict):
        return None
    low = {k.lower(): v for k, v in obj.items()}
    for k in keys:
        v = obj.get(k)
        if v in (None, ""):
            v = low.get(k.lower())
        if v not in (None, ""):
            return v
    return None


def normalize_notice(it):
    text = mask_personal(strip_html(g(it, "htmlBody", "html", "body", "content") or ""))
    full, base = normalize_bzp(g(it, "noticeNumber", "bzpNumber", "number"))
    _, base2 = normalize_bzp(g(it, "bzpNumber"))
    contractors = g(it, "contractors", "contractorList") or []
    if isinstance(contractors, dict):
        contractors = [contractors]
    oid = g(it, "objectId", "id")
    tmpl = config.get()["bzp"]["notice_url_template"]
    return {
        "notice_type": g(it, "noticeType", "type"),
        "notice_number": full,
        "bzp_number": base2 or base,
        "object_id": oid,
        "tender_id": g(it, "tenderId", "procedureId", "ocid"),
        "publication_date": (g(it, "publicationDate", "publishedDate") or "")[:19] or None,
        "title": g(it, "orderObject", "title", "subject", "name"),
        "cpv": g(it, "cpvCode", "cpv", "mainCpv"),
        "order_type": g(it, "orderType"),
        "organization_name": g(it, "organizationName", "buyerName", "contractingAuthorityName"),
        "organization_nip": normalize_nip(g(it, "organizationNationalId", "nationalId", "organizationNip", "nip")),
        "organization_id": g(it, "organizationId", "buyerId"),
        "organization_city": g(it, "organizationCity"),
        "organization_province": g(it, "organizationProvince"),
        "procedure_result": g(it, "procedureResult", "result"),
        "contractors": [
            {
                "name": g(c, "contractorName", "name"),
                "nip": normalize_nip(g(c, "contractorNationalId", "nationalId", "nip")),
                "city": g(c, "contractorCity", "city"),
            }
            for c in contractors if isinstance(c, dict)
        ],
        "url": tmpl.format(objectId=oid) if oid else None,
        "text": text,
        "is_below_eu": g(it, "isTenderAmountBelowEU"),
    }


NOTICE_TYPE_LABELS = {
    "ContractNotice": "Ogłoszenie o zamówieniu",
    "TenderResultNotice": "Ogłoszenie o wyniku postępowania",
    "NoticeUpdateNotice": "Ogłoszenie o zmianie ogłoszenia",
    "ContractPerformingNotice": "Ogłoszenie o wykonaniu umowy",
    "AgreementUpdateNotice": "Ogłoszenie o zmianie umowy",
    "ContractModificationNotice": "Ogłoszenie o zmianie umowy",
    "CompetitionNotice": "Ogłoszenie o konkursie",
    "SmallContractNotice": "Ogłoszenie o zamówieniu (art. 2 ust. 1 pkt 1)",
    "AgreementIntentionNotice": "Ogłoszenie o zamiarze zawarcia umowy",
}


# ---------------------------------------------------------------- parser treści ogłoszeń

LABELS = {
    "n_offers": (r"liczba (otrzymanych|zlozonych|zlozonych w terminie) ofert|liczba ofert|otrzymano ofert", "int", "nd"),
    "contract_value": (r"cena lub koszt oferty wykonawcy, ktoremu udzielono zamowienia|cena (wybranej|najkorzystniejszej) oferty|wartosc (zawartej )?umowy( brutto)?|wynagrodzenie (umowne|brutto)", "amount", "brutto"),
    "offer_min": (r"oferta z najnizsza cena|najnizsza cena|cena oferty najtanszej", "amount", "brutto"),
    "offer_max": (r"oferta z najwyzsza cena|najwyzsza cena|cena oferty najdrozszej", "amount", "brutto"),
    "estimated_value_net": (r"wartosc zamowienia( bez vat| netto)?|szacunkowa wartosc", "amount", "netto"),
    "budget_amount": (r"kwot\w* (jaka zamawiajacy zamierza przeznaczyc|przeznaczon\w* na sfinansowanie)", "amount", "brutto"),
    "signed_date": (r"data zawarcia umowy", "date", "nd"),
    "planned_end_date": (r"termin (realizacji|wykonania)( umowy| zamowienia)?|okres realizacji( umowy| zamowienia)?|zakonczenie realizacji", "date_or_duration", "nd"),
    "actual_end_date": (r"data (faktycznego )?(wykonania|zakonczenia|zakonczenia realizacji) umowy|umowa zostala wykonana w dniu|data wykonania", "date", "nd"),
    "final_paid": (r"laczna (wartosc|kwota) (wynagrodzenia )?wyplacon\w*|wartosc wyplaconego wynagrodzenia|kwota wyplacona wykonawcy|wynagrodzenie wyplacone", "amount", "brutto"),
    "performed_properly": (r"czy umowa zostala wykonana nalezycie|umowa zostala wykonana nalezycie", "yesno", "nd"),
    "performed_on_time": (r"czy umowa zostala wykonana w terminie|wykonana w terminie", "yesno", "nd"),
    "contract_changed": (r"czy umowa zostala zmieniona|czy dokonano zmian umowy|umowa zostala zmieniona", "yesno", "nd"),
    "penalties": (r"kar\w* umown\w* (naliczon|nalozon)|wysokosc kar umownych", "amount", "brutto"),
}

YES_RE = re.compile(r"\b(tak|nie)\b")
DURATION_RE = re.compile(r"(\d{1,4})\s*(dni|dzien|miesi\w*|tygodn\w*)")


def _same_len(text):
    f = fold(text)
    return f if len(f) == len(text) else None


def parse_notice_facts(text):
    """Zwraca listę faktów {key, value_num|value_text, unit, vat, quote}."""
    out = []
    if not text:
        return out
    folded = _same_len(text) or fold(text)
    mapped = len(folded) == len(text)
    for key, (label, kind, vat) in LABELS.items():
        for m in re.finditer(label, folded):
            window = folded[m.end(): m.end() + 260]
            val, unit, vtext, end = None, None, None, None
            if kind == "amount":
                am = AMOUNT_ANY_RE.search(window)
                if am and am.start() < 120:
                    val = parse_amount(am.group(1))
                    if val is not None and val < 100:  # numery punktów/sekcji, nie kwoty
                        val = None
                    unit, end = "PLN", am.end()
            elif kind == "int":
                im = re.search(r"\b(\d{1,3})\b", window)
                if im and im.start() < 60:
                    val, unit, end = float(im.group(1)), "szt.", im.end()
            elif kind == "date":
                dm = DATE_RE.search(window)
                if dm and dm.start() < 80:
                    vtext, end = parse_date(dm.group(0)), dm.end()
            elif kind == "date_or_duration":
                dm = DATE_RE.search(window)
                du = DURATION_RE.search(window)
                if dm and dm.start() < 100 and (not du or dm.start() <= du.start()):
                    vtext, end = parse_date(dm.group(0)), dm.end()
                elif du and du.start() < 80:
                    # „przedłużono termin realizacji o 60 dni” to zmiana, nie termin umowny
                    if re.search(r"przedluz|zmian|wydluz|skroc", folded[max(0, m.start() - 40): m.start()] + window[: du.start()]):
                        continue
                    n = int(du.group(1))
                    u = du.group(2)
                    days = n * (30 if u.startswith("miesi") else 7 if u.startswith("tygod") else 1)
                    q = (text if mapped else folded)[m.start(): m.end() + du.end()]
                    out.append({"key": "planned_duration_days", "value_num": float(days),
                                "value_text": f"{n} mies." if u.startswith("miesi") else None, "unit": "dni", "vat": "nd",
                                "quote": re.sub(r"\s+", " ", q).strip()})
                    continue
            elif kind == "yesno":
                ym = YES_RE.search(window)
                if ym and ym.start() < 40:
                    vtext, end = ym.group(1), ym.end()
            if (val is None and vtext is None) or end is None:
                continue
            src = text if mapped else folded
            # cytat: od początku etykiety (z ewentualnym numerem punktu, np. „6.1.)”) do końca wartości
            a = m.start()
            pre = re.search(r"(\d+(?:\.\d+)+\.?\)?\s*|\d+\.\)\s*)$", folded[max(0, a - 14): a])
            if pre:
                a -= len(pre.group(1))
            quote = re.sub(r"\s+", " ", src[a: m.end() + end]).strip()
            out.append({"key": key, "value_num": val, "value_text": vtext, "unit": unit, "vat": vat, "quote": quote[:400]})
    # deduplikacja: ten sam klucz i wartość
    seen, uniq = set(), []
    for f in out:
        k = (f["key"], f.get("value_num"), f.get("value_text"))
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


def legal_bases(text):
    out = []
    for m in re.finditer(r"art\.?\s?455\s?ust\.?\s?(\d)(?:\s?pkt\.?\s?(\d))?", fold(text or "")):
        b = f"art. 455 ust. {m.group(1)}" + (f" pkt {m.group(2)}" if m.group(2) else "")
        if b not in out:
            out.append(b)
    return out


# ======================================================================================
# Parser formularzy BZP (zweryfikowany na 198 prawdziwych ogłoszeniach z kopii organizatora)
# Ogłoszenie = sekwencja pól „N.N.) Etykieta: wartość”, z podziałem na „Część N”.
# ======================================================================================

FIELD_RE = re.compile(r"^\s*(\d+(?:\.\d+)*\.?\)?)\s+([^:\n]{2,220}?):\s*(.*)$")
PART_RE = re.compile(r"^\s*Cz[eę]ść\s+(\d+)\s*$", re.I)
FOOTER_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2}\s+Biuletyn Zamówień Publicznych|Ogłoszenie o .{3,200}\s-\s)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(Numer (?:telefonu|faksu):\s*)[\d +()\-]{6,}", re.I)


def mask_personal(text):
    """Minimalizacja danych: e-maile i telefony osób kontaktowych nie są potrzebne do analizy."""
    if not text:
        return text
    text = EMAIL_RE.sub("[e-mail usunięty]", text)
    return PHONE_RE.sub(r"\1[usunięty]", text)


def parse_form(text):
    """Zwraca listę pól: {num, label, value, part, line} — wartość może ciągnąć się przez kolejne wiersze."""
    fields, part, cur = [], None, None
    for raw in (text or "").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if FOOTER_RE.match(line):
            cur = None  # stopka ogłoszenia nie jest częścią wartości pola
            continue
        pm = PART_RE.match(line)
        if pm:
            part, cur = int(pm.group(1)), None
            continue
        m = FIELD_RE.match(line)
        if m:
            cur = {"num": m.group(1).rstrip(".)").rstrip("."), "label": m.group(2).strip(), "value": m.group(3).strip(),
                   "part": part, "line": line}
            fields.append(cur)
        elif cur is not None and len(cur["value"]) < 4000:
            cur["value"] = (cur["value"] + " " + line).strip()
            if len(cur["line"]) < 600:
                cur["line"] = (cur["line"] + " " + line)[:600]
    return fields


def _lab(f, pattern):
    return re.search(pattern, fold(f["label"])) is not None


def _amount(v):
    m = AMOUNT_ANY_RE.search(v or "")
    return parse_amount(m.group(1)) if m else None


def _yes(v):
    fv = fold(v or "")
    return "tak" if fv.startswith("tak") else "nie" if fv.startswith("nie") else None


def _duration(v):
    """„5 miesiące” / „do 2026-04-27” / „120 dni” -> (days, months_text, date)."""
    if re.match(r"^\s*(do\s+(dnia\s+)?)?(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})", v or "", re.I):
        return None, None, parse_date(v)
    m = re.search(r"(\d{1,4})\s*(dni|dzien|dzień|miesi\w*|mies\.?|tygodn\w*|lat|rok\w*)", fold(v or ""))
    if not m:
        d = parse_date(v)
        return (None, None, d) if d else (None, None, None)
    n, u = int(m.group(1)), m.group(2)
    if u.startswith("mies"):
        return n * 30, f"{n} mies.", None
    if u.startswith("tygod"):
        return n * 7, None, None
    if u.startswith(("lat", "rok")):
        return n * 365, f"{n * 12} mies.", None
    return n, None, None


def _fact(key, f, value_num=None, value_text=None, unit=None, vat="nd"):
    return {"key": key, "value_num": value_num, "value_text": value_text, "unit": unit, "vat": vat,
            "quote": f["line"][:400], "part": f.get("part")}


def extract_structured(notice_type, text):
    """Strukturalne dane z ogłoszenia BZP: fakty (z częścią), zmiany umowy, przyczyny unieważnienia, zapisy o zmianach."""
    fields = parse_form(text)
    facts, changes, info = [], [], {"parts": sorted({f["part"] for f in fields if f["part"]}), "provisions": None,
                                    "result_ref": None, "notice_ref": None, "cancel": []}
    cur_change = None

    def push_change():
        nonlocal cur_change
        if cur_change and (cur_change.get("basis") or cur_change.get("reason") or cur_change.get("value")):
            changes.append(cur_change)
        cur_change = None

    for f in fields:
        L, v, num = fold(f["label"]), f["value"], f["num"]
        # --- wspólne
        if re.search(r"numer ogloszenia o wyniku postepowania", L):
            info["result_ref"] = normalize_bzp(v)[0]
        elif re.search(r"^numer ogloszenia( w bzp lub dz\. urz\. ue)?$", L) and num.startswith(("2.14", "3.1.1", "3.2.1")):
            info["notice_ref"] = normalize_bzp(v)[1]
        if notice_type == "ContractNotice":
            if re.search(r"okres realizacji zamowienia", L) or L == "termin realizacji":
                days, months, date = _duration(v)
                if date:
                    facts.append(_fact("planned_end_date", f, value_text=date))
                elif days:
                    facts.append(_fact("planned_duration_days", f, value_num=float(days), value_text=months, unit="dni"))
            elif L.startswith("wartosc zamowienia"):
                a = _amount(v)
                if a:
                    facts.append(_fact("estimated_value_net", f, value_num=a, unit="PLN", vat="netto"))
            elif re.search(r"rodzaj i zakres zmian umowy", L):
                info["provisions"] = v
            elif re.search(r"wymaga zabezpieczenia nalezytego wykonania", L):
                facts.append(_fact("security_required", f, value_text=_yes(v)))
            elif re.search(r"stosowane kryteria oceny ofert", L):
                facts.append(_fact("criteria", f, value_text=v[:300]))
        elif notice_type == "TenderResultNotice":
            if L.startswith("wartosc zamowienia"):
                a = _amount(v)
                if a:
                    facts.append(_fact("estimated_value_net", f, value_num=a, unit="PLN", vat="netto"))
            elif L.startswith("wartosc czesci"):
                a = _amount(v)
                if a:
                    facts.append(_fact("part_value_net", f, value_num=a, unit="PLN", vat="netto"))
            elif L.startswith("postepowanie zakonczylo sie"):
                facts.append(_fact("procedure_result", f, value_text="unieważnienie" if "uniewaz" in fold(v) else "zawarcie umowy"))
            elif L.startswith("przyczyna uniewaznienia"):
                info["cancel"].append({"reason": v, "part": f["part"], "line": f["line"]})
            elif L.startswith("podstawa prawna uniewaznienia"):
                if info["cancel"]:
                    info["cancel"][-1]["basis"] = v
                else:
                    info["cancel"].append({"basis": v, "part": f["part"], "line": f["line"]})
            elif L.startswith("liczba otrzymanych ofert lub wnioskow") or L == "liczba otrzymanych ofert":
                m = re.search(r"\d+", v)
                if m:
                    facts.append(_fact("n_offers", f, value_num=float(m.group(0)), unit="szt."))
            elif L.startswith("liczba ofert odrzuconych"):
                m = re.search(r"\d+", v)
                if m:
                    facts.append(_fact("n_rejected", f, value_num=float(m.group(0)), unit="szt."))
            elif "z najnizsza cena" in L:
                facts.append(_fact("offer_min", f, value_num=_amount(v), unit="PLN", vat="brutto"))
            elif "z najwyzsza cena" in L:
                facts.append(_fact("offer_max", f, value_num=_amount(v), unit="PLN", vat="brutto"))
            elif "oferty wykonawcy, ktoremu udzielono" in L:
                facts.append(_fact("awarded_price", f, value_num=_amount(v), unit="PLN", vat="brutto"))
            elif L.startswith("nazwa (firma) wykonawcy"):
                facts.append(_fact("contractor", f, value_text=v[:200]))
            elif L.startswith("data zawarcia umowy"):
                facts.append(_fact("signed_date", f, value_text=parse_date(v)))
            elif L.startswith("wartosc umowy"):
                facts.append(_fact("contract_value", f, value_num=_amount(v), unit="PLN", vat="brutto"))
            elif L.startswith("okres realizacji"):
                days, months, date = _duration(v)
                if date:
                    facts.append(_fact("planned_end_date", f, value_text=date))
                elif days:
                    facts.append(_fact("planned_duration_days", f, value_num=float(days), value_text=months, unit="dni"))
        elif notice_type in ("ContractPerformingNotice", "AgreementUpdateNotice"):
            if L.startswith("data zawarcia umowy"):
                facts.append(_fact("signed_date", f, value_text=parse_date(v)))
            elif L.startswith("okres realizacji") and v:
                days, months, date = _duration(v)
                if date:
                    facts.append(_fact("planned_end_date", f, value_text=date))
                elif days:
                    facts.append(_fact("planned_duration_days", f, value_num=float(days), value_text=months, unit="dni"))
            elif L.startswith("wartosc umowy"):
                facts.append(_fact("contract_value", f, value_num=_amount(v), unit="PLN", vat="brutto"))
            elif L.startswith("nazwa (firma) wykonawcy"):
                facts.append(_fact("contractor", f, value_text=v[:200]))
            elif L == "czy umowa zostala wykonana":
                facts.append(_fact("performed", f, value_text=_yes(v)))
            elif L.startswith("termin wykonania umowy"):
                facts.append(_fact("actual_end_date", f, value_text=parse_date(v)))
            elif L.startswith("czy umowe wykonano w pierwotnie okreslonym terminie"):
                facts.append(_fact("performed_on_time", f, value_text=_yes(v)))
            elif L.startswith("liczba zmian"):
                m = re.search(r"\d+", v)
                if m:
                    facts.append(_fact("n_changes", f, value_num=float(m.group(0))))
            elif L.startswith("laczna wartosc wynagrodzenia wyplacon"):
                facts.append(_fact("final_paid", f, value_num=_amount(v), unit="PLN", vat="brutto"))
            elif L.startswith("czy umowa zostala wykonana nalezycie"):
                facts.append(_fact("performed_properly", f, value_text=_yes(v)))
            # --- zmiany umowy
            elif L.startswith("numer zmiany"):
                push_change()
                cur_change = {"no": v, "lines": [f["line"]]}
            elif L.startswith("data zmiany umowy"):
                push_change()
                cur_change = {"no": "1", "date": parse_date(v), "lines": [f["line"]]}
            elif L.startswith("podstawa prawna zmiany"):
                cur_change = cur_change or {"no": "1", "lines": []}
                cur_change["basis"] = v
                cur_change["lines"].append(f["line"])
            elif L.startswith("przyczyny dokonania zmian"):
                cur_change = cur_change or {"no": "1", "lines": []}
                cur_change["reason"] = v
                cur_change["lines"].append(f["line"])
            elif L.startswith("krotki opis") and cur_change is not None:
                cur_change["description"] = v
            elif L == "wartosc zmiany" and cur_change is not None:
                cur_change["value"] = _amount(v)
                cur_change["lines"].append(f["line"])
            elif L.startswith("wzrost ceny w zwiazku ze zmiana") and cur_change is not None:
                cur_change["price_increase"] = _yes(v)
    push_change()
    for c in changes:
        c["legal_basis"] = ", ".join(legal_bases(c.get("basis") or "")) or (c.get("basis") or "")[:80]
        c["quote"] = " | ".join(c.pop("lines", []))[:900]
    return {"facts": [x for x in facts if x.get("value_num") is not None or x.get("value_text")], "changes": changes, "info": info}


LEGAL_BASIS_MEANING = {
    "art. 455 ust. 1 pkt 1": "zmiana przewidziana w dokumentach zamówienia",
    "art. 455 ust. 1 pkt 2": "zmiana wykonawcy",
    "art. 455 ust. 1 pkt 3": "roboty/dostawy/usługi dodatkowe",
    "art. 455 ust. 1 pkt 4": "okoliczności nieprzewidywalne",
    "art. 455 ust. 2": "zmiana o niewielkiej wartości",
}


def basis_meaning(basis):
    fb = fold(basis or "").replace(" ", "")
    for k, v in LEGAL_BASIS_MEANING.items():
        if fold(k).replace(" ", "") in fb:
            return k, v
    return None, None
