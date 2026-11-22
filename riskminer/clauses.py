"""Audyt klauzul projektu umowy (PPU/SWZ) na tle tego, co faktycznie działo się w podobnych umowach.

Dla każdej klauzuli: czy jest w przekazanym tekście (z cytatem i stroną), czy jest wymagana ustawą,
które ryzyka z katalogu zabezpiecza i — najważniejsze — jak często te ryzyka zmaterializowały się
w klasie referencyjnej oraz jaką podstawą prawną zamawiający musieli potem zmieniać umowy.

To lista kontrolna dla eksperta i prawnika, nie opinia prawna. Wzorce działają na tekście bez polskich znaków.
"""
import re

from .util import fold

CLAUSES = [
    {"id": "K01", "name": "Waloryzacja wynagrodzenia (zmiana cen materiałów i kosztów)", "ref": "art. 439 Pzp",
     "mandatory": "months>6", "mandatory_text": "obowiązkowa w umowie na roboty budowlane zawartej na okres dłuższy niż 6 miesięcy",
     "risks": ["R08", "R13"],
     "patterns": [r"waloryzac", r"zmian\w* (cen|kosztow) (materialow|zwiazanych z realizacj)", r"wskaznik\w* (cen|zmiany cen|gus)", r"art\.?\s*439"],
     "exclude": [r"\bnie (podlega|przewiduje|przewiduj\w*)[^.]{0,40}waloryzac", r"wylacz\w*[^.]{0,30}waloryzac"],
     "model": "Wynagrodzenie podlega waloryzacji wg wskaźnika cen produkcji budowlano-montażowej GUS, po przekroczeniu progu zmiany "
              "(np. 5%) liczonego od miesiąca złożenia oferty; maksymalna łączna zmiana — np. 10% wynagrodzenia; wskazanie, jak zmiana "
              "przenosi się na wynagrodzenie podwykonawców."},
    {"id": "K02", "name": "Katalog zmian przewidzianych (przesłanki, sposób wyceny, limit)", "ref": "art. 455 ust. 1 pkt 1 Pzp",
     "risks": ["R07", "R06", "R01"],
     "patterns": [r"art\.?\s*455", r"przewiduje (sie )?(mozliwos\w* )?(dokonani\w* )?(istotn\w* )?zmian", r"dopuszcza (sie )?(mozliwos\w* )?(dokonani\w* )?(istotn\w* )?zmian",
                  r"zmian\w* (postanowien|tresci) (zawartej )?umowy"],
     "model": "Zamknięty katalog zmian: przesłanka (zdarzenie), jej udokumentowanie, skutek (termin/wynagrodzenie), sposób wyceny "
              "(składniki cenotwórcze z oferty) i łączny limit wartości zmian. Zmiana „przewidziana” wymaga jasnych, precyzyjnych "
              "i jednoznacznych postanowień — inaczej zostają podstawy z limitami (pkt 3–4, ust. 2)."},
    {"id": "K03", "name": "Warunki gruntowe i stan istniejący odmienne od dokumentacji", "ref": "podział ryzyka (dobra praktyka, raport bazowy)",
     "risks": ["R02"],
     "patterns": [r"warunk\w* (gruntow|geologiczn|hydrogeologiczn|gruntowo-wodn)\w*[^.]{0,100}(odmienn|inn\w* niz|rozn\w* od|nieprzewidzian)",
                  r"(odmienn|inn\w* niz|nieprzewidzian)\w*[^.]{0,60}warunk\w* (gruntow|geologiczn)",
                  r"(raport|dokumentacj|opini)\w* (geotechniczn|geologiczn)"],
     "model": "Dokumentacja geotechniczna jako „raport bazowy”: warunki gorsze niż opisane uprawniają do zmiany terminu i wynagrodzenia "
              "(wycena wg składników z oferty); ryzyko warunków opisanych w raporcie ponosi wykonawca."},
    {"id": "K04", "name": "Przedłużenie terminu — warunki atmosferyczne z obiektywnym kryterium", "ref": "art. 455 ust. 1 pkt 1 Pzp",
     "risks": ["R06"],
     "patterns": [r"warunk\w* atmosferyczn", r"imgw", r"temperatur\w* (ponizej|powietrza)", r"opad\w* (deszczu|sniegu|atmosferyczn)"],
     "quality": [r"imgw", r"temperatur\w* ponizej", r"\d+\s*(mm|°c|stopni)", r"dni\w* (roboczych )?(w ktorych|z opadami)"],
     "quality_text": "brak obiektywnego kryterium (np. dane IMGW, temperatura, liczba dni z opadem) — spór o to, czy pogoda „uniemożliwiała” roboty",
     "model": "Termin wydłuża się o liczbę dni, w których warunki uniemożliwiały roboty, potwierdzone danymi IMGW (np. temperatura "
              "poniżej −5°C lub opad powyżej 10 mm/dobę) i wpisem do dziennika budowy."},
    {"id": "K05", "name": "Przedłużenie terminu — decyzje, organy, gestorzy sieci", "ref": "art. 455 ust. 1 pkt 1 Pzp",
     "risks": ["R04"],
     "patterns": [r"(decyzj|pozwoleni|uzgodnieni|organ\w* (administracj|wydajac)|gestor)[^.]{0,140}(przedluz|zmian\w* terminu|wydluz)",
                  r"(przedluz|zmian\w* terminu|wydluz)[^.]{0,140}(decyzj|pozwoleni|uzgodnieni|organ\w*|gestor)"],
     "model": "Wydłużenie terminu o czas procedowania decyzji/uzgodnień ponad terminy ustawowe, jeśli wykonawca złożył kompletny wniosek "
              "w terminie z harmonogramu; obowiązek bieżącego informowania zamawiającego."},
    {"id": "K06", "name": "Teren budowy, kolizje i prawa do nieruchomości", "ref": "podział ryzyka (dobra praktyka)",
     "risks": ["R03"],
     "patterns": [r"przekaz\w* (wykonawcy )?(terenu|teren|placu|plac) budowy", r"kolizj", r"sluzebnos", r"prawo do dysponowania", r"zgod\w* wlasciciel"],
     "model": "Przekazanie terenu w podziale na odcinki z terminami; przedłużenie terminu o czas opóźnienia w przekazaniu terenu "
              "lub ustanowieniu służebności z przyczyn zamawiającego; procedura dla kolizji z niezinwentaryzowanym uzbrojeniem."},
    {"id": "K07", "name": "Roboty zamienne, dodatkowe i zaniechane — zasady wyceny", "ref": "art. 455 ust. 1 pkt 1 / pkt 3 Pzp",
     "risks": ["R07", "R01"],
     "patterns": [r"robot\w* (zamienn|dodatkow|zaniechan)", r"skladnik\w* cenotworcz", r"kosztorys\w* (ofertow|powykonawcz|szczegolow|roznicow)",
                  r"\bknr\b", r"sekocenbud", r"stawk\w* (roboczogodzin|r-g)"],
     "model": "Wycena zmian z kosztorysu ofertowego, a gdy brak pozycji — wg składników cenotwórczych z oferty i nakładów KNR/KNNR, "
              "ceny materiałów wg SEKOCENBUD; protokół konieczności przed wykonaniem robót."},
    {"id": "K08", "name": "Hierarchia dokumentów umowy", "ref": "dobra praktyka (spójność zakresu)",
     "risks": ["R01", "R05"],
     "patterns": [r"kolejnos\w* (waznosci|pierwszenstwa|stosowania)", r"hierarchi\w* dokument", r"pierwszenstw\w*[^.]{0,40}dokument"],
     "model": "W razie rozbieżności: Umowa > SWZ z wyjaśnieniami > PFU/projekt > STWiORB > przedmiar (pomocniczo przy ryczałcie)."},
    {"id": "K09", "name": "Kary umowne z łącznym limitem", "ref": "art. 436 pkt 3 Pzp",
     "mandatory": "if_penalties", "mandatory_text": "umowa określa łączną maksymalną wysokość kar umownych",
     "risks": ["R12"],
     "patterns": [r"kar\w* umown"],
     "quality": [r"(laczn\w*|maksymaln\w*) (maksymaln\w* )?(wysokos|wartos|kwot|sum)\w* (naliczonych )?kar", r"kar\w* umown\w*[^.]{0,160}nie (moze|moga|mog\w*) przekroczyc",
                 r"limit\w* kar"],
     "quality_text": "są kary umowne, ale brak łącznego limitu — wymóg art. 436 pkt 3 Pzp",
     "model": "Łączna maksymalna wysokość kar umownych — np. 20% wynagrodzenia brutto; kary za zwłokę liczone od wartości "
              "niewykonanego etapu, nie całej umowy."},
    {"id": "K10", "name": "Płatności częściowe / zaliczki", "ref": "art. 443 i art. 447 Pzp",
     "mandatory": "months>12", "mandatory_text": "w umowie na okres dłuższy niż 12 miesięcy — zapłata częściowego wynagrodzenia lub zaliczki (art. 447 Pzp)",
     "risks": ["R13", "R12"],
     "patterns": [r"(platnos|wynagrodzeni|faktur)\w* czesciow", r"zaliczk", r"(etap|odcink|element)\w*[^.]{0,80}(platn|faktur|rozliczen)"],
     "model": "Płatności częściowe za odebrane elementy harmonogramu rzeczowo-finansowego (np. co kwartał), z limitem przed odbiorem "
              "końcowym; zgodność z harmonogramem wypłat dofinansowania."},
    {"id": "K11", "name": "Podwykonawstwo i bezpośrednia zapłata podwykonawcom", "ref": "art. 437, art. 463–465 Pzp",
     "risks": ["R12"],
     "patterns": [r"podwykonaw"],
     "quality": [r"bezposredni\w* zaplat", r"art\.?\s*465", r"zaplat\w*[^.]{0,60}podwykonawc"],
     "quality_text": "podwykonawstwo wspomniane, ale bez zasad zapłaty i akceptacji umów (art. 464–465 Pzp)",
     "model": "Akceptacja projektów umów o podwykonawstwo, dowody zapłaty jako warunek zapłaty wykonawcy, bezpośrednia zapłata "
              "podwykonawcy i potrącenie z wynagrodzenia wykonawcy."},
    {"id": "K12", "name": "Odbiory, próby i rozruch (kryteria odbioru)", "ref": "dobra praktyka (sektor wod-kan)",
     "risks": ["R10", "R15"],
     "patterns": [r"odbior\w* (koncow|czesciow|robot zanikajac)", r"inspekcj\w* (tv|telewiz|kamer)", r"prob\w* (szczelnos|cisnien)", r"rozruch"],
     "model": "Warunki odbioru: pozytywne próby szczelności, inspekcja TV kanałów z raportem, rozruch przepompowni, dokumentacja "
              "powykonawcza i inwentaryzacja geodezyjna, szkolenie obsługi."},
    {"id": "K13", "name": "Zabezpieczenie należytego wykonania umowy", "ref": "art. 449–453 Pzp",
     "risks": ["R12"],
     "patterns": [r"zabezpieczeni\w* nalezyt"],
     "model": "Zabezpieczenie (np. 5% ceny ofertowej), 70% zwracane po odbiorze końcowym, 30% po okresie rękojmi."},
    {"id": "K14", "name": "Model wynagrodzenia dopasowany do niepewności zakresu", "ref": "dobra praktyka",
     "risks": ["R08", "R01", "R02"],
     "patterns": [r"ryczalt", r"(wynagrodzeni|rozliczeni)\w* kosztorysow", r"obmiar"],
     "model": "Przy niepewnym zakresie (sieci, grunt, przyłącza) — rozliczenie mieszane: ryczałt za projekt i obiekty, kosztorys/obmiar "
              "za długość sieci i przyłącza; albo ryczałt z jasnym mechanizmem zmian (K02, K07)."},
]

