# YetAnotherCyclingSim — plan assetów

**Status:** aktywny plan produkcyjny  
**Zakres:** MVP `v0.1.0-mvp` + backlog po MVP  
**Budżet początkowy:** do 500 zł łącznie na narzędzia i assety  
**Zasada nadrzędna:** nie kupujemy assetu, dopóki nie ma przypisanego etapu, konkretnego zastosowania i planu walidacji.

## 1. Cel

Ten dokument odpowiada na cztery pytania:

1. Jakich **source assets** potrzebuje YACS?
2. Jakich **technical UE assets** musimy zbudować sami?
3. W którym etapie roadmapy dany asset ma wejść do projektu?
4. Jak go walidujemy, wersjonujemy i utrzymujemy?

Assety mają wspierać jedną fikcyjną trasę alpejską 20–30 minut. MVP nie jest katalogiem rowerów, postaci ani regionów — priorytetem jest spójna wizualnie, wydajna i grywalna trasa.

### 1.1 Dwa typy assetów

**Source assets** to wejściowe zasoby artystyczne lub nagraniowe pozyskane z zewnątrz albo wygenerowane poza UE, np.:

- vegetation meshes;
- rocks/cliffs;
- landscape textures;
- rider/bike meshes;
- mocap clips;
- audio samples;
- UI icons/fonts.

**Technical UE assets** to produkcyjne zasoby tworzone i wersjonowane wewnątrz projektu Unreal, np.:

- PCG Graphs / PCG Settings;
- Material / Material Instance;
- IK Rig / IK Retargeter;
- Control Rig;
- Niagara System / Emitter;
- MetaSound Source / Patch;
- Data Assets / Data Tables;
- generated helper meshes;
- Editor Utility assets;
- World/Level assets i inne deterministyczne outputy generatora.

Technical UE asset może być równie krytyczny produkcyjnie jak model 3D. Nie traktujemy go jako „narzędziowego śmiecia” tylko dlatego, że powstał wewnątrz Unreal Editor.

### 1.2 Kontrakt progresywnego wdrażania assetów

Assety w YACS **nie są odkładane do jednego końcowego art passu**. Każdy etap ma własny minimalny asset gate i ten gate jest częścią Definition of Done etapu.

Obowiązuje sekwencja:

`candidate -> approved -> acquired -> imported -> validated`

gdzie:
- `candidate` oznacza wyłącznie potencjalnie pasujący zasób;
- `approved` oznacza zaakceptowane źródło/licencję i konkretne zastosowanie;
- `acquired` oznacza pobranie/pozyskanie źródła z zapisaną provenance;
- `imported` oznacza kontrolowany import potrzebnej części do projektu, bez dumpowania całej paczki;
- `validated` oznacza użycie w docelowym etapie oraz odpowiedni proof wizualny/techniczny/wydajnościowy.

**Nie wolno zamknąć etapu tylko dlatego, że kod, build lub CI są zielone, jeśli jego wymagane assety nadal są jedynie `candidate` / `approved`.** Późniejszy Stage 7 rozwija środowisko produkcyjnie, ale nie przejmuje zaległego minimum ze Stage 3G, Stage 5 ani Stage 6.

Dla technical UE assets analogicznie: `planned` nie spełnia asset gate'u. Wymagany element musi przejść przez `prototype` / `reviewed` do `validated` w etapie, do którego został przypisany.

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

