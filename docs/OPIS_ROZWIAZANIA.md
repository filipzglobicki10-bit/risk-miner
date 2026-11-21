# Risk Miner — opis rozwiązania

**Tytuł:** Risk Miner — cyfrowa pamięć instytucjonalna inwestycji publicznych
**Wyzwanie:** MFiPR, Departament PPP — „Risk Miner: inteligentna baza doświadczeń inwestycji publicznych”

## Problem

Wiedza o tym, co faktycznie wydarzyło się w zrealizowanych inwestycjach — opóźnienia, aneksy, roboty dodatkowe,
odwołania, kary — jest rozproszona między BZP, TED, BIP-ami, raportami NIK i aktami poszczególnych jednostek.
Osoba przygotowująca nową inwestycję nie ma prostego sposobu, by zobaczyć, jak przebiegały podobne projekty,
ile kosztowały naprawdę, co je opóźniło i jakie zapisy umowne pomogły.

## Rozwiązanie

Aplikacja webowa, która:

1. **Buduje bazę przypadków automatycznie.** Po wgraniu pliku z rekordami (np. 22 projekty wod-kan od organizatora)
   sama wyszukuje w BZP ogłoszenie o zamówieniu, wynik, zmiany i wykonanie umowy; łączy je po identyfikatorach
   (numer ogłoszenia, tenderId, NIP), a gdy klucza brak — po zamawiającym, przedmiocie, miejscu i datach, pokazując
   podstawę i % pewności. Dokumenty (PDF, DOCX, XLSX, CSV, strony BIP/NIK/KIO) są czytane stronami.
2. **Wyciąga udokumentowane zdarzenia ryzyka** zgodnie z katalogiem eksperckim MFiPR (R01–R15) i typami zdarzeń
   (zmiana terminu, wynagrodzenia, roboty dodatkowe, kary, unieważnienie, KIO, NIK…), z przyczyną, skutkiem
   (dni, zł), działaniami zaradczymi i cytatem ze wskazaniem strony. Odchylenia kosztu i czasu są wyliczane
   z ogłoszeń o wyniku i wykonaniu umowy.
3. **Stawia eksperta w centrum.** Każde zdarzenie, fakt i niepewne powiązanie czeka na decyzję: zatwierdź, popraw,
   odrzuć. Decyzje mają historię i uczą system (pewność reguł, odrzucone fragmenty nie wracają). Katalog ryzyk,
   typy zdarzeń, podsektory i lista kontrolna są edytowalne bez programisty; LLM może proponować nowe kategorie,
   ale dodaje je ekspert.
4. **Wspiera przygotowanie nowej inwestycji.** Użytkownik opisuje projekt zwykłym językiem lub wgrywa koncepcję/PFU
   i projekt umowy. System dobiera najbardziej zbliżone inwestycje i wyjaśnia, które cechy przesądziły o podobieństwie,
   a potem:
   - **prognoza referencyjna P50/P80/P90** — jak skończyły się podobne umowy (wypłata i data wykonania z BZP), ważone
     podobieństwem; osobno koszt końcowy względem szacunku inwestora i rezerwa od ceny umowy po przetargu, czas
     realizacji; z efektywną liczebnością próby i przedziałem bootstrap,
   - **rejestr ryzyk z wyceną** — prawdopodobieństwo, mediana skutku, wartość oczekiwana w zł i podstawy art. 455 Pzp,
     którymi zmieniano umowy,
   - **audyt klauzul PPU/SWZ** — 14 klauzul (m.in. wymogi art. 439, 436 pkt 3, 447 Pzp), cytat ze strony, a przy luce
     — jak często odpowiadające ryzyko wystąpiło w podobnych umowach; propozycja zapisu,
   - **ryzyko utraty dofinansowania** — prawdopodobieństwo, że inwestycja nie zdąży przed terminem z umowy
     o dofinansowanie (ścieżki prawdziwych umów: czas przetargu + realizacja z faktycznym wydłużeniem), najpóźniejsza
     bezpieczna data ogłoszenia przetargu,
   - „Odpowiedź w 30 sekund” (kafelki i lista działań), czerwone flagi, zagadnienia do sprawdzenia; karta ryzyka do druku.
   Wynik jest rozdzielony na **dane źródłowe**, **obliczenia** i **wnioski**.
5. **Monitoruje trwające inwestycje.** Nowe ogłoszenie (wynik, zmiana umowy, wykonanie) lub nowy dokument →
   ponowna analiza: potwierdzenia, sprzeczności (np. inna data wykonania), nowe zdarzenia.

## Czego nauczyła nas baza (22 prawdziwe umowy z BZP)

