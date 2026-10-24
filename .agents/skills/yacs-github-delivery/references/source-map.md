# Źródła dostawy GitHub

Repozytorium: `karnalooch/YetAnotherCyclingSim`.
Przegląd bazowy: `5a33c31a43e4933547a64bcb12e78552ce06e83a`, 2026-10-20. Pobierz bieżący SHA i źródła; nie przypinaj dostawy na stałe do tej rewizji.

| Obszar | Źródła | Co sprawdzić |
|---|---|---|
| Zakres i autorytet | `AGENTS.md`; `docs/README.md`; `docs/PRODUCT_REQUIREMENTS.md`; `docs/ROADMAP.md` | Zatwierdzony problem, etap, dependency gates i SSOT |
| Delegacja | `docs/ai/README.md`; `docs/ai/ROLE_REGISTRY.json`; `docs/ai/TASK_HANDOFF.md` | Domena, jeden piszący, rzeczywiste uruchomienie subagenta |
| Git, PR i merge | `docs/ai/policies/GIT_AND_PROJECT.md`; `docs/ai/policies/DELIVERY_AND_SCOPE.md` | Aktualne wyjątki, gałęzie, issue, Draft, standing authorization vs hold |
| Dokumentacja i platforma | `docs/ai/policies/DOCS_AND_PLATFORM.md`; `docs/ENGINEERING_PLATFORM.md` | SSOT w tej samej zmianie, preserve-local, immutable piny, Aggregate |
| Ryzyko i klasyfikacja | `.github/workflows/ci.yml`; `scripts/ci/classify_changes.py`; `docs/ci/CHANGE_CLASSIFIER.md` | Klasa, ue_code, asset_full, koszt i lane'y |
| Testy i reuse | `docs/CI_VALIDATION_TIERS.md`; `scripts/ci/plan_script_tests.py`; `scripts/ci/run_script_tests.py` | FULL/scoped, odroczenia, discovery, cache equivalence |
| Docs | `scripts/ci/check_docs_index.py` | Osobne links/i18n/structure/freshness |
| Dowody | `docs/evidence/JSON_STORAGE.md`; `scripts/ci/check_evidence_storage.py` | Tożsamość bajtów i dokładne wyjątki JSON |
| Zasoby i LFS | `.gitattributes`; `.gitignore`; `docs/legal/DEPENDENCY_PROVENANCE.md`; `THIRD_PARTY_NOTICES.md` | Pointer/obiekt, licencja, brak cache |
| Host | `docs/tooling/LOCAL_WORKSPACE.md`; `scripts/runner/Get-YacsUnrealHostState.ps1`; `.github/workflows/reusable-unreal.yml` | Osobny checkout, właściciel, trusted execution |
| Ciężki proof | `.gumball/proof-broker.json`; `.github/workflows/proof-broker.yml`; `scripts/ops/proof_broker.py` | Upoważnienie, SHA, deduplikacja, retry, provenance |

## Odczyt i zapis dostępnymi narzędziami

Odkryj aktualne capability GitHub. Typowe operacje: odczyt PR, commitów, zmienionych plików, checków, workflow jobs/logs i artefaktów. Zapis wykonaj udokumentowanym narzędziem lub autoryzowanym Git/CLI; nie zgaduj nazw ani schematów API.

Przez Git Data API utwórz bloby/drzewo/commit z właściwym rodzicem, następnie przesuń istniejący ref ze sprawdzeniem oczekiwanego HEAD. Odrzucenie wymaga odczytu nowego HEAD. Commit w bazie obiektów bez przesuniętego ref nie jest ukończoną dostawą.

Zwykły push nie wymaga przepisywania historii. Nie korzystaj z `--force`, `--force-with-lease`, resetowania wspólnego worktree ani zmiany ochrony branchy, aby ominąć odmowę publikacji.

## Fakty w raporcie

Linkuj pliki przez GitHub URL z pełnym SHA, testy przez run i attempt. Nie podawaj starego HEAD jako bieżącego. Dla rozpoczętego CI raportuj `in_progress`/`queued`, nie „zielone”. Wymagane checki i rzeczywiste dowody są nadrzędne wobec nazwy workflow lub sukcesu poprzedniej próby.
