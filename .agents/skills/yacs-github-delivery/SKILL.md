---
name: yacs-github-delivery
description: "Prowadź pracę i dostawę zmian YetAnotherCyclingSim (YACS) przez GitHub: issue i zależności, istniejąca gałąź/PR, ograniczone poprawki, Git LFS, diff, dokumentacja, klasyfikacja CI i bezpieczny push. Używaj przy kontynuacji PR, naprawie CI, porządkowaniu dostawy i prośbie o wysłanie zmian na remote."
---

# YACS — GitHub Delivery

## Rozpoznaj bieżącą pracę

1. Ustal repozytorium `karnalooch/YetAnotherCyclingSim`, issue, rzeczywisty PR i pełny HEAD. Przeczytaj `AGENTS.md`, `docs/ai/README.md`, `docs/README.md` oraz źródła z [mapy źródeł](references/source-map.md).
2. Sprawdź aktualny zakres i zależności etapu. Zamknięcie issue jako „not planned”, Draft PR lub zielone CI nie dowodzą ukończenia poprzednika.
3. Wznawiaj istniejącą dostawę na jej gałęzi. Nowa sesja bez kontekstu nie uzasadnia kolejnego PR ani restartu prac. Przydziel jednego piszącego do każdej ścieżki/worktree i respektuj bieżący limit gałęzi implementacyjnych.
4. Sprawdź narzędzia: używaj dostępnej integracji GitHub do odpowiednich odczytów i operacji. Lokalny Git/CLI wykorzystuj do analizy, edycji i testów, gdy dostępny. Nie wymagaj Kilo, Cursora ani przenoszenia patchy przez użytkownika.
5. Sprawdź `git status`, gałąź i diff przed edycją. Zachowaj niezwiązane zmiany; przy konflikcie użyj odizolowanego checkoutu/worktree zamiast resetowania wspólnego katalogu.

## Wykonaj małą, pełną zmianę

- Zdefiniuj problem, zakres plików i dowód potwierdzający poprawkę. Upoważnione odwracalne kroki wykonuj bez ponownej zgody; nie poszerzaj celu na inne repozytoria lub przyszłe etapy.
- Przeczytaj implementację i SSOT. Dla nowej logiki integracyjnej zbadaj aktualne oficjalne rozwiązanie przed adapterem. Dla świata stosuj aktualny kierunek Houdini/SideFX, nie historyczne preferencje narzędzi.
- Wykorzystaj obecne skrypty i Gumball. Nie twórz drugiego kontrolera CI, proof frameworku, task registry ani stałego workflow do jednorazowego obejścia błędu.
- Zmień wymagane ścieżki. Gdy zmienia się zachowanie, popraw SSOT w tej samej dostawie. Raport eksperymentu nie zastępuje dokumentacji kontraktu.
- Przed binariami sprawdź `.gitattributes`, źródło/licencję i Git LFS. Oddziel commit pointera, wysłanie obiektu i niezależną możliwość pobrania. Nie dodawaj DDC, Binaries, Intermediate, Saved, sekretów ani prywatnych danych.

## Diagnozuj CI od pierwszej przyczyny

1. Pobierz checki aktualnego SHA i log błędnego joba/attemptu. Porównaj SHA joba z PR i merge ref. Test przerwany przed wykonaniem oznacz jako niewykonany.
2. Rozdziel błąd kodu, testu, docs, orchestration, UHT/UBT/DLL i hosta. Podaj pierwszy konkretny błąd zamiast samego Aggregate.
3. Napraw potwierdzoną przyczynę, uruchom najwęższe sensowne sprawdzenie i wymagane gate'y. Ponowienie bez nowej hipotezy lub oznaki błędu przejściowego nie jest naprawą.
4. Dobierz test do ryzyka i kontraktu. Nie osłabiaj asercji, progów, liczby testów ani klasyfikatora, żeby uzyskać zielony wynik.
5. Respektuj STATIC/RUNTIME/COMPILE i FULL/DRAFT_SCOPED. Nie wymuszaj pełnego buildu dla zwykłej iteracji materiału ani ręcznie nie fałszuj scoped planu. Gotowość oceniaj przez `$yacs-verify-evidence`.

