# YetAnotherCyclingSim — roadmapa

**Wersja:** 0.1  
**Status:** Draft  
**Tryb pracy:** 11–20 godzin tygodniowo  
**Cel krótkoterminowy:** grywalna wersja od startu do mety  
**Cel docelowy:** pełne MVP opisane w PRODUCT_REQUIREMENTS.md

## Zasady pracy

1. Każdy etap kończy się działającym rezultatem.
2. Nie rozpoczynamy kolejnego dużego modułu, dopóki obecny nie działa.
3. Najpierw poprawność, później wygląd i optymalizacja.
4. Kod generowany przez AI musi zostać uruchomiony i sprawdzony.
5. Jedna zmiana logiczna powinna odpowiadać jednemu commitowi.
6. Nie kupujemy assetów bez konkretnego zastosowania.
7. Nie dodajemy funkcji spoza wymagań MVP.
8. Co tydzień przygotowujemy działającą wersję projektu.
9. Płynność mierzymy regularnie na komputerze referencyjnym.
10. Każdy ważny wzór fizyczny otrzymuje test automatyczny.
11. Performance jest kontraktem inżynierskim, nie końcowym etapem „optymalizacji”.
12. Projektujemy tanie ścieżki skalowania wcześnie, ale optymalizujemy dopiero na podstawie pomiarów.
13. Regresje czasu klatki, pamięci, shaderów, builda lub cooka porównujemy z zapisanym baseline'em; nie oceniamy ich wyłącznie „na oko”.
14. Każdy zewnętrzny asset lub pakiet musi mieć przypisany etap, zastosowanie i status licencji zgodnie z [`ASSET_PLAN.md`](ASSET_PLAN.md).

## Realistyczne oczekiwania czasowe

Plan 12-tygodniowy jest wariantem ambitnym.

Przy braku wcześniejszego doświadczenia pełne MVP może wymagać więcej czasu. Po 12 tygodniach priorytetem jest kompletna i grywalna jazda, nawet jeśli część grafiki, animacji, pogody lub eksportu FIT będzie wymagała dalszego dopracowania.

Zakresu nie zwiększamy bez aktualizacji dokumentu wymagań i roadmapy.

## Plan assetów

Szczegółowa lista potrzebnych assetów, kolejność ich pozyskiwania oraz dwa rejestry — **Source Asset Ledger** i **Technical UE Asset Ledger** — znajdują się w [`ASSET_PLAN.md`](ASSET_PLAN.md). Technical UE assets (np. PCG Graph, Control Rig, IK Rig, Niagara, MetaSound) są pełnoprawnymi deliverables produkcyjnymi, mimo że nie są kupowanymi paczkami.

## Plan narzędzi i pluginów Unreal Engine

Pluginy i narzędzia UE włączamy etapami, dokładnie tak samo jak assety. Każdy plugin musi mieć konkretny cel, przypisany etap oraz własną walidację; nie aktywujemy dużych zestawów funkcji „na zapas”.

Źródłem prawdy dla planu integracji jest [`UNREAL_TOOLING_PLUGIN_PLAN.md`](UNREAL_TOOLING_PLUGIN_PLAN.md).

Najważniejsze bramki:

| Etap | Tooling / plugin gate |
|---|---|
| **3G** | PCG, Editor Scripting Utilities, Geometry Script; PCG Geometry Script Interop tylko gdy potrzebny do konkretnego graphu; PCGToolset dopiero po zielonym MCP smoke |
| **3G / #85** | db-lyon `ue-mcp` pozostaje warstwą orkiestracji/guards/flows; oficjalny UE 5.8 Unreal MCP / Toolset Registry może być wykorzystywany przez tę warstwę, ale nie uruchamiamy na początku dwóch niezależnych MCP serverów |
| **6** | Control Rig + IK Rig + FullBodyIK; opcjonalnie Skeletal Mesh Editing Tools i Control Rig Modules po realnym zapotrzebowaniu |
| **7** | opcjonalnie Scriptable Tools Editor Mode, jeśli własny panel/tryb worldgen przyspiesza pracę względem flows |
| **8** | Niagara dla VFX oraz MetaSounds dla parametrycznego audio |
| **opcjonalnie 3G/7** | Water + Landmass tylko jeśli jezioro/rzeka pozostają w art direction i uzasadniają koszt subsystemu |

Assety wchodzą etapami, a nie jako osobny wielki art-pass:

| Etap | Asset gate |
|---|---|
| **3G** | landscape/ground baseline, vegetation, rocks/cliffs, atmosphere/sky/fog; bez obowiązku zakupu, jeśli natywne/darmowe zasoby wystarczą |
| **4** | wyłącznie lekkie debug/guidance decals potrzebne do mechaniki zakrętów |
| **5** | font i minimalny zestaw ikon HUD |
| **6** | jeden produkcyjny rider + jeden road bike + strój/kask + rig/retargeting |
| **7** | właściwy environment art pass: vegetation, rocks, road dressing, alpine buildings, roadside props, kilka pojazdów/scenek życia |
| **8** | wet-weather VFX oraz cycling/nature audio |
| **10** | asset freeze; wyłącznie polish i braki blokujące spójność/czytelność MVP |
| **Po MVP** | tłumy, traffic, zwierzęta, wiele rowerów/ubrań i kolejne regiony |

## Równoległa praca biuro–dom

Prace prowadzone są na dwóch komputerach: biurowym (dokumentacja, Git, lekki kod, testy Pythona, bez Unreal Engine) i domowym (build projektu UE, testy automatyzacji, walidacja wydajności).

- Jednocześnie mogą istnieć co najwyżej dwie niescalone gałęzie implementacyjne.
- Równoległa praca jest dozwolona wyłącznie w ramach bieżącego etapu roadmapy.
- Zadania równoległe muszą być od siebie niezależne.
- Gałąź równoległa nie może korzystać z API, plików źródłowych, assetów ani zachowań, które wprowadza dopiero inna niescalona gałąź.
- Każde zadanie korzysta z jednego issue i jednej dedykowanej gałęzi: recenzja → commit → push → PR → automatyczne scalenie po spełnieniu wymaganych bramek i walidacji.
- Checkpoint przygotowany na komputerze biurowym może zostać zacommitowany i wypchnięty po recenzji, ale raport musi jawnie oznaczać `Unreal validation pending`.
- Pull Request zawierający kod C++ UE, assety UE albo zmiany integracyjne nie może zostać otwarty, dopóki odpowiedni build projektu UE i testy automatyzacji nie przejdą na komputerze domowym.
- Pull Requesty zawierające wyłącznie dokumentację oraz inne zmiany niemające wpływu na build UE nie wymagają walidacji w Unreal Engine.
- Od 2026-09-23 obowiązuje stała zgoda właściciela produktu na automatyczne scalanie: PR może zostać scalony bez osobnej komendy `scal`, jeżeli zakres jest zatwierdzony, wszystkie wymagane walidacje i bramki CI są zielone, nie ma nierozwiązanych uwag ani blockerów, a PR jest mergeable i nie jest draftem.
- Stała zgoda na merge nie omija walidacji: nie wolno automatycznie scalać przy brakującym wymaganym proofie UE/home-PC, oczekującej lub czerwonej bramce, nierozwiązanym review/blockerze, konflikcie/drafcie ani gdy właściciel jawnie każe wstrzymać merge.
- Po niepowodzeniu walidacji nie wolno osłabiać wymagań ani testów; najpierw trzeba zdiagnozować przyczynę.
- Prac z kolejnych etapów roadmapy nie rozpoczynamy przed spełnieniem kryteriów ukończenia obecnego etapu.
- Kompilacja UE, integracja z edytorem, walidacja assetów i wydajności pozostają odpowiedzialnością komputera domowego, gdy na komputerze biurowym nie ma Unreal Engine.
- Docelowo komputer domowy jest kontrolowanym self-hosted runnerem GitHub Actions dla zaufanych workflow UE. Do czasu ukończenia #24 obowiązuje ręczne uruchamianie proofów; podczas Phase 1 #24 dozwolony jest wyłącznie ręczny `workflow_dispatch`, bez triggera na dowolny `pull_request`.

