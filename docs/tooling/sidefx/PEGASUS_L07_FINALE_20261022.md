# YACS M3 / #365: PEGASUS Lesson07 — plan domknięcia materiałów i renderu

**Data:** 2026-10-22. **Repo:** karnalooch/YetAnotherCyclingSim. **Gałąź:** codex/365-world-graph. **PR #474:** Draft. **Stan:** PLAN GOTOWY; CAŁA LEKCJA NADAL NIEZAKOŃCZONA.

## Kontrakt zadania

Cel nie brzmi „wykonać ładny shader”. Celem jest **pełen, natywnie przeliczony, wiarygodny 8×8 km Landscape Sa Calobra z materiałami i kolorami opartymi na Pegasus**, poprawnie odczytany w Unreal i potwierdzony rzeczywistymi kadrami Lit. Zachować workflow 03→04→05→06→07 SideFX; osobny projekt Material Forge/Blender/PCGEx nie może zastępować Houdiniego.

W dniu 22.10.2026 użytkownik **zezwolił wybrać zamienniki ośmiu rodzin Poly Haven CC0** zamiast szukać niepewnych oryginalnych skanów Quixel. Zmieniło to wymaganie *identyczności assetów*, a nie obowiązek odwzorowania topologii grafu i potwierdzonych parametrów Pegasusa. Nie opisywać końcowego wyniku jako dosłownych oryginalnych skanów / identycznych pikseli.

