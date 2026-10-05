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

Assety mają wspierać aktualną trasę Sa Calobra zgodnie z wymaganiami produktu i roadmapą. Bieżące zadanie #363 obejmuje cały istniejący Landscape 2016,5 × 2016,5 m; nie rozszerza go na pełną trasę. MVP nie jest katalogiem rowerów, postaci ani regionów — priorytetem jest spójna wizualnie, wydajna i grywalna trasa.

W #363 dobór zaczyna się od [referencji i porównania kandydatów](experiments/sa-calobra-material-reference-review-2026-10-05.md). Obecny materiał jest odrzuconym prototypem. Historyczne wpisy Alpine oraz ich statusy importu i walidacji zachowują znaczenie dla dawnych dowodów; nie zatwierdzają przydatności do Sa Calobra ani aktualnej kolejności zakupów. Sześć wymaganych ról to odsłonięta skała, rumosz/żwir, suche podłoże mineralne, podłoże z rzadką suchą trawą, lokalne podłoże leśne oraz istniejące wykopy/nasypy. Nowe źródła przechodzą pełny cykl opisany poniżej; ten przegląd nie zatwierdza ani nie pozyskuje assetów.

### 1.1 Dwa typy assetów

Aktualne porównanie #363: [21 źródeł dla sześciu ról powierzchni](experiments/sa-calobra-surface-candidates-2026-10-05.md).
Lokalne kopie koloru zostały dopuszczone i pozyskane wyłącznie do przeglądu;
rekomendacja do prób nie oznacza zatwierdzenia zestawu produkcyjnego. Skala
`Rock024` pozostaje nieznana. Nie wykonano nowego importu Unreal.

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

Jeżeli akceptacja assetu lub technical UE assetu zależy od tego, **jak faktycznie wygląda scena**, wymagany jest również wpis w [`visual-history/`](visual-history/README.md). `validated` nie może wynikać wyłącznie z zielonego CI. Visual History zapisuje ostatni zaakceptowany `BEFORE`, bieżący `NOW`, finalny `AFTER`, dokładny SHA/PR/CI oraz osobne decyzje techniczną i wizualną.

### 1.3 Julka — inventory, transport i lokalny restore

Issue #345 wprowadza izolowane narzędzie `tools/julka/`. Julka zarządza
identyfikacją, transferem i integralnością danych; nie zastępuje generatora,
metodologii ani odbioru Unreal.

- `.uasset`, `.umap` i zatwierdzone rastry śledzone przez repozytorium pozostają
  w Git LFS. Julka potrafi wyliczyć dokładne obiekty dla wybranego commita,
  wykryć pointer-only i pobrać tylko assety w obsługiwanych klasach.
- 17 surowych plików CNIG Sa Calobra pozostaje identyfikowanych przez receipt
  z 3 października 2026 r. Ich istniejąca kopia transportowa jest Draft GitHub
  Release; manifest Julki sprawdza Release i receipt względem SHA-256 przed
  restore. Nazwa katalogowa CNIG i nazwa dostarczonego pliku są osobnymi
  polami, więc oryginały nie są przemianowywane.
- Ten snapshot zawiera 4 MDS, 9 LAZ i 4 ortofotomapy; **nie zawiera** 17
  osobnych kafli MDT50cm, z których przygotowano raster 8×8 km. Manifest
  `prepare_sa_calobra_mdt50cm.py` nadal jest authority dla nazw/rozmiarów/SHA
  tych wejść. Odczytane lokalnie ścieżki runnera i głównego checkoutu
  2026-10-03 nie miały osobnego katalogu z tym zestawem, dlatego `sa-calobra-8x8`
  pozostaje incomplete i wymaga jawnego CNIG acquisition/adopt. To nie oznacza,
  że pliki nie istnieją na żadnym innym komputerze lub nośniku.
- Lokalny asset root jest jawnie wybierany przez `YACS_ASSET_ROOT`. Default jest
  w profilu użytkownika, nie wewnątrz katalogów generowanych Unreal. Nie jest
  synchronizowany ani backupowany samoczynnie.
- Nie dodajemy DVC ani drugiego lokalnego content store w tej dostawie. DVC
  pozostaje kandydatem z osobnego Issue #340 i wymaga przyjęcia jego eksperymentu
  oraz ponownego przeglądu licencji. Dane bez dopuszczonej darmowej kopii remote
  pozostają na wybranym `YACS_ASSET_ROOT` lub muszą zostać ponownie pozyskane od
  oficjalnego dostawcy; nie oznacza to backupu na drugim urządzeniu.