Gałęzie wyłącznie dokumentacyjne nie wliczają się do limitu dwóch gałęzi implementacyjnych.

---

# Etap 0 — fundament projektu

**Planowany czas:** tydzień 1

## Zadania

- [x] Utworzenie repozytorium GitHub (obecnie publicznego).
- [x] Dodanie `.gitignore` dla Unreal Engine.
- [x] Utworzenie dokumentu wymagań.
- [x] Utworzenie roadmapy.
- [x] Konfiguracja Git LFS.
- [x] Utworzenie zasad pracy dla asystentów AI.
- [ ] GitHub Project `YACS — MVP` skopiowany 1:1 z boardu 4VELO; aktualny source ma statusy `Backlog` / `Ready` / `In progress` / `In review` / `Blocked` / `Done`, a automatyzacja repo steruje `Backlog` / `In progress` / `In review` / `Done`. Bootstrap #88 porównuje układ ze źródłem zamiast hardkodować liczbę kolumn; po poprawce trzeba ponownie uruchomić jednorazowy bootstrap.
- [x] Instalacja wymaganych narzędzi na komputerze domowym.
- [x] Utworzenie projektu Unreal Engine 5.
- [x] Uruchomienie pustego projektu na komputerze referencyjnym.

**Notatka statusowa:** na komputerze referencyjnym udało się zbudować projekt
UE 5.8 w trybie C++ (edytor, Windows) oraz uruchomić pusty projekt
YetAnotherCyclingSim.

**Jawny dług infrastrukturalny (nie blokuje bieżącego 3G):**

- #22 — włączyć pozostałe ustawienia bezpieczeństwa GitHub i ochronę `main`; API nadal raportuje `main.protected = false`.
- #24 — wdrożyć prawdziwy Windows/Unreal Engine build + Automation na domowym self-hosted runnerze. **Teraz realizujemy Phase 1:** bezpieczny ręczny `workflow_dispatch` na dedykowanej etykiecie `yacs-ue58`, bez automatycznego uruchamiania kodu z PR-ów i bez wpinania joba do `Aggregate CI gate`. Stage 3G / #80 będzie pierwszym canary. Pełny plan: [`UNREAL_SELF_HOSTED_RUNNER_PLAN.md`](UNREAL_SELF_HOSTED_RUNNER_PLAN.md).
  - **Odroczony milestone operacyjny — dopiero przed Phase 2:** zastąpić ręczne uruchamianie `run.cmd` kontrolowanym autostartem runnera przez Windows Task Scheduler pod dedykowanym kontem runnera. Nie blokuje Phase 1 ani Stage 3G. Przed włączeniem trusted automatic UE execution wymagany jest reboot proof: restart hosta → runner sam wraca online → odbiera testowy job → build/Automation oraz co najmniej jeden workload wymagający interaktywnej sesji/GPU nadal przechodzą. Klasyczna usługa Windows nie jest domyślną ścieżką dla workloadów visual/GPU; można ją rozważyć wyłącznie po osobnym proofie kompatybilności.
- #23 — ekstrakcja wspólnego CI do `engineering-platform` jest ukończona i zamknięta.

## Kryterium ukończenia

- Repozytorium można sklonować na obu komputerach.
- Dokumentacja jest dostępna w repozytorium.
- Pusty projekt UE5 uruchamia się bez błędów.
- Projekt można zbudować na Windows.

---

# Etap 1 — prototyp fizyki poza grafiką

**Planowany czas:** tydzień 1–2

**Status:** ukończony

## Cel

Stworzyć testowalny model jazdy, zanim powstanie docelowa trasa i grafika.

## Zadania

- [x] Zdefiniowanie jednostek wszystkich parametrów.
- [x] Zdefiniowanie danych wejściowych i wyjściowych silnika fizycznego.
- [x] Implementacja masy kolarza i roweru.
- [x] Implementacja mocy i kadencji testowej.
- [x] Implementacja grawitacji.
- [x] Implementacja oporu toczenia.
- [x] Implementacja oporu aerodynamicznego.
- [x] Implementacja wiatru.
- [x] Implementacja przyspieszania i toczenia.
- [x] Zastosowanie stałego kroku czasowego.
- [x] Dodanie testów dla podjazdu, płaskiego odcinka i zjazdu.
- [x] Dodanie prostego rejestru wyników symulacji.

**Uwaga:** Referencyjny pakiet Pythona w katalogu `physics_reference/`
(kontrakty danych, siły, stały krok czasowy i testy jednostkowe) jest
ukończony i przechodzi **260 testów automatycznych**. Port C++ do Unreal
Engine jest ukończony: zawiera kontrakty danych, siły oporu,
deterministyczny krok symulacji oraz testy dynamiki długookresowej.
Budowa edytora UE 5.8 (Windows, Development) kończy się sukcesem,
a wszystkie cztery testy automatyczne `CyclingPhysics` przechodzą.
Etap 1 dostarcza czyste obliczenia ze stałym krokiem czasowym. Akumulator
czasu w trakcie gry, który uniezależnia rozgrywkę od zmiennego FPS, został
następnie zaimplementowany i przetestowany w ramach etapu 2. Prototypy Pythona dotyczące trasy, pogody
i zakrętów nie oznaczają jednak ukończenia późniejszych etapów Unreal
Engine — te etapy nadal wymagają implementacji i weryfikacji w UE5.

## Kryterium ukończenia

Dla ustalonych parametrów symulator oblicza powtarzalną prędkość i dystans, a wszystkie testy przechodzą automatycznie.

---

# Etap 2 — pierwszy grywalny prototyp UE5

**Planowany czas:** tydzień 2–3  
**Status:** ukończony

## Cel

Połączyć wejście testowe, fizykę i ruch obiektu po prostej trasie.

## Zadania