- Ceny umów wyszły poniżej szacunku inwestora w 13 z 14 przypadków (mediana −26%).
- Po podpisaniu rozliczenie wzrosło w 16 z 22 umów: mediana +6,6%, P80 +23,8% (przedział bootstrap 8,7–32,7%).
- 18 z 22 umów zakończono po terminie umownym: mediana +27% czasu, P80 +69%.
- Połowa z 40 zmian umów szła przez zmiany przewidziane w umowie (art. 455 ust. 1 pkt 1); reszta — przez podstawy
  z limitami (zmiana o niewielkiej wartości 25%, okoliczności nieprzewidywalne 20%, roboty dodatkowe 5%).
- Najczęstsze przyczyny zmian: harmonogram i warunki atmosferyczne (R06, 9 z 22), zmiany i roboty dodatkowe
  (R07, 9 z 22), kolizje i prawa do terenu (R03, 3 z 22 — najwyższy skutek, mediana +21,7% wartości umowy),
  warunki gruntowe (R02, 3 z 22).
- Wykryte błędy danych: numer ogłoszenia z rekordu RM-2026-022 nie istnieje w BZP; dla RM-2026-002 opublikowano
  dwa sprzeczne ogłoszenia o wykonaniu tej samej umowy; w 3 ogłoszeniach o wyniku „wartość zamówienia” równa
  co do grosza cenie umowy netto.

Wniosek dla instytucji: oszczędności przetargowych nie należy zwalniać w całości, a harmonogram planować na P80.

## Główny scenariusz użytkownika

1. Analityk wgrywa plik projektów → pasek postępu i dziennik pobierania z BZP.
2. W bazie przypadków otwiera projekt: drzewo projekt → postępowanie → ogłoszenia → umowa → zmiany; każdy element
   z linkiem do BZP i datą pobrania; KPI: wartość umowy, wypłata, odchylenie kosztu, opóźnienie.
3. Ekspert w panelu zatwierdza/odrzuca zdarzenia i potwierdza niepewne dopasowania (np. projekt KPO bez numeru BZP).
4. Planista wpisuje opis nowej kanalizacji (6,5 km, zaprojektuj i wybuduj, 14 mies., grunty prywatne) i dołącza projekt
   umowy → otrzymuje grupę porównawczą, prognozę P50/P80/P90 (czas P80 ≈ 24 mies. zamiast 14), rejestr ryzyk z wyceną,
   audyt klauzul (2 niespełnione wymogi ustawowe: waloryzacja wyłączona przy umowie na 14 mies., kary bez łącznego
   limitu; luki: warunki gruntowe, pogoda bez obiektywnego kryterium) → drukuje kartę ryzyka / eksportuje.

## Co działa, a co zaprojektowano

| Element | Stan |
|---|---|
| Import XLSX/CSV, normalizacja i walidacja identyfikatorów | działa |
| Klient API BZP (kopia organizatora + oficjalne, limit, cache, paginacja, tryb offline) | działa; zachowanie API sprawdzone na bzp.cytr.us (działające i ignorowane filtry); kopia 198 prawdziwych ogłoszeń w `samples/` |
| Łączenie po identyfikatorach i przybliżone z pewnością i przesłankami | działa |
| Parser formularzy BZP (numerowane pola, części, zmiany umowy z podstawą i przyczyną, wynik, wykonanie) | działa na wszystkich 198 ogłoszeniach kopii; wyniki sprawdzone ręcznie dla wybranych projektów (raport z testów) |
| Prognoza referencyjna P50/P80/P90, rejestr ryzyk z wyceną, audyt klauzul PPU/SWZ | działa |
| TED (API v3), pobieranie URL (BIP/NIK/KIO) | działa (TED: wyszukiwanie po NIP) |
| Ekstrakcja zdarzeń: reguły, wyliczenia, LLM z weryfikacją cytatu | działa (LLM po podaniu klucza) |
| Panel eksperta, historia, uczenie reguł, edycja wiedzy | działa |
| Analiza nowej inwestycji z wyjaśnieniem i prognozą | działa |
| Monitoring + harmonogram | działa |
| Eksport JSON/CSV, raport z testu łączenia | działa |
| OCR skanów | działa, gdy dostępny Tesseract (Docker) |
| Integracja KPOŚK/AKPOŚK, KIO (wyszukiwarka), BK2021 | zaprojektowane: źródło jako adapter jak `ted.py`; obecnie przez dodanie URL/dokumentu |
| Użytkownicy i role | zaprojektowane: nazwa eksperta w nagłówku żądań trafia do historii; SSO/role — kolejny etap |

## Dlaczego tak

- **Zero zależności** → uruchomienie w każdej jednostce bez instalacji; łatwy audyt bezpieczeństwa.
- **Reguły + statystyka jako fundament, LLM jako dodatek** → wyniki sprawdzalne, powtarzalne i tanie;
  model nigdy nie zapisuje niczego bez cytatu i bez eksperta.
- **Wiedza ekspercka jako dane** → nowy sektor (drogi, szkoły, PPP) = nowy katalog i lista kontrolna, bez kodu.