- Cleanup w Julce jedynie raportuje rozmiar cache. Nie usuwa źródeł, LFS,
  outputów, evidence ani `DerivedDataCache`.

Pełna komenda, storage/proof boundaries i limitations: [`tooling/JULKA.md`](tooling/JULKA.md).

Checkpoint P1 z 4 października 2026 r.: Julka ma 45 dodatkowych lokalnych
identities w `p1_context.json`: BTN 30 PBF / 250 386 B / 21 warstw;
SIOSE capabilities + diagnostyczny GML / 1 434 573 B; Catastro capabilities +
12 odpowiedzi błędu / 19 782 B. BTN ma status `acquired` jako kontekst usługowy.
SIOSE 2014 jest `partial`: usługa deklaruje HR 2017, a 244 obiekty mają datę
obserwacji 2016; nie dopuszczamy ich jako 2014. Catastro jest `partial`:
`Area of extension out of limits`, 0 dopuszczonych GML. Profil P1 pozostaje
niekompletny mimo poprawnych hashy wszystkich plików. Raw cache jest poza Git,
bez zarejestrowanego backupu remote. Pełne evidence i restore/status są w
[raporcie P1](../worldgen/terrain/benchmarks/sa_calobra/world_data/P1_ACQUISITION_2026-10-04.md).

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
| **3G R4.1 — Alpine Visual Recovery** | reuse existing Poly Haven ground/vegetation/rock set; prioritize Rock Face 01, controlled grass/understory, optional isolated hero fir and mountain-mass source | continuous/tiled terrain presentation path, terrain material foundation, `PCG_Roadside`, slope/biome masks, optional scenic/view exclusion data, deterministic atmosphere preset | **required visual recovery before R5**; no broad marketplace purchase; real DEM/heightmap allowed only as a licensed bounded macro-terrain input after A/B proof |
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
- IK Rig + IK Retargeter dla jawnego source → rider pipeline;
- proceduralne pozycje: seated, aero, descending tuck, standing/sprint, cornering;
- Control Rig;
- FullBodyIK z czterema stabilnymi celami kontaktowymi: lewa/prawa dłoń na gripach i lewa/prawa stopa na pedałach;
- look-ahead / head stabilization jako warstwa additive/presentation;
- cadence-driven crank/pedals dostarczające transformy celu foot IK;
- physics-driven lean/corner pose konsumujące stan Stage 4 bez sprzężenia zwrotnego do fizyki.

**Game Animation Sample 5.8** jest wyłącznie reference project do wzorców retargetingu/Control Rig/Look-At/debugowania; nie jest source assetem YACS i nie importujemy całego frameworka locomotion.

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

Preferujemy model, w którym koła, korba i elementy wymagające animacji nie są zespawane w jeden mesh. Rower musi dać się przygotować z czterema stabilnymi punktami kontaktowymi/sockets dla dłoni i stóp oraz z jednoznaczną osią/pozycją korby i pedałów potrzebną do cadence-driven contact solve.

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

Najpierw używamy natywnych systemów UE (SkyAtmosphere, Volumetric Clouds, Niagara itd.). Nie kupujemy dużego weather frameworka przed udowodnieniem konkretnej luki. Dla MVP deszcz/spray są projektowane jako lokalne efekty wokół ridera/kamery i kół; globalny stan pogody nie oznacza globalnej symulacji cząstek na całej trasie.

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
- jawne `LeftHandGrip`, `RightHandGrip`, `LeftPedal`, `RightPedal` goal/socket definitions oraz pelvis/head goals tam, gdzie potrzebne;
- cadence/crank presentation data potrzebne do deterministycznego wyliczenia pozycji pedałów;
- rider presentation Data Asset, jeśli parametry proceduralnej pozy będą wymagały wersjonowanej konfiguracji.

Reference/sample projekty i spike'owe pluginy (np. Game Animation Sample, Gameplay Cameras/GameplayCameraToolset) **nie trafiają do Technical UE Asset Ledger**, dopóki nie staną się rzeczywistą, zatwierdzoną zależnością produkcyjną.

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
- wetness/material instances zależne od stanu pogody;
- jawne scalability/intensity data dla lokalnego rain/spray envelope, jeśli nie wystarczą parametry systemu Niagara.

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