- [x] Utworzenie podstawowej mapy testowej.
- [x] Utworzenie drogi opartej na spline.
- [x] Dodanie tymczasowego obiektu reprezentującego rower.
- [x] Poruszanie obiektu zgodnie z wynikiem silnika fizycznego.
- [x] Sterowanie mocą i kadencją z klawiatury.
- [x] Dodanie panelu diagnostycznego.
- [x] Dodanie zatrzymania i ponownego uruchomienia jazdy.
- [x] Dodanie stałego kroku fizyki niezależnego od FPS.
- [x] Pomiar liczby FPS i czasu klatki.

### Domknięte transze architektoniczne Stage 2

- [x] **2.2.1 — #17:** `FCyclingSimulationSession` — czysty, testowalny C++ spinający `RiderInputController`, parametry kolarza/środowiska i `FixedStepRunner`; konfiguracja oraz operacje fallible są transakcyjne, reset i deterministyczny rerun są objęte Automation. Ta transza została wcześniej zaimplementowana i scalona, ale nie była jawnie zapisana w roadmapie.

**Dowód ukończenia:** #17, #44, #47, #48 oraz końcowy proof #49 / PR #59.  
Stage 2 zakończył się zielonym buildem i Automation, realnym PIE proof, deterministycznym frame-pacing proof oraz bazowym pomiarem wydajności 1920×1080 na komputerze referencyjnym.

## Kryterium ukończenia

Użytkownik może przejechać prostą trasę, zmieniając moc i kadencję, a prędkość wynika z modelu fizycznego.

---

# Etap 3 — trasa testowa i profil wysokości

**Planowany czas:** tydzień 3–5  
**Status:** ukończony; Stage 4 aktywny

## Cel

Stworzyć pełny przebieg fikcyjnej trasy alpejskiej i doprowadzić jej prototypową prezentację do uzgodnionego poziomu referencyjnego przed rozpoczęciem mechaniki zakrętów.

## Plan wykonawczy

Stage 3 jest realizowany kolejno:

1. **3A — #53:** route context i granice rozwiązywane na poziomie każdego fixed-step — **ukończone / PR #70**.
2. **3B — #64:** port profilu `ALPINE_JOURNEY` do czystego modelu domenowego Unreal — **ukończone / PR #71**.
3. **3C — #65:** pełny ciągły spline 10 km oraz deterministyczne wyznaczanie nachylenia z geometrii — **ukończone / PR #74**.
4. **3D — #66:** integracja runtime, start/sektory/meta i deterministyczne crossing events — **ukończone / PR #75**.
5. **3E — #67:** minimalny teren oraz pełny start-to-finish proof Stage 3 — **ukończone / PR #78**.
6. **3F — PR #79:** utrwalenie pełnego stanu mapy, materiałów drogi/terenu i wizualnego baseline'u — **ukończone**.
7. **3G — #80:** Reference Environment Pass — dolina, warstwowe góry, kontrolowany las, atmosfera/oświetlenie i porównywalny BEFORE/AFTER proof — **ukończone / PR #155**.
8. **3G-MCP — #85:** kontrolowany spike `db-lyon/ue-mcp` jako warstwa wykonawcza dla generowania świata — **odroczony do Stage 7; nie blokuje Stage 4**.

Mechaniki techniki zakrętów ze Stage 4 nie rozpoczynamy przed zielonym proofem 3G.

## Zadania rdzenia Stage 3

- [x] Zaprojektowanie profilu 20–30-minutowej jazdy.
- [x] Utworzenie przebiegu od doliny do wysokich gór.
- [x] Dodanie podjazdów, zjazdów i wypłaszczeń.
- [x] Dodanie zakrętów o różnych promieniach.
- [x] Obliczanie nachylenia z geometrii trasy.
- [x] Utworzenie punktów startu, sektorów i mety.
- [x] Dodanie podstawowego terenu.
- [x] Sprawdzenie ciągłości drogi i braku gwałtownych zmian nachylenia.
- [x] Pierwszy pełny przejazd od startu do mety.
- [x] Zapisać Stage 3 baseline czasu lokalnego build/proof dla bieżącego małego projektu, bez wymuszania pełnego cooka przy każdej zmianie.
- [x] Potwierdzić granicę domenową: wynik symulacji trasy/jazdy nie zależy od `AActor`, renderingu ani transformu presentation jako źródła prawdy.

**Dowód ukończenia rdzenia:** PR #70, #71, #74, #75 i #78. PR #78 raportuje 10 km trasy, zielony pełny proof, Map Check 0/0, save/reopen oraz reprezentatywny proof 1080p. PR #79 utrwala pełny stan mapy i materiałów Stage 3F na `main`.

## 3G — Reference Environment Pass

- [ ] Ukształtować spójną dolinę otaczającą drogę zamiast czytelnych jako osobne kafle podpór terenu.
- [ ] Zbudować kilka planów gór z wyraźną głębią i atmospheric perspective.
- [ ] Poprawić kontrolowaną, deterministyczną gęstość lasu w sektorze leśnym.
- [ ] Uporządkować przejście materiałów/kolorystyki: meadow → forest → high Alpine.
- [ ] Dodać wodę w dolinie, jeżeli poprawia uzgodnioną kompozycję bez tworzenia dużego nowego subsystemu.
- [ ] Poprawić lighting / sky / fog przy zachowaniu czytelności drogi.
- [ ] Wykonać porównywalny BEFORE/AFTER capture w 1200 m, 4900 m i 8000 m.
- [ ] Potwierdzić build, Automation, Map Check, save/reopen, LFS/fresh-checkout i podstawowy 1080p performance sanity na komputerze referencyjnym.

### Tooling gate 3G

- [ ] Włączyć natywny UE plugin **PCG** jako podstawowy system proceduralnego rozmieszczania vegetation/rocks/roadside dressing.
- [ ] Włączyć **Editor Scripting Utilities** jako uzupełnienie istniejącego `PythonScriptPlugin` dla bezpiecznej automatyzacji edytora.
- [ ] Włączyć **Geometry Script** dla generowania, analizy i modyfikacji geometrii pomocniczej; traktować jego API jako Beta i nie uzależniać od niego autorytatywnej fizyki/trasy.
- [ ] Włączyć **PCG Geometry Script Interop** tylko wtedy, gdy pierwszy graph faktycznie potrzebuje przepływu PCG ↔ Dynamic/Static Mesh; nie jest warunkiem samego startu PCG.
- [ ] Po zielonym #85 MCP smoke ocenić eksperymentalny **PCGToolset** UE 5.8 do tworzenia/modyfikacji PCG Graphów przez agenta.
- [ ] **Water/Landmass** pozostawić wyłączone do decyzji, że jezioro/rzeka są częścią zaakceptowanej kompozycji 3G.
- [ ] Pierwszy PCG proof ma być editor-time, deterministyczny i ograniczony do jednego sektora; runtime PCG nie jest wymaganiem MVP.
- [ ] PCG może konsumować route spline/WorldSpec jako constraints, ale nie może stać się źródłem prawdy dla przebiegu trasy.
- [ ] Zbudować i zarejestrować w Technical UE Asset Ledger pierwszy zestaw: `PCG_RouteExclusion`, `PCG_Valley`, `PCG_Forest`, `PCG_HighAlpine`; każdy przechodzi deterministic regenerate/proof zanim dostanie status `validated`.
- [ ] Authoring assets PCG przechowywać poza `/Game/Generated/YACS/**`; katalog `Generated` jest wyłącznie dla odtwarzalnych outputów generatora.

