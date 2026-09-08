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
  src/
    cycling_physics/
      __init__.py     pakiet Python
      model.py        kontrakty danych fizyki (bez równań ruchu)
  tests/
    test_model.py     testy kontraktów danych i walidacji
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

## Obecny stan

Model zawiera zdefiniowane **kontrakty danych**: niezmienne rekordy
`RiderParameters`, `Environment`, `RiderInput` i `SimulationState` (dataclass
ze `slots`), z walidacją wartości w momencie tworzenia i komunikatami
`ValueError` dla błędnych danych. Równania ruchu nie zostały jeszcze
zaimplementowane — najpierw powstaną w tym module, a następnie zostaną
przeniesione do C++ w UE5.
