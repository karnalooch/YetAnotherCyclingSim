# Źródła — drogi i BOB

Repozytorium: `karnalooch/YetAnotherCyclingSim`. Ścieżki są względem repozytorium. Mapa sprawdzona na `5a33c31a43e4933547a64bcb12e78552ce06e83a`; zawsze odśwież zakres i kod przed wykonaniem.

| Potrzeba | Źródło |
|---|---|
| Bieżący etap i zgody | `AGENTS.md`, `docs/ROADMAP.md`, `docs/ai/roles/road-bob.md` |
| Warstwy, kontakt, droga, cut/fill i BOB | `docs/WORLD_BUILDING_BIBLE.md`: sekcje 3.3, 6–9 oraz BOB single-direction bend contract |
| Ograniczenia operacji świata | `docs/ai/policies/M3_WORLD_OPERATIONS.md` |
| Geometria trasy i embedding | `docs/STAGE_3_ROUTE_GEOMETRY_CONTRACT.md`, `docs/STAGE_3_ROUTE_CONTEXT_CONTRACT.md` |
| Fizyczna droga i S/D | `docs/ROAD_PHYSICS_PROFILE.md`, `Source/YetAnotherCyclingSim/Public/Cycling/RoadPhysicsProfile.h` |
| Wybrany wykonawca/receptury | `docs/tooling/sidefx/README.md`, `docs/tooling/sidefx/SA_CALOBRA_BUILD_GUIDE.md` |
| Inspektor profilu — bez authoringu | `scripts/worldgen/bob_profile_inspector.py` |
| Inspektor pomiarów road/Landscape | `scripts/worldgen/bob_terrain_fit_inspector.py` |
| Read-only interfejs inspekcji | `scripts/worldgen/bob_mcp_inspection.py` |
| Konfiguracja strategii i przypadków | `worldgen/terrain/adaptive_terrain_policy.json`, `worldgen/terrain/adaptive_terrain_feature_contract.json`, `worldgen/terrain/verified_terrain_cases.json` |
| Historyczny kandydat profilu | `scripts/assets/prepare_ma2141_profile.py`, `scripts/assets/prepare_ma2141_road_preview.py` |
| Wąskie testy istniejących granic | `scripts/worldgen/test_bob_terrain_fit_inspector.py`, `scripts/worldgen/test_bob_mcp_inspection.py`, `scripts/assets/test_prepare_ma2141_profile.py` |

Sprawdź aktualne kontrakty funkcji przed użyciem modułu — nie każdy plik jest wykonywalnym CLI. `bob_profile_inspector.py` ma jawny kontrakt konkretnego eksperymentu i sam sprawdza tylko format zadeklarowanej proweniencji. `adaptive_terrain_solver.py`/ledger nie przyznają prawa samodzielnego budowania ani awansu przypadku do przyjętych.

Przykładowe komendy odczytu:

```sh
rg -n 'def inspect_|INSPECTOR_ONLY|road_admitted|eligible_for_learning' scripts/worldgen/bob_profile_inspector.py scripts/worldgen/bob_terrain_fit_inspector.py
rg -n 'single-direction|Road_Earthworks|Base_DTM' docs/WORLD_BUILDING_BIBLE.md
```

Historia liczby pomiarów, zera misses albo wcześniejszego green CI jest dowodem konkretnego producenta/kandydata. Późniejsze zmiany profilu, skali, kolizji lub mapy wymagają właściwego nowego odczytu; nie dziedziczą mechanicznie poprzedniego wyniku.