### Asset gate 3G

Na tym etapie wolno wprowadzić tylko assety potrzebne do uzyskania referencyjnego środowiska: bazowe landscape/ground materials, vegetation, rocks/cliffs oraz atmosferę. To nie jest jeszcze finalny art pass Stage 7. Zakup paczki jest uzasadniony wyłącznie wtedy, gdy natywne UE/darmowe zasoby nie pozwalają osiągnąć spójnego baseline'u. Szczegóły: [`ASSET_PLAN.md`](ASSET_PLAN.md).

## Kryterium ukończenia

Rdzeń Stage 3 jest ukończony: całą trasę można przejechać bez przerwania, błędu pozycji lub opuszczenia drogi; baseline build/proof jest zapisany, a domenowa symulacja pozostaje niezależna od presentation.

### 3G-MCP — kontrolowana warstwa world generation (#85)

UE-MCP jest narzędziem deweloperskim dla Stage 3G i późniejszego Stage 7, a nie nowym źródłem prawdy dla trasy.

- [ ] Przypiąć stabilne `db-lyon/ue-mcp` i uruchomić bridge na UE 5.8.2.
- [ ] Zachować Stage 3 route profile / geometry / spline / fixed-step simulation jako warstwę autorytatywną.
- [ ] Wprowadzić `WorldSpec` z deterministycznym seedem i jawnymi granicami biome/set-dressing.
- [ ] Zacząć od read-only inspection oraz transient actor proof, którego nie da się zapisać do mapy.
- [ ] Włączyć trwałe generowanie dopiero po zielonym bridge/build/Automation proof i po aktywowaniu generated-content guard.
- [ ] Docelowe trwałe outputy world generation ograniczyć do `/Game/Generated/YACS/**`.
- [ ] Nie wystawiać agentowi escape hatchy `execute_python` / `execute_command` w początkowym surface.
- [ ] Reużyć istniejące BEFORE/AFTER proofy 1200 m / 4900 m / 8000 m.

Szczegóły architektury i plan wdrożenia: [`UE_MCP_WORLD_GENERATION.md`](UE_MCP_WORLD_GENERATION.md).

**Warunek przejścia do Stage 4:** spełniony przez PR #155. Finalny trusted self-hosted proof: build ✅, Automation 53/53 ✅, Map Check 0/0 ✅, LFS/fresh-checkout ✅, trzy porównywalne visual captures ✅, cleanup ✅.

**Canary infrastrukturalny:** Stage 3G jest pierwszym rzeczywistym workloadem dla Phase 1 #24. Jeżeli runner zostanie zarejestrowany przed finalnym proofem 3G, authoring/build/Automation/capture mogą zostać wykonane przez ręczny workflow na home PC. Nie zmienia to kryteriów 3G: wynik musi być przypięty do dokładnego SHA, artefakty `.uasset`/`.umap` muszą wejść przez Git LFS, a wizualny AFTER proof nadal podlega review.

---

# Etap 4 — technika pokonywania zakrętów

**Planowany czas:** tydzień 5–7  
**Status:** w toku — Stage 4A / #156

## Cel

Wprowadzić autorską mechanikę oceniającą odpuszczenie i ponowne rozpoczęcie pedałowania.

## Plan wykonawczy

1. **4A — #156:** czysty C++ cornering domain contract z parity do Python reference model — **w toku**.
2. **4B:** route corner context — krzywizna/promień, corner-ahead, entry/apex/exit i limity gripu per fixed-step.
3. **4C:** technique + consequences — spięcie mocy/kadencji z wide-line, utratą prędkości i controlled slip; bez upadków w MVP.
4. **4D:** guidance + assists — linia przejazdu, markery entry/apex/exit, grip warning i poziomy asysty jako presentation-only.
5. **4E:** deterministyczny full-route corner proof dla reprezentatywnych zakrętów oraz suchej/mokrej nawierzchni.

## Zadania

- [ ] Obliczanie krzywizny drogi.
- [ ] Określenie strefy wejścia, apeksu i wyjścia.
- [ ] Obliczanie zalecanej prędkości.
- [ ] Analiza momentu zmniejszenia mocy.
- [ ] Analiza momentu wznowienia pedałowania.
- [ ] Automatyczny wybór toru przejazdu.
- [ ] Wizualna linia przejazdu i strefy entry/apex/exit na drodze.
- [ ] Kontekstowe ostrzeżenia o przyczepności i trudności zakrętu.
- [ ] Poszerzenie toru po błędzie.
- [ ] Utrata prędkości po błędzie.
- [ ] Kontrolowany uślizg bez upadku.
- [ ] Wpływ mokrej nawierzchni.
- [ ] Ocena każdego zakrętu.
- [ ] Regulowane poziomy asysty.
- [ ] Testy powtarzalności wyników.

### Asset gate Stage 4

Nie planujemy zakupu produkcyjnej paczki graficznej. Dopuszczalne są proste decals/markery potrzebne do czytelnego pokazania entry/apex/exit, linii przejazdu, grip warning i debug guidance. Finalne road dressing i decals należą do Stage 7.

## Kryterium ukończenia

Różne decyzje dotyczące mocy i kadencji dają widocznie różne, ale powtarzalne rezultaty przejazdu zakrętu.

---

# Etap 5 — HUD i przebieg sesji

**Planowany czas:** tydzień 6–8

## Zadania

- [ ] Ekran konfiguracji jazdy.
- [ ] Ustawienia masy, CdA i Crr.
- [ ] Wybór poziomu asysty.
- [ ] Moc i kadencja.
- [ ] Prędkość.
- [ ] Nachylenie.
- [ ] Czas i dystans.
- [ ] Pozostały dystans.
- [ ] Profil wysokości.
- [ ] Pozycja na profilu.
- [ ] Informacje o nadchodzącym zakręcie.
- [ ] Ocena przejazdu zakrętu.
- [ ] Ekran mety i podsumowania.
- [ ] Możliwość ograniczenia lub ukrycia HUD-u.
- [ ] Dobrać produkcyjny font i minimalny zestaw ikon/SVG HUD zgodnie z `ASSET_PLAN.md`; nie kupować pełnego UI kitu bez uzasadnienia.

## Kryterium ukończenia

Użytkownik może rozpocząć, ukończyć i podsumować całą sesję bez korzystania z narzędzi deweloperskich.

---

# Etap 6 — kamery, kolarz i rower

**Planowany czas:** tydzień 7–9

## Założenie animacji kolarza

