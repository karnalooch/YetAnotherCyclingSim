# cycling_physics — referencyjny model fizyki

Ten katalog zawiera **referencyjny, deterministyczny model fizyki kolarstwa** napisany w Pythonie.

Jego celem jest **weryfikacja wzorów i zachowania modelu fizycznego zanim zostanie
zaimplementowany w Unreal Engine 5 w języku C++** (Etap 1 roadmapy). Python pozwala
szybko testować logikę poza edytorem, bez uruchamiania silnika graficznego.

## Właściwości

- Model jest deterministyczny: te same dane wejściowe zawsze dają te same wyniki.
- Fizyka używa stałego kroku czasowego i jednostek SI.
- Do działania wystarczy **biblioteka standardowa Pythona 3.14 lub nowsza** —
  nie trzeba instalować żadnych zależności.
- Testy korzystają wyłącznie z modułu `unittest` ze standardowej biblioteki.

## Struktura

```
physics_reference/
  pyproject.toml      metadane projektu
  README.md           ten plik
  examples/
    run_demo.py       przykładowy przejazd demonstracyjny
  src/
    cycling_physics/
      __init__.py     pakiet Python
      model.py        kontrakty danych, siły i krok symulacji
  tests/
    test_model.py     testy kontraktów danych, sił i kroku symulacji
```

## Uruchamianie testów

Z katalogu `physics_reference/`:

```
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

Na systemach z powłoką POSIX odpowiednikiem jest:

```
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Przykład uruchomienia

Skrypt `examples/run_demo.py` symuluje 60-sekundowy przejazd z krokiem
20 Hz przez cztery fazy (start na płaskim, podjazd, zjazd bez pedałowania,
zjazd z mocą) i wypisuje stan co 5 sekund oraz podsumowanie.

Z katalogu `physics_reference/`, w aktywnym środowisku z zainstalowanym
pakietem:

```
python examples/run_demo.py
```

Jeśli pakiet nie jest zainstalowany (bez `pip install -e .`), wskaż katalog
`src` zmienną `PYTHONPATH`, np. w PowerShell:

```
$env:PYTHONPATH = "src"
python examples/run_demo.py
```

Przejazd przykładową trasą segmentową `ALPINE_JOURNEY` (10 km, „Alpine
Journey") z planem mocy, aż do mety:

```
python examples/run_alpine_route.py
```

## Obecny stan

Model zawiera zdefiniowane **kontrakty danych**: niezmienne rekordy
`RiderParameters`, `Environment`, `RiderInput` i `SimulationState` (dataclass
ze `slots`), z walidacją wartości w momencie tworzenia i komunikatami
`ValueError` dla błędnych danych. Na ich podstawie zaimplementowano siły
(grawitacja, opór toczenia, opór aerodynamiczny) oraz pojedynczy
deterministyczny krok symulacji `step_simulation` metodą bilansu energii.
Wyniki zostaną następnie przeniesione do C++ w UE5.

## Syntetyczny test asfalt - szuter - asfalt

`examples/run_mixed_surface.py` wykonuje ciągły przejazd po 300-metrowej trasie testowej, używając istniejącego Road Physics Profile, oporu toczenia i kroku 0,05 s. Jawna polityka przyczepności jest odczytywana niezależnie; prostoliniowy przykład nie wykonuje pokonywania zakrętów ani hamowania.

**Wszystkie parametry i geometria są syntetycznymi danymi testowymi. Nie są skalibrowanym modelem gravela, rzeczywistą trasą Passo Giau ani dowodem integracji z Unreal.** Zmiana nawierzchni nie resetuje prędkości, dystansu ani czasu; brak polityki nie zamienia się w asfalt. Ostatni krok może nieznacznie przekroczyć koniec trasy bez ukrytego przycinania stanu.

Z katalogu głównego repozytorium w PowerShell:

```powershell
$env:PYTHONPATH = "physics_reference/src"
python physics_reference/examples/run_mixed_surface.py
python -m unittest discover -s physics_reference/tests -p test_mixed_surface_reference.py -v
```

W powłoce POSIX:

```sh
PYTHONPATH=physics_reference/src python physics_reference/examples/run_mixed_surface.py
PYTHONPATH=physics_reference/src python -m unittest discover -s physics_reference/tests -p test_mixed_surface_reference.py -v
```

Przykład wypisuje JSON z ostrzeżeniem `SYNTHETIC_ONLY_NOT_CALIBRATED_NOT_A_REAL_ROUTE`, przejściami nawierzchni i końcowym stanem. Zestaw regresji sprawdza granice odcinków, deterministyczność, grupowanie podkroków, niezależność przyczepności/oporu i brak resetowania stanu. Jest automatycznie wykrywany przez istniejące `scripts/ci/run_python_tests.py`; nie potrzebuje renderów ani kompilacji UE.
