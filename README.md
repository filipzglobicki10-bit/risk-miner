# Risk Miner - inteligentna baza doświadczeń inwestycji publicznych

**HackNation 2026 · wyzwanie Ministerstwa Funduszy i Polityki Regionalnej (Departament PPP)**

Risk Miner automatycznie buduje z rozproszonych źródeł (plik organizatora, BZP/e-Zamówienia, TED, dokumenty
PDF/DOCX/XLSX, strony BIP/NIK/KIO) **ustrukturyzowaną bazę przypadków** inwestycji, wykrywa **udokumentowane
zdarzenia ryzyka** wg katalogu eksperckiego, przekazuje je **do weryfikacji eksperta**, a dla **nowej inwestycji**
odpowiada na pytanie, które naprawdę interesuje instytucję: *jak skończyły się podobne umowy i co trzeba zapisać
w tej umowie, żeby nie skończyła się tak samo*. Pilotaż: sektor wodociągowo-kanalizacyjny.

## Jak uruchomić (dla jury, 3 minuty)

Potrzebny jest tylko **Python 3.9 lub nowszy** (bez instalowania bibliotek).
Nie masz Pythona? Windows: [python.org/downloads](https://www.python.org/downloads/) — przy instalacji
zaznacz „Add python.exe to PATH”. macOS: przy pierwszym poleceniu `python3` system sam zaproponuje instalację.

**1. Pobierz projekt** — zielony przycisk **Code → Download ZIP**, potem rozpakuj
(albo `git clone https://github.com/filipzglobicki10-bit/risk-miner.git`).

**2. Uruchom**

| System | Co zrobić |
|---|---|
| **Windows** | w rozpakowanym folderze kliknij dwa razy **`Uruchom Risk Miner.bat`** |
| **macOS / Linux** | otwórz Terminal, przejdź do folderu projektu i wpisz `python3 app.py --open` |

Przeglądarka otworzy się sama na **http://127.0.0.1:8080**. Okna terminala nie zamykaj, dopóki pracujesz.

> macOS: `Risk Miner.app` i `Uruchom Risk Miner.command` działają po `git clone`. Po pobraniu ZIP-a
> macOS blokuje programy z internetu, dlatego najpewniejsze jest `python3 app.py --open`.

**3. Pokaż dane** — na ekranie **Start** kliknij **„Demo na prawdziwych danych BZP (22 projekty, offline)”**.
Po ok. 5 s pojawi się wykres 22 umów, mapa i liczby. Wersja „BZP na żywo” robi to samo, pobierając ogłoszenia z API.

**4. Przeanalizuj nową inwestycję** — **Analizuj nową inwestycję → „wstaw przykładowy opis”** → dołącz plik
`samples/projekt_umowy_przyklad.txt` → **Analizuj**. Wynik eksportujesz przyciskami JSON / CSV / karta ryzyka.

## Spis treści

- [Jak uruchomić (dla jury, 3 minuty)](#jak-uruchomić-dla-jury-3-minuty)
- [Co wyróżnia to rozwiązanie](#co-wyróżnia-to-rozwiązanie)
- [Szybki start (1 minuta)](#szybki-start-1-minuta)
  - [Źródło BZP](#źródło-bzp)
- [Co robi — mapa wymagań wyzwania](#co-robi--mapa-wymagań-wyzwania)
- [Architektura w skrócie](#architektura-w-skrócie)
- [Konfiguracja (`config.json`)](#konfiguracja-configjson)
- [Testy](#testy)
- [Licencje](#licencje)
- [Znane ograniczenia](#znane-ograniczenia)

## Co wyróżnia to rozwiązanie

1. **Sprawdzone na prawdziwym API, nie na założeniach.** Zbadaliśmy faktyczne zachowanie API BZP: filtry
   `OrganizationId`, `TenderId`, `CpvCode` i NIP są **ignorowane** (zwracają cały biuletyn), działają `NoticeType`,
   `NoticeNumber`, daty i `OrganizationName`; typ `ContractModificationNotice` daje HTTP 400. Strategia wyszukiwania
   jest zbudowana na tym, co działa, a łączenie ogłoszeń w postępowanie odbywa się lokalnie po `tenderId`.
   W repozytorium jest kopia **198 prawdziwych ogłoszeń** dla 22 projektów — demo i testy działają bez sieci.
2. **Czyta formularz BZP jak ekspert, nie jak wyszukiwarka słów.** Numerowane pola (`5.4.3) Podstawa prawna zmiany`,
   `5.4.4) Przyczyny`, `5.2) Termin wykonania umowy`…), części zamówienia, stopki. Każda zmiana umowy to osobny rekord:
   podstawa z art. 455 Pzp i jej znaczenie, przyczyna sklasyfikowana do katalogu ryzyk, wartość. Rekord „część 1”
   liczony tylko dla tej części.
3. **Prognoza referencyjna (P50/P80/P90) zamiast „średniej z podobnych”.** Klasa referencyjna = umowy z bazy
   z wynikiem realizacji; waga = podobieństwo²; P80 z przedziałem bootstrap i efektywną liczebnością próby.
   Dwa etapy: *koszt końcowy względem szacunku inwestora* i *rezerwa od ceny umowy po przetargu*. Na 22 prawdziwych
   umowach: ceny umów wyszły poniżej szacunku w 13 z 14 przypadków (mediana −26%), ale po podpisaniu rozliczenie
   wzrosło w 16 z 22 umów (mediana +6,6%, P80 +23,8%), a 18 z 22 skończyło się po terminie (mediana +27% czasu,
   P80 +69%) — więc oszczędności przetargowych nie należy zwalniać w całości, a harmonogram trzeba planować na P80.
4. **Rejestr ryzyk z wyceną.** Prawdopodobieństwo (k z n podobnych umów), skutek (mediana kosztu zmian w % umowy,
   mediana wydłużenia), wartość oczekiwana w zł dla planowanej inwestycji i podstawy prawne, którymi
   zamawiający musieli potem zmieniać umowy.
5. **Audyt klauzul projektu umowy na tle historii.** Wgraj PPU/SWZ — system sprawdza 14 klauzul (waloryzacja
   z art. 439 Pzp, limit kar z art. 436 pkt 3, płatności częściowe z art. 447, katalog zmian z art. 455 ust. 1 pkt 1,
   warunki gruntowe, pogoda z obiektywnym kryterium…), pokazuje cytat ze strony, a przy każdej luce podaje,
   jak często odpowiadające jej ryzyko zmaterializowało się w podobnych umowach.
6. **„Czy zdążysz przed końcem dofinansowania?”** Z opisu odczytuje planowany start przetargu i termin z umowy
   o dofinansowanie, a potem przepuszcza inwestycję przez ścieżki 22 prawdziwych umów (czas przetargu z BZP +
   realizacja z ich faktycznym wydłużeniem). Dla przykładu: „na papierze” koniec w kwietniu 2028, czyli przed terminem,
   ale w 16 z 22 przebiegów — po 30.06.2028 (ok. 74% ryzyka utraty dofinansowania); system podaje najpóźniejszą
   bezpieczną datę ogłoszenia przetargu i maksymalny czas realizacji, który daje 80% szans.
7. **Odpowiedź w 30 sekund + historia projektu.** Na górze analizy: kafelki (dofinansowanie, budżet, rezerwa,
   termin, największe ryzyko, umowa) i lista „co zrobić przed ogłoszeniem przetargu”; przy każdym projekcie —
   jego przebieg opowiedziany w 3 zdaniach, złożony z ogłoszeń BZP bez modelu językowego.
8. **Biblioteka zmian umów.** Wszystkie 40 zmian umów z BZP w jednym miejscu, z przyczyną, kategorią ryzyka,
   podstawą z art. 455 Pzp, kosztem i linkiem do ogłoszenia. Wpisujesz „grunt”, „służebność” albo „Wody Polskie”
   i widzisz, jak to się skończyło u innych. Pulpit startowy pokazuje wszystkie umowy na jednym wykresie
   „plan → rzeczywistość” (koszt × czas, klik otwiera projekt).
9. **Mapa inwestycji.** Projekty na mapie Polski (kolor = jak skończyły się koszt i termin, wielkość = wartość umowy),
   z rankingiem najdłuższych opóźnień i największych przekroczeń; klik otwiera projekt.
10. **Wykrywa błędy w danych wejściowych.** Np. numer ogłoszenia z rekordu nie istnieje w BZP (RM-2026-022),
   dwa sprzeczne ogłoszenia o wykonaniu tej samej umowy (RM-2026-002), szacunek równy co do grosza cenie
   umowy (pole wypełnione wartością umowy — pomijany w statystyce).

## Szybki start (1 minuta)

Wymagany tylko **Python 3.9+** — aplikacja nie ma obowiązkowych zależności (sama biblioteka standardowa).

**Bez terminala (kliknij dwa razy w folderze projektu):**
- **Windows:** `Uruchom Risk Miner.bat`
- **macOS:** `Risk Miner.app` (bez okna terminala) lub `Uruchom Risk Miner.command`

Aplikacja sama uruchomi serwer i otworzy przeglądarkę na **http://127.0.0.1:8080**.

**Z terminala:**
```bash
./scripts/run.sh         # macOS / Linux   (Windows: scripts\run.bat)
# lub:  python3 app.py --open
```

Otwórz **http://127.0.0.1:8080** → Pulpit → **„Demo na prawdziwych danych BZP (22 projekty, offline)”**.
W ~5 sekund system wczyta rekordy organizatora i kopię ogłoszeń BZP, powiąże je, wyliczy koszty i terminy,
odczyta zmiany umów i pokaże „Czego uczy baza”. Przycisk „Pakiet organizatora — BZP na żywo” robi to samo
z pobieraniem ogłoszeń z API. Potem: **Analiza nowej inwestycji** → „wstaw przykładowy opis” → dołącz
`samples/projekt_umowy_przyklad.txt` → Analizuj.

Docker (z OCR skanów):  `docker compose -f deploy/docker-compose.yml up --build`  → http://localhost:8080

| Opcjonalnie | Po co |
|---|---|
| `pip install pypdf` (robi to skrypt uruchomieniowy) | odczyt warstwy tekstowej PDF |
| `tesseract` + `pdftoppm` w PATH (w Dockerze są) | OCR skanów PDF i zdjęć |
| klucz LLM w `RISKMINER_LLM_API_KEY` + `config.json` | ekstrakcja zdarzeń modelem językowym, narracja analizy |

**Wymagania sprzętowe:** dowolny laptop (≈60 MB RAM, SQLite w pliku `data/riskminer.sqlite`). Bez GPU.

### Co jest w folderze

```
risk-miner/
├── Risk Miner.app              ← macOS: kliknij dwa razy
├── Uruchom Risk Miner.command  ← macOS (z oknem terminala)
├── Uruchom Risk Miner.bat      ← Windows: kliknij dwa razy
├── app.py                      ← start z terminala: python3 app.py --open
├── config.example.json         ← wzór konfiguracji (kopiowany do config.json przy 1. starcie)
├── riskminer/                  ← logika: BZP, łączenie, ekstrakcja, prognoza, audyt klauzul, serwer
├── static/                     ← interfejs (HTML, CSS, JS, fonty)
├── samples/                    ← dane organizatora: 22 projekty (.xlsx), kopia BZP, przykładowy opis i umowa
├── tests/                      ← testy jednostkowe i test całego przepływu z atrapą BZP
├── docs/                       ← opis rozwiązania, architektura, raport z testów, scenariusz demo, system wyglądu
├── scripts/                    ← run.sh / run.bat — uruchomienie z terminala
├── deploy/                     ← Dockerfile i docker-compose.yml (wersja z OCR)
└── data/                       ← baza SQLite i cache (tworzone przy starcie, poza gitem)
```

### Źródło BZP
Najpierw zawsze API na żywo: kopia organizatora **https://bzp.cytr.us** (ten sam interfejs co API e-Zamówień),
z przejściem na `ezamowienia.gov.pl` (limit 25 zapytań/min — klient sam zwalnia). Gdy API nie odpowiada,
aplikacja **sama przełącza się na kopię offline** (wgraną w *Ustawieniach* albo wbudowaną
`samples/bzp_kopia_22_projekty.json`) i mówi o tym w dzienniku. Odpowiedzi są zapisywane w `data/cache/`
(powtarzalność, ponowne uruchomienie bez ręcznego wpisywania).

---

## Co robi — mapa wymagań wyzwania

| Wymaganie | Jak zrealizowane | Gdzie |
|---|---|---|
| Automatyczne zasilanie bazy z pliku .xls i źródeł publicznych | import XLSX/CSV (rozpoznanie nagłówków) → zadanie w tle: BZP (zamówienie, wynik, zmiany, wykonanie umowy), TED, dokumenty, URL (BIP/NIK/KIO) | `pipeline.py`, `bzp.py`, `ted.py` |
| Łączenie po identyfikatorach | numer ogłoszenia BZP, `tenderId` (OCDS), NIP (z walidacją sumy kontrolnej), nr KPO/CST — normalizacja formatów | `util.py`, `pipeline.py` |
| Dopasowanie bez klucza + podstawa i pewność | NIP zamawiającego + podobieństwo przedmiotu + miejscowość + okno dat; każde powiązanie ma listę przesłanek i % pewności; < 95% → kolejka eksperta | `pipeline._score_candidate` |
| Model danych: projekt → postępowania → ogłoszenia → umowy → zmiany, zdarzenia, koszty/terminy, dokumenty, źródła | 18 tabel SQLite; umowy i zmiany **per część zamówienia**; każdy rekord ma źródło (id, link, data pobrania, strona/cytat) | `db.py` |
| Odczyt ogłoszeń BZP | parser numerowanych pól formularza (części, stopki, zmiany umowy 5.4.x / 5.x), mapowanie podstaw art. 455 Pzp; ponowne ogłoszenia o wykonaniu tej samej umowy — obowiązuje najnowsze, rozbieżności do „jakości danych” | `bzp.parse_form`, `bzp.extract_structured`, `pipeline._reconcile` |
| Ekstrakcja zdarzeń ryzyka wg katalogu, otwarty katalog | reguły R01–R15 + 15 typów zdarzeń (E01–E15) z materiału eksperckiego; skutki (koszt, dni), przyczyny, działania; LLM (opcjonalnie) proponuje nowe kategorie | `rules.py`, `knowledge.py`, `llm.py` |
| Człowiek w procesie | każde zdarzenie/powiązanie/fakt: zatwierdź / popraw / odrzuć + komentarz; pełna historia; decyzje korygują pewność reguł (uczenie bez kodu) | `review.py`, Panel eksperta |
| Panel eksperta: edycja wszystkiego | katalog ryzyk, typy zdarzeń, podsektory, lista kontrolna, opis sektora, klasyfikacja projektu, fakty, „wzorcowe” | Wiedza ekspercka |
| Analiza nowej inwestycji | opis w języku naturalnym i/lub dokumenty → grupa porównawcza (TF-IDF + cechy strukturalne, wyjaśnienie wkładu cech) → **prognoza referencyjna P50/P80/P90** (koszt od szacunku i od ceny umowy, czas) → **rejestr ryzyk z wyceną** → **audyt klauzul PPU/SWZ** → flagi, rekomendacje, propozycje zapisów, braki z listy kontrolnej, karta do druku | `analysis.py`, `forecast.py`, `clauses.py`, `similarity.py` |
| Odróżnienie danych / obliczeń / wniosków | wynik w trzech warstwach: **A. Dane źródłowe**, **B. Obliczenia**, **C. Wnioski** (+ oznaczona narracja LLM) | UI „Analiza nowej inwestycji” |
| Identyfikowalność | źródło, URL, data pobrania, strona i cytat przy każdym fakcie i zdarzeniu; zdarzenia wyliczone cytują oba fakty | wszędzie |
| Wyniki jako rekordy + eksport | wszystkie tabele JSON/CSV, pełny przypadek (JSON), analiza (JSON/CSV), raport z testu łączenia | Raporty i eksport |
| Ponowna analiza po nowych dokumentach | potwierdzenia, sprzeczności (np. inna data wykonania), nowe zdarzenia, nowe numery BZP → propozycje powiązań | `pipeline.add_document` |
| Moduł monitorowania (atut) | dla projektów w toku: nowe ogłoszenia (wynik, zmiana umowy, wykonanie) → „istotna zmiana”, ponowne wyliczenie; harmonogram co N min | `monitor.py` |
| Model w konfiguracji, bez uzależnienia od dostawcy | `config.json` → `llm.provider/model/base_url`; OpenAI-compatible (OpenAI, Ollama, vLLM, Mistral) lub Anthropic; klucz tylko w zmiennej środowiskowej; miejsce przetwarzania danych w konfiguracji | `config.py`, `llm.py` |
| Skalowalność | brak ręcznego importu powiązań; nowe sektory = nowe wpisy wiedzy eksperckiej (bez kodu); cache i limit zapytań; SQLite → PostgreSQL bez zmiany modelu | |

**Czego nie ma (świadomie):** podpisanych umów zwykle nie ma w źródłach otwartych — system rozpoznaje brak
(„nie ma w paczce” ≠ „nie istnieje”) i używa PPU/SWU jako źródła zastępczego, gdy ekspert je doda.

## Architektura w skrócie

```
static/ (UI: vanilla JS)  ──REST──▶  riskminer/server.py (http.server)
                                         │
     ┌──────────────┬───────────────┬────┴──────────┬───────────────┬──────────────┐
  pipeline.py    rules.py        analysis.py      review.py       monitor.py     exporter.py
  (import,       (katalog →      (podobieństwo,   (decyzje,       (nowe          (JSON/CSV,
   BZP/TED,       sygnały,        prognoza,        historia,       ogłoszenia)    raport)
   dokumenty)     uczenie)        flagi)           uczenie)
     │               │                │
  bzp.py ted.py   knowledge.py    similarity.py   llm.py (opcjonalny)   extract.py (PDF/DOCX/XLSX/OCR)
     └───────────────────────────── db.py (SQLite) ─────────────────────────────┘
```

Szczegóły: [`docs/ARCHITEKTURA.md`](docs/ARCHITEKTURA.md) · opis rozwiązania: [`docs/OPIS_ROZWIAZANIA.md`](docs/OPIS_ROZWIAZANIA.md) ·
scenariusz demo: [`docs/SCENARIUSZ_DEMO.md`](docs/SCENARIUSZ_DEMO.md) · testy: [`docs/RAPORT_Z_TESTOW.md`](docs/RAPORT_Z_TESTOW.md)

## Konfiguracja (`config.json`)

| Klucz | Znaczenie |
|---|---|
| `bzp.base_url`, `bzp.fallback_urls` | adres API BZP i zapasowe |
| `bzp.requests_per_minute` | limit (0 = bez; dla ezamowienia.gov.pl automatycznie 25) |
| `bzp.related_notice_types` | typy ogłoszeń wyszukiwane dla postępowania |
| `ted.enabled`, `ted.query_template` | wyszukiwanie w TED (API v3, bez klucza) |
| `llm.provider` / `model` / `base_url` / `api_key_env` / `data_location` | model językowy — zmiana bez kodu |
| `monitor.interval_minutes` | cykliczny monitoring (0 = wyłączony) |
| `analysis.weights`, `top_k`, `min_similarity` | wagi cech podobieństwa |
| `link_auto_accept_confidence` | próg auto-akceptacji powiązań po identyfikatorze |

Zmienne środowiskowe: `RISKMINER_PORT`, `RISKMINER_HOST`, `RISKMINER_BZP_URL`, `RISKMINER_LLM_PROVIDER`,
`RISKMINER_LLM_MODEL`, `RISKMINER_LLM_BASE_URL`, `RISKMINER_LLM_API_KEY`, `RISKMINER_CONFIG`.

## Testy

```bash
python3 tests/test_units.py    # parser BZP, kwantyle ważone, audyt klauzul, województwa, bezpieczeństwo URL (14 testów)
python3 tests/test_e2e.py      # pełny scenariusz przez REST API: atrapa BZP z PRAWDZIWYMI ogłoszeniami
                               # i zachowaniem prawdziwego API (ignorowane filtry, stronicowanie, HTTP 400)
python3 tests/mock_bzp.py      # sama atrapa BZP na :8765 (do pokazów offline)
```

## Licencje

Kod: MIT. Zależności obowiązkowe: brak (Python stdlib, licencja PSF). Opcjonalne: pypdf (BSD-3-Clause),
Tesseract OCR (Apache-2.0), Poppler (GPL-2.0, wywoływany jako osobny program). Dane: BZP/e-Zamówienia (UZP —
informacja publiczna, ponowne wykorzystanie), TED (Urząd Publikacji UE — ponowne wykorzystanie na zasadach decyzji Komisji 2011/833/UE), materiały MFiPR — wyłącznie
na potrzeby wydarzenia.

## Znane ograniczenia

- Klasa referencyjna to 22 umowy — efektywna liczebność próby (n_eff) i przedział bootstrap dla P80 są pokazywane
  przy każdej prognozie; przy n_eff < 6 prognoza jest oznaczona jako niskiej pewności. Baza rośnie z każdym
  zaimportowanym projektem — metoda się nie zmienia.
- Wartość szacunkowa z ogłoszenia o wyniku (pole 4.3) bywa wypełniana ceną umowy — takie przypadki (równość
  co do grosza) są pomijane w statystyce przetargowej i wypisane w metodzie.
- Audyt klauzul działa na wzorcach (wyrażenia regularne na tekście bez polskich znaków) — wskazuje cytat i stronę,
  ale nie zastępuje opinii prawnej; wzorce i wzorcowe zapisy są w `clauses.py`.
- Przy KPO/CST (bez numeru BZP) dopasowanie postępowania jest przybliżone i czeka na decyzję eksperta; do tego czasu
  takie umowy ważą w prognozie 4× mniej.
- Reguły słownikowe dają fałszywe alarmy — dlatego trafiają do eksperta, a jego decyzje obniżają pewność reguły.
