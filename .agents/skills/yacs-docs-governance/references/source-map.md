# Mapa źródeł i rzeczywiste granice walidacji

Ścieżki są względem `karnalooch/YetAnotherCyclingSim`, nie katalogu skilla. Odczytuj je z aktualnego SHA zadania. Sprawdzenie mapy: 2026-10-20, `5a33c31a43e4933547a64bcb12e78552ce06e83a`; [polityka dokumentacji](https://github.com/karnalooch/YetAnotherCyclingSim/blob/5a33c31a43e4933547a64bcb12e78552ce06e83a/docs/ai/policies/DOCS_AND_PLATFORM.md). Ten punkt odniesienia nie jest aktualnym statusem projektu.

| Potrzeba | Odczytaj |
|---|---|
| SSOT i indeks top-level | `docs/README.md`, `README.md` |
| Reguły i rola | `AGENTS.md`, `docs/ai/roles/docs-governor.md`, `docs/ai/policies/DOCS_AND_PLATFORM.md` |
| Pierwszeństwo decyzji | `docs/ai/DECISION_LIFECYCLE.md`, właściwa decyzja użytkownika / issue / PR |
| Produkt i aktywacje etapów | `docs/PRODUCT_REQUIREMENTS.md`, `docs/ROADMAP.md` |
| Metoda generowania świata | `docs/WORLD_BUILDING_BIBLE.md`, `docs/tooling/sidefx/README.md` |
| Concordance SideFX | `docs/tooling/sidefx/catalog/README.md`, wybrany wpis katalogu, `docs/tooling/sidefx/RECIPE_TEMPLATE.md` |
| Procedury hosta | `docs/tooling/LOCAL_WORKSPACE.md`; starsze opisy runnera porównaj z datą i zakresem bieżącej decyzji |
| Kontrole dokumentacji | `scripts/ci/check_docs_index.py`, `.github/workflows/ci.yml` |
| Kontrolowany zapis dowodów | `docs/evidence/JSON_STORAGE.md`, `docs/experiments/README.md` |
| Platforma i koszty testów | `docs/ENGINEERING_PLATFORM.md`, `docs/CI_VALIDATION_TIERS.md` |

## Co sprawdza docs-index

Komenda: `python scripts/ci/check_docs_index.py`, wykonana z korzenia checkoutu.

| Wypisywana kontrola | Faktyczny zakres w sprawdzonej wersji |
|---|---|
| i18n | Odczyt UTF-8 `docs/README.md` i głównego `README.md`; odrzucenie replacement character |
| structure | Wymagane nagłówki i linki autorytatywne; odsyłacz README do docs index |
| links | Istnienie lokalnych celów linków z obu entrypointów |
| freshness | Obecność wszystkich top-level `docs/*.md` w indeksie |

Nie nazywaj tego pełnym testem tłumaczeń, prawdziwości opisów, wszystkich anchorów ani świeżości całego repo. Przy zmianie helpera odczytaj jego aktualny zakres. Jeśli wykonanie zakończy się wcześniej, późniejsze niewykonane kontrole pozostają `NOT RUN`.

## Odczyt statusów i korekta sprzeczności

Zacznij od wyszukania identyfikatora kroku/parametru wraz z `PASS`, `FAIL`, `PENDING`, `BLOCKED`, `NOT RUN`, `COMPLETE`, `TECHNICAL_PASS`. Dla każdej deklaracji ustal:

1. Który plik lub log ją dowodzi i dla jakiego SHA/run/attempt?
2. Jaki jest zakres: mały pilot, wyeksportowane kafle, cały consumer, obraz czy odrębna akceptacja właściciela?
3. Czy poprzedza późniejszy dowód błędu albo zmianę zależnego assetu?
4. Czy jest aktualnym wnioskiem, czy oznaczoną historią?

Przykład: zero różnic na krawędziach heightfieldów nie dowodzi zgodności skal i kolizji po konwersji do UE. Napraw opis akceptacji, zachowując prawdziwy sukces eksportu.

## Zapis decyzji

Użyj istniejących pól lifecycle: `decision_id`, `scope`, `status` (`ACTIVE`/`SUPERSEDED`/`HISTORICAL`), `source_issue_or_pr`, `authority_file`, `supersedes`, `effective_since`, `expiration_or_review_gate`. Wprowadź tylko rzeczywistą decyzję użytkownika lub właściwego autorytetu. Nie twórz nowych obowiązkowych zgód na zwykłe naprawy.

Jeżeli poprawka dotyczy uniwersalnego kontraktu CI/governance, sprawdź istniejący mechanizm `.gumball/candidates/`. Nie kopiuj platformy lokalnie ani nie promuj nazw map, prywatnych ścieżek i progów YACS do wspólnego kontraktu.
