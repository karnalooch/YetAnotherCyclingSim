---
name: yacs-houdini-world
description: "Prowadź generowanie i naprawę świata YetAnotherCyclingSim (YACS) według oryginalnych metod SideFX/Houdini. Używaj przy Sa Calobra, Passo Giau, DTM/HeightField/Landscape, Pegasus, maskach, cache, HDA, kaflach, szwach, proceduralnym detalu, klifach, drogach, roślinności i przekazaniu geometrii do Unreal. Łącz z yacs-materials-visual dla wyglądu oraz ze specjalistą runtime dla uruchomień UE; nie używaj do ogólnych pytań o Houdini poza YACS."
---

# YACS — Houdini i świat

## Zacznij od aktualnej decyzji

1. Odczytaj bieżący checkout/PR i SHA repozytorium `karnalooch/YetAnotherCyclingSim`, root `AGENTS.md`, aktualne decyzje w `docs/ROADMAP.md` oraz `docs/WORLD_BUILDING_BIBLE.md`. Sprawdź stan zadania i zależności przed wykonaniem późniejszego etapu.
2. Przeczytaj `docs/tooling/sidefx/README.md`, właściwą recepturę i [mapę źródeł](references/source-map.md). Traktuj datowane dowody jako wyniki przypisane do producenta, obszaru i plików; odśwież stan po przejęciu pracy.
3. Zastosuj zakres i zgody już udzielone w rozmowie. Nie domagaj się ponownego potwierdzenia zwykłej, autoryzowanej poprawki. Oddziel brak możliwości wykonania od braku zgody; dokończ niezależną pracę.
4. Określ jeden wynik roboczy: zmieniany graf/warstwa, pełny docelowy obszar, wejścia, odbiorca i kryterium sprawdzenia. Kontynuuj istniejący projekt i gałąź; nie twórz konkurencyjnego generatora lub PR wyłącznie z braku kontekstu.

## Zachowaj podział odpowiedzialności

Przekaż źródła GIS i pochodzenie do `$yacs-world-data`, route/earthworks do `$yacs-road-bob`, materiały do `$yacs-materials-visual`, uruchomienia UE do `$yacs-unreal-integration`, a kwalifikację dowodów do `$yacs-verify-evidence`, gdy zadanie wymaga tych domen. Zachowaj jeden wspólny cel i SHA.

- Używaj Houdiniego jako głównego wykonawcy proceduralnego świata. Zacznij od właściwego oryginalnego HIP/HDA i fragmentu tutoriala. Używaj Python/HOM do sterowania i pomiarów; nie ukrywaj w adapterze nowego algorytmu terenu, erozji lub dróg.
- Pozostaw geografię źródłom i World/domain Authorities. Zachowaj metry, CRS, orientację osi, wysokości, ważność danych oraz kanoniczne XY trasy. Materiał i dekoracja nie mogą nadać fikcji statusu pomiaru.
- Zachowaj BOB jako domenę drogi, earthworks i kontaktu, a kontrakty route/physics jako prawdę fizyczną. Recepturę drogi wybieraj w Houdinim dopiero w aktywnym zakresie drogowym.
- Stosuj PCG/PCGEx wyłącznie tam, gdzie wymaga tego wybrana integracja. Wykorzystuj Blender do przygotowania/inspekcji, Material Forge do wyglądu powierzchni, Labs do konkretnej brakującej operacji.
- Odczytuj zakres zamrożenia z aktualnej decyzji. Wyjątek dla nowego niezależnego kandydata nie upoważnia do globalnej wymiany zaakceptowanego świata. Nie zamrażaj na zawsze parametrów historycznej próby.

## Wykonaj recepturę ze źródła

1. Znajdź serię/lekcję w `docs/tooling/sidefx/catalog/README.md`. Otwórz oryginalny materiał; zapisz czas, checksum HIP/HDA, typ i wersję węzłów. Rozróżnij przeczytane napisy, obejrzane kadry i obejrzany film.
2. Rozwiąż ścieżki przez `workspace.json`, `YACS_SIDEFX_CORPUS` i aktualne piny narzędzi. Zweryfikuj rzeczywiście załadowaną definicję HDA/Labs. Nie zakładaj obecności narzędzia na podstawie dokumentacji lub starej ścieżki hosta.
3. Zapisz adaptacje wejść, CRS, skali, rozdzielczości, parametrów, wersji i materiałów w recepturze danego zadania, według `docs/tooling/sidefx/RECIPE_TEMPLATE.md`; zachowaj sam szablon do dalszego użycia. Odwołaj się do konkretnego oficjalnego rozwiązania brakującej operacji; przy nierozwiązanym braku wstrzymaj tylko zależny etap.
4. Najpierw otwórz istniejący Source/Base_DTM; zmierz próbki w rzeczywistych współrzędnych, granice, krok siatki, NoData i pokrycie wszystkich części trasy. Gęstsze próbkowanie nie podnosi dokładności źródła.
5. Zachowaj osobno Source, Manual Edits i Procedural Detail. Pozostaw detal regulowany i odwracalny; mierz max/mean/percentyle różnicy, maskę zmian i wyciek poza obszar. Nie kopiuj amplitud przykładowej wyspy na rzeczywiste Sa Calobra.
6. Sprawdź mały reprezentatywny przypadek zawierający trudną granicę; potem wykonaj pełny autoryzowany obszar. Gdy zamówiono cały Landscape, wycinek i proxy służą iteracji, a nie zamykają zakresu.
7. Zachowaj cache dla oddzielnych etapów. Unieważniaj faktycznych odbiorców zmienionych wejść; porównaj fingerprint danych, grafu, wersji, parametrów, seedów i transformacji. Użyj ponownie niezmienionego zweryfikowanego cache.

