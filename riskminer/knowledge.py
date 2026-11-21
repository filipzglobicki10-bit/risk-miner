"""Wiedza ekspercka startowa (pilotaż: sektor wodociągowo-kanalizacyjny).

Źródło: materiały eksperckie MFiPR dla HackNation 2026 (katalog ryzyk R01–R15, sygnały zmian,
podsektory, checklista przygotowania inwestycji). Po zasileniu bazy wszystkie elementy są edytowalne
w panelu eksperta — kod nie zawiera reguł „na sztywno” poza tym ziarnem.

Wzorce (patterns) to wyrażenia regularne stosowane do tekstu złożonego do małych liter BEZ polskich
znaków (np. „opóźnienie” -> „opoznienie”).
"""
import json

from . import db
from .util import now_iso

RISKS = [
    {
        "code": "R01", "name": "Niepełny lub niespójny zakres",
        "effects": "Błędna wycena, pominięcie lub dublowanie robót, zmiana zakresu, roboty dodatkowe, roszczenie albo spór o wynagrodzenie.",
        "patterns": [r"zwiekszeni\w* zakresu", r"rozszerzeni\w* zakresu", r"(nieobjet|nieujet|nieprzewidzian)\w* (w |pierwotn\w* )?(pfu|programie funkcjonalno|dokumentacj)", r"poza zakresem (pfu|dokumentacji|umowy)",
                     r"niezgodnos\w* (dokumentacj|przedmiar|projekt)", r"rozbieznos\w* (miedzy|pomiedzy|w dokumentacj)",
                     r"pominiet\w* (robot|pozycj|w przedmiarze)", r"niekompletn\w* (dokumentacj|projekt)",
                     r"zmian\w* zakresu", r"ograniczeni\w* zakresu", r"brak\w* w przedmiarze", r"bledy w dokumentacji"],
        "mitigations": ["Weryfikacja kompletności PFU/OPZ, przedmiaru i projektu przed ogłoszeniem (przegląd krzyżowy).",
                        "Jasna hierarchia dokumentów w umowie i SWZ.",
                        "Zebranie pytań wykonawców i wyprzedzające doprecyzowanie zakresu."],
        "clauses": ["Hierarchia dokumentów: Umowa > SWZ z odpowiedziami > PFU/Projekt > STWiORB > przedmiar (pomocniczo).",
                    "Procedura zmiany zakresu z wyceną według uzgodnionych składników cenotwórczych i limitem wartości zmian."],
        "checks": ["Czy przedmiar i projekt obejmują wszystkie odcinki i przyłącza?", "Czy zakres jest spójny w SWZ, PFU/OPZ i PPU?"],
    },
    {
        "code": "R02", "name": "Niedostateczne rozpoznanie stanu istniejącego",
        "effects": "Przeprojektowanie, nieprzewidziane roboty, przestoje, wzrost kosztu albo wydłużenie terminu.",
        "patterns": [r"warunk\w* gruntow", r"grunt\w* skaln", r"odmienn\w* grunt", r"kategori\w* (v|vi|iv)\b", r"geotechn", r"geolog", r"niezinwentaryzowan", r"niezidentyfikowan",
                     r"wod\w* gruntow", r"kurzawk", r"odmienn\w* (warunk|od przewidywan)", r"nieznan\w* (sieci|uzbrojeni|przeszkod)",
                     r"stan\w* technicz\w* (istniejac|obiekt)", r"nienosn"],
        "mitigations": ["Badania geotechniczne i inwentaryzacja uzbrojenia przed przetargiem.",
                        "Rezerwa na nieprzewidziane warunki (5–10%) w budżecie."],
        "clauses": ["Mechanizm podziału ryzyka warunków gruntowych odmiennych od opisanych w dokumentacji geotechnicznej (raport bazowy)."],
        "checks": ["Czy wykonano badania gruntu na trasie i w miejscach obiektów?", "Czy zinwentaryzowano istniejące uzbrojenie?"],
    },
    {
        "code": "R03", "name": "Kolizje, dostęp do terenu i prawa do nieruchomości",
        "effects": "Brak możliwości rozpoczęcia części robót, zmiana trasy lub technologii, wstrzymanie prac albo roszczenia.",
        "patterns": [r"kolizj", r"brak\w* (zgody|dostepu) (wlasciciel|do teren|do nieruchom)", r"sluzebnos",
                     r"przekazani\w* (terenu|placu) budowy", r"prawo do dysponowania", r"wlasciciel\w* (nieruchomos|dzialk)\w* (nie wyraz|odmow|sprzeciw)",
                     r"zmian\w* (trasy|przebiegu)", r"grunt\w* prywatn", r"wejsci\w* w teren"],
        "mitigations": ["Uzyskanie zgód właścicieli / służebności przed ogłoszeniem przetargu.",
                        "Prowadzenie trasy w pasach drogowych tam, gdzie to możliwe; wczesne uzgodnienia z zarządcami dróg."],
        "clauses": ["Termin przekazania terenu w podziale na odcinki; przedłużenie terminu o czas opóźnienia w przekazaniu terenu z przyczyn Zamawiającego."],
        "checks": ["Czy dla wszystkich działek na trasie jest prawo do dysponowania terenem?", "Czy znane są kolizje z innymi sieciami?"],
    },
    {
        "code": "R04", "name": "Decyzje, pozwolenia i uzgodnienia zależne od podmiotów trzecich",
        "effects": "Opóźnienie rozpoczęcia lub kontynuacji prac, zmiana warunków realizacji albo brak możliwości użytkowania obiektu.",
        "patterns": [r"pozwoleni\w* na budowe", r"decyzj\w* (o )?srodowiskow", r"pozwoleni\w* wodnoprawn", r"uzgodnieni\w* z (gestor|zarzadc)",
                     r"zgloszeni\w* robot", r"warunk\w* techniczn\w* (przylacz|zasilan)", r"(opoznieni|przedluz)\w* (wydania|uzyskania)\w* (decyzj|pozwol|uzgodn)",
                     r"natura 2000", r"konserwator"],
        "mitigations": ["Harmonogram decyzji z rezerwą czasową; uzyskanie kluczowych decyzji przed przetargiem w formule tradycyjnej.",
                        "W „zaprojektuj i wybuduj” — jasny podział, kto i w jakim terminie występuje o decyzje."],
        "clauses": ["Wydłużenie terminu o czas procedowania decyzji przez organy ponad terminy ustawowe (art. 455 ust. 1 pkt 1 Pzp — zmiana przewidziana)."],
        "checks": ["Czy wymagana jest decyzja środowiskowa / pozwolenie wodnoprawne?", "Kto odpowiada za uzyskanie decyzji?"],
    },
    {
        "code": "R05", "name": "Niejasny lub nieadekwatny podział odpowiedzialności",
        "effects": "Luka odpowiedzialności, dublowanie prac, odmowa wykonania, roszczenie i spór o koszt lub termin.",
        "patterns": [r"spor\w* (o|co do|miedzy)", r"niejasn\w* (podzial|zapis|odpowiedzialn)", r"niejednoznaczn\w* (podzial|zapis)",
                     r"odpowiedzialnos\w* (za|stron|zamawiaj|wykonawc)", r"roszczeni"],
        "mitigations": ["Macierz odpowiedzialności (inwestor / projektant / wykonawca / operator) w dokumentach zamówienia."],
        "clauses": ["Załącznik do umowy: macierz podziału ryzyk i odpowiedzialności, z przypisaniem kosztu i terminu do strony."],
        "checks": ["Czy wiadomo, kto eksploatuje sieć i kto odbiera roboty po stronie operatora?"],
    },
    {
        "code": "R06", "name": "Nierealistyczny harmonogram i nieuwzględnione zależności",
        "effects": "Opóźnienie, kary, kumulacja prac, presja na skrócenie prób i badań albo pogorszenie jakości.",
        "patterns": [r"przedluz\w* (termin|czas)", r"zmian\w* terminu", r"opoznien", r"nie(dotrzyma|zachowa)\w* termin", r"po terminie",
                     r"warunk\w* atmosferyczn", r"okres\w* zimow", r"harmonogram\w* (rzeczowo|aktualiz|zmian)", r"wydluzeni\w* (termin|okres)"],
        "mitigations": ["Harmonogram uwzględniający okres zimowy, czas decyzji i odbiorów operatora.",
                        "Kamienie milowe i aktualizacja harmonogramu co miesiąc."],
        "clauses": ["Przesłanki przedłużenia terminu (warunki atmosferyczne uniemożliwiające roboty potwierdzone danymi IMGW, opóźnienia organów, kolizje)."],
        "checks": ["Czy termin realizacji jest zgodny z medianą dla podobnych projektów?", "Czy uwzględniono okres zimowy?"],
    },
    {
        "code": "R07", "name": "Nieprzewidziane zmiany i roboty dodatkowe",
        "effects": "Wstrzymanie robót, negocjacje, aneks, roszczenie, przekroczenie budżetu albo spór o odpowiedzialność.",
        "patterns": [r"robot\w* (dodatkow|zamienn|uzupelniaj|nieprzewidzian)", r"art\.? ?455 ust\.? ?1 pkt\.? ?[34]", r"protokol\w* koniecznosci",
                     r"nieprzewidzi", r"aneks", r"zamowieni\w* (dodatkow|uzupelniaj)", r"zmian\w* umowy"],
        "mitigations": ["Rezerwa budżetowa na roboty nieprzewidziane; ścieżka szybkiej akceptacji zmian (protokół konieczności)."],
        "clauses": ["Katalog zmian przewidzianych (art. 455 ust. 1 pkt 1 Pzp) z zasadami wyceny i limitem łącznej wartości."],
        "checks": ["Czy przewidziano rezerwę na roboty nieprzewidziane?", "Czy umowa zawiera katalog zmian?"],
    },
    {
        "code": "R08", "name": "Model wynagrodzenia niedopasowany do niepewności zakresu",
        "effects": "Zawyżona rezerwa w cenie albo niedoszacowanie, problemy płynnościowe i spory o zakres objęty wynagrodzeniem.",
        "patterns": [r"wynagrodzeni\w* ryczalt", r"kosztorys\w* powykonawcz", r"waloryzacj", r"(zmian|zwieksz|zmniejsz)\w* wynagrodzeni",
                     r"wzrost\w* cen", r"inflacj", r"cen\w* materialow"],
        "mitigations": ["Dobór modelu: ryczałt tylko przy pełnej dokumentacji; przy niepewnym zakresie — kosztorysowe lub mieszane.",
                        "Klauzula waloryzacyjna (art. 439 Pzp) oparta na wskaźniku GUS."],
        "clauses": ["Klauzula waloryzacyjna wg wskaźnika cen produkcji budowlano-montażowej GUS, z progiem i limitem zmiany."],
        "checks": ["Czy wybrany model wynagrodzenia odpowiada kompletności dokumentacji?"],
    },
    {
        "code": "R09", "name": "Niejednoznaczne lub niemierzalne wymagania techniczne",
        "effects": "Niewłaściwy dobór rozwiązania, przeprojektowanie, trudność w potwierdzeniu zgodności, problem z odbiorem.",
        "patterns": [r"parametr\w* techniczn\w* (niejasn|niejednoznaczn|nieokresl)", r"rozwiazani\w* rownowazn", r"zmian\w* technologi",
                     r"przeprojektow", r"zmian\w* (materialu|rozwiazania technicznego)", r"niejednoznaczn\w* wymag"],
        "mitigations": ["Mierzalne parametry w PFU/OPZ (wydajność, ciśnienie, parametry ścieków oczyszczonych) i metody ich weryfikacji."],
        "clauses": ["Opis sposobu wykazania równoważności oraz metodyki prób potwierdzających parametry."],
        "checks": ["Czy wymagania techniczne są mierzalne i sprawdzalne przy odbiorze?"],
    },
    {
        "code": "R10", "name": "Niedookreślone próby, rozruch i odbiór",
        "effects": "Wykonane roboty nie mogą zostać odebrane; opóźnia się użytkowanie i rozliczenie; powstaje spór o osiągnięcie parametrów.",
        "patterns": [r"rozruch", r"odmow\w* (dokonania )?odbioru", r"wad\w* (istotn|i usterek)", r"prob\w* szczelnosci", r"inspekcj\w* tv",
                     r"odbior\w* (koncow|czesciow)\w* .{0,40}(przesun|opozn|odmow)", r"usterk"],
        "mitigations": ["Program prób i rozruchu w dokumentach zamówienia; udział operatora w odbiorach."],
        "clauses": ["Warunki odbioru końcowego: pozytywne próby, inspekcja TV kanałów, dokumentacja powykonawcza, szkolenie obsługi."],
        "checks": ["Czy określono program prób, rozruchu i kryteria odbioru?"],
    },
    {
        "code": "R11", "name": "Postępowanie podatne na odwołanie lub ograniczenie konkurencji",
        "effects": "Przedłużenie albo unieważnienie postępowania, słabsza konkurencja, wyższa cena lub wybór rozwiązania nieadekwatnego do potrzeb.",
        "patterns": [r"odwolani\w* do (krajowej izby|kio)", r"\bkio\b", r"uniewazni\w*", r"(wplynela|zlozono|zlozona) (tylko )?(jedna|1) ofert",
                     r"cena (najkorzystniejszej )?oferty przewyzsza kwote", r"art\.? ?255", r"brak ofert", r"powtorzon\w* postepowani"],
        "mitigations": ["Rynkowe szacowanie wartości (aktualne ceny jednostkowe), proporcjonalne warunki udziału.",
                        "Konsultacje rynkowe przy niestandardowym zakresie."],
        "clauses": ["Warunki udziału proporcjonalne do przedmiotu; podział na części, jeśli zwiększa konkurencję."],
        "checks": ["Czy budżet jest zgodny z cenami ofert w podobnych postępowaniach?", "Ile ofert wpływało w podobnych przetargach?"],
    },
    {
        "code": "R12", "name": "Niewystarczająca zdolność wykonawcy lub łańcucha dostaw",
        "effects": "Opóźnienie, zamiana materiałów lub urządzeń, problemy jakościowe i finansowe albo przerwanie realizacji.",
        "patterns": [r"upadlos", r"zmian\w* (wykonawcy|podwykonawc)", r"odstapi\w* od umowy", r"rozwiazani\w* umowy", r"niewyplacal",
                     r"brak\w* (materialow|dostaw|urzadzen)", r"zamian\w* (materialow|urzadzen)", r"kar\w* umown", r"nienalezyt\w* wykonani"],
        "mitigations": ["Weryfikacja doświadczenia i potencjału; zabezpieczenie należytego wykonania; kontrola podwykonawców."],
        "clauses": ["Kary umowne proporcjonalne z limitem; prawo odstąpienia przy opóźnieniu ponad X dni; bezpośrednia płatność podwykonawcom."],
        "checks": ["Czy przewidziano zabezpieczenie i mechanizmy reakcji na niewykonanie?"],
    },
    {
        "code": "R13", "name": "Ryzyko finansowania, budżetu i płatności",
        "effects": "Ograniczenie zakresu, opóźnione płatności, utrata dofinansowania, brak środków na niezbędne zmiany albo problemy płynnościowe.",
        "patterns": [r"zwiekszeni\w* (srodkow|kwoty|budzetu)", r"brak\w* srodkow", r"\bwpf\b", r"wieloletni\w* prognoz", r"korekt\w* finansow",
                     r"utrat\w* dofinansowani", r"zator\w* platnicz", r"przekracza kwote"],
        "mitigations": ["Zabezpieczenie środków w WPF z rezerwą; harmonogram płatności zgodny z harmonogramem dofinansowania."],
        "clauses": ["Płatności częściowe za odebrane etapy; zaliczka przy długim cyklu dostaw."],
        "checks": ["Czy środki w WPF pokrywają przewidywaną cenę (z rezerwą)?", "Czy terminy dofinansowania są zgodne z harmonogramem?"],
    },
    {
        "code": "R14", "name": "Nadmierne koszty eksploatacji i utrzymania",
        "effects": "Obiekt spełnia wymagania inwestycyjne, ale jest drogi, trudny lub niestabilny w eksploatacji.",
        "patterns": [r"koszt\w* eksploatac", r"zuzyci\w* energii", r"awaryjnos", r"zagniwani", r"czas\w* przebywania wody", r"maly przeplyw"],
        "mitigations": ["Analiza kosztów cyklu życia (LCC) w wyborze wariantu; konsultacja z operatorem."],
        "clauses": ["Kryterium kosztu cyklu życia lub wymagania energochłonności urządzeń."],
        "checks": ["Czy operator potwierdził akceptowalność kosztów eksploatacji?"],
    },
    {
        "code": "R15", "name": "Nieosiągnięcie efektu technologicznego, użytkowego lub środowiskowego",
        "effects": "Brak wymaganej jakości lub wydajności, ograniczenie użytkowania, konieczność dodatkowych prac, ryzyko sankcji albo utraty efektu projektu.",
        "patterns": [r"nie ?osiagn\w* (efekt|wskaznik|parametr)", r"wskaznik\w* rezultatu", r"przekroczeni\w* (parametr|norm|dopuszczaln)",
                     r"niski\w* (poziom|stopien) przylaczen", r"mala liczba przylaczen", r"\brlm\b"],
        "mitigations": ["Wczesne potwierdzenie liczby przyłączeń (deklaracje); monitoring wskaźników."],
        "clauses": ["Obowiązek wykonawcy wykazania parametrów w okresie rozruchu; gwarancja efektu technologicznego."],
        "checks": ["Czy liczba przyłączeń/odbiorców jest potwierdzona?", "Czy parametry efektu są mierzalne?"],
    },
]

