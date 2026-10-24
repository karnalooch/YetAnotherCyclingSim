# Źródła — fizyka i gameplay

Repozytorium: `karnalooch/YetAnotherCyclingSim`. Ścieżki poniżej są względem jego katalogu głównego, nie folderu umiejętności. Mapa powstała z rewizji `5a33c31a43e4933547a64bcb12e78552ce06e83a`; to pochodzenie tej instrukcji, nie twierdzenie o aktualnym stanie projektu. Przed wykonaniem odczytaj aktualny ref i treść źródeł.

| Pytanie | Odczytaj |
|---|---|
| Co jest zatwierdzone i co jest następne? | `AGENTS.md`, `docs/ROADMAP.md`, `docs/PRODUCT_REQUIREMENTS.md`, `docs/ai/roles/physics-gameplay.md` |
| Model fizyczny i zasady C++/Blueprint | `docs/ai/policies/CODE_PHYSICS_UNREAL.md` |
| Sesja, pause/restart, frame delta i widoczny ruch | `docs/STAGE_2_RUNTIME_CONTRACT.md`, `docs/STAGE_3_ROUTE_CONTEXT_CONTRACT.md` |
| Stan fizycznej drogi, znaki S/D, bank i grip | `docs/ROAD_PHYSICS_PROFILE.md` |
| Referencja i sposób testowania | `physics_reference/README.md`, `physics_reference/pyproject.toml`, `physics_reference/src/cycling_physics/model.py`, `physics_reference/tests/` |
| C++ — runtime API | `Source/YetAnotherCyclingSim/Public/Cycling/FixedStepRunner.h`, `Source/YetAnotherCyclingSim/Public/Cycling/CyclingSimulationSession.h`, `Source/YetAnotherCyclingSim/Public/Cycling/RiderInputController.h` |
| C++ — implementacja | `Source/YetAnotherCyclingSim/Private/Cycling/FixedStepRunner.cpp`, `Source/YetAnotherCyclingSim/Private/Cycling/SimulationStep.cpp`, `Source/YetAnotherCyclingSim/Private/Cycling/CyclingPrototypePawn.cpp` |
| Istniejąca regresja | `Source/YetAnotherCyclingSim/Private/Tests/FixedStepRunner.spec.cpp`, `Source/YetAnotherCyclingSim/Private/Tests/CyclingSimulationSession.spec.cpp`, `Source/YetAnotherCyclingSim/Private/Tests/GoldenRide.spec.cpp`, `physics_reference/tests/test_mixed_surface_reference.py` |
| Wymagany tor dowodu | `docs/CI_VALIDATION_TIERS.md`, `docs/ENGINEERING_PLATFORM.md` |

Nie ładuj wszystkiego. Zacznij od kontraktu zmienianej granicy, potem odpowiadającej implementacji i testu. W kodzie znajdziesz zarówno historyczne Stage 3/4, jak i aktualne nazwy milestone M3/M4; sprawdź mapowanie roadmapy zamiast wnioskować o zgodzie z nazwy klasy.

Komendy orientacyjne, wyłącznie odczyt:

```sh
rg -n 'FixedStepDtS|TryAdvance|TryAdvanceWithContext' Source/YetAnotherCyclingSim
rg -n 'brake_ratio|lateral_position_m|step_simulation' physics_reference/src/cycling_physics
rg -n 'HUD|FIT|BLE|FTMS|replay|M[4-9]' docs/ROADMAP.md docs/PRODUCT_REQUIREMENTS.md
```
