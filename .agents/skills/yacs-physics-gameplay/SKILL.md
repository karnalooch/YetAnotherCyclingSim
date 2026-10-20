---
name: yacs-physics-gameplay
description: "Utrzymuj i rozwijaj fizykę oraz gameplay YetAnotherCyclingSim (YACS): model Python/C++, fixed step, RiderInputController, sesję, Road Physics Profile i zgodność z renderem. Używaj przy błędach prędkości, mocy, kadencji, hamowania, zakrętów, start/stop/restart oraz planowaniu HUD, replay, save/FIT, trenażera, pogody i prezentacji zawodnika; najpierw sprawdź aktualny gate roadmapy."
---

# YACS — fizyka, wejście i sesja

## Ustal właściwy etap

1. Zidentyfikuj checkout `karnalooch/YetAnotherCyclingSim`, bieżący SHA i zakres zadania użytkownika. Przeczytaj `AGENTS.md`, `docs/ai/README.md`, aktualny `docs/ROADMAP.md` oraz właściwy kontrakt z [mapy źródeł](references/source-map.md).
2. Sprawdź rzeczywisty stan kodu i issue. Istniejący kod zakrętów lub wzmianka o przyszłym systemie nie oznaczają otwarcia jego milestone'u. Gdy M3 trwa, utrzymuj zatwierdzoną fizykę w zakresie zadania; plan nowego M4+ oznacz jako plan z zależnościami.
3. Uwzględnij aktualne polecenia i zgody użytkownika. Wykonuj dostępne bezpieczne prace samodzielnie; zgłoś konkretną brakującą zależność zamiast wymagać ponownego zatwierdzania już uzgodnionych kroków.

## Zachowaj granice danych

| Element | Właściciel prawdy |
|---|---|
| Moc, kadencja, hamulec | `FRiderInput` / `RiderInput` poprzez istniejący kontroler wejścia |
| Prędkość, dystans, czas, boczne `D` | `FSimulationState` / `SimulationState` |
| Czas symulacji i podkroki | `FFixedStepSimulationRunner` |
| Pochylenie, krzywizna, szerokość, cross-slope, nawierzchnia | aktualny kontrakt `Road Physics Profile` i provider kontekstu kroku |
| Aktor, spline prezentacyjny, kamera, HUD, animacja | wynik odczytu stanu; nie zapis do fizyki |

Używaj SI wewnątrz domeny. Zamieniaj metry na centymetry UE wyłącznie na granicy prezentacji. `grade_decimal=0.08` oznacza 8%, a nie 0,08 stopnia. Sprawdź konwencje znaków w aktualnych strukturach: wiatr, krzywizna, `D` i cross-slope mają różne znaczenia.

Zachowaj stały krok z aktualnego `FixedStepRunner.h` (w bazie tej umiejętności: 0,05 s). Nie zmieniaj go, akumulatora ani modelu integracji dla płynniejszej animacji. Kod referencyjny zawiera już integrator; nie zastępuj go wzorem odtworzonym z pamięci.

## Wykonaj zmianę

1. Odtwórz błąd na najmniejszym istniejącym fixture. Zapisz wejścia, oczekiwane zachowanie i miejsce rozbieżności: model, provider, kontroler, sesja czy prezentacja.
2. Odczytaj odpowiadające sobie implementacje Python i C++ oraz testy. Dla zmian równań/kontraktów zachowaj ich zgodność i jawne tolerancje. Nie zmieniaj wyników wzorcowych tylko dlatego, że nowa implementacja je narusza.
3. Rozwiązuj kontekst trasy z autorytatywnego stanu przed każdym podkrokiem, nie raz na klatkę renderu. Look-ahead zakrętu nie zastępuje nawierzchni aktualnie pod kołami.
4. Zachowaj transakcyjność: nieudany podkrok nie może częściowo przesunąć stanu, akumulatora, zdarzeń granicznych ani oceny techniki. Błędne/nieznane wejście ma zwrócić jawny błąd, nie domyślny asfalt czy zgadniętą liczbę.
5. Rozdziel `Stop` od `Reset/Restart`: zatrzymanie zachowuje stan i akumulator; restart wykonuje istniejący reset sesji. Nie ukrywaj hitcha przez obcięcie delta-time, dystansu lub energii.
6. Dla przyczepności zachowaj wspólny budżet hamowania i zakrętu. Zero hamowania musi zachować przewidzianą regresję poprzedniego integratora. Opór aerodynamiczny, grawitacja i toczenie nie są dodatkowym zużyciem przyczepności hamulca.
7. Zmień tylko odpowiednią warstwę. Input/UI ma korzystać z jednej sesji i istniejącego API; nie twórz drugiej symulacji w HUD, Blueprint ani adapterze trenażera.

