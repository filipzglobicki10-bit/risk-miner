# Scenariusz demonstracji (film ≤ 3 min i pokaz dla jury)

Przygotowanie: `./run.sh`, przeglądarka na http://127.0.0.1:8080, w polu „Ekspert” wpisane imię i nazwisko.
Demo działa **bez internetu** na prawdziwej kopii ogłoszeń BZP (przycisk na pulpicie).

| Czas | Ekran | Co pokazać / powiedzieć |
|---|---|---|
| 0:00–0:15 | Pulpit | Problem: wiedza o tym, jak naprawdę kończą się inwestycje, leży w BZP, ale nikt jej nie składa. |
| 0:15–0:40 | „Demo na prawdziwych danych BZP” | W 5 s: 22 projekty, 83 ogłoszenia, umowy, zmiany. Pokaż „Czego uczy baza”: 16 z 22 umów rozliczono powyżej wartości umowy, 18 z 22 po terminie, ceny ofert −26% względem szacunku. „To nie są dane syntetyczne.” |
| 0:40–1:05 | Pulpit → „Wykryte problemy w danych” | Numer BZP z rekordu RM-2026-022 nie istnieje; dwa sprzeczne ogłoszenia o wykonaniu (RM-2026-002). System nie tylko łączy dane — sprawdza je. |
| 1:05–1:35 | RM-2026-003 Steklin | Oś czasu: termin 2025-08-18, wykonanie 2026-05-22 (+277 dni); 3 zmiany umowy odczytane z pól formularza: roboty dodatkowe (art. 455 ust. 1 pkt 3), postępowanie Wód Polskich (R04). Link do ogłoszenia i cytat. Potem RM-2026-008: rekord = część 1 z 4 — liczona tylko ta część. |
| 1:35–2:30 | Analiza nowej inwestycji → przykładowy opis + `projekt_umowy_przyklad.txt` | B2: szacunek wystarcza, ale po przetargu zostaw rezerwę P80 ≈ +24–27% ceny umowy; czas P80 ≈ 2 lata zamiast 14 mies. B3: rejestr ryzyk z wyceną w zł. C: audyt klauzul — waloryzacja wyłączona przy umowie na 14 mies. (art. 439 Pzp), kary bez limitu (art. 436 pkt 3), brak klauzuli o warunkach gruntowych, choć grunt zaskoczył w 3 z 22 umów. „Drukuj kartę ryzyka”. |
| 2:30–3:00 | Panel eksperta | Każde zdarzenie i niepewne powiązanie (KPO bez numeru BZP) czeka na decyzję eksperta; decyzje uczą reguły. Zakończenie: liczby z prawdziwych umów, każdy wniosek z dowodem źródłowym. |

## Test jury — ścieżki obowiązkowe

1. **Import i automatyczne wzbogacenie**: Pulpit → plik od jury → „od razu wzbogać z BZP” → Raporty → „Raport z testu łączenia (CSV)”.
2. **Analiza nowej inwestycji z eksportem**: Analiza nowej inwestycji → opis i/lub dokumenty (PPU/SWZ) → Analizuj → Eksport JSON/CSV / druk.
3. **Test źródłowy**: w dowolnym zdarzeniu kliknij źródło → ogłoszenie BZP / dokument (podgląd stron) → cytat.
4. **Test pracy eksperta**: Panel eksperta → Niepewne powiązania → potwierdź/odrzuć (odrzucenie usuwa dane wyprowadzone).
5. **Ponowne uruchomienie**: „Wzbogać wszystkie” drugi raz nie dubluje rekordów (cache + deduplikacja).

## Pytania, których można się spodziewać

- *Skąd pewność, że to działa na prawdziwym API?* — Sprawdziliśmy filtry ręcznie (docs/RAPORT_Z_TESTOW.md, p. 1);
  atrapa w testach odtwarza dokładnie to zachowanie, na prawdziwych ogłoszeniach.
- *22 projekty to mało na statystykę.* — Dlatego pokazujemy n, n_eff i przedział bootstrap przy każdym P80, a umowy
  niezweryfikowane ważą mniej. Metoda nie zmienia się, gdy baza urośnie.
- *Czy audyt klauzul to opinia prawna?* — Nie: lista kontrolna z cytatem i podstawą, do oceny prawnika.
