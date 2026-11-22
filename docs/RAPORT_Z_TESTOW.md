# Raport z testów

## 1. Zachowanie prawdziwego API BZP (sprawdzone ręcznie na https://bzp.cytr.us)

Zanim powstała strategia wyszukiwania, sprawdziliśmy, które parametry `GET /mo-board/api/v1/notice` naprawdę działają:

| Parametr | Wynik |
|---|---|
| `NoticeType` | działa (wymagany); `ContractModificationNotice` → **HTTP 400**; poprawne typy powiązane: `TenderResultNotice`, `AgreementUpdateNotice`, `ContractPerformingNotice`, `NoticeUpdateNotice` |
| `NoticeNumber`, `PublicationDateFrom/To` | działają |
| `OrganizationName` | działa — fragment nazwy, bez względu na wielkość liter |
| `OrganizationId`, `OrganizationNationalId` (NIP), `TenderId`, `CpvCode`, `BzpNumber`, `PageNumber` | **ignorowane** — API zwraca wtedy cały biuletyn |
| `PageSize` | domyślnie 10, maksymalnie 500 |
| stronicowanie | `SearchAfter=<objectId>` (wyłącznie), sortowanie od najnowszych |

Wniosek: powiązane ogłoszenia pobieramy po nazwie zamawiającego i oknie dat, a łączymy lokalnie po `tenderId`
i numerze ogłoszenia w treści. Rozwiązanie oparte na filtrze `TenderId` lub NIP dostałoby „cały BZP” i błędne
powiązania.

## 2. Testy automatyczne

```bash
python3 tests/test_units.py   # 11 testów: parser formularza, kwantyle ważone, audyt klauzul
python3 tests/test_e2e.py     # scenariusz przez REST API
```

`tests/mock_bzp.py` odtwarza **zachowanie prawdziwego API** (powyższa tabela) na **prawdziwej kopii 198 ogłoszeń**
(`samples/bzp_kopia_22_projekty.json`, pobrane 2026-11-21; e-maile i telefony usunięte). Test sprawdza też, że
aplikacja nigdy nie wysyła ignorowanych filtrów ani niepoprawnego typu ogłoszenia.

| # | Sprawdzenie (e2e) | Wynik |
|---|---|---|
| 1 | Import 22 rekordów, wzbogacenie w tle: 22 postępowania, 83 ogłoszenia | OK |
| 2 | RM-2026-003 Steklin: umowa 2 131 590 zł, wypłata 2 990 000 zł (+40,3%), termin 2025-08-18, wykonanie 2026-05-22 (+277 dni), 3 zmiany umowy | OK |
| 3 | RM-2026-011 Sanok: wykonanie 6 dni przed terminem | OK |
| 4 | RM-2026-008 (rekord „część 1” postępowania 4-częściowego): liczone tylko dla części 1 (1 952 120,53 → 2 375 309,26 zł); zmiana z części 3 wyłączona | OK |
| 5 | Przyczyny zmian z pól formularza: grunt skalny → R02 (Sanok), postępowanie Wód Polskich → R04 (Steklin) | OK |
| 6 | Jakość danych: RM-2026-022 — numer z rekordu nie istnieje w BZP; RM-2026-002 — dwa ogłoszenia o wykonaniu tej samej umowy (przyjęte nowsze, 1 zmiana, nie 2) | OK |
| 7 | Wnioski z bazy: 22 umowy w klasie referencyjnej, ≥ 15 rozliczonych powyżej wartości umowy, P80 > P50, rejestr ryzyk, najczęstsza podstawa zmian art. 455 ust. 1 pkt 1 | OK |
| 8 | KPO bez numeru BZP: kandydaci po NIP i przedmiocie, status „do weryfikacji” | OK |
| 9 | Każde zdarzenie ma cytat i źródło; pełny cykl ogłoszeń (zamówienie, wynik, zmiana, wykonanie) | OK |
| 10 | Dokument (aneks): typ rozpoznany, ≥ 2 zdarzenia, sprzeczność daty wykonania | OK |
| 11 | Decyzje eksperta w historii z nazwą eksperta; nowa kategoria ryzyka przez API | OK |
| 12 | Analiza nowej inwestycji + projekt umowy: okres 14 mies. odczytany, P80 kosztu i czasu, rezerwa od ceny umowy, przedział bootstrap, rejestr ryzyk | OK |
| 13 | Audyt klauzul: waloryzacja **wyłączona** (wymóg art. 439 Pzp), kary bez łącznego limitu (art. 436 pkt 3), pogoda bez kryterium — „niepełna”, warunki gruntowe — „brak”, płatności częściowe — „jest”; flaga „audyt klauzul” | OK |
| 14 | Eksport, raport łączenia, ponowne wzbogacenie i monitoring nie dublują ogłoszeń | OK |
| 15 | Ogłoszenie innej umowy tego samego zamawiającego (bez wspólnego tenderId): powiązanie „do weryfikacji”, jego zmiany umowy, zdarzenia i terminy nie wchodzą do bazy przed decyzją eksperta (RM-2026-018: 2026/BZP 00342646/01 dotyczy umowy „Zduny, ul. Masłowskiego”) | OK |
| 16 | Ogłoszenia w formacie BZP na żywo (`<h3>etykieta</h3> wartość`): przyczyna i opis zmiany odczytane, ta sama zmiana z ogłoszenia o zmianie umowy i o wykonaniu liczona raz | OK |

Wynik: `Ran 1 test … OK` (e2e, ~2,5 s) i `Ran 11 tests … OK` (jednostkowe). Sprawdzono na Pythonie 3.13 (Linux); kod wymaga Pythona 3.9+.

## 3. Wyniki dla 22 projektów pakietu (prawdziwe ogłoszenia BZP)

