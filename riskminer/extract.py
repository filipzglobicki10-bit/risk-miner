"""Ekstrakcja tekstu z dokumentów: PDF (warstwa tekstowa + opcjonalny OCR), DOCX, XLSX, CSV, TXT, HTML.

Bez wymaganych zależności: DOCX i XLSX czytane są bezpośrednio z XML (zipfile).
PDF: biblioteka `pypdf` (jeśli zainstalowana). OCR: programy `pdftoppm` + `tesseract` (jeśli dostępne w PATH).
Wynik zawsze w postaci listy stron [{page, text}], żeby wnioski mogły wskazywać stronę.
"""
import csv
import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from .util import strip_html

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def capabilities():
    try:
        import pypdf  # noqa: F401
        pdf = True
    except Exception:
        pdf = False
    ocr = bool(shutil.which("tesseract") and shutil.which("pdftoppm"))
    return {"pdf_text": pdf, "ocr": ocr, "docx": True, "xlsx": True, "csv": True, "html": True}


# ---------------------------------------------------------------- XLSX

def read_xlsx(data):
    """Zwraca {nazwa_arkusza: [[komórki...], ...]} — wartości jako str/float."""
    z = zipfile.ZipFile(io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("s:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['s']}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rel_map = {r.get("Id"): r.get("Target") for r in rels}
    sheets = {}
    for sh in wb.find("s:sheets", NS):
        name = sh.get("name")
        rid = sh.get(f"{{{NS['r']}}}id")
        target = rel_map.get(rid, "")
        target = target.lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter(f"{{{NS['s']}}}row"):
            cells = {}
            for c in row.findall("s:c", NS):
                ref = c.get("r")
                col = _col_index(re.match(r"[A-Z]+", ref).group(0)) if ref else len(cells)
                t = c.get("t")
                v = c.find("s:v", NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{{{NS['s']}}}t"))
                elif v is not None and v.text is not None:
                    val = v.text
                    try:
                        f = float(val)
                        val = int(f) if f.is_integer() and "E" not in val.upper() else f
                    except ValueError:
                        pass
                else:
                    val = None
                cells[col] = val
            if cells:
                width = max(cells) + 1
                rows.append([cells.get(i) for i in range(width)])
            else:
                rows.append([])
        sheets[name] = rows
    return sheets


def _col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def excel_date(v):
    """Data jako liczba Excela -> ISO."""
    import datetime as dt
    if isinstance(v, (int, float)) and 20000 < v < 80000:
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()
    return v


# ---------------------------------------------------------------- DOCX

def read_docx(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find("w:body", NS)
    paras = []
    for el in body.iter():
        if el.tag == f"{{{NS['w']}}}p":
            txt = "".join(t.text or "" for t in el.iter(f"{{{NS['w']}}}t"))
            if txt.strip():
                paras.append(txt)
    # podział na „strony” po ~3000 znaków (DOCX nie ma stron logicznych) — zachowujemy numerację fragmentów
    pages, buf, n = [], [], 0
    for p in paras:
        buf.append(p)
        n += len(p)
        if n > 3000:
            pages.append("\n".join(buf))
            buf, n = [], 0
    if buf:
        pages.append("\n".join(buf))
    return [{"page": i + 1, "text": t} for i, t in enumerate(pages)] or [{"page": 1, "text": ""}]


# ---------------------------------------------------------------- PDF

def read_pdf(data, ocr=True):
    pages = []
    ocr_used = False
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        for i, p in enumerate(reader.pages):
            try:
                t = p.extract_text() or ""
            except Exception:
                t = ""
            pages.append({"page": i + 1, "text": t})
    except ImportError:
        pages = []
    except Exception:
        pages = []
    if not pages and shutil.which("pdftotext"):
        pages = _pdftotext(data)
    empty = [p for p in pages if len(p["text"].strip()) < 30]
    if ocr and capabilities()["ocr"] and (not pages or len(empty) >= max(1, len(pages) // 2)):
        o = _ocr_pdf(data)
        if o:
            pages, ocr_used = o, True
    return pages, ocr_used


def _pdftotext(data):
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.pdf")
        with open(src, "wb") as f:
            f.write(data)
        out = subprocess.run(["pdftotext", "-layout", src, "-"], capture_output=True, timeout=120)
        txt = out.stdout.decode("utf-8", "ignore")
    return [{"page": i + 1, "text": t} for i, t in enumerate(txt.split("\f")) if t.strip()]


def _ocr_pdf(data, max_pages=40):
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    lang = "pol" if "pol" in langs else "eng"
    pages = []
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.pdf")
        with open(src, "wb") as f:
            f.write(data)
        subprocess.run(["pdftoppm", "-r", "200", "-l", str(max_pages), "-png", src, os.path.join(td, "p")], timeout=600)
        imgs = sorted(f for f in os.listdir(td) if f.endswith(".png"))
        for i, img in enumerate(imgs):
            out = subprocess.run(["tesseract", os.path.join(td, img), "-", "-l", lang], capture_output=True, timeout=300)
            pages.append({"page": i + 1, "text": out.stdout.decode("utf-8", "ignore")})
    return pages


def ocr_image(data):
    if not shutil.which("tesseract"):
        return []
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    lang = "pol" if "pol" in langs else "eng"
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "img")
        with open(src, "wb") as f:
            f.write(data)
        out = subprocess.run(["tesseract", src, "-", "-l", lang], capture_output=True, timeout=300)
    return [{"page": 1, "text": out.stdout.decode("utf-8", "ignore")}]


# ---------------------------------------------------------------- dispatcher

def extract(filename, data):
    """Zwraca (pages, meta)."""
    ext = os.path.splitext(filename.lower())[1]
    meta = {"ext": ext, "ocr_used": False}
    if ext == ".pdf":
        pages, ocr_used = read_pdf(data)
        meta["ocr_used"] = ocr_used
        if not pages:
            meta["warning"] = "Brak warstwy tekstowej i brak OCR (zainstaluj pypdf lub tesseract+pdftoppm)."
    elif ext == ".docx":
        pages = read_docx(data)
    elif ext in (".xlsx", ".xlsm"):
        sheets = read_xlsx(data)
        pages = []
        for i, (name, rows) in enumerate(sheets.items()):
            lines = [" | ".join("" if c is None else str(c) for c in r) for r in rows if any(c not in (None, "") for c in r)]
            pages.append({"page": i + 1, "text": f"[Arkusz: {name}]\n" + "\n".join(lines)})
    elif ext in (".csv", ".tsv"):
        from .util import csv_rows, decode_text
        rows = csv_rows(decode_text(data))
        pages = [{"page": 1, "text": "\n".join(" | ".join(r) for r in rows)}]
    elif ext in (".html", ".htm"):
        pages = [{"page": 1, "text": strip_html(data.decode("utf-8", "ignore"))}]
    elif ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        pages = ocr_image(data)
        meta["ocr_used"] = bool(pages)
        if not pages:
            meta["warning"] = "Obraz wymaga OCR (tesseract) — niedostępny."
    elif ext == ".doc":
        pages = _doc_legacy(data)
        if not pages:
            meta["warning"] = "Format .doc wymaga programu antiword lub LibreOffice — zapisz jako DOCX."
    else:
        pages = [{"page": 1, "text": data.decode("utf-8", "ignore")}]
    return pages, meta


def _doc_legacy(data):
    tool = shutil.which("antiword")
    if tool:
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as f:
            f.write(data)
            p = f.name
        try:
            out = subprocess.run([tool, p], capture_output=True, timeout=60).stdout.decode("utf-8", "ignore")
            return [{"page": 1, "text": out}]
        finally:
            os.unlink(p)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "in.doc")
            with open(src, "wb") as f:
                f.write(data)
            subprocess.run([soffice, "--headless", "--convert-to", "docx", "--outdir", td, src], capture_output=True, timeout=120)
            dst = os.path.join(td, "in.docx")
            if os.path.exists(dst):
                with open(dst, "rb") as f:
                    return read_docx(f.read())
    return []


def guess_doc_type(filename, text):
    """Rozpoznanie typu dokumentu (heurystyka: nazwa pliku + nagłówek treści)."""
    f = (filename or "").lower()
    head = (text or "")[:500].lower()  # tytuł dokumentu — dalsza treść często cytuje inne dokumenty
    rules = [
        ("Ogłoszenie o wykonaniu umowy", ["ogłoszenie o wykonaniu umowy", "wykonaniu umowy"]),
        ("Ogłoszenie o zmianie umowy", ["ogłoszenie o zmianie umowy", "zmianie umowy"]),
        ("Ogłoszenie o wyniku postępowania", ["ogłoszenie o wyniku", "wyniku postępowania"]),
        ("Ogłoszenie o zamówieniu", ["ogłoszenie o zamówieniu"]),
        ("Aneks do umowy", ["aneks"]),
        ("Umowa", ["umowa nr", "zawarta w dniu", "zawarta dnia"]),
        ("PPU / wzór umowy", ["projektowane postanowienia", "wzór umowy", "wzor_umowy", "wzor umowy", "projekt umowy", "projekt_umowy", "istotne postanowienia", "ppu"]),
        ("SWZ", ["specyfikacja warunków zamówienia", "swz"]),
        ("PFU", ["program funkcjonalno", "pfu"]),
        ("OPZ", ["opis przedmiotu zamówienia", "opz"]),
        ("STWiORB", ["specyfikacje techniczne wykonania", "stwiorb"]),
        ("Przedmiar / kosztorys", ["przedmiar", "kosztorys"]),
        ("Orzeczenie KIO", ["krajowa izba odwoławcza", "wyrok kio", "sygn. akt kio", "kio "]),
        ("Wystąpienie pokontrolne / NIK", ["najwyższa izba kontroli", "wystąpienie pokontrolne", "informacja o wynikach kontroli"]),
        ("Protokół odbioru", ["protokół odbioru"]),
        ("Protokół konieczności", ["protokół konieczności"]),
        ("Uchwała / WPF", ["wieloletnia prognoza finansowa", "uchwała nr", "wpf"]),
        ("Studium wykonalności", ["studium wykonalności"]),
        ("Opis inwestycji", ["opis inwestycji", "koncepcja"]),
    ]
    for label, keys in rules:
        if any(k in f for k in keys):
            return label
    for label, keys in rules:
        if any(k in head for k in keys):
            return label
    return "Inny dokument"


PHASES = {
    "Studium wykonalności": "Planowanie", "Uchwała / WPF": "Planowanie", "Opis inwestycji": "Planowanie",
    "PFU": "Przygotowanie", "OPZ": "Przygotowanie", "STWiORB": "Przygotowanie", "Przedmiar / kosztorys": "Przygotowanie",
    "SWZ": "Postępowanie zakupowe", "Ogłoszenie o zamówieniu": "Postępowanie zakupowe", "Ogłoszenie o wyniku postępowania": "Postępowanie zakupowe",
    "Orzeczenie KIO": "Postępowanie zakupowe", "PPU / wzór umowy": "Zawarcie umowy", "Umowa": "Zawarcie umowy",
    "Aneks do umowy": "Realizacja", "Ogłoszenie o zmianie umowy": "Realizacja", "Protokół konieczności": "Realizacja",
    "Protokół odbioru": "Próby, rozruch i odbiór", "Ogłoszenie o wykonaniu umowy": "Zamknięcie i gwarancja",
    "Wystąpienie pokontrolne / NIK": "Materiały zewnętrzne",
}
