---
name: yacs-road-bob
description: "Diagnozuj i naprawiaj w zatwierdzonym zakresie drogi oraz roboty ziemne YetAnotherCyclingSim (YACS): Ma-2141, nawrotki, canonical route XY, Road Physics Profile, BOB, cut/fill, pobocza, banking, kolizję i kontakt z Landscape. Używaj przy wiszącej drodze, penetracji gruntu, ostrych zmianach profilu, szerokości lub krzywizny oraz przygotowaniu kolejnego dopuszczonego etapu drogi."
---

# YACS — droga i BOB

## Odtwórz zakres bez rozpoczynania drugiego pipeline'u

1. Przeczytaj `AGENTS.md`, aktualny issue/SHA, `docs/ROADMAP.md`, rolę `docs/ai/roles/road-bob.md` i właściwe kontrakty z [mapy źródeł](references/source-map.md).
2. Ustal, czy zadanie dotyczy odczytu, naprawy istniejącego konsumenta czy nowej geometrii. Zadanie samego Landscape/masek nie przyznaje automatycznie zakresu budowy drogi.
3. Zachowaj obecne zgody użytkownika i kontynuuj dozwolone kroki. Zbierz dostępne dane przed zgłoszeniem konkretnej brakującej zależności; nie uruchamiaj zbędnej pętli potwierdzeń.
4. Dla nowej geometrii użyj obecnie wybranej receptury SideFX/Houdini. Historyczne skrypty BOB/PCGEx służą tylko w swoich dopuszczonych rolach. Nie kopiuj starej naprawy jako uniwersalnego generatora.

## Ustal właścicieli

- Zweryfikowany przebieg GIS i canonical route zachowują XY, kilometraż i znaczące zakręty.
- `Road Physics Profile` zachowuje fizyczny profil, `S/D`, szerokość, bank, krzywiznę i nawierzchnię.
- BOB odpowiada za analizę drogi/earthworks i dopuszczone ograniczenia cut/fill; nie jest Terrain/Vegetation/Building Authority.
- Houdini lub inny wyraźnie dopuszczony wykonawca realizuje geometrię z tych wejść.
- Mesh, spline prezentacyjny, materiał i aktor UE są konsumentami; nie mogą bezgłośnie przenieść drogi, zmienić fizyki ani zamaskować defektu gruntu.

Zachowaj `Base_DTM`, oddzielne `Road_Earthworks` i odwracalny lokalny zakres. Nie wnioskuj o zgodzie na globalny rebuild z lokalnego błędu. Gdy heightfield nie potrafi przedstawić rozdzielonych wysokości/przewieszenia, zgłoś potrzebę właściwej konstrukcji zamiast fałszować teren.

## Zdiagnozuj przed korektą

1. Zidentyfikuj problem na rzeczywistej drodze: chainage `S`, strona/dystans `D`, actor/package, aktualne źródła, zakres AOI i wersja geometrii. Obraz bez tych danych jest wskazówką, nie pomiarem.
2. Sprawdź CRS, skalę, pionowe odniesienie, offset, NoData i zgodność footprintu. MDS lub korona drzew nie mogą stać się drogowym gruntem. Zła konwersja może udawać kanion lub estakadę.
3. Zbierz próbki na całej szerokości i wymaganym odcinku, także we wnętrzach trójkątów, na krawędziach, styku kafli i zbliżonych gałęziach nawrotki. Nie wykluczaj trudnych miejsc z miary pokrycia.
4. Oblicz residual `road_surface_z_m - landscape_z_m` i interpretuj znak według bieżącego inspektora. Zachowaj trace misses oraz identyfikację trafionego obiektu; trafienie backgroundu nie dowodzi kontaktu docelowej drogi/terenu.
5. Użyj `bob_profile_inspector.py` dla zgodnego profilu i `bob_terrain_fit_inspector.py` dla zgodnych pomiarów. Odczytaj wymagane schema, odstęp próbek i progi z bieżącego kodu. Ich historycznych 300 m/0,5 m nie ustanawiaj normą dla całej trasy.
6. Rozdziel objaw i przyczynę: duży residual nie dowodzi muru, mostu, wypełnienia ani błędnej epoki. W raporcie zachowaj `UNRESOLVED`, gdy źródła nie rozstrzygają.

## Rozpoznawaj wynik inspektora

| Wynik | Znaczenie |
|---|---|
| `INSPECTION_INCOMPLETE` | Brakuje poprawnego wymaganego wejścia/pokrycia |
| `REVIEW_REQUIRED` | Przekroczono jawne progi diagnostyczne |
| `REVIEW_PENDING` | Wykonany zestaw nie znalazł przekroczeń; nadal brak akceptacji drogi |
| `CONTACT_OK` w próbce | Tylko ta próbka mieści się w zadeklarowanym paśmie kontaktu |
| `STRUCTURE_REVIEW` | Wymaga rozstrzygnięcia geometrii/konstrukcji; nie jest poleceniem generowania muru |

`inspection_complete` nie dowodzi pełnej prawdy źródłowej ani rideability. Poprawny hash zapisany w kandydacie nie zastępuje odczytu jego źródła. Nie włączaj `road_admitted` czy learning na podstawie inspektora. Zweryfikowany przypadek uczenia BOB wymaga procedury i akceptacji zapisanej w aktualnym kontrakcie.

## Napraw ograniczony problem

1. Wybierz najmniejszą zmianę odpowiadającą pomiarom: poprawkę transformacji/źródła, profilu, lokalnego earthworks lub konsumenta. Nie obniżaj progu testu, żeby ukryć problem.
2. Przed authoringiem zapisz granice zmiany, niezmieniane źródła, parametry, miejsce wyjściowe i sposób rollbacku. Użyj istniejącej receptury; nie resetuj aktywnego świata użytkownika.
3. Dla pojedynczego łuku sprawdź znak krzywizny i całkowity obrót osi oraz obu fizycznych krawędzi. Wejście, łuk i wyjście mają ten sam kierunek. Sama ciągłość G2 i gęsta tessellacja nie usuwają nosa, zwężenia czy odwrotnego łuku.
4. Zachowaj jawną bazową szerokość podejść. Poszerzenie w łuku wymaga uzasadnienia swept-path i płynnego powrotu przed wyjściem; nie utożsamiaj automatycznie linii GIS z osią nawierzchni.
5. Sprawdź powiązanie szerokości, banku i przejść z Road Physics Profile. Materiał asfaltu, blend/RVT, skały lub żwir nie mogą naprawiać brakującej podpory ani penetracji.
6. Ponownie zmierz zmieniony kandydat. Przejście testu starego profilu lub surowego DTM-conforming preview nie dowodzi kontaktu po regularizacji/wygładzeniu.

## Walidacja i przekazanie

Dla zmian samego klasyfikatora dobierz istniejące testy inspektora. Dla zmian geometrii wymagaj pomiarów krawędzi/wnętrz/pokrycia, tożsamości trafień, zapisania i świeżego otwarcia, natywnej kolizji oraz widoków z drogi i planu. Przypisz dowody do aktualnego SHA/kandydata i użyj `$yacs-verify-evidence`.

Zwróć: źródła, segment/AOI, before/after metryk, wprowadzone zmiany, rzeczywiste testy, pozostałe misses/penetrations/unsupported, ryzyko i następny dozwolony krok. Zachowaj odrębność technicznego dowodu, przeglądu wizualnego, owner signoff i wydajności; końcowej akceptacji użytkownika nie zastępuje subagent.
