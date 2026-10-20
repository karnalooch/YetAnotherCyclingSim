# Mapa źródeł weryfikacji dowodów

Repozytorium: `karnalooch/YetAnotherCyclingSim`.
Przegląd bazowy: `5a33c31a43e4933547a64bcb12e78552ce06e83a`, 2026-10-20. Przed audytem odczytaj aktualne źródła; ten SHA nie wyznacza bieżącego świata.

| Zakres | Źródła | Zastosowanie |
|---|---|---|
| Uprawnienia i zakres | `AGENTS.md`; `docs/ai/roles/proof-qa.md`; `docs/ai/TASK_HANDOFF.md` | Zadanie, rola, statusy i zwrot dowodów |
| Aktywne SSOT | `docs/README.md`; `docs/ROADMAP.md`; `docs/WORLD_BUILDING_BIBLE.md` | Etap, geometria i wymagane akceptacje |
| Checki i testy | `docs/CI_VALIDATION_TIERS.md`; `docs/ci/CHANGE_CLASSIFIER.md`; `.github/workflows/ci.yml` | Rzeczywisty graf CI; FULL/scoped, static/native |
| Plan i discovery | `scripts/ci/plan_script_tests.py`; `scripts/ci/run_script_tests.py`; `.github/workflows/reusable-python.yml` | plan.json, summary.json i natywne odroczenia |
| Build i Automation | `scripts/ci/Invoke-YacsUnrealCi.ps1`; `scripts/ue/Invoke-YacsProof.ps1`; `.github/workflows/reusable-unreal.yml` | ExpectedHead, liczba testów, exit code i pierwsza błędna faza |
| Ciężki proof i provenance | `docs/ENGINEERING_PLATFORM.md`; `.gumball/proof-broker.json`; `scripts/ops/proof_broker.py` | Producent, scenariusz, exact SHA, idempotencja i retry |
| Admission świata | `.gumball/world-proof-policy.json`; `scripts/ci/world_proof_gate.py` | Wymagane scenariusze i jawne odroczenia |
| Wydajność | `docs/performance/PERFORMANCE_FRAMEWORK.md`; `docs/CI_VALIDATION_TIERS.md` | CSV, sprzęt, jakość, sektory i progi |
| Landscape i późniejsze decyzje | `docs/ai/policies/M3_WORLD_OPERATIONS.md`; `docs/tooling/sidefx/SA_CALOBRA_BUILD_GUIDE.md` | Obszar, source/manual/detail, zakres i wyjątki |
| L06/L07 | `docs/tooling/sidefx/LESSON06_FULL_IDMAP.md`; `docs/tooling/sidefx/LESSON07_MATERIAL_SETUP.md`; `docs/tooling/sidefx/catalog/PEG-02.md` | Plan i zgodność źródłowa; status wymaga potwierdzenia artefaktem |
| Ograniczenia UE readback | `scripts/ue/Invoke-YacsLesson07Readback.ps1`; `scripts/ue/readback_lesson07_geometry.py`; `.github/workflows/yacs-lesson07-unreal-readonly.yml` | Pochodzenie DLL i kopii mapy, komponenty, raycasty, niepotwierdzone source height/visibility; komplet zapytań pakietów nie oznacza zweryfikowanego wyglądu |
| Trwałość i Live Host | `docs/tooling/LOCAL_WORKSPACE.md`; `docs/tooling/YACS_LIVE_HOST.md`; `scripts/live_host/Get-YacsLiveHostStatus.ps1` | Zapis, reopen, backup, nowe klatki i post-job survival |
| Archiwa i JSON | `docs/evidence/JSON_STORAGE.md`; `scripts/ci/check_evidence_storage.py`; `scripts/ci/test_evidence_storage.py` | Byte identity, indeksy gzip i exact-blob wyjątki |
| Raport błędu i docs | `docs/ai/policies/DOCS_AND_PLATFORM.md`; `scripts/ci/check_docs_index.py` | Konkretna przyczyna i links/i18n/structure/freshness |

## Przydatne odczyty

```text
rg -n "geometry_accepted|source_height|visibility|components_pass|rounded_reference" scripts/ue/readback_lesson07_geometry.py
rg -n "full_suite_passed|DRAFT_SCOPED|deferred_native|tests" scripts/ci/run_script_tests.py
rg -n "ScenarioId|Head|Result|MapPackage|FrameP95|GpuP95" scripts/ci/world_proof_gate.py
rg -n "DEFERRED_AFTER_M3|performance_pass|owner|whole" docs/CI_VALIDATION_TIERS.md docs/ai/policies/M3_WORLD_OPERATIONS.md
```

Odczytuj artefakty GitHub Actions przez connector lub autoryzowany CLI. Zachowaj run i attempt; przy ograniczeniu rozmiaru pobierz istotny plik lub zakres logu. Raport subagenta nie zastępuje artefaktu źródłowego.