## Sprawdź HeightField i maski

- Zweryfikuj rozmiar, pierwszy/ostatni środek próbki, orientację rzędów, krok, zakres, skończoność wartości i hash zapisanych wolumenów.
- Rozróżnij `Alpha`/ważność źródła, maskę korytarza, wagi materiałów, IDMap i Unreal `visibility`. Zapisz osobny kontrakt semantyczny każdego pola.
- Dla etapu IDMap porównaj wysokość i globalny kolor przed/po kodowaniu; dekoduj każdą klasę oryginalnym HDA. Filtruj dane kategorialne zgodnie z ich kodowaniem; nie rozmywaj klas, by ukryć błędną rejestrację.
- Zapisz i ponownie otwórz HIP/cache w świeżym procesie. Sprawdź zależności z dysku; wynik bieżącej pamięci sesji nie dowodzi odtwarzalności.

## Przekaż teren do Unreal

1. Odczytaj istniejący importer i jego zakres zmian przed uruchomieniem. Dla kontynuacji lekcji 7 zastosuj wykazane `PE_Load_Landscape` / `Update Existing` / Procedural Edits. Nie uruchamiaj skryptu kasującego aktory jako rutynowego reloadu.
2. Rozróżnij generowanie nowego Landscape od modyfikacji Edit Layer istniejącego. Wybierz konkretny actor/layer zgodnie z obsługą zainstalowanego Houdini Engine, zachowując pozostałe warstwy.
3. Uzgodnij rozmiary kafli, powtarzane wspólne próbki, obrót/offset i wysokościową konwersję. Odczytaj rzeczywiste komponenty i transformacje; liczba komponentów nie dowodzi jakości ani wydajności.
4. Zachowaj wspólne parametry konwersji wysokości tam, gdzie wymaga tego tiled import. Ustaw zakresy osobno dla `height` i maski widoczności. Zapisz jednostki kwantyzacji z rzeczywistego `Scale.Z`; nie przenoś jednej tolerancji na aktory o innych skalach.
5. Używaj ważności źródła przy paddingu. W recepturze L06/L07 `Alpha > 0` oznacza dane ważne; adapter normalizuje kopię do 0/1. To kontrakt YACS, nie uniwersalna konwencja tutoriali. Zero IDMap pozostaje legalną klasą.
6. Sprawdź zapisane krawędzie kafli: współrzędne, wysokości oraz ważność. Tolerancja reprezentacji float32 współrzędnych i tolerancja różnicy wysokości są osobne. Nie luzuj geometrii, aby naprawić test transformacji.
7. Po imporcie sprawdź native readback, widoczność otworów i kolizję. Materiał otworów musi rzeczywiście konsumować `LandscapeVisibilityMask`; samo pole `visibility` nie wystarcza.
8. Porównaj geometrię i raycasty z dokładnym źródłem w tych samych współrzędnych oraz właściwą interpolacją trójkątów. Zapisz trafiony actor/component, brak trafienia i próbki po obu stronach granic. Cztery zaokrąglone landmarki nie dowodzą braku szwów.
9. Zapisz kandydata i odczytaj go w świeżym procesie. Sprawdź pełny obszar oraz trudne miejsca z kamery rowerzysty; użyj materiału neutralnego, aby ocenić samą geometrię.

## Wykorzystaj istniejącą weryfikację

- Wybierz testy i producentów z [mapy źródeł](references/source-map.md), przeczytaj ich wejścia oraz skutki uboczne. Przykładowo `readback_lesson07_geometry.py` ładuje mapę i kończy edytor; uruchamiaj go w izolowanym procesie kontrolnym.
- Odczytaj bieżący workflow oraz politykę zajętego hosta przed hython/UE. Nie uruchamiaj konkurencyjnych ciężkich procesów ani nie wymieniaj DLL aktywnego edytora. Użyj istniejącego zaufanego launchera i konfiguracji sesyjnej.
- Weryfikuj konkretny pozostały defekt, potem zakończ opcjonalne testowanie. Nie twórz nowego frameworka proof, gdy istniejący producent wystarcza.

## Zwróć dowody i pozostały krok

Podaj źródłowy SHA, zmieniony graf/parametry, obszar, identyfikatory cache i natywnego odbiorcy, sprawdzone wyniki, rzeczywiste widoki oraz niewykonane testy. Zachowaj oddzielnie: inspekcję źródła, cook, fresh reopen, zgodność geograficzną, transfer UE, kolizję, wygląd i wydajność. Nie awansuj kodu lub screenshotu do runtime PASS. Sprawdź nagłówki, podsumowania i JSON pod kątem sprzecznych statusów. Utrzymaj wymagane dowody techniczne bez ponawiania pośrednich zgód wizualnych, jeżeli owner przeniósł je na koniec M3.
