"""Narzędzia wspólne: normalizacja identyfikatorów, kwot, dat, tekstu."""
import datetime as _dt
import hashlib
import html
import math
import re
import unicodedata

# ---------------------------------------------------------------- czas

def now_iso():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def today():
    return _dt.date.today().isoformat()


# ---------------------------------------------------------------- identyfikatory

def normalize_nip(value):
    """Zwraca 10 cyfr NIP lub None."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("48") and len(digits) == 12:  # PL prefix po numerze kraju
        digits = digits[2:]
    return digits if len(digits) == 10 else None


def nip_valid(nip):
    nip = normalize_nip(nip)
    if not nip:
        return False
    weights = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    s = sum(int(nip[i]) * weights[i] for i in range(9)) % 11
    return s != 10 and s == int(nip[9])


def normalize_regon(value):
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) in (9, 14) else None


BZP_RE = re.compile(r"(\d{4})\s*/\s*BZP\s*0*(\d{1,8})(?:\s*/\s*(\d{1,2}))?", re.I)


def normalize_bzp(value):
    """'2022/BZP 00058537/01' -> ('2022/BZP 00058537/01', '2022/BZP 00058537')."""
    if not value:
        return None, None
    m = BZP_RE.search(str(value))
    if not m:
        return None, None
    year, num, part = m.group(1), int(m.group(2)), m.group(3)
    base = f"{year}/BZP {num:08d}"
    full = f"{base}/{int(part):02d}" if part else f"{base}/01"
    return full, base


def find_bzp_numbers(text):
    out = []
    for m in BZP_RE.finditer(text or ""):
        full, base = normalize_bzp(m.group(0))
        if base and base not in out:
            out.append(base)
    return out


KPO_RE = re.compile(r"\bKPO[A-Z]?\.\d{2}\.\d{2}-[A-Z]{2}\.\d{2}-\d{4}/\d{2}\b")
CST_RE = re.compile(r"\bF[A-Z]{2,6}\.\d{2}\.\d{2}-[A-Z]{2,4}\.\d{2}-\d{3,4}/\d{2}\b")
OCID_RE = re.compile(r"\bocds-[a-z0-9]{6}-[0-9a-f\-]{8,}\b", re.I)
TED_RE = re.compile(r"\b(\d{1,6})-(20\d{2})\b")


def classify_identifier(value):
    """Rozpoznaje rodzaj identyfikatora publicznego."""
    if not value:
        return None, None
    v = str(value).strip()
    full, _ = normalize_bzp(v)
    if full:
        return "BZP", full
    if KPO_RE.search(v):
        return "KPO", KPO_RE.search(v).group(0)
    if CST_RE.search(v):
        return "CST", CST_RE.search(v).group(0)
    if OCID_RE.search(v):
        return "OCID", OCID_RE.search(v).group(0).lower()
    if normalize_nip(v) and nip_valid(v):
        return "NIP", normalize_nip(v)
    m = TED_RE.fullmatch(v)
    if m:
        return "TED", v
    return "INNY", v


def year_from_identifier(id_type, value):
    if not value:
        return None
    if id_type == "BZP":
        return int(str(value)[:4])
    m = re.search(r"/(\d{2})$", str(value))
    if m:
        return 2000 + int(m.group(1))
    return None


# ---------------------------------------------------------------- kwoty

AMOUNT_RE = re.compile(
    r"(?<![\d,])(\d{1,3}(?:[   .]\d{3})+(?:,\d{1,2})?|\d+(?:[,.]\d{1,2})?)\s*(?:zł|zl|złotych|zlotych|PLN|pln|ZŁ|ZL)\b",
)
AMOUNT_ANY_RE = re.compile(r"(?<![\d,])(\d{1,3}(?:[   .]\d{3})+(?:,\d{1,2})?|\d+(?:[,.]\d{1,2})?)")


def parse_amount(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().replace(" ", " ").replace(" ", " ")
    s = re.sub(r"(zł|złotych|PLN|pln)", "", s).strip()
    if not s:
        return None
    # 1 234 567,89 | 1.234.567,89 | 1234567.89
    if "," in s:
        s = s.replace(" ", "").replace(".", "").replace(",", ".")
    else:
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", s.replace(" ", "")):
            s = s.replace(".", "")
        s = s.replace(" ", "")
    try:
        return float(s)
    except ValueError:
        return None


def find_amounts(text):
    return [(parse_amount(m.group(1)), m.start(), m.end()) for m in AMOUNT_RE.finditer(text or "")]


def fmt_pln(v):
    if v is None:
        return "—"
    return f"{v:,.2f} zł".replace(",", " ").replace(".", ",")


# ---------------------------------------------------------------- daty

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
    "wrzesnia": 9, "pazdziernika": 10,
}
DATE_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})|(\d{1,2})[./](\d{1,2})[./](\d{4})|(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})",
    re.I,
)


def parse_date(s):
    if not s:
        return None
    if isinstance(s, (_dt.date, _dt.datetime)):
        return s.date().isoformat() if isinstance(s, _dt.datetime) else s.isoformat()
    m = DATE_RE.search(str(s))
    if not m:
        return None
    try:
        if m.group(1):
            d = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        elif m.group(4):
            d = _dt.date(int(m.group(6)), int(m.group(5)), int(m.group(4)))
        else:
            d = _dt.date(int(m.group(9)), MONTHS[m.group(8).lower()], int(m.group(7)))
        return d.isoformat()
    except ValueError:
        return None


def find_dates(text):
    out = []
    for m in DATE_RE.finditer(text or ""):
        d = parse_date(m.group(0))
        if d:
            out.append((d, m.start(), m.end()))
    return out


def add_duration(date_iso, days=None, months_text=None):
    """Data + okres; „12 mies.” liczone kalendarzowo, w przeciwnym razie dni."""
    try:
        d = _dt.date.fromisoformat(date_iso[:10])
    except Exception:
        return None
    if months_text:
        m = re.match(r"(\d+)\s*mies", months_text)
        if m:
            total = d.month - 1 + int(m.group(1))
            y, mo = d.year + total // 12, total % 12 + 1
            import calendar
            day = min(d.day, calendar.monthrange(y, mo)[1])
            return _dt.date(y, mo, day).isoformat()
    if days is None:
        return None
    return (d + _dt.timedelta(days=int(days))).isoformat()


def days_between(a, b):
    try:
        da = _dt.date.fromisoformat(a[:10])
        db = _dt.date.fromisoformat(b[:10])
        return (db - da).days
    except Exception:
        return None


# ---------------------------------------------------------------- tekst

def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    # każdy blok (także jego początek) to nowa linia: BZP na żywo podaje pola jako
    # <h3>5.3.) Etykieta: </h3> wartość <h3>5.4.) …</h3> — bez tego wartość zlewa się z kolejną etykietą
    s = re.sub(r"(?i)<br\s*/?>|</?(?:p|div|h\d|li|tr|section|article|table|ul|ol)(?:\s[^>]*)?>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t ]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def fold(s):
    """Małe litery bez polskich znaków — do porównań."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = s.replace("ł", "l")
    return "".join(c for c in s if not unicodedata.combining(c))