| Rekord | Identyfikator | Status | Ogł. | Wartość umowy | Wypłacono | Koszt | Termin | Zmiany |
|---|---|---|---|---|---|---|---|---|
| RM-2026-001 | Ogłoszenie BZP | wzbogacony | 3 | 2 107 348 zł | 2 246 178 zł | +6,6% | +77 dni | 4 |
| RM-2026-002 | Projekt KPO | do weryfikacji | 4 | 5 350 783 zł | 5 350 783 zł | +0,0% | +27 dni | 1 |
| RM-2026-003 | Ogłoszenie BZP | wzbogacony | 5 | 2 131 590 zł | 2 990 000 zł | +40,3% | +277 dni | 3 |
| RM-2026-004 | Ogłoszenie BZP | wzbogacony | 3 | 3 918 954 zł | 4 134 920 zł | +5,5% | +98 dni | 3 |
| RM-2026-005 | Projekt KPO | do weryfikacji | 3 | 2 936 010 zł | 3 087 492 zł | +5,2% | +36 dni | 1 |
| RM-2026-006 | Ogłoszenie BZP | wzbogacony | 5 | 2 499 110 zł | 2 604 551 zł | +4,2% | +81 dni | 4 |
| RM-2026-007 | Projekt KPO | do weryfikacji | 3 | 1 478 460 zł | 1 468 960 zł | −0,6% | +19 dni | 0 |
| RM-2026-008 | Ogłoszenie BZP (część 1) | wzbogacony | 6 | 1 952 121 zł | 2 375 309 zł | +21,7% | 0 dni | 1 |
| RM-2026-009 | Ogłoszenie BZP (część 2) | wzbogacony | 4 | 1 810 534 zł | 1 881 383 zł | +3,9% | −2 dni | 1 |
| RM-2026-010 | Projekt KPO | do weryfikacji | 4 | 3 348 882 zł | 3 348 882 zł | +0,0% | +45 dni | 1 |
| RM-2026-011 | Ogłoszenie BZP | wzbogacony | 3 | 2 880 536 zł | 3 134 219 zł | +8,8% | −6 dni | 1 |
| RM-2026-012 | Ogłoszenie BZP | wzbogacony | 3 | 3 616 200 zł | 3 650 944 zł | +1,0% | +58 dni | 2 |
| RM-2026-013 | Ogłoszenie BZP | wzbogacony | 3 | 5 991 656 zł | 6 397 551 zł | +6,8% | +31 dni | 2 |
| RM-2026-014 | Ogłoszenie BZP | wzbogacony | 3 | 1 193 100 zł | 1 294 008 zł | +8,5% | +41 dni | 2 |
| RM-2026-015 | Ogłoszenie BZP | wzbogacony | 5 | 3 744 316 zł | 4 703 040 zł | +25,6% | +150 dni | 3 |
| RM-2026-016 | Ogłoszenie BZP | wzbogacony | 3 | 4 879 410 zł | 5 067 267 zł | +3,9% | +31 dni | 2 |
| RM-2026-017 | Projekt KPO | do weryfikacji | 3 | 4 275 776 zł | 5 422 833 zł | +26,8% | +53 dni | 1 |
| RM-2026-018 | Projekt KPO | do weryfikacji | 5 | 3 665 400 zł | 4 194 313 zł | +14,4% | +40 dni | 1 |
| RM-2026-019 | Ogłoszenie BZP | wzbogacony | 3 | 3 154 933 zł | 4 186 736 zł | +32,7% | +395 dni | 3 |
| RM-2026-020 | Projekt KPO | do weryfikacji | 5 | 1 969 611 zł | 1 719 611 zł | −12,7% | +185 dni | 2 |
| RM-2026-021 | Ogłoszenie BZP | wzbogacony | 4 | 5 421 102 zł | 2 979 984 zł | −45,0% | +68 dni | 1 |
| RM-2026-022 | Ogłoszenie BZP — **numer nie istnieje w BZP** | do weryfikacji | 3 | 444 898 zł | 444 898 zł | +0,0% | −11 dni | 0 |

Raport łączenia: **72 połączenia pewne** (po identyfikatorze), **33 niepewne** (do decyzji eksperta: projekty KPO
i RM-2026-022), 0 błędnych. Czas pełnego wzbogacenia 22 projektów z kopii: ok. 3 s.

Uwagi do pojedynczych wyników (sprawdzone w treści ogłoszeń):
- RM-2026-002: w nowszym ogłoszeniu o wykonaniu pole „Wartość zmiany” zawiera wartość całej umowy — system
  przelicza to na przyrost (0 zł) i zapisuje adnotację.
- RM-2026-021: wypłata o 45% niższa od wartości umowy — zdarzenie „możliwe ograniczenie zakresu” (R01) do oceny eksperta.
- RM-2026-008/009: dwa rekordy pakietu to dwie części jednego postępowania; każdy liczony dla swojej części.
- RM-2026-018 i RM-2026-012: wyszukiwanie po zamawiającym znajduje też ogłoszenia innych umów tej samej gminy
  (np. „Zduny, ul. Masłowskiego”, „sieć kanalizacyjna w Smętowie Chmieleńskim”). Bez wspólnego tenderId trafiają do
  eksperta jako niepewne i nie zmieniają kosztów, terminów ani biblioteki zmian, dopóki ich nie zatwierdzi.

## 4. Weryfikacja wizualna

Chrome (1400 px), wszystkie widoki: pulpit z „Czego uczy baza”, projekt z osią czasu (w tym 4 części z wyszarzeniem
spoza zakresu rekordu), analiza z prognozą referencyjną, rejestrem i audytem klauzul — bez błędów konsoli.