EVENT_TYPES = [
    {"code": "E01", "name": "Zmiana terminu wykonania", "risk_codes": ["R06"],
     "patterns": [r"(przedluz|zmian|wydluz)\w* (termin|okres)\w* (realizacji|wykonania|zakonczenia)", r"termin\w* (realizacji|wykonania) .{0,60}(zmienia|przedluza)"]},
    {"code": "E02", "name": "Zmiana wynagrodzenia", "risk_codes": ["R08", "R07"],
     "patterns": [r"(zmian|zwieksz|zmniejsz|podwyzsz|obniz)\w* (wynagrodzeni|wartosci umowy|ceny)", r"waloryzacj"]},
    {"code": "E03", "name": "Zmiana zakresu, roboty dodatkowe lub zamienne", "risk_codes": ["R07", "R01"],
     "patterns": [r"robot\w* (dodatkow|zamienn|uzupelniaj)", r"art\.? ?455 ust\.? ?1 pkt\.? ?3", r"zmian\w* zakresu"]},
    {"code": "E04", "name": "Wykonanie po pierwotnym terminie", "risk_codes": ["R06"], "patterns": [r"wykonan\w* po (terminie|uplywie)"]},
    {"code": "E05", "name": "Wypłata wyższa niż pierwotna wartość umowy", "risk_codes": ["R07", "R08"], "patterns": []},
    {"code": "E06", "name": "Nienależyte wykonanie albo kara umowna", "risk_codes": ["R12"],
     "patterns": [r"kar\w* umown\w* (nalozon|naliczon|w wysokosci)", r"nalozono kar", r"nienalezyt\w* wykonani"]},
    {"code": "E07", "name": "Niewykonanie, rozwiązanie albo odstąpienie od umowy", "risk_codes": ["R12"],
     "patterns": [r"odstapi\w* od umowy", r"rozwiazani\w* umowy", r"umowa nie zostala wykonana"]},
    {"code": "E08", "name": "Unieważnienie postępowania", "risk_codes": ["R11"],
     "patterns": [r"uniewazni\w* postepowani", r"postepowanie (zostalo )?uniewaznion"]},
    {"code": "E09", "name": "Odwołanie do KIO", "risk_codes": ["R11"], "patterns": [r"odwolani\w*", r"\bkio\b", r"krajowa izba odwolawcza"]},
    {"code": "E10", "name": "Zmiana wykonawcy", "risk_codes": ["R12"], "patterns": [r"zmian\w* wykonawcy", r"art\.? ?455 ust\.? ?1 pkt\.? ?2", r"nowy wykonawca"]},
    {"code": "E11", "name": "Nieprawidłowość stwierdzona w kontroli", "risk_codes": ["R05", "R13"],
     "patterns": [r"nieprawidlowos", r"wystapieni\w* pokontroln", r"najwyzsza izba kontroli", r"\bnik\b"]},
    {"code": "E12", "name": "Problem z terenem / kolizja", "risk_codes": ["R03"], "patterns": [r"kolizj", r"brak\w* zgody wlasciciel", r"zmian\w* (trasy|przebiegu)", r"sluzebnos"]},
    {"code": "E16", "name": "Warunki atmosferyczne", "risk_codes": ["R06"], "patterns": [r"warunk\w* (atmosferyczn|pogodow)", r"opad\w* deszczu", r"ekstremaln\w* (warunk|zjawisk)"]},
    {"code": "E13", "name": "Opóźnienie decyzji / uzgodnienia", "risk_codes": ["R04"],
     "patterns": [r"(opoznieni|przedluz|oczekiwani)\w* (na )?(wydani|uzyskani)\w* (decyzj|pozwol|uzgodn)"]},
    {"code": "E14", "name": "Niekorzystne warunki gruntowo-wodne", "risk_codes": ["R02"], "patterns": [r"warunk\w* gruntow", r"wod\w* gruntow", r"kurzawk", r"grunt\w* skaln"]},
    {"code": "E15", "name": "Problemy z próbami, rozruchem lub odbiorem", "risk_codes": ["R10"], "patterns": [r"rozruch", r"odmow\w* odbioru", r"usterk", r"wad\w* istotn"]},
]