Mocap jest bazową warstwą naturalnego ruchu, a nie zbiorem gotowych animacji dla
każdej sytuacji. Docelowa poza kolarza ma wynikać z parametrów jazdy przez
warstwowanie animacji, `Control Rig`, IK i proceduralne offsety. Pozwala to
obsłużyć zjazd, zakręty, zmianę chwytu lub geometrii roweru bez nagrywania
osobnego mocapu dla każdego przypadku.

Minimalny przepływ Stage 6:

`base mocap / cadence animation -> additive cycling pose -> procedural Control Rig -> hand/foot IK -> final rider pose`.

## Zadania

- [ ] Jeden model roweru.
- [ ] Jeden model kolarza.
- [ ] Dopasowanie kolarza do roweru.
- [ ] Import szkieletu kolarza i przygotowanie retargetingu bazowego mocapu.
- [ ] Animacja pedałowania zależna od kadencji.
- [ ] Toczenie bez pedałowania.
- [ ] Bazowe blendowane pozycje: neutral seated, aggressive/aero, descending tuck, standing/sprint i cornering.
- [ ] Pochylenie roweru i ciała w zakrętach sterowane stanem fizyki zamiast sztywną animacją.
- [ ] `Control Rig` / proceduralne offsety dla miednicy, kręgosłupa, głowy, barków i łokci.
- [ ] IK dłoni do punktów chwytu kierownicy oraz IK stóp do pedałów, niezależne od bazowego mocapu.
- [ ] Stabilizacja głowy i look-ahead po spline trasy, tak aby kolarz patrzył przez zakręt.
- [ ] Rozdzielenie warstwy prezentacji od konkretnego mesha/szkieletu, aby model kolarza można było później podmienić bez przepisywania logiki jazdy.
- [ ] Kamera za kolarzem.
- [ ] Kamera z perspektywy kierownicy.
- [ ] Przełączanie kamer podczas jazdy.
- [ ] Stabilizacja kamer na nierównościach i zakrętach.
- [ ] Dodać interpolation presentation pomiędzy stanami fixed-step bez sprzężenia zwrotnego do fizyki.
- [ ] Zmierzyć baseline kosztu jednego ridera: Animation Blueprint / Control Rig / IK / skeletal mesh na komputerze referencyjnym.
- [ ] Utrzymać animation/presentation API tak, aby późniejsze ograniczenie update rate przez significance nie wymagało zmian w fizyce jazdy.

## Parametry proceduralnej pozy

Warstwa prezentacji może korzystać m.in. z: `Speed`, `Grade`,
`CornerRadius` / `LateralAcceleration`, `Cadence`, `Braking`,
`Technique` i `AeroLevel`. Wynikiem są wyłącznie parametry prezentacji,
np. rotacje/przesunięcia `Pelvis`, `Spine`, `Head`, `Elbow`, `Knee`
oraz cele IK `Hand` / `Foot`; system animacji nie może zmieniać wyniku fizyki.

### Tooling gate Stage 6

- [ ] Włączyć **Control Rig** dla proceduralnej warstwy pozy kolarza.
- [ ] Włączyć **IK Rig** dla retargetingu oraz definiowania goal/solver chain dla ridera.
- [ ] Włączyć **FullBodyIK** dla wielu jednoczesnych celów dłonie/pedały/głowa/miednica i proceduralnych korekt całego ciała.
- [ ] Ocenić **Skeletal Mesh Editing Tools** tylko jeśli naprawy skinning/rigging w UE realnie oszczędzają eksport do Blendera.
- [ ] Ocenić **Control Rig Modules** dopiero po powstaniu pierwszego działającego minimalnego Control Riga; nie dodawać modułów przed pomiarem potrzeby.
- [ ] Zmierzyć koszt Control Rig + IK/FBIK na komputerze referencyjnym i zachować możliwość LOD/update-rate reduction bez wpływu na fizykę.
- [ ] Technical UE Asset Ledger musi objąć co najmniej `IK_Rider`, `RTG_CyclingMocap` i `CR_Cyclist`; status `validated` wymaga retarget proof oraz kontaktu dłoni/stóp w reprezentatywnych pozach.

### Asset gate Stage 6

To pierwszy obowiązkowy asset pass postaci: wybieramy i walidujemy **jeden** model kolarza oraz **jeden** road bike. Rider obejmuje minimalny strój/kask i skeleton/rig nadający się do retargetingu; rower powinien mieć rozdzielone elementy wymagające animacji (co najmniej koła i korba/pedały). Model z Tripo/Meshy jest dopuszczalny po review topologii, skali, materiałów i riggingu. Nie budujemy jeszcze katalogu rowerów ani ubrań.

## Kryterium ukończenia

Ruch kolarza, roweru i kamer jest płynny i zgodny z parametrami jazdy.
Zmiana kadencji, wejście w zakręt i przejście do zjazdu dają widoczną,
ciągłą zmianę pozy bez utraty kontaktu dłoni z kierownicą i stóp z pedałami.

---

# Etap 7 — świat i oprawa wizualna

**Planowany czas:** tydzień 8–11

## Zadania

- [ ] Podział świata na dolinę, las i wysokie góry.
- [ ] Materiały drogi i mokrej nawierzchni.
- [ ] Roślinność.
- [ ] Skały i teren wysokogórski.
- [ ] Mała miejscowość.
- [ ] Punkty charakterystyczne trasy.
- [ ] Życie w kilku przygotowanych lokalizacjach.
- [ ] System LOD, Nanite lub instancjonowania zależnie od assetu.
- [ ] Kontrola gęstości obiektów.
- [ ] Profile jakości grafiki.
- [ ] Testy 1080p/60 FPS na RTX 2070 Super.
- [ ] Zdefiniować i zmierzyć Wind/Animation LOD dla foliage; daleka roślinność nie może bez pomiaru ponosić kosztu pełnego WPO/wind.
- [ ] Wykonać Alpine Skyline / Streaming Proof: dolina → las → podjazd → odsłonięte góry, z kontrolą HLOD, pop-in, dziur świata i hitchy streamingu.
- [ ] Wprowadzić Material/Shader Permutation Contract: każdy nowy Static Switch wymagający dodatkowych permutacji musi mieć uzasadnienie; ciągłe stany pogody preferują parametry runtime, gdy to właściwe.
- [ ] Zebrać baseline GPU, Game Thread, Render Thread, RAM/VRAM i hitchy dla reprezentatywnych scen.
- [ ] Nanite, Virtual Texturing/RVT i inne cięższe technologie dobierać przez benchmark przed/po, nie jako domyślną regułę świata.

### Tooling gate Stage 7

- [ ] Rozszerzać istniejące PCG graphs/flows zamiast ręcznie stawiać masowe environment dressing.
- [ ] Rozważyć **Scriptable Tools Editor Mode** tylko wtedy, gdy własny panel/tryb typu „Generate YACS World” daje wyraźną przewagę nad nazwanymi MCP flows i zwykłymi Editor Utility workflows.
- [ ] Nie dodawać ciężkich world-building frameworków, jeżeli natywne PCG + Geometry Script + nasze flows pokrywają potrzebę.
- [ ] Każde nowe narzędzie świata musi respektować `/Game/Generated/YACS/**`, deterministyczny seed, route clearance i cleanup/regeneration contract.

