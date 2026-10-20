---
name: yacs-materials-visual
description: "Twórz, naprawiaj i oceniaj materiały oraz wygląd YetAnotherCyclingSim (YACS): Pegasus IDMap/global colour, Texture2DArrays, PBR, Material Forge, asfalt, pobocza, wapień, scree, projekcja, RVT, diagnostyka oświetlenia i porównania kamer. Używaj przy błędnych klasach, połysku, czarnych skałach, kafelkowaniu, brakujących teksturach i wizualnym odbiorze świata YACS. Łącz z yacs-houdini-world dla geometrii i ze specjalistą runtime dla uruchomień UE; nie używaj do ogólnego generowania obrazów poza YACS."
---

# YACS — Materiały i wygląd

## Ustal odbiorcę i wadę

1. Odczytaj aktualny SHA/PR repozytorium `karnalooch/YetAnotherCyclingSim`, root `AGENTS.md`, aktualną decyzję w `docs/ROADMAP.md` i `docs/WORLD_BUILDING_BIBLE.md`, następnie [mapę źródeł](references/source-map.md).
2. Zidentyfikuj rzeczywistą mapę/asset, master material, instancję, sloty, tekstury i producenta dowodów. Otwórz istniejący wynik zanim zaczniesz go odtwarzać.
3. Sformułuj sprawdzalną wadę oraz zestaw porównawczy: kamera, transformacja, rozdzielczość, tryb renderowania, światło/ekspozycja, wersja mapy. Nie nazywaj statystyk pikseli oceną jakości.
4. Kontynuuj w już autoryzowanym zakresie. Odczytaj skutki uboczne adaptera; użyj izolowanego kandydata/rollbacku, gdy pracujesz obok zaakceptowanego świata. Nie uruchamiaj ogólnego rebake'u w celu poprawy koloru.

## Zachowaj semantykę i geometrię

Współpracuj z `$yacs-houdini-world` przy eksporcie/geometrii, `$yacs-road-bob` przy kontakcie poboczy, `$yacs-unreal-integration` przy izolowanym konsumencie i `$yacs-verify-evidence` przy kwalifikacji wyników. Nie zmieniaj celu ani SHA między domenami bez odnotowania.

- Pozostaw geografię i przestrzenne maski World/domain Authorities; Houdini wykonuje bieżącą recepturę. Material Forge tworzy wygląd i materiałowe maski drobnego detalu. Starsze etykiety PCG-first nie przywracają dawnej architektury.
- Zmieniaj wygląd wskazanej powierzchni bez przemieszczania jej klasy. Rejestruj source hashes i `classification_changed=false` tam, gdzie wymaga tego istniejący kontrakt.
- Nie ukrywaj wysokościowych szwów, braków podparcia, błędnej kolizji lub kształtu klifu przez ciemniejszy materiał, RVT, vegetation albo dodatkowe kamienie. Kieruj potwierdzoną wadę geometrii do właściwej receptury świata.
- Traktuj Forge Height jako dane authoringu/inspekcji. Użycie w displacement Houdiniego wymaga jawnej kalibracji jednostek, fizycznej wielkości i skali; zwykły import materiału UE nie może zmieniać Landscape.

## Uzgodnij kontrakt tekstur

| Dane | Sprawdź przed użyciem |
|---|---|
| IDMap | dyskretne kody i kolejność klas, pojedynczy kanał, właściwy format, sRGB wyłączone, filtrowanie zgodne z kodowaniem |
| Global Colour / BaseColor | przestrzeń barw, tylko jedna potrzebna konwersja linear→sRGB, mapowanie osi i skali |
| Normal | DirectX dla YACS/UE, poprawna normalizacja i compression, sRGB wyłączone |
| Forge ORM | R=AO, G=Roughness, B=Metallic; wymagany brak metalu według receptury |
| Pegasus Masks/ORD | R=AO, G=Roughness, B=Displacement; jawnie przepakuj odpowiednie Height, nie kopiuj B z ORM |
| DetailMasks | lokalne znaczenie każdego kanału oraz brak zmiany klas świata |
| Alpha / visibility | osobna ważność, zero IDMap nie oznacza NoData, shader i kolizja wymagają osobnej kontroli |

Dla każdego assetu zapisz hash, rozdzielczość, format, channel packing, sRGB, compression, filter, addressing oraz fizyczny rozmiar powtórzenia. Nie zakładaj, że import lub zapis zachował ustawienia.

## Użyj Pegasus IDMap i materiału

