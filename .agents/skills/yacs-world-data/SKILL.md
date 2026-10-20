---
name: yacs-world-data
description: "Sprawdzaj i przygotowuj rzeczywiste dane świata YetAnotherCyclingSim (YACS): Sa Calobra/Ma-2141, DTM/DEM/MDT, LiDAR, ortofoto, land cover, Catastro/BTN/SIOSE, CRS, NoData, maski i World Authority. Używaj przy pozyskiwaniu, normalizacji, sprawdzaniu pokrycia i pochodzenia danych oraz rozbieżnościach geografii, wysokości i masek przed Houdinim lub Unrealem."
---

# YACS — dane geograficzne i World Authority

## Ustal źródło i zakres

1. Odczytaj aktualny SHA, `AGENTS.md`, `docs/ai/roles/world-data.md`, odpowiednie sekcje `docs/WORLD_BUILDING_BIBLE.md` i zadanie użytkownika. [Mapa źródeł](references/source-map.md) wskazuje istniejące manifesty i narzędzia.
2. Ustal wymagany AOI z bieżącego zadania/manifestu: granice, pełny przebieg drogi, bufor, otoczenie oraz siatkę. Nie zastępuj całego wymaganego Landscape wygodnym wycinkiem. Rozróżnij zakres danych źródłowych, zakres authoringu i zakres testu.
3. Nie przenoś liczb ze starszego benchmarku na nowy obszar. Historyczny kwadrat 4033 próbek i kontekst 8 km mają własne kontrakty; wywołuj ich helpery tylko dla zgodnych wejść.
4. Odkrywaj i odczytuj istniejące źródła/cache przed pobieraniem. Nowe źródła sprawdzaj w aktualnej dokumentacji dostawcy: produkt, wydanie, dostęp, licencja, metadane i rzeczywiste pokrycie. Nie zgaduj nazw plików z numerów siatki.

## Przyjmij jawny kontrakt danych

Zapisz w istniejącym manifeście/receipcie, bez tworzenia równoległego frameworka:

- dostawcę, produkt, wydanie/datę odniesienia, URL lub dokładny identyfikator;
- dozwolony sposób użycia i wymagane attribution, zgodnie z rejestrem proweniencji;
- oryginalny CRS, kolejność osi, jednostki i interpretację pionową wysokości;
- bbox, rozdzielczość/gęstość punktów, rozmiary rastra, transformację i regułę próbkowania;
- NoData/invalid/unknown, typ i semantykę każdego kanału;
- rzeczywiste rozmiary i SHA-256 wejść, wersje narzędzi, parametry pochodnych;
- klasę dowodu: fakt źródłowy, pomiar wyprowadzony, wnioskowanie albo dekorację.

Nie uznawaj poprawnego formatu hash za weryfikację pliku. Oblicz hash z dostępnych bajtów lub oznacz ten krok jako niewykonany. Wskaźnik LFS nie jest plikiem wysokości ani chmurą punktów.

## Zachowaj znaczenie źródeł

| Dane | Do czego wolno ich użyć |
|---|---|
| Zweryfikowany DTM/MDT lub właściwe punkty ground | Źródłowa rzeźba gruntu i pomiary względem gruntu |
| DSM/MDS, dachy, korony | Powierzchnia obiektów; nie zamiennik gruntu |
| Ortofoto | Obraz i dowód przestrzenny/epoka; nie wysokość gruntu |
| Zweryfikowany przebieg GIS drogi | Położenie XY i topologia zgodnie z przyjętym kontraktem |
| Maski pochodne | Reprodukowalne pomiary/klasyfikacja z confidence i unknown |
| Wynik Houdini/PCG/DCC | Reprezentacja danych; nie nowa niezależna geografia |

Zachowaj skalę 1 m rzeczywisty = 1 m świata. Oddziel błąd próbkowania/konwersji od ręcznej korekty i proceduralnego detalu. Mała odwracalna deformacja nie staje się pomiarem geodezyjnym. Spór źródeł zapisz wraz z datą, dokładnością i objętym obszarem; nie ukrywaj go przesuwaniem drogi czy gór.

## Przygotuj i sprawdź pochodne

1. Zweryfikuj pliki oraz ich nagłówki: CRS, bbox, bandy, rozmiary, typy, pionowy datum/interpretację i NoData. Dla usług sprawdź kompletność paginacji/feature count, błędy WFS i zgodność żądanego wydania.
2. Zestaw źródła na przyjętej siatce. Jawnie sprawdź transformację GIS → lokalne metry → UE cm, położenie centrów próbek i kierunek osi. Nie poprawiaj przesunięcia obrazu zgadniętym znakiem offsetu.
3. Użyj istniejącej dopuszczonej receptury i helperów. W przypadku innych wymiarów/CRS najpierw oceń ich kontrakt i ograniczenia; nie wyłączaj asercji, aby przepuścić nowy obszar.
4. Zachowaj NoData/unknown także po cropie, resamplingu i pochodnych. Brak returnów LiDAR nie jest dowodem nieistnienia obiektu; pusta mapa footprintów nie dowodzi wolnego miejsca. Interpolacja kolorów nie może tworzyć pozwolenia na placement.
5. Zachowaj rozłączne kanały lub jawne priorytety: grunt, droga/pobocze/BOB, budynki, roślinność, pola, hydrologia/infrastruktura, skały i strefy niewiadome. Nie rozszerzaj BOB na cały świat.
6. Weryfikuj niezależnym czytnikiem: hashe, CRS/grid/dtype/NoData, maski ważności, pokrycie i statystyki. Porównuj z tym samym źródłem i siatką; osobno mierz błąd kodowania wysokości.
7. Dla kafli sprawdź wspólne krawędzie i narożniki zarówno wysokości, jak i ważności/masek. Zachowaj wynik dla wszystkich wymaganych styków. Kolorowy preview nie dowodzi bezszwowej geometrii.
8. Przekaż Houdini/UE jednoznaczny manifest wejść i braków. Czytnik offline nie dowodzi poprawnego odczytu materiału, widoczności NoData, geometrii ani kolizji w Unreal.

## Korzystaj z istniejących helperów

Odczytaj ich bieżące `--help` i wejścia. Poniższy planner tylko sprawdza zadeklarowany manifest; nie pobiera ani nie potwierdza fizycznych źródeł:

```sh
python scripts/assets/plan_sa_calobra_world_data.py --manifest worldgen/terrain/benchmarks/sa_calobra/world_data/working_space_sources.json --json
```

Dla istniejącego formatu pochodnych użyj właściwego `verify_normalized_context.py` albo `verify_sa_calobra_lidar_masks.py` z rzeczywistą ścieżką manifestu. Dla innego producenta wybierz jego czytnik zamiast wymuszać niezgodny schemat. Duże surowe dane przechowuj w istniejącym cache; nie publikuj automatycznie prywatnego/draft zbioru w publicznym repozytorium.

## Raport i przekazanie

Podaj: SHA kodu, źródła i ich hashe, wymagany/obecny AOI, ważne/nieważne próbki, pokrycie, przyjęte transformacje, pomierzone rozbieżności i brakujące dowody. Rozdziel `pobrano`, `zweryfikowano bajty`, `utworzono pochodne`, `odczytano pochodne`, `sprawdzono w UE`.

Przekaż geometrię/detal do `$yacs-houdini-world`, drogi/earthworks do `$yacs-road-bob`, a test konsumenta do `$yacs-unreal-integration`. Jeśli nazwa specjalisty została zmieniona, wybierz odpowiadającą rolę z aktualnego routera; nie twórz nowej receptury na podstawie samego braku umiejętności.
