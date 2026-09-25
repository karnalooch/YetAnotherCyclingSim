# YetAnotherCyclingSim — plan assetów

**Status:** aktywny plan produkcyjny  
**Zakres:** MVP `v0.1.0-mvp` + backlog po MVP  
**Budżet początkowy:** do 500 zł łącznie na narzędzia i assety  
**Zasada nadrzędna:** nie kupujemy assetu, dopóki nie ma przypisanego etapu, konkretnego zastosowania i planu walidacji.

## 1. Cel

Ten dokument odpowiada na dwa pytania:

1. Jakich assetów potrzebuje YACS?
2. W którym etapie roadmapy dany asset ma wejść do projektu?

Assety mają wspierać jedną fikcyjną trasę alpejską 20–30 minut. MVP nie jest katalogiem rowerów, postaci ani regionów — priorytetem jest spójna wizualnie, wydajna i grywalna trasa.

## 2. Kolejność pozyskiwania

### Priorytet A — potrzebne przed lub w trakcie budowy MVP

- spójny zestaw landscape / ground materials;
- vegetation dla doliny, lasu i strefy wysokogórskiej;
- rocks / cliffs / scree;
- podstawowe elementy drogi i pobocza;
- jeden model roweru;
- jeden model kolarza + podstawowy strój/kask;
- materiały mokrej nawierzchni;
- podstawowe VFX deszczu / sprayu;
- cycling audio + alpine/nature ambience;
- minimalny zestaw UI: font + ikony.

### Priorytet B — polish MVP

- alpejskie budynki i mała miejscowość;
- roadside props;
- decals asfaltu i pobocza;
- kilka pojazdów i przygotowanych scenek „życia”;
- dodatkowe warianty roślinności;
- dodatkowe VFX atmosferyczne;
- LUT/HDRI tylko jeśli realnie poprawiają wynik względem natywnych systemów UE.

### Priorytet C — po MVP

- tłumy i rozbudowane NPC;
- zwierzęta;
- pełny traffic system;
- wiele modeli rowerów;
- katalog ubrań i personalizacja postaci;
- kolejne regiony / biomy;
- dodatkowe pakiety architektury;
- rozbudowane efekty upadków i kolizji;
- multiplayer-specific crowd presentation.

## 3. Harmonogram assetów wg etapów

| Etap | Co dokładamy | Poziom jakości | Zakup? |
|---|---|---|---|
| **3G — Reference Environment Pass** | landscape materials, trawa, podstawowy las, skały/klify, prosty zestaw meadow→forest→high Alpine, sky/fog/woda jeśli potrzebna | referencyjny baseline, nie final art | tylko gdy darmowe/natywne assety nie wystarczą |
| **4 — zakręty** | debug/guidance decals i proste oznaczenia entry/apex/exit | funkcjonalne | nie planujemy paczki produkcyjnej |
| **5 — HUD** | font, proste ikony/SVG: power, cadence, speed, grade, wind, weather, corner guidance | produkcyjne minimum | tylko jeśli brak dobrego darmowego/licencjonowanego zestawu |
| **6 — kolarz i rower** | 1 rower, 1 rider, strój, kask, skeleton/rig, mocap/retargeting | produkcyjne dla MVP | wysoki priorytet |
| **7 — świat** | pełny vegetation pass, rocks, roadside props, road decals, alpine buildings, village props, landmark props, kilka pojazdów i scenek życia | produkcyjne | główny etap zakupów środowiska |
| **8 — pogoda i audio** | rain/spray VFX, wetness/puddles jeśli potrzebne, wind/leaf particles, drivetrain/freehub/tyres/brakes, rain/forest/village ambience | produkcyjne | selektywnie |
| **9 — zapis/FIT** | brak nowych assetów wymaganych | — | nie |
| **10 — stabilizacja MVP** | tylko brakujące assety blokujące spójność lub czytelność; polish istniejących | final MVP polish | zakupy wyjątkowo, po profilowaniu i review |
| **Po MVP** | kolejne rowery, stroje, tłumy, traffic, zwierzęta, kolejne regiony | rozszerzenia | osobny budżet |

## 4. Lista assetów według kategorii

### 4.1 Środowisko alpejskie

Potrzebne:

- landscape master material;
- meadow / grass ground;
- forest floor;
- dirt / mud;
- gravel;
- exposed rock;
- alpine scree;
- snow patch opcjonalnie, jeśli pojawi się w wysokiej strefie;
- blend/macro variation pozwalające ukryć tiling;
- wetness support dla materiałów, które tego wymagają.

