---
name: yacs-verify-evidence
description: "Weryfikuj dowody i status wykonania w YetAnotherCyclingSim (YACS): aktualny SHA, GitHub Actions, cache Houdini, natywny Unreal, geometria i kolizja, materiały, zapis/reopen, wizualna akceptacja i wydajność. Używaj przy audytach, przeglądzie raportów, pytaniach czy jest PASS i ocenie gotowości etapu."
---

# YACS — Evidence Review

## Zbuduj zakres audytu

1. Ustal pytanie: źródło, eksport, wykonanie konsumenta, trwałość, obraz, wydajność czy gotowość PR. Zapisz bieżący SHA i identyfikator świata/mapy; nie mieszaj ich w pojedyncze „działa”.
2. Przeczytaj `AGENTS.md`, `docs/ai/roles/proof-qa.md`, właściwy kontrakt i [mapę źródeł](references/source-map.md). Ustal aktualny issue, zakres przestrzenny, etap i wymagania akceptacji.
3. Odróżnij aktualne SSOT od historii. Datowany PASS zachowuje znaczenie dla opisanych wejść, konsumenta i testu. Przy sprzeczności sprawdź najnowszą decyzję właściciela i jej zakres.
4. Prowadź niezależny odczyt. Gdy zadanie obejmuje naprawę, przekaż defekt właścicielowi ścieżek; samo audytowanie nie nadaje uprawnień do zmiany świata, progów ani dowodów.

## Sprawdź łańcuch tożsamości

Dla każdego istotnego wyniku odczytaj artefakt lub log i sprawdź:

- pełny SHA źródła, ewentualny osobny SHA buildu oraz czysty/brudny checkout;
- repozytorium, workflow, run ID i attempt, status i zakończenie procesu;
- scenariusz, mapę/pakiety, wejścia oraz ich rozmiary i hashe;
- datę, host/silnik/narzędzia, PID/sesję dla żywego edytora;
- asercje, liczbę odkrytych testów/próbek i surowe pomiary;
- producenta: zaufany workflow z default branch dla chronionego dowodu lub jawna diagnostyka z gałęzi.

Nie rekonstruuj brakujących pól z nazwy artefaktu ani wartości oczekiwanych. Wykorzystuj istniejące schematy i walidatory, bez nowego „certyfikatu”. Jeśli SHA się zmienił, sprawdź wpływ diffu i istniejącą politykę równoważności; nie przenoś PASS automatycznie.

## Rozdziel znaczenie dowodów

| Dowód | Co może potwierdzić | Co sprawdzić osobno |
|---|---|---|
| Lint, compileall, unit test, CodeQL | Statyczny kontrakt lub model | Build C++, start UE i świat |
| UBT/UHT/linker | Build targetu | Uruchomienie DLL, Automation i scena |
| Cache Houdini i seam export | Dane źródłowe i transport kafli | Co UE wczytał, wyrenderował i skolidował |
| Setter lub żądanie MCP | Wywołanie operacji | Natywny odczyt, rezultat i trwałość |
| Raycast | Próbkowana kolizja i trafiony aktor | Surowe wierzchołki Landscape i cały zakres |
| Screenshot, contact sheet, film z klatek | Obraz z podanym pochodzeniem | Zapis/reopen, geometria, FPS gry i akceptacja właściciela |
| Kopia pliku lub LFS pointer | Istnienie kopii/wskaźnika | Pobrane bajty, hash i możliwość odtworzenia |
| HTTP 200 lub zadanie Running | Endpoint/stan harmonogramu | Nowy obraz, proces i przeżycie końca joba |
| Aggregate CI gate | Wybrany graf checków | Pozostałe bramki etapu i akceptacja wizualna |

## Zbadaj pełny obszar i konsumenta

