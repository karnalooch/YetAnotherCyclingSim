# Źródła materiałów i diagnostyki YACS

## Stan i użycie

Odczyt źródeł: 2026-10-20, repo `karnalooch/YetAnotherCyclingSim`, SHA `5a33c31a43e4933547a64bcb12e78552ce06e83a`. [Przejrzyj ten stan](https://github.com/karnalooch/YetAnotherCyclingSim/tree/5a33c31a43e4933547a64bcb12e78552ce06e83a). Przy nowym zadaniu odczytaj aktualny HEAD, deklaracje w roadmapie i faktyczne wejścia producenta. Piny i statusy w starszych raportach nie są automatycznie aktualne.

Poniższe ścieżki są względne do root YACS. Rozwiązuj host paths przez aktualny workspace. Zachowaj istniejące udzielone zgody oraz granice zadania; skill nie dodaje własnego obowiązku pośrednich akceptacji.

## Dokumenty i rzeczywiste entrypointy

| Źródło | Po co je otworzyć |
|---|---|
| `docs/WORLD_BUILDING_BIBLE.md`, `docs/ROADMAP.md` | metoda, role, granice geometrii, moment owner visual review/performance |
| `docs/tooling/MATERIAL_FORGE.md` | aktualne Houdini-first ownership, PBR contract, render i FAST/FULL |
| `tools/material-forge/README.md` | gotowe komendy author/render/validate/compare |
| `worldgen/materials/material_forge/families.json` | rodziny, warianty, seed i fizyczna skala |
| `worldgen/materials/material_forge/upstreams.json` | aktualne piny i źródła runtime |
| `scripts/assets/material_forge.py` | author, validate, compare, plan-rebuild i ścisłe kontrakty |
| `scripts/assets/render_material_forge.py` | Godot/source/variant, render i native decode receipts |
| `scripts/ue/import_material_forge_variant.py` | weryfikowany import pięciu map / UE settings |
| `scripts/ue/preview_material_forge_canary.py` | bounded historyczny component canary + rollback |
| `scripts/ue/build_material_forge_landscape_master.py` | zapisany parametryzowany master i sposób budowy |
| `scripts/ue/run_material_forge_unified_proof.py` | istniejący proof konsumenta; odczytaj bieżący zakres |
| `scripts/ue/capture_material_forge_landscape.py` | kamery, diagnostyki i rollback |
| `docs/tooling/BLENDER_HEADLESS.md` | pinned launcher, workspace, receipt i rozdział od UE |
| `scripts/blender/run_headless.py`, `scripts/blender/material_forge_reference.py` | Blender reference w skali fizycznej; normal DX konwertowana tylko dla podglądu |
| `docs/tooling/sidefx/LESSON05_MATERIAL_PREPARATION.md` | Forge scree jako przygotowanie do jawnej kalibracji w HDA |
| `docs/tooling/sidefx/LESSON07_MATERIAL_SETUP.md` i receipt JSON | aktywna mapa/MI/tablice, historyczne wyniki i otwarte kontrole |
| `scripts/ue/author_lesson07_materials.py` | import IDMap/colour/slices, trzy tablice i MI; mutuje zasoby |
| `scripts/ue/l07_visibility_material_author.py` | isolated hole material i ograniczenie proof |
| `scripts/ue/test_l07_visibility_material_contract.py` | statyczny kontrakt authoringu, bez dowodu native visibility |
| `docs/tooling/SA_CALOBRA_WHOLE_MAP_SURFACE_PREPARATION.md` | historycznie zaakceptowany material foundation i właściwy saved consumer |
| `docs/evidence/ROAD_SURFACE_MATERIALS_364.md`, `docs/evidence/ROAD_SURFACE_VISUAL_REVIEW_364.md` | asfalt/pobocza, wariant dry_varied, aktualne A/B i ograniczenia |
| `docs/tooling/SA_CALOBRA_CLIFF_EROSION_PASS.md` | odrębna reprezentacja klifów i granica naprawy materiałem |

Nie kopiuj wszystkich entrypointów do jednego launchera. Wybierz procedurę odpowiednią dla bieżącej mapy i wersji. Nazwa `verify`, `readback` lub `preview` nie gwarantuje braku zapisu albo zamykania procesu.

## Kontrakt Pegasus pięciu klas w L06/L07

| Nazwa receptury | Kod uint8 | Slice Colour / Normal / Masks |
|---|---:|---:|
| Grass | 0 | 0 |
| Grass2 | 64 | 1 |
| Sand | 128 | 2 |
| Cliffs | 191 | 3 |
| Scree | 255 | 4 |

Źródło: `lesson07-material-setup-verification-receipt.json` → `idmap_and_color_registration.class_order` oraz oryginalne napisy L06. To mapowanie konkretnej receptury; nie przyjmuj pięciu klas dla każdego przyszłego świata. Obecność slice'u nie dowodzi jego poprawnego przestrzennego użycia. Mała liczebność rzadkiej klasy nie usprawiedliwia jej pominięcia.

## Różnica ORM a Pegasus Masks

W Forge `ORM.B` to metaliczność; w Pegasus `Masks.B` to displacement/height. Przy adapterze wybierz i skalibruj właściwy Height, zachowaj AO i roughness oraz zapisz źródłowe hashe. `DetailMasks` to osobny materiałowy sygnał i nie staje się mapą klas. Dokument `MATERIAL_FORGE.md` opisuje pięć map; dokument L07 i jego kod opisują packing odbiorcy.

Domyślne wartości global colour strength, detail brightness czy specular z tutoriala są ustawieniami przykładu. Oceniaj je na konkretnych danych i tej samej kamerze; nie przedstawiaj jako uniwersalnej normy jakości PBR.

## Oryginalne źródła i zakres odczytu

- [Landscape Workflow](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/) oraz `docs/tooling/sidefx/catalog/PEG-02.md`: receptury L06/L07 i oryginalne HDA.
- [L06 IDmap Workflow](https://vimeo.com/888569182): maski materiałów, rejestr klas i decoder.
- [L07 Material Setup](https://vimeo.com/888569514): eksport IDMap/colour, materiał Unreal i tablice.
- [Landscape Material](https://www.sidefx.com/tutorials/project-pegasus-landscape-material/) oraz `catalog/PEG-03.md`: pogłębienie faktycznego mastera.
- `catalog/PEG-12.md`: osobna seria o global colour; otwórz oryginalną lekcję przed użyciem.
- [Houdini Engine Landscape basics](https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html): visibility mask i requirements odbiorcy.

Dnia 2026-10-20 pobrano i przeczytano całe oryginalne napisy L06/L07; nie obejrzano w tym audycie filmu/kadrów. VTT mają SHA zgodne z katalogiem: L06 `71e2246974f9ab56c0beeff2c0f05d8516132ecd4fb84e538840475ae527273b`, L07 `2f0c5e8292219b145ab59ecb173f706bcced71bec15622cb0e926c500a32fa80`. Pozostałe serie są mapą dalszego odczytu, nie deklaracją odbytego audytu.

W L07 istotne dodatkowe zakresy to 22:01–22:19 (sRGB tablicy Colour po zmianach) i 24:38–25:43 (Normal/Masks oraz światło). Alpha/NoData pochodzi z kontraktu YACS; nie przypisuj tego wymogu tym napisom.

## Diagnostyka i koszty: co dziedziczyć

`docs/tooling/MATERIAL_FORGE.md` rozróżnia Unlit, Lighting Only i Detail Lighting, dokumentuje compile-drain/GC, bootstrap A/B oraz FAST versus FULL. Czytaj bieżące implementacje i progi; historyczne `LandscapeComponent_230`, liczba 1024 komponentów i zestaw kamer należą do konkretnego konsumenta. Nie nadaj nowej mapie starego geometry/visual PASS.

Dla izolacji normalnych porównaj Lighting Only z Detail Lighting. Dla rozdzielenia BaseColor od światła użyj Unlit. Tymczasowe wyłączenie cieni lub zmiana bias to pomiar przyczyny, nie ukończona naprawa. Zachowaj tę samą kamerę i przywróć stan.

`plan-rebuild` dopuszcza odtworzenie cache przy niezmienionym fingerprint; zmiana mastera wymaga odpowiedniej pełnej walidacji. Do wznowienia przerwanego natywnego proof potrzebny jest nowy jednoznaczny run; nie łącz częściowych wyników różnych producentów.

## Ujawnione niespójności stanu 5a33c31a

L07 markdown zawierał jednocześnie statusy true/false i błędny znak w wyprowadzeniu równania UV. Ustal faktyczny aktualny graf przed zmianą MI. Nagłówek receipt `LESSON07_REQUIRES_NATIVE_GEOMETRY_RECHECK` i `LESSON07_TECHNICAL_PASS=false` nie znika od samej obecności tablic i renderów historycznych. Sprawdź, czy sprzeczności zostały naprawione, zanim powielisz opis.

Fragmenty starszych plików Forge nadal nazywają PCG/PCGEx semantic owner; dokument aktualizujący ownership kieruje do World/domain Authorities + Houdini. Nie obchodź walidatora przez fałszywą metadaną; ewentualną migrację kontraktu przeprowadź jawnie i w zakresie osobnej wymaganej poprawki.