**Wchodzi:** baseline w 3G, finalizacja w Stage 7, wet variants w Stage 8.

### 4.2 Vegetation

Potrzebne:

- trawa łąkowa;
- małe krzaki;
- paprocie;
- kwiaty / drobna roślinność jako spice;
- świerki / jodły / sosny;
- kilka drzew liściastych dla doliny;
- niska roślinność wysokogórska.

Wymagania techniczne:

- LOD/Nanite/instancing dobierane po benchmarku;
- kontrola density;
- daleka roślinność nie może domyślnie ponosić kosztu pełnego WPO/wind;
- możliwość deterministycznego rozmieszczenia w proofach.

**Wchodzi:** 3G minimum, Stage 7 produkcyjnie.

### 4.3 Rocks / cliffs / terrain dressing

Potrzebne:

- duże cliff faces;
- średnie boulders;
- małe rocks;
- roadside stones;
- scree / rubble;
- retaining-rock variants.

To jedna z trzech najważniejszych grup wizualnych razem z vegetation i landscape materials.

**Wchodzi:** 3G minimum, Stage 7 final.

### 4.4 Droga i pobocze

Potrzebne:

- asphalt material;
- wet asphalt variant;
- road markings;
- shoulder/gravel edge;
- guard rails;
- bollards / delineators;
- road signs;
- stone retaining walls;
- drainage / culvert props;
- barriers;
- decals: cracks, patches, stains, tyre marks.

Droga pozostaje częścią systemu YACS; nie kupujemy „gotowej trasy”. Assety jedynie ubierają geometrię.

**Wchodzi:** część wizualna w 3G/7, wetness w 8.

### 4.5 Kolarz

MVP potrzebuje jednej dopracowanej postaci:

- bazowy model człowieka;
- cycling jersey;
- bib shorts;
- cycling shoes;
- gloves;
- helmet;
- glasses opcjonalnie;
- skeleton/rig nadający się do retargetingu w UE;
- sensowna topologia i skinning.

Animacja:

- istniejący cycling mocap jako warstwa bazowa;
- proceduralne pozycje: seated, aero, descending tuck, standing/sprint, cornering;
- Control Rig;
- hand IK;
- foot/pedal IK;
- look-ahead / head stabilization.

**Wchodzi:** Stage 6.

### 4.6 Rower

MVP potrzebuje jednego road bike'a z możliwie rozdzielonymi elementami:

- frame;
- fork;
- handlebar;
- wheels;
- crank;
- pedals;
- cassette;
- derailleurs;
- brake components;
- saddle.

Preferujemy model, w którym koła, korba i elementy wymagające animacji nie są zespawane w jeden mesh.

Model może pochodzić z marketplace'u albo z pipeline'u Tripo/Meshy, jeżeli przejdzie review geometrii, topologii, skali i materiałów.

**Wchodzi:** Stage 6.

### 4.7 Architektura alpejska

Minimalny zestaw modularny:

- chalet / house;
- barn/farm building;
- small hotel/inn;
- mountain hut;
- chapel/church element;
- retaining wall;
- tunnel portal;
- small bridge;
- fences;
- village street props.

Nie potrzebujemy dużego city packa. Dla MVP wystarczy około 10–15 dobrze dobranych elementów, które można rozsądnie reużywać.

**Wchodzi:** Stage 7.

### 4.8 Życie przy trasie

Minimalny zestaw:

- 2–4 samochody;
- van / camper;
- motocykl opcjonalnie;
- kilka rowerów/kolarzy jako dressing;
- proste pedestrian NPC;
- benches;
- tables/chairs;
- bins;
- tourism/signage props;
- parking / roadside props.

MVP nie wymaga pełnej symulacji ruchu. Preferujemy przygotowane scenki i ambience.

**Wchodzi:** Stage 7.

### 4.9 Pogoda / VFX

Potrzebne:

- rain;
- wheel spray;
- road wetness;
- puddles opcjonalnie;
- mist/fog;
- wind-driven leaves/debris;
- dust/pollen/insects jako subtelne dodatki;
- skid/brake FX tylko jeśli mechanika faktycznie tego używa.

Najpierw używamy natywnych systemów UE (SkyAtmosphere, Volumetric Clouds, Niagara itd.). Nie kupujemy dużego weather frameworka przed udowodnieniem konkretnej luki.