### Asset gate Stage 7

To główny produkcyjny art pass środowiska. W tym etapie dobieramy/uzupełniamy: vegetation, rocks/cliffs, road/roadside props, asphalt/decals, modularne alpine buildings, village props, landmarks oraz ograniczony zestaw pojazdów i przygotowanych scenek życia. Preferujemy spójność zestawu landscape + vegetation + rocks nad liczbę różnych paczek. Nie wdrażamy pełnego traffic systemu.

Każdy płatny lub zewnętrzny pack trafia do Asset Ledger w [`ASSET_PLAN.md`](ASSET_PLAN.md) wraz z licencją, kosztem, etapem i wynikiem podstawowej walidacji wydajności.

## Kryterium ukończenia

Świat ma spójny alpejski charakter, a pełna trasa utrzymuje założony budżet wydajności.

---

# Etap 8 — dynamiczna pogoda i dźwięk

**Planowany czas:** tydzień 9–11

## Zadania

- [ ] Zaplanowany przebieg pogody.
- [ ] Opcjonalny tryb losowy.
- [ ] Zapisywane ziarno losowości.
- [ ] Wiatr wpływający na fizykę.
- [ ] Deszcz i moknięcie nawierzchni.
- [ ] Wpływ mokrej drogi na fizykę zakrętów.
- [ ] Dźwięki napędu i wolnobiegu.
- [ ] Dźwięki opon i hamowania.
- [ ] Wiatr zależny od prędkości i kierunku.
- [ ] Dźwięki deszczu, lasu, zwierząt i miejscowości.
- [ ] Testy wydajności podczas najcięższych warunków, w tym co najmniej dense foliage + deszcz + mokra droga + dynamiczne cienie na reprezentatywnym fragmencie.

### Tooling gate Stage 8

- [ ] Włączyć/zweryfikować **Niagara** jako podstawowy system VFX dla deszczu, sprayu, wind/debris i subtelnych efektów atmosferycznych.
- [ ] Włączyć/zweryfikować **MetaSounds** dla parametrycznego drivetrain/freehub/tyres/brakes/wind audio zależnego od stanu jazdy.
- [ ] Nie włączać eksperymentalnego MetaSounds feature set bez konkretnej potrzeby; bazowy MetaSound ma pierwszeństwo.
- [ ] Audio/VFX otrzymują parametry z gameplay/presentation, ale nie stają się źródłem prawdy dla fizyki.
- [ ] Zarejestrować i zwalidować w Technical UE Asset Ledger co najmniej `NS_Rain`, `NS_WheelSpray`, `MS_Drivetrain` i `MS_Wind`, z proofem GPU/audio odpowiednim dla typu assetu.

### Asset gate Stage 8

Wprowadzamy wyłącznie efekty i dźwięki potrzebne do działającej pogody i wiarygodnego roweru: rain/spray, wetness/puddles gdy uzasadnione, subtelne wind/debris particles, drivetrain/freehub/tyres/brakes oraz ambience deszczu, lasu i miejscowości. Najpierw wykorzystujemy natywne systemy UE; duży zewnętrzny weather framework wymaga osobnego dowodu, że rozwiązuje konkretną lukę.

## Kryterium ukończenia

Pogoda zmienia wygląd, dźwięk i fizykę, nie powodując niedopuszczalnych spadków płynności.

---

# Etap 9 — zapis sesji i eksport FIT

**Planowany czas:** tydzień 11–12

## Zadania

- [ ] Lokalny format zapisu sesji.
- [ ] Historia przejazdów.
- [ ] Automatyczne zabezpieczenie danych podczas jazdy.
- [ ] Podsumowanie zakrętów.
- [ ] Generowanie pliku FIT.
- [ ] Walidacja wygenerowanego pliku.
- [ ] Test importu FIT do co najmniej jednej zewnętrznej usługi.
- [ ] Obsługa błędu zapisu.

## Kryterium ukończenia

Ukończona aktywność jest dostępna lokalnie i może zostać wyeksportowana jako poprawny plik FIT.

---

# Etap 10 — stabilizacja MVP

**Planowany czas:** od tygodnia 12

## Zadania

- [ ] Pełny test trasy od startu do mety.
- [ ] Test różnych poziomów mocy.
- [ ] Test wszystkich poziomów asysty.
- [ ] Test suchej i mokrej nawierzchni.
- [ ] Test obu kamer.
- [ ] Test zapisu i eksportu FIT.
- [ ] Profilowanie CPU, GPU i pamięci.
- [ ] Zebrać końcowy MVP baseline: Game Thread, Render Thread, GPU, RAM/VRAM, hitch percentiles/spikes i streaming stalls podczas pełnego przejazdu.
- [ ] Zebrać baseline build pipeline: C++ compile, shader compile, cook, package/stage, total build time i rozmiar artefaktu tam, gdzie pomiar jest dostępny.
- [ ] Wykonać packaged PSO/first-use stutter proof dla reprezentatywnego materiałowo pełnego przejazdu.
- [ ] Porównać końcowe wyniki 1080p/60 z wcześniejszymi baseline'ami i wyjaśnić istotne regresje.
- [ ] Usunięcie błędów blokujących.
- [ ] Przygotowanie wersji Windows.
- [ ] Instrukcja instalacji i uruchomienia.
- [ ] Oznaczenie wydania `v0.1.0-mvp`.
- [ ] Zamknąć Asset Ledger dla MVP: źródło/licencja/status wszystkich użytych zewnętrznych assetów i brak nieużywanych importów „na zapas”.
- [ ] Asset freeze: nowe zakupy tylko wtedy, gdy rozwiązują konkretny blocker jakości/czytelności lub regresję, której nie można rozsądnie naprawić istniejącymi zasobami.

## Kryterium ukończenia

Spełnione są wszystkie kryteria z dokumentu PRODUCT_REQUIREMENTS.md, a aplikację można uruchomić na innym komputerze z Windows bez środowiska programistycznego.

---

# Po MVP

Kolejność orientacyjna:

1. Obsługa BLE/FTMS i pierwszego prawdziwego trenażera.
2. Sterowanie oporem.
3. Integracja ze Stravą.
4. Import i generowanie kolejnych tras.
5. Treningi strukturalne.
6. Ghost i porównywanie przejazdów.
7. Multiplayer.
8. Pack Dynamics: drafting, automatyczne pozycjonowanie, wyprzedzanie i fizyka grupy.
9. Kolejne platformy treningowe.
10. Inne systemy operacyjne.

### Skalowanie riderów przed pełnym multiplayerem

Zanim architektura zostanie uznana za gotową na duży peleton, wymagany jest `Crowd Scaling Spike` z pomiarami dla:

