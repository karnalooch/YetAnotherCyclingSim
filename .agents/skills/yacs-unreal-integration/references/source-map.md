# Źródła procedur Unreal

Repozytorium: `karnalooch/YetAnotherCyclingSim`.
Przegląd bazowy: `5a33c31a43e4933547a64bcb12e78552ce06e83a`, 2026-10-20.
To tożsamość przeglądu skilla, nie domyślny SHA wdrożenia ani status świata. Przed pracą pobierz aktualne pliki z wybranego SHA i sprawdź implementację.

| Pytanie | Źródła w repozytorium | Co odczytać |
|---|---|---|
| Kto i w jakim zakresie działa? | `AGENTS.md`; `docs/ai/README.md`; `docs/ai/TASK_HANDOFF.md`; `docs/ai/roles/unreal-integration.md` | Aktualny issue, zakres, właściciel ścieżek i dowód |
| Gdzie jest projekt i runner? | `docs/tooling/LOCAL_WORKSPACE.md`; `scripts/manage_local_workspace.py` | Rzeczywisty workspace.json, ścieżki i tryb sesji |
| Jak zachować aktywną sesję? | `docs/ai/policies/M3_WORLD_OPERATIONS.md` | Późniejsze decyzje live iteration, in-place upgrade, independent Live Host |
| Kto zajmuje host? | `scripts/runner/Get-YacsUnrealHostState.ps1` | IDLE/REMOTE_BUSY/LOCAL_BUSY/MIXED_BUSY i procesy |
| Jaki build jest konieczny? | `docs/CI_VALIDATION_TIERS.md`; `docs/ci/CHANGE_CLASSIFIER.md`; `scripts/ci/Resolve-YacsUnrealCiCache.ps1` | STATIC/RUNTIME/COMPILE i fingerprinty |
| Jak rozwiązać silnik i dowód? | `scripts/ci/Resolve-YacsUnrealEngine.ps1`; `scripts/ue/Preflight-YacsProof.ps1`; `scripts/ci/Invoke-YacsUnrealCi.ps1`; `scripts/ue/Invoke-YacsProof.ps1` | Parametry, rezerwy, ExpectedHead, discovery Automation i błędy |
| Gdzie badać ToolsetRegistry/UHT? | `Source/YetAnotherCyclingSimEditor/YetAnotherCyclingSimEditor.Build.cs`; `Source/YetAnotherCyclingSimPcg365Editor.Target.cs`; `Source/YetAnotherCyclingSimEditor/Public/PCG/YacsPcgWitnessToolset.h` | Zależności, UCLASS, widoczność modułu dla UHT |
| Jak zachować izolację Houdini Engine? | `docs/tooling/sidefx/UNREAL_CONFIGURATION.md`; `scripts/houdini/unreal-engine.args` | HAPI, efektywne ustawienia, jawny argument |
| Jak interpretować L07 readback? | `scripts/ue/readback_lesson07_geometry.py`; `.github/workflows/yacs-lesson07-unreal-readonly.yml` | Ładowana mapa, ograniczenia raycastu, brak pełnej akceptacji |
| Jak sprawdzić zapis bez przebudowy? | `scripts/ue/verify_accepted_scene_checkpoint.py`; `docs/tooling/LOCAL_WORKSPACE.md` | Dokładny profil/mapa; historyczny checkpoint nie zastępuje nowego |
| Jak działa Live Host? | `docs/tooling/YACS_LIVE_HOST.md`; `scripts/live_host/Get-YacsLiveHostStatus.ps1`; `scripts/live_host/protocol.py`; `scripts/live_host/recipes/catalog.json` | SHA/sesja/PID/start, heartbeat, mapa, klatki, zakres |
| Jak publikować recepty? | `scripts/live_host/Publish-YacsLiveRecipe.ps1`; `scripts/live_host/Send-YacsLiveHostCommand.ps1`; `.github/workflows/yacs-live-command.yml` | Typowane żądanie, katalog, serializacja, upoważnienie i readback |
| Jak diagnozować runner? | `docs/UNREAL_CI_RUNNER.md`; `docs/ci/RUNNER_WORKSPACE_RETENTION.md` | Aktualne vs historyczne reguły, podgląd kandydatów przed apply |

## Szybkie wyszukiwanie

```text
rg -n "ToolsetRegistry|UToolsetDefinition|YACS_WITH_PCGEX" Source
rg -n "STATIC|RUNTIME|COMPILE|SkipBuild|ownership" docs/CI_VALIDATION_TIERS.md scripts/ci
rg -n "load_map|save_|geometry_accepted|visibility|trace" scripts/ue/readback_lesson07_geometry.py
rg -n "heartbeat|map_package|source_sha|browser_frames|post_job" scripts/live_host/Get-YacsLiveHostStatus.ps1
```

## Dokumentacja zewnętrzna

Przed implementacją sprawdź aktualne oficjalne źródła dla zainstalowanych wersji. Katalog SideFX w repo wskazuje lekcje i projekty. Dokumentacja opisuje API; natywny test YACS potwierdza użycie.

- Epic, konfiguracja: https://dev.epicgames.com/documentation/unreal-engine/configuration-files-in-unreal-engine
- SideFX, integracja: https://www.sidefx.com/docs/houdini/unreal/settings.html
- SideFX, preferencje: https://www.sidefx.com/docs/houdini/unreal/editorpref.html