CONTRACT_MARKERS = [r"§\s*\d", r"projektowan\w* postanowien\w* umowy", r"wzor\w* umowy", r"\bppu\b", r"specyfikacj\w* warunkow zamowienia",
                    r"zamawiajacy[^.]{0,40}wykonawc"]


def detect_months(text):
    """Okres realizacji w miesiącach z opisu lub umowy.
    Pierwszeństwo ma okres podany wprost („termin/okres/czas realizacji…”, „realizacja 10 miesięcy”); okresy gwarancji,
    rękojmi, kar i przechowywania dokumentów są pomijane (np. „gwarancja na okres 60 miesięcy od dnia odbioru”)."""
    ft = fold(text)

    def ok(m):
        # tylko w obrębie tego samego zdania: „…gwarancji 60 miesięcy. Termin realizacji 14 miesięcy…” → 14
        before = re.split(r"[.;\n]", ft[max(0, m.start() - 80): m.start()])[-1]
        return not re.search(r"gwaranc|rekojm|\bkar[aeyi]?\b|przechowyw|archiw", before + ft[m.start(): m.end()])

    explicit, generic = [], []
    for m in re.finditer(r"(termin\w*|okres\w*|czas\w*) (realizacji|wykonania)[^.]{0,80}?(\d{1,3})\s*(mies|miesiec)", ft):
        if ok(m):
            explicit.append(int(m.group(3)))
    for m in re.finditer(r"(termin\w*|okres\w*) (realizacji|wykonania)[^.]{0,80}?(\d{2,4})\s*dni", ft):
        if ok(m):
            explicit.append(round(int(m.group(3)) / 30.4))
    for m in re.finditer(r"(realizacj\w*|trwa\w*|harmonogram\w*)[^.\d]{0,40}?(\d{1,3})\s*(mies|miesiec)", ft):
        if ok(m):
            explicit.append(int(m.group(2)))
    for m in re.finditer(r"(\d{1,3})\s*(miesiecy|miesiace|mies\.?)\s*(od|licz)", ft):
        if ok(m):
            generic.append(int(m.group(1)))
    if not explicit and not generic:
        # „…, 18 miesięcy.” bez słowa „realizacja”
        for m in re.finditer(r"\b(\d{1,3})\s*(miesiecy|miesiace|miesiac)\b", ft):
            if ok(m):
                generic.append(int(m.group(1)))
    vals = [v for v in (explicit or generic) if 1 <= v <= 120]
    return max(vals) if vals else None