| Etap | Source assets | Technical UE assets | Poziom jakości / zakup |
|---|---|---|---|
| **3G — Reference Environment Pass** | landscape materials, grass, trees, rocks/cliffs, sky/fog inputs, water input jeśli potrzebny | PCG graphs/settings, material instances, biome/exclusion assets, generated helper geometry, proof worlds/data | **obowiązkowy referencyjny baseline przed dalszym Stage 4**; zakup tylko gdy darmowe/natywne zasoby nie wystarczą |
| **4 — zakręty** | proste decals/markery guidance | debug/guidance material instances, ewentualne spline/decal helper assets | funkcjonalne; bez paczki produkcyjnej |
| **5 — HUD** | font, ikony/SVG | UMG widget assets, style/data assets | produkcyjne minimum |
| **6 — kolarz i rower** | 1 bike, 1 rider, strój, kask, mocap | IK Rig, IK Retargeter, Control Rig, Animation/Blend assets, rider/bike presentation data | produkcyjne dla MVP; wysoki priorytet |
| **7 — świat** | pełny vegetation/rocks/roadside/buildings/vehicles pass | production PCG graphs, generator data assets, generated helper meshes, material instances, optional world-authoring utility assets | główny art pass |
| **8 — pogoda i audio** | audio samples, VFX textures/noise jeśli potrzebne | Niagara systems/emitters, MetaSound sources/patches, wet-weather material instances | produkcyjne; zakupy selektywne |
| **9 — zapis/FIT** | brak wymaganych source assets | ewentualne Data Assets/config assets dla profili eksportu | zwykle bez zakupów |
| **10 — stabilizacja MVP** | wyłącznie braki blokujące spójność | finalizacja/cleanup technical assets, redirectors/dependencies, asset audit | final MVP polish |
| **Po MVP** | kolejne rowery, stroje, tłumy, traffic, regiony | nowe PCG biomy, rigs, VFX/audio graphs, crowd/world systems | osobny budżet |

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

### 4.13 Technical UE assets

Ta kategoria obejmuje assety tworzone **wewnątrz Unreal Engine** lub generowane przez nasze tooling/flows. Nie wymagają zakupu, ale wymagają planu produkcyjnego tak samo jak source art.

#### Stage 3G / world generation

Planowane:

- `PCG_Valley`;
- `PCG_Forest`;
- `PCG_HighAlpine`;
- `PCG_Roadside`;
- `PCG_RouteExclusion`;
- biome/settings assets;
- material instances dla meadow / forest / high-Alpine;
- generated helper meshes tam, gdzie Geometry Script daje realną wartość;
- WorldSpec-compatible data assets tylko jeśli tekstowy WorldSpec nie wystarcza runtime/editorowi.

Zasady:

- outputy generatora mają trafiać pod `/Game/Generated/YACS/**`;
- source graphs/settings mają żyć w stabilnym, ręcznie wersjonowanym katalogu projektu, nie w `Generated`;
- ten sam seed + input assets + generator version ma dawać równoważny wynik;
- PCG graph jest kodem/konfiguracją produkcyjną i podlega review/proof.

#### Stage 6 / rider

Planowane:

- `IK_Rider`;
- `IK_MocapSource` jeśli źródłowy skeleton tego wymaga;
- `RTG_CyclingMocap`;
- `CR_Cyclist`;
- Animation Blueprint / Blend Spaces / pose assets potrzebne do runtime;
- jawne hand/foot/pelvis/head goal definitions;
- rider presentation Data Asset, jeśli parametry proceduralnej pozy będą wymagały wersjonowanej konfiguracji.

#### Stage 8 / VFX i audio

Planowane:

- `NS_Rain`;
- `NS_WheelSpray`;
- `NS_WindDebris`;
- Niagara emitters wspólne dla systemów powyżej;
- `MS_Drivetrain`;
- `MS_Freehub`;
- `MS_Tyres`;
- `MS_Wind`;
- MetaSound patches dla współdzielonej modulacji, jeśli faktycznie redukują duplikację;
- wetness/material instances zależne od stanu pogody.

#### Konwencja katalogów

Docelowa struktura ma rozdzielać **authoring assets** od **generated outputs**:

