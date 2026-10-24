---
name: yacs-unreal-integration
description: "Integruj i diagnozuj Unreal Engine w YetAnotherCyclingSim (YACS): konsument Houdini, UBT/UHT/DLL, natywny odczyt Landscape, kolizja, zapis i ponowne otwarcie oraz YACS Live Host/UE Remote. Używaj przy błędach uruchamiania UE, importu, readbacku i sesji edytora."
---

# YACS — Unreal Integration

## Ustal źródła i stan

1. Ustal repozytorium `karnalooch/YetAnotherCyclingSim`, bieżący issue, PR, pełny SHA i zakres zadania. Nie przyjmuj historycznej mapy lub brancha za aktualny cel.
2. Przeczytaj `AGENTS.md`, router `docs/ai/README.md`, rolę `unreal-integration` i właściwe źródła z [mapy źródeł](references/source-map.md). Wybierz sekcje dotyczące aktualnej operacji; nie ładuj całej historii.
3. Odróżnij aktywny projekt autora, odizolowany checkout CI i proces do niezależnego reopen. Ustal ścieżki przez `workspace.json`/`scripts/manage_local_workspace.py` i wersję UE przez istniejący resolver.
4. Sprawdź naprawdę dostępne narzędzia. GitHub i logi nie dają same w sobie dostępu do procesów Windows. Zapisz dokładny brak możliwości; kontynuuj dostępne odczyty i naprawy kodu.

Polecenia odczytu na właściwym hoście Windows:

```powershell
pwsh -NoProfile -File ./scripts/runner/Get-YacsUnrealHostState.ps1 -AsJson
pwsh -NoProfile -File ./scripts/live_host/Get-YacsLiveHostStatus.ps1
```

Drugie polecenie dotyczy zainstalowanego Live Host. Jego przypięta mapa może być innym konsumentem niż aktualny Landscape z Houdiniego; porównaj nazwy pakietów i hashe przed użyciem wyniku.

## Dobierz procedurę

| Zgłoszenie | Pierwszy krok | Wymagane zakończenie |
|---|---|---|
| Edytor nie startuje | Ustal pierwszą błędną fazę: UBT, UHT, linker, loader DLL, inicjalizacja plugina lub mapy | Uruchomienie właściwego targetu i wymagany test natywny |
| Import lub szwy Landscape | Zwiąż cache, eksport i rzeczywistą mapę; odczytaj transformacje i geometrię | Źródłowe wysokości, styki i kolizja na tym konsumencie |
| Niepoprawny materiał | Odczytaj binding i stan kompilacji; przekaż authoring materiału właścicielowi domeny | Natywny binding i widok właściwej mapy, zapis/reopen gdy wymagany |
| UE Remote nie pokazuje świata | Porównaj sesję, PID/start, heartbeat, profil świata, porty i nowe klatki | Proces i nowy obraz; sam HTTP 200 nie wystarcza |
| Zmiana C++ lub konfiguracji | Sprawdź klasyfikację i resolver STATIC/RUNTIME/COMPILE | Właściwy build/Automation z tożsamością aktualnych źródeł |

## Naprawiaj właściwą fazę buildu

- Odczytaj `.uproject`, zwykły i specjalny `.Target.cs`, odpowiedni `.Build.cs`, deklarację klasy i jej implementację. Sprawdź załadowane pluginy oraz zgodność silnika/HAPI dla Houdini Engine.
- Zachowaj rozdział zwykłego `YetAnotherCyclingSimEditor` i opt-in `YetAnotherCyclingSimPcg365Editor`. Nie dopisuj eksperymentalnych pluginów do wspólnego projektu tylko po to, by uciszyć błąd.
- Dla `Unable to find parent class ... UToolsetDefinition` sprawdź przetwarzanie nagłówka `UCLASS` przez UHT. Zmiana zależności lub osłona kodu C++ nie dowodzi, że UHT przestał widzieć klasę. Ustal wspieraną strukturę modułów/targetów i zweryfikuj oba potrzebne targety.
- Dla brakującej DLL sprawdź importującą bibliotekę, target, moduł/plugin i tożsamość artefaktów. Nie kopiuj DLL z innego buildu do otwartego projektu.
- Sprawdź aktualną dokumentację Epic/SideFX i kod API przed nowym adapterem. Wykorzystaj istniejący pipeline; nie twórz kolejnego launchera, proof brokera ani mechanizmu dostępu zdalnego.
- Użyj `scripts/ci/Invoke-YacsUnrealCi.ps1` i `scripts/ue/Invoke-YacsProof.ps1` według klasyfikacji. `-SkipBuild` wymaga potwierdzonego reuse przez istniejący kontrakt cache; nie dobieraj go na wyczucie.
- Zachowaj izolację ustawień Houdini od `DefaultEngine.ini`, jeśli konsument korzysta z odrębnego profilu. Plik `scripts/houdini/unreal-engine.args` sam nie stosuje ustawień w działającej sesji.