SUBSECTORS = [
    {"name": "Sieć wodociągowa", "patterns": [r"wodociag", r"przylacz\w* wod", r"sieci wodn", r"magistral\w* wod"]},
    {"name": "Kanalizacja sanitarna", "patterns": [r"kanalizacj\w* sanitarn", r"przepompowni", r"tloczn", r"sciekow sanitarn", r"kanaliz\w* (grawitacyjn|ciśnieniow|cisnieniow)"]},
    {"name": "Oczyszczalnia ścieków", "patterns": [r"oczyszczalni"]},
    {"name": "Uzdatnianie i zaopatrzenie w wodę", "patterns": [r"stacj\w* uzdatniania", r"\bsuw\b", r"ujeci\w* wod", r"studni\w* (glebin|wiercon|ujeciow)", r"zbiornik\w* (wody|retencyjn\w* wody)", r"hydrofor"]},
    {"name": "Kanalizacja deszczowa i retencja", "patterns": [r"deszczow", r"retencj", r"odwodnieni", r"wod\w* opadow"]},
    {"name": "Inne obiekty wod-kan", "patterns": []},
]

CHECKLIST = [
    {"id": "C1", "text": "Konkretny problem zaopatrzenia w wodę / odprowadzania ścieków i oczekiwany efekt inwestycji.", "ref": "1.1–1.2",
     "patterns": [r"problem", r"brak\w* (dostepu|sieci|kanalizacji)", r"niedobor", r"\bcel\w*", r"efekt", r"zapewnieni"]},
    {"id": "C2", "text": "Obszar obsługi oraz przybliżona liczba i charakter odbiorców.", "ref": "1.3–1.4",
     "patterns": [r"mieszkan", r"odbiorc", r"budynk", r"gospodarstw", r"nieruchomos", r"\brlm\b"]},
    {"id": "C3", "text": "Przewidywani odbiorcy początkowi i wiarygodne przesłanki dalszego przyłączania nieruchomości.", "ref": "2.1–2.3",
     "patterns": [r"przylacz", r"deklaracj", r"zainteresowan"]},
    {"id": "C4", "text": "Orientacyjny przebieg i długość sieci oraz zakres przewidywanych przyłączy.", "ref": "3.1–3.4",
     "patterns": [r"\d+[,.]?\d*\s*(km|mb|m)\b", r"dlugos", r"przebieg", r"tras"]},
    {"id": "C5", "text": "Przewidywane miejsce zasilania / odbioru ścieków i stanowisko operatora.", "ref": "4.1–4.4",
     "patterns": [r"zasilan", r"operator", r"przedsiebiorstw\w* (wodociag|komunaln)", r"wlaczeni", r"wpiet", r"istniejac\w* (sieci|oczyszczalni|kanalizacj)"]},
    {"id": "C6", "text": "Wstępna trasa sieci, rodzaj własności gruntów i znane trudności z dostępem.", "ref": "5.1–5.4",
     "patterns": [r"grunt", r"dzialk", r"wlasnos", r"pas\w* drog", r"prywatn"]},
    {"id": "C7", "text": "Główne przeszkody lokalizacyjne i zależności od innych inwestycji.", "ref": "5.4; 6.1–6.2",
     "patterns": [r"przeszk", r"kolizj", r"ciek", r"kolej", r"zalezn", r"przekroczen", r"przejsci\w* pod"]},
    {"id": "C8", "text": "Wstępne rozpoznanie potrzeby decyzji środowiskowej i ograniczeń ochrony przyrody.", "ref": "6.3–6.5",
     "patterns": [r"srodowisk", r"natura 2000", r"ochron\w* przyrody", r"wodnoprawn"]},
    {"id": "C9", "text": "Podział odpowiedzialności za przygotowanie, projekt, nieruchomości, decyzje i eksploatację oraz główne ryzyka.", "ref": "7.1–7.5",
     "patterns": [r"odpowiedzialn", r"projektant", r"nadzor", r"eksploatac", r"podzial\w* ryzyk", r"zaprojektuj i wybuduj", r"projektuj i buduj"]},
]