**Źródła nadrzędne:** [SideFX Landscape Workflow](https://www.sidefx.com/tutorials/project-pegasus-landscape-workflow/), [Landscape Material](https://www.sidefx.com/tutorials/project-pegasus-landscape-material/), oryginalne materiały, archiwum ProjectFiles_LandscapeWorkflow3, [katalog lekcji PEG-02](catalog/PEG-02.md), [69 klatek i parametry źródłowe](../../assets/lesson07-sidefx-source-20261021/houdini-author-graph-followup-20261022.json), [pięć oryginalnych HDA instances](../../assets/lesson07-sidefx-source-20261021/houdini-author-material-observations-20261022.json).

**Terminologia dowodowa:** `SOURCE_VERIFIED` oznacza bezpośrednią klatkę wideo/HDA, `NATIVE_VERIFIED` natywny pozytywny wynik bieżącego kodu, `YACS_ADAPTATION` jawne odejście dla geografii lub wybranych CC0, `INFERRED` odczyty z różnych momentów filmu, `UNKNOWN` niezweryfikowany parametr. Nigdy nie zamieniać `UNKNOWN` w domyślną liczbę bez odrębnej decyzji i świadomego oznaczenia `YACS_ADAPTATION`.

## A. Chronione źródła i zastany stan

| Element | Identifikator/status | Zakres |
|---|---|---|
| Sa Calobra | 16 000 × 16 000, 0,5 m, 8×8 km | 256 mln próbek, 4 istniejące aktywa UE Landscape, zachować world transform / orientację / alfabetyczny podział |
| L06 base | SHA256 `08586f0e1aa6aa033cf7364a929d2c260c87c41d6dc11445c981e10ec6ba2952` | Wysokość i Alpha; bez zmian |
| L06 masks | SHA256 `203d46ea79a0a697d46256f631271135a0cd8766ba8768f7432ea315512c16a8` | grass_mask, sand_mask, cliff_mask, ramp_layer; bez zmian |
| Historical L06 Stage3 scree | SHA256 `2af8ce5b467db28613c2033677c444dba5a89af943b906b01258a0b44106edb7` | 96 479 665 B. Rozmiar i hash zgadzają się z producentem; pełna linia pochodzenia niepotwierdzona (Stage4C 4,3 GB bez producer JSON) |
| SideFX material HDA | SHA256 `e7d41ca64757699aa65b69520aca96b11f7325365506ddc675f8ea2b23a45023` | Oryginalne PE_heightfield_material::1.0; nie zmieniać definicji |
| SideFX tint HDA | SHA256 `93cc47dd511bc3d5868835b5dd3b9082c13cab23355b688aaf2a947e8687a2ed` | Oryginalne PE_heightfield_tint::1.0; nie zmieniać definicji |
| Poly Haven CC0 | [run 39774587988](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39774587988), [39776164539](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39776164539) | 8 rodzin i 45 map PBR (917 734 092 B), MD5/SHA256 i OIIO headery 4K/2K PASS |
| SideFX pięć HDA na terenie | [run 39789846215](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39789846215) | PASS na 256² realnych próbkach **z piargiem cliff-mask proxy**; nie jest to cały świat ani w pełni autorski graf tintów |
| Wycinek Stage3 scree | [run 39794174742](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39794174742) | 8619 niezerowych realnych scree voxeli vs 51727 w błędnym proxy; tylko diagnostyczny origin |
| 5 HDA z prawdziwym Stage3 | [run 39795208757](https://github.com/karnalooch/YetAnotherCyclingSim/actions/runs/39795208757) | Brak potwierdzonego PASSED material evidence; wcześniejsza kolejka/startup_failure |
| Pełne UE arrays/Lit/world | NIEPOTWIERDZONE | Do ukończenia, żaden „source installed” nie jest PASS wizualnym |

Kanoniczny projekt `D:/yacs/project/YetAnotherCyclingSim.uproject`, mapa `L_SaCalobra_Lesson07`, źródła mask/terrain w `D:/yacs/work/lesson06-unified-20261019`, PBR `D:/yacs/work/lesson07-polyhaven-cc0-v1` i próbki realnego 16K pod `D:/yacs/work/lesson07-cc0-real-crops`. Każdy nowy test musi mieć **osobny katalog na D:** i nowy token run/attempt. Zakaz nadpisania accepted BGEO/UASSET, zakaz uruchamiania drugiej instancji UE, zakaz wyłączania LOCAL_BUSY oraz guardów `all --force`. Jeden native writer na raz. PR pozostaje Draft, `LESSON07_TECHNICAL_PASS=false` i `performance_pass=false` aż do wiarygodnego ukończenia.

## B. Dokładny graf PEG-02-03/04/05 do odbudowania w Houdinim

```text
[Accepted Source/Manual/Procedural height + Alpha + mask]
  -> [rocky PE_heightfield_material: dark_rock]     mask rocky
  -> [grass PE_heightfield_material: sparse_grass]  grass mask enabled, Curl
  -> [grass gradient PE_heightfield_tint1]          mask6 -> mask7 -> mask8
  -> [grass brightness PE_heightfield_tint2]        SOLID (2,2,2), UNMASKED
  -> [sand PE_heightfield_material4: dense_sand]    sand mask
  -> [cliff PE_heightfield_material5: dark_rock_02] cliff mask
  -> [cliff PE_heightfield_tint3]                   (.597,.597,.597) with mask
  -> [scree PE_heightfield_material6: gray_rocks]  TRUE scree mask, no cliff proxy
  -> [scree PE_heightfield_tint4]                   (.874,.822347,.701822)
  -> [exposure PE_heightfield_tint5]                branch tint4 -> visualize4 -> mask12
  -> [curvature PE_heightfield_tint6]               mask12 -> mask13
  -> [registered RGB, Roughness, Alpha, five classes, IDMap]
```

Kluczowe edges źródłowe: `material5 -> tint3 -> material6 -> tint4`; `heightfield_remap1` jako maskowe wejście do `material6` i `tint4`; `tint4 -> tint5 input 1`; na **odnodze**, nie na głównym przewodzie: `tint4 -> heightfield_visualize4 (Default Tinting; No Change) -> mask12 -> tint5 input 2`; `mask12 -> mask13 -> tint6 input 2` i `tint5 -> tint6 input 1`. Nie budować nowego wymyślonego grafu, odtwarzać nazwy węzłów/piny zgodnie z udokumentowanym Lesson05.

### B1. Pięć material HDA z lekcji (parametry z filmu, nie automatyczna zgoda na deformację Sa Calobra)

| Materiał, oryg. Quixel | CC0 wybrany | Filmowy Size / Height Scale | Mask | Distort |
|---|---|---|---|---|
| Rocky base `tjmledzr` | `dark_rock` | 1000 / +10 | mask rocky | OFF |
| Grass `ulgmbhwn` | `sparse_grass` | 100 / 0 | **ON**, grass_mask | Curl ON: Amplitude 100, Element Size 100, Element Scale (1,1,1), Offset 0 |
| Sand `td1hcimn` | `dense_sand` | 500 / +10 | sand_mask | OFF |
| Cliff `tdwlcc1l` | `dark_rock_02` | 100 / −10 | cliff_mask | OFF |
| Scree `vjdqcba` | `gray_rocks` | 100 / +1 | prawdziwy scree_mask | OFF |

Źródłowe wysokości +10/−10/+1 to **ustawienia przykładu**, nie pozwolenie na przebudowę przyjętych 16K wysokości i dróg. Bounded canary z `heightscale=0` jest **YACS_ADAPTATION**, a nie „100% Pegasus”. Mikrodetal ma być reprodukowany bez modyfikacji chronionego heightfield, ewentualnie na warstwie shader/displacement pod osobnym testem. W materiale autora Roughness wskazywało literalnie `default.pic`, ale oryginalne HDA sprawdza istnienie pliku; wynik ścieżki/CWD u autora i wartość numeric Roughness są **UNKNOWN**. Użycie prawdziwej Roughness z CC0 jest świadomym wyborem adaptacyjnym.

### B2. Wierne wartości masek i tintów z klatek autora

| Węzeł | VERIFIED z filmów | Brakujące / ostrożność |
|---|---|---|
| Rocky slope/height mask2 | Slope 0–90; Height Min 14.8582, Max 424.469 | Upper Height Ramp knot i bindingi UNKNOWN. Wg wideo górna rampa osiąga plateau przed prawą krawędzią |
| Grass height mask6 | Height 14.8582–426.961, Slope OFF, Smooth1/Replace/Invert OFF | Exact ramp tuples UNKNOWN |
| Grass slope mask7 | 0–90°, Smooth1, Combine **Add**, Invert OFF | Rampa rosnąca, exact native tuples UNKNOWN |
| Grass occlusion mask8 | Combine **Subtract**, Invert Mask **OFF**, Occlusion ON, View Distance 15, Step Scale 1, Searches 16 | Sama rampa jest odwrócona: punkt1 (0.656198,1), punkt2 (1,0), Linear. Nie włączać checkboxu Invert |
| Grass tint1 | Gradient; Mask puste, Ramp Layer `mask`, Strength .95 | P1 (0,RGB .34/.55/.12705), P2 (.996694,RGB 1/.822741/.538), Linear. P1/P2 widoczne w różnych chwilach, wspólny finał **INFERRED** |
| Grass tint2 | Solid RGB (2,2,2), Strength1, Mask puste | Bezpośrednio po gradientzie trawy, **PRZED sand**, nie globalne gamma po wszystkim |
| Cliff tint3 | Solid (.597,.597,.597), Strength1, Mask `mask` | Źródłowe połączenie przed materiałem piargu potwierdzone w późniejszych klatkach Lesson05 |
| Scree tint4 | Solid (.874,.822347,.701822), Strength1, Mask `mask` | Musi używać prawdziwego scree, nie maski klifu |
| Exposure mask12 | Occlusion ON, Replace, Invert OFF, ViewDistance **145**, StepScale1, Searches16, Smooth1 | Ramp right point (1,1) Linear; final left endpoint numeric UNKNOWN, mimo wcześniejszego stanu (0,0) |
| Exposure tint5 | Gradient, Mask puste, Strength1, Ramp Layer `mask` | P2 (.93538, RGB .651/.651/.651) Linear; lewy biały punkt widziany wcześniej; finalny prawy biały punkt UNKNOWN |
| Curvature mask13 | Input z mask12, Curvature ON, Max Curvature **.18**, Occlusion OFF, Replace/Invert OFF, Smooth1 | Finalna rampa rosnąca, exact tuples UNKNOWN |
| Curvature tint6 | Gradient, Mask puste, Strength **.613**, Ramp Layer `mask` | P2 (1,RGB 2/2/2) Linear; P1 intended brightness1 z narracji, exact numeric tuple UNKNOWN |

**Niezbędne rozróżnienie HDA:** pole UI `Mask` oryginalnego tint HDA to parametr `ramp_mask`, a `Ramp Layer` to `srcname1`. Podmiana tych pól daje zły wynik, mimo poprawnych nazw węzłów. Nie przypisywać wartości kliku z filmu do błędnego parametru.

## C. Plan 10 pakietów wykonawczych (bez testowania usera ręcznie)

### F0 — Freeze, inwentaryzacja i bezpieczeństwo [P0, przed wszystkim]
**Wejścia:** bieżący exact HEAD PR #474, HDA hashes, accepted Stage1/Stage2, mask Stage3, 45 CC0 PBR. **Wykonawca:** integrator read-only.  
**Operacje:** (1) odczyt bieżącego GitHub workflow i source SHA, (2) read-only map/MI/array/actor inventory, active Unreal PID/owner SID i Wingman discovery, (3) wolny fizyczny RAM/commit/VRAM/dysk D, (4) hash accepted base/masks i LFS, (5) odczyt script/recipe namespace bez side effects.  
**Wyjście:** `F0-receipt.json`, zawiera source SHA, 4 Landscape snapshot, tekstury, asset hash, memory, branch, ograniczenia. **PASS** tylko jeśli zerowa niespodziewana mutacja i singleton editor. **FAIL:** rozbieżny źródłowy SHA, próba resetu cache, drugi UE, nierespektowany LOCAL_BUSY.

### F1 — Realne scree i nadmorski piasek [P0]
**Problem:** scree 8619 nonzero real cells (13.15% wycinka) kontra 51727 proxy cells; na tym samym wycinku sand_mask=0.  
**Operacje:** (1) pobrać finalny status runu `39795208757` i dalsze real Stage3 diagnostics; nie zgłaszać PASS jeśli workflow miał startup_failure; (2) zrefingerprintfowac Stage4C 4.3GB **strumieniowo**, jeśli bezpieczne i może być źródłem Stage3, lub odtworzyć Stage3 tylko w izolowanym scratch; oznaczyć niepewne lineage, nie akceptować wyłącznie producer-self-hash; (3) drugie miejsce o sand_mask>0 znalezione z rzeczywistego Stage2, plus dark steep cliff site; (4) dla trzech sites wyeksportować HEIGHT/Alpha/Mask/ID as NPZ/BGEO z exact world coords i obligatoryjnymi hashami.  
**Wyjście:** 3 niezależne site-metadata z georeferencją + 3 proof boards. **PASS:** sand>0, scree>0 i cliff>0 we właściwych miejscach; rzeczywisty scree zamiast proxy i pełne protected height/masks checksum. **FAIL:** zerowy piasek uznany za test, pomylenie screw i cliff, nieznany Stage3 lineage „zaakceptowany”.

### F2 — Jeden nowy, wersjonowany source graph Houdiniego [P0]
**Wejście:** B1/B2 i oryginalne dwa HDA, CC0 manifest + real clips.  
**Operacje:** (1) zbudować w nowym adapterze dokładne native `PE_heightfield_material::1.0` i `PE_heightfield_tint::1.0` w kolejności B, (2) podłączyć prawdziwe mask branch i source CC0 4K; wymagane oryginalne HDA path/checksum, (3) rozróżnić verified/inferred/unknown per parm i per input port, (4) grassa użyć z Curl Amp100/ElementSize100, mask ON; nie „Simplex3.5/15” starego YACS, (5) puste Mask i Ramp Layer przekładać na literalne właściwe HDA parms, (6) nie zgadywać collapsed ramp knots.  
**Planowane nowe pliki:** `scripts/houdini/l07_pegasus_tint_network.py`, `worldgen/houdini/sa_calobra/recipes/l07-tints-v1.json` (to nazwy docelowe, nie obiecane istniejące pliki).  
**Weryfikacja:** mask/value snapshots per node, original HDA SHA, cook errors/warnings, RGB histogram, bgEO reopen, Source Stage1/Stage2 hex bytes unchanged. Dopuszczalny **tylko scratch** limited floating roundoff <=0.1mm i <=5% cells z przywróceniem dokładnych oryginalnych height bytes; większe odchylenie = STOP.  
**PASS:** prawdziwy graf SideFX i oddzielne trzy site proofs. **FAIL:** silent substitute, jakiekolwiek naruszenie source geometry/Alpha/Stage2, tints nie w źródłowej kolejności.

### F3 — Kalibracja kolorów (użytkownik: ciemnoszare wapienie, nie błyszczące) [P0]
**Zachowany baseline z prawdziwego 5-HDA proof (średni 8-bit RGB, NIE screenshot UE):** rock ~33.5/28.7/24; grass ~47.1/38.4/23.2; cliff ~60.1/51.5/38; historyczne scree **proxy** ~105.6/96.5/79.5 (nieważny dla prawdziwego scree).  
**Operacje:** najpierw true masks + source verified tints, potem jedna oznaczona `YACS_ADAPTATION` zmiana na próbę. Normal/roughness i color osobno. Zmierzyć clipping, dark-region fraction na ważnych Alpha cells, RGB hue neutralność w cliff, wzory vertical streak, histogram UE Lit i Houdini RGB niezależnie. Nie podnosić global brightness do „zakrycia” czarnych danych.  
**PASS:** brak nowych black valid cells, brak ostrych smug pionowych, realistyczne matowe ciemnoszare klify bez sepii, czytelne skały i rzadki piarg, na wszystkich realnych sites; A/B ta sama kamera i ekspozycja. **FAIL:** czarny albedo w ważnych komórkach, wyraźny brązowy cast, połysk plastiku, clipowane highlights. Liczbowe progi szarości są do ustalenia z pomiarów, **nie** parametrami Pegasusa.

### F4 — Całe 16K Houdini (nie wycinek, który „udaje” mapę) [P0]
**Przed:** F1–F3 udowodnione na real sites. **Operacje:** (1) nowy versioned output prefix w `D:/yacs/work`, nigdy nie run `lesson06_unified_pipeline.py --stage all --force` na accepted original; (2) pełna siatka 16000², proponowane core-chunks 1024² *z halo wyliczonym* z zasięgu największej operacji, globalne world-space UV i stable seed, nie lokalne tile UV; (3) dwa sąsiednie chunki i centralny 4-Landscape seam jako admission; (4) jeden fresh hython per chunk, przed nim guard fizyczny RAM i available commit; wykluczyć równoległe duże procesy i nie kasować aktywnego UE; (5) po każdym chunk: input SHA→cooked→fresh reopen→height/Alpha/masks/ID byte equality→output SHA; (6) assembler obejmuje 100% 8 km i wszystkie cztery aktualne aktory.  
**Uzasadnienie pamięci:** jedna 16000² float32 warstwa = ok. 0.954 GiB **bez** overhead i kopii HDA; wiele volume layers to potencjalne OOM przy 32 GB host RAM. Kandydacki chunk 1024 nie jest liczbą z filmu.  
**PASS:** cała mapa bez dziur/no-data, wszystkie chunki, zero height/Alpha mismatch, pełne seam guards (dla color tolerancja uzasadniona 1 LSB albo mocniejsza), deterministyczny repeat. **FAIL:** 4k/8k demo zamiast pełnego real domain, zniszczone source BGEO, brak 100% pokrycia lub seams.

### F5 — IDMap i eksport RGB/AO/masek [P0]
**Klucz autora:** pod oficjalnym kursem George Hulm wskazał: liczba IDMap Layers musi = liczbie zakodowanych warstw; `Bit` należy do Blend, `Texture Atlas Index` do Layer; pokazany master domyślnie zakłada demo 2017 vertices / Terrain Resolution=2016 i wymaga kompensacji dla innych rozdzielczości.  
**Operacje:** real F4 output → pięć klas w oryginalnych `PE_heightfield_layers_to_ID` / decoder, test class 0/bit i IDvalue, eksport 16k color/ID/Alpha. Nigdy nie kopiować Scottish ZIP debug Colour/AO na Majorkę. Na aktualnym UE test grayscale/linear/lossless/nearest ID sample na krawędziach z pionowymi maskami; nie akceptować bleeding. **Nie włączać UV Rotate=-90 z demo** bez testu real world IDMap/Colour mapping (UV Rotate zasila także odczyty IDMap).  
**PASS:** 5 klas, wszystkie ważne komórki zachowane, brak zgubionego indeksu 0, ID i RGB na tej samej rejestracji/co najmniej 4 tyles seamless. **FAIL:** nierówna liczba bit/layer, brak wierności IDMap, jakikolwiek rotate/offset mismatch.

### F6 — PBR UE: 5 rodzin × 3 tablice 2048² [P0]
**Stała kolejność po zatwierdzeniu CC0:** 0 `mossy_rock`, 1 `sparse_grass`, 2 `gravel_floor_02`, 3 `dark_rock_02`, 4 `coast_sand_rocks_02`. Każda ma 2K Diffuse, Roughness, DX Normal, AO, Displacement (25 verified source maps).
**Operacje:** (1) z oryginalnego zapisanego Master i Material Functions odczytać rzeczywiste shadery oraz sampler swizzles, (2) dopiero na tej podstawie sporządzić D/N/ORD(p) packing do 3 × pięcioelementowej Texture2DArray, **nie zakładać że ORM/ARM = ORD(p)**, (3) albedo sRGB, normals DX linear + UE Normal compression, mask pack linear + Masks compression, 2K consistent dims, mipmaps i normal green channel; (4) tymczasowy katalog UE, żadnego overwrite aktywnych 3 arrays, readback SourceTextures i per slice sample; (5) monitor texture streaming pool/VRAM, bez podnoszenia PoolSize na ślepo (wcześniej +~853MiB over budget).  
**PASS:** trzy pełne i nie-diagnostyczne arrays, 5/5 layers, 2K consistent, poprawny packing/readback i material preview shader compile. **FAIL:** domyślne szare array slice, losowe swizzle, odwrócone normals, pusta alpha, LFS bez praw.

### F7 — UE master i izolowana MI PEGASUS/YACS [P0]
Wersjonowany `M_Landscape_YACS` zachowuje zgodność **257 wspólnych expression/links** z oryginałem; YACS dodaje widoczność i usuwa nieużyte grass output. Nie produkować innego custom master. Duplikować original instance do izolowanego testowego MI, zachować 5 layers/4 blends i associations/GUID/slot indexes.
**Filmowe finalne wartości do porównania** (nie do ślepej podmiany): Detail Brightness=5, UV Distort=1, Specular Falloff Exponent=1, Global Brightness=.5, Global Colour Strength=.5, Global Saturation=.5, Global Normal Flatten=0, Global Specular Scale=1, Macro Tiling=.05, Num IDmap Layers=5. ZIP defaults i video-final są różne. Demo UV Rotate=-90, Terrain Resolution=2016, Offset 1047/1080 nie mogą nadpisać zarejestrowanej geografii YACS.  
**Operacje:** readback assoc/index/ExpressionGUID i input bindings; MI changes tylko candidate / transient viewport, wymuszona shader compilation, 4 Landscape actors i render in editor. Zrobić A/B normal flatten0 vs obecny1 na pionowym wapieniu; rollback przy błędzie. Nie zmieniać aktywnej mapy przed PASS.  
**PASS:** kompilacja, rzeczywiste źródła 3 arrays, 5/4 layers, poprawna rejestracja, MI readback z aktualnego edytora i zero zmian pakietów/aktora przez preview.

### F8 — Native full-world UE Lit visual proof [P0]
W jednym właściwym edytorze (bez restartu i konkurenta Live Host) zapisać świeże screenshoty nie starszych prób. **Macierz minimum:**
1. 4 aktory Landscape, panorama całych 8km, widok nie może pokazywać wyłącznie nieba.
2. Serpentyna/hairpin: road contact, matowy asfalt, szary żwir pobocza, erozja, szew pobocze/klif.
3. Stromy ciemnoszary klif: normal detail, brak vertical streak i niepoprawnie rozciągniętej UV.
4. Piarg na prawdziwym Stage3 mask (w tym rzadkie 0.5+ cells).
5. Wybrzeże z prawdziwym sand_mask>0 i materiałem piasku.
6. Trawa, strefa przejścia rock↔grass i tints.
7. Centralny styk czterech UE kafli, osobny ID/Alpha debug i Lit.
8. Punkt z wysokości kierownicy/TPP oraz macro/medium/daleki dystans do oceny detalu.
**Każdy zrzut:** current PID/SID, world, camera transform, UTC timestamp, shader/MI asset path+SHA, renderer/Lit mode, lighting/exposure snapshot, źródłowe doc cache run, PNG SHA. A/B zawsze identyczna kamera/exposure i sun. Poprawiać błędną geometrię tylko lokalnie i oddzielnym zgodnym źródłem, globalne Landscape freeze.
**PASS:** brak black valid/pionowych smug, poprawne warstwy i brak znikających aktorów, ciekawe matowe ciemnoszare wapienie, rzadki prawdziwy scree, naturalne przejścia, nieprzekroczony texture streaming; owner visual acceptance pozostaje osobną bramką. **FAIL:** wyłącznie screenshot materiału zamiast Lit world, stary stale screenshot, błędy seam, glossy asphalt lub brak geometry contact.

### F9 — Retencja, rollback, CI i ogłoszenie wyniku [P0]
Każde nowe binarium ma source provenance, SHA-256, manifest plus Git LFS OID (weryfikacja real LFS server readback); nie commitować źródeł na zwykłego Gita. W końcowym raporcie: oryginalny HDA i adaptacje, finalny graf z różnicami, 16k colour/ID/AO, 3 UE arrays, shader final MI, native screenshot galeria, lighting, 4 UE actor snapshot, cache hashes, CI, full readback i plan rollback. PR #474 **Draft** dopóki nie będzie G00–G11 PASS, nie scalać samodzielnie. Performance after M3 w oddzielnej bramce i bez fałszywego PASS.

## D. Macierz PASS/FAIL, nie deklaracje sukcesu

| Gate | Obecny stan | Minimalny obowiązkowy dowód |
|---|---|---|
| G00 | PASS source only | 45 PBR map hashes, original HDA hash and header |
| G01 | PASS bounded real crop | stage1+stage2 16k pins and 256² coordinates/voxel samples |
| G02 | PASS diagnostic; production BLOCKED | actual Stage3 scree source registration + upstream lineage |
| G03 | PASS with proxy; true scree **UNVERIFIED** | five real 256² materials with actual scree and source-mask hashes |
| G04 | TODO | full source-like HDA Mask/Tint graph and all known/unknown parms |
| G05 | TODO | new cliff neutral-grey/no black/roughness/normal A/B proof |
| G06 | TODO | 3 real semantic sites, incl coast with sand>0 |
| G07 | TODO | 100% 16000² Houdini producer with 4 Landscape seams and intact base |
| G08 | TODO | UE D/N/ORD(p) packed 3 arrays, 5×2K, true slices, compression |
| G09 | TODO | isolated original master/MI candidate and shader compile/readback |
| G10 | TODO | fresh UE Lit screenshots at real 8 site types and native data |
| G11 | TODO | separate user-approved final visual review |
| G12 | DEFERRED AFTER M3 | distinct performance/VRAM/fps gate |

**Nie promować:** G03 do G07, ponieważ pięć HDA gotowych na 256² nie jest 16k. G10 nie jest PASS na podstawie testów CPU/shader compile. Brak source proof = BLOCKED, nie „prawie PASS”.

## E. Rozdział pracy dla słabszych LLM/subagentów

**Integrator/writer jedyny:** scala patch, chroni jedno źródło HDA, na jednym HEAD wykonuje każdą mutację, nigdy równolegle graf/UE map. Każdy podagent pracuje **READ-ONLY**, oddaje konkretny manifest/raport i minimalny patch do review; nie rusza C:, nie modyfikuje mapy/UE bez procesu autoryzowanego.

**A — Scree+Sand source.** Wejścia: audit_l07_scree_cache.py, verify_l07_scree_crop.py, 16K historical Stage3 provenance oraz run 39794174742. Wyjście: upstream lineage report, autentyczne 3 material-sites z maskami >0, candidate source hashes. Nie ustala kolorów.

**B — Houdini graph.** Wejścia: author-material-observations, graph-followup-20261022, oryginalne HDA hashes i PE-02-03/04/05 caption. Wyjście: dokładna lista node/parm/input, odrębne UNKNOWN i source-timestamp dla każdej liczby, minimalny adapter bez zmiany oryginalnego HDA. Wykonywanie full 16k zabronione przed F3.

**C — Materiał/kolor.** Wejścia: real five-HDA proof images oraz statystyka RGB, PBR 4K, true mask source. Wyjście: before/after fixed camera, histogram mask-weighted i jedna odwracalna grade/correction, no gloss, no dark-black cliff. Bez wymyślania parametrów „z filmu”.

**D — Unreal arrays & shader (READ ONLY).** Wejścia: original master/MI/texture arrays, material contract GUIDs, 5 CC0 UE sources. Wyjście: przegląd dokładnego ORDp swizzle/pins/normal compression/mips/sRGB, 5 layer + 4 blend parameter associations i konkretny manifest pod izolowany import. Nie startuje drugiego UE.

**Wspólny szablon oddania prac:** `SOURCE_COMMIT`, `FILES_READ`, `NATIVE_VERIFICATION`, `SOURCE_VIDEO_TIMESTAMP`, `PROPOSED_CHANGE`, `UNKNOWN`, `SAFETY_INVARIANTS`, `PASS_FAIL`, `OUTPUT_SHA256`, `ROLLBACK`. Nie mówić, że graf lub materiał został ukończony, jeśli wykonano tylko analizę.

## F. Ścieżka krytyczna na teraz

1. Rozstrzygnąć ostatni run five HDA z rzeczywistą Stage3 mask — jeśli workflow `startup_failure`, jest to błąd uruchomienia, **nie** dowód błędu shaderu. Powtórzyć wyłącznie po weryfikacji host concurrency i exact SHA.
2. Zamknąć Stage3 upstream lineage lub oznaczyć ją jawnie diagnostyczną; znaleźć real sand>0 i cliff vertical site.
3. Dopiero potem przygotować pełną sieć tint/mask oryginalnym HDA i A/B neutral-grey cliffs.
4. Cały 16000² authoring z pamięcią i geograficznym seam proof, następnie 3 UE arrays i final MI.
5. Dopiero finalny Lit, galeria i przyjęcie przez użytkownika.

**Zabronione:** nowy blender-first pipeline, duplikowanie PR, wielokrotne naprawianie jednego błędu przez miarowe podnoszenie UE scalarów, reset runnera bez właściciela, commit z niezweryfikowanymi 0.9 GB binariów, każde „wynik wizualny PASS” bez świeżego natywnego screenshotu.