## Chroń aktywną pracę i zasoby hosta

- Rezerwuj Unreal/GPU/home runner według istniejącego mechanizmu własności. `LOCAL_BUSY`, `MIXED_BUSY` i nieznany stan nie upoważniają do przejęcia sesji.
- Rutynowe upoważnione odczyty i odwracalne aktualizacje wykonuj bez ponownego pytania. Przed nowym rodzajem mutacji sprawdź zakres zgody, zapisane pakiety i niezapisane zmiany.
- Dla obsługiwanej iteracji użyj bieżącej sesji i istniejącej typowanej recepty. Sprawdź katalog, hash, parametry, zakres `preview`/`author`, kolejkę i natywny odczyt. Przyjęcie żądania nie oznacza wykonania.
- Nie zatrzymuj edytora w celu zwolnienia runnera. Konieczny restart najpierw wyjaśnij i zabezpiecz stan w ramach istniejącej zgody; nie uruchamiaj pętli restartów.
- Nie wykonuj `Save All`, bake ani ponownego importu pod pozorem odczytu. Sprawdź skrypt przed wykonaniem: `readback_lesson07_geometry.py` ładuje wskazaną mapę i wysyła `QUIT_EDITOR`; uruchamiaj go w odizolowanym procesie kontrolnym, nie w cudzej niezapisanej sesji.
- Ścieżki i wolne miejsce weryfikuj przed kosztownym krokiem. Użyj aktualnego preflightu operacji; nie kopiuj historycznego progu z canary i nie obniżaj go po błędzie.

## Potwierdź rzeczywisty konsument

1. Zwiąż test z pełnym SHA, hashem źródła/eksportu, mapą, pakietami, wersją silnika, procesem i run/attempt. Dla odmiennego buildu lub mapy zanotuj osobną tożsamość.
2. Odczytaj aktory, komponenty, transformacje, ustawienia sekcji i materiał. Niedostępna właściwość pozostaje `UNKNOWN`; oczekiwanego układu nie wpisuj jako pomiaru.
3. Porównaj wysokości z próbkami lub jawnie opisaną interpolacją źródła. Uwzględnij osie, cm/m, kwantyzację, globalny zakres i padding. Zaokrąglony historyczny punkt nie jest wzorcem wysokości.
4. Zbadaj styki i wspólne narożniki w wymaganym obszarze. Oddziel surową geometrię od raycastu kolizji; odczytaj trafiony aktor i powierzchnię. Kilka punktów nie dowodzi całej trasy.
5. Sprawdź `Alpha`/NoData w UE, visibility, rzeczywiste otwory i kolizję obszaru nieważnego. Sam eksport maski nie dowodzi konsumenta.
6. Dla wymaganej trwałości zapisz wyłącznie upoważnionego kandydata, potem otwórz go w niezależnym procesie i powtórz odczyt. Reopen ma czytać zapisane pakiety; replay generatora nie dowodzi zapisu.
7. Dla wyglądu użyj nowego renderu właściwej mapy; `NullRHI` nie daje dowodu wizualnego. Oddziel ocenę obrazu od akceptacji właściciela i pomiaru FPS.

## Zwróć wynik

Podaj osobno: kod, build/UHT/Automation, natywny odczyt, źródłową geometrię, kolizję i styki, NoData, materiał, zapis/reopen, obraz i Live Host. Stosuj `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` zgodnie z dowodami. Zacytuj pierwszy błąd z logu, ścieżki i następny krok. Nie zamieniaj zielonego CI w akceptację świata; użyj `$yacs-verify-evidence` do audytu dowodów.