### Performance gate for mass-repeated assets

For assets expected to appear many times in the rendered world (for example mass foliage, repeated rocks, later dense rider populations), static mesh complexity alone is not an acceptance criterion.

Use the lifecycle and evidence rules from [`performance/PERFORMANCE_FRAMEWORK.md`](performance/PERFORMANCE_FRAMEWORK.md):

```text
SOURCE_FOUND
  -> LICENSE_OK
  -> STATIC_AUDIT_OK
  -> LOD_PROFILED
  -> MICROBENCH_OK
  -> WORLD_ACCEPTED
```

The gate may consider LOD behavior, materials/sections, masked overdraw, shadows, instancing/component pressure and measured Frame/Game/Draw/RHI/GPU cost on the reference scenario. A low triangle count does not override a measured performance regression, and a high LOD0 count is not an automatic rejection when measured world cost remains acceptable.

## 8. Source asset ledger

Po wyborze konkretnych paczek tabela poniżej staje się rejestrem źródła prawdy.

| Asset / pack | Źródło | Licencja | Cena | Stage | Status | Uwagi |
|---|---|---|---:|---|---|---|
| Sparse Grass (`sparse_grass`) | Poly Haven | CC0 | 0 zł | 3G | imported | meadow/valley ground; merged-main 1200 m visual proof accepted in PR #192 / CI #421 and aggregate Stage 3G environment performance passed in PR #197 / run #13; per-asset LOD/instancing/cost proof remains before `validated` |
| Forest Ground 03 (`forrest_ground_03`) | Poly Haven | CC0 | 0 zł | 3G | imported | pine-needle forest floor; 4900 m visual proof and final three-biome Visual History are accepted; aggregate Stage 3G environment performance passed in PR #197 / run #13, but source-asset LOD/instancing validation remains before `validated` |
| Rocky Terrain (`rocky_terrain`) | Poly Haven | CC0 | 0 zł | 3G | imported | high-Alpine ground layer; merged-main 8000 m visual proof accepted in PR #192 / CI #421 and aggregate Stage 3G environment performance passed in PR #197 / run #13; per-asset LOD/cost proof remains before `validated` |
| Rock Face 01 (`rock_face_01`) | Poly Haven | CC0 | 0 zł | 3G/R4.1 | approved | **R4.1 highest next import/validation priority** for road cuts, cliff faces and high-Alpine meso terrain; slope/composition driven placement; performance validation pending |
| Boulder 01 (`boulder_01`) | Poly Haven | CC0 | 0 zł | 3G | imported | canonical `SM_Stage3G_Boulder` is used by accepted R3 valley/high-Alpine massing; merged-main visual proof and aggregate Stage 3G environment performance passed; explicit per-asset LOD/instancing proof remains before `validated` |
| Mountainside (`mountainside`) | Poly Haven | CC0 | 0 zł | 3G | candidate | mid-ground mountain mass; compare against cheaper authored geometry |
| Fir Tree 01 (`fir_tree_01`) | Poly Haven | CC0 | 0 zł | 3G | candidate | retained as a hero/sparse conifer candidate; broad-scatter reduction in PR #162 is blocked by whole-FBX A/B/C import memory pressure on the trusted runner, so it is not the R2 mass-forest mesh |
| Fir Sapling (`fir_sapling`) | Poly Haven | CC0 | 0 zł | 3G | candidate | lightweight young-tree / understory candidate; useful as forest variation, not the primary tall-canopy mesh |
| Fir Sapling Medium (`fir_sapling_medium`) | Poly Haven | CC0 | 0 zł | 3G | validated | R2 mass-scatter conifer; persisted as `SM_Stage3G_FirSaplingMedium`, used by `PCG_Forest` and reference-map forest layers; PR #162 / CI #398 / 4900 m visual proof accepted |
| Grass Medium 01 (`grass_medium_01`) | Poly Haven | CC0 | 0 zł | 3G/R4.1 | candidate | R4.1 foreground/roadside meadow clusters; controlled instancing, density and cull policy required; LOD/instancing validation pending |
| Sa Calobra MDT50cm terrain source | CNIG/IGN MDT50 cm — 3ª cobertura v1 | CNIG license compatible with CC BY 4.0 | 0 zł | Active M3 terrain source | acquired | 8 km × 8 km, 0,5 m, EPSG:25831; derived GeoTIFF tracked in Git LFS under `worldgen/terrain/benchmarks/sa_calobra/`; 17 verified source COG tiles remain outside Git; selected replacement for the retired Passo Giau map, with UE import and visual/performance acceptance still pending |

