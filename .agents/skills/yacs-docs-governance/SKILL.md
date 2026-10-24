---
name: yacs-docs-governance
description: "Utrzymuj spójność dokumentacji YetAnotherCyclingSim (YACS): SSOT, roadmapę, decyzje, indeks źródeł SideFX, raporty i instrukcje agentów. Używaj przy zmianach dokumentacji, audycie sprzecznych PASS, aktualizacji planu lub synchronizacji opisów z kodem i aktualnymi dowodami YACS."
---

# Dokumentacja i decyzje YACS

## Ustal właściwy dokument

1. Ustal aktualny branch/PR i SHA repo `karnalooch/YetAnotherCyclingSim`. Przeczytaj `AGENTS.md`, `docs/README.md` oraz kartę `docs/ai/roles/docs-governor.md`.
2. Wybierz SSOT wskazany przez indeks: produkt → `PRODUCT_REQUIREMENTS`; kolejność → `ROADMAP`; metody świata → `WORLD_BUILDING_BIBLE`; pozostałe dziedziny zgodnie z tabelą indeksu. Użyj [mapy źródeł i kontroli](references/source-map.md).
3. Odczytaj konkretną implementację, konfigurację, workflow lub dowód, który zmienia opis. Historia eksperymentu i wklejony raport są wskazówką do źródła, nie bieżącym stanem.
4. Przy zmianie decyzji sprawdź użytkownika, datę, zakres i regułę zastąpienia w `docs/ai/DECISION_LIFECYCLE.md`. Nie przenoś wyjątku dla jednego kandydata na cały projekt.

## Popraw opis w całym objętym zakresie

- Wyszukaj wszystkie aktywne odwołania do zmienianego kroku, statusu, skryptu i decyzji. Popraw nagłówek, tabelę statusów, instrukcję wykonania i wniosek, jeśli opisują ten sam aktualny wynik.
- Rozdziel dowód źródłowy, implementację, eksport, import UE, build, natywny odczyt, kolizję, wygląd, performance oraz akceptację właściciela. Użyj statusu z dowodu tej konkretnej warstwy.
- Nie zostawiaj bezwarunkowego `TECHNICAL_PASS: true`, gdy aktualny nagłówek mówi o oczekiwaniu na natywny test. Historyczną deklarację zachowaj tylko jako jednoznacznie oznaczoną historię z jej SHA i ograniczeniami.
- Nie zmieniaj oryginalnych logów, receiptów, hashy ani manifestów, aby naprawić narrację. Koryguj dokument odwołujący się do dowodu; nowy pomiar zapisuj jako nowy dowód.
- Dla tutoriala rozdziel oryginalne kroki i ustawienia od adaptacji YACS. Podaj lekcję/czas/node/parametr, typ źródła oraz ograniczenia dostępu. Pełne napisy nie oznaczają obejrzenia kadrów, a obejrzenie tutoriala nie dowodzi działania integracji.
- Zweryfikuj przykłady rachunkowe: jednostki, znak, podstawienie wartości brzegowych i wynik. Jeśli przykładowy wzór jest błędny, popraw go z dowodem; nie zmieniaj ustawień assetu na podstawie niesprawdzonego wzoru.
- Zaktualizuj implementacyjnie powiązany SSOT w tym samym PR. Nie twórz dodatkowego konkurencyjnego planu ani kopii całej dokumentacji.

## Zachowaj konwencje projektu

- Pisz teksty publikowane na GitHubie i commity po angielsku; bezpośrednie wyjaśnienia dla użytkownika po polsku. Istniejący polski PRD edytuj zgodnie z jego konwencją, bez niezamówionego tłumaczenia całego pliku.
- Dla nowego dokumentu określ status: authoritative, supporting workflow, evidence lub historical. Dodaj odsyłacz z właściwego indeksu. Każdy nowy top-level `docs/*.md` musi być osiągalny z `docs/README.md`.
- Zachowaj źródła, licencje, dokładne ścieżki i powiązanie decyzji z issue/PR. Nie zamieniaj propozycji asystenta w obowiązujący próg jakości ani domniemaną decyzję właściciela.
- Dla diagramów repozytorium odczytaj `docs/DIAGRAM_STYLE.md`. Diagram ma wyjaśniać konkretny kontrakt, bez zastępowania tekstu źródłowego samą ilustracją.
- Aktualizacja docs nie jest zgodą na zmianę zależności milestone, geometrii świata, polityki merge, CI ani uprawnień agentów. W zatwierdzonym zakresie działaj bez ponawiania pytań o zgodę.

## Sprawdź i dostarcz

1. Obejrzyj diff i porównaj poprawiony opis z rzeczywistym kodem/dowodem. Wyszukaj ponownie stare sformułowanie i przeciwne statusy w aktywnych dokumentach.
2. Uruchom istniejący `python scripts/ci/check_docs_index.py` z korzenia repo. Zapisz oddzielnie wyniki i18n, structure, links i freshness, które faktycznie wypisał skrypt.
3. Sprawdź ręcznie linki i fakty w zmienionych dokumentach: ten guard sprawdza entrypointy/indeks, nie całą semantykę dokumentacji. Dodatkowe kontrole dobierz do konkretnej zmiany, np. architektury lub integralności archiwum, według aktywnego CI.
4. Gdy sparse checkout nie zawiera celu linku, potwierdź plik w drzewie Git i materializuj potrzebne źródło. Jeśli lokalny Git nie pobiera brakującego blobu, sprawdź dostępny odczyt GitHub dla tej samej ścieżki i SHA. Nie twórz pustego pliku ani nie usuń prawidłowego odsyłacza, aby uzyskać PASS; brak lokalnych bajtów nie jest dowodem braku pliku w repo.
5. Przy blokadzie narzędzia podaj wykonaną komendę, dokładny błąd i zakres niezweryfikowany. Nie oznaczaj pominiętej kontroli jako PASS.
6. Dla dostarczenia użyj `yacs-github-delivery`. Zgłoś źródło prawdy, co skorygowano, dowód zmiany, wyniki guardów i nadal otwarte braki produktu.