1. Wyprowadź zakres z zadania i manifestu, nie starej nazwy 2×2 ani wielkości dostępnego źródła. Oddziel źródło, transport envelope, padding i oceniany obszar.
2. Zweryfikuj georeferencję, jednostki, orientację, skalę i wysokości. Odróżnij topologię oczekiwaną od odczytanej. Sprawdź styki i wspólne narożniki; zapisz metodę próbkowania.
3. Dla kontaktu sprawdź trafiony aktor, brak brakujących trafień/penetracji/zawieszeń i zasięg próbek. Stary wynik na innej drodze lub wycinku nie zamyka całej mapy.
4. Dla `Alpha`/NoData sprawdź źródło, eksport, import, visibility/material i kolizję UE. Zero seam w masce nie dowodzi znaczenia maski w silniku.
5. Dla materiałów odczytaj przypisania, tekstury/tablice/sloty, kompilację i nowy render. Default checker, kolor podglądowy i plik tablicy nie dowodzą ukończonego materiału.
6. Dla trwałości wymagaj zapisu właściwych pakietów i niezależnego odczytu po reopen. Replay generatora może ukryć brak zapisanych danych.
7. Oceń obraz całego wymaganego obszaru. Akceptację właściciela oznacz jako oczekującą bez jej potwierdzenia; nie nadawaj jej samodzielnie.

## Czytaj CI bez skrótów

- Sprawdź aktualny PR HEAD, wymagane checki, run/attempt i log pierwszej błędnej fazy. Merge ref może mieć odrębną tożsamość; nazwij ją.
- Rozróżnij `FULL`, `DRAFT_SCOPED`, `STATIC`, `RUNTIME`, `COMPILE`, `NOT_REQUIRED` i odroczenie natywnego entrypointu. Scoped nie staje się pełnym przebiegiem; STATIC wymaga dowodu równoważności.
- Brak testów, same skipped, timeout, anulowany/nieukończony run lub brak artefaktu nie dają PASS. Sprawdź `plan.json`, `summary.json` i logi modułów zamiast zielonego kafelka.
- Legacy Stage 3G nie zastępuje bieżącego Sa Calobra; dowód infrastruktury nie jest akceptacją nowego konsumenta.
- Korzystaj z istniejącego Gumball Proof Broker i walidatorów w zakresie zadania. Luka nie upoważnia do ciężkiego proofu. Dla już upoważnionego uruchomienia sprawdź deduplikację i host ownership.

## Zachowaj uczciwy stan wydajności i archiwów

- Ustal, czy aktualny etap odracza pomiar. `DEFERRED_AFTER_M3` z `performance_pass: false` to brak pomiaru, nie zwolnienie z późniejszych budżetów ani sukces.
- Gdy pomiar jest wymagany, sprawdź sprzęt, rozdzielczość, aktywne RHI, jakość, scenariusz, sektory, próbki i CSV według kontraktu. FPS filmu i czas produkcji screenshotów nie mierzą FPS gry.
- Czytaj `.json.gz` przez standardowy gzip i potwierdź hash oryginalnych bajtów oraz indeks. Nie zmieniaj dat, błędów, statusów ani producenta archiwalnego dowodu.
- Użyj `python scripts/ci/check_evidence_storage.py` przy zmianie przechowywania dowodów. Nie rozszerzaj wyjątków bez uzasadnionej migracji konsumenta. Przywracaj do odizolowanego katalogu, bez ponownego commitu surowego historycznego JSON.

## Zwróć audyt możliwy do sprawdzenia

Dla każdej bramki podaj wymaganie, obserwację, `PASS`/`FAIL`/`BLOCKED`/`NOT RUN`, link do pliku/logu z SHA/run/attempt i brakujący dowód. Oddziel wniosek od hipotezy. Podaj pierwszą konkretną przyczynę i najkrótsze działanie rozstrzygające niepewność. Nie zmieniaj wcześniejszej akceptacji bez wykazanej regresji ani nie deklaruj nowej przez skopiowanie starej.