Statusy: `candidate`, `approved`, `acquired`, `imported`, `validated`, `rejected`.

### Stage 3G — reproducible free-asset bootstrap

Lista Stage 3G jest utrzymywana w `scripts/assets/stage3g_polyhaven.json`. Skrypt `scripts/assets/download_stage3g_assets.py` korzysta z publicznego API Poly Haven, pobiera domyślnie warianty 2K/FBX do lokalnego, ignorowanego katalogu `ExternalAssets/Stage3G/PolyHaven/`, weryfikuje rozmiar/MD5 z metadanych API i zapisuje lokalny `download-index.json`.

Pobranie źródeł **nie oznacza akceptacji assetu do mapy**. Status `candidate` lub `approved` w ledgerze dotyczy doboru/licencji; status `validated` wymaga importu do UE, użycia w odpowiadającym mu sektorze, sprawdzenia LOD/Nanite/instancing i pomiaru kosztu na komputerze referencyjnym.

### Stage 3G — recovery checklist po audycie 26.09.2026

PR #155 udowodnił authoring/CI/proof harness, ale nie przesunął source assetów przez pełny lifecycle. Dlatego Stage 3G pozostaje otwarty do czasu wykonania co najmniej:

- [x] `Sparse Grass` -> `imported`, 1200 m Visual History i aggregate environment performance zaliczone; [ ] -> `validated` po per-asset LOD/instancing/cost proof;
- [x] `Forest Ground 03` -> `imported`; [x] forest-ground proof + pełny 3-biome Visual History + aggregate environment performance zaakceptowane; [ ] source-asset LOD/instancing validation przed `validated`;
- [x] `Rocky Terrain` -> `imported`, 8000 m Visual History i aggregate environment performance zaliczone; [ ] -> `validated` po per-asset LOD/cost proof;
- [x] `Boulder 01` -> `imported`, używany w R3; visual acceptance i aggregate environment performance zaliczone; [ ] finalne `validated` po explicit per-asset LOD/instancing proof;
- [x] `Fir Sapling Medium` -> `validated` jako R2 mass-scatter conifer: PR #162 / CI #398 / 4900 m visual proof;
- [x] `PCG_RouteExclusion` -> `validated` po R2 deterministic reload + route-clearance + committed-SHA proof;
- [x] `PCG_Forest` -> `validated` jako pierwszy produkcyjnie użyteczny graph scatterujący zatwierdzony realny asset;
- [x] `PCG_Valley` + `PCG_HighAlpine` -> `validated`: persisted/reloaded w PR #192, 1200/8000 m Visual History + merged-main CI #421 oraz explicit 1080p/60 environment performance PR #197 / run #13 zaliczone;
- [x] capture 1200/4900/8000 m pokazuje faktyczne assety i rozróżnialne biomy jako zaakceptowany, trwały tryptyk `BEFORE | NOW | AFTER` z merged-main AFTER;
- [x] merged-main visual capture 1920x1080 + Fresh Load + Map Check 0/0 zaliczone; [x] osobny environment performance sanity 1920x1080 / 60 FPS na RTX 2070 Super zaliczony w PR #197 / run #13 (`STAGE3G_ENVIRONMENT_PERFORMANCE.md`).

Dopiero wtedy minimalny environment asset baseline przechodzi z 3G do Stage 7 jako **punkt startowy do rozwijania**, a nie jako niewykonana zaległość.

## 9. Technical UE asset ledger

Technical assets zwykle nie mają osobnej ceny zakupu, ale mogą dziedziczyć ograniczenia/licencję swoich inputów. Każdy ma właściciela etapu, status, zależności i wymagany proof.