# Oczekiwane dokumenty/ogłoszenia w cyklu życia postępowania — do wykrywania braków w paczce.
DOC_EXPECTATIONS = [
    {"key": "ContractNotice", "label": "Ogłoszenie o zamówieniu", "phase": "Postępowanie zakupowe", "why": "Zakres, tryb, terminy, kryteria — punkt wyjścia do łączenia źródeł."},
    {"key": "TenderResultNotice", "label": "Ogłoszenie o wyniku postępowania", "phase": "Postępowanie zakupowe", "why": "Wykonawca, cena, liczba ofert — podstawa wartości kontraktu."},
    {"key": "contract_terms", "label": "Umowa lub PPU/SWU (warunki kontraktowe)", "phase": "Zawarcie umowy", "why": "Termin, wynagrodzenie, kary, katalog zmian. Bez tego analiza zapisów umownych jest ograniczona."},
    {"key": "change_info", "label": "Ogłoszenie o zmianie umowy / aneks", "phase": "Realizacja", "why": "Potwierdza zmiany terminu, wartości, zakresu (sygnał materializacji ryzyka)."},
    {"key": "ContractPerformingNotice", "label": "Ogłoszenie o wykonaniu umowy", "phase": "Zamknięcie", "why": "Faktyczny termin, łączna wypłata, kary — podstawa do wyliczenia odchyleń kosztu i czasu."},
    {"key": "control", "label": "Wyniki kontroli (NIK / RIO / IZ) lub orzeczenia KIO", "phase": "Materiały zewnętrzne", "why": "Opisują przyczyny problemów, których nie ma w dokumentach postępowania."},
]