```text
Content/YACS/
├── WorldGen/
│   ├── PCG/
│   ├── Materials/
│   ├── Data/
│   └── Utilities/
├── Rider/
│   ├── IK/
│   ├── Rig/
│   ├── Animation/
│   └── Data/
├── Weather/
│   ├── Niagara/
│   ├── Materials/
│   └── Data/
└── Audio/
    └── MetaSounds/

Content/Generated/YACS/
└── ... deterministic generator outputs only ...
```

Nie przenosimy wszystkiego natychmiast do tej struktury. Jest to kontrakt docelowy stosowany przy nowych technical assets; istniejących assetów nie przemieszczamy bez osobnego, bezpiecznego migration tasku.

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

## 8. Source asset ledger

Po wyborze konkretnych paczek tabela poniżej staje się rejestrem źródła prawdy.

| Asset / pack | Źródło | Licencja | Cena | Stage | Status | Uwagi |
|---|---|---|---:|---|---|---|
| Sparse Grass (`sparse_grass`) | Poly Haven | CC0 | 0 zł | 3G | approved | meadow/valley ground; 2K bootstrap |
| Forest Ground 03 (`forrest_ground_03`) | Poly Haven | CC0 | 0 zł | 3G | approved | pine-needle forest floor; 2K bootstrap |
| Rocky Terrain (`rocky_terrain`) | Poly Haven | CC0 | 0 zł | 3G | approved | high-Alpine ground layer; 2K bootstrap |
| Rock Face 01 (`rock_face_01`) | Poly Haven | CC0 | 0 zł | 3G | approved | roadside cliff candidate; performance validation pending |
| Boulder 01 (`boulder_01`) | Poly Haven | CC0 | 0 zł | 3G | approved | sparse rock dressing; prefer instancing |
| Mountainside (`mountainside`) | Poly Haven | CC0 | 0 zł | 3G | candidate | mid-ground mountain mass; compare against cheaper authored geometry |
| Fir Tree 01 (`fir_tree_01`) | Poly Haven | CC0 | 0 zł | 3G | candidate | includes LODs; high source-polycount, must be profiled before forest scatter |
| Grass Medium 01 (`grass_medium_01`) | Poly Haven | CC0 | 0 zł | 3G | candidate | controlled meadow ground cover; LOD/instancing validation pending |

Statusy: `candidate`, `approved`, `acquired`, `imported`, `validated`, `rejected`.

### Stage 3G — reproducible free-asset bootstrap

Lista Stage 3G jest utrzymywana w `scripts/assets/stage3g_polyhaven.json`. Skrypt `scripts/assets/download_stage3g_assets.py` korzysta z publicznego API Poly Haven, pobiera domyślnie warianty 2K/FBX do lokalnego, ignorowanego katalogu `ExternalAssets/Stage3G/PolyHaven/`, weryfikuje rozmiar/MD5 z metadanych API i zapisuje lokalny `download-index.json`.

Pobranie źródeł **nie oznacza akceptacji assetu do mapy**. Status `candidate` lub `approved` w ledgerze dotyczy doboru/licencji; status `validated` wymaga importu do UE, użycia w odpowiadającym mu sektorze, sprawdzenia LOD/Nanite/instancing i pomiaru kosztu na komputerze referencyjnym.

### Stage 3G — recovery checklist po audycie 26.09.2026

PR #155 udowodnił authoring/CI/proof harness, ale nie przesunął source assetów przez pełny lifecycle. Dlatego Stage 3G pozostaje otwarty do czasu wykonania co najmniej:

- [ ] `Sparse Grass` -> `validated` w valley/meadow;
- [ ] `Forest Ground 03` -> `validated` w forest;
- [ ] `Rocky Terrain` -> `validated` w high Alpine;
- [ ] co najmniej jeden z `Rock Face 01` / `Boulder 01` -> `validated` jako rzeczywisty rock dressing;
- [ ] wybrać i sprofilować realny conifer asset; `Fir Tree 01` może przejść do `approved` dopiero po pomiarze LOD/instancing;
- [ ] pierwszy `PCG_RouteExclusion` -> `validated`;
- [ ] minimum jeden produkcyjnie użyteczny graph scatterujący approved/validated assets -> `validated`;
- [ ] capture 1200/4900/8000 m pokazuje faktyczne assety i rozróżnialne biomy;
- [ ] 1080p sanity nie wykazuje nieakceptowalnej regresji na komputerze referencyjnym.