## Sprawdź przed publikacją

Dobierz polecenia do zmienionych plików po przeczytaniu aktualnej implementacji:

```text
git diff --check
python scripts/ci/check_docs_index.py
python scripts/ci/check_evidence_storage.py
```

- `check_docs_index.py` uruchom przy dokumentacji i raportuj links, i18n, structure, freshness. PASS dotyczy jego rzeczywistego zakresu; nie twierdź, że przeczytał wszystkie dokumenty.
- `check_evidence_storage.py` sprawdza archiwa i budżet JSON. Przy sparse checkout uzupełnij wymagane pliki lub zgłoś ograniczenie; brak danych nie jest błędem produktu.
- Testy wybiera istniejący planner/runner. Pełny przebieg to `python scripts/ci/run_script_tests.py --workers 4 --output <isolated-output>`; użyj go gdy wymagany jest FULL, nie po każdej zmianie tekstu.
- C++/Unreal sprawdzaj trusted runnerem i właściwym targetem, chroniąc aktywną sesję. Brak UE lokalnie pozwala na sprawdzony checkpoint/Draft z `Unreal validation pending`, nie natywny PASS.
- Po potrzebnym dowodzie zakończ opcjonalne powtarzanie testów. Pozostałe wymagane gate'y obowiązują.

## Opublikuj bez nadpisania cudzej pracy

1. Sprawdź końcowy diff, licencje/LFS i listę plików. Stage'uj wyłącznie własne ścieżki.
2. Przygotuj skupiony commit po angielsku. Przed push odczytaj remote HEAD. Dla API użyj aktualnego `expected_sha`; aktualizuj ref bez force. Dla Git stosuj zwykły fast-forward push.
3. Przy zmianie HEAD przeczytaj nowe commity, zintegruj je w odizolowanej pracy i powtórz odpowiednią walidację. Nie rozwiązuj wyścigu force pushem ani resetem wspólnej historii.
4. Zweryfikuj remote: nowy pełny SHA, treść i właściwy branch/PR. Lokalny commit nie oznacza wysłania.
5. Gdy zadanie wymaga aktualizacji PR, zachowaj istniejący PR i zakres. Tytuł/opis/komentarz/review przygotuj po angielsku przez strukturalny argument lub plik UTF-8 z `--body-file`, potem sprawdź zapisany Markdown.
6. Wiadomości/komentarze wysyłaj wyłącznie w upoważnionym zakresie. Prośba o naprawę kodu sama nie wymaga Slacka, e-maila ani komentarza do innych osób.
7. Sprawdź checki po push. Nie deklaruj sukcesu z poprzedniego SHA. Dla trwającego joba podaj stan i kontynuuj dostępną pracę.

## Oddziel publikację od merge

Skill nie tworzy upoważnienia do merge. Odczytaj aktualną decyzję użytkownika; jawny hold ma pierwszeństwo przed dawną zgodą ogólną. Przy już upoważnionym merge wymagaj mergeable, nie-Draft PR oraz wszystkich checków, review, native/asset i wizualnych bramek. Nie włączaj auto-merge jako obejścia oczekującego dowodu. Bez właściwej zgody zakończ na opublikowanej, zweryfikowanej zmianie.

## Zwróć raport po polsku

Podaj co i dlaczego naprawiono, issue/PR, commit/link, zakres plików, sprawdzenia, SSOT/doc guards i niepotwierdzone elementy. Rozdziel lokalną zmianę, remote commit, CI, native, obraz i merge. Przy błędzie podaj operację, pierwszą przyczynę, próbę poprawki i następny krok.
