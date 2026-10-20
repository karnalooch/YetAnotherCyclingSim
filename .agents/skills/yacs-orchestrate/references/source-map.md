# Źródła i pokrycie całego projektu

## Tożsamość źródeł

Repozytorium: `karnalooch/YetAnotherCyclingSim`. Ścieżki poniżej są względem jego korzenia, nie katalogu tego skilla. Znajdź lokalny checkout albo odczytaj je przez GitHub przy zweryfikowanym SHA. Jeśli źródło jest niepełne, rozróżnij brak w sparse checkout od nieistnienia pliku w Git.

Mapa została sprawdzona 2026-10-20 na `5a33c31a43e4933547a64bcb12e78552ce06e83a`: [agent router](https://github.com/karnalooch/YetAnotherCyclingSim/blob/5a33c31a43e4933547a64bcb12e78552ce06e83a/docs/ai/README.md), [roadmap](https://github.com/karnalooch/YetAnotherCyclingSim/blob/5a33c31a43e4933547a64bcb12e78552ce06e83a/docs/ROADMAP.md). Jest mapą odnalezienia aktualnych źródeł, nie potwierdzeniem obecnego HEAD, statusu PR, ukończenia etapu ani konfiguracji hosta.

## Pierwszeństwo i dobór dokumentów

| Pytanie | Źródło do odczytu |
|---|---|
| Co budujemy, co jest poza MVP? | `docs/PRODUCT_REQUIREMENTS.md` |
| Co jest następne, jakie zależności? | `docs/ROADMAP.md` |
| Który dokument jest SSOT? | `docs/README.md` |
| Kto posiada daną dziedzinę? | `docs/ai/ROLE_REGISTRY.json`, `docs/ai/roles/` |
| Jak przekazać i ocenić zadanie? | `docs/ai/TASK_HANDOFF.md` |
| Co zmieniła późniejsza decyzja? | `docs/ai/DECISION_LIFECYCLE.md` |
| Jak budować świat? | `docs/WORLD_BUILDING_BIBLE.md`, `docs/tooling/sidefx/README.md` |
| Jakie są granice zakresu i wykonania? | `docs/ai/policies/DELIVERY_AND_SCOPE.md` |
| Jak sprawdzić wynik i dobrać koszt testu? | `docs/CI_VALIDATION_TIERS.md`, `docs/ENGINEERING_PLATFORM.md` |
| Jak bezpiecznie korzystać z PC użytkownika? | `docs/tooling/LOCAL_WORKSPACE.md`, `docs/ai/policies/M3_WORLD_OPERATIONS.md` |

W razie rozbieżności przeczytaj aktualną decyzję użytkownika i jej zakres. Umowa roli nie przyznaje uprawnień i nie znosi ograniczeń narzędzi. Dawne PASS, progi, mapy i nazwy hostów w historii nie stanowią aktualnego kontraktu.

## Pokrycie M0–M10

Odczytaj bieżące entry/exit gates z roadmapy. Poniższy podział wskazuje, do którego specjalisty kierować pracę po potwierdzeniu jej zakresu; nie nadaje planowanym rolom statusu active.

| Obszar | Pierwszy skill | Kontekst uzupełniający |
|---|---|---|
| M0: repozytorium i narzędzia | `yacs-github-delivery` | dokumentacja, CI, LFS, zależności |
| M1: rdzeń fizyki | `yacs-physics-gameplay` | `physics_reference/`, testy C++ |
| M2: działający runtime i wejścia | `yacs-physics-gameplay` | `yacs-unreal-integration`, kontrakt runtime |
| M3: trasa i fundament świata | `yacs-world-data`, `yacs-road-bob`, `yacs-houdini-world` | materiały, UE, dowody; dobierz właściciela według zadania |
| M4: technika zakrętów i asysty | `yacs-physics-gameplay` | Road Physics Profile, geometria drogi |
| M5: HUD i sesja | `yacs-physics-gameplay` | właściciel planowany `session-ui`, UE i dowody |
| M6: kolarz, rower, kamery i animacje | `yacs-physics-gameplay`, `yacs-materials-visual` | właściciel planowany `rider-animation`, dane mocap i licencje |
| M7: skały, roślinność i otoczenie | `yacs-houdini-world`, `yacs-materials-visual` | istniejące specjalizacje świata i dane źródłowe |
| M8: pogoda, wiatr, mokrość i dźwięk | `yacs-physics-gameplay`, `yacs-materials-visual` | właściciel planowany `environment-systems`, jeden model wejść środowiska |
| M9: zapis i FIT | `yacs-physics-gameplay` | właściciel planowany `data-export-release`, ciągłość danych sesji |
| M10: stabilizacja i wydanie | `yacs-unreal-integration`, `yacs-verify-evidence` | wydajność rzeczywistego buildu, pakowanie, GitHub delivery |
| Po MVP: realny trainer, sieć, pack dynamics | `yacs-orchestrate` → właściwy aktywowany właściciel | najpierw aktualny scope/roadmap i stabilność poprzedników |

Przy HUD, FIT, avatarze, pogodzie i trenerze nie wymyślaj istniejącej implementacji. Wyszukaj rzeczywiste klasy/testy i odróżnij kod od planu. Jeśli wymagany właściciel jest nadal planned, przygotuj analizę/wejścia i zgłoś konkretną zależność blokującą implementację.

## Wyszukiwanie bez przeładowania kontekstu

- `rg -n '^#{1,3} ' docs/ROADMAP.md docs/PRODUCT_REQUIREMENTS.md docs/WORLD_BUILDING_BIBLE.md` pozwala wybrać potrzebne sekcje.
- `rg --files Source physics_reference scripts docs/ai` pozwala odnaleźć istniejącą implementację i kontrakty.
- Szukaj numeru zadania, nazwy klasy/skryptu lub decyzji po ustaleniu bieżącego SHA; nie wnioskuj stanu z samej nazwy pliku.
- Jeśli subskill nie jest dostępny w danym narzędziu, otwórz jego `SKILL.md` dostępnym mechanizmem Skills lub użyj powiązanej karty repozytoryjnej. Nie twierdź, że specjalista został uruchomiony, jeżeli wykonano tylko odczyt pliku.