## Sprawdź zachowanie

Dobierz testy do zmienionego kontraktu; nie uruchamiaj renderów dla samego modelu Python.

- Sprawdź płaskie/podjazd/zjazd, coasting, wiatr i wartości niepoprawne, jeśli dotyczą zmiany sił.
- Porównaj identyczne wejścia przy 30/60/120 FPS i jitterze, jeżeli zmieniasz runner/runtime. Zgodność dotyczy stanu fizyki i zdarzeń, nie tylko końcowego transformu aktora.
- Sprawdź początek/koniec odcinka, zmianę nawierzchni i cross-slope, jeżeli zmieniasz zapytania trasy.
- Zweryfikuj rollback oraz brak resetu przy przejściach i błędach, jeśli ruszasz sesję lub runner.

Przykład testu istniejącej granicy nawierzchni, z katalogu repozytorium w POSIX:

```sh
PYTHONPATH=physics_reference/src python -m unittest discover -s physics_reference/tests -p test_mixed_surface_reference.py -v
```

W PowerShell ustaw `PYTHONPATH` na `physics_reference/src` i uruchom tę samą komendę `python -m unittest ...`. Sprawdź wymaganą wersję Pythona w `physics_reference/pyproject.toml`. Dla innego błędu wybierz jego rzeczywisty moduł testowy. Zmiany C++ wymagają właściwej natywnej kompilacji i Automation przez istniejący tor UE; użyj `$yacs-unreal-integration` i `$yacs-verify-evidence`.

## Kieruj dalsze systemy według roadmapy

| Zadanie | Postępowanie |
|---|---|
| Zakręty, scoring, konsekwencje | Utrzymuj istniejące kontrakty; nowe funkcje prowadź według bieżącego gate M4. Nie dodawaj crash/fall do MVP. |
| HUD i przebieg sesji | Sprawdź M5 i sekcję HUD w Product Requirements. Wyświetlaj stan domeny, zachowaj jednostki i lifecycle. Panel diagnostyczny nie jest finalnym HUD. |
| Rowerzysta, rower, mocap i kamera | Sprawdź M6; kieruj warstwę wizualną do specjalisty DCC/Unreal. Kadencja steruje prezentacją pedałowania; animacja nie produkuje mocy. |
| Pogoda i audio | Sprawdź M8. Oddziel deterministyczne wejścia środowiska od efektów wizualnych/audio; zachowaj seed i oś czasu dla odtwarzalności. |
| Zapis aktywności i FIT | Sprawdź M9 oraz wymagane pola MVP. Użyj aktualnej oficjalnej dokumentacji formatu i istniejącego kodu; poprawność eksportu sprawdź niezależnym odczytem. Nie deklaruj eksportera na podstawie samego JSON. |
| Replay/telemetria | Sprawdź konkretny kontrakt i zakres. Odróżnij log diagnostyczny, zapis aktywności i replay deterministyczny; nie obiecuj zgodności między wersjami bez schematu i dowodu. |
| BLE/FTMS/ANT+ i prawdziwy trenażer | Sprawdź aktualne Product Requirements i otwarcie zakresu; w bazowym MVP wejście jest testowe. Adapter ma dostarczać istniejące wielkości domenowe, a brak sprzętu oznacza brak dowodu sprzętowego. |

## Zwróć sprawdzalny wynik

Podaj zakres/SHA, zmienione pliki, zachowane lub zmienione kontrakty, komendy i liczby wykonanych testów oraz faktyczne braki natywnej weryfikacji. Rozdziel zgodność modelu, integrację UE, obraz i wydajność. Nie przenoś historycznego PASS na nowy kod ani nie nazywaj syntetycznej nawierzchni skalibrowanym modelem prawdziwej drogi.
