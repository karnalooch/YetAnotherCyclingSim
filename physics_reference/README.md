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

## Obecny stan

Model zawiera zdefiniowane **kontrakty danych**: niezmienne rekordy
`RiderParameters`, `Environment`, `RiderInput` i `SimulationState` (dataclass
ze `slots`), z walidacją wartości w momencie tworzenia i komunikatami
`ValueError` dla błędnych danych. Na ich podstawie zaimplementowano siły
(grawitacja, opór toczenia, opór aerodynamiczny) oraz pojedynczy
deterministyczny krok symulacji `step_simulation` metodą bilansu energii.
Wyniki zostaną następnie przeniesione do C++ w UE5.
