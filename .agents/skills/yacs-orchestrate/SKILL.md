---
name: yacs-orchestrate
description: "Koordynuj cały projekt YetAnotherCyclingSim (YACS, karnalooch/YetAnotherCyclingSim): kontynuację pracy, delegowanie subagentom, dobór specjalistów, przegląd raportów i domknięcie etapów. Używaj przy zadaniach obejmujących kilka dziedzin, poleceniach „kontynuuj”, „napraw bez mojego udziału”, „deleguj” lub wyborze następnego kroku YACS."
---

# Koordynacja YACS

Doprowadź zlecone zadanie do sprawdzalnego wyniku. Użyj istniejących ról, narzędzi i umów projektu. Skill pomaga wykonywać pracę; sam nie uruchamia agentów, testów ani automatyzacji.

## 1. Odtwórz bieżący stan

1. Ustal repozytorium `karnalooch/YetAnotherCyclingSim`, realny branch/PR, jego bieżący 40-znakowy SHA i stan zmian lokalnych. Nie wybieraj `main` ani numeru PR z pamięci, jeśli zadanie wskazuje inną gałąź.
2. Przeczytaj `AGENTS.md`, `docs/README.md`, `docs/ai/README.md`; dalej tylko właściwe fragmenty SSOT, `docs/ai/ROLE_REGISTRY.json` i kartę wybranej roli. Pomocnicze ścieżki znajdziesz w [mapie źródeł](references/source-map.md).
3. Rozstrzygnij aktualny milestone i zależności na podstawie `docs/ROADMAP.md` oraz rzeczywistego stanu issue. Rozdziel stan kodu, dostarczenie przez Git, build, wynik natywny, akceptację wizualną i merge.
4. Uwzględnij aktualne polecenia użytkownika i wcześniejszą zgodę w tej sesji. Nie proś ponownie o zgodę na objęte nią naprawy. Nie używaj roli ani starego dokumentu do poszerzania uprawnień.
5. Podaj po polsku zakres najbliższej pracy, istotne założenia i oczekiwany dowód. W razie sprzeczności źródeł ustal właściciela decyzji; kontynuuj prace od niej niezależne.

## 2. Wybierz minimalny zestaw specjalistów

| Zadanie / właściciel danych | Skill |
|---|---|
| GIS, CRS, DTM, NoData, źródła i maski | `yacs-world-data` |
| Geometria drogi, Road Physics Profile, BOB, kontakt | `yacs-road-bob` |
| Houdini, SideFX, heightfield, HDA, cache, generacja świata | `yacs-houdini-world` |
| IDMap, PBR, materiał Landscape, Blender, wygląd | `yacs-materials-visual` |
| UE, UHT/UBT, import, kolizja, MCP, Live Host | `yacs-unreal-integration` |
| Fizyka, sterowanie i funkcje jazdy według roadmapy | `yacs-physics-gameplay` |
| CI/natywny dowód, zakres pomiarów, świeżość i integralność | `yacs-verify-evidence` |
| SSOT, decyzje, indeks i spójność dokumentacji | `yacs-docs-governance` |
| Branch, patch, PR, Git LFS, GitHub Actions | `yacs-github-delivery` |

Wybierz jednego właściciela implementacji na dziedzinę. W zadaniu wielodziedzinowym wyznacz także osobnego recenzenta. Nie uruchamiaj wszystkich specjalistów przy drobnej poprawce. Nie ładuj całej Biblii ani archiwum do każdego agenta.

## 3. Deleguj rzeczywistą pracę