**Wchodzi:** Stage 8; część atmosfery już w 3G.

### 4.10 Audio

Cycling:

- drivetrain;
- freehub/coasting;
- shifting;
- tyres on dry asphalt;
- tyres on wet asphalt;
- braking;
- wheel/spray details.

Environment:

- low/high wind;
- rain;
- forest;
- birds;
- insects;
- stream/river;
- village ambience;
- distant vehicles;
- optional cowbells/bells jako detal alpejski.

**Wchodzi:** Stage 8.

### 4.11 UI

Minimalny zestaw:

- czytelny font;
- ikony: power, cadence, speed, grade, distance, time, wind, weather, corner difficulty;
- elementy elevation profile;
- marker pozycji na profilu;
- guidance shapes/patterns.

Nie kupujemy pełnego fantasy/sci-fi UI kitu. HUD ma być budowany pod YACS.

**Wchodzi:** Stage 5.

### 4.12 Sky / lighting / color

Najpierw wykorzystujemy natywne UE:

- SkyAtmosphere;
- Volumetric Clouds;
- Exponential Height Fog;
- Lumen / obecny system oświetlenia projektu.

Dodatkowe HDRI, sky presets lub LUT-y kupujemy/dodajemy wyłącznie wtedy, gdy porównanie BEFORE/AFTER pokazuje realną poprawę.

**Wchodzi:** 3G i później polish w 7/8.

## 5. Minimalny koszyk MVP

Jeżeli trzeba będzie kupować paczki, preferowana kolejność to:

1. **spójny Alpine/Mountain Environment albo landscape/ground foundation**;
2. **Conifer/Alpine Vegetation**;
3. **Rocks & Cliffs**;
4. **European Road / Roadside Props**;
5. **Alpine Buildings / Village**;
6. **Cycling + Nature Audio**;
7. **Vehicles / roadside-life pack**.

Rider i bike mogą pochodzić z osobnego zakupu albo z kontrolowanego pipeline'u generowania 3D; ich wybór jest częścią Stage 6.

## 6. Reguły zakupu i importu

Przed zakupem lub trwałym importem zapisujemy:

- nazwę assetu/paczki;
- źródło;
- licencję;
- cenę;
- datę pozyskania;
- etap roadmapy;
- dokładne zastosowanie;
- czy asset może trafić do repo/LFS;
- wymagania atrybucji;
- ryzyko vendor lock-in;
- wynik podstawowego testu wydajności.

Nie importujemy całej paczki „na zapas”. Do projektu trafiają tylko potrzebne elementy, o ile licencja i sposób dystrybucji na to pozwalają.

## 7. Kryteria techniczne przed akceptacją assetu

Każdy większy asset lub pack powinien przejść odpowiedni podzbiór kontroli:

- poprawna skala UE;
- pivot/orientation;
- UV/materials;
- collision;
- LOD/Nanite suitability;
- liczba materiałów;
- koszt shaderów;
- WPO/wind cost;
- rozmiar tekstur;
- RAM/VRAM;
- draw calls / instancing behavior;
- wpływ na shader compile/cook;
- licencja i możliwość dystrybucji w buildzie;
- brak niepotrzebnych zależności od pluginów.

## 8. Asset ledger

Po wyborze konkretnych paczek tabela poniżej staje się rejestrem źródła prawdy.

| Asset / pack | Źródło | Licencja | Cena | Stage | Status | Uwagi |
|---|---|---|---:|---|---|---|
| — | — | — | — | — | do wyboru | — |

Statusy: `candidate`, `approved`, `acquired`, `imported`, `validated`, `rejected`.

## 9. Definition of done dla asset passu MVP

Asset pass MVP jest ukończony, gdy:

- dolina, las i high Alpine są wizualnie rozróżnialne, ale spójne;
- droga i pobocze nie wyglądają jak placeholder;
- rider i bike są wiarygodne w obu kamerach;
- kilka starannie przygotowanych miejsc nadaje światu „życie” bez pełnego traffic systemu;
- pogoda ma widoczny i słyszalny wpływ na świat;
- assety nie łamią celu 1080p/60 FPS na RTX 2070 Super;
- nie ma niewyjaśnionych problemów licencyjnych;
- repo nie zawiera przypadkowego dumpu całych paczek marketplace;
- końcowa lista użytych assetów jest zapisana w Asset Ledger.