def fold_keep(s):
    """fold() zachowujący długość tekstu — pozycje dopasowań wskazują ten sam fragment w oryginale."""
    return "".join((fold(c) or " ")[0] for c in (s or ""))


SENT_START = re.compile(r"(\n|\.\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„\"(]))")


def _quote(t, s0, e0):
    a = 0
    for m in SENT_START.finditer(t, max(0, s0 - 220), s0):
        a = m.end()
    if s0 - a > 220:
        a = s0 - 120
    ends = [m.start() + 1 for m in SENT_START.finditer(t, e0, min(len(t), e0 + 320))]
    b = ends[0] if ends else min(len(t), e0 + 260)
    return t[a:b].strip()


def _find(patterns, pages):
    best = None
    for pg in pages:
        ft = fold_keep(pg["text"])
        for pat in patterns:
            for m in re.finditer(pat, ft):
                q = _quote(pg["text"], m.start(), m.end())
                hit = {"page": pg.get("page"), "doc": pg.get("doc"), "quote": q, "pattern": pat}
                if len(q) >= 40:
                    return hit
                best = best or hit  # nagłówek („§ 6. Kary umowne”) — szukamy treści, a nagłówek zostaje w odwodzie
    return best


def has_contract_text(pages, doc_types=()):
    if any(re.search(r"umow|ppu|swz|specyfikacj", fold(t or "")) for t in doc_types):
        return True
    ft = fold(" ".join(p["text"] for p in pages))
    hits = sum(1 for pat in CONTRACT_MARKERS if re.search(pat, ft))
    return hits >= 2 or len(re.findall(r"§\s*\d", ft)) >= 3