| Technical UE asset | Typ | Stage | Status | Źródła wejściowe / zależności | Wymagany proof |
|---|---|---|---|---|---|
| `PCG_Valley` | PCG Graph | 3G | validated | WorldSpec + `FRouteGeometryProfile` + route exclusion + Boulder 01 | PR #192: persisted/reloaded + 1200 m Visual History + merged-main CI #421; PR #197 / run #13: 1920x1080 60 FPS gate PASS (frame p95 9.032 ms, GPU p95 8.063 ms) |
| `PCG_Forest` | PCG Graph | 3G/7 | validated | WorldSpec + validated route exclusion + Fir Sapling Medium / forest-ground assets | PR #162 / CI #398: deterministic reload, route exclusion, real Static Mesh Spawner, 4900 m visual proof, full Stage 3G validation |
| `PCG_HighAlpine` | PCG Graph | 3G/7 | validated | WorldSpec + `FRouteGeometryProfile` + route exclusion + Boulder 01 / high-Alpine materials | PR #192: persisted/reloaded + 8000 m Visual History + merged-main CI #421; PR #197 / run #13: 1920x1080 60 FPS gate PASS (frame p95 9.476 ms, GPU p95 7.281 ms) |
| `PCG_RouteExclusion` | PCG helper/settings | 3G | validated | authoritative `FRouteGeometryProfile` + tested Stage 3G route-clearance contract | PR #162 / CI #398 deterministic reload + protected 4 m route corridor + full Stage 3G proof |
| `IK_Rider` | IK Rig | 6 | planned | production rider skeleton | retarget chain validation |
| `RTG_CyclingMocap` | IK Retargeter | 6 | planned | mocap source + rider IK rigs | representative cycling clip retarget proof |
| `CR_Cyclist` | Control Rig | 6 | planned | rider skeleton + four bike contact goals + physics presentation inputs | four-point contact + cadence transition + tuck/corner/standing + head look-ahead proof |
| `NS_Rain` | Niagara System | 8 | planned | optional VFX textures/noise + weather intensity | localized rider/camera envelope + visual + GPU proof |
| `NS_WheelSpray` | Niagara System | 8 | planned | wheel/surface/wetness state | camera-visible spray + GPU proof |
| `MS_Drivetrain` | MetaSound Source | 8 | planned | drivetrain source samples + cadence/power inputs | parameter continuity + audio sanity |
| `MS_Wind` | MetaSound Source | 8 | planned | wind source samples/noise + speed/wind inputs | direction/speed response proof |

Statusy technical assets: `planned`, `prototype`, `reviewed`, `validated`, `deprecated`, `removed`.

Tabela opisuje stan zaakceptowany dla bieżącej linii dokumentacji/main. R2 / PR #162 daje `validated` dla `PCG_RouteExclusion` i `PCG_Forest`; R3 / PR #192 + Visual History / CI #421 oraz formalny 1080p/60 proof PR #197 / run #13 dają `validated` dla `PCG_Valley` i `PCG_HighAlpine`. Source Asset Ledger pozostaje bardziej konserwatywny: aggregate environment PASS nie zastępuje osobnych wymagań LOD/Nanite/instancing dla konkretnego source assetu.

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
- generated outputs można odtworzyć albo ich pochodzenie jest jawnie zapisane; nie ma ręcznie zmodyfikowanych „generated” assetów bez źródła prawdy;
- większe zmiany wizualne mają wpis w `docs/visual-history/` z baseline `BEFORE`, bieżącym `NOW`, zaakceptowanym `AFTER`, commit/PR/CI provenance oraz osobną decyzją techniczną i wizualną.

## P1 alternative source checkpoint — 2026-10-04

Alternatywne ścieżki zatwierdzone przez właściciela dostarczyły Catastro ATOM
Escorca (ZIP 127 448 B, 224 budynki / 595 części / 24 inne konstrukcje) oraz
regionalne SIOSE 2014 (15/15 obiektów AOI, EPSG:25831). Julka rejestruje 8
dodatkowych identities, profil `sa-calobra-p1-inputs` przechodzi 38/38 hashy.
Wcześniejsze błędy WFS pozostają jako historyczne evidence. Dane raw nadal poza
Git, restore lokalny; brak remote backupu. To acquisition, nie normalized masks
ani dowód kompletnego pokrycia AOI granicą gminy. [Pełny raport](../worldgen/terrain/benchmarks/sa_calobra/world_data/P1_ALTERNATIVES_2026-10-04.md).

## Normalized GIS candidate checkpoint — 2026-10-04