1. Dopasuj recepturę do dokładnej lekcji oraz aktualnych definicji HDA; skorzystaj z krótkiej concordance w referencji. Nie zastępuj mastera Pegasus jednolitym kolorem i nie uznawaj palety klas za finalny materiał.
2. Utrzymaj jedno mapowanie klasa → kod → slice we wszystkich tablicach. Dla bieżącej receptury pięciu klas sprawdź `Grass/Grass2/Sand/Cliffs/Scree`; przy innej recepturze odczytaj jej własny rejestr.
3. Sprawdź eksport `id` jako single-channel uint8; zachowaj legalne wartości i dekodowanie. Unikaj interpolacji oraz mipowania, które tworzy nielegalne identyfikatory; ustawienia skonfrontuj z faktycznym masterem i natywnym readbackiem.
4. Wyprowadź globalny kolor z właściwej gałęzi RGB. Spłaszczaj wyłącznie kopię do eksportu/podglądu; zachowaj oryginalną geometrię. Sprawdź linear/sRGB przez neutralny unlit podgląd i próbki danych.
5. Wypełnij `Colour`, `Normal`, `Masks` taką samą liczbą zgodnych slice'ów. Sprawdź nazwy assetów i zawartość każdego indeksu, szczególnie rzadkiej klasy scree. Po zmianie tablicy odczytaj ponownie sRGB/compression.
6. Wyprowadź mapowanie world→texel→UV z rzeczywistego grafu mastera, origin, kroków i orientacji obrazu. Sprawdź znak offsetu i pół piksela na landmarkach oraz granicach. Poprawne wartości setterów nie dowodzą rejestracji przestrzennej.
7. Skompiluj i odczytaj instancję, błędy samplera, wiązania wszystkich wymaganych aktorów/komponentów oraz obecność danych po fresh reopen. Rejestruj fallback/default material jako błąd, a nie udany PBR.
8. Weryfikuj materiał otworów przy zmianie ważności. `LandscapeVisibilityMask` musi wpływać na Opacity Mask; istnienie tekstury Alpha lub wolumenu visibility nie potwierdza otworów ani kolizji.

## Wytwórz brakującą powierzchnię przez Material Forge

1. Przeczytaj `docs/tooling/MATERIAL_FORGE.md`, bieżące `families.json` i `upstreams.json`; wybierz istniejącą rodzinę/wariant lub autoryzowaną zmianę receptury.
2. Użyj istniejącego `author` z oboma selektorami `--family` i `--variant`, gdy potrzebny jest jeden wariant. Zapisuj do nowego katalogu; zachowaj zaakceptowane wyniki.
3. Rozwiąż przypięty runtime Material Maker source + Godot. Wykonaj wymagany import cache przed renderem; obecność checkoutu nie dowodzi gotowości renderera. Nie wracaj do odrzuconego release CLI tylko dlatego, że plik wykonywalny istnieje.
4. Renderuj istniejącym adapterem; sprawdź pięć map, natywne decode/hash receipts, rozmiary, zawijanie, normalne, metaliczność i sygnał detalu. Uruchom `validate-run` oraz porównanie dwóch niezależnych renderów przy zmianie producenta.
5. Sprawdź powierzchnię w skali fizycznej przez przypięty Blender headless/reference. Odwracaj kanał normalnej tylko w potrzebnym adapterze podglądu; nie zmieniaj artefaktu UE. Blender preview nie zastępuje testu UE.
6. Użyj istniejącego importera i ograniczonego canary UE. Odczytaj parametry i rzeczywiste tekstury; przyjęty world-mask pozostaje niezmieniony. Rozszerz na zamówiony obszar dopiero po rozwiązaniu konkretnej wady.

## Rozpoznaj przyczynę przez tę samą kamerę

| Obserwacja | Następny sprawdzany element |
|---|---|
| Wada pozostaje w Unlit | BaseColor, UV/projekcja, global colour, klasy |
| Znika w Unlit, pozostaje w Lighting Only | geometria, światło, self-shadowing, AO |
| Detail Lighting pogarsza Lighting Only | normal map, skala i orientacja normalnych |
| Tylko granice klas pokazują obwódki | IDMap: sRGB, filter, mipmapy, kody, rejestracja |
| Ciemna/inna ćwiartka lub komponent | binding materiału, fallback, streaming, offset/skala |
| Sztuczny połysk asfaltu | rzeczywisty roughness/specular, packing, normalna i światło przy tej samej ekspozycji |

Użyj zmiany światła/cienia wyłącznie jako kontrolowanej próby diagnostycznej i przywróć ustawienia po porównaniu. Zachowaj jeden sprawdzany czynnik na iterację. Porównuj przegląd, widok średni, nawroty/pobocza i bliski widok rowerzysty; atrakcyjny pojedynczy screenshot nie zamyka całego Landscape.

## Zachowaj kontrolę kosztu i statusów

- W istniejącej pętli Forge użyj FAST tylko przy zgodnym fingerprint i zweryfikowanym warm cache. Zmiana mastera lub kontraktu wejść wymaga właściwego FULL proof. Nie przenoś historycznego `LandscapeComponent_230` na inny świat bez identyfikacji mapy i bounds.
- Zachowaj progi pamięci i kolejność drain/GC istniejącego producenta. Jeśli potrzeba, zastosuj udokumentowane rozdzielenie budowy/importu i capture na procesy; nie obniżaj progu dla uzyskania PASS.
- Podaj zmianę i przyczynę, SHA materiałów/mapy, rzeczywiste A/B obrazy, testy oraz zakres pozostałych braków. Zapisane assety, deterministyczne mapy, natywny render, owner visual acceptance i benchmark są osobnymi stanami.
- Sprawdź aktualny moment audytu ownera w ROADMAP; nie wymagaj powtarzanych pośrednich akceptacji, jeżeli audyt został przeniesiony na koniec M3. Dopóki brak właściwego pomiaru, zachowaj `DEFERRED_AFTER_M3` / `performance_pass: false` zgodnie z aktywną decyzją.
