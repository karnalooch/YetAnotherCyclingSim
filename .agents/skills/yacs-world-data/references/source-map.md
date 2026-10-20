# Źródła — World Data

Repozytorium: `karnalooch/YetAnotherCyclingSim`; wszystkie ścieżki są repozytoryjne. Zweryfikowana baza mapy: `5a33c31a43e4933547a64bcb12e78552ce06e83a`. Przed pracą odczytaj aktualną rewizję, AOI i status dowodów. Ta mapa nie przyznaje PASS żadnemu z wymienionych produktów.

| Potrzeba | Źródło |
|---|---|
| Autorstwo i domeny świata | `docs/WORLD_BUILDING_BIBLE.md`: sekcje 2, 2.1, 5, 6, 7.4; `docs/ai/roles/world-data.md` |
| Aktualny kierunek Houdini i kolejność | `AGENTS.md`, `docs/ROADMAP.md`, `docs/tooling/sidefx/README.md`, `docs/tooling/sidefx/SA_CALOBRA_BUILD_GUIDE.md` |
| Pochodzenie/licencje | `docs/legal/DEPENDENCY_PROVENANCE.md`, `THIRD_PARTY_NOTICES.md`, `docs/ASSET_PLAN.md` |
| Benchmark DTM i profil importu | `worldgen/terrain/benchmarks/sa_calobra/sa_calobra_8x8km_mdt50cm_epsg25831.json`, `worldgen/terrain/benchmarks/sa_calobra/terrain_import_profile.json` |
| Historyczny World Data Stack i dokładne wejścia | `worldgen/terrain/benchmarks/sa_calobra/world_data/README.md`, `worldgen/terrain/benchmarks/sa_calobra/world_data/working_space_sources.json` |
| Pokrycie i źródła bez zgadywania nazw | `scripts/assets/plan_sa_calobra_world_data.py`, `scripts/assets/resolve_sa_calobra_cnig_records.py`, `scripts/assets/world_data_service_evidence.py` |
| Normalizacja i niezależny odczyt | `scripts/assets/normalize_sa_calobra_context.py`, `scripts/assets/verify_normalized_context.py` |
| Maski LiDAR i niezależny odczyt | `scripts/assets/prepare_sa_calobra_lidar_masks.py`, `scripts/assets/verify_sa_calobra_lidar_masks.py` |
| Regresje danych | `scripts/assets/test_normalized_context.py`, `scripts/assets/test_sa_calobra_lidar_masks.py`, `scripts/assets/test_world_data_service_evidence.py` |
| Zachowanie danych przy naprawach hosta | `docs/ai/policies/M3_WORLD_OPERATIONS.md`, `scripts/assets/Restore-YacsSaCalobraWorldData.ps1` |

`prepare_region_terrain.py` obsługuje historyczny kontrakt 4033 próbek, `reject_in_baseline` i określone R16. Nie jest ogólnym importerem dowolnego Landscape. `normalize_sa_calobra_context.py` i maski LiDAR również sprawdzają konkretną siatkę. Pełny nowy AOI wymaga zgodnego źródła/producenta, nie zmiany nazwy folderu.

Przy nowym źródle korzystaj z oficjalnych rekordów CNIG/IGN, GOIB/IDEIB, Catastro lub właściwego dostawcy wskazanych przez bieżący rejestr źródeł. Ponownie sprawdź publikację/epokę i licencję; adres usługi i mapa na stronie nie zastępują dowodu kompletności danych.
