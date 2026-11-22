# Przykładowy eksport danych

Pliki wygenerowane przez Risk Miner na danych organizatora: 22 projekty z `samples/Risk_Miner_dane_projekty.xlsx`,
powiązane automatycznie z 83 prawdziwymi ogłoszeniami BZP (kopia `samples/bzp_kopia_22_projekty.json`),
oraz analiza przykładowej nowej inwestycji (`samples/opis_nowej_inwestycji.txt` + `samples/projekt_umowy_przyklad.txt`).

Pliki CSV mają separator `;` i kodowanie UTF-8 z BOM — otwierają się bezpośrednio w Excelu.
Zdarzenia i niepewne powiązania mają status `proposed`, bo w tym przykładzie nie podjęto jeszcze decyzji eksperta;
po zatwierdzeniu w Panelu eksperta status zmienia się na `approved`, `edited` albo `rejected`.

## Baza przypadków

| Plik | Co zawiera |
|---|---|
| `projects.csv` | 22 projekty: beneficjent, NIP (z walidacją), lokalizacja, podsektor, formuła, stan wzbogacenia |
| `procurements.csv` | postępowania przetargowe powiązane z projektami |
| `notices.csv` | 83 ogłoszenia BZP: typ, numer, data publikacji, link do źródła |
| `contracts.csv` | 26 umów: wartość, data zawarcia, termin, wypłata, data wykonania |
| `contract_changes.csv` | 40 zmian umów: przyczyna, podstawa prawna (art. 455 Pzp), zmiana wartości i terminu, cytat |
| `events.csv` | 80 zdarzeń ryzyka z kategorią, przyczyną, skutkiem, pewnością i cytatem źródłowym |
| `links.csv` | wszystkie powiązania rekordów z metodą dopasowania, pewnością i przesłankami |
| `facts.csv` | 714 pojedynczych faktów (kwoty, daty, okresy) — każdy ze źródłem i fragmentem formularza |
| `risk_catalog.csv` | katalog 15 kategorii ryzyka (wiedza ekspercka edytowana w aplikacji) |
| `baza_przypadkow.json` | to samo w jednym pliku JSON: projekty, postępowania, ogłoszenia, umowy, zmiany, zdarzenia, powiązania |
| `przypadek_RM-2026-003.json` | kompletny przypadek (Czernikowo, +40,3% kosztu, 277 dni po terminie): umowy, ogłoszenia, zmiany, zdarzenia, źródła |

## Raport z testu łączenia

| Plik | Co zawiera |
|---|---|
| `raport_polaczen.csv` / `.json` | ocena każdego powiązania: **72 poprawne** (po identyfikatorze), **33 niepewne** (do decyzji eksperta, m.in. projekty KPO bez numeru BZP), **0 błędnych** |

## Analiza nowej inwestycji

| Plik | Co zawiera |
|---|---|
| `analiza_nowej_inwestycji.json` | pełny wynik w trzech warstwach: `dane_zrodlowe` (podobne umowy i uzasadnienie podobieństwa), `obliczenia` (prognoza P50/P80/P90 kosztu i czasu, ryzyko utraty dofinansowania — tu 74%), `wnioski` (czerwone flagi, rejestr ryzyk, audyt 14 klauzul umowy, rekomendacje i propozycje zapisów) |
| `analiza_nowej_inwestycji.csv` | to samo w formie tabeli: podobne projekty, czerwone flagi, rekomendacje i zagadnienia do sprawdzenia |

## Jak wygenerować ponownie

W aplikacji: **Raporty i eksport** (tabele i raport łączenia), widok projektu → **Eksport** (przypadek),
wynik analizy → **Eksport JSON / CSV**. Przez API: `GET /api/export/<tabela>?format=csv`,
`GET /api/report/links?format=csv`, `GET /api/projects/<id>/export`, `GET /api/analyses/<id>/export?format=csv`.