- 1 rider;
- 10 riderów;
- 50 riderów;
- 100 riderów;
- 300 riderów jako stress probe.

Dla każdego poziomu mierzymy co najmniej Game Thread, Render Thread, GPU, rider simulation time, animation cost, RAM/VRAM, hitching oraz później koszt sieci. 300 riderów nie jest wymaganiem MVP ani gwarantowanym targetem produktu — służy do znalezienia punktu załamania architektury.

Po MVP należy wprowadzić centralny `RiderSignificance` / Unified Rider Cost Policy sterujący oddzielnymi budżetami dla simulation update rate, animacji, IK, collision/physics detail, render/shadows, audio/UI oraz przyszłej network relevancy. Dokładne progi ustalamy wyłącznie na podstawie profilowania.

Jeżeli zwykła scentralizowana/batchowa reprezentacja stanów riderów przestanie skalować się wystarczająco dobrze, dopiero wtedy wykonujemy spike MassEntity/ECS. MassEntity nie jest wymaganiem MVP ani warunkiem rozpoczęcia multiplayera.

W przyszłym multiplayerze network update/relevancy korzysta ze wspólnych danych significance, ale gameplay relevance, visual relevance i session relevance pozostają rozdzielone. Wybór Iris vs Replication Graph pozostaje odroczony do aktualnej wersji UE i pomiarów.

### YACS Pose Lab / CyclingPoseController — narzędzie po MVP

Po ustabilizowaniu podstawowej warstwy animacji ze Stage 6 można zbudować
narzędzie deweloperskie minimalizujące ręczną pracę animatora.

Założenia:

- `CyclingPoseController` przyjmuje parametry jazdy, m.in. `Speed`, `Grade`,
  `CornerRadius` / `LateralAcceleration`, `Cadence`, `Braking`,
  `Technique` i `AeroLevel`;
- wyjściem są kontrolowane offsety miednicy, kręgosłupa, głowy, łokci i kolan
  oraz cele IK dla dłoni i stóp;
- `YACS Pose Lab` udostępnia podgląd i strojenie pozy w edytorze z operacjami
  `Save Pose`, `Mirror Pose` i `Export JSON`;
- pozycje można przygotowywać na podstawie pojedynczych klatek referencyjnych
  z nagrań rzeczywistych kolarzy, np. `Approach -> TurnIn -> Apex -> Exit`;
- późniejsza iteracja może półautomatycznie wyciągać punkty ciała lub kąty
  stawów z materiału referencyjnego, ale film jest źródłem biomechanicznej
  referencji, a nie źródłem fizyki gry;
- fizyka określa wymagany ruch roweru i wielkość pochylenia, a referencja
  określa relacje ciała, np. counter-lean głowy, pracę łokci i pozycję
  zewnętrznej nogi;
- system musi wspierać co najmniej zjazd, zakręty, aero, hamowanie,
  standing/sprint i późniejsze warianty zmęczenia;
- lewa/prawa wersja symetrycznej pozy powinna być generowana przez mirror,
  gdy nie wymaga osobnej biomechanicznej definicji;
- celem jest ograniczenie ręcznego ustawiania kości i liczby wymaganych
  nagrań mocap, nie zastąpienie walidacji wizualnej.

Pose Lab pozostaje narzędziem deweloperskim po MVP; Stage 6 zawiera tylko
minimalną warstwę runtime potrzebną do wiarygodnego single-player ridera.

### Pack Dynamics — założenia projektowe

Ten zakres jest planowany po stabilizacji single-player MVP.

- Gracz nie steruje bezpośrednio w lewo/prawo; moc i kadencja określają wysiłek i wynikającą z niego intencję prędkości.
- Tor boczny jest wybierany automatycznie na podstawie geometrii drogi, zajętości przestrzeni, dostępnych luk, ryzyka kolizji, draftu i ograniczeń trajektorii.
- Każda zmiana boczna musi mieć jawny `LateralIntent`; brak intencji oznacza utrzymanie stabilnej linii.
- System stosuje predykcyjne unikanie kolizji zamiast odpychania modeli po kontakcie.
- Twarde obszary rowerów/kolarzy nie mogą się przenikać; większe miękkie strefy służą do wcześniejszego planowania.
- Gdy wyprzedzenie nie jest możliwe, zawodnik pozostaje na kole zamiast przenikać przez model lub wykonywać sztuczny skok w bok.
- Solver nie może przypadkowo tworzyć trwałej pełnej „ściany” zawodników blokującej całą użyteczną szerokość drogi (`No Static Wall`).
- Solver nie może tworzyć stałego pustego pasa ani „VIP lane”; może wykorzystywać i rezerwować naturalnie istniejące lub przewidywane luki.
- `BOXED_IN` jest poprawny, gdy rzeczywista geometria i occupancy fizycznie uzasadniają brak przejazdu; chwilowe zajęcie całej szerokości drogi może być prawidłowe.
- `Passing Opportunity Negotiation` może rezerwować naturalną lukę i dopuszczać tylko małe korekty innych riderów, które same są uzasadnione avoidance/stabilnością — nie może rozpychać peletonu dla gracza.
- Rozpoczęty manewr ma commitment/hysteresis, aby wyeliminować bezcelowe myszkowanie lewo–prawo.
- Automatyczna zmiana toru jest ciągłą trajektorią z ograniczeniami prędkości bocznej, przyspieszenia, jerk i krzywizny.
- Animacja skrętu, yaw i pochylenie muszą wynikać z trajektorii, aby automatyczne prowadzenie było wizualnie wiarygodne.
- Pierwszeństwo jest deterministyczne: jadący z przodu domyślnie utrzymuje linię, a wyprzedzający odpowiada za znalezienie bezpiecznej luki.
- Docelowy subsystem obejmuje drafting, hold-wheel, anti-churn, overtaking, drop/bridge i pack cornering; crosswind/echelons oraz bardziej zaawansowana taktyka należą do późniejszych iteracji.
- Sąsiedztwo Pack Dynamics musi respektować topologię trasy, a nie tylko odległość XYZ; serpentyny, mosty, tunele i różne okrążenia nie mogą generować fałszywego draftu/kolizji.
- Planner stosuje twardą hierarchię: collision → road bounds → grip/kinematics → committed manoeuvre → pack safety → power intent → draft → comfort.
- Moc niewykorzystana podczas automatycznego ograniczenia prędkości nie może być magazynowana jako późniejszy boost; trafia do rozliczenia strat, np. `WastedEnergy`.
- Prediction horizon i safety margin muszą skalować się z prędkością i sytuacją.

### Road Guidance Overlay — rozwój po MVP

Road Guidance Overlay ma pozostać kontekstową warstwą informacyjną, a nie systemem sterowania.