def audit(pages, doc_types=(), register=None, bases=None, months=None, formula=None):
    """pages: [{page, text, doc}] — tekst opisu i dokumentów planowanej inwestycji.
    register: wynik forecast.risk_register (ryzyka zmaterializowane w podobnych umowach)."""
    contract = has_contract_text(pages, doc_types)
    months = months or detect_months(" ".join(p["text"] for p in pages))
    reg = {r["code"]: r for r in ((register or {}).get("rows") or [])}
    n_ref = (register or {}).get("n") or 0
    rows = []
    for c in CLAUSES:
        found = _find(c["patterns"], pages) if contract else None
        excl = _find(c.get("exclude", []), pages) if contract else None
        status, note = ("nie oceniono", "brak projektu umowy / SWZ w materiałach") if not contract else ("jest", None) if found else ("brak", None)
        if contract and excl:
            status, note, found = "wyłączona", "umowa wprost wyłącza ten mechanizm", excl
        if contract and found and c.get("quality") and status == "jest" and not _find(c["quality"], pages):
            status, note = "niepełna", c.get("quality_text")
        mand = c.get("mandatory")
        required = False
        if mand == "months>6":
            required = months is None or months > 6
        elif mand == "months>12":
            required = months is not None and months > 12
        elif mand == "if_penalties":
            required = bool(found)
        legal_gap = required and status in ("brak", "wyłączona", "niepełna")
        # dane: jak często ryzyka, które zabezpiecza klauzula, zmaterializowały się w podobnych umowach
        evid = [reg[r] for r in c["risks"] if r in reg]
        emv = sum((r.get("emv_pct") or 0) for r in evid)
        prob = max((r["probability"] for r in evid), default=0)
        why = []
        for r in evid:
            s = f"{r['code']} {r['name']}: {r['k']} z {r['n']} podobnych umów"
            if r.get("impact_cost_pct") is not None:
                s += f", mediana kosztu zmian {r['impact_cost_pct'] * 100:+.1f}% wartości umowy".replace(".", ",")
            if r.get("impact_delay_days"):
                s += f", mediana wydłużenia {r['impact_delay_days']:.0f} dni"
            if r.get("bases"):
                s += "; zmieniano na podstawie: " + ", ".join(f"{b['basis']} ({b['n']}×)" for b in r["bases"][:3])
            why.append(s)
        if c["id"] == "K14" and contract and found and "ryczalt" in found["pattern"] and (formula == "zaprojektuj i wybuduj" or prob >= 0.15):
            status, note = ("do przemyślenia", "wynagrodzenie ryczałtowe przy niepewnym zakresie (R01/R02 w podobnych umowach) — "
                                               "rozważ rozliczenie mieszane albo mocny mechanizm zmian")
        priority = (100 if legal_gap else 0) + round(emv * 1000) + round(prob * 30) + (5 if status in ("brak", "niepełna") else 0)
        rows.append({"id": c["id"], "name": c["name"], "ref": c["ref"], "risks": c["risks"], "status": status, "note": note,
                     "required": required, "required_text": c.get("mandatory_text") if required else None, "legal_gap": legal_gap,
                     "evidence": found, "data_why": why, "probability": prob, "emv_pct": emv or None, "model": c["model"],
                     "priority": priority})
    rows.sort(key=lambda r: -r["priority"])
    gaps = [r for r in rows if r["legal_gap"]]
    weak = [r for r in rows if not r["legal_gap"] and r["status"] in ("brak", "niepełna", "do przemyślenia") and r["probability"] >= 0.1]
    if contract:
        summary = (f"Sprawdzono {len(rows)} klauzul. Wymogi ustawowe niespełnione: {len(gaps)}"
                   + (f" ({', '.join(r['ref'] for r in gaps)})" if gaps else "")
                   + f". Luki wobec ryzyk, które wystąpiły w podobnych umowach: {len(weak)}.")
    else:
        summary = ("Nie przekazano projektu umowy ani SWZ — pokazano listę klauzul do zaplanowania, uporządkowaną według tego, "
                   "jak często i jak kosztownie odpowiadające im ryzyka materializowały się w podobnych umowach. "
                   "Dodaj PPU/SWZ, aby sprawdzić tekst.")
    return {"has_contract": contract, "months": months, "rows": rows, "summary": summary, "n_reference": n_ref,
            "bases": bases,
            "disclaimer": "Lista kontrolna dla eksperta i prawnika — nie stanowi opinii prawnej. Wzorcowe zapisy wymagają dostosowania."}