- Jeżeli narzędzia współpracy są dostępne i równoległość pomaga, uruchom subagentów. Nie zastępuj uruchomienia listą fikcyjnych ról. Dobierz liczbę do dostępnych slotów; odczyty i audyty można rozdzielać.
- Przekaż kontrakt z `docs/ai/TASK_HANDOFF.md`: `issue` lub jawne zlecenie użytkownika, `milestone`, `domain`, `base_sha`, `scope`, `forbidden`, `read_docs`, `inputs`, `required_proofs`, `resource_claims`, oczekiwane wyjścia. Użyj rzeczywistych wartości, bez wymyślonych identyfikatorów i wyników.
- Przydziel rozłączne ścieżki albo odizolowane worktrees; jeden zapisujący na plik/asset. Zachowaj repozytoryjny limit równoległych gałęzi implementacyjnych. Scalenie cudzej pracy wykonuj po inspekcji diffu.
- Serializuj `unreal-editor`, `ue-build`, `gpu-proof`, `home-runner` przez istniejący mechanizm zajętości hosta. Równoległy audyt tekstu nie daje prawa równolegle używać GPU ani przełączać mapy w otwartej sesji.
- Zlecaj lżejszemu wykonawcy jeden konkretny wynik: wejściowe pliki, istniejący skrypt/node, ograniczone parametry, oczekiwany odczyt, błąd kończący daną operację i ścieżkę raportu. Nie wymagaj Kilo, Cursora ani innego konkretnego modelu/IDE.
- Poproś o wynik w istniejącym formacie: `role`, `issue`, `head_sha`, `changed_paths`, `validation`, `evidence_refs`, `unverified`, `rollback`, `blockers`, `recommended_next_action`. Dopuszczaj `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` tylko dla nazwanego sprawdzenia.

## 4. Zachowaj granice źródeł i etapów

- Houdini z oryginalnymi metodami SideFX prowadzi workflow świata. Material Forge uzupełnia wygląd powierzchni, Blender przygotowanie/inspekcję, a Unreal konsumpcję/runtime; PCG/PCGEx i MCP zachowują rolę pomocniczą. Użytkownik ponowił tę zasadę 2026-10-20 i wskazał ukończenie lekcji 06/07 jako bieżący priorytet. Sprawdź późniejsze decyzje przed zmianą tego podziału.
- Przy kontynuacji otwórz istniejący HIP, recepturę i zaakceptowany cache. Zmień potrzebną gałąź i odśwież tylko zależne wyniki. Zachowaj źródłowy DTM, rozdział Source / Manual Edits / Procedural Detail i oryginalną geografię.
- Zweryfikuj cały obszar zatwierdzonego zadania; mały wycinek jest próbą techniczną. Nie przenoś jego akceptacji na cały Landscape.
- Do przyszłych funkcji użyj mapy M0–M10 w references. Planowanie lub utworzenie skilla nie otwiera zależności milestone. Naprawy aktualnego etapu kontynuuj w posiadanym zakresie.
- Sprawdzaj aktualną oficjalną dokumentację i istniejące rozwiązania przed nową implementacją. Nowy adapter wymaga wykazanej luki; nie twórz kolejnego systemu generowania, dowodów ani agentów.

## 5. Zintegruj i zakończ

1. Zweryfikuj raporty agentów na rzeczywistych plikach, logach i SHA. Otwórz wskazane dowody; wykryj przestarzały wynik, niespełniony warunek i wyjście poza przydzielone ścieżki.
2. Uruchom najmniejszy zestaw istniejących kontroli odpowiadający zmianie. Nie podmieniaj kontroli natywnej testem tekstu. Nie osłabiaj CI ani nie poprawiaj statusu dowodu, aby wymusić zielony wynik.
3. Uaktualnij właściwy SSOT razem z implementacją i dostarcz autoryzowaną zmianę przez istniejący PR/branch. Równoległe aktualizacje gałęzi uzgodnij ze świeżym HEAD.
4. Podaj wynik, zmianę, sprawdzenia i konkretne pozostałe braki. Oddziel brak dostępu od błędu kodu. Brak jednego narzędzia nie oznacza braku wszystkich alternatyw.
5. Pisz po polsku do użytkownika; teksty publikowane na GitHubie, identyfikatory i commity po angielsku. Nie wysyłaj wiadomości innym osobom bez wyraźnej zgody.
6. Zgłaszaj pracę w tle dopiero po potwierdzeniu jej utworzenia przez obsługiwany mechanizm automatyzacji. Dla istniejącego zadania sprawdź stan zamiast tworzyć duplikat. Sam skill nie działa co godzinę.