Po wdrożeniu Pack Dynamics planowane są:
- `DRAFT_POCKET`;
- `HOLD_WHEEL`;
- `BOXED_IN`;
- `PASS_CORRIDOR_LEFT` / `PASS_CORRIDOR_RIGHT`;
- stan `SEARCHING_FOR_GAP` podczas wyszukiwania bezpiecznej możliwości wyprzedzenia;
- ostrzeżenia o zamykającej się luce;
- strefy kompresji grupy;
- sygnalizacja zwężeń i bocznego wiatru;
- wizualizacja stopnia pewności guidance.

Każdy overlay korzysta z już obliczonego stanu fizyki, trasy lub Pack Dynamics i nie może wpływać zwrotnie na wynik symulacji.

### Rider Technical Profile — rozwój po MVP

Po ustabilizowaniu Pack Dynamics można dodać deterministyczny profil umiejętności technicznych zawodnika.

Założenia:

- parametry fizyczne (np. masa, `CdA`, geometria postaci) zmieniają rzeczywiste możliwości fizyczne;
- cechy techniczne nie dają magicznych bonusów do prędkości, mocy ani przyczepności;
- należy rozdzielić `PhysicalCapability`, `PlayerTechnique` i `AutopilotProficiency`;
- progres może dotyczyć wyłącznie zachowań, na które użytkownik faktycznie miał wpływ; sukces wykonany wyłącznie przez autopilot nie może sam zwiększać skilla;
- `PackHandling` i `BikeHandling` przed implementacją muszą zostać sklasyfikowane jako rzeczywista technika użytkownika albo parametr autopilota, zamiast mieszać oba pojęcia;
- wynik manewru powinien zależeć od relacji `TechnicalDemand` do `TechnicalCapacity`, a nie od losowego rzutu procentowego;
- wysoka technika nie może łamać twardych ograniczeń geometrii, kolizji ani zasad Pack Dynamics;
- przyszły `PackTechniqueScore` może raportować m.in. draft efficiency, wheel holding, gap closures, wasted energy i missed passing opportunities.

### Skill balancing i progresja — wymagania po MVP

Przed implementacją progresji Rider Technical Profile należy:

- zagwarantować `Power Integrity`: skill nie może modyfikować `PowerWatts` ani tworzyć wirtualnych watów;
- utrzymać priorytet rzeczywistej mocy i fizyki nad progresją postaci;
- projektować skill jako redukcję strat i poprawę jakości decyzji automatycznego prowadzenia;
- unikać prostego grindu kilometrów, czasu gry i banalnych powtarzalnych sytuacji;
- premiować poprawne wykonanie scenariuszy o `TechnicalDemand` zbliżonym do `TechnicalCapacity`;
- zastosować diminishing returns i twarde limity wpływu bardzo wysokiego skilla;
- zbudować deterministyczny balancing harness dla scenariuszy `TechnicalDemand × TechnicalCapacity`;
- stroić krzywe później na podstawie telemetrii rzeczywistych jazd.

### Feedback dla mechanik bez naturalnych bodźców fizycznych

Przy implementacji zakrętów, Pack Dynamics, techniki i warunków środowiskowych należy jawnie identyfikować sytuacje, w których użytkownik trenażera nie otrzymuje bodźca obecnego podczas prawdziwej jazdy.

Dla takich sytuacji wymagany jest odpowiedni feedback wizualny, a opcjonalnie także dźwiękowy.

Priorytet prezentacji:
1. zachowanie świata i animacji;
2. oznaczenie na drodze lub w świecie;
3. dyskretny HUD;
4. tekst tylko jako ostateczne wsparcie.

Do kryteriów ukończenia odpowiednich systemów należy dodać walidację, czy użytkownik rozumie:
- co się wydarzyło;
- dlaczego automat zachował się w dany sposób;
- czy ograniczenie wynika z fizyki, geometrii, Pack Dynamics czy jego techniki;
- czy powinien zmienić moc lub kadencję.

Mechanika bez realnego odpowiednika haptycznego/kinestetycznego nie jest kompletna, jeśli jej kluczowy stan pozostaje niewidoczny dla gracza.

Przy kilku jednoczesnych sygnałach wymagany jest `GuidanceComposer`, który ustala priorytet i ogranicza wizualny clutter. Kolor nie może być jedynym nośnikiem znaczenia; wymagane są także różnice kształtu/wzoru/animacji oraz walidacja w różnych kamerach i warunkach pogodowo-oświetleniowych.

### Pack Dynamics Torture Harness — wymagania przed implementacją produkcyjną

Przed uznaniem Pack Dynamics za stabilny wymagany jest deterministyczny harness bez renderingu obejmujący ręczne edge case'y oraz masowo generowane warianty.

Obowiązkowe invariants:
- brak hard overlap;
- brak teleportów;
- brak wyjazdu poza dozwoloną drogę;
- brak niemożliwego lateral acceleration;
- brak trwałego reciprocal dance / oscillation;
- brak sztucznego deadlocku;
- brak energy banking;
- brak fałszywych interakcji pomiędzy różnymi segmentami/poziomami trasy;
- brak wymuszonego `VIP lane`;
- identyczny stan i wejścia dają identyczny wynik.

Harness musi zawierać co najmniej scenariusze: wspólna luka dla dwóch riderów, zamknięcie luki w trakcie passu, symetryczny deadlock, realne i sztuczne `BOXED_IN`, crosswind/echelon, hairpin, mokry zakręt, crest, szybki zjazd, wolny podjazd, stopped rider, merge/split grup, serpentyny/mosty/tunele, różne `lapIndex`, finish behavior oraz błędne/dropoutowe wejście mocy.

### Pack Dynamics v0.1 — spec freeze

Przed właściwą implementacją Pack Dynamics wymagane są następujące kontrakty:

- jawna `RiderPackStateMachine`;
- opisowy `PackPhaseModel`;
- `RouteOccupancyModel`;
- atomowy i deterministyczny `GapReservation`;
- `InputIntegrity` dla danych trenażera;
- debug/telemetry contract;
- deterministic replay;
- performance contract oparty na lokalnym neighborhood zamiast O(N²);
- rozdzielenie `PlayerTechnique` i `AutopilotProficiency`;
- competitive fairness policy;
- przyszły network authority contract;
- posture-aware occupancy;
- walidacja bicycle-like/non-holonomic kinematics dla każdej trajektorii lateralnej.

Po zapisaniu tych zasad spec Pack Dynamics v0.1 uznaje się za zamrożoną do czasu właściwego etapu po MVP.

Nowe pomysły dotyczące Pack Dynamics trafiają do backlogu, chyba że rozwiązują krytyczną lukę w istniejących invariants.

## Dokument kierunkowy po MVP

Założenia dotyczące budżetów runtime/build, streamingu świata, przyszłej sieci dróg, skalowania dużej liczby kolarzy oraz multiplayera opisuje
[`PERFORMANCE_MULTIPLAYER_ARCHITECTURE.md`](PERFORMANCE_MULTIPLAYER_ARCHITECTURE.md).

Dokument ten definiuje ograniczenia architektoniczne i edge case'y, ale nie przenosi
multiplayera ani otwartego świata do bieżącego zakresu MVP.