SECTOR_DESCRIPTION = (
    "Pilotaż: sektor wodociągowo-kanalizacyjny. Projekty mają powtarzalne elementy techniczne (sieci, przyłącza, "
    "przepompownie, SUW, oczyszczalnie), mierzalne rezultaty (km sieci, liczba przyłączy, RLM) i liczne publiczne "
    "źródła danych (BZP, KPO, BIP gmin). Wartość projektu nie jest wartością umowy z wykonawcą. Wartość zamówienia "
    "jest szacunkiem netto; kwota przeznaczona na sfinansowanie, ceny ofert i wartość umowy są brutto."
)


def seed(force=False):
    if force or not db.q1("SELECT code FROM risk_catalog LIMIT 1"):
        for r in RISKS:
            db.x("DELETE FROM risk_catalog WHERE code=?", (r["code"],))
            db.insert("risk_catalog", {
                "code": r["code"], "name": r["name"], "description": r.get("description", ""), "effects": r["effects"],
                "patterns": r["patterns"], "mitigations": r["mitigations"], "clauses": r["clauses"], "checks": r["checks"],
                "status": "approved", "proposed_by": "materiał ekspercki MFiPR", "updated_at": now_iso(),
            })
    if force or not db.q1("SELECT code FROM event_types LIMIT 1"):
        for e in EVENT_TYPES:
            db.x("DELETE FROM event_types WHERE code=?", (e["code"],))
            db.insert("event_types", {"code": e["code"], "name": e["name"], "risk_codes": e["risk_codes"],
                                      "patterns": e["patterns"], "status": "approved", "updated_at": now_iso()})
    defaults = {
        "subsectors": SUBSECTORS,
        "checklist": CHECKLIST,
        "doc_expectations": DOC_EXPECTATIONS,
        "sector_description": SECTOR_DESCRIPTION,
    }
    for k, v in defaults.items():
        if force or not db.q1("SELECT key FROM knowledge WHERE key=?", (k,)):
            db.x("INSERT OR REPLACE INTO knowledge(key,value,updated_at) VALUES(?,?,?)", (k, json.dumps(v, ensure_ascii=False), now_iso()))


def get(key, default=None):
    row = db.q1("SELECT value FROM knowledge WHERE key=?", (key,))
    return db.jload(row["value"], default) if row else default


def put(key, value, actor="ekspert"):
    before = get(key)
    db.x("INSERT OR REPLACE INTO knowledge(key,value,updated_at) VALUES(?,?,?)", (key, json.dumps(value, ensure_ascii=False), now_iso()))
    db.audit("knowledge.update", "knowledge", key, before=before, after=value, actor=actor)


def risks(include_proposed=False):
    sql = "SELECT * FROM risk_catalog" + ("" if include_proposed else " WHERE status='approved'") + " ORDER BY code"
    out = []
    for r in db.q(sql):
        for k in ("patterns", "mitigations", "clauses", "checks"):
            r[k] = db.jload(r[k], [])
        out.append(r)
    return out


def event_types():
    out = []
    for r in db.q("SELECT * FROM event_types WHERE status='approved' ORDER BY code"):
        r["patterns"] = db.jload(r["patterns"], [])
        r["risk_codes"] = db.jload(r["risk_codes"], [])
        out.append(r)
    return out


def risk_names():
    return {r["code"]: r["name"] for r in db.q("SELECT code,name FROM risk_catalog")}