Dopiero wtedy minimalny environment asset baseline przechodzi z 3G do Stage 7 jako **punkt startowy do rozwijania**, a nie jako niewykonana zaległość.

## 9. Technical UE asset ledger

Technical assets zwykle nie mają osobnej ceny zakupu, ale mogą dziedziczyć ograniczenia/licencję swoich inputów. Każdy ma właściciela etapu, status, zależności i wymagany proof.

| Technical UE asset | Typ | Stage | Status | Źródła wejściowe / zależności | Wymagany proof |
|---|---|---|---|---|---|
| `PCG_Valley` | PCG Graph | 3G | planned | WorldSpec + route constraints + approved meadow/rock assets | deterministic regenerate + 1200 m screenshot + perf sanity |
| `PCG_Forest` | PCG Graph | 3G/7 | planned | WorldSpec + route exclusion + approved conifers/ground assets | deterministic regenerate + 4900 m screenshot + density/perf proof |
| `PCG_HighAlpine` | PCG Graph | 3G/7 | planned | WorldSpec + rocks/scree/cliff assets | deterministic regenerate + 8000 m screenshot |
| `PCG_RouteExclusion` | PCG helper/settings | 3G | planned | authoritative route spline | no generated instance violates route-clearance contract |
| `IK_Rider` | IK Rig | 6 | planned | production rider skeleton | retarget chain validation |
| `RTG_CyclingMocap` | IK Retargeter | 6 | planned | mocap source + rider IK rigs | representative cycling clip retarget proof |
| `CR_Cyclist` | Control Rig | 6 | planned | rider skeleton + bike contact goals | hand/foot contact + tuck/corner/standing proof |
| `NS_Rain` | Niagara System | 8 | planned | optional VFX textures/noise | visual + GPU proof |
| `NS_WheelSpray` | Niagara System | 8 | planned | wheel/surface/wetness state | camera-visible spray + GPU proof |
| `MS_Drivetrain` | MetaSound Source | 8 | planned | drivetrain source samples + cadence/power inputs | parameter continuity + audio sanity |
| `MS_Wind` | MetaSound Source | 8 | planned | wind source samples/noise + speed/wind inputs | direction/speed response proof |

Statusy technical assets: `planned`, `prototype`, `reviewed`, `validated`, `deprecated`, `removed`.

Technical asset przechodzi do `validated` dopiero po wymaganym build/proofie na komputerze referencyjnym.

## 10. Definition of done dla asset passu MVP

Asset pass MVP jest ukończony, gdy:

- dolina, las i high Alpine są wizualnie rozróżnialne, ale spójne;
- droga i pobocze nie wyglądają jak placeholder;
- rider i bike są wiarygodne w obu kamerach;
- kilka starannie przygotowanych miejsc nadaje światu „życie” bez pełnego traffic systemu;
- pogoda ma widoczny i słyszalny wpływ na świat;
- assety nie łamią celu 1080p/60 FPS na RTX 2070 Super;
- nie ma niewyjaśnionych problemów licencyjnych;
- repo nie zawiera przypadkowego dumpu całych paczek marketplace;
- końcowa lista użytych source assets jest zapisana w Source Asset Ledger;
- krytyczne PCG/rig/IK/Niagara/MetaSound assets są zapisane w Technical UE Asset Ledger i mają status `validated`;
- generated outputs można odtworzyć albo ich pochodzenie jest jawnie zapisane; nie ma ręcznie zmodyfikowanych „generated” assetów bez źródła prawdy.