Working-space AOI ma 9 znormalizowanych produktów na natywnej siatce 0,5 m:
elevation/slope/aspect/local relief, mapped Catastro footprint, historyczny index
SIOSE i trzy przycięte zbiory geometrii. Dwa niezależne katalogi wyników dają te
same manifesty i 9/9 byte/logical hashes. Oficjalna geometria IDEIB potwierdza
pokrycie AOI przez Escorca; nie dowodzi aktualności wszystkich budynków.
Julka: profil candidate 56/56 hashów PASS; pełny World Authority nadal FAIL dla
brakujących warstw. Status `candidate`, bez integracji UE i bez human visual
acceptance. Duże lokalne różnice wysokości DTM pozostają do przeglądu.
[Raport i provenance](../worldgen/terrain/benchmarks/sa_calobra/world_data/NORMALIZED_CONTEXT_2026-10-04.md).

## Frozen geometry and environment fidelity — 2026-10-04

Decyzja właściciela dla Issue #335: istniejący teren i drogi są zamrożone.
Maski dopasowujemy do obecnego Landscape i kontraktu współrzędnych drogi;
nie zmieniamy wysokości, geometrii ani earthworks i nie importujemy nowej heightmapy.
Droga, położenie/obrysy budynków i Landscape zachowują zgodność 1:1 w granicach
wiarygodności dopuszczonych źródeł. Nieznane lub sprzeczne dane pozostają jawne.
Otoczenie ma możliwie wiernie oddawać klimat miejsca: domeny roślinności/skał,
gęstość, charakter koron i ważne widoki. Nie wymagamy kopii pozycji każdego drzewa
ani przesuwania go o 50 cm. Swoboda dekoracyjna respektuje budynki, domeny świata
i wykluczenia/bezpieczeństwo drogi. Podgląd kolorowych masek służy przeglądowi
rozbieżności; poprawiamy przetwarzanie i wyrównanie masek, nie zamrożoną geometrię.
Kontrakt normatywny: [World Building Bible, sekcja 5.3](WORLD_BUILDING_BIBLE.md#53-world-data-stack--spatial-evidence-before-presentation).

## Frozen Landscape mask review candidate — 2026-10-04

Trzy obrazy kontekstu/podglądu, raster klas diagnostycznych i manifest mają
osobne identities Julki (`sa-calobra-mask-review-candidate`, 61 plików z closure).
Podgląd w UE używa istniejącej mapy i materiałów tylko w sesji; nie zapisuje
assetów/mapy ani nie zmienia geometrii. Amber = relief do przeglądu, cyan =
mapped Catastro candidate, gray = unknown. Kolory SIOSE oznaczają historyczne
obiekty, nie aktualny biome. Pozostałe maski 2A nadal wymagają dopuszczenia.

## Placement evidence handoff candidate — 2026-10-04

Osobna maska wykluczenia budynków zachowuje footprint z Catastro bez arbitralnego
bufora. Raster stanu sadzenia blokuje mapped footprint (0), a pozostały obszar
pozostawia nierozstrzygnięty (255). Nie emituje zgody na sadzenie (1), ponieważ
brakuje dopuszczonych masek roślinności, drogi/bezpieczeństwa i pozostałych domen.
Żółty relief pozostaje wyłącznie do przeglądu; nie staje się klasą skał ani
automatycznym zakazem sadzenia. Dwa rastry i manifest są poza Git, w cache
`placement-handoff-v1-2026-10-04`, z identities, hashami i restore w Julce.
Przygotowanie kończy się świadomym `BLOCKED_FOR_PLANTING` (exit 2).

## Native LiDAR evidence candidate — 2026-10-04

Po zgodzie właściciela dekoder laspy 2.7.0 + lazrs 0.8.2 działa w odizolowanym
środowisku authoringowym. Istniejące 9 LAZ odczytano w całości (81 990 059
punktów), bez ponownego pobierania lub modyfikacji. Dopuszczone próbki w AOI:
23 588 890. Wszystkie nagłówki: LAS 1.4 / format 8 / EPSG:25831.

Dziewięć produktów (8 rastrów + PNG kontekstu) i manifest pozostają w cache
`lidar-masks-v1b-2026-10-04`. Zawierają klasy/counts/occupancy, próbki first return,
kandydata wysokości roślinności, fraction native/5m i review flags. Luki (2 713 728
cells) i ujemna/invalid normalizacja (341 399 cells) pozostają jawne. To kandydaci
pomiarów, nie gatunki, footprint nowych budynków ani zgoda na sadzenie. DTM i
zamrożona geometria pozostają read-only. Licencje narzędzi i notices:
[dependency provenance](legal/DEPENDENCY_PROVENANCE.md#sa-calobra-local-laz-decoder--2026-10-04).

Podgląd LiDAR korzysta z osobnych przygotowanych obrazów; nowe niebo/słońce w UE
jest tylko w sesji podglądu i nie zapisuje się w istniejącej mapie. Wykluczenia
drogi/BOB i dopuszczenie do produkcyjnego PCGEx pozostają osobnymi wymaganiami.

Właściciel zaakceptował wizualnie zieloną roślinność i dopuścił krzaki jako
interpretację różowych obszarów. Osobny kandydat `vegetation-domains-v1a-2026-10-04`
zachowuje trzy nakładające się domeny klas LiDAR: niską, średnią i wysoką.
Różowy nadal oznacza niepewną normalizację wysokości; nie zmieniamy go w
automatycznie potwierdzone krzaki. 328 201 z 341 399 takich cells zawiera niską
lub średnią roślinność bez wysokiej, a 13 198 także wysoką. Dwa rastry i manifest
są poza Git, z osobnym receipt, identities i restore w Julce. Brak próbek
pozostaje unknown, a budynki i relief mają osobne review flags. Nie zmieniono
terenu, drogi, istniejących masek wysokości ani materiału aktualnego podglądu.

## Maski do bounded PCGEx — 2026-10-04

Pakiet `pcg-masks-v1-2026-10-04` jest gotowy do odczytu masek z jawnymi fallbackami,
bez przebudowy terenu lub drogi. Selektory niskiej/średniej/wysokiej roślinności
uwzględniają asfalt, zachowawcze pobocze 0,51m, budynki, obszary BOB oraz wodę
i infrastrukturę. Woda: BTN plus 106 odcinków oficjalnej tymczasowej sieci GOIB;
5m wokół linii/punktów to robocze odsunięcie dekoracji, nie szerokość koryta.
Dane historyczne i brak próbek pozostają jawne. Nie tworzymy gatunków ani
dokładnych koron drzew ze zdjęcia. Wysokości unknown pozostają unknown.

Po zgodzie właściciela zatrzymano 375 zamrożonych wyników c5573b3 / draft #338
plus recipe, bez przyjmowania kodu tej gałęzi i bez uruchamiania buildera.
17 oryginalnych ciężkich źródeł CNIG nie pobrano ponownie ani nie zmodyfikowano.
Nowa hydrologia: 7 plików z receipt, 171 059 B, kompletna odpowiedź AOI, jedna
warstwa polyline. Road masks: 6 plików / 33 594 104 B; context: 4 / 198 439 B;
pakiet PCG: 5 / 20 245 980 B. Liczby obejmują manifesty. Wszystkie payloady są
w zewnętrznym world-data cache; w Git wyłącznie skrypty, metadata i receipts.

Kontrakt promienia obiektu, clearance, UV/grid, unknown i fallbacków opisuje
[World Building Bible](WORLD_BUILDING_BIBLE.md#bounded-pcgex-mask-package-with-explicit-fallbacks-issue-335).
Julka ma osobne identities/restore/profile. Nie deklarujemy wykonanego grafu
PCGEx, pełnego zamknięcia 2A lub performance PASS. Nowe odsunięcia mają podgląd
do przeglądu; fiolet oznacza obszar BOB, a nie wcześniejszy różowy review wysokości.

## Przejścia masek i podgląd koryt — 2026-10-04

Kandydat `mask-transitions-v1a-2026-10-04` dodaje miękkie przejście BOB na
zewnątrz istniejącego wykluczenia oraz wagi gęstości roślinności. Hard masks
pozostają wiążące. Niebieski jest pasem odsunięcia, ochra linią źródłową cieku,
pomarańczowy oznacza większe luki do sprawdzenia. Dziewięć połączeń poniżej 1cm
ma znaczenie wyłącznie dla podglądu topologii; 43 większych kandydatów nie połączono.
Próba punktów 200x200m: 60 niskich, 0 średnich i 0 wysokich; to przykładowe
promienie, bez instancji assetów i bez wykonania grafu PCGEx. Próba 3D wymaga
przypisanego zestawu assetów i osobnego dowodu konsumenta. Publiczne materiały
Embark wspierają szybkie iteracje z kontrolą artysty, nie narzucają nam wartości
buforów ani obowiązku instalacji Houdini. Źródła i granice wnioskowania zapisano
w [production references](PRODUCTION_WORLD_ARCHITECTURE_REFERENCES.md#embark-research-follow-up-masks-and-dressing--2026-10-04).