STOP = set(
    """a aby ale albo ani az bez bo by byc byl byla bylo byly co czy dla do gdy gdzie i ich innych jak jako jest
    jej jego juz lub ma maja na nad nie niz o od oraz po pod przez przy sa sie ta tak takze te tego tej to tu tym
    w we wraz z za ze zl ul nr oraz m.in r roku dz poz gmina gminy gminie miejscowosci miejscowosc terenie zadanie
    realizacja ramach projekt projektu przedsiewziecie inwestycja inwestycji wraz etap""".split()
)


def tokens(text, stem=6):
    out = []
    for t in re.findall(r"[a-z0-9]+", fold(text)):
        if len(t) < 3 or t in STOP or t.isdigit():
            continue
        out.append(t[:stem] if stem else t)
    return out


_ABBR = re.compile(r"\b(art|ust|pkt|nr|poz|tj|tzw|godz|ok|zł|dz|lit|par|str|ul|al|r|m\.in|im|sp|wg|zm|tys|mln|mld)\.(?=\s)", re.I)


def sentences(text):
    protected = _ABBR.sub(lambda m: m.group(1) + "․", text or "")
    parts = re.split(r"(?<=[.;!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ0-9\-•])|\n+", protected)
    return [p.replace("․", ".").strip() for p in parts if p and len(p.strip()) > 3]


def snippet(text, start, end, width=160):
    a = max(0, start - width)
    b = min(len(text), end + width)
    pre = "…" if a > 0 else ""
    post = "…" if b < len(text) else ""
    return pre + re.sub(r"\s+", " ", text[a:b]).strip() + post


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


_SSL_CTX = None


def ssl_context():
    """Kontekst TLS z zaufanymi certyfikatami CA (działa też w Python.org na macOS bez Install Certificates)."""
    global _SSL_CTX
    if _SSL_CTX is not None:
        return _SSL_CTX
    import os
    import ssl
    try:
        import certifi
        _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
        return _SSL_CTX
    except ImportError:
        pass
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) == 0:
        for path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
            if os.path.exists(path):
                ctx.load_verify_locations(cafile=path)
                break
    _SSL_CTX = ctx
    return _SSL_CTX


def ratio_similarity(a, b):
    """Podobieństwo zbiorów tokenów (Dice)."""
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    return 2 * len(ta & tb) / (len(ta) + len(tb))


def log_ratio_sim(a, b, span=10.0):
    """1 dla równych wartości, 0 gdy różnią się o czynnik `span` lub więcej."""
    if not a or not b or a <= 0 or b <= 0:
        return None
    return max(0.0, 1 - abs(math.log(a / b)) / math.log(span))


def percentile(values, p):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return vals[int(k)]
    return vals[f] + (vals[c] - vals[f]) * (k - f)


def extract_length_km(text):
    """Szuka długości sieci w tekście; zwraca km (suma najczęściej to przesada — bierzemy największą wartość)."""
    vals = []
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(km|kilometr\w*)", text or "", re.I):
        vals.append(float(m.group(1).replace(",", ".")))
    for m in re.finditer(r"(\d[\d ]*(?:[.,]\d+)?)\s*(m|mb|metr\w*)\b", text or "", re.I):
        try:
            v = float(m.group(1).replace(" ", "").replace(",", ".")) / 1000
        except ValueError:
            continue
        if 0.05 <= v <= 200:
            vals.append(v)
    return max(vals) if vals else None


# ---------------------------------------------------------------- CSV

def decode_text(data):
    """UTF-8 (także z BOM), a gdy się nie da — Windows-1250 (polski Excel zapisuje CSV w tym kodowaniu)."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1250", "replace")


def csv_rows(txt):
    """Wiersze CSV z automatycznym separatorem (; , tabulator). Sniffer zawodzi przy długich polach z przecinkami
    i średnikami w treści — wtedy decyduje liczba separatorów w wierszu nagłówka."""
    import csv
    import io
    first = (txt or "").split("\n", 1)[0]
    try:
        delim = csv.Sniffer().sniff(txt[:3000], delimiters=";,\t").delimiter
    except csv.Error:
        delim = None
    if not delim or first.count(delim) == 0:
        delim = max(";,\t", key=first.count)
    return list(csv.reader(io.StringIO(txt), delimiter=delim))
