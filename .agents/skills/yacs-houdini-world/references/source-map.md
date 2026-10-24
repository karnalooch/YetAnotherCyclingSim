# Źródła procedury świata YACS

## Stan i sposób użycia

Źródła repozytorium odczytano 2026-10-20 na `5a33c31a43e4933547a64bcb12e78552ce06e83a`, `karnalooch/YetAnotherCyclingSim`, PR #474 / `codex/365-world-graph`. To punkt audytu tej instrukcji, nie przypięcie przyszłych prac do starego HEAD. Przy wznowieniu odczytaj bieżące pliki i decyzje. Nie odtwarzaj starego defektu, jeżeli został już poprawiony.

[Repozytorium w stanie audytu](https://github.com/karnalooch/YetAnotherCyclingSim/tree/5a33c31a43e4933547a64bcb12e78552ce06e83a).
Ścieżki tabel poniżej są względne do root tego repozytorium; najpierw ustal jego rzeczywistą lokalizację. Nie traktuj ścieżek dawnego Windows hosta jako dowodu obecności pliku.

## Mapa odpowiedzialności i źródeł

| Potrzeba | Otwórz | Użyj do |
|---|---|---|
| Metoda i konflikty dawnych decyzji | `docs/WORLD_BUILDING_BIBLE.md` | aktualny executor, geografię, zakres freeze, rolę BOB i odbiór |
| Aktywny etap i kolejność | `docs/ROADMAP.md` | zakres, zależności GitHub, końcowy audyt M3 i benchmark |
| Proces source-first | `docs/tooling/sidefx/README.md` | corpus roots, dowody, adaptacje, brakujące operacje |
| Kontynuacja Sa Calobra | `docs/tooling/sidefx/SA_CALOBRA_BUILD_GUIDE.md` | istniejąca baza, osobny detal, pełny zakres i cache |
| Receptura konkretnego grafu | `docs/tooling/sidefx/RECIPE_TEMPLATE.md` | oryginał, zmienione parametry, wejścia/wyjścia, proof |
| Ścieżki i własność hosta | `docs/tooling/LOCAL_WORKSPACE.md` | workspace/config, tool roots, cache i checkpoints |
| Houdini Engine w izolowanej sesji | `docs/tooling/sidefx/UNREAL_CONFIGURATION.md` | opt-in `.args`, effective HAPI, niezmienione stare checkpointy |
| Narzędzia Labs | `docs/tooling/sidefx/SIDEFX_LABS_22_0_466.md` | zainstalowane definicje, odpowiedniki i ograniczenia |
| Role downstream | `docs/tooling/MATERIAL_FORGE.md`, `docs/tooling/BLENDER_HEADLESS.md` | wspierające PBR/preparation, bez przejmowania geografii |
| Dowody i repo hygiene | `docs/evidence/JSON_STORAGE.md` | zwarte receipts, zachowanie błędów i archiwów |

## Wybór tutoriala dla domeny

Wybierz właściwy istniejący wpis spośród `docs/tooling/sidefx/catalog/PEG-*.md`, potem wybraną część i rzeczywisty oryginalny HIP/HDA. Katalog indeksuje źródła; nie poświadcza opanowania ani uruchomienia wszystkich lekcji.

| Domena | Wpisy katalogu |
|---|---|
| Pakiety, współpraca, ścieżki | PEG-00 |
| Baza HeightField i HDA | PEG-01 |
| Warstwy, surface detail, scree, IDMap, trails i vegetation handoff | PEG-02 |
| Master material i technika HeightField RGB | PEG-03, PEG-04 |
| Klify, piles, skały/Nanite/UV/bake/PDG | PEG-05, PEG-06, PEG-07 |
| Architektura i warianty obiektów | PEG-08, PEG-09, PEG-14 |
| Chmury i flora | PEG-10, PEG-11 |
| Global colour | PEG-12 |
| Drogi, tracks, rivers | PEG-13; zawsze zachowaj canonical route/physics |
| Utility Widgets i kontrola Engine | PEG-15; nie buduj alternatywnej platformy sterowania |

Nie utożsamiaj dwóch serii Architecture: PEG-08 i PEG-14 mają osobne źródła. Późniejsza seria wskazuje metodę dla aktywnego zadania, nie znosi jego zależności roadmapy.

## Konkretne entrypointy L06/L07

| Plik w repo | Znaczenie i ograniczenie |
|---|---|
| `scripts/houdini/lesson06_unified_pipeline.py` | producent zunifikowanego etapu; nie uruchamiaj ponownie bez powodu unieważniającego cache |
| `scripts/houdini/verify_and_render_lesson06_unified.py` | native invariants, decoder i podglądy; sprawdź ścieżki i wymagane zasoby |
| `docs/tooling/sidefx/lesson06-unified-verification-receipt.json` | identyfikacja zaakceptowanego cache i zakres historycznego dowodu |
| `scripts/houdini/setup_lesson07_unified_houdini.py` | graf procedural delta, IDMap, colour i osobne previews |
| `scripts/houdini/cook_and_verify_lesson07_exports.py` | natywny eksport i sprawdzenie danych; wykonuje pracę i zapisuje wyniki |
| `scripts/houdini/prepare_lesson07_ue_transfer.py` | kopia do nowych czterech kafli; kontrola L06 SHA, nowy output dir, Alpha/visibility |
| `scripts/houdini/l07_tile_invariants.py` | orientacja krawędzi, ważność paddingu, seam comparison i bilinear diagnostic |
| `scripts/houdini/test_l07_tile_invariants.py` | testy kontraktu transferu, nie proof natywnego UE |
| `scripts/ue/readback_lesson07_geometry.py` | map/component/raycast report; ładuje mapę, zapisuje raport i wykonuje `QUIT_EDITOR` |
| `scripts/ue/l07_visibility_material_author.py` | oddzielny materiał otworów; jego utworzenie nie dowodzi działania po bake |
| `scripts/ue/bake_lesson07_landscape.py` | mutujący bake z opt-in guard; nie jest rutynowym readbackiem ani update-existing |
| `.github/workflows/yacs-lesson07-native-audit.yml` | istniejąca lane audytu; przed dispatch odczytaj aktualne inputs, kroki i własność hosta |
| `docs/tooling/sidefx/LESSON07_MATERIAL_SETUP.md` i receipt JSON | historia oraz bieżące zastrzeżenia; wyszukaj sprzeczne statusy |

Dobierz powyższe skrypty do defektu; nie uruchamiaj ich wszystkich jako obowiązkowej listy. Przy geometry audit nie utożsamiaj bilinear diagnostic z natywną triangulacją Landscape. Odczyt czterech landmarków nie sprawdza wszystkich krawędzi.

## Świeżo odczytane źródła lekcji 6 i 7

Pobrano oryginalne angielskie napisy z publicznych playerów Vimeo i przeczytano je w całości 2026-10-20. Hash obu VTT zgadza się z katalogiem repozytorium. W tym audycie nie oglądano filmu ani wszystkich kadrów; nie dopisuj takiej deklaracji. Automatyczne napisy mogą przekręcać nazwy węzłów, więc ustal je z definicji HDA.

| Źródło | Czas i znaczenie |
|---|---|
| [L06 IDmap Workflow](https://vimeo.com/888569182) | 11:54–12:13: pięć klas; 16:45–17:05: powrót IDMap→maski |
| [L07 Material Setup](https://vimeo.com/888569514) | 01:43–03:56: osobna różnica wysokości i cache Layer3 |
| L07 | 05:03–05:28, 08:01–08:06: 8-bit single-channel z warstwy `id` |
| L07 | 06:24–07:26, 10:36–11:54: osobny eksport RGB oraz linear→sRGB |
| L07 | 12:38–12:58: `PE_Load_Landscape`, `Update Existing`, Procedural Edits, Unreal, Reload |
| L07 | 15:32–17:35: grayscale, sRGB off, Nearest |
| L07 | 17:45–18:56, 24:38–25:43: zgodne indeksy tablic i kontrola wyglądu |

VTT L06: `71e2246974f9ab56c0beeff2c0f05d8516132ecd4fb84e538840475ae527273b` (373 cues).
VTT L07: `2f0c5e8292219b145ab59ecb173f706bcced71bec15622cb0e926c500a32fa80` (595 cues).
Oryginały pozostają w corpus; nie kopiuj pełnych transkrypcji do skillu/repozytorium.

`Alpha`, NoData i maskowanie paddingu nie są omówione w tych napisach. Ich wymagania wynikają ze źródłowego DTM, kodu transferu YACS i kontraktu Houdini Engine.

## Oficjalne źródła dla konkretnego braku

- [Landscape Workflow](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/): źródłowe lekcje i oryginalne materiały.
- [Houdini Engine Landscape basics](https://www.sidefx.com/docs/houdini/unreal/landscape/basics.html): `unreal_landscape_output_mode` 0/1, Edit Layers, wysokościowa konwersja, size/sections, wspólne layer min/max i otwory.
- [Landscape outputs](https://www.sidefx.com/docs/houdini/unreal/landscape/outputs.html): output actors, baking oraz związane zasoby.
- [Attributes](https://www.sidefx.com/docs/houdini/unreal/attributes.html): dokładne nazwy i typy atrybutów; dopasuj do zainstalowanej wersji.

## Pułapki ujawnione w stanie audytu

Na wskazanym SHA dokument L07 jednocześnie zawiera nagłówek technical false i dawną sekcję 8 z true. W sekcji UV równanie z dodawaniem offsetu wyprowadza błędny znak. Nie powtarzaj tych twierdzeń; odczytaj aktualny status oraz rzeczywisty graf. Poprawka samego tekstu nie naprawia materiału.

Historyczny wspólny krok kwantyzacji koliduje z różnymi Scale.Z aktorów. `readback_lesson07_geometry.py` rozdziela krok per actor, zaokrąglone referencje i brak source witness. Historyczne odchylenie około 39 cm nie jest samo w sobie pomiarem uskoku między dwoma kaflami. Wyznacz geometrię krawędzi i rzeczywiste źródło, zanim nazwiesz przyczynę.
